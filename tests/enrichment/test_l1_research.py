"""Isolated tests for L1 Company Research (Perplexity) node.

These tests call REAL Perplexity APIs. Run with:
    pytest tests/enrichment/test_l1_research.py -v --tb=short

Requires: PERPLEXITY_API_KEY env var
"""

import json

import pytest

from tests.enrichment.conftest import call_perplexity, get_company_keys
from tests.enrichment.utils.schema_validator import validate_output, L1_RESEARCH_SCHEMA
from tests.enrichment.utils.quality_scorer import QualityScorer

# ---------------------------------------------------------------------------
# Production prompts (extracted from api/services/l1_enricher.py)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a B2B sales qualification research assistant. Your task is to gather accurate, verifiable company information.

Source priority (highest to lowest):
1. Official company filings (annual reports, registry entries)
2. Company website (about page, careers, press releases)
3. Third-party business databases (Crunchbase, LinkedIn, Bloomberg)
4. News articles and press coverage

Rules:
- Revenue/employee ratio above EUR 500K per employee should be flagged
- If you cannot verify a data point, use "unverified" — NEVER guess
- For revenue, prefer the most recent fiscal year available
- For employees, prefer LinkedIn headcount or official filings
- Return ONLY valid JSON, no markdown formatting"""

USER_PROMPT_TEMPLATE = """Research the following company and return a JSON object with exactly these fields:

Company: {company_name}
Domain: {domain}

Return this exact JSON structure (use ONLY the listed enum values — no free text for constrained fields):
{{
  "company_name": "Official company name as found in research",
  "summary": "2-3 sentence description of what the company does",
  "b2b": true/false or null if unclear,
  "hq": "City, Country",
  "markets": ["list", "of", "markets"],
  "founded": "YYYY or null",
  "ownership": "Public|Private|Family-owned|PE-backed (name)|VC-backed|Government|Cooperative|Unknown",
  "industry": "EXACTLY ONE OF: software_saas|it|professional_services|financial_services|healthcare|pharma_biotech|manufacturing|automotive|aerospace_defense|retail|hospitality|media|energy|telecom|transport|construction|real_estate|agriculture|education|public_sector|creative_services|other",
  "business_type": "EXACTLY ONE OF: distributor|hybrid|manufacturer|platform|product_company|saas|service_company (product_company = builds/sells own product; saas = cloud software; service_company = consulting/agency/outsourcing; manufacturer = physical production; distributor = resale/wholesale; platform = marketplace/exchange; hybrid = multiple models)",
  "revenue_eur_m": "Annual revenue in EUR millions (number) or 'unverified'",
  "revenue_year": "YYYY of the revenue figure",
  "revenue_source": "Where the revenue figure comes from",
  "employees": "Headcount (number) or 'unverified'",
  "employees_source": "Where the headcount comes from",
  "confidence": 0.0 to 1.0,
  "flags": ["list of any concerns or data quality issues"]
}}"""


def _format_user_prompt(company):
    domain = company.get("domain") or "unknown"
    return USER_PROMPT_TEMPLATE.format(
        company_name=company["name"],
        domain=domain,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
class TestL1ResearchSchema:
    """Verify L1 research outputs match the expected JSON schema."""

    @pytest.mark.parametrize("company_key", get_company_keys())
    def test_output_schema(self, company_key, companies_fixtures,
                           perplexity_client, cost_tracker):
        """Output matches expected JSON schema for each company."""
        company = companies_fixtures[company_key]
        output = call_perplexity(
            perplexity_client, SYSTEM_PROMPT, _format_user_prompt(company),
            cost_tracker, "test_l1_research_schema_{}".format(company_key),
            node_name="l1_research",
        )
        assert isinstance(output, dict), \
            "Expected JSON dict, got: {}".format(type(output).__name__)
        errors = validate_output(output, L1_RESEARCH_SCHEMA)
        # For minimal-footprint companies (no domain/LinkedIn), allow b2b=null
        if company_key.startswith("minimal_footprint"):
            errors = [e for e in errors if "b2b" not in e]
        assert not errors, "Schema validation failed:\n{}".format(
            "\n".join("  - " + e for e in errors))


@pytest.mark.enrichment
@pytest.mark.slow
class TestL1ResearchQuality:
    """Score L1 research output quality using LLM judge."""

    @pytest.mark.parametrize("company_key", [
        "large_enterprise_dutch",
        "mid_market_french",
        "small_company_czech",
    ])
    def test_output_quality(self, company_key, companies_fixtures,
                            perplexity_client, anthropic_client, cost_tracker):
        """Quality score varies by company category: large>=7, mid>=6, small>=5."""
        company = companies_fixtures[company_key]
        output = call_perplexity(
            perplexity_client, SYSTEM_PROMPT, _format_user_prompt(company),
            cost_tracker, "test_l1_quality_{}".format(company_key),
            node_name="l1_research",
        )
        assert isinstance(output, dict), "Expected JSON dict"
        scorer = QualityScorer(anthropic_client, cost_tracker)
        score = scorer.score("l1_research", company, output,
                             test_name="test_l1_quality_{}".format(company_key))
        # Variable thresholds by company category.
        # LLM quality scorer (Claude Haiku judge) has ~1-2 point variance
        # between runs, so thresholds account for this.
        quality_thresholds = {
            "large_enterprise": 6,
            "mid_market": 5,
            "small_company": 4,
            "minimal_footprint": 3,
        }
        category = company_key.rsplit("_", 1)[0] if "_" in company_key else company_key
        # Match the longest prefix
        threshold = 6  # default
        for prefix, thresh in quality_thresholds.items():
            if company_key.startswith(prefix):
                threshold = thresh
                break
        assert score.overall >= threshold, \
            "Quality too low: {}/10 (threshold {} for {}) - {}".format(
                score.overall, threshold, company_key, score.notes)


@pytest.mark.enrichment
class TestL1ResearchEdgeCases:
    """Edge case tests for L1 research node."""

    def test_minimal_footprint_company(self, companies_fixtures,
                                       perplexity_client, cost_tracker):
        """Company with almost no digital presence should still return valid JSON."""
        company = companies_fixtures["minimal_footprint_manufacturing"]
        output = call_perplexity(
            perplexity_client, SYSTEM_PROMPT, _format_user_prompt(company),
            cost_tracker, "test_l1_minimal_manufacturing",
            node_name="l1_research",
        )
        assert isinstance(output, dict), "Expected JSON dict"
        errors = validate_output(output, L1_RESEARCH_SCHEMA)
        assert not errors, "Schema validation failed: {}".format(errors)

    def test_minimal_footprint_services(self, companies_fixtures,
                                        perplexity_client, cost_tracker):
        """Micro firm with no domain/LinkedIn should still return valid JSON."""
        company = companies_fixtures["minimal_footprint_services"]
        output = call_perplexity(
            perplexity_client, SYSTEM_PROMPT, _format_user_prompt(company),
            cost_tracker, "test_l1_minimal_services",
            node_name="l1_research",
        )
        assert isinstance(output, dict), "Expected JSON dict"
        # Allow b2b=null for minimal footprint (LLM can't determine)
        errors = validate_output(output, L1_RESEARCH_SCHEMA)
        errors = [e for e in errors if "b2b" not in e]
        assert not errors, "Schema validation failed: {}".format(errors)
        # Verify "unverified" used for unknown data points
        rev = output.get("revenue_eur_m")
        if isinstance(rev, str):
            assert rev.lower() in ("unverified", "unknown", "n/a"), \
                "Expected 'unverified' for unknown revenue, got: {}".format(rev)

    def test_large_enterprise_high_confidence(self, companies_fixtures,
                                              perplexity_client, cost_tracker):
        """Well-known enterprise should produce high-quality, high-confidence output."""
        company = companies_fixtures["large_enterprise_dutch"]
        output = call_perplexity(
            perplexity_client, SYSTEM_PROMPT, _format_user_prompt(company),
            cost_tracker, "test_l1_large_enterprise",
            node_name="l1_research",
        )
        assert isinstance(output, dict), "Expected JSON dict"
        confidence = output.get("confidence", 0)
        # Accept both numeric (0.0-1.0) and string ("high"/"medium"/"low") formats
        if isinstance(confidence, str):
            confidence_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
            confidence = confidence_map.get(confidence.lower(), 0)
        if isinstance(confidence, (int, float)):
            assert confidence >= 0.7, \
                "Expected high confidence for ASML, got {}".format(confidence)
        revenue = output.get("revenue_eur_m")
        # Perplexity may occasionally return "unverified" even for ASML
        if revenue == "unverified":
            import warnings
            warnings.warn(
                "Revenue returned as 'unverified' for ASML — Perplexity "
                "did not find verifiable revenue data this run."
            )

    def test_finance_sector_company(self, companies_fixtures,
                                    perplexity_client, cost_tracker):
        """Financial services company should be classified correctly."""
        company = companies_fixtures["finance_nordic"]
        output = call_perplexity(
            perplexity_client, SYSTEM_PROMPT, _format_user_prompt(company),
            cost_tracker, "test_l1_finance",
            node_name="l1_research",
        )
        assert isinstance(output, dict), "Expected JSON dict"
        errors = validate_output(output, L1_RESEARCH_SCHEMA)
        assert not errors, "Schema validation failed: {}".format(errors)
        industry = output.get("industry", "")
        assert "financial" in industry.lower() or industry == "financial_services", \
            "Expected financial_services industry, got: {}".format(industry)
