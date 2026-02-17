"""Tests for company detail API — new enrichment fields (BL-046)."""
import json

import pytest

from tests.conftest import auth_header


class TestCompanyDetailNewFields:
    """Verify new columns appear in GET /api/companies/<id>."""

    def test_new_company_columns_returned(self, client, seed_companies_contacts):
        """AC-4/AC-5: website_url, linkedin_url, logo_url, last_enriched_at, data_quality_score."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        company_id = seed_companies_contacts["companies"][0].id

        resp = client.get(f"/api/companies/{company_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        # New fields present (null since seed data doesn't populate them)
        assert "website_url" in data
        assert "linkedin_url" in data
        assert "logo_url" in data
        assert "last_enriched_at" in data
        assert "data_quality_score" in data

    def test_new_columns_with_values(self, client, db, seed_companies_contacts):
        """AC-4: When populated, new columns are returned with correct values."""
        from api.models import Company

        company = seed_companies_contacts["companies"][0]
        company.website_url = "https://acme.com"
        company.linkedin_url = "https://linkedin.com/company/acme"
        company.logo_url = "https://acme.com/logo.png"
        company.data_quality_score = 85.0
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(f"/api/companies/{company.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["website_url"] == "https://acme.com"
        assert data["linkedin_url"] == "https://linkedin.com/company/acme"
        assert data["logo_url"] == "https://acme.com/logo.png"
        assert data["data_quality_score"] == 85.0

    def test_enrichment_l1_returned(self, client, db, seed_companies_contacts):
        """AC-1: L1 enrichment data returned when available."""
        from api.models import CompanyEnrichmentL1

        company = seed_companies_contacts["companies"][0]
        l1 = CompanyEnrichmentL1(
            company_id=company.id,
            triage_notes="VERDICT: PASS",
            pre_score=7.5,
            research_query="acme corp acme.com",
            confidence=0.85,
            quality_score=7,
            qc_flags=json.dumps(["name_mismatch"]),
        )
        db.session.add(l1)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(f"/api/companies/{company.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["enrichment_l1"] is not None
        assert data["enrichment_l1"]["triage_notes"] == "VERDICT: PASS"
        assert data["enrichment_l1"]["pre_score"] == 7.5
        assert data["enrichment_l1"]["research_query"] == "acme corp acme.com"
        assert data["enrichment_l1"]["confidence"] == 0.85
        assert data["enrichment_l1"]["quality_score"] == 7

    def test_enrichment_l1_null_when_absent(self, client, seed_companies_contacts):
        """AC-5: enrichment_l1 is null when no L1 data exists."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        company_id = seed_companies_contacts["companies"][0].id
        resp = client.get(f"/api/companies/{company_id}", headers=headers)
        data = resp.get_json()

        assert data["enrichment_l1"] is None

    def test_modular_l2_fields(self, client, db, seed_companies_contacts):
        """AC-2/AC-3: L2 data from module tables includes new fields."""
        from api.models import (
            CompanyEnrichmentProfile,
            CompanyEnrichmentSignals,
            CompanyEnrichmentMarket,
            CompanyEnrichmentOpportunity,
        )

        company = seed_companies_contacts["companies"][0]

        profile = CompanyEnrichmentProfile(
            company_id=company.id,
            company_intel="Leading tech firm",
            key_products="SaaS platform",
        )
        signals = CompanyEnrichmentSignals(
            company_id=company.id,
            digital_initiatives="Cloud migration",
            growth_indicators="30% YoY revenue growth",
            job_posting_count=45,
            hiring_departments=json.dumps(["engineering", "sales"]),
        )
        market = CompanyEnrichmentMarket(
            company_id=company.id,
            recent_news="Series B announced",
            media_sentiment="Positive coverage in TechCrunch",
            press_releases="Q4 results published",
            thought_leadership="CEO keynote at SaaS conference",
        )
        opportunity = CompanyEnrichmentOpportunity(
            company_id=company.id,
            pain_hypothesis="Manual processes in supply chain",
            ai_opportunities="Automate QC with computer vision",
        )
        db.session.add_all([profile, signals, market, opportunity])
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(f"/api/companies/{company.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        l2 = data["enrichment_l2"]
        assert l2 is not None

        # Profile fields
        assert l2["company_intel"] == "Leading tech firm"
        assert l2["key_products"] == "SaaS platform"

        # New signal fields (AC-3)
        assert l2["growth_indicators"] == "30% YoY revenue growth"
        assert l2["job_posting_count"] == 45

        # New market fields (AC-3)
        assert l2["media_sentiment"] == "Positive coverage in TechCrunch"
        assert l2["press_releases"] == "Q4 results published"
        assert l2["thought_leadership"] == "CEO keynote at SaaS conference"

        # Opportunity fields
        assert l2["pain_hypothesis"] == "Manual processes in supply chain"
        assert l2["ai_opportunities"] == "Automate QC with computer vision"
