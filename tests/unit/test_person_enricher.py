"""Unit tests for Person enrichment."""

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text as sa_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_ID = "t0000000-0000-0000-0000-000000000001"
COMPANY_ID = "c0000000-0000-0000-0000-000000000001"
CONTACT_ID = "ct000000-0000-0000-0000-000000000001"


def _make_profile_response():
    return {
        "current_role_verified": True,
        "role_verification_source": "LinkedIn",
        "role_mismatch_flag": None,
        "career_highlights": "10y in B2B SaaS, ex-Salesforce",
        "career_trajectory": "ascending",
        "thought_leadership": "Regular LinkedIn poster on AI topics",
        "thought_leadership_topics": ["AI", "automation", "digital transformation"],
        "education": "MSc Computer Science, TU Munich",
        "certifications": "AWS Solutions Architect",
        "expertise_areas": ["AI/ML", "SaaS", "Process Automation"],
        "public_presence_level": "medium",
        "data_confidence": "high",
    }


def _make_signals_response():
    return {
        "ai_champion_evidence": "Led AI chatbot implementation, posts about ML weekly",
        "ai_champion_score": 4,
        "authority_signals": "Manages team of 15, approved $2M platform migration",
        "authority_level": "high",
        "team_size_indication": "15 engineers",
        "budget_signals": "Approved $2M migration budget",
        "technology_interests": ["AI/ML", "cloud migration", "workflow automation"],
        "pain_indicators": "Mentioned manual reporting challenges in blog post",
        "buying_signals": "Evaluating new CRM tools per LinkedIn post",
        "recent_activity_level": "active",
        "data_confidence": "high",
    }


def _make_synthesis_response():
    return {
        "personalization_angle": "Tech-forward VP driving AI adoption",
        "connection_points": [
            "Both attended AI Summit Berlin 2025",
            "Published article on process automation",
            "Leading cloud migration initiative",
        ],
        "pain_connection": "Manual reporting slowing team velocity",
        "conversation_starters": "How is the cloud migration affecting your AI roadmap?",
        "objection_prediction": "Already evaluating alternatives — position as complementary",
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


def _patch_clients(profile_resp, signals_resp, synthesis_resp):
    """Return context managers patching PerplexityClient and AnthropicClient."""
    pplx_cls = MagicMock()
    pplx_instance = pplx_cls.return_value
    pplx_instance.query.side_effect = [profile_resp, signals_resp]

    anthro_cls = MagicMock()
    anthro_instance = anthro_cls.return_value
    anthro_instance.query.return_value = synthesis_resp

    return (
        patch("api.services.person_enricher.PerplexityClient", pplx_cls),
        patch("api.services.person_enricher.AnthropicClient", anthro_cls),
    )


def _setup_contact_with_company(db):
    """Insert tenant, company with L1+L2, and contact. Returns contact_id."""
    db.session.execute(
        sa_text("""
            INSERT INTO tenants (id, name, slug) VALUES (:tid, :name, :slug)
        """),
        {"tid": TENANT_ID, "name": "Test Tenant", "slug": "test"},
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
            "id": COMPANY_ID,
            "tid": TENANT_ID,
            "name": "TestCorp",
            "domain": "testcorp.com",
            "industry": "software_saas",
            "status": "enriched_l2",
            "revenue": 10.0,
            "employees": 120,
            "geo": "dach",
            "tier": "tier_1",
            "country": "Germany",
        },
    )
    # L1 enrichment
    db.session.execute(
        sa_text("""
            INSERT INTO company_enrichment_l1 (company_id, raw_response, confidence,
                                               qc_flags, enriched_at)
            VALUES (:cid, :raw, :conf, :qc, CURRENT_TIMESTAMP)
        """),
        {
            "cid": COMPANY_ID,
            "raw": json.dumps({
                "company_name": "TestCorp",
                "summary": "A B2B SaaS platform",
                "b2b": True,
                "industry": "software_saas",
            }),
            "conf": 0.85,
            "qc": json.dumps([]),
        },
    )
    # L2 enrichment
    db.session.execute(
        sa_text("""
            INSERT INTO company_enrichment_l2 (company_id, company_intel,
                                               pain_hypothesis, ai_opportunities,
                                               enriched_at)
            VALUES (:cid, :intel, :pain, :ai, CURRENT_TIMESTAMP)
        """),
        {
            "cid": COMPANY_ID,
            "intel": "B2B SaaS for workflow automation, growing fast",
            "pain": "Manual processes not scaling with headcount growth",
            "ai": "Process automation, intelligent document handling",
        },
    )
    # Contact
    db.session.execute(
        sa_text("""
            INSERT INTO contacts (id, tenant_id, company_id, first_name, last_name,
                                  job_title, email_address, linkedin_url,
                                  location_city, location_country, processed_enrich)
            VALUES (:id, :tid, :cid, :fn, :ln, :title, :email, :linkedin,
                    :city, :country, :processed)
        """),
        {
            "id": CONTACT_ID,
            "tid": TENANT_ID,
            "cid": COMPANY_ID,
            "fn": "Jane",
            "ln": "Doe",
            "title": "VP Engineering",
            "email": "jane@testcorp.com",
            "linkedin": "https://linkedin.com/in/janedoe",
            "city": "Berlin",
            "country": "Germany",
            "processed": False,
        },
    )
    db.session.commit()
    return CONTACT_ID


# ---------------------------------------------------------------------------
# Test: Basic enrichment success
# ---------------------------------------------------------------------------

class TestPersonEnrichmentSuccess:
    """Test successful person enrichment flow."""

    def test_returns_cost_and_no_errors(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.003)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(profile_resp, signals_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                result = enrich_person(contact_id)

            assert "enrichment_cost_usd" in result
            assert result["enrichment_cost_usd"] > 0
            assert "error" not in result

    def test_saves_enrichment_record(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.003)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(profile_resp, signals_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                enrich_person(contact_id)

            row = db.session.execute(
                sa_text(
                    "SELECT person_summary, linkedin_profile_summary "
                    "FROM contact_enrichment WHERE contact_id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row is not None
            assert row[0] is not None  # person_summary

    def test_updates_contact_fields(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.003)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(profile_resp, signals_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                enrich_person(contact_id)

            row = db.session.execute(
                sa_text(
                    "SELECT seniority_level, department, ai_champion, "
                    "contact_score, processed_enrich FROM contacts WHERE id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row is not None
            assert row[0] is not None  # seniority_level
            assert row[1] is not None  # department
            assert row[4]  # processed_enrich (SQLite returns 1, PG returns True)

    def test_aggregates_cost(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.003)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(profile_resp, signals_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                result = enrich_person(contact_id)

            # Total = 0.003 + 0.002 + 0.004 = 0.009
            assert abs(result["enrichment_cost_usd"] - 0.009) < 0.001


# ---------------------------------------------------------------------------
# Test: Scoring logic
# ---------------------------------------------------------------------------

class TestPersonScoring:
    """Test the validate & score logic."""

    def test_detects_vp_seniority(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.003)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(profile_resp, signals_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                enrich_person(contact_id)

            row = db.session.execute(
                sa_text("SELECT seniority_level FROM contacts WHERE id = :cid"),
                {"cid": contact_id},
            ).fetchone()
            assert row[0] == "VP"

    def test_detects_engineering_department(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.003)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(profile_resp, signals_resp, synthesis_resp)
            with pplx_patch, anthro_patch:
                enrich_person(contact_id)

            row = db.session.execute(
                sa_text("SELECT department FROM contacts WHERE id = :cid"),
                {"cid": contact_id},
            ).fetchone()
            assert row[0] == "Engineering"


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------

class TestPersonErrorHandling:
    """Test error scenarios in person enrichment."""

    def test_perplexity_error_returns_failure(self, app, db):
        from api.services.person_enricher import enrich_person
        from requests.exceptions import HTTPError

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            pplx_cls = MagicMock()
            pplx_instance = pplx_cls.return_value
            pplx_instance.query.side_effect = HTTPError("503 Service Unavailable")

            anthro_cls = MagicMock()

            with patch("api.services.person_enricher.PerplexityClient", pplx_cls), \
                 patch("api.services.person_enricher.AnthropicClient", anthro_cls):
                result = enrich_person(contact_id)

            assert result.get("error") is not None

    def test_synthesis_error_still_saves_research(self, app, db):
        """If Anthropic fails, we still save raw research data."""
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.003)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.002)

            pplx_cls = MagicMock()
            pplx_instance = pplx_cls.return_value
            pplx_instance.query.side_effect = [profile_resp, signals_resp]

            anthro_cls = MagicMock()
            anthro_instance = anthro_cls.return_value
            anthro_instance.query.side_effect = Exception("Anthropic API down")

            with patch("api.services.person_enricher.PerplexityClient", pplx_cls), \
                 patch("api.services.person_enricher.AnthropicClient", anthro_cls):
                result = enrich_person(contact_id)

            # Should still have cost from Perplexity
            assert result["enrichment_cost_usd"] > 0

            row = db.session.execute(
                sa_text(
                    "SELECT person_summary FROM contact_enrichment WHERE contact_id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row is not None

    def test_contact_not_found_returns_error(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            _setup_contact_with_company(db)
            result = enrich_person("ct000000-0000-0000-0000-nonexistent00")

            assert result.get("error") is not None
            assert result["enrichment_cost_usd"] == 0


# ---------------------------------------------------------------------------
# Test: Boost mode
# ---------------------------------------------------------------------------

class TestPersonBoostMode:
    """Test boost model selection for person enrichment."""

    def test_standard_model_by_default(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.003)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.002)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(profile_resp, signals_resp, synthesis_resp)
            with pplx_patch as pplx_p, anthro_patch:
                enrich_person(contact_id, boost=False)

            pplx_instance = pplx_p.return_value
            for call in pplx_instance.query.call_args_list:
                model = call[1].get("model")
                # Person standard model is "sonar" per stage_registry
                assert model == "sonar"

    def test_boost_model_when_enabled(self, app, db):
        from api.services.person_enricher import enrich_person

        with app.app_context():
            contact_id = _setup_contact_with_company(db)
            profile_resp = _make_mock_pplx_response(_make_profile_response(), cost=0.010)
            signals_resp = _make_mock_pplx_response(_make_signals_response(), cost=0.008)
            synthesis_resp = _make_mock_anthropic_response(_make_synthesis_response(), cost=0.004)

            pplx_patch, anthro_patch = _patch_clients(profile_resp, signals_resp, synthesis_resp)
            with pplx_patch as pplx_p, anthro_patch:
                enrich_person(contact_id, boost=True)

            pplx_instance = pplx_p.return_value
            for call in pplx_instance.query.call_args_list:
                model = call[1].get("model")
                # Person boost model is "sonar-pro" per stage_registry
                assert model == "sonar-pro"
