"""Unit tests for Career History enrichment (BL-235)."""

import json
from unittest.mock import MagicMock, patch

from sqlalchemy import text as sa_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_ID = "t0000000-0000-0000-0000-000000000001"
COMPANY_ID = "c0000000-0000-0000-0000-000000000001"
CONTACT_ID = "ct000000-0000-0000-0000-000000000001"


def _make_career_response():
    return {
        "career_trajectory": "ascending",
        "career_summary": "Progressed from engineer to VP over 12 years in B2B SaaS",
        "previous_companies": [
            {
                "name": "Salesforce",
                "role": "Senior Engineer",
                "duration": "4y",
                "industry": "CRM/SaaS",
            },
            {
                "name": "Stripe",
                "role": "Engineering Manager",
                "duration": "3y",
                "industry": "FinTech",
            },
        ],
        "industry_experience": [
            {"industry": "SaaS", "years": 8},
            {"industry": "FinTech", "years": 3},
        ],
        "total_experience_years": 12,
        "tenure_pattern": "Average 3-4 years per company, stable career",
        "career_highlights": "Led team of 20 at Stripe, shipped key payment integration",
        "data_confidence": "high",
    }


def _make_mock_pplx_response(content_dict, cost=0.003):
    resp = MagicMock()
    resp.content = json.dumps(content_dict)
    resp.model = "sonar"
    resp.input_tokens = 600
    resp.output_tokens = 400
    resp.cost_usd = cost
    return resp


def _setup_contact(db):
    """Insert tenant, company, and contact. Returns contact_id."""
    db.session.execute(
        sa_text("""
            INSERT INTO tenants (id, name, slug) VALUES (:tid, :name, :slug)
        """),
        {"tid": TENANT_ID, "name": "Test Tenant", "slug": "test"},
    )
    db.session.execute(
        sa_text("""
            INSERT INTO companies (id, tenant_id, name, domain, industry, status)
            VALUES (:id, :tid, :name, :domain, :industry, :status)
        """),
        {
            "id": COMPANY_ID,
            "tid": TENANT_ID,
            "name": "TestCorp",
            "domain": "testcorp.com",
            "industry": "software_saas",
            "status": "enriched_l2",
        },
    )
    db.session.execute(
        sa_text("""
            INSERT INTO contacts (id, tenant_id, company_id, first_name, last_name,
                                  job_title, linkedin_url,
                                  location_city, location_country)
            VALUES (:id, :tid, :cid, :fn, :ln, :title, :linkedin, :city, :country)
        """),
        {
            "id": CONTACT_ID,
            "tid": TENANT_ID,
            "cid": COMPANY_ID,
            "fn": "Jane",
            "ln": "Doe",
            "title": "VP Engineering",
            "linkedin": "https://linkedin.com/in/janedoe",
            "city": "Berlin",
            "country": "Germany",
        },
    )
    db.session.commit()
    return CONTACT_ID


def _patch_perplexity(response):
    """Return context manager patching PerplexityClient."""
    pplx_cls = MagicMock()
    pplx_instance = pplx_cls.return_value
    pplx_instance.query.return_value = response
    return patch("api.services.career_enricher.PerplexityClient", pplx_cls)


# ---------------------------------------------------------------------------
# Test: Basic enrichment success
# ---------------------------------------------------------------------------


class TestCareerEnrichmentSuccess:
    """Test successful career enrichment flow."""

    def test_returns_cost_and_no_errors(self, app, db):
        from api.services.career_enricher import enrich_career

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_career_response(), cost=0.003)

            with _patch_perplexity(resp):
                result = enrich_career(contact_id)

            assert "enrichment_cost_usd" in result
            assert result["enrichment_cost_usd"] > 0
            assert "error" not in result

    def test_saves_career_fields(self, app, db):
        from api.services.career_enricher import enrich_career

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_career_response(), cost=0.003)

            with _patch_perplexity(resp):
                enrich_career(contact_id)

            row = db.session.execute(
                sa_text(
                    "SELECT career_trajectory, career_highlights, previous_companies, "
                    "industry_experience, total_experience_years "
                    "FROM contact_enrichment WHERE contact_id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row is not None
            assert row[0] == "ascending"  # career_trajectory
            assert "Stripe" in row[1]  # career_highlights
            # previous_companies is JSON (stored as text in SQLite)
            prev = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            assert len(prev) == 2
            assert prev[0]["name"] == "Salesforce"
            # industry_experience is JSON
            ind_exp = json.loads(row[3]) if isinstance(row[3], str) else row[3]
            assert len(ind_exp) == 2
            assert ind_exp[0]["industry"] == "SaaS"
            # total_experience_years
            assert row[4] == 12

    def test_correct_perplexity_prompt(self, app, db):
        from api.services.career_enricher import enrich_career

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_career_response(), cost=0.003)

            with _patch_perplexity(resp) as pplx_p:
                enrich_career(contact_id)

            pplx_instance = pplx_p.return_value
            call_kwargs = pplx_instance.query.call_args[1]
            user_prompt = (
                call_kwargs.get("user_prompt") or pplx_instance.query.call_args[0][1]
            )
            assert "Jane Doe" in user_prompt
            assert "testcorp.com" in user_prompt
            assert "VP Engineering" in user_prompt


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestCareerErrorHandling:
    """Test error scenarios."""

    def test_contact_not_found(self, app, db):
        from api.services.career_enricher import enrich_career

        with app.app_context():
            _setup_contact(db)
            result = enrich_career("ct000000-0000-0000-0000-nonexistent00")

            assert result.get("error") is not None
            assert result["enrichment_cost_usd"] == 0

    def test_perplexity_error_returns_failure(self, app, db):
        from api.services.career_enricher import enrich_career
        from requests.exceptions import HTTPError

        with app.app_context():
            contact_id = _setup_contact(db)
            pplx_cls = MagicMock()
            pplx_instance = pplx_cls.return_value
            pplx_instance.query.side_effect = HTTPError("503 Service Unavailable")

            with patch("api.services.career_enricher.PerplexityClient", pplx_cls):
                result = enrich_career(contact_id)

            assert result.get("error") is not None

    def test_handles_invalid_experience_years(self, app, db):
        from api.services.career_enricher import enrich_career

        with app.app_context():
            contact_id = _setup_contact(db)
            data = _make_career_response()
            data["total_experience_years"] = "not a number"
            resp = _make_mock_pplx_response(data, cost=0.003)

            with _patch_perplexity(resp):
                result = enrich_career(contact_id)

            assert "error" not in result

            row = db.session.execute(
                sa_text(
                    "SELECT total_experience_years "
                    "FROM contact_enrichment WHERE contact_id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row is not None
            assert row[0] is None  # Invalid value stored as null


# ---------------------------------------------------------------------------
# Test: Boost mode
# ---------------------------------------------------------------------------


class TestCareerBoostMode:
    """Test boost model selection."""

    def test_standard_model_by_default(self, app, db):
        from api.services.career_enricher import enrich_career

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_career_response(), cost=0.003)

            with _patch_perplexity(resp) as pplx_p:
                enrich_career(contact_id, boost=False)

            pplx_instance = pplx_p.return_value
            call_kwargs = pplx_instance.query.call_args[1]
            assert call_kwargs["model"] == "sonar"

    def test_boost_model_when_enabled(self, app, db):
        from api.services.career_enricher import enrich_career

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_career_response(), cost=0.006)

            with _patch_perplexity(resp) as pplx_p:
                enrich_career(contact_id, boost=True)

            pplx_instance = pplx_p.return_value
            call_kwargs = pplx_instance.query.call_args[1]
            assert call_kwargs["model"] == "sonar-pro"
