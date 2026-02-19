"""Unit tests for L2 Deep Research enrichment."""

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text as sa_text

from api.services.l2_enricher import enrich_l2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_news_response():
    return {
        "recent_news": "Jan 2026: Secured EUR 5M Series A",
        "funding": "EUR 5M Series A from Accel, Jan 2026",
        "leadership_changes": "New CTO hired: Jane Doe, Dec 2025",
        "expansion": "Opened Berlin office, Nov 2025",
        "workflow_ai_evidence": "None found",
        "digital_initiatives": "Migrated to AWS, Oct 2025",
        "revenue_trend": "growing — 40% YoY growth",
        "growth_signals": "Headcount grew from 80 to 120",
        "news_confidence": "high",
    }


def _make_strategic_response():
    return {
        "leadership_team": "CEO: John Smith, CTO: Jane Doe",
        "ai_transformation_roles": "Hiring: AI Engineer, Data Scientist",
        "other_hiring_signals": "5 open roles in engineering",
        "eu_grants": "None found",
        "certifications": "ISO 27001",
        "regulatory_pressure": "NIS2 deadline Q4 2025",
        "vendor_partnerships": "AWS Advanced Partner",
        "employee_sentiment": "Glassdoor: 4.2/5 (45 reviews)",
        "data_completeness": "high",
    }


def _make_synthesis_response():
    return {
        "ai_opportunities": "1. Process Automation: Evidence from AWS migration",
        "pain_hypothesis": "Growing fast but manual processes not scaling",
        "quick_wins": [
            {
                "use_case": "Automate onboarding docs",
                "evidence": "Rapid headcount growth",
                "impact": "Save 10h/week in HR",
                "complexity": "low",
            }
        ],
        "industry_pain_points": "Manual reporting, slow proposal generation",
        "cross_functional_pain": "Data silos between sales and ops",
        "adoption_barriers": "No dedicated AI team yet",
        "competitor_ai_moves": "Competitor X launched AI chatbot",
        "pitch_framing": "growth_acceleration",
        "executive_brief": "Fast-growing SaaS company, just raised Series A.",
    }


def _make_mock_pplx_response(content_dict, cost=0.003):
    resp = MagicMock()
    resp.content = json.dumps(content_dict)
    resp.model = "sonar-pro"
    resp.input_tokens = 800
    resp.output_tokens = 400
    resp.cost_usd = cost
    return resp


def _make_mock_anthropic_response(content_dict, cost=0.004):
    resp = MagicMock()
    resp.content = json.dumps(content_dict)
    resp.model = "claude-sonnet-4-5-20250929"
    resp.input_tokens = 1200
    resp.output_tokens = 600
    resp.cost_usd = cost
    return resp


def _patch_clients(news_resp, strategic_resp, synthesis_resp):
    """Return context managers patching PerplexityClient and AnthropicClient."""
    pplx_cls = MagicMock()
    pplx_instance = pplx_cls.return_value
    pplx_instance.query.side_effect = [news_resp, strategic_resp]

    anthro_cls = MagicMock()
    anthro_instance = anthro_cls.return_value
    anthro_instance.query.return_value = synthesis_resp

    return (
        patch("api.services.l2_enricher.PerplexityClient", pplx_cls),
        patch("api.services.l2_enricher.AnthropicClient", anthro_cls),
    )


def _setup_company_with_l1(db):
    """Insert a test company with L1 enrichment data. Returns company_id."""
    company_id = "c0000000-0000-0000-0000-000000000001"
    tenant_id = "t0000000-0000-0000-0000-000000000001"

    db.session.execute(
        sa_text("""
            INSERT INTO tenants (id, name, slug) VALUES (:tid, :name, :slug)
        """),
        {"tid": tenant_id, "name": "Test Tenant", "slug": "test"},
    )
    db.session.execute(
        sa_text("""
            INSERT INTO companies (id, tenant_id, name, domain, industry, status,
                                   verified_revenue_eur_m, verified_employees,
                                   geo_region, tier, hq_country)
            VALUES (:id, :tid, :name, :domain, :industry, :status,
                    :revenue, :employees, :geo, :tier, :country)
        """),
        {
            "id": company_id,
            "tid": tenant_id,
            "name": "TestCorp",
            "domain": "testcorp.com",
            "industry": "software_saas",
            "status": "triage_passed",
            "revenue": 10.0,
            "employees": 120,
            "geo": "dach",
            "tier": "tier_1",
            "country": "Germany",
        },
    )
    db.session.execute(
        sa_text("""
            INSERT INTO company_enrichment_l1 (company_id, raw_response, confidence,
                                               qc_flags, enriched_at)
            VALUES (:cid, :raw, :conf, :qc, CURRENT_TIMESTAMP)
        """),
        {
            "cid": company_id,
            "raw": json.dumps({
                "company_name": "TestCorp",
                "summary": "A B2B SaaS platform for workflow automation",
                "b2b": True,
                "industry": "software_saas",
                "revenue_eur_m": 10.0,
                "employees": 120,
                "hq": "Berlin, Germany",
                "ownership": "VC-backed",
                "markets": ["DACH", "Nordics"],
                "business_model": "saas",
            }),
            "conf": 0.85,
            "qc": json.dumps([]),
        },
    )
    db.session.commit()
    return company_id


# ---------------------------------------------------------------------------
# Test: Basic enrichment success
# ---------------------------------------------------------------------------

class TestL2EnrichmentSuccess:
    """Test successful L2 enrichment flow."""

    def test_returns_cost_and_no_errors(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.003)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(news_resp, strategic_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                result = enrich_l2(company_id)

            assert "enrichment_cost_usd" in result
            assert result["enrichment_cost_usd"] > 0
            assert "error" not in result

    def test_saves_l2_enrichment_record(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.003)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(news_resp, strategic_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                enrich_l2(company_id)

            row = db.session.execute(
                sa_text(
                    "SELECT company_intel, pain_hypothesis, ai_opportunities "
                    "FROM company_enrichment_l2 WHERE company_id = :cid"
                ),
                {"cid": company_id},
            ).fetchone()
            assert row is not None

    def test_updates_company_status(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.003)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(news_resp, strategic_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                enrich_l2(company_id)

            status = db.session.execute(
                sa_text("SELECT status FROM companies WHERE id = :cid"),
                {"cid": company_id},
            ).scalar()
            assert status == "enriched_l2"

    def test_aggregates_cost_from_all_calls(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.003)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(news_resp, strategic_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                result = enrich_l2(company_id)

            # Total = 0.003 + 0.002 + 0.004 = 0.009
            assert abs(result["enrichment_cost_usd"] - 0.009) < 0.001


# ---------------------------------------------------------------------------
# Test: L1 data loading
# ---------------------------------------------------------------------------

class TestL1DataLoading:
    """Test that L2 reads and uses L1 data in prompts."""

    def test_passes_l1_data_to_synthesis(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.003)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(news_resp, strategic_resp, synthesis_resp)
            with pplx_patch, anthro_patch as anthro_p:
                enrich_l2(company_id)

            anthro_instance = anthro_p.return_value
            assert anthro_instance.query.call_count == 1
            call_args = anthro_instance.query.call_args
            user_prompt = call_args[1].get("user_prompt") or call_args[0][1]
            assert "TestCorp" in user_prompt
            assert "testcorp.com" in user_prompt

    def test_passes_company_data_to_perplexity(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.003)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(news_resp, strategic_resp, synthesis_resp)
            with pplx_patch as pplx_p, anthro_patch:
                enrich_l2(company_id)

            pplx_instance = pplx_p.return_value
            assert pplx_instance.query.call_count == 2
            for call in pplx_instance.query.call_args_list:
                user_prompt = call[1].get("user_prompt") or call[0][1]
                assert "TestCorp" in user_prompt


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------

class TestL2ErrorHandling:
    """Test error scenarios in L2 enrichment."""

    def test_perplexity_error_returns_failure(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            pplx_cls = MagicMock()
            pplx_instance = pplx_cls.return_value
            from requests.exceptions import HTTPError
            pplx_instance.query.side_effect = HTTPError("503 Service Unavailable")

            anthro_cls = MagicMock()

            with patch("api.services.l2_enricher.PerplexityClient", pplx_cls), \
                 patch("api.services.l2_enricher.AnthropicClient", anthro_cls):
                result = enrich_l2(company_id)

            assert result.get("error") is not None
            status = db.session.execute(
                sa_text("SELECT status FROM companies WHERE id = :cid"),
                {"cid": company_id},
            ).scalar()
            assert status == "enrichment_l2_failed"

    def test_synthesis_error_still_saves_research(self, app, db):
        """If Anthropic fails, we still save raw Perplexity research."""
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.003)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)

            pplx_cls = MagicMock()
            pplx_instance = pplx_cls.return_value
            pplx_instance.query.side_effect = [news_resp, strategic_resp]

            anthro_cls = MagicMock()
            anthro_instance = anthro_cls.return_value
            anthro_instance.query.side_effect = Exception("Anthropic API down")

            with patch("api.services.l2_enricher.PerplexityClient", pplx_cls), \
                 patch("api.services.l2_enricher.AnthropicClient", anthro_cls):
                result = enrich_l2(company_id)

            assert result["enrichment_cost_usd"] > 0
            row = db.session.execute(
                sa_text(
                    "SELECT recent_news FROM company_enrichment_l2 WHERE company_id = :cid"
                ),
                {"cid": company_id},
            ).fetchone()
            assert row is not None

    def test_bad_json_from_perplexity_handled(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            bad_resp = MagicMock()
            bad_resp.content = "This is not valid JSON at all"
            bad_resp.model = "sonar-pro"
            bad_resp.input_tokens = 800
            bad_resp.output_tokens = 400
            bad_resp.cost_usd = 0.003

            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_cls = MagicMock()
            pplx_instance = pplx_cls.return_value
            pplx_instance.query.side_effect = [bad_resp, strategic_resp]

            anthro_cls = MagicMock()
            anthro_instance = anthro_cls.return_value
            anthro_instance.query.return_value = synthesis_resp

            with patch("api.services.l2_enricher.PerplexityClient", pplx_cls), \
                 patch("api.services.l2_enricher.AnthropicClient", anthro_cls):
                result = enrich_l2(company_id)

            assert "enrichment_cost_usd" in result


# ---------------------------------------------------------------------------
# Test: Boost mode
# ---------------------------------------------------------------------------

class TestL2BoostMode:
    """Test boost model selection for L2."""

    def test_standard_model_by_default(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.003)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(news_resp, strategic_resp, synthesis_resp)
            with pplx_patch as pplx_p, anthro_patch:
                enrich_l2(company_id, boost=False)

            pplx_instance = pplx_p.return_value
            for call in pplx_instance.query.call_args_list:
                model = call[1].get("model")
                assert model == "sonar-pro"

    def test_boost_model_when_enabled(self, app, db):
        with app.app_context():
            company_id = _setup_company_with_l1(db)
            news_resp = _make_mock_pplx_response(_make_news_response(), cost=0.010)
            strategic_resp = _make_mock_pplx_response(_make_strategic_response(), cost=0.008)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(news_resp, strategic_resp, synthesis_resp)
            with pplx_patch as pplx_p, anthro_patch:
                enrich_l2(company_id, boost=True)

            pplx_instance = pplx_p.return_value
            for call in pplx_instance.query.call_args_list:
                model = call[1].get("model")
                assert model == "sonar-reasoning-pro"
