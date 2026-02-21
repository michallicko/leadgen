"""Tests for Playbook API endpoints."""
import json
from unittest.mock import patch, MagicMock


def auth_header(client, email="admin@test.com", password="testpass123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestGetPlaybook:
    def test_auto_creates_document(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "draft"
        assert data["version"] == 1
        assert "id" in data

    def test_returns_existing_document(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Strategy\n\nExisting content.",
            status="active",
            version=3,
        )
        db.session.add(doc)
        db.session.commit()
        resp = client.get("/api/playbook", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "active"
        assert data["version"] == 3

    def test_tenant_isolation(self, client, seed_tenant, seed_super_admin, db):
        from api.models import Tenant, StrategyDocument
        headers = auth_header(client)
        other = Tenant(name="Other", slug="other-corp", is_active=True)
        db.session.add(other)
        db.session.commit()
        doc = StrategyDocument(tenant_id=other.id, content="secret content")
        db.session.add(doc)
        db.session.commit()
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook", headers=headers)
        data = resp.get_json()
        assert data.get("content") != "secret content"

    def test_requires_auth(self, client, seed_tenant):
        resp = client.get("/api/playbook", headers={"X-Namespace": seed_tenant.slug})
        assert resp.status_code == 401


class TestUpdatePlaybook:
    def test_save_document(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(tenant_id=seed_tenant.id, version=1)
        db.session.add(doc)
        db.session.commit()
        resp = client.put("/api/playbook", json={
            "content": "# Updated Strategy\n\nNew content here.",
            "version": 1,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == 2

    def test_optimistic_lock_conflict(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(tenant_id=seed_tenant.id, version=3)
        db.session.add(doc)
        db.session.commit()
        resp = client.put("/api/playbook", json={
            "content": "# Strategy",
            "version": 1,
        }, headers=headers)
        assert resp.status_code == 409
        data = resp.get_json()
        assert "conflict" in data["error"].lower()

    def test_version_required(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc)
        db.session.commit()
        resp = client.put("/api/playbook", json={"content": "# Strategy"}, headers=headers)
        assert resp.status_code == 400


class TestPlaybookChat:
    def test_get_empty_chat_history(self, client, seed_tenant, seed_super_admin):
        """GET /api/playbook/chat returns empty messages when no chat exists."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook/chat", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["messages"] == []

    @patch("api.routes.playbook_routes._get_anthropic_client")
    def test_post_message_creates_pair(self, mock_get_client, client, seed_tenant, seed_super_admin):
        """POST /api/playbook/chat creates user + assistant message pair (non-streaming)."""
        # Mock the AnthropicClient.stream_query to yield text chunks
        mock_client = MagicMock()
        mock_client.stream_query.return_value = iter(["Your ICP ", "should focus on ", "enterprise SaaS."])
        mock_get_client.return_value = mock_client

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/playbook/chat",
            json={"message": "What is our ICP?"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["content"] == "What is our ICP?"
        assert data["assistant_message"]["role"] == "assistant"
        assert data["assistant_message"]["content"] == "Your ICP should focus on enterprise SaaS."

        # Verify stream_query was called with correct args
        mock_client.stream_query.assert_called_once()
        call_kwargs = mock_client.stream_query.call_args
        assert call_kwargs.kwargs["max_tokens"] == 4096
        # Messages should end with the user message
        msgs = call_kwargs.kwargs["messages"]
        assert msgs[-1] == {"role": "user", "content": "What is our ICP?"}

    @patch("api.routes.playbook_routes._get_anthropic_client")
    def test_post_message_streaming(self, mock_get_client, client, seed_tenant, seed_super_admin):
        """POST /api/playbook/chat with Accept: text/event-stream returns SSE."""
        mock_client = MagicMock()
        mock_client.stream_query.return_value = iter(["Hello ", "world!"])
        mock_get_client.return_value = mock_client

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        headers["Accept"] = "text/event-stream"
        resp = client.post(
            "/api/playbook/chat",
            json={"message": "Hello"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/event-stream")

        # Parse SSE events from the response data
        raw = resp.get_data(as_text=True)
        events = [
            line[len("data: "):]
            for line in raw.strip().split("\n")
            if line.startswith("data: ")
        ]
        assert len(events) == 3  # 2 chunks + 1 done

        chunk1 = json.loads(events[0])
        assert chunk1["type"] == "chunk"
        assert chunk1["text"] == "Hello "

        chunk2 = json.loads(events[1])
        assert chunk2["type"] == "chunk"
        assert chunk2["text"] == "world!"

        done = json.loads(events[2])
        assert done["type"] == "done"
        assert "message_id" in done

    @patch("api.routes.playbook_routes._get_anthropic_client")
    def test_post_message_llm_error_non_streaming(self, mock_get_client, client, seed_tenant, seed_super_admin):
        """POST /api/playbook/chat handles LLM errors gracefully in non-streaming mode."""
        mock_client = MagicMock()
        mock_client.stream_query.side_effect = Exception("API rate limited")
        mock_get_client.return_value = mock_client

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/playbook/chat",
            json={"message": "What is our ICP?"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user_message"]["content"] == "What is our ICP?"
        # Assistant message should be an error fallback
        assert "error" in data["assistant_message"]["content"].lower()

    def test_chat_history_ordered(self, client, seed_tenant, seed_super_admin, db):
        """GET /api/playbook/chat returns messages in chronological order."""
        from datetime import datetime, timedelta
        from api.models import StrategyDocument, StrategyChatMessage

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(tenant_id=seed_tenant.id, status="draft")
        db.session.add(doc)
        db.session.flush()

        now = datetime.utcnow()
        msgs = [
            StrategyChatMessage(
                tenant_id=seed_tenant.id, document_id=doc.id,
                role="user", content="First message",
                created_at=now - timedelta(minutes=2),
            ),
            StrategyChatMessage(
                tenant_id=seed_tenant.id, document_id=doc.id,
                role="assistant", content="First reply",
                created_at=now - timedelta(minutes=1),
            ),
            StrategyChatMessage(
                tenant_id=seed_tenant.id, document_id=doc.id,
                role="user", content="Second message",
                created_at=now,
            ),
        ]
        db.session.add_all(msgs)
        db.session.commit()

        resp = client.get("/api/playbook/chat", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 3
        assert data["messages"][0]["content"] == "First message"
        assert data["messages"][1]["content"] == "First reply"
        assert data["messages"][2]["content"] == "Second message"

    def test_chat_requires_auth(self, client, seed_tenant):
        """GET and POST /api/playbook/chat return 401 without token."""
        headers = {"X-Namespace": seed_tenant.slug}
        resp_get = client.get("/api/playbook/chat", headers=headers)
        assert resp_get.status_code == 401
        resp_post = client.post(
            "/api/playbook/chat",
            json={"message": "hello"},
            headers=headers,
        )
        assert resp_post.status_code == 401

    def test_post_requires_message(self, client, seed_tenant, seed_super_admin):
        """POST /api/playbook/chat returns 400 if no message field."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/chat", json={}, headers=headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "message" in data["error"].lower()


class TestPlaybookExtract:
    @patch("api.routes.playbook_routes._get_anthropic_client")
    def test_extract_returns_structured_data(self, mock_get_client, client, seed_tenant, seed_super_admin, db):
        """POST /api/playbook/extract calls LLM and saves extracted_data."""
        from api.models import StrategyDocument

        # Create a document with some content
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Executive Summary\n\nWe sell AI to enterprise SaaS.",
            status="active",
            version=2,
        )
        db.session.add(doc)
        db.session.commit()

        # Mock the AnthropicClient.query to return valid JSON
        extracted = {
            "icp": {
                "industries": ["SaaS", "FinTech"],
                "company_size": {"min": 50, "max": 500},
                "geographies": ["DACH", "UK"],
                "tech_signals": ["AI adoption"],
                "triggers": ["Series B"],
                "disqualifiers": ["No budget"],
            },
            "personas": [
                {
                    "title_patterns": ["CTO", "VP Engineering"],
                    "pain_points": ["Scaling AI"],
                    "goals": ["Reduce costs"],
                }
            ],
            "messaging": {
                "tone": "consultative",
                "themes": ["AI transformation"],
                "angles": ["ROI-driven"],
                "proof_points": ["3x revenue increase"],
            },
            "channels": {
                "primary": "LinkedIn",
                "secondary": ["Email"],
                "cadence": "3 touches per week",
            },
            "metrics": {
                "reply_rate_target": 0.15,
                "meeting_rate_target": 0.05,
                "pipeline_goal_eur": 500000,
                "timeline_months": 6,
            },
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps(extracted)
        mock_client.query.return_value = mock_response
        mock_get_client.return_value = mock_client

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/extract", headers=headers)

        assert resp.status_code == 200
        data = resp.get_json()
        assert "extracted_data" in data
        assert data["extracted_data"]["icp"]["industries"] == ["SaaS", "FinTech"]
        assert data["extracted_data"]["channels"]["primary"] == "LinkedIn"
        assert "version" in data

        # Verify it was saved to the database
        db.session.expire_all()
        saved_doc = StrategyDocument.query.filter_by(tenant_id=seed_tenant.id).first()
        saved_extracted = saved_doc.extracted_data
        if isinstance(saved_extracted, str):
            saved_extracted = json.loads(saved_extracted)
        assert saved_extracted["icp"]["industries"] == ["SaaS", "FinTech"]

    def test_extract_requires_auth(self, client, seed_tenant):
        """POST /api/playbook/extract returns 401 without token."""
        headers = {"X-Namespace": seed_tenant.slug}
        resp = client.post("/api/playbook/extract", headers=headers)
        assert resp.status_code == 401

    def test_extract_404_when_no_document(self, client, seed_tenant, seed_super_admin):
        """POST /api/playbook/extract returns 404 when no strategy document exists."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/extract", headers=headers)
        assert resp.status_code == 404

    @patch("api.routes.playbook_routes._get_anthropic_client")
    def test_extract_handles_invalid_json(self, mock_get_client, client, seed_tenant, seed_super_admin, db):
        """POST /api/playbook/extract returns 422 when LLM returns invalid JSON."""
        from api.models import StrategyDocument

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="## ICP\n\nsome data",
            status="active",
        )
        db.session.add(doc)
        db.session.commit()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON at all!"
        mock_client.query.return_value = mock_response
        mock_get_client.return_value = mock_client

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/extract", headers=headers)

        assert resp.status_code == 422
        data = resp.get_json()
        assert "error" in data

    @patch("api.routes.playbook_routes._get_anthropic_client")
    def test_extract_strips_markdown_fences(self, mock_get_client, client, seed_tenant, seed_super_admin, db):
        """POST /api/playbook/extract handles LLM wrapping JSON in markdown fences."""
        from api.models import StrategyDocument

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Executive Summary\n\nWe do things.",
            status="active",
            version=1,
        )
        db.session.add(doc)
        db.session.commit()

        extracted = {
            "icp": {"industries": ["SaaS"], "company_size": {"min": 0, "max": 0},
                     "geographies": [], "tech_signals": [], "triggers": [], "disqualifiers": []},
            "personas": [],
            "messaging": {"tone": "", "themes": [], "angles": [], "proof_points": []},
            "channels": {"primary": "", "secondary": [], "cadence": ""},
            "metrics": {"reply_rate_target": 0.0, "meeting_rate_target": 0.0,
                        "pipeline_goal_eur": 0, "timeline_months": 0},
        }

        # LLM wraps the JSON in markdown code fences
        fenced_json = "```json\n{}\n```".format(json.dumps(extracted))

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = fenced_json
        mock_client.query.return_value = mock_response
        mock_get_client.return_value = mock_client

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/extract", headers=headers)

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["extracted_data"]["icp"]["industries"] == ["SaaS"]


class TestPlaybookResearch:
    """Tests for POST/GET /api/playbook/research endpoints."""

    @patch("api.routes.playbook_routes.threading")
    def test_trigger_research_creates_self_company(self, mock_threading, client, seed_tenant, seed_super_admin, db):
        """POST /api/playbook/research creates a company with is_self=True."""
        from api.models import Company

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/playbook/research",
            json={"domain": "testcorp.com"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "triggered"
        assert data["domain"] == "testcorp.com"
        assert "company_id" in data

        # Verify the company was created with is_self=True
        company = db.session.get(Company, data["company_id"])
        assert company is not None
        assert company.is_self is True
        assert company.domain == "testcorp.com"
        assert company.tenant_id == seed_tenant.id

        # Verify background thread was started
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()

    @patch("api.routes.playbook_routes.threading")
    def test_trigger_research_saves_objective(self, mock_threading, client, seed_tenant, seed_super_admin, db):
        """POST /api/playbook/research saves the objective to the document."""
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/playbook/research",
            json={"domain": "testcorp.com", "objective": "Grow pipeline 3x"},
            headers=headers,
        )
        assert resp.status_code == 200

        doc = StrategyDocument.query.filter_by(tenant_id=seed_tenant.id).first()
        assert doc is not None
        assert doc.objective == "Grow pipeline 3x"

    @patch("api.routes.playbook_routes.threading")
    def test_trigger_research_links_to_document(self, mock_threading, client, seed_tenant, seed_super_admin, db):
        """POST /api/playbook/research sets the document's enrichment_id."""
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/playbook/research",
            json={"domain": "testcorp.com"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()

        # Verify the strategy document's enrichment_id is set
        doc = StrategyDocument.query.filter_by(tenant_id=seed_tenant.id).first()
        assert doc is not None
        assert doc.enrichment_id == data["company_id"]

    @patch("api.routes.playbook_routes.threading")
    def test_trigger_research_reuses_existing(self, mock_threading, client, seed_tenant, seed_super_admin, db):
        """POST /api/playbook/research twice doesn't create duplicate companies."""
        from api.models import Company

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp1 = client.post(
            "/api/playbook/research",
            json={"domain": "testcorp.com"},
            headers=headers,
        )
        assert resp1.status_code == 200
        company_id_1 = resp1.get_json()["company_id"]

        resp2 = client.post(
            "/api/playbook/research",
            json={"domain": "testcorp.com"},
            headers=headers,
        )
        assert resp2.status_code == 200
        company_id_2 = resp2.get_json()["company_id"]

        # Same company should be returned
        assert company_id_1 == company_id_2

        # Only one is_self company for this tenant
        count = Company.query.filter_by(
            tenant_id=seed_tenant.id, is_self=True
        ).count()
        assert count == 1

    @patch("api.routes.playbook_routes.threading")
    def test_trigger_research_uses_tenant_domain_as_fallback(self, mock_threading, client, seed_super_admin, db):
        """POST /api/playbook/research without domain uses tenant's domain."""
        from api.models import Tenant, Company

        # Create tenant with a domain
        tenant = Tenant(name="Domain Corp", slug="domain-corp", domain="domaincorp.com", is_active=True)
        db.session.add(tenant)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        resp = client.post(
            "/api/playbook/research",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["domain"] == "domaincorp.com"

        company = db.session.get(Company, data["company_id"])
        assert company.domain == "domaincorp.com"

    def test_trigger_research_requires_domain(self, client, seed_tenant, seed_super_admin, db):
        """POST /api/playbook/research returns 400 when no domain and tenant has no domain."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            "/api/playbook/research",
            json={},
            headers=headers,
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "domain" in data["error"].lower()

    def test_get_research_not_started(self, client, seed_tenant, seed_super_admin, db):
        """GET /api/playbook/research returns not_started when no enrichment linked."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook/research", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "not_started"

    def test_get_research_with_company(self, client, seed_tenant, seed_super_admin, db):
        """GET /api/playbook/research returns company info when linked."""
        from api.models import Company, StrategyDocument

        # Create a self-company with enriched status
        company = Company(
            tenant_id=seed_tenant.id,
            name="Test Corp",
            domain="testcorp.com",
            status="enriched_l2",
            tier="tier_1_platinum",
            is_self=True,
        )
        db.session.add(company)
        db.session.flush()

        # Create strategy document linked to company
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            enrichment_id=company.id,
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook/research", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["company"]["name"] == "Test Corp"
        assert data["company"]["domain"] == "testcorp.com"
        assert data["company"]["tier"] == "tier_1_platinum"

    def test_research_requires_auth(self, client, seed_tenant):
        """GET and POST /api/playbook/research return 401 without token."""
        headers = {"X-Namespace": seed_tenant.slug}
        resp_get = client.get("/api/playbook/research", headers=headers)
        assert resp_get.status_code == 401
        resp_post = client.post(
            "/api/playbook/research",
            json={"domain": "test.com"},
            headers=headers,
        )
        assert resp_post.status_code == 401
