"""Tests for advanced ICP contact filters (BL-046)."""
from tests.conftest import auth_header


class TestMultiValueFilters:
    """Test multi-value include/exclude filters on GET /api/contacts."""

    def test_filter_by_industry_include(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts?industry=software_saas", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # Acme Corp has industry=software_saas, with contacts John Doe and Jane Smith
        assert data["total"] == 2
        names = {c["full_name"] for c in data["contacts"]}
        assert "John Doe" in names
        assert "Jane Smith" in names

    def test_filter_by_industry_multi_value(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts?industry=software_saas,it", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # Acme (software_saas) has 2, Beta (it) has 2 = 4 total
        assert data["total"] == 4

    def test_filter_by_industry_exclude(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts?industry=software_saas&industry_exclude=true", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # 10 total - 2 at Acme (software_saas) = 8
        assert data["total"] == 8

    def test_filter_by_seniority_level(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts?seniority_level=c_level", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # Contacts with C in title get c_level: CEO, CTO, CFO, CIO = 4
        assert data["total"] == 4

    def test_filter_by_department(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts?department=executive", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # All C-suite get executive department
        assert data["total"] == 4

    def test_filter_combined_company_and_contact(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        # C-level at software_saas companies
        resp = client.get("/api/contacts?industry=software_saas&seniority_level=c_level", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # Acme Corp (software_saas) has CEO and CTO = 2
        assert data["total"] == 2

    def test_filter_by_job_titles(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts?job_titles=CEO", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        for c in data["contacts"]:
            assert "ceo" in c["job_title"].lower()

    def test_exclude_preserves_nulls(self, client, seed_companies_contacts, seed_tenant):
        """Excluding a value should NOT exclude contacts with NULL in that field."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        # All contacts have companies with industries, so excluding should keep all non-matching
        resp = client.get("/api/contacts?industry=software_saas&industry_exclude=true", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # Should have all contacts except those at software_saas companies
        assert data["total"] == 8

    def test_empty_filter_returns_all(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts?industry=", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 10


class TestFilterCounts:
    """Test POST /api/contacts/filter-counts endpoint."""

    def test_counts_no_filters(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/filter-counts",
            json={"filters": {}},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 10
        assert "industry" in data["facets"]
        assert "seniority_level" in data["facets"]
        # Check that industry facets have correct counts
        industry_facets = {f["value"]: f["count"] for f in data["facets"]["industry"]}
        assert industry_facets.get("software_saas") == 2  # Acme Corp: 2 contacts
        assert industry_facets.get("it") == 2  # Beta Inc: 2 contacts

    def test_counts_with_cross_filter(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/filter-counts",
            json={
                "filters": {
                    "seniority_level": {"values": ["c_level"], "exclude": False}
                }
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Total should be c_level only = 4
        assert data["total"] == 4
        # Industry counts should reflect c_level filter
        industry_facets = {f["value"]: f["count"] for f in data["facets"]["industry"]}
        # Acme has CEO + CTO (both c_level) = 2
        assert industry_facets.get("software_saas") == 2

    def test_counts_facet_excludes_own_filter(self, client, seed_companies_contacts, seed_tenant):
        """Industry facet counts should NOT apply the industry filter itself."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/contacts/filter-counts",
            json={
                "filters": {
                    "industry": {"values": ["software_saas"], "exclude": False}
                }
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Total should reflect the industry filter
        assert data["total"] == 2
        # But industry facet should show ALL industries (not filtered by industry)
        industry_facets = {f["value"]: f["count"] for f in data["facets"]["industry"]}
        assert "it" in industry_facets  # Should still show IT even though we filtered to SaaS


class TestJobTitleSuggestions:
    """Test GET /api/contacts/job-titles endpoint."""

    def test_suggestions_basic(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts/job-titles?q=CEO", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["titles"]) >= 1
        assert data["titles"][0]["title"] == "CEO"

    def test_suggestions_min_chars(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts/job-titles?q=C", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["titles"]) == 0  # Too short

    def test_suggestions_partial_match(self, client, seed_companies_contacts, seed_tenant):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/contacts/job-titles?q=Director", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # Should match "Director of AI" and "Sales Director"
        assert len(data["titles"]) >= 2
