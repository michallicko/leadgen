"""Tests for bulk action endpoints (add-tags, remove-tags, assign-campaign, matching-count)."""

import pytest
from api.models import Campaign, db
from tests.conftest import auth_header


@pytest.fixture
def seed_campaign(seed_tenant, seed_companies_contacts):
    """Create a campaign for bulk-assign testing."""
    data = seed_companies_contacts
    c = Campaign(
        tenant_id=seed_tenant.id,
        name="Test Campaign",
        status="draft",
        owner_id=data["owners"][0].id,
    )
    db.session.add(c)
    db.session.commit()
    return c


def _headers(client):
    h = auth_header(client)
    h["X-Namespace"] = "test-corp"
    return h


class TestBulkAddTags:
    """POST /api/bulk/add-tags"""

    def test_add_tags_by_ids(self, client, seed_companies_contacts):
        data = seed_companies_contacts
        contacts = data["contacts"]
        tag = data["tags"][0]
        ids = [str(contacts[0].id), str(contacts[1].id)]
        resp = client.post("/api/bulk/add-tags", json={
            "entity_type": "contact",
            "ids": ids,
            "tag_ids": [str(tag.id)],
        }, headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["affected"] == 2
        assert body["errors"] == []

    def test_add_tags_by_filters(self, client, seed_companies_contacts):
        data = seed_companies_contacts
        tag = data["tags"][0]
        resp = client.post("/api/bulk/add-tags", json={
            "entity_type": "contact",
            "filters": {"tag_name": tag.name},
            "tag_ids": [str(tag.id)],
        }, headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["affected"] >= 0

    def test_add_tags_to_companies(self, client, seed_companies_contacts):
        data = seed_companies_contacts
        companies = data["companies"]
        tag = data["tags"][0]
        ids = [str(companies[0].id)]
        resp = client.post("/api/bulk/add-tags", json={
            "entity_type": "company",
            "ids": ids,
            "tag_ids": [str(tag.id)],
        }, headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["affected"] == 1

    def test_add_tags_requires_tag_ids(self, client, seed_companies_contacts):
        resp = client.post("/api/bulk/add-tags", json={
            "entity_type": "contact",
            "ids": [str(seed_companies_contacts["contacts"][0].id)],
        }, headers=_headers(client))
        assert resp.status_code == 400

    def test_add_tags_requires_ids_or_filters(self, client, seed_companies_contacts):
        resp = client.post("/api/bulk/add-tags", json={
            "entity_type": "contact",
            "tag_ids": [str(seed_companies_contacts["tags"][0].id)],
        }, headers=_headers(client))
        assert resp.status_code == 400


class TestBulkRemoveTags:
    """POST /api/bulk/remove-tags"""

    def test_remove_tags_by_ids(self, client, seed_companies_contacts):
        data = seed_companies_contacts
        contacts = data["contacts"]
        tag = data["tags"][0]
        # Contacts 0-5 have tag1 via junction table
        ids = [str(contacts[0].id), str(contacts[1].id)]
        resp = client.post("/api/bulk/remove-tags", json={
            "entity_type": "contact",
            "ids": ids,
            "tag_ids": [str(tag.id)],
        }, headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["removed"] == 2

    def test_remove_tags_from_companies(self, client, seed_companies_contacts):
        data = seed_companies_contacts
        companies = data["companies"]
        tag = data["tags"][0]
        # Companies 0-2 have tag1
        ids = [str(companies[0].id), str(companies[1].id)]
        resp = client.post("/api/bulk/remove-tags", json={
            "entity_type": "company",
            "ids": ids,
            "tag_ids": [str(tag.id)],
        }, headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["removed"] == 2


class TestBulkAssignCampaign:
    """POST /api/bulk/assign-campaign"""

    def test_assign_campaign_by_ids(self, client, seed_companies_contacts, seed_campaign):
        data = seed_companies_contacts
        contacts = data["contacts"]
        ids = [str(contacts[0].id), str(contacts[1].id)]
        resp = client.post("/api/bulk/assign-campaign", json={
            "entity_type": "contact",
            "ids": ids,
            "campaign_id": str(seed_campaign.id),
        }, headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["affected"] == 2

    def test_assign_campaign_requires_campaign_id(self, client, seed_companies_contacts):
        resp = client.post("/api/bulk/assign-campaign", json={
            "entity_type": "contact",
            "ids": [str(seed_companies_contacts["contacts"][0].id)],
        }, headers=_headers(client))
        assert resp.status_code == 400

    def test_assign_campaign_only_contacts(self, client, seed_companies_contacts, seed_campaign):
        resp = client.post("/api/bulk/assign-campaign", json={
            "entity_type": "company",
            "ids": [str(seed_companies_contacts["companies"][0].id)],
            "campaign_id": str(seed_campaign.id),
        }, headers=_headers(client))
        assert resp.status_code == 400


class TestMatchingCount:
    """POST /api/contacts/matching-count and /api/companies/matching-count"""

    def test_contacts_matching_count_no_filters(self, client, seed_companies_contacts):
        resp = client.post("/api/contacts/matching-count",
                           json={"filters": {}}, headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 10

    def test_contacts_matching_count_with_tag_filter(self, client, seed_companies_contacts):
        data = seed_companies_contacts
        tag = data["tags"][0]
        resp = client.post("/api/contacts/matching-count",
                           json={"filters": {"tag_name": tag.name}},
                           headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        # batch-1 has 6 contacts (John, Jane, Bob, Carol, Dave, Ivy)
        assert body["count"] == 6

    def test_companies_matching_count_no_filters(self, client, seed_companies_contacts):
        resp = client.post("/api/companies/matching-count",
                           json={"filters": {}}, headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 5

    def test_companies_matching_count_with_status_filter(self, client, seed_companies_contacts):
        # DB stores "new", not display "New" (matching existing filter behavior)
        resp = client.post("/api/companies/matching-count",
                           json={"filters": {"status": "new"}},
                           headers=_headers(client))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 1
