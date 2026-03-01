"""Tests for Strategy Template API endpoints."""
import json
from unittest.mock import patch, MagicMock


def auth_header(client, email="admin@test.com", password="testpass123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_template(db, tenant_id=None, name="Test Template", is_system=False):
    from api.models import StrategyTemplate

    tpl = StrategyTemplate(
        tenant_id=tenant_id,
        name=name,
        description="A test template",
        category="Testing",
        content_template="## Section One\n\nContent for {{company}}.\n\n## Section Two\n\nMore content.",
        extracted_data_template=json.dumps({"icp": "B2B SaaS"}),
        is_system=is_system,
    )
    db.session.add(tpl)
    db.session.commit()
    return tpl


def _create_strategy_doc(db, tenant_id, content="# My Strategy\n\nSome content."):
    from api.models import StrategyDocument

    doc = StrategyDocument(
        tenant_id=tenant_id,
        content=content,
        status="active",
        version=1,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


class TestListStrategyTemplates:
    def test_returns_system_and_tenant_templates(self, client, seed_tenant, seed_super_admin, db):
        _create_template(db, tenant_id=None, name="System GTM", is_system=True)
        _create_template(db, tenant_id=seed_tenant.id, name="My Template")

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/strategy-templates", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        names = {t["name"] for t in data}
        assert "System GTM" in names
        assert "My Template" in names

    def test_includes_section_headers(self, client, seed_tenant, seed_super_admin, db):
        _create_template(db, tenant_id=None, name="With Sections", is_system=True)

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/strategy-templates", headers=headers)
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["section_headers"] == ["Section One", "Section Two"]

    def test_tenant_isolation(self, client, seed_tenant, seed_super_admin, db):
        from api.models import Tenant

        other = Tenant(name="Other Corp", slug="other-corp", is_active=True)
        db.session.add(other)
        db.session.commit()
        _create_template(db, tenant_id=other.id, name="Other's Template")

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/strategy-templates", headers=headers)
        data = resp.get_json()
        assert len(data) == 0

    def test_requires_auth(self, client, seed_tenant):
        resp = client.get("/api/strategy-templates", headers={"X-Namespace": seed_tenant.slug})
        assert resp.status_code == 401


class TestGetStrategyTemplate:
    def test_returns_template_with_content(self, client, seed_tenant, seed_super_admin, db):
        tpl = _create_template(db, tenant_id=None, name="Full Template", is_system=True)

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get(f"/api/strategy-templates/{tpl.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Full Template"
        assert "content_template" in data
        assert "## Section One" in data["content_template"]

    def test_404_for_missing_template(self, client, seed_tenant, seed_super_admin, db):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/strategy-templates/nonexistent-id", headers=headers)
        assert resp.status_code == 404

    def test_tenant_isolation(self, client, seed_tenant, seed_super_admin, db):
        from api.models import Tenant

        other = Tenant(name="Other Corp", slug="other-corp", is_active=True)
        db.session.add(other)
        db.session.commit()
        tpl = _create_template(db, tenant_id=other.id, name="Other's Private")

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get(f"/api/strategy-templates/{tpl.id}", headers=headers)
        assert resp.status_code == 404


class TestCreateStrategyTemplate:
    def test_creates_from_current_strategy(self, client, seed_tenant, seed_super_admin, db):
        _create_strategy_doc(db, seed_tenant.id, "# My GTM\n\n## Targeting\n\nB2B SaaS")

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/strategy-templates", json={
            "name": "Saved Framework",
            "description": "My reusable framework",
            "category": "Custom",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Saved Framework"
        assert data["is_system"] is False
        assert "## Targeting" in data["content_template"]

    def test_requires_name(self, client, seed_tenant, seed_super_admin, db):
        _create_strategy_doc(db, seed_tenant.id)

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/strategy-templates", json={}, headers=headers)
        assert resp.status_code == 400

    def test_requires_existing_strategy(self, client, seed_tenant, seed_super_admin, db):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/strategy-templates", json={
            "name": "Empty Save",
        }, headers=headers)
        assert resp.status_code == 400


class TestDeleteStrategyTemplate:
    def test_deletes_user_template(self, client, seed_tenant, seed_super_admin, db):
        tpl = _create_template(db, tenant_id=seed_tenant.id, name="Deletable")

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.delete(f"/api/strategy-templates/{tpl.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Verify it's gone
        resp2 = client.get(f"/api/strategy-templates/{tpl.id}", headers=headers)
        assert resp2.status_code == 404

    def test_cannot_delete_system_template(self, client, seed_tenant, seed_super_admin, db):
        tpl = _create_template(db, tenant_id=None, name="System", is_system=True)

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.delete(f"/api/strategy-templates/{tpl.id}", headers=headers)
        assert resp.status_code == 403

    def test_cannot_delete_other_tenants_template(self, client, seed_tenant, seed_super_admin, db):
        from api.models import Tenant

        other = Tenant(name="Other Corp", slug="other-corp", is_active=True)
        db.session.add(other)
        db.session.commit()
        tpl = _create_template(db, tenant_id=other.id, name="Other's")

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.delete(f"/api/strategy-templates/{tpl.id}", headers=headers)
        assert resp.status_code == 404


class TestApplyTemplate:
    def test_requires_template_id(self, client, seed_tenant, seed_super_admin, db):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/apply-template", json={}, headers=headers)
        assert resp.status_code == 400

    def test_404_for_missing_template(self, client, seed_tenant, seed_super_admin, db):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/apply-template", json={
            "template_id": "nonexistent",
        }, headers=headers)
        assert resp.status_code == 404

    @patch("api.routes.strategy_template_routes.AnthropicClient")
    @patch("api.routes.strategy_template_routes.log_llm_usage")
    def test_applies_template_with_ai_merge(
        self, mock_log, mock_client_cls,
        client, seed_tenant, seed_super_admin, db,
    ):
        import os
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        # Setup mock LLM response
        mock_response = MagicMock()
        mock_response.content = "# Personalized Strategy\n\n## Section One\n\nCustom content."
        mock_response.model = "claude-haiku-4-5-20251001"
        mock_response.input_tokens = 500
        mock_response.output_tokens = 1000
        mock_response.cost_usd = 0.001
        mock_client_cls.return_value.query.return_value = mock_response

        # Create template and doc
        tpl = _create_template(db, tenant_id=None, name="GTM Framework", is_system=True)
        _create_strategy_doc(db, seed_tenant.id, "# Old Strategy")

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/apply-template", json={
            "template_id": tpl.id,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["has_ai_edits"] is True
        assert data["applied_template"] == "GTM Framework"
        assert "Personalized Strategy" in data["content"]

        # Verify LLM usage was logged
        mock_log.assert_called_once()

    def test_requires_auth(self, client, seed_tenant):
        resp = client.post(
            "/api/playbook/apply-template",
            json={"template_id": "abc"},
            headers={"X-Namespace": seed_tenant.slug},
        )
        assert resp.status_code == 401
