"""Tests for the workflow state machine (BL-144)."""

import json

import pytest

from tests.conftest import auth_header


class TestGetWorkflowState:
    """GET /api/workflow/state — computed from actual data."""

    def test_no_strategy(self, client, seed_companies_contacts):
        """With no strategy doc, phase is no_strategy."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/workflow/state", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["current_phase"] == "no_strategy"
        assert body["completed_phases"] == []
        assert body["progress_pct"] == 0
        assert body["next_action"]["action"] == "create_strategy"
        assert "context" in body

    def test_strategy_draft(self, client, seed_companies_contacts):
        """With strategy content but no ICP, phase is strategy_draft."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Create a strategy document with content but no extracted ICP
        from api.models import StrategyDocument, db

        tenant_id = _get_tenant_id(client, headers)
        doc = StrategyDocument(
            tenant_id=tenant_id,
            content="# My GTM Strategy\n\nWe sell widgets.",
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.get("/api/workflow/state", headers=headers)
        body = resp.get_json()
        assert body["current_phase"] == "strategy_draft"
        assert "no_strategy" in body["completed_phases"]

    def test_strategy_ready(self, client, seed_companies_contacts):
        """With extracted ICP but no contacts, phase is strategy_ready."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        from api.models import StrategyDocument, db

        tenant_id = _get_tenant_id(client, headers)

        # Delete existing contacts to isolate the test
        db.session.execute(
            db.text("DELETE FROM contacts WHERE tenant_id = :t"), {"t": tenant_id}
        )

        doc = StrategyDocument(
            tenant_id=tenant_id,
            content="# Strategy\nFull strategy here.",
            extracted_data={"icp": {"industry": "SaaS", "size": "50-200"}},
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.get("/api/workflow/state", headers=headers)
        body = resp.get_json()
        assert body["current_phase"] == "strategy_ready"
        assert body["next_action"]["action"] == "import_contacts"

    def test_contacts_imported(self, client, seed_companies_contacts):
        """With contacts + ICP but no enrichment, phase is contacts_imported."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        from api.models import StrategyDocument, db

        tenant_id = _get_tenant_id(client, headers)

        doc = StrategyDocument(
            tenant_id=tenant_id,
            content="# Strategy",
            extracted_data={"icp": {"industry": "SaaS"}},
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        # seed_companies_contacts already creates contacts, so they exist
        resp = client.get("/api/workflow/state", headers=headers)
        body = resp.get_json()
        assert body["current_phase"] == "contacts_imported"
        assert body["next_action"]["action"] == "run_enrichment"
        assert body["context"]["contacts"]["total"] > 0

    def test_enrichment_done(self, client, seed_companies_contacts):
        """With enriched contacts, phase advances past enrichment."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        from api.models import StrategyDocument, db

        tenant_id = _get_tenant_id(client, headers)

        doc = StrategyDocument(
            tenant_id=tenant_id,
            content="# Strategy",
            extracted_data={"icp": {"industry": "SaaS"}},
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        # Mark some contacts as enriched
        db.session.execute(
            db.text(
                "UPDATE contacts SET processed_enrich = true WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )
        db.session.commit()

        resp = client.get("/api/workflow/state", headers=headers)
        body = resp.get_json()
        assert body["current_phase"] == "enrichment_done"
        assert body["next_action"]["action"] == "select_contacts"

    def test_qualified_reviewed(self, client, seed_companies_contacts):
        """With selected contacts in playbook, phase is qualified_reviewed."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        from api.models import Contact, StrategyDocument, db

        tenant_id = _get_tenant_id(client, headers)

        # Mark contacts enriched
        db.session.execute(
            db.text(
                "UPDATE contacts SET processed_enrich = true WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )

        # Get a contact ID for selection
        contact = Contact.query.filter_by(tenant_id=tenant_id).first()

        doc = StrategyDocument(
            tenant_id=tenant_id,
            content="# Strategy",
            extracted_data={"icp": {"industry": "SaaS"}},
            playbook_selections={
                "contacts": {"selected_ids": [str(contact.id)]}
            },
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.get("/api/workflow/state", headers=headers)
        body = resp.get_json()
        assert body["current_phase"] == "qualified_reviewed"
        assert body["next_action"]["action"] == "generate_messages"

    def test_requires_auth(self, client, db):
        resp = client.get("/api/workflow/state")
        assert resp.status_code == 401

    def test_response_structure(self, client, seed_companies_contacts):
        """Verify all expected fields are present."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/workflow/state", headers=headers)
        body = resp.get_json()

        assert "current_phase" in body
        assert "current_phase_label" in body
        assert "completed_phases" in body
        assert "total_phases" in body
        assert "progress_pct" in body
        assert "next_action" in body
        assert "context" in body
        assert isinstance(body["completed_phases"], list)
        assert isinstance(body["progress_pct"], int)
        assert 0 <= body["progress_pct"] <= 100


class TestAdvanceWorkflow:
    """POST /api/workflow/advance — record explicit transitions."""

    def test_advance_records_transition(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/workflow/advance",
            headers=headers,
            json={
                "to_phase": "strategy_draft",
                "trigger": "user_action",
                "metadata": {"note": "User started writing"},
            },
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["transition"]["to_phase"] == "strategy_draft"
        assert body["transition"]["trigger"] == "user_action"
        assert body["transition"]["metadata"]["note"] == "User started writing"
        assert "state" in body

    def test_advance_invalid_phase(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/workflow/advance",
            headers=headers,
            json={"to_phase": "invalid_phase"},
        )
        assert resp.status_code == 400
        assert "valid_phases" in resp.get_json()

    def test_advance_missing_phase(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/workflow/advance",
            headers=headers,
            json={},
        )
        assert resp.status_code == 400

    def test_advance_requires_auth(self, client, db):
        resp = client.post("/api/workflow/advance", json={"to_phase": "strategy_draft"})
        assert resp.status_code == 401


class TestWorkflowHistory:
    """GET /api/workflow/history — list transitions."""

    def test_empty_history(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/workflow/history", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["transitions"] == []

    def test_history_after_advance(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Record a transition
        client.post(
            "/api/workflow/advance",
            headers=headers,
            json={"to_phase": "strategy_draft", "trigger": "test"},
        )

        resp = client.get("/api/workflow/history", headers=headers)
        body = resp.get_json()
        assert len(body["transitions"]) == 1
        assert body["transitions"][0]["to_phase"] == "strategy_draft"

    def test_history_limit(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/workflow/history?limit=5", headers=headers)
        assert resp.status_code == 200

    def test_history_requires_auth(self, client, db):
        resp = client.get("/api/workflow/history")
        assert resp.status_code == 401


def _get_tenant_id(client, headers):
    """Helper to resolve tenant ID from auth context."""
    from api.models import Tenant

    tenant = Tenant.query.filter_by(slug="test-corp").first()
    return str(tenant.id)
