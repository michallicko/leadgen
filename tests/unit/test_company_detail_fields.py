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
        modules = l2["modules"]

        # Profile fields
        assert modules["profile"]["company_intel"] == "Leading tech firm"
        assert modules["profile"]["key_products"] == "SaaS platform"

        # New signal fields (AC-3)
        assert modules["signals"]["growth_indicators"] == "30% YoY revenue growth"
        assert modules["signals"]["job_posting_count"] == 45

        # New market fields (AC-3)
        assert modules["market"]["media_sentiment"] == "Positive coverage in TechCrunch"
        assert modules["market"]["press_releases"] == "Q4 results published"
        assert (
            modules["market"]["thought_leadership"] == "CEO keynote at SaaS conference"
        )

        # Opportunity fields
        assert (
            modules["opportunity"]["pain_hypothesis"]
            == "Manual processes in supply chain"
        )
        assert (
            modules["opportunity"]["ai_opportunities"]
            == "Automate QC with computer vision"
        )

    def test_new_l2_signals_fields(self, client, db, seed_companies_contacts):
        """BL-156: 6 new signals fields are returned in API response."""
        from api.models import CompanyEnrichmentSignals

        company = seed_companies_contacts["companies"][0]
        signals = CompanyEnrichmentSignals(
            company_id=company.id,
            digital_initiatives="Cloud-first strategy",
            regulatory_pressure="GDPR compliance deadline Q3 2026",
            employee_sentiment="High engagement per Glassdoor",
            digital_maturity_score="7",
            fiscal_year_end="December",
            it_spend_indicators="$2M annual cloud budget",
            tech_stack_categories="CRM: Salesforce, ERP: SAP",
        )
        db.session.add(signals)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(f"/api/companies/{company.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        sig = data["enrichment_l2"]["modules"]["signals"]
        assert sig["regulatory_pressure"] == "GDPR compliance deadline Q3 2026"
        assert sig["employee_sentiment"] == "High engagement per Glassdoor"
        assert sig["digital_maturity_score"] == "7"
        assert sig["fiscal_year_end"] == "December"
        assert sig["it_spend_indicators"] == "$2M annual cloud budget"
        assert sig["tech_stack_categories"] == "CRM: Salesforce, ERP: SAP"

    def test_new_l2_market_fields(self, client, db, seed_companies_contacts):
        """BL-156: 5 new market fields are returned in API response."""
        from api.models import CompanyEnrichmentMarket

        company = seed_companies_contacts["companies"][0]
        market = CompanyEnrichmentMarket(
            company_id=company.id,
            recent_news="IPO rumored",
            expansion="Opened DACH office in Munich",
            workflow_ai_evidence="Uses UiPath for invoice processing",
            revenue_trend="15% YoY growth",
            growth_signals="Hiring 50+ engineers in Q1",
            ma_activity="Acquired DataCo in 2025",
        )
        db.session.add(market)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(f"/api/companies/{company.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        mkt = data["enrichment_l2"]["modules"]["market"]
        assert mkt["expansion"] == "Opened DACH office in Munich"
        assert mkt["workflow_ai_evidence"] == "Uses UiPath for invoice processing"
        assert mkt["revenue_trend"] == "15% YoY growth"
        assert mkt["growth_signals"] == "Hiring 50+ engineers in Q1"
        assert mkt["ma_activity"] == "Acquired DataCo in 2025"

    def test_new_l2_opportunity_fields(self, client, db, seed_companies_contacts):
        """BL-156: pitch_framing field is returned in opportunity module."""
        from api.models import CompanyEnrichmentOpportunity

        company = seed_companies_contacts["companies"][0]
        opp = CompanyEnrichmentOpportunity(
            company_id=company.id,
            pain_hypothesis="Manual data entry slows operations",
            pitch_framing="Position as ROI-driven automation partner",
        )
        db.session.add(opp)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(f"/api/companies/{company.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        opp_data = data["enrichment_l2"]["modules"]["opportunity"]
        assert opp_data["pitch_framing"] == "Position as ROI-driven automation partner"

    def test_new_l2_fields_null_when_absent(self, client, db, seed_companies_contacts):
        """BL-156: New fields are null when not populated (no error)."""
        from api.models import CompanyEnrichmentSignals

        company = seed_companies_contacts["companies"][0]
        # Create signals with only old fields, new fields stay None
        signals = CompanyEnrichmentSignals(
            company_id=company.id,
            digital_initiatives="Some initiative",
        )
        db.session.add(signals)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(f"/api/companies/{company.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        sig = data["enrichment_l2"]["modules"]["signals"]
        assert sig["regulatory_pressure"] is None
        assert sig["employee_sentiment"] is None
        assert sig["digital_maturity_score"] is None
        assert sig["fiscal_year_end"] is None
        assert sig["it_spend_indicators"] is None
        assert sig["tech_stack_categories"] is None
