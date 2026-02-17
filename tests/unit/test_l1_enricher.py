"""Unit tests for L1 company profile enrichment via Perplexity."""

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper parser tests (no DB / no Flask app needed)
# ---------------------------------------------------------------------------

class TestParseRevenue:
    def setup_method(self):
        from api.services.l1_enricher import _parse_revenue
        self.parse = _parse_revenue

    def test_none(self):
        assert self.parse(None) is None

    def test_int(self):
        assert self.parse(42) == 42.0

    def test_float(self):
        assert self.parse(1.5) == 1.5

    def test_string_number(self):
        assert self.parse("42") == 42.0

    def test_string_with_m(self):
        assert self.parse("42M") == 42.0

    def test_string_with_million(self):
        assert self.parse("1.5 million") == 1.5

    def test_billion(self):
        assert self.parse("1.5 billion") == 1500.0

    def test_unverified(self):
        assert self.parse("unverified") is None

    def test_unknown(self):
        assert self.parse("unknown") is None

    def test_na(self):
        assert self.parse("n/a") is None

    def test_empty(self):
        assert self.parse("") is None

    def test_with_currency(self):
        assert self.parse("€42") == 42.0

    def test_with_eur(self):
        assert self.parse("EUR 42") == 42.0

    def test_comma_separated(self):
        assert self.parse("1,500") == 1500.0


class TestParseEmployees:
    def setup_method(self):
        from api.services.l1_enricher import _parse_employees
        self.parse = _parse_employees

    def test_none(self):
        assert self.parse(None) is None

    def test_int(self):
        assert self.parse(500) == 500

    def test_float(self):
        assert self.parse(500.0) == 500

    def test_string(self):
        assert self.parse("500") == 500

    def test_range(self):
        assert self.parse("200-300") == 250

    def test_range_with_comma(self):
        assert self.parse("1,000-2,000") == 1500

    def test_comma_separated(self):
        assert self.parse("1,234") == 1234

    def test_unverified(self):
        assert self.parse("unverified") is None

    def test_approx(self):
        assert self.parse("~500") == 500

    def test_about(self):
        assert self.parse("about 500") == 500

    def test_plus(self):
        assert self.parse("500+") == 500

    def test_empty(self):
        assert self.parse("") is None


class TestDeriveGeoRegion:
    def setup_method(self):
        from api.services.l1_enricher import _derive_geo_region
        self.derive = _derive_geo_region

    def test_germany(self):
        assert self.derive("Germany") == "dach"

    def test_austria(self):
        assert self.derive("Austria") == "dach"

    def test_switzerland(self):
        assert self.derive("Switzerland") == "dach"

    def test_sweden(self):
        assert self.derive("Sweden") == "nordics"

    def test_czech(self):
        assert self.derive("Czech Republic") == "cee"

    def test_uk(self):
        assert self.derive("United Kingdom") == "uk_ireland"

    def test_france(self):
        assert self.derive("France") == "southern_europe"

    def test_us(self):
        assert self.derive("United States") == "us"

    def test_unknown(self):
        assert self.derive("Mars") is None

    def test_none(self):
        assert self.derive(None) is None


class TestMapOwnership:
    def setup_method(self):
        from api.services.l1_enricher import _map_ownership
        self.map = _map_ownership

    def test_family_owned(self):
        assert self.map("Family-owned") == "family_owned"

    def test_pe_backed(self):
        assert self.map("PE-backed (EQT)") == "pe_backed"

    def test_private_equity(self):
        assert self.map("Private Equity backed") == "pe_backed"

    def test_public(self):
        assert self.map("Public") == "public"

    def test_private(self):
        assert self.map("Private") == "bootstrapped"

    def test_vc(self):
        assert self.map("VC-backed") == "vc_backed"

    def test_none(self):
        assert self.map(None) is None


class TestRevenueToBucket:
    def setup_method(self):
        from api.services.l1_enricher import _revenue_to_bucket
        self.bucket = _revenue_to_bucket

    def test_micro(self):
        assert self.bucket(0.5) == "micro"

    def test_small(self):
        assert self.bucket(5) == "small"

    def test_medium(self):
        assert self.bucket(25) == "medium"

    def test_mid_market(self):
        assert self.bucket(100) == "mid_market"

    def test_enterprise(self):
        assert self.bucket(500) == "enterprise"

    def test_none(self):
        assert self.bucket(None) is None


class TestEmployeesToBucket:
    def setup_method(self):
        from api.services.l1_enricher import _employees_to_bucket
        self.bucket = _employees_to_bucket

    def test_micro(self):
        assert self.bucket(5) == "micro"

    def test_startup(self):
        assert self.bucket(30) == "startup"

    def test_smb(self):
        assert self.bucket(100) == "smb"

    def test_mid_market(self):
        assert self.bucket(500) == "mid_market"

    def test_enterprise(self):
        assert self.bucket(5000) == "enterprise"

    def test_none(self):
        assert self.bucket(None) is None


class TestParseConfidence:
    def setup_method(self):
        from api.services.l1_enricher import _parse_confidence
        self.parse = _parse_confidence

    def test_float(self):
        assert self.parse(0.8) == 0.8

    def test_int(self):
        assert self.parse(1) == 1.0

    def test_string_low(self):
        assert self.parse("low") == 0.3

    def test_string_high(self):
        assert self.parse("high") == 0.9

    def test_string_number(self):
        assert self.parse("0.75") == 0.75

    def test_none(self):
        assert self.parse(None) is None

    def test_out_of_range(self):
        assert self.parse(1.5) is None


class TestNameSimilarity:
    def setup_method(self):
        from api.services.l1_enricher import _name_similarity
        self.sim = _name_similarity

    def test_exact(self):
        assert self.sim("Acme Corp", "Acme Corp") == 1.0

    def test_case_insensitive(self):
        assert self.sim("ACME CORP", "acme corp") == 1.0

    def test_suffix_stripping(self):
        assert self.sim("Acme GmbH", "Acme") == 1.0

    def test_different(self):
        assert self.sim("Acme", "Zeta") < 0.5

    def test_empty(self):
        assert self.sim("", "Acme") == 0.0

    def test_none(self):
        assert self.sim(None, "Acme") == 0.0

    def test_similar(self):
        # Should be reasonably high
        assert self.sim("Acme Corporation", "Acme Corp") > 0.6

    def test_a_slash_s_suffix(self):
        """Danish A/S suffix should be stripped."""
        assert self.sim("NNIT", "NNIT A/S") == 1.0

    def test_sp_z_oo_suffix(self):
        """Polish sp. z o.o. suffix should be stripped."""
        assert self.sim("Formika", "Formika Sp. z o.o.") == 1.0

    def test_bv_suffix(self):
        """Dutch B.V. suffix should be stripped."""
        assert self.sim("Philips", "Philips B.V.") == 1.0

    def test_spa_suffix(self):
        """Italian S.p.A. suffix should be stripped."""
        assert self.sim("Enel", "Enel S.p.A.") == 1.0


class TestParseResearchJson:
    def setup_method(self):
        from api.services.l1_enricher import _parse_research_json
        self.parse = _parse_research_json

    def test_plain_json(self):
        result = self.parse('{"company_name": "Acme"}')
        assert result == {"company_name": "Acme"}

    def test_markdown_fenced(self):
        result = self.parse('```json\n{"company_name": "Acme"}\n```')
        assert result == {"company_name": "Acme"}

    def test_invalid_json(self):
        result = self.parse("not json at all")
        assert result is None

    def test_empty(self):
        result = self.parse("")
        assert result is None

    def test_none(self):
        result = self.parse(None)
        assert result is None

    def test_embedded_json(self):
        result = self.parse('Here is the result: {"company_name": "Acme"}')
        assert result == {"company_name": "Acme"}


class TestMapFields:
    def setup_method(self):
        from api.services.l1_enricher import _map_fields
        self.map = _map_fields

    def test_full_mapping(self):
        research = {
            "summary": "A software company",
            "hq": "Berlin, Germany",
            "ownership": "Private",
            "industry": "Software",
            "business_model": "SaaS",
            "revenue_eur_m": 42,
            "employees": 500,
            "b2b": True,
        }
        mapped = self.map(research)
        assert mapped["summary"] == "A software company"
        assert mapped["hq_city"] == "Berlin"
        assert mapped["hq_country"] == "Germany"
        assert mapped["geo_region"] == "dach"
        assert mapped["ownership_type"] == "bootstrapped"
        assert mapped["industry"] == "software_saas"
        assert mapped["business_type"] == "saas"
        assert mapped["verified_revenue_eur_m"] == 42.0
        assert mapped["revenue_range"] == "medium"
        assert mapped["verified_employees"] == 500
        assert mapped["company_size"] == "mid_market"
        assert mapped["business_model"] == "b2b"

    def test_minimal_mapping(self):
        research = {"summary": "Short desc"}
        mapped = self.map(research)
        assert mapped["summary"] == "Short desc"
        assert "hq_city" not in mapped
        assert "verified_revenue_eur_m" not in mapped

    def test_unverified_revenue_skipped(self):
        research = {"revenue_eur_m": "unverified"}
        mapped = self.map(research)
        assert "verified_revenue_eur_m" not in mapped

    def test_enum_mapping_applied_geo_region(self):
        """Verify _map_fields routes geo_region through the enum mapper."""
        research = {"hq": "London, United Kingdom"}
        mapped = self.map(research)
        assert mapped["geo_region"] == "uk_ireland"

    def test_enum_mapping_applied_ownership(self):
        """Verify _map_fields routes ownership through the enum mapper."""
        research = {"ownership": "Privately held"}
        mapped = self.map(research)
        assert mapped["ownership_type"] == "bootstrapped"

    def test_enum_mapping_us_from_map_fields(self):
        """USA country → us geo_region (not north_america)."""
        research = {"hq": "New York, United States"}
        mapped = self.map(research)
        assert mapped["geo_region"] == "us"

    def test_enum_mapping_france_from_map_fields(self):
        """France country → southern_europe geo_region (not 'france')."""
        research = {"hq": "Paris, France"}
        mapped = self.map(research)
        assert mapped["geo_region"] == "southern_europe"

    def test_enum_mapping_arts_industry(self):
        """Arts & entertainment → creative_services via enum mapper."""
        research = {"industry": "arts & entertainment"}
        mapped = self.map(research)
        assert mapped["industry"] == "creative_services"

    def test_enum_mapping_events_industry(self):
        """Events → creative_services via enum mapper."""
        research = {"industry": "events"}
        mapped = self.map(research)
        assert mapped["industry"] == "creative_services"


# ---------------------------------------------------------------------------
# QC validation tests
# ---------------------------------------------------------------------------

class TestValidateResearch:
    def setup_method(self):
        from api.services.l1_enricher import _validate_research
        self.validate = _validate_research

    def _good_research(self, **overrides):
        base = {
            "company_name": "Acme Corp",
            "summary": "A leading software company based in Germany with 500 employees.",
            "b2b": True,
            "hq": "Berlin, Germany",
            "industry": "Software",
            "employees": 500,
            "revenue_eur_m": 42,
            "confidence": 0.8,
        }
        base.update(overrides)
        return base

    def test_clean_research_no_flags(self):
        flags = self.validate(self._good_research(), "Acme Corp")
        assert flags == []

    def test_name_mismatch(self):
        flags = self.validate(self._good_research(company_name="Completely Different Inc"), "Acme Corp")
        assert "name_mismatch" in flags

    def test_incomplete_research(self):
        flags = self.validate({"company_name": "Acme"}, "Acme")
        assert "incomplete_research" in flags

    def test_revenue_implausible_too_high(self):
        flags = self.validate(self._good_research(revenue_eur_m=60000), "Acme Corp")
        assert "revenue_implausible" in flags

    def test_revenue_implausible_ratio(self):
        # Revenue per employee > 500K EUR
        flags = self.validate(self._good_research(revenue_eur_m=500, employees=10), "Acme Corp")
        assert "revenue_implausible" in flags

    def test_employees_implausible(self):
        flags = self.validate(self._good_research(employees=600000), "Acme Corp")
        assert "employees_implausible" in flags

    def test_low_confidence(self):
        flags = self.validate(self._good_research(confidence=0.2), "Acme Corp")
        assert "low_confidence" in flags

    def test_b2b_unclear(self):
        flags = self.validate(self._good_research(b2b=None), "Acme Corp")
        assert "b2b_unclear" in flags

    def test_summary_too_short(self):
        flags = self.validate(self._good_research(summary="Short"), "Acme Corp")
        assert "summary_too_short" in flags

    def test_incomplete_at_3_of_5(self):
        """3 of 5 critical fields should now be flagged (threshold raised to 4)."""
        research = self._good_research(employees="unverified", revenue_eur_m="unverified")
        flags = self.validate(research, "Acme Corp")
        assert "incomplete_research" in flags

    def test_complete_at_4_of_5(self):
        """4 of 5 critical fields should pass."""
        research = self._good_research(revenue_eur_m="unverified")
        flags = self.validate(research, "Acme Corp")
        assert "incomplete_research" not in flags

    def test_source_warning_from_perplexity_flags(self):
        """Perplexity flags containing 'not found' trigger source_warning."""
        research = self._good_research(flags=["Company not found in search results"])
        flags = self.validate(research, "Acme Corp")
        assert "source_warning" in flags

    def test_source_warning_discrepancy(self):
        """Perplexity flags containing 'discrepancy' trigger source_warning."""
        research = self._good_research(flags=["HQ location discrepancy between sources"])
        flags = self.validate(research, "Acme Corp")
        assert "source_warning" in flags

    def test_no_source_warning_for_benign_flags(self):
        """Perplexity flags without warning keywords should not trigger."""
        research = self._good_research(flags=["Revenue converted from USD"])
        flags = self.validate(research, "Acme Corp")
        assert "source_warning" not in flags

    def test_no_source_warning_without_flags(self):
        """No Perplexity flags → no source_warning."""
        research = self._good_research(flags=[])
        flags = self.validate(research, "Acme Corp")
        assert "source_warning" not in flags


class TestLoadPreviousEnrichment:
    """Test auto-loading previous enrichment data for re-enrichment."""

    def test_load_from_enrichment_table(self, app, db, seed_companies_contacts):
        """When company has prior L1 enrichment, load it as previous_data."""
        from api.services.l1_enricher import _load_previous_enrichment
        data = seed_companies_contacts
        company = data["companies"][0]

        with app.app_context():
            # Insert a prior enrichment record
            from sqlalchemy import text as sa_text
            db.session.execute(sa_text("""
                INSERT INTO company_enrichment_l1 (
                    company_id, raw_response, qc_flags, confidence, quality_score,
                    enrichment_cost_usd
                ) VALUES (
                    :cid, :raw, :flags, :conf, :qs, :cost
                )
            """), {
                "cid": str(company.id),
                "raw": '{"summary": "Old summary", "industry": "Software"}',
                "flags": '["name_mismatch"]',
                "conf": 0.7,
                "qs": 85,
                "cost": 0.001,
            })
            db.session.commit()

            prev = _load_previous_enrichment(str(company.id))
            assert prev is not None
            assert prev["summary"] == "Old summary"
            assert prev["industry"] == "Software"
            assert "name_mismatch" in prev.get("previous_qc_flags", "")

    def test_no_prior_enrichment_returns_none(self, app, db, seed_companies_contacts):
        """When company has no prior enrichment, return None."""
        from api.services.l1_enricher import _load_previous_enrichment
        data = seed_companies_contacts
        company = data["companies"][0]

        with app.app_context():
            prev = _load_previous_enrichment(str(company.id))
            assert prev is None


class TestQCThresholdsConfigurable:
    """Test that QC thresholds can be overridden via config dict."""

    def setup_method(self):
        from api.services.l1_enricher import _validate_research, QC_DEFAULTS
        self.validate = _validate_research
        self.defaults = QC_DEFAULTS

    def _good_research(self, **overrides):
        base = {
            "company_name": "Acme Corp",
            "summary": "A leading software company based in Germany with 500 employees.",
            "b2b": True,
            "hq": "Berlin, Germany",
            "industry": "Software",
            "employees": 500,
            "revenue_eur_m": 42,
            "confidence": 0.8,
        }
        base.update(overrides)
        return base

    def test_defaults_exist(self):
        """QC_DEFAULTS dict should be importable with all threshold keys."""
        assert "name_similarity_min" in self.defaults
        assert "min_critical_fields" in self.defaults
        assert "confidence_min" in self.defaults
        assert "summary_min_length" in self.defaults

    def test_name_similarity_custom_threshold(self):
        """Lower name_similarity_min should pass previously-flagged names."""
        # "Acme Corp" vs "Acme Corporation" fails at 0.6 but passes at 0.3
        research = self._good_research(company_name="Acme Corporation Ltd")
        # Default should NOT flag (similar enough)
        flags = self.validate(research, "Acme Corp")
        assert "name_mismatch" not in flags

        # Very different name should still flag
        research2 = self._good_research(company_name="Completely Different Inc")
        flags2 = self.validate(research2, "Acme Corp", qc_config={"name_similarity_min": 0.3})
        assert "name_mismatch" in flags2

    def test_lenient_name_threshold_passes_close_names(self):
        """With a very low threshold, close-ish names should pass."""
        research = self._good_research(company_name="Completely Different Inc")
        # With default 0.6 it fails
        flags_default = self.validate(research, "Acme Corp")
        assert "name_mismatch" in flags_default
        # With 0.0 threshold everything passes
        flags_lenient = self.validate(research, "Acme Corp", qc_config={"name_similarity_min": 0.0})
        assert "name_mismatch" not in flags_lenient

    def test_critical_fields_threshold_configurable(self):
        """Lower min_critical_fields should pass research with fewer fields."""
        # Only 3 of 5 fields → fails at threshold 4
        research = self._good_research(employees="unverified", revenue_eur_m="unverified")
        flags_strict = self.validate(research, "Acme Corp")
        assert "incomplete_research" in flags_strict
        # Passes at threshold 3
        flags_lenient = self.validate(research, "Acme Corp", qc_config={"min_critical_fields": 3})
        assert "incomplete_research" not in flags_lenient

    def test_confidence_threshold_configurable(self):
        """Custom confidence_min should change when low_confidence fires."""
        research = self._good_research(confidence=0.35)
        # Default 0.4 → flags it
        flags_default = self.validate(research, "Acme Corp")
        assert "low_confidence" in flags_default
        # Threshold 0.3 → passes
        flags_lenient = self.validate(research, "Acme Corp", qc_config={"confidence_min": 0.3})
        assert "low_confidence" not in flags_lenient

    def test_summary_length_configurable(self):
        """Custom summary_min_length should change when summary_too_short fires."""
        research = self._good_research(summary="A decent company summary")
        # Default 30 → flags (24 chars)
        flags_default = self.validate(research, "Acme Corp")
        assert "summary_too_short" in flags_default
        # Threshold 20 → passes
        flags_lenient = self.validate(research, "Acme Corp", qc_config={"summary_min_length": 20})
        assert "summary_too_short" not in flags_lenient


# ---------------------------------------------------------------------------
# Integration tests (with DB, mocked Perplexity)
# ---------------------------------------------------------------------------

MOCK_PERPLEXITY_RESPONSE = {
    "company_name": "Acme Corp",
    "summary": "Acme Corp is a leading B2B software company based in Berlin, Germany, specializing in enterprise automation.",
    "b2b": True,
    "hq": "Berlin, Germany",
    "markets": ["Germany", "Austria", "Switzerland"],
    "founded": "2015",
    "ownership": "Private",
    "industry": "Software",
    "business_model": "SaaS",
    "revenue_eur_m": 8.5,
    "revenue_year": "2025",
    "revenue_source": "Company website",
    "employees": 120,
    "employees_source": "LinkedIn",
    "confidence": 0.85,
    "flags": [],
}


def _make_mock_pplx_response(content_dict, input_tokens=350, output_tokens=200, cost=0.00055):
    """Create a mock PerplexityResponse object."""
    resp = MagicMock()
    resp.content = json.dumps(content_dict)
    resp.model = "sonar"
    resp.input_tokens = input_tokens
    resp.output_tokens = output_tokens
    resp.cost_usd = cost
    return resp


def _patch_perplexity_client(response):
    """Return a patch context manager that mocks PerplexityClient.

    The mock's .query() returns the given response object.
    """
    mock_client_cls = MagicMock()
    instance = mock_client_cls.return_value
    instance.query.return_value = response
    return patch("api.services.l1_enricher.PerplexityClient", mock_client_cls)


def _mock_perplexity_success_response():
    """Create a successful mock PerplexityResponse."""
    return _make_mock_pplx_response(MOCK_PERPLEXITY_RESPONSE)


def _mock_perplexity_error_client():
    """Return a patch that makes PerplexityClient.query() raise an error."""
    import requests as req
    mock_client_cls = MagicMock()
    instance = mock_client_cls.return_value
    instance.query.side_effect = req.HTTPError("Server error")
    return patch("api.services.l1_enricher.PerplexityClient", mock_client_cls)


def _mock_perplexity_bad_json_response():
    """Create a mock PerplexityResponse with unparseable content."""
    resp = MagicMock()
    resp.content = "I couldn't find any information about this company."
    resp.model = "sonar"
    resp.input_tokens = 100
    resp.output_tokens = 20
    resp.cost_usd = 0.00012
    return resp


class TestEnrichL1Integration:
    """Full enrichment flow tests with mocked Perplexity API."""

    def test_successful_enrichment(self, app, db, seed_companies_contacts):
        """L1 enriches a 'new' company successfully → triage_passed."""
        data = seed_companies_contacts
        company = data["companies"][0]  # Acme Corp, status='new'

        with app.app_context():
            # Set Perplexity API key in config
            app.config["PERPLEXITY_API_KEY"] = "test-key"

            with _patch_perplexity_client(_mock_perplexity_success_response()):
                from api.services.l1_enricher import enrich_l1
                result = enrich_l1(str(company.id), str(data["tenant"].id))

            assert result["enrichment_cost_usd"] > 0
            assert result["qc_flags"] == []

            # Verify company was updated
            from sqlalchemy import text as sa_text
            row = db.session.execute(
                sa_text("SELECT status, summary, hq_city, hq_country, geo_region FROM companies WHERE id = :id"),
                {"id": str(company.id)},
            ).fetchone()
            assert row[0] == "triage_passed"
            assert "Acme Corp" in row[1]
            assert row[2] == "Berlin"
            assert row[3] == "Germany"
            assert row[4] == "dach"

    def test_api_error_sets_enrichment_failed(self, app, db, seed_companies_contacts):
        """Perplexity API error → status='enrichment_failed'."""
        data = seed_companies_contacts
        company = data["companies"][0]

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"

            with _mock_perplexity_error_client():
                from api.services.l1_enricher import enrich_l1
                result = enrich_l1(str(company.id), str(data["tenant"].id))

            assert "api_error" in result["qc_flags"]

            from sqlalchemy import text as sa_text
            row = db.session.execute(
                sa_text("SELECT status FROM companies WHERE id = :id"),
                {"id": str(company.id)},
            ).fetchone()
            assert row[0] == "enrichment_failed"

    def test_parse_error_sets_enrichment_failed(self, app, db, seed_companies_contacts):
        """Unparseable Perplexity response → status='enrichment_failed'."""
        data = seed_companies_contacts
        company = data["companies"][0]

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"

            with _patch_perplexity_client(_mock_perplexity_bad_json_response()):
                from api.services.l1_enricher import enrich_l1
                result = enrich_l1(str(company.id), str(data["tenant"].id))

            assert "parse_error" in result["qc_flags"]

            from sqlalchemy import text as sa_text
            row = db.session.execute(
                sa_text("SELECT status FROM companies WHERE id = :id"),
                {"id": str(company.id)},
            ).fetchone()
            assert row[0] == "enrichment_failed"

    def test_qc_flags_set_needs_review(self, app, db, seed_companies_contacts):
        """Research with QC issues → status='needs_review'."""
        data = seed_companies_contacts
        company = data["companies"][0]

        # Build a response with QC issues: low confidence + b2b unclear
        bad_research = dict(MOCK_PERPLEXITY_RESPONSE)
        bad_research["confidence"] = 0.2
        bad_research["b2b"] = None

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"

            with _patch_perplexity_client(_make_mock_pplx_response(bad_research)):
                from api.services.l1_enricher import enrich_l1
                result = enrich_l1(str(company.id), str(data["tenant"].id))

            assert "low_confidence" in result["qc_flags"]
            assert "b2b_unclear" in result["qc_flags"]

            from sqlalchemy import text as sa_text
            row = db.session.execute(
                sa_text("SELECT status, error_message FROM companies WHERE id = :id"),
                {"id": str(company.id)},
            ).fetchone()
            assert row[0] == "needs_review"
            # error_message contains JSON flag list
            flags = json.loads(row[1])
            assert "low_confidence" in flags

    def test_missing_api_key(self, app, db, seed_companies_contacts):
        """No API key configured → enrichment_failed."""
        data = seed_companies_contacts
        company = data["companies"][0]

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = ""

            from api.services.l1_enricher import enrich_l1
            result = enrich_l1(str(company.id), str(data["tenant"].id))

            assert "api_error" in result["qc_flags"]

    def test_company_not_found(self, app, db, seed_tenant):
        """Non-existent company ID → returns error flag."""
        with app.app_context():
            from api.services.l1_enricher import enrich_l1
            result = enrich_l1("00000000-0000-0000-0000-000000000000", str(seed_tenant.id))
            assert "company_not_found" in result["qc_flags"]

    def test_domain_resolution_from_contacts(self, app, db, seed_companies_contacts):
        """Company without domain resolves it from contact emails."""
        data = seed_companies_contacts
        company = data["companies"][0]  # Acme Corp, has contacts with @acme.com

        with app.app_context():
            # Clear the company domain
            from sqlalchemy import text as sa_text
            db.session.execute(
                sa_text("UPDATE companies SET domain = NULL WHERE id = :id"),
                {"id": str(company.id)},
            )
            db.session.commit()

            app.config["PERPLEXITY_API_KEY"] = "test-key"

            with _patch_perplexity_client(_mock_perplexity_success_response()):
                from api.services.l1_enricher import enrich_l1
                enrich_l1(str(company.id), str(data["tenant"].id))

            # Domain should be resolved from contacts
            row = db.session.execute(
                sa_text("SELECT domain FROM companies WHERE id = :id"),
                {"id": str(company.id)},
            ).fetchone()
            assert row[0] == "acme.com"

    def test_linkedin_urls_passed_to_perplexity(self, app, db, seed_companies_contacts):
        """Contact LinkedIn URLs are included in the Perplexity prompt."""
        data = seed_companies_contacts
        company = data["companies"][0]  # Acme Corp, contacts have LinkedIn URLs

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"

            with patch("api.services.l1_enricher.PerplexityClient") as MockClient:
                instance = MockClient.return_value
                instance.query.return_value = _mock_perplexity_success_response()

                from api.services.l1_enricher import enrich_l1
                enrich_l1(str(company.id), str(data["tenant"].id))

                # Check that the user_prompt passed to client.query contains LinkedIn URLs
                query_call = instance.query.call_args
                user_prompt = query_call[1]["user_prompt"]
                assert "linkedin.com/in/" in user_prompt
                assert "Known employees" in user_prompt


class TestPerplexityClientIntegration:
    """Test that L1 enricher uses the shared PerplexityClient."""

    def test_standard_model_used_by_default(self, app, db, seed_companies_contacts):
        """Without boost, L1 uses the standard Perplexity model from BOOST_MODELS."""
        from api.services.stage_registry import BOOST_MODELS

        data = seed_companies_contacts
        company = data["companies"][0]

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"

            mock_response = MagicMock()
            mock_response.content = json.dumps(MOCK_PERPLEXITY_RESPONSE)
            mock_response.model = BOOST_MODELS["l1"]["standard"]
            mock_response.input_tokens = 350
            mock_response.output_tokens = 200
            mock_response.cost_usd = 0.00055

            with patch("api.services.l1_enricher.PerplexityClient") as MockClient:
                instance = MockClient.return_value
                instance.query.return_value = mock_response

                from api.services.l1_enricher import enrich_l1
                result = enrich_l1(str(company.id), str(data["tenant"].id))

                # Verify the client was instantiated with the API key
                MockClient.assert_called_once()
                call_kwargs = MockClient.call_args
                assert call_kwargs[1]["api_key"] == "test-key" or call_kwargs[0][0] == "test-key"

                # Verify query was called with the standard model
                query_call = instance.query.call_args
                assert query_call[1]["model"] == BOOST_MODELS["l1"]["standard"]

            assert result["qc_flags"] == []
            assert result["enrichment_cost_usd"] > 0

    def test_boost_model_used_when_boost_true(self, app, db, seed_companies_contacts):
        """With boost=True, L1 uses the boost Perplexity model."""
        from api.services.stage_registry import BOOST_MODELS

        data = seed_companies_contacts
        company = data["companies"][0]

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"

            mock_response = MagicMock()
            mock_response.content = json.dumps(MOCK_PERPLEXITY_RESPONSE)
            mock_response.model = BOOST_MODELS["l1"]["boost"]
            mock_response.input_tokens = 350
            mock_response.output_tokens = 200
            mock_response.cost_usd = 0.0063

            with patch("api.services.l1_enricher.PerplexityClient") as MockClient:
                instance = MockClient.return_value
                instance.query.return_value = mock_response

                from api.services.l1_enricher import enrich_l1
                result = enrich_l1(str(company.id), str(data["tenant"].id),
                                   boost=True)

                # Verify boost model was requested
                query_call = instance.query.call_args
                assert query_call[1]["model"] == BOOST_MODELS["l1"]["boost"]

            assert result["enrichment_cost_usd"] > 0

    def test_cost_from_client_used(self, app, db, seed_companies_contacts):
        """Cost should come from the PerplexityClient response."""
        data = seed_companies_contacts
        company = data["companies"][0]

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"

            mock_response = MagicMock()
            mock_response.content = json.dumps(MOCK_PERPLEXITY_RESPONSE)
            mock_response.model = "sonar"
            mock_response.input_tokens = 500
            mock_response.output_tokens = 300
            mock_response.cost_usd = 0.123  # Distinctive value

            with patch("api.services.l1_enricher.PerplexityClient") as MockClient:
                instance = MockClient.return_value
                instance.query.return_value = mock_response

                from api.services.l1_enricher import enrich_l1
                result = enrich_l1(str(company.id), str(data["tenant"].id))

            # Cost should match the client's cost_usd
            assert result["enrichment_cost_usd"] == 0.123
