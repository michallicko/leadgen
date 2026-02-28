"""Tests for contacts & companies analyzer tool handlers (ANALYZE feature).

Tests cover:
- count_contacts: total and filtered counts
- count_companies: total and filtered counts
- list_contacts: pagination, filters, output shape
- list_companies: pagination, filters, contact_count subquery
- Tenant isolation: queries only return data for the given tenant
- Invalid filter handling
"""

import pytest

from api.services.analyze_tools import (
    count_contacts,
    count_companies,
    list_contacts,
    list_companies,
    ANALYZE_TOOLS,
)
from api.services.tool_registry import ToolContext, register_tool, clear_registry


@pytest.fixture(autouse=True)
def _register_analyze_tools():
    """Register analyze tools for each test."""
    clear_registry()
    for tool in ANALYZE_TOOLS:
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


@pytest.fixture
def other_tenant(db):
    """Create a second tenant to test isolation."""
    from api.models import Tenant, Company, Contact
    t = Tenant(name="Other Corp", slug="other-corp", is_active=True)
    db.session.add(t)
    db.session.flush()

    c = Company(tenant_id=t.id, name="Other Co", status="new", industry="finance")
    db.session.add(c)
    db.session.flush()

    ct = Contact(
        tenant_id=t.id, first_name="Zara", last_name="Other",
        company_id=c.id, email_address="zara@other.com",
    )
    db.session.add(ct)
    db.session.commit()
    return t


class TestCountContacts:
    def test_count_all(self, db, seed_companies_contacts, ctx):
        result = count_contacts({}, ctx)
        assert result["count"] == 10
        assert result["filters_applied"] == {}

    def test_count_with_company_filter(self, db, seed_companies_contacts, ctx):
        result = count_contacts({"filters": {"company_name": "Acme"}}, ctx)
        assert result["count"] == 2  # John + Jane at Acme Corp

    def test_count_with_has_email_true(self, db, seed_companies_contacts, ctx):
        result = count_contacts({"filters": {"has_email": True}}, ctx)
        # John, Jane, Bob, Carol, Eve, Frank, Ivy = 7 with emails
        assert result["count"] == 7

    def test_count_with_has_email_false(self, db, seed_companies_contacts, ctx):
        result = count_contacts({"filters": {"has_email": False}}, ctx)
        # Dave, Grace, Hank = 3 without emails
        assert result["count"] == 3

    def test_count_with_tag_filter(self, db, seed_companies_contacts, ctx):
        result = count_contacts({"filters": {"tag": "batch-1"}}, ctx)
        # John, Jane, Bob, Carol, Dave, Ivy = 6 in batch-1
        assert result["count"] == 6

    def test_count_with_enrichment_status(self, db, seed_companies_contacts, ctx):
        result = count_contacts({"filters": {"enrichment_status": "approved"}}, ctx)
        # Jane, Eve = 2 approved
        assert result["count"] == 2

    def test_count_combined_filters(self, db, seed_companies_contacts, ctx):
        result = count_contacts({
            "filters": {"company_name": "Beta", "has_email": True}
        }, ctx)
        # Bob + Carol at Beta, both have emails
        assert result["count"] == 2

    def test_invalid_filters_type(self, db, seed_companies_contacts, ctx):
        result = count_contacts({"filters": "not a dict"}, ctx)
        assert "error" in result

    def test_tenant_isolation(self, db, seed_companies_contacts, other_tenant, ctx):
        """Contacts from other tenant must not appear."""
        result = count_contacts({}, ctx)
        assert result["count"] == 10  # Only seed tenant contacts

        other_ctx = ToolContext(tenant_id=str(other_tenant.id))
        result2 = count_contacts({}, other_ctx)
        assert result2["count"] == 1


class TestCountCompanies:
    def test_count_all(self, db, seed_companies_contacts, ctx):
        result = count_companies({}, ctx)
        assert result["count"] == 5

    def test_count_by_status(self, db, seed_companies_contacts, ctx):
        result = count_companies({"filters": {"status": "triage_passed"}}, ctx)
        assert result["count"] == 2  # Beta + Gamma

    def test_count_by_industry(self, db, seed_companies_contacts, ctx):
        result = count_companies({"filters": {"industry": "health"}}, ctx)
        assert result["count"] == 1  # Gamma (healthcare)

    def test_count_by_tier(self, db, seed_companies_contacts, ctx):
        result = count_companies({"filters": {"tier": "tier_1_platinum"}}, ctx)
        assert result["count"] == 2  # Beta + Delta

    def test_count_by_tag(self, db, seed_companies_contacts, ctx):
        result = count_companies({"filters": {"tag": "batch-2"}}, ctx)
        assert result["count"] == 2  # Delta + Epsilon

    def test_tenant_isolation(self, db, seed_companies_contacts, other_tenant, ctx):
        result = count_companies({}, ctx)
        assert result["count"] == 5

        other_ctx = ToolContext(tenant_id=str(other_tenant.id))
        result2 = count_companies({}, other_ctx)
        assert result2["count"] == 1


class TestListContacts:
    def test_list_default_page(self, db, seed_companies_contacts, ctx):
        result = list_contacts({}, ctx)
        assert result["total"] == 10
        assert result["limit"] == 10
        assert result["offset"] == 0
        assert len(result["contacts"]) == 10

    def test_list_pagination(self, db, seed_companies_contacts, ctx):
        result = list_contacts({"limit": 3, "offset": 0}, ctx)
        assert len(result["contacts"]) == 3
        assert result["total"] == 10
        assert result["limit"] == 3

    def test_list_offset(self, db, seed_companies_contacts, ctx):
        result = list_contacts({"limit": 3, "offset": 8}, ctx)
        assert len(result["contacts"]) == 2  # 10 total, offset 8 = 2 left
        assert result["total"] == 10

    def test_list_max_limit(self, db, seed_companies_contacts, ctx):
        result = list_contacts({"limit": 999}, ctx)
        assert result["limit"] == 50  # Capped at MAX_PAGE_SIZE

    def test_list_with_filter(self, db, seed_companies_contacts, ctx):
        result = list_contacts({"filters": {"company_name": "Delta"}}, ctx)
        assert result["total"] == 2  # Eve + Frank at Delta
        assert len(result["contacts"]) == 2
        for c in result["contacts"]:
            assert c["company_name"] == "Delta GmbH"

    def test_contact_shape(self, db, seed_companies_contacts, ctx):
        result = list_contacts({"filters": {"enrichment_status": "sent"}}, ctx)
        assert result["total"] == 1
        c = result["contacts"][0]
        assert "name" in c
        assert "email" in c
        assert "company_name" in c
        assert "tags" in c
        assert "enrichment_status" in c
        assert c["name"] == "Frank Black"

    def test_tenant_isolation(self, db, seed_companies_contacts, other_tenant, ctx):
        other_ctx = ToolContext(tenant_id=str(other_tenant.id))
        result = list_contacts({}, other_ctx)
        assert result["total"] == 1
        assert result["contacts"][0]["name"] == "Zara Other"


class TestListCompanies:
    def test_list_default(self, db, seed_companies_contacts, ctx):
        result = list_companies({}, ctx)
        assert result["total"] == 5
        assert len(result["companies"]) == 5

    def test_list_pagination(self, db, seed_companies_contacts, ctx):
        result = list_companies({"limit": 2, "offset": 0}, ctx)
        assert len(result["companies"]) == 2
        assert result["total"] == 5

    def test_list_with_status_filter(self, db, seed_companies_contacts, ctx):
        result = list_companies({"filters": {"status": "enriched_l2"}}, ctx)
        assert result["total"] == 1
        assert result["companies"][0]["name"] == "Delta GmbH"

    def test_company_shape(self, db, seed_companies_contacts, ctx):
        result = list_companies({"filters": {"status": "new"}}, ctx)
        assert result["total"] == 1
        c = result["companies"][0]
        assert c["name"] == "Acme Corp"
        assert "status" in c
        assert "tier" in c
        assert "industry" in c
        assert "tags" in c
        assert "contact_count" in c
        assert c["contact_count"] == 2  # John + Jane

    def test_contact_count_correct(self, db, seed_companies_contacts, ctx):
        result = list_companies({"filters": {"status": "triage_passed"}}, ctx)
        # Beta has 2 contacts, Gamma has 2 contacts
        counts = {c["name"]: c["contact_count"] for c in result["companies"]}
        assert counts["Beta Inc"] == 2
        assert counts["Gamma LLC"] == 2

    def test_tenant_isolation(self, db, seed_companies_contacts, other_tenant, ctx):
        other_ctx = ToolContext(tenant_id=str(other_tenant.id))
        result = list_companies({}, other_ctx)
        assert result["total"] == 1
        assert result["companies"][0]["name"] == "Other Co"


class TestAnalyzeToolDefinitions:
    def test_all_tools_registered(self):
        from api.services.tool_registry import get_tool
        for tool in ANALYZE_TOOLS:
            assert get_tool(tool.name) is not None

    def test_tool_count(self):
        assert len(ANALYZE_TOOLS) == 4

    def test_tool_names(self):
        names = {t.name for t in ANALYZE_TOOLS}
        assert names == {"count_contacts", "count_companies", "list_contacts", "list_companies"}

    def test_tool_schemas_valid(self):
        for tool in ANALYZE_TOOLS:
            assert tool.input_schema["type"] == "object"
            assert "properties" in tool.input_schema
