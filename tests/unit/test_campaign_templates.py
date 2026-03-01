"""Unit tests for campaign template routes (BL-037)."""

import json

from tests.conftest import auth_header


def _headers(client):
    headers = auth_header(client)
    headers["X-Namespace"] = "test-corp"
    return headers


def _create_campaign_with_steps(client, headers):
    """Create a campaign and give it template_config with steps."""
    resp = client.post("/api/campaigns", headers=headers, json={"name": "My Campaign"})
    campaign_id = resp.get_json()["id"]

    steps = [
        {
            "step": 1,
            "channel": "email",
            "label": "Cold Email",
            "enabled": True,
            "needs_pdf": False,
            "variant_count": 1,
        },
        {
            "step": 2,
            "channel": "linkedin",
            "label": "LinkedIn",
            "enabled": True,
            "needs_pdf": False,
            "variant_count": 1,
        },
    ]
    gen_config = {
        "tone": "professional",
        "language": "en",
        "strategy_snapshot": {"data": True},
        "cancelled": False,
    }

    client.patch(
        f"/api/campaigns/{campaign_id}",
        headers=headers,
        json={"template_config": steps, "generation_config": gen_config},
    )
    return campaign_id


class TestListCampaignTemplates:
    def test_list_empty(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.get("/api/campaign-templates", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["templates"] == []


class TestCreateCampaignTemplate:
    def test_create_template(self, client, seed_companies_contacts):
        headers = _headers(client)
        steps = [{"step": 1, "channel": "email", "label": "Email", "enabled": True}]

        resp = client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "name": "My Template",
                "description": "A test template",
                "steps": steps,
                "default_config": {"tone": "casual"},
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "My Template"
        assert data["description"] == "A test template"
        assert len(data["steps"]) == 1
        assert data["is_system"] is False
        assert "id" in data

    def test_create_requires_name(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "steps": [{"step": 1}],
            },
        )
        assert resp.status_code == 400
        assert "name" in resp.get_json()["error"].lower()

    def test_create_requires_steps(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "name": "No Steps",
            },
        )
        assert resp.status_code == 400
        assert "steps" in resp.get_json()["error"].lower()

    def test_create_rejects_empty_steps(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "name": "Empty Steps",
                "steps": [],
            },
        )
        assert resp.status_code == 400

    def test_created_template_appears_in_list(self, client, seed_companies_contacts):
        headers = _headers(client)
        client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "name": "Listed Template",
                "steps": [{"step": 1, "channel": "email"}],
            },
        )

        resp = client.get("/api/campaign-templates", headers=headers)
        templates = resp.get_json()["templates"]
        names = [t["name"] for t in templates]
        assert "Listed Template" in names


class TestSaveAsTemplate:
    def test_save_campaign_as_template(self, client, seed_companies_contacts):
        headers = _headers(client)
        campaign_id = _create_campaign_with_steps(client, headers)

        resp = client.post(
            f"/api/campaigns/{campaign_id}/save-as-template",
            headers=headers,
            json={"name": "Saved Template", "description": "From campaign"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Saved Template"
        assert "id" in data

    def test_save_strips_runtime_keys(self, client, seed_companies_contacts):
        headers = _headers(client)
        campaign_id = _create_campaign_with_steps(client, headers)

        client.post(
            f"/api/campaigns/{campaign_id}/save-as-template",
            headers=headers,
            json={"name": "Clean Template"},
        )

        # Fetch the template to verify
        resp = client.get("/api/campaign-templates", headers=headers)
        templates = resp.get_json()["templates"]
        tpl = next(t for t in templates if t["name"] == "Clean Template")
        assert "strategy_snapshot" not in tpl["default_config"]
        assert "cancelled" not in tpl["default_config"]
        assert tpl["default_config"].get("tone") == "professional"

    def test_save_default_name(self, client, seed_companies_contacts):
        headers = _headers(client)
        campaign_id = _create_campaign_with_steps(client, headers)

        resp = client.post(
            f"/api/campaigns/{campaign_id}/save-as-template",
            headers=headers,
            json={},
        )
        assert resp.status_code == 201
        assert resp.get_json()["name"] == "My Campaign Template"

    def test_save_campaign_no_steps_fails(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post("/api/campaigns", headers=headers, json={"name": "Empty"})
        campaign_id = resp.get_json()["id"]

        resp = client.post(
            f"/api/campaigns/{campaign_id}/save-as-template",
            headers=headers,
            json={"name": "Should Fail"},
        )
        assert resp.status_code == 400

    def test_save_nonexistent_campaign(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000000/save-as-template",
            headers=headers,
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404


class TestUpdateCampaignTemplate:
    def test_rename_template(self, client, seed_companies_contacts):
        headers = _headers(client)

        # Create template
        resp = client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "name": "Old Name",
                "steps": [{"step": 1}],
            },
        )
        tpl_id = resp.get_json()["id"]

        # Rename
        resp = client.patch(
            f"/api/campaign-templates/{tpl_id}",
            headers=headers,
            json={"name": "New Name"},
        )
        assert resp.status_code == 200

        # Verify
        resp = client.get("/api/campaign-templates", headers=headers)
        names = [t["name"] for t in resp.get_json()["templates"]]
        assert "New Name" in names
        assert "Old Name" not in names

    def test_rename_empty_rejected(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "name": "Template",
                "steps": [{"step": 1}],
            },
        )
        tpl_id = resp.get_json()["id"]

        resp = client.patch(
            f"/api/campaign-templates/{tpl_id}",
            headers=headers,
            json={"name": ""},
        )
        assert resp.status_code == 400

    def test_no_fields_rejected(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "name": "Template",
                "steps": [{"step": 1}],
            },
        )
        tpl_id = resp.get_json()["id"]

        resp = client.patch(
            f"/api/campaign-templates/{tpl_id}",
            headers=headers,
            json={},
        )
        assert resp.status_code == 400


class TestDeleteCampaignTemplate:
    def test_delete_own_template(self, client, seed_companies_contacts):
        headers = _headers(client)

        # Create template
        resp = client.post(
            "/api/campaign-templates",
            headers=headers,
            json={
                "name": "To Delete",
                "steps": [{"step": 1}],
            },
        )
        tpl_id = resp.get_json()["id"]

        # Delete
        resp = client.delete(f"/api/campaign-templates/{tpl_id}", headers=headers)
        assert resp.status_code == 200

        # Verify gone
        resp = client.get("/api/campaign-templates", headers=headers)
        ids = [t["id"] for t in resp.get_json()["templates"]]
        assert tpl_id not in ids

    def test_delete_nonexistent(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.delete(
            "/api/campaign-templates/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_cannot_delete_system_template(self, client, seed_companies_contacts, db):
        """System templates (is_system=True) cannot be deleted."""
        from api.models import CampaignTemplate

        headers = _headers(client)

        # Insert a system template directly
        tpl = CampaignTemplate(
            tenant_id=None,
            name="System Default",
            steps=json.dumps([{"step": 1, "channel": "email"}]),
            default_config=json.dumps({}),
            is_system=True,
        )
        db.session.add(tpl)
        db.session.commit()

        resp = client.delete(f"/api/campaign-templates/{tpl.id}", headers=headers)
        assert resp.status_code == 403
        assert "system" in resp.get_json()["error"].lower()
