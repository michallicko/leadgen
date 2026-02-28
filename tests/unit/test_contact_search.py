"""Tests for contact search API and campaign chat tools (BL-052 Phase 1).

Tests cover:
- POST /api/contacts/search: filtering, facets, pagination
- POST /api/contacts/search/summary: aggregate stats
- Chat tools: filter_contacts, create_campaign, assign_to_campaign,
  check_strategy_conflicts, get_campaign_summary
- Tenant isolation
"""

import pytest

from api.services.campaign_tools import (
    CAMPAIGN_TOOLS,
    assign_to_campaign,
    check_strategy_conflicts,
    create_campaign,
    filter_contacts,
    get_campaign_summary,
)
from api.services.tool_registry import ToolContext, clear_registry, register_tool
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _register_campaign_tools():
    """Register campaign tools for each test."""
    clear_registry()
    for tool in CAMPAIGN_TOOLS:
        try:
            register_tool(tool)
        except ValueError:
            pass
    yield
    clear_registry()


@pytest.fixture
def ctx(seed_tenant):
    """ToolContext for the seed tenant."""
    return ToolContext(tenant_id=str(seed_tenant.id))


# ---------------------------------------------------------------------------
# POST /api/contacts/search
# ---------------------------------------------------------------------------


class TestContactSearchEndpoint:
    def test_basic_search(self, client, db, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/search",
            json={"filters": {}, "page": 1, "page_size": 50, "include_facets": False},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Should exclude disqualified by default but include all non-disqualified
        assert data["total"] == 10
        assert len(data["contacts"]) == 10
        assert data["page"] == 1
        assert "facets" not in data

    def test_search_with_facets(self, client, db, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/search",
            json={"filters": {}, "include_facets": True},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "facets" in data
        assert "seniority_level" in data["facets"]
        assert "industry" in data["facets"]

    def test_search_with_tier_filter(
        self, client, db, seed_companies_contacts, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/search",
            json={
                "filters": {"tier": ["tier_1_platinum"]},
                "include_facets": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Beta Inc (tier 1) + Delta GmbH (tier 1) = Bob, Carol, Eve, Frank
        assert data["total"] == 4

    def test_search_with_text_search(
        self, client, db, seed_companies_contacts, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/search",
            json={
                "text_search": "Acme",
                "include_facets": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # John + Jane at Acme Corp
        assert data["total"] == 2

    def test_search_pagination(
        self, client, db, seed_companies_contacts, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/search",
            json={"filters": {}, "page": 1, "page_size": 3, "include_facets": False},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["contacts"]) == 3
        assert data["total"] == 10
        assert data["page"] == 1
        assert data["page_size"] == 3

    def test_search_response_shape(
        self, client, db, seed_companies_contacts, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/search",
            json={"text_search": "John", "include_facets": False},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        contact = data["contacts"][0]
        assert "id" in contact
        assert "first_name" in contact
        assert "last_name" in contact
        assert "job_title" in contact
        assert "company" in contact
        assert "name" in contact["company"]
        assert "enrichment_stages" in contact
        assert "active_campaigns" in contact


# ---------------------------------------------------------------------------
# POST /api/contacts/search/summary
# ---------------------------------------------------------------------------


class TestContactSearchSummary:
    def test_summary_basic(
        self, client, db, seed_companies_contacts, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/search/summary",
            json={"filters": {}},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 10
        assert "avg_contact_score" in data
        assert "with_email" in data
        assert "with_linkedin" in data


# ---------------------------------------------------------------------------
# Chat tool: filter_contacts
# ---------------------------------------------------------------------------


class TestFilterContactsTool:
    def test_filter_all(self, db, seed_companies_contacts, ctx):
        result = filter_contacts({}, ctx)
        assert result["total"] == 10
        assert len(result["contacts"]) == 10

    def test_filter_by_tier(self, db, seed_companies_contacts, ctx):
        result = filter_contacts({"tiers": ["tier_1_platinum"]}, ctx)
        assert result["total"] == 4

    def test_filter_by_search(self, db, seed_companies_contacts, ctx):
        result = filter_contacts({"search": "Acme"}, ctx)
        assert result["total"] == 2

    def test_filter_with_limit(self, db, seed_companies_contacts, ctx):
        result = filter_contacts({"limit": 3}, ctx)
        assert result["total"] == 10  # Total unaffected
        assert len(result["contacts"]) == 3

    def test_filter_contacts_shape(self, db, seed_companies_contacts, ctx):
        result = filter_contacts({"limit": 1}, ctx)
        c = result["contacts"][0]
        assert "id" in c
        assert "full_name" in c
        assert "job_title" in c
        assert "company_name" in c
        assert "contact_score" in c

    def test_filter_min_score(self, db, seed_companies_contacts, ctx):
        result = filter_contacts({"min_contact_score": 80}, ctx)
        # John (85), Jane (90), Carol (80), Frank (88) = 4
        assert result["total"] == 4
        for c in result["contacts"]:
            assert c["contact_score"] >= 80


# ---------------------------------------------------------------------------
# Chat tool: create_campaign
# ---------------------------------------------------------------------------


class TestCreateCampaignTool:
    def test_create_campaign(self, db, seed_companies_contacts, ctx):
        result = create_campaign({"name": "Test Campaign Q1"}, ctx)
        assert "campaign_id" in result
        assert result["status"] == "draft"
        assert "error" not in result

    def test_create_campaign_with_description(self, db, seed_companies_contacts, ctx):
        result = create_campaign(
            {"name": "Test Campaign", "description": "Test desc"}, ctx
        )
        assert "campaign_id" in result

    def test_create_campaign_empty_name(self, db, seed_companies_contacts, ctx):
        result = create_campaign({"name": ""}, ctx)
        assert "error" in result

    def test_create_campaign_duplicate_name(self, db, seed_companies_contacts, ctx):
        create_campaign({"name": "Unique Campaign"}, ctx)
        result = create_campaign({"name": "Unique Campaign"}, ctx)
        assert "error" in result
        assert "already exists" in result["error"]
        assert "existing_campaign_id" in result


# ---------------------------------------------------------------------------
# Chat tool: assign_to_campaign
# ---------------------------------------------------------------------------


class TestAssignToCampaignTool:
    def test_assign_contacts(self, db, seed_companies_contacts, ctx):
        camp = create_campaign({"name": "Assignment Test"}, ctx)
        cid = camp["campaign_id"]

        # Get some contact IDs
        contacts = filter_contacts({"limit": 3}, ctx)
        contact_ids = [c["id"] for c in contacts["contacts"]]

        result = assign_to_campaign(
            {"campaign_id": cid, "contact_ids": contact_ids}, ctx
        )
        assert result["added"] == 3
        assert result["skipped"] == 0

    def test_assign_deduplication(self, db, seed_companies_contacts, ctx):
        camp = create_campaign({"name": "Dedup Test"}, ctx)
        cid = camp["campaign_id"]

        contacts = filter_contacts({"limit": 2}, ctx)
        contact_ids = [c["id"] for c in contacts["contacts"]]

        assign_to_campaign({"campaign_id": cid, "contact_ids": contact_ids}, ctx)
        result = assign_to_campaign(
            {"campaign_id": cid, "contact_ids": contact_ids}, ctx
        )
        assert result["added"] == 0
        assert result["skipped"] == 2

    def test_assign_missing_campaign(self, db, seed_companies_contacts, ctx):
        result = assign_to_campaign(
            {
                "campaign_id": "00000000-0000-0000-0000-000000000000",
                "contact_ids": ["x"],
            },
            ctx,
        )
        assert "error" in result

    def test_assign_no_contacts(self, db, seed_companies_contacts, ctx):
        camp = create_campaign({"name": "Empty Test"}, ctx)
        result = assign_to_campaign({"campaign_id": camp["campaign_id"]}, ctx)
        assert "error" in result


# ---------------------------------------------------------------------------
# Chat tool: check_strategy_conflicts
# ---------------------------------------------------------------------------


class TestCheckStrategyConflictsTool:
    def test_no_conflicts(self, db, seed_companies_contacts, ctx):
        camp = create_campaign({"name": "Clean Test"}, ctx)
        cid = camp["campaign_id"]

        contacts = filter_contacts({"limit": 2}, ctx)
        contact_ids = [c["id"] for c in contacts["contacts"]]
        assign_to_campaign(
            {"campaign_id": cid, "contact_ids": contact_ids}, ctx
        )

        result = check_strategy_conflicts({"campaign_id": cid}, ctx)
        assert result["total_contacts"] == 2
        assert result["clean"] == 2
        assert isinstance(result["conflicts"], list)

    def test_missing_campaign(self, db, seed_companies_contacts, ctx):
        result = check_strategy_conflicts(
            {"campaign_id": "00000000-0000-0000-0000-000000000000"}, ctx
        )
        assert "error" in result

    def test_overlap_detection(self, db, seed_companies_contacts, ctx):
        """Test that contacts in multiple campaigns are detected."""
        camp1 = create_campaign({"name": "Overlap A"}, ctx)
        camp2 = create_campaign({"name": "Overlap B"}, ctx)

        contacts = filter_contacts({"limit": 3}, ctx)
        contact_ids = [c["id"] for c in contacts["contacts"]]

        assign_to_campaign(
            {"campaign_id": camp1["campaign_id"], "contact_ids": contact_ids}, ctx
        )
        assign_to_campaign(
            {"campaign_id": camp2["campaign_id"], "contact_ids": contact_ids}, ctx
        )

        result = check_strategy_conflicts({"campaign_id": camp2["campaign_id"]}, ctx)
        # All 3 contacts should show overlap with camp1
        overlap_conflicts = [
            c for c in result["conflicts"] if c["type"] == "segment_overlap"
        ]
        assert len(overlap_conflicts) == 3


# ---------------------------------------------------------------------------
# Chat tool: get_campaign_summary
# ---------------------------------------------------------------------------


class TestGetCampaignSummaryTool:
    def test_campaign_summary(self, db, seed_companies_contacts, ctx):
        camp = create_campaign({"name": "Summary Test"}, ctx)
        cid = camp["campaign_id"]

        contacts = filter_contacts({"limit": 5}, ctx)
        contact_ids = [c["id"] for c in contacts["contacts"]]
        assign_to_campaign(
            {"campaign_id": cid, "contact_ids": contact_ids}, ctx
        )

        result = get_campaign_summary({"campaign_id": cid}, ctx)
        assert result["name"] == "Summary Test"
        assert result["status"] == "draft"
        assert result["total_contacts"] == 5
        assert "contacts_by_status" in result
        assert "enrichment_ready" in result
        assert "enrichment_needed" in result

    def test_campaign_summary_empty(self, db, seed_companies_contacts, ctx):
        camp = create_campaign({"name": "Empty Summary"}, ctx)
        result = get_campaign_summary({"campaign_id": camp["campaign_id"]}, ctx)
        assert result["total_contacts"] == 0

    def test_campaign_summary_not_found(self, db, seed_companies_contacts, ctx):
        result = get_campaign_summary(
            {"campaign_id": "00000000-0000-0000-0000-000000000000"}, ctx
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_filter_contacts_isolation(self, db, seed_companies_contacts, ctx):
        """filter_contacts only returns contacts for the given tenant."""
        from api.models import Contact, Company, Tenant

        other = Tenant(name="Other Corp", slug="other-corp", is_active=True)
        db.session.add(other)
        db.session.flush()
        c = Company(tenant_id=other.id, name="Other Co")
        db.session.add(c)
        db.session.flush()
        ct = Contact(
            tenant_id=other.id,
            first_name="Stranger",
            last_name="Danger",
            company_id=c.id,
        )
        db.session.add(ct)
        db.session.commit()

        result = filter_contacts({"search": "Stranger"}, ctx)
        assert result["total"] == 0

    def test_create_campaign_isolation(self, db, seed_companies_contacts, ctx):
        """Campaigns are created in the correct tenant."""
        result = create_campaign({"name": "Tenant Test"}, ctx)
        campaign = db.session.execute(
            db.text("SELECT tenant_id FROM campaigns WHERE id = :id"),
            {"id": result["campaign_id"]},
        ).fetchone()
        assert str(campaign[0]) == ctx.tenant_id
