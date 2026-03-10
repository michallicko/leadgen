"""Unit tests for Social & Online enrichment (BL-232)."""

import json
from unittest.mock import MagicMock, patch

from sqlalchemy import text as sa_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_ID = "t0000000-0000-0000-0000-000000000001"
COMPANY_ID = "c0000000-0000-0000-0000-000000000001"
CONTACT_ID = "ct000000-0000-0000-0000-000000000001"


def _make_social_response():
    return {
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "linkedin_activity": "Posts weekly about AI and automation",
        "twitter_handle": "@janedoe_tech",
        "twitter_activity": "Active, tweets about SaaS and AI",
        "github_username": "janedoe",
        "github_activity": "Contributor to open-source ML tools",
        "speaking_engagements": "AI Summit Berlin 2025, SaaStr Europa 2024",
        "publications": "3 articles on LinkedIn about workflow automation",
        "online_presence_summary": "Strong online presence across LinkedIn and Twitter",
        "data_confidence": "high",
    }


def _make_mock_pplx_response(content_dict, cost=0.002):
    resp = MagicMock()
    resp.content = json.dumps(content_dict)
    resp.model = "sonar"
    resp.input_tokens = 500
    resp.output_tokens = 300
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
                                  job_title, linkedin_url)
            VALUES (:id, :tid, :cid, :fn, :ln, :title, :linkedin)
        """),
        {
            "id": CONTACT_ID,
            "tid": TENANT_ID,
            "cid": COMPANY_ID,
            "fn": "Jane",
            "ln": "Doe",
            "title": "VP Engineering",
            "linkedin": "https://linkedin.com/in/janedoe",
        },
    )
    db.session.commit()
    return CONTACT_ID


def _patch_perplexity(response):
    """Return context manager patching PerplexityClient."""
    pplx_cls = MagicMock()
    pplx_instance = pplx_cls.return_value
    pplx_instance.query.return_value = response
    return patch("api.services.social_enricher.PerplexityClient", pplx_cls)


# ---------------------------------------------------------------------------
# Test: Basic enrichment success
# ---------------------------------------------------------------------------


class TestSocialEnrichmentSuccess:
    """Test successful social enrichment flow."""

    def test_returns_cost_and_no_errors(self, app, db):
        from api.services.social_enricher import enrich_social

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_social_response(), cost=0.002)

            with _patch_perplexity(resp):
                result = enrich_social(contact_id)

            assert "enrichment_cost_usd" in result
            assert result["enrichment_cost_usd"] > 0
            assert "error" not in result

    def test_saves_social_fields(self, app, db):
        from api.services.social_enricher import enrich_social

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_social_response(), cost=0.002)

            with _patch_perplexity(resp):
                enrich_social(contact_id)

            row = db.session.execute(
                sa_text(
                    "SELECT twitter_handle, speaking_engagements, publications, "
                    "github_username FROM contact_enrichment WHERE contact_id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row is not None
            assert row[0] == "@janedoe_tech"  # twitter_handle
            assert "AI Summit" in row[1]  # speaking_engagements
            assert "automation" in row[2]  # publications
            assert row[3] == "janedoe"  # github_username

    def test_correct_perplexity_prompt(self, app, db):
        from api.services.social_enricher import enrich_social

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_social_response(), cost=0.002)

            with _patch_perplexity(resp) as pplx_p:
                enrich_social(contact_id)

            pplx_instance = pplx_p.return_value
            call_kwargs = pplx_instance.query.call_args[1]
            user_prompt = (
                call_kwargs.get("user_prompt") or pplx_instance.query.call_args[0][1]
            )
            assert "Jane Doe" in user_prompt
            assert "testcorp.com" in user_prompt


# ---------------------------------------------------------------------------
# Test: LinkedIn URL update
# ---------------------------------------------------------------------------


class TestSocialLinkedInUpdate:
    """Test that LinkedIn URL is written to contacts table when empty."""

    def test_updates_linkedin_when_empty(self, app, db):
        from api.services.social_enricher import enrich_social

        with app.app_context():
            # Create contact without LinkedIn
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
                    INSERT INTO contacts (id, tenant_id, company_id, first_name,
                                          last_name, job_title)
                    VALUES (:id, :tid, :cid, :fn, :ln, :title)
                """),
                {
                    "id": CONTACT_ID,
                    "tid": TENANT_ID,
                    "cid": COMPANY_ID,
                    "fn": "Jane",
                    "ln": "Doe",
                    "title": "VP Engineering",
                },
            )
            db.session.commit()

            resp = _make_mock_pplx_response(_make_social_response(), cost=0.002)
            with _patch_perplexity(resp):
                enrich_social(CONTACT_ID)

            row = db.session.execute(
                sa_text("SELECT linkedin_url FROM contacts WHERE id = :cid"),
                {"cid": CONTACT_ID},
            ).fetchone()
            assert row[0] == "https://linkedin.com/in/janedoe"


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestSocialErrorHandling:
    """Test error scenarios."""

    def test_contact_not_found(self, app, db):
        from api.services.social_enricher import enrich_social

        with app.app_context():
            _setup_contact(db)
            result = enrich_social("ct000000-0000-0000-0000-nonexistent00")

            assert result.get("error") is not None
            assert result["enrichment_cost_usd"] == 0

    def test_perplexity_error_returns_failure(self, app, db):
        from api.services.social_enricher import enrich_social
        from requests.exceptions import HTTPError

        with app.app_context():
            contact_id = _setup_contact(db)
            pplx_cls = MagicMock()
            pplx_instance = pplx_cls.return_value
            pplx_instance.query.side_effect = HTTPError("503 Service Unavailable")

            with patch("api.services.social_enricher.PerplexityClient", pplx_cls):
                result = enrich_social(contact_id)

            assert result.get("error") is not None

    def test_empty_response_no_crash(self, app, db):
        from api.services.social_enricher import enrich_social

        with app.app_context():
            contact_id = _setup_contact(db)
            # Response with all nulls
            empty_data = {
                "linkedin_url": None,
                "twitter_handle": None,
                "github_username": None,
                "speaking_engagements": "None found",
                "publications": "None found",
                "data_confidence": "low",
            }
            resp = _make_mock_pplx_response(empty_data, cost=0.001)

            with _patch_perplexity(resp):
                result = enrich_social(contact_id)

            assert "error" not in result
            assert result["enrichment_cost_usd"] > 0


# ---------------------------------------------------------------------------
# Test: Boost mode
# ---------------------------------------------------------------------------


class TestSocialBoostMode:
    """Test boost model selection."""

    def test_standard_model_by_default(self, app, db):
        from api.services.social_enricher import enrich_social

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_social_response(), cost=0.002)

            with _patch_perplexity(resp) as pplx_p:
                enrich_social(contact_id, boost=False)

            pplx_instance = pplx_p.return_value
            call_kwargs = pplx_instance.query.call_args[1]
            assert call_kwargs["model"] == "sonar"

    def test_boost_model_when_enabled(self, app, db):
        from api.services.social_enricher import enrich_social

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(_make_social_response(), cost=0.005)

            with _patch_perplexity(resp) as pplx_p:
                enrich_social(contact_id, boost=True)

            pplx_instance = pplx_p.return_value
            call_kwargs = pplx_instance.query.call_args[1]
            assert call_kwargs["model"] == "sonar-pro"
