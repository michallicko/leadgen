"""Tests for BL-158: Data Quality service."""

import uuid

import pytest

from tests.conftest import auth_header


@pytest.fixture
def seed_quality_data(db, seed_tenant, seed_super_admin):
    """Seed companies with mixed data quality for testing."""
    from api.models import (
        Company,
        CompanyEnrichmentL1,
        CompanyEnrichmentL2,
        CompanyLegalProfile,
        Owner,
        Tag,
        UserTenantRole,
    )

    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=seed_tenant.id,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)

    tag = Tag(tenant_id=seed_tenant.id, name="quality-test", is_active=True)
    owner = Owner(tenant_id=seed_tenant.id, name="Alice", is_active=True)
    db.session.add_all([tag, owner])
    db.session.flush()

    # Company 1: fully enriched, good quality
    c1 = Company(
        tenant_id=seed_tenant.id,
        name="Good Corp",
        domain="good.com",
        status="enriched_l2",
        industry="software_saas",
        hq_country="Germany",
        company_size="51-200",
        summary="A great software company",
        tag_id=tag.id,
        owner_id=owner.id,
    )
    db.session.add(c1)
    db.session.flush()

    l1_good = CompanyEnrichmentL1(
        company_id=c1.id,
        triage_notes="Good company",
        pre_score=8.5,
        quality_score=85,
    )
    l2_good = CompanyEnrichmentL2(
        company_id=c1.id,
        company_intel="Leading SaaS provider",
        recent_news="Expanded to US market",
        ai_opportunities="Process automation",
        pain_hypothesis="Manual workflows",
    )
    db.session.add_all([l1_good, l2_good])

    # Company 2: L1 done but missing fields (gaps)
    c2 = Company(
        tenant_id=seed_tenant.id,
        name="Gap Inc",
        domain="gap.io",
        status="triage_passed",
        industry=None,  # gap: no industry
        hq_country=None,  # gap: no country
        company_size=None,
        summary=None,  # gap: no summary
        tag_id=tag.id,
        owner_id=owner.id,
    )
    db.session.add(c2)
    db.session.flush()

    l1_gap = CompanyEnrichmentL1(
        company_id=c2.id,
        triage_notes="Incomplete data",
        pre_score=5.0,
        quality_score=40,
    )
    db.session.add(l1_gap)

    # Company 3: L1 + registry with country contradiction
    c3 = Company(
        tenant_id=seed_tenant.id,
        name="Conflict Ltd",
        domain="conflict.de",
        status="enriched_l2",
        industry="manufacturing",
        hq_country="Germany",
        company_size="201-500",
        summary="A manufacturing company",
        tag_id=tag.id,
        owner_id=owner.id,
    )
    db.session.add(c3)
    db.session.flush()

    l1_conflict = CompanyEnrichmentL1(
        company_id=c3.id,
        triage_notes="Manufacturing firm",
        pre_score=7.0,
    )
    reg_conflict = CompanyLegalProfile(
        company_id=c3.id,
        official_name="Totally Different Name SpA",
        registration_country="FR",  # contradiction: L1 says Germany, registry says FR
        match_confidence=0.45,
        match_method="name_search",
    )
    l2_conflict = CompanyEnrichmentL2(
        company_id=c3.id,
        company_intel="Known manufacturer",
        recent_news="New factory opened",
    )
    db.session.add_all([l1_conflict, reg_conflict, l2_conflict])

    db.session.commit()
    return {
        "tenant": seed_tenant,
        "tag": tag,
        "c1": c1,
        "c2": c2,
        "c3": c3,
    }


class TestDataQualityService:
    def test_good_company_high_score(self, app, seed_quality_data):
        from api.services.data_quality import analyze_company_data_quality

        data = seed_quality_data
        with app.app_context():
            result = analyze_company_data_quality(
                str(data["c1"].id), str(data["tenant"].id)
            )
            assert result["score"] >= 80
            assert result["company_name"] == "Good Corp"
            assert result["enrichment_coverage"]["l1"] is True
            assert result["enrichment_coverage"]["l2"] is True

    def test_gap_company_flags_missing_fields(self, app, seed_quality_data):
        from api.services.data_quality import analyze_company_data_quality

        data = seed_quality_data
        with app.app_context():
            result = analyze_company_data_quality(
                str(data["c2"].id), str(data["tenant"].id)
            )
            # Should have gap indicators for missing fields
            gap_fields = [
                i["field"] for i in result["indicators"] if i["category"] == "gap"
            ]
            assert "industry" in gap_fields
            assert "hq_country" in gap_fields
            assert "summary" in gap_fields
            assert result["score"] < 80

    def test_contradiction_company_flags_conflicts(self, app, seed_quality_data):
        from api.services.data_quality import analyze_company_data_quality

        data = seed_quality_data
        with app.app_context():
            result = analyze_company_data_quality(
                str(data["c3"].id), str(data["tenant"].id)
            )
            # Should flag country contradiction and name divergence
            categories = [i["category"] for i in result["indicators"]]
            assert "contradiction" in categories
            fields = [i["field"] for i in result["indicators"]]
            assert "hq_country" in fields or "name" in fields

    def test_nonexistent_company(self, app, seed_quality_data):
        from api.services.data_quality import analyze_company_data_quality

        data = seed_quality_data
        with app.app_context():
            result = analyze_company_data_quality(
                str(uuid.uuid4()), str(data["tenant"].id)
            )
            assert result.get("error") == "Company not found"

    def test_batch_analysis(self, app, seed_quality_data):
        from api.services.data_quality import analyze_batch_data_quality

        data = seed_quality_data
        with app.app_context():
            result = analyze_batch_data_quality(
                str(data["tenant"].id), str(data["tag"].id), limit=50
            )
            assert result["total_companies"] == 3
            assert "average_score" in result
            assert "by_category" in result
            assert "top_issues" in result


class TestDataQualityEndpoints:
    def test_company_endpoint(self, client, seed_quality_data):
        data = seed_quality_data
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(
            f"/api/enrich/data-quality/{data['c1'].id}",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["company_name"] == "Good Corp"
        assert "score" in body
        assert "indicators" in body

    def test_batch_endpoint(self, client, seed_quality_data):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(
            "/api/enrich/data-quality?tag_name=quality-test",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total_companies"] == 3

    def test_batch_endpoint_missing_tag(self, client, seed_quality_data):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(
            "/api/enrich/data-quality",
            headers=headers,
        )
        assert resp.status_code == 400
