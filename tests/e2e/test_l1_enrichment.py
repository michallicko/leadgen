"""E2E tests for L1 enrichment pipeline.

Validates the full L1 enrichment flow:
  create entities → run L1 → verify outcomes per scenario.

Uses mocked Perplexity API to avoid cost/flakiness.
Run with: pytest tests/e2e/test_l1_enrichment.py -v
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from api.models import Company, Contact, db


# ---------------------------------------------------------------------------
# Mock Perplexity responses per scenario
# ---------------------------------------------------------------------------

def _research_response(company_name, **overrides):
    """Build a standard research JSON blob."""
    base = {
        "company_name": company_name,
        "summary": f"{company_name} is a well-established B2B technology company "
                   f"providing enterprise solutions across European markets.",
        "b2b": True,
        "hq": "Berlin, Germany",
        "markets": ["Germany", "Austria", "Switzerland"],
        "founded": "2010",
        "ownership": "Private",
        "industry": "Software",
        "business_model": "SaaS",
        "revenue_eur_m": 25.0,
        "revenue_year": "2025",
        "revenue_source": "Annual report",
        "employees": 200,
        "employees_source": "LinkedIn",
        "confidence": 0.85,
        "flags": [],
    }
    base.update(overrides)
    return base


def _mock_response(research_json, status_code=200):
    """Create a mock requests.Response for Perplexity API."""
    mock = MagicMock()
    mock.status_code = status_code
    if status_code == 200:
        mock.json.return_value = {
            "choices": [{"message": {"content": json.dumps(research_json)}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 300},
        }
    else:
        mock.json.return_value = {"error": "Server error"}
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def l1_test_batch(app, db, seed_tenant, seed_super_admin):
    """Create a dedicated batch with 10 test companies for L1 E2E."""
    app.config["PERPLEXITY_API_KEY"] = "test-key"

    from api.models import Batch, Owner, UserTenantRole

    # Ensure admin has role
    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=seed_tenant.id,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)

    owner = Owner(tenant_id=seed_tenant.id, name="TestOwner", is_active=True)
    db.session.add(owner)
    db.session.flush()

    batch = Batch(tenant_id=seed_tenant.id, name="l1-e2e-test", is_active=True)
    db.session.add(batch)
    db.session.flush()

    scenarios = [
        # (name, domain, country, description)
        ("SAP SE", "sap.com", "Germany", "full_data"),
        ("Spotify Technology", "spotify.com", None, "domain_only"),
        ("Skoda Auto", None, "Czech Republic", "no_domain"),
        ("John Smith Consulting", "gmail.com", "UK", "freemail"),
        ("Nonexistent Corp XYZ", "does-not-exist-12345.com", "US", "bad_domain"),
        ("Kiwi.com", None, None, "minimal"),
        ("Avast Software", "avast.com", "Czech Republic", "czech_registry"),
        ("Telenor ASA", "telenor.com", "Norway", "nordic"),
        ("Siemens AG", "siemens.com", "Germany", "large_enterprise"),
        ("SAP SE Duplicate", "sap.de", "Germany", "duplicate_name"),
    ]

    companies = []
    for name, domain, country, scenario_tag in scenarios:
        c = Company(
            tenant_id=seed_tenant.id,
            batch_id=batch.id,
            owner_id=owner.id,
            name=name,
            domain=domain,
            hq_country=country,
            status="new",
            notes=scenario_tag,  # tag for easy lookup in assertions
        )
        db.session.add(c)
        companies.append(c)
    db.session.flush()

    # Add contacts for domain-resolution test (freemail company)
    freemail_company = companies[3]  # John Smith Consulting (gmail.com)
    ct = Contact(
        tenant_id=seed_tenant.id,
        batch_id=batch.id,
        owner_id=owner.id,
        company_id=freemail_company.id,
        first_name="John",
        last_name="Smith",
        email_address="john@smithconsulting.co.uk",
        job_title="Founder",
    )
    db.session.add(ct)

    # Add contacts with LinkedIn for full_data company
    full_data_company = companies[0]  # SAP SE
    ct2 = Contact(
        tenant_id=seed_tenant.id,
        batch_id=batch.id,
        owner_id=owner.id,
        company_id=full_data_company.id,
        first_name="Maria",
        last_name="Schmidt",
        email_address="maria@sap.com",
        linkedin_url="https://www.linkedin.com/in/mariaschmidt",
        job_title="VP Engineering",
    )
    db.session.add(ct2)

    db.session.commit()
    return {
        "tenant": seed_tenant,
        "batch": batch,
        "owner": owner,
        "companies": companies,
    }


# ---------------------------------------------------------------------------
# Perplexity mock that returns scenario-specific responses
# ---------------------------------------------------------------------------

def _perplexity_side_effect(url, **kwargs):
    """Return different mock responses based on the company name in the prompt."""
    body = kwargs.get("json", {})
    messages = body.get("messages", [])
    user_msg = messages[-1]["content"] if messages else ""

    # Match scenario by company name in prompt
    if "Nonexistent Corp XYZ" in user_msg:
        return _mock_response(
            _research_response(
                "Nonexistent Corp XYZ",
                summary="No information found for this company.",
                confidence=0.1,
                flags=["Company not found in any public sources"],
                revenue_eur_m=None,
                employees=None,
                hq=None,
                industry=None,
            )
        )

    if "John Smith Consulting" in user_msg:
        return _mock_response(
            _research_response(
                "John Smith Consulting",
                hq="London, UK",
                revenue_eur_m=0.5,
                employees=5,
                industry="Consulting",
                business_model="Service provider",
                b2b=True,
                confidence=0.6,
            )
        )

    if "SAP SE" in user_msg:
        return _mock_response(
            _research_response(
                "SAP SE",
                hq="Walldorf, Germany",
                revenue_eur_m=30000,
                employees=107000,
                industry="Enterprise Software",
                business_model="SaaS",
                ownership="Public",
                confidence=0.95,
            )
        )

    if "Spotify" in user_msg:
        return _mock_response(
            _research_response(
                "Spotify Technology",
                hq="Stockholm, Sweden",
                revenue_eur_m=13000,
                employees=9000,
                industry="Technology / Media",
                business_model="Platform",
                ownership="Public",
                b2b=False,  # B2C
                confidence=0.9,
            )
        )

    if "Skoda" in user_msg:
        return _mock_response(
            _research_response(
                "Skoda Auto",
                hq="Mlada Boleslav, Czech Republic",
                revenue_eur_m=22000,
                employees=35000,
                industry="Automotive / Manufacturing",
                business_model="Manufacturer",
                ownership="Subsidiary of VW Group",
                confidence=0.9,
            )
        )

    if "Kiwi.com" in user_msg:
        return _mock_response(
            _research_response(
                "Kiwi.com",
                hq="Brno, Czech Republic",
                revenue_eur_m=500,
                employees=1000,
                industry="Travel Technology",
                business_model="Platform",
                confidence=0.75,
            )
        )

    if "Avast" in user_msg:
        return _mock_response(
            _research_response(
                "Avast Software",
                hq="Prague, Czech Republic",
                revenue_eur_m=900,
                employees=1800,
                industry="Cybersecurity",
                business_model="SaaS",
                confidence=0.85,
            )
        )

    if "Telenor" in user_msg:
        return _mock_response(
            _research_response(
                "Telenor ASA",
                hq="Oslo, Norway",
                revenue_eur_m=12000,
                employees=15000,
                industry="Telecommunications",
                business_model="Service provider",
                ownership="State-owned",
                confidence=0.9,
            )
        )

    if "Siemens" in user_msg:
        return _mock_response(
            _research_response(
                "Siemens AG",
                hq="Munich, Germany",
                revenue_eur_m=77000,
                employees=300000,
                industry="Industrial / Engineering",
                business_model="Manufacturer",
                ownership="Public",
                confidence=0.95,
            )
        )

    # Default fallback
    return _mock_response(
        _research_response("Unknown Company", confidence=0.5)
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestL1EnrichmentE2E:
    """End-to-end L1 enrichment tests with mocked Perplexity."""

    @patch("api.services.l1_enricher.requests.post", side_effect=_perplexity_side_effect)
    def test_full_batch_enrichment(self, mock_post, app, l1_test_batch):
        """Run L1 on all 10 companies and validate each scenario."""
        from api.services.l1_enricher import enrich_l1

        tenant_id = str(l1_test_batch["tenant"].id)
        companies = l1_test_batch["companies"]

        results = {}
        with app.app_context():
            for c in companies:
                result = enrich_l1(str(c.id), tenant_id=tenant_id)
                # Re-read company from DB
                updated = db.session.execute(
                    db.text("SELECT status, hq_country, hq_city, industry, "
                            "verified_revenue_eur_m, verified_employees, "
                            "enrichment_cost_usd, error_message, triage_score "
                            "FROM companies WHERE id = :id"),
                    {"id": str(c.id)},
                ).fetchone()
                results[c.notes] = {
                    "result": result,
                    "status": updated[0],
                    "hq_country": updated[1],
                    "hq_city": updated[2],
                    "industry": updated[3],
                    "revenue": updated[4],
                    "employees": updated[5],
                    "cost": updated[6],
                    "error": updated[7],
                    "score": updated[8],
                }

        # --- Scenario assertions ---

        # 1. Full data (SAP SE) — should enrich cleanly
        sap = results["full_data"]
        assert sap["status"] in ("triage_passed", "needs_review")
        assert sap["hq_country"] == "Germany"
        assert sap["hq_city"] == "Walldorf"
        assert sap["cost"] is not None and float(sap["cost"]) > 0

        # 2. Domain only (Spotify) — country should be resolved
        spotify = results["domain_only"]
        assert spotify["status"] in ("triage_passed", "needs_review")
        assert spotify["hq_country"] == "Sweden"

        # 3. No domain (Skoda) — should still enrich with name+country
        skoda = results["no_domain"]
        assert skoda["status"] in ("triage_passed", "needs_review")
        assert skoda["hq_city"] == "Mlada Boleslav"

        # 4. Freemail (John Smith Consulting) — domain should be resolved from contact
        freemail = results["freemail"]
        assert freemail["status"] in ("triage_passed", "needs_review")
        # Should have enriched (freemail domain gets replaced by contact email domain)
        assert freemail["cost"] is not None and float(freemail["cost"]) > 0

        # 5. Bad domain (Nonexistent) — should set needs_review with flags
        bad = results["bad_domain"]
        assert bad["status"] == "needs_review"
        # Should have QC flags due to low confidence and source warnings
        assert bad["result"]["qc_flags"], "Expected QC flags for non-existent company"

        # 6. Minimal (Kiwi.com) — should still enrich with just a name
        kiwi = results["minimal"]
        assert kiwi["status"] in ("triage_passed", "needs_review")
        assert kiwi["cost"] is not None and float(kiwi["cost"]) > 0

        # 7. Czech company (Avast) — enriched, eligible for registry follow-up
        avast = results["czech_registry"]
        assert avast["status"] in ("triage_passed", "needs_review")
        assert avast["hq_country"] in ("Czech Republic", "Czechia")

        # 8. Nordic (Telenor) — should map to nordics geo_region
        telenor = results["nordic"]
        assert telenor["status"] in ("triage_passed", "needs_review")
        assert telenor["hq_country"] == "Norway"

        # 9. Large enterprise (Siemens) — revenue may trigger sanity check
        siemens = results["large_enterprise"]
        assert siemens["status"] in ("triage_passed", "needs_review")
        assert siemens["hq_city"] == "Munich"

        # 10. Duplicate name — both should process independently
        dup = results["duplicate_name"]
        assert dup["status"] in ("triage_passed", "needs_review")
        assert dup["cost"] is not None and float(dup["cost"]) > 0

    @patch("api.services.l1_enricher.requests.post", side_effect=_perplexity_side_effect)
    def test_cost_tracking(self, mock_post, app, l1_test_batch):
        """Verify cost is calculated and stored for each entity."""
        from api.services.l1_enricher import enrich_l1

        tenant_id = str(l1_test_batch["tenant"].id)
        company = l1_test_batch["companies"][0]  # SAP SE

        with app.app_context():
            result = enrich_l1(str(company.id), tenant_id=tenant_id)

        assert result["enrichment_cost_usd"] > 0

    @patch("api.services.l1_enricher.requests.post")
    def test_api_error_handled_gracefully(self, mock_post, app, l1_test_batch):
        """Verify L1 handles Perplexity API errors without crashing."""
        mock_post.return_value = _mock_response({}, status_code=500)

        from api.services.l1_enricher import enrich_l1

        tenant_id = str(l1_test_batch["tenant"].id)
        company = l1_test_batch["companies"][0]

        with app.app_context():
            result = enrich_l1(str(company.id), tenant_id=tenant_id)

            updated = db.session.execute(
                db.text("SELECT status FROM companies WHERE id = :id"),
                {"id": str(company.id)},
            ).fetchone()

        assert updated[0] == "enrichment_failed"
        assert "api_error" in result["qc_flags"]

    @patch("api.services.l1_enricher.requests.post", side_effect=_perplexity_side_effect)
    def test_enrichment_completes_without_crash(self, mock_post, app, l1_test_batch):
        """Verify L1 enrichment runs to completion and returns valid result.

        Note: research_asset insertion uses raw SQL with gen_random_uuid() which
        only works on PostgreSQL. In SQLite tests, the insert silently fails
        (wrapped in try/except). This is tested on staging with real PG.
        """
        from api.services.l1_enricher import enrich_l1

        tenant_id = str(l1_test_batch["tenant"].id)
        company = l1_test_batch["companies"][0]  # SAP SE

        with app.app_context():
            result = enrich_l1(str(company.id), tenant_id=tenant_id)

            updated = db.session.execute(
                db.text("SELECT status, enrichment_cost_usd FROM companies WHERE id = :id"),
                {"id": str(company.id)},
            ).fetchone()

        assert result["enrichment_cost_usd"] > 0
        assert updated[0] in ("triage_passed", "needs_review")
        assert float(updated[1]) > 0

    @patch("api.services.l1_enricher.requests.post", side_effect=_perplexity_side_effect)
    def test_qc_flags_for_low_confidence(self, mock_post, app, l1_test_batch):
        """Company with low confidence should get QC flags and needs_review status."""
        from api.services.l1_enricher import enrich_l1

        tenant_id = str(l1_test_batch["tenant"].id)
        company = l1_test_batch["companies"][4]  # Nonexistent Corp XYZ

        with app.app_context():
            result = enrich_l1(str(company.id), tenant_id=tenant_id)

            updated = db.session.execute(
                db.text("SELECT status FROM companies WHERE id = :id"),
                {"id": str(company.id)},
            ).fetchone()

        assert updated[0] == "needs_review"
        assert len(result["qc_flags"]) > 0
        # Should flag low confidence (0.1 < 0.4 threshold)
        assert any("confidence" in f.lower() for f in result["qc_flags"])
