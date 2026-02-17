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


class TestCampaignContacts:
    """BL-032: Campaign contacts — add, list, remove contacts from campaigns."""

    def _create_campaign(self, client, headers, name="Test Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_add_contacts_by_ids(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        contact_ids = [str(data["contacts"][0].id), str(data["contacts"][1].id)]
        resp = client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "contact_ids": contact_ids,
        })
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 2
        assert result["skipped"] == 0
        assert result["total"] == 2

    def test_add_contacts_by_company(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Company[0] = Acme Corp with contacts[0] and contacts[1]
        resp = client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "company_ids": [str(data["companies"][0].id)],
        })
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 2  # John Doe + Jane Smith

    def test_add_contacts_skips_duplicates(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        contact_ids = [str(data["contacts"][0].id)]
        client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={"contact_ids": contact_ids})

        # Add same contact again
        resp = client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={"contact_ids": contact_ids})
        result = resp.get_json()
        assert result["added"] == 0
        assert result["skipped"] == 1

    def test_add_contacts_requires_ids(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        cid = self._create_campaign(client, headers)

        resp = client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={})
        assert resp.status_code == 400

    def test_add_contacts_only_draft_or_ready(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Move to ready then generating
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={"status": "ready"})
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={"status": "generating"})

        resp = client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "contact_ids": [str(data["contacts"][0].id)],
        })
        assert resp.status_code == 400
        assert "draft or ready" in resp.get_json()["error"].lower()

    def test_list_campaign_contacts(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Add 3 contacts
        contact_ids = [str(c.id) for c in data["contacts"][:3]]
        client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={"contact_ids": contact_ids})

        resp = client.get(f"/api/campaigns/{cid}/contacts", headers=headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["total"] == 3
        assert len(result["contacts"]) == 3
        # Check contact fields are returned
        c = result["contacts"][0]
        assert "contact_id" in c
        assert "full_name" in c
        assert "company_name" in c
        assert "status" in c

    def test_list_contacts_empty_campaign(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        cid = self._create_campaign(client, headers)

        resp = client.get(f"/api/campaigns/{cid}/contacts", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0

    def test_list_contacts_nonexistent_campaign(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/campaigns/00000000-0000-0000-0000-000000000099/contacts", headers=headers)
        assert resp.status_code == 404

    def test_remove_contacts(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        contact_ids = [str(c.id) for c in data["contacts"][:3]]
        client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={"contact_ids": contact_ids})

        # Remove first contact
        resp = client.delete(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "contact_ids": [contact_ids[0]],
        })
        assert resp.status_code == 200
        assert resp.get_json()["removed"] == 1

        # Verify only 2 remain
        resp = client.get(f"/api/campaigns/{cid}/contacts", headers=headers)
        assert resp.get_json()["total"] == 2

    def test_remove_contacts_only_draft_or_ready(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Add a contact, then move to generating
        contact_ids = [str(data["contacts"][0].id)]
        client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={"contact_ids": contact_ids})
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={"status": "ready"})
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={"status": "generating"})

        resp = client.delete(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "contact_ids": contact_ids,
        })
        assert resp.status_code == 400

    def test_campaign_detail_shows_contact_count(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        contact_ids = [str(c.id) for c in data["contacts"][:4]]
        client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={"contact_ids": contact_ids})

        resp = client.get(f"/api/campaigns/{cid}", headers=headers)
        assert resp.get_json()["total_contacts"] == 4


class TestEnrichmentCheck:
    """BL-034: Enrichment readiness check for campaign contacts."""

    def _create_campaign_with_contacts(self, client, headers, data, contact_indices):
        resp = client.post("/api/campaigns", headers=headers, json={"name": "Readiness Test"})
        cid = resp.get_json()["id"]
        contact_ids = [str(data["contacts"][i].id) for i in contact_indices]
        client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={"contact_ids": contact_ids})
        return cid

    def test_enrichment_check_no_completions(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign_with_contacts(client, headers, data, [0, 1, 2])

        resp = client.post(f"/api/campaigns/{cid}/enrichment-check", headers=headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["summary"]["total"] == 3
        assert result["summary"]["needs_enrichment"] == 3
        assert result["summary"]["ready"] == 0
        # All contacts should have gaps
        for c in result["contacts"]:
            assert len(c["gaps"]) > 0

    def test_enrichment_check_with_completions(self, client, seed_companies_contacts, db):
        from api.models import EntityStageCompletion
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts

        # Use contact[0] (John Doe @ Acme Corp)
        cid = self._create_campaign_with_contacts(client, headers, data, [0])

        # Add all completions for Acme Corp company + contact
        company_id = str(data["companies"][0].id)
        contact_id = str(data["contacts"][0].id)
        for stage in ["l1_company", "l2_deep_research"]:
            comp = EntityStageCompletion(
                tenant_id=data["tenant"].id,
                batch_id=data["batches"][0].id,
                entity_type="company",
                entity_id=company_id,
                stage=stage,
                status="completed",
            )
            db.session.add(comp)
        person_comp = EntityStageCompletion(
            tenant_id=data["tenant"].id,
            batch_id=data["batches"][0].id,
            entity_type="contact",
            entity_id=contact_id,
            stage="person",
            status="completed",
        )
        db.session.add(person_comp)
        db.session.commit()

        resp = client.post(f"/api/campaigns/{cid}/enrichment-check", headers=headers)
        result = resp.get_json()
        assert result["summary"]["ready"] == 1
        assert result["summary"]["needs_enrichment"] == 0
        assert result["contacts"][0]["ready"] is True
        assert result["contacts"][0]["gaps"] == []

    def test_enrichment_check_partial(self, client, seed_companies_contacts, db):
        from api.models import EntityStageCompletion
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign_with_contacts(client, headers, data, [0])

        # Only L1 completed
        comp = EntityStageCompletion(
            tenant_id=data["tenant"].id,
            batch_id=data["batches"][0].id,
            entity_type="company",
            entity_id=str(data["companies"][0].id),
            stage="l1_company",
            status="completed",
        )
        db.session.add(comp)
        db.session.commit()

        resp = client.post(f"/api/campaigns/{cid}/enrichment-check", headers=headers)
        result = resp.get_json()
        assert result["summary"]["needs_enrichment"] == 1
        gaps = result["contacts"][0]["gaps"]
        assert "l2_deep_research" in gaps
        assert "person" in gaps
        assert "l1_company" not in gaps

    def test_enrichment_check_empty_campaign(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Empty"})
        cid = resp.get_json()["id"]

        resp = client.post(f"/api/campaigns/{cid}/enrichment-check", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["summary"]["total"] == 0

    def test_enrichment_check_nonexistent_campaign(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/enrichment-check",
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
