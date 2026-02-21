"""Unit tests for campaign contact selection with ICP filters and enrichment gaps."""
import json

from api.models import EntityStageCompletion
from tests.conftest import auth_header


class TestAddContactsByIds:
    """Adding contacts by explicit IDs should return enrichment gaps."""

    def _create_campaign(self, client, headers, name="Test Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_add_by_ids_returns_gaps(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Contacts have no enrichment completions, so gaps should be reported
        contact_ids = [str(data["contacts"][0].id), str(data["contacts"][1].id)]
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": contact_ids},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 2
        assert result["skipped"] == 0
        assert result["total"] == 2
        assert "gaps" in result
        assert len(result["gaps"]) == 2
        # Each gap should list all 3 missing stages
        for gap in result["gaps"]:
            assert "contact_id" in gap
            assert "contact_name" in gap
            assert "missing" in gap
            assert "l1_company" in gap["missing"]
            assert "l2_deep_research" in gap["missing"]
            assert "person" in gap["missing"]

    def test_add_by_ids_no_gaps_when_enriched(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        contact = data["contacts"][0]
        company = data["companies"][0]

        # Complete all enrichment stages
        for stage in ["l1_company", "l2_deep_research"]:
            db.session.add(
                EntityStageCompletion(
                    tenant_id=data["tenant"].id,
                    tag_id=data["tags"][0].id,
                    entity_type="company",
                    entity_id=str(company.id),
                    stage=stage,
                    status="completed",
                )
            )
        db.session.add(
            EntityStageCompletion(
                tenant_id=data["tenant"].id,
                tag_id=data["tags"][0].id,
                entity_type="contact",
                entity_id=str(contact.id),
                stage="person",
                status="completed",
            )
        )
        db.session.commit()

        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": [str(contact.id)]},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 1
        assert result["gaps"] == []


class TestAddContactsByOwnerFilter:
    """Adding contacts by owner_id filter resolves matching contacts."""

    def _create_campaign(self, client, headers, name="Owner Filter Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_filter_by_owner(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        owner2 = data["owners"][1]  # Bob
        # Bob owns contacts: Dave Brown, Grace White, Hank Grey, Ivy Blue
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"owner_id": str(owner2.id)},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 4
        assert "gaps" in result

    def test_filter_by_owner_with_company_ids(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        owner1 = data["owners"][0]  # Alice
        # Alice owns contacts at companies[0] (Acme): John, Jane
        # Also at companies[1] (Beta): Bob Wilson, Carol Lee
        # Also at companies[3] (Delta): Eve Green, Frank Black
        # Restrict to just company[0]
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={
                "owner_id": str(owner1.id),
                "company_ids": [str(data["companies"][0].id)],
            },
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 2  # John Doe and Jane Smith


class TestAddContactsByICPFilters:
    """Adding contacts using ICP filter criteria."""

    def _create_campaign(self, client, headers, name="ICP Filter Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_filter_by_tier(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # tier_1_platinum: Beta Inc (Bob Wilson, Carol Lee) and Delta GmbH (Eve Green, Frank Black)
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"tiers": ["tier_1_platinum"]}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 4

    def test_filter_by_industry(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # healthcare: Gamma LLC (Dave Brown, Ivy Blue)
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"industries": ["healthcare"]}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 2

    def test_filter_by_icp_fit(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # strong_fit contacts: John Doe, Jane Smith, Carol Lee, Frank Black
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"icp_fit": ["strong_fit"]}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 4

    def test_filter_by_seniority(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # c_level seniority: CEO (John), CTO (Jane), CFO (Eve), CIO (Frank)
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"seniority_levels": ["c_level"]}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 4

    def test_filter_by_min_contact_score(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Contacts with score >= 85: John (85), Jane (90), Frank (88)
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"min_contact_score": 85}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 3

    def test_filter_by_tag_ids(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # tag2 (batch-2) contacts: Eve Green, Frank Black, Grace White, Hank Grey
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"tag_ids": [str(data["tags"][1].id)]}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 4

    def test_combined_filters(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # tier_1_platinum + strong_fit: Carol Lee (Beta, strong_fit) and Frank Black (Delta, strong_fit)
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={
                "icp_filters": {
                    "tiers": ["tier_1_platinum"],
                    "icp_fit": ["strong_fit"],
                }
            },
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 2

    def test_filters_exclude_disqualified(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts

        # Disqualify John Doe
        from api.models import db as _db

        _db.session.execute(
            _db.text("UPDATE contacts SET is_disqualified = true WHERE id = :id"),
            {"id": str(data["contacts"][0].id)},
        )
        _db.session.commit()

        cid = self._create_campaign(client, headers)

        # strong_fit: without John (disqualified) = Jane, Carol, Frank
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"icp_fit": ["strong_fit"]}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 3

    def test_no_matching_contacts_returns_400(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # No contacts with tier_0_diamond
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"tiers": ["tier_0_diamond"]}},
        )
        assert resp.status_code == 400
        assert "No contacts found" in resp.get_json()["error"]


class TestEnrichmentReadyFilter:
    """The enrichment_ready ICP filter should exclude contacts without completed stages."""

    def _create_campaign(self, client, headers, name="Enrichment Ready Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_enrichment_ready_excludes_unenriched(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # No enrichment completions exist, so enrichment_ready should find 0
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"enrichment_ready": True}},
        )
        assert resp.status_code == 400
        assert "No contacts found" in resp.get_json()["error"]

    def test_enrichment_ready_includes_fully_enriched(
        self, client, seed_companies_contacts, db
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts

        contact = data["contacts"][0]  # John Doe @ Acme Corp
        company = data["companies"][0]  # Acme Corp

        # Complete all 3 stages
        for stage in ["l1_company", "l2_deep_research"]:
            db.session.add(
                EntityStageCompletion(
                    tenant_id=data["tenant"].id,
                    tag_id=data["tags"][0].id,
                    entity_type="company",
                    entity_id=str(company.id),
                    stage=stage,
                    status="completed",
                )
            )
        db.session.add(
            EntityStageCompletion(
                tenant_id=data["tenant"].id,
                tag_id=data["tags"][0].id,
                entity_type="contact",
                entity_id=str(contact.id),
                stage="person",
                status="completed",
            )
        )
        db.session.commit()

        cid = self._create_campaign(client, headers)

        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"enrichment_ready": True}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        # John Doe should be included; Jane Smith shares company but has no person stage
        assert result["added"] == 1
        assert result["gaps"] == []  # Fully enriched, no gaps

    def test_enrichment_ready_excludes_partial(
        self, client, seed_companies_contacts, db
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts

        contact = data["contacts"][0]  # John Doe
        company = data["companies"][0]  # Acme Corp

        # Only L1 completed (missing L2 and person)
        db.session.add(
            EntityStageCompletion(
                tenant_id=data["tenant"].id,
                tag_id=data["tags"][0].id,
                entity_type="company",
                entity_id=str(company.id),
                stage="l1_company",
                status="completed",
            )
        )
        db.session.commit()

        cid = self._create_campaign(client, headers)

        # enrichment_ready filter requires ALL stages
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"enrichment_ready": True}},
        )
        assert resp.status_code == 400
        assert "No contacts found" in resp.get_json()["error"]


class TestDuplicateDetection:
    """Duplicate prevention still works with ICP filters."""

    def _create_campaign(self, client, headers, name="Dupe Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_duplicate_prevention_with_filters(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Add by explicit IDs first
        contact_ids = [str(data["contacts"][0].id)]
        client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": contact_ids},
        )

        # Now add by owner filter (which would include the same contact)
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"owner_id": str(data["owners"][0].id)},
        )
        result = resp.get_json()
        assert result["skipped"] >= 1  # At least the already-added contact
        # Total should be all Alice's non-disqualified contacts (including the pre-existing one)

    def test_merge_explicit_and_filter_ids(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Add with both explicit IDs and filters -- should merge and deduplicate
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={
                "contact_ids": [str(data["contacts"][0].id)],
                "icp_filters": {"icp_fit": ["strong_fit"]},
            },
        )
        assert resp.status_code == 200
        result = resp.get_json()
        # strong_fit: John, Jane, Carol, Frank -- John is also in explicit IDs
        # Should deduplicate: 4 unique contacts total
        assert result["added"] == 4


class TestEnrichmentGapReporting:
    """The response should include per-contact enrichment gap details."""

    def _create_campaign(self, client, headers, name="Gap Report Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_partial_enrichment_gaps(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts

        contact = data["contacts"][0]  # John Doe
        company = data["companies"][0]  # Acme Corp

        # Only L1 company completed
        db.session.add(
            EntityStageCompletion(
                tenant_id=data["tenant"].id,
                tag_id=data["tags"][0].id,
                entity_type="company",
                entity_id=str(company.id),
                stage="l1_company",
                status="completed",
            )
        )
        db.session.commit()

        cid = self._create_campaign(client, headers)

        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": [str(contact.id)]},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 1
        assert len(result["gaps"]) == 1

        gap = result["gaps"][0]
        assert gap["contact_id"] == str(contact.id)
        assert "John" in gap["contact_name"]
        assert "l1_company" not in gap["missing"]
        assert "l2_deep_research" in gap["missing"]
        assert "person" in gap["missing"]

    def test_no_gaps_when_empty_add(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Add a contact first
        contact_ids = [str(data["contacts"][0].id)]
        client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": contact_ids},
        )

        # Try adding same contact again -- 0 added, no gap check needed
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": contact_ids},
        )
        result = resp.get_json()
        assert result["added"] == 0
        assert result["gaps"] == []


class TestListCampaignContacts:
    """GET /api/campaigns/{id}/contacts returns contact details."""

    def _create_campaign(self, client, headers, name="List Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_list_contacts_with_details(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        contact_ids = [str(c.id) for c in data["contacts"][:3]]
        client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": contact_ids},
        )

        resp = client.get(f"/api/campaigns/{cid}/contacts", headers=headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["total"] == 3

        # Verify contact detail fields
        contact = result["contacts"][0]
        assert "campaign_contact_id" in contact
        assert "contact_id" in contact
        assert "full_name" in contact
        assert "job_title" in contact
        assert "email_address" in contact
        assert "company_name" in contact
        assert "company_tier" in contact
        assert "status" in contact
        assert "enrichment_gaps" in contact
        assert "icp_fit" in contact
        assert "contact_score" in contact

    def test_list_contacts_nonexistent_campaign(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/contacts",
            headers=headers,
        )
        assert resp.status_code == 404


class TestRemoveContactCascade:
    """DELETE /api/campaigns/{id}/contacts removes contacts and updates counts."""

    def _create_campaign(self, client, headers, name="Remove Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_remove_updates_total_contacts(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        contact_ids = [str(c.id) for c in data["contacts"][:3]]
        client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": contact_ids},
        )

        # Verify total_contacts is 3
        detail = client.get(f"/api/campaigns/{cid}", headers=headers)
        assert detail.get_json()["total_contacts"] == 3

        # Remove one
        resp = client.delete(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": [contact_ids[0]]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["removed"] == 1

        # Verify total_contacts updated to 2
        detail = client.get(f"/api/campaigns/{cid}", headers=headers)
        assert detail.get_json()["total_contacts"] == 2

    def test_remove_nonexistent_contact(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        cid = self._create_campaign(client, headers)

        resp = client.delete(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": ["00000000-0000-0000-0000-000000000099"]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["removed"] == 0

    def test_remove_requires_contact_ids(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        cid = self._create_campaign(client, headers)

        resp = client.delete(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={},
        )
        assert resp.status_code == 400
        assert "contact_ids" in resp.get_json()["error"]


class TestValidationErrors:
    """Edge cases and validation errors for the contacts endpoint."""

    def _create_campaign(self, client, headers, name="Validation Campaign"):
        resp = client.post("/api/campaigns", headers=headers, json={"name": name})
        return resp.get_json()["id"]

    def test_requires_some_input(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        cid = self._create_campaign(client, headers)

        resp = client.post(
            f"/api/campaigns/{cid}/contacts", headers=headers, json={}
        )
        assert resp.status_code == 400
        assert "required" in resp.get_json()["error"].lower()

    def test_campaign_not_found(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/contacts",
            headers=headers,
            json={"contact_ids": ["some-id"]},
        )
        assert resp.status_code == 404

    def test_only_draft_or_ready_campaigns(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = seed_companies_contacts
        cid = self._create_campaign(client, headers)

        # Move to generating (draft -> ready -> generating)
        client.patch(
            f"/api/campaigns/{cid}", headers=headers, json={"status": "ready"}
        )
        client.patch(
            f"/api/campaigns/{cid}",
            headers=headers,
            json={"status": "generating"},
        )

        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": [str(data["contacts"][0].id)]},
        )
        assert resp.status_code == 400
        assert "draft or ready" in resp.get_json()["error"].lower()
