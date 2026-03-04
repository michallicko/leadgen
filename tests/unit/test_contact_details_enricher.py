"""Unit tests for Contact Details enrichment (BL-233)."""

import json
from unittest.mock import MagicMock, patch

from sqlalchemy import text as sa_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_ID = "t0000000-0000-0000-0000-000000000001"
COMPANY_ID = "c0000000-0000-0000-0000-000000000001"
CONTACT_ID = "ct000000-0000-0000-0000-000000000001"


def _make_contact_details_response():
    return {
        "email_address": "jane.doe@testcorp.com",
        "email_confidence": "high",
        "phone_number": "+49301234567",
        "phone_confidence": "medium",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "profile_photo_url": "https://media.licdn.com/janedoe.jpg",
        "data_confidence": "high",
    }


def _make_mock_pplx_response(content_dict, cost=0.001):
    resp = MagicMock()
    resp.content = json.dumps(content_dict)
    resp.model = "sonar"
    resp.input_tokens = 400
    resp.output_tokens = 200
    resp.cost_usd = cost
    return resp


def _setup_contact(db, email=None, phone=None, linkedin=None):
    """Insert tenant, company, and contact with optional existing fields."""
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
                                  job_title, email_address, phone_number, linkedin_url)
            VALUES (:id, :tid, :cid, :fn, :ln, :title, :email, :phone, :linkedin)
        """),
        {
            "id": CONTACT_ID,
            "tid": TENANT_ID,
            "cid": COMPANY_ID,
            "fn": "Jane",
            "ln": "Doe",
            "title": "VP Engineering",
            "email": email,
            "phone": phone,
            "linkedin": linkedin,
        },
    )
    db.session.commit()
    return CONTACT_ID


def _patch_perplexity(response):
    """Return context manager patching PerplexityClient."""
    pplx_cls = MagicMock()
    pplx_instance = pplx_cls.return_value
    pplx_instance.query.return_value = response
    return patch("api.services.contact_details_enricher.PerplexityClient", pplx_cls)


# ---------------------------------------------------------------------------
# Test: Basic enrichment success
# ---------------------------------------------------------------------------


class TestContactDetailsSuccess:
    """Test successful contact details enrichment."""

    def test_returns_cost_and_no_errors(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(
                _make_contact_details_response(), cost=0.001
            )

            with _patch_perplexity(resp):
                result = enrich_contact_details(contact_id)

            assert "enrichment_cost_usd" in result
            assert result["enrichment_cost_usd"] > 0
            assert "error" not in result

    def test_fills_empty_fields(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            # Contact with no email, phone, or linkedin
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(
                _make_contact_details_response(), cost=0.001
            )

            with _patch_perplexity(resp):
                enrich_contact_details(contact_id)

            row = db.session.execute(
                sa_text(
                    "SELECT email_address, phone_number, linkedin_url, "
                    "profile_photo_url FROM contacts WHERE id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row[0] == "jane.doe@testcorp.com"  # email filled
            assert row[1] == "+49301234567"  # phone filled
            assert row[2] == "https://linkedin.com/in/janedoe"  # linkedin filled
            assert row[3] == "https://media.licdn.com/janedoe.jpg"  # photo filled


# ---------------------------------------------------------------------------
# Test: Don't overwrite existing values (critical requirement)
# ---------------------------------------------------------------------------


class TestContactDetailsNoOverwrite:
    """Verify existing contact values are never overwritten."""

    def test_preserves_existing_email(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            contact_id = _setup_contact(db, email="existing@corp.com")
            resp = _make_mock_pplx_response(
                _make_contact_details_response(), cost=0.001
            )

            with _patch_perplexity(resp):
                enrich_contact_details(contact_id)

            row = db.session.execute(
                sa_text("SELECT email_address FROM contacts WHERE id = :cid"),
                {"cid": contact_id},
            ).fetchone()
            assert row[0] == "existing@corp.com"  # NOT overwritten

    def test_preserves_existing_phone(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            contact_id = _setup_contact(db, phone="+1555123456")
            resp = _make_mock_pplx_response(
                _make_contact_details_response(), cost=0.001
            )

            with _patch_perplexity(resp):
                enrich_contact_details(contact_id)

            row = db.session.execute(
                sa_text("SELECT phone_number FROM contacts WHERE id = :cid"),
                {"cid": contact_id},
            ).fetchone()
            assert row[0] == "+1555123456"  # NOT overwritten

    def test_preserves_existing_linkedin(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            contact_id = _setup_contact(db, linkedin="https://linkedin.com/in/existing")
            resp = _make_mock_pplx_response(
                _make_contact_details_response(), cost=0.001
            )

            with _patch_perplexity(resp):
                enrich_contact_details(contact_id)

            row = db.session.execute(
                sa_text("SELECT linkedin_url FROM contacts WHERE id = :cid"),
                {"cid": contact_id},
            ).fetchone()
            assert row[0] == "https://linkedin.com/in/existing"  # NOT overwritten

    def test_fills_only_missing_fields(self, app, db):
        """Contact with email but no phone — only phone gets filled."""
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            contact_id = _setup_contact(db, email="existing@corp.com")
            resp = _make_mock_pplx_response(
                _make_contact_details_response(), cost=0.001
            )

            with _patch_perplexity(resp):
                enrich_contact_details(contact_id)

            row = db.session.execute(
                sa_text(
                    "SELECT email_address, phone_number FROM contacts WHERE id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row[0] == "existing@corp.com"  # preserved
            assert row[1] == "+49301234567"  # filled


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestContactDetailsErrorHandling:
    """Test error scenarios."""

    def test_contact_not_found(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            _setup_contact(db)
            result = enrich_contact_details("ct000000-0000-0000-0000-nonexistent00")

            assert result.get("error") is not None
            assert result["enrichment_cost_usd"] == 0

    def test_perplexity_error_returns_failure(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details
        from requests.exceptions import HTTPError

        with app.app_context():
            contact_id = _setup_contact(db)
            pplx_cls = MagicMock()
            pplx_instance = pplx_cls.return_value
            pplx_instance.query.side_effect = HTTPError("503 Service Unavailable")

            with patch(
                "api.services.contact_details_enricher.PerplexityClient", pplx_cls
            ):
                result = enrich_contact_details(contact_id)

            assert result.get("error") is not None

    def test_null_response_preserves_existing(self, app, db):
        """Perplexity returns nulls — existing data must not be wiped."""
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            contact_id = _setup_contact(db, email="keep@me.com", phone="+1111")
            null_data = {
                "email_address": None,
                "phone_number": None,
                "linkedin_url": None,
                "profile_photo_url": None,
                "data_confidence": "low",
            }
            resp = _make_mock_pplx_response(null_data, cost=0.001)

            with _patch_perplexity(resp):
                result = enrich_contact_details(contact_id)

            assert "error" not in result

            row = db.session.execute(
                sa_text(
                    "SELECT email_address, phone_number FROM contacts WHERE id = :cid"
                ),
                {"cid": contact_id},
            ).fetchone()
            assert row[0] == "keep@me.com"  # preserved
            assert row[1] == "+1111"  # preserved


# ---------------------------------------------------------------------------
# Test: Boost mode
# ---------------------------------------------------------------------------


class TestContactDetailsBoostMode:
    """Test boost model selection."""

    def test_standard_model_by_default(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(
                _make_contact_details_response(), cost=0.001
            )

            with _patch_perplexity(resp) as pplx_p:
                enrich_contact_details(contact_id, boost=False)

            pplx_instance = pplx_p.return_value
            call_kwargs = pplx_instance.query.call_args[1]
            assert call_kwargs["model"] == "sonar"

    def test_boost_model_when_enabled(self, app, db):
        from api.services.contact_details_enricher import enrich_contact_details

        with app.app_context():
            contact_id = _setup_contact(db)
            resp = _make_mock_pplx_response(
                _make_contact_details_response(), cost=0.003
            )

            with _patch_perplexity(resp) as pplx_p:
                enrich_contact_details(contact_id, boost=True)

            pplx_instance = pplx_p.return_value
            call_kwargs = pplx_instance.query.call_args[1]
            assert call_kwargs["model"] == "sonar-pro"
