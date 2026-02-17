"""Unit tests for campaign CRUD routes."""
import json

from tests.conftest import auth_header


class TestListCampaigns:
    def test_list_empty(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/campaigns", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["campaigns"] == []

    def test_list_returns_created_campaigns(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Create two campaigns
        client.post("/api/campaigns", headers=headers, json={"name": "Alpha Campaign"})
        client.post("/api/campaigns", headers=headers, json={"name": "Beta Campaign"})

        resp = client.get("/api/campaigns", headers=headers)
        data = resp.get_json()
        assert len(data["campaigns"]) == 2
        names = {c["name"] for c in data["campaigns"]}
        assert "Alpha Campaign" in names
        assert "Beta Campaign" in names

    def test_list_excludes_archived(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Create and delete (archive) one campaign
        resp = client.post("/api/campaigns", headers=headers, json={"name": "Archived"})
        campaign_id = resp.get_json()["id"]
        client.delete(f"/api/campaigns/{campaign_id}", headers=headers)

        # Create another
        client.post("/api/campaigns", headers=headers, json={"name": "Active"})

        resp = client.get("/api/campaigns", headers=headers)
        data = resp.get_json()
        assert len(data["campaigns"]) == 1
        assert data["campaigns"][0]["name"] == "Active"

    def test_list_requires_auth(self, client, db):
        resp = client.get("/api/campaigns")
        assert resp.status_code == 401


class TestCreateCampaign:
    def test_create_basic(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={
            "name": "My Campaign",
            "description": "Test campaign",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "My Campaign"
        assert data["status"] == "Draft"
        assert "id" in data

    def test_create_name_required(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"description": "no name"})
        assert resp.status_code == 400
        assert "name" in resp.get_json()["error"].lower()

    def test_create_empty_name_rejected(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "  "})
        assert resp.status_code == 400

    def test_create_from_template(self, client, seed_companies_contacts, db):
        from api.models import CampaignTemplate
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Create a system template
        tpl = CampaignTemplate(
            name="Test Template",
            steps=json.dumps([{"step": 1, "channel": "email", "label": "Email 1", "enabled": True}]),
            default_config=json.dumps({"tone": "casual"}),
            is_system=True,
        )
        db.session.add(tpl)
        db.session.commit()

        resp = client.post("/api/campaigns", headers=headers, json={
            "name": "From Template",
            "template_id": tpl.id,
        })
        assert resp.status_code == 201

        # Verify template config was copied
        campaign_id = resp.get_json()["id"]
        detail = client.get(f"/api/campaigns/{campaign_id}", headers=headers)
        data = detail.get_json()
        assert len(data["template_config"]) == 1
        assert data["template_config"][0]["channel"] == "email"


class TestGetCampaign:
    def test_get_detail(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Detail Test"})
        campaign_id = resp.get_json()["id"]

        resp = client.get(f"/api/campaigns/{campaign_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Detail Test"
        assert data["status"] == "Draft"
        assert "contact_status_counts" in data
        assert data["total_contacts"] == 0

    def test_get_nonexistent(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/campaigns/00000000-0000-0000-0000-000000000099", headers=headers)
        assert resp.status_code == 404


class TestUpdateCampaign:
    def test_update_name_and_description(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Original"})
        campaign_id = resp.get_json()["id"]

        resp = client.patch(f"/api/campaigns/{campaign_id}", headers=headers, json={
            "name": "Updated",
            "description": "New desc",
        })
        assert resp.status_code == 200

        detail = client.get(f"/api/campaigns/{campaign_id}", headers=headers)
        data = detail.get_json()
        assert data["name"] == "Updated"
        assert data["description"] == "New desc"

    def test_valid_status_transition_draft_to_ready(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Transit"})
        campaign_id = resp.get_json()["id"]

        resp = client.patch(f"/api/campaigns/{campaign_id}", headers=headers, json={"status": "ready"})
        assert resp.status_code == 200

        detail = client.get(f"/api/campaigns/{campaign_id}", headers=headers)
        assert detail.get_json()["status"] == "Ready"

    def test_invalid_status_transition(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Bad Transit"})
        campaign_id = resp.get_json()["id"]

        # Draft cannot go directly to review
        resp = client.patch(f"/api/campaigns/{campaign_id}", headers=headers, json={"status": "review"})
        assert resp.status_code == 400
        assert "Cannot transition" in resp.get_json()["error"]

    def test_update_no_valid_fields(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "NF"})
        campaign_id = resp.get_json()["id"]

        resp = client.patch(f"/api/campaigns/{campaign_id}", headers=headers, json={"bogus": "field"})
        assert resp.status_code == 400

    def test_update_nonexistent(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.patch(
            "/api/campaigns/00000000-0000-0000-0000-000000000099",
            headers=headers,
            json={"name": "x"},
        )
        assert resp.status_code == 404


class TestDeleteCampaign:
    def test_delete_draft(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Delete Me"})
        campaign_id = resp.get_json()["id"]

        resp = client.delete(f"/api/campaigns/{campaign_id}", headers=headers)
        assert resp.status_code == 200

        # Should not appear in list
        resp = client.get("/api/campaigns", headers=headers)
        names = [c["name"] for c in resp.get_json()["campaigns"]]
        assert "Delete Me" not in names

    def test_delete_non_draft_forbidden(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Promote"})
        campaign_id = resp.get_json()["id"]

        # Move to ready first
        client.patch(f"/api/campaigns/{campaign_id}", headers=headers, json={"status": "ready"})

        # Attempt delete
        resp = client.delete(f"/api/campaigns/{campaign_id}", headers=headers)
        assert resp.status_code == 400
        assert "draft" in resp.get_json()["error"].lower()

    def test_delete_nonexistent(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.delete(
            "/api/campaigns/00000000-0000-0000-0000-000000000099",
            headers=headers,
        )
        assert resp.status_code == 404


class TestCampaignTemplates:
    def test_list_system_templates(self, client, seed_companies_contacts, db):
        from api.models import CampaignTemplate
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Create a system template
        tpl = CampaignTemplate(
            name="System T1",
            description="A system template",
            steps=json.dumps([{"step": 1, "channel": "email", "label": "Email"}]),
            is_system=True,
        )
        db.session.add(tpl)
        db.session.commit()

        resp = client.get("/api/campaign-templates", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["templates"]) >= 1
        names = [t["name"] for t in data["templates"]]
        assert "System T1" in names
