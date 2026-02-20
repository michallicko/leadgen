"""Isolated tests for L2 AI Synthesis (Anthropic Claude) node.

These tests call REAL Anthropic APIs. Run with:
    pytest tests/enrichment/test_l2_synthesis.py -v --tb=short

Requires: ANTHROPIC_API_KEY env var (and PERPLEXITY_API_KEY for full pipeline tests)
"""

import pytest

from tests.enrichment.conftest import call_anthropic
from tests.enrichment.utils.schema_validator import validate_output, L2_SYNTHESIS_SCHEMA
from tests.enrichment.utils.quality_scorer import QualityScorer

# ---------------------------------------------------------------------------
# Production prompts (from api/services/l2_enricher.py)
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """You are an AI transformation strategist for a B2B AI consulting firm \
targeting European mid-market businesses.

You receive a company profile (L1 data) and validated research signals (L2 data). \
Generate actionable sales intelligence.

RULES:
- Every opportunity must link to a specific finding from the research
- If research is thin, generate fewer opportunities — 2 strong beats 5 weak
- Quick wins MUST be achievable in 4-8 weeks with clear ROI
- Pain hypothesis = what keeps a senior leader awake, based on evidence

PITCH FRAMING:
- growth_acceleration: expansion, funding, hiring
- efficiency_protection: cost pressure, layoffs, flat revenue
- competitive_catch_up: competitors adopting AI, no AI initiatives found
- compliance_driven: regulatory deadlines, audit pressure

OUTPUT FORMAT: Return ONLY valid JSON. Start with {.

{
  "ai_opportunities": "Top 3-5 AI use cases with evidence and impact",
  "pain_hypothesis": "1-2 sentences based on evidence",
  "quick_wins": [{"use_case": "...", "evidence": "...", "impact": "...", "complexity": "low|medium"}],
  "industry_pain_points": "Top 3 industry-specific pain points",
  "cross_functional_pain": "Cross-department pain points",
  "adoption_barriers": "Likely objections or blockers",
  "competitor_ai_moves": "Competitor AI activity or null",
  "pitch_framing": "growth_acceleration|efficiency_protection|competitive_catch_up|compliance_driven",
  "executive_brief": "3-4 sentence summary for a sales rep"
}"""

SYNTHESIS_USER_TEMPLATE = """Generate AI opportunity analysis for {company_name} ({domain}):

=== COMPANY PROFILE (from L1) ===
Industry: {industry}
Size: {employees} employees
Revenue: {revenue}
Country: {country}
Summary: {summary}
Products: {products}
Customers: {customers}
Competitors: {competitors}

=== L2 RESEARCH: NEWS & SIGNALS ===
Recent News: {recent_news}
Funding: {funding}
Leadership Changes: {leadership_changes}
Digital Initiatives: {digital_initiatives}
Revenue Trend: {revenue_trend}
Growth Signals: {growth_signals}

=== L2 RESEARCH: STRATEGIC INTELLIGENCE ===
Leadership Team: {leadership_team}
AI/Transformation Roles: {ai_transformation_roles}
Hiring Signals: {other_hiring_signals}
EU Grants: {eu_grants}
Certifications: {certifications}
Regulatory Pressure: {regulatory_pressure}
Vendor Partnerships: {vendor_partnerships}
Employee Sentiment: {employee_sentiment}"""


def _format_synthesis_prompt(company, news_data=None, signals_data=None):
    """Build synthesis prompt using company data and optional research data."""
    news = news_data or {}
    signals = signals_data or {}
    return SYNTHESIS_USER_TEMPLATE.format(
        company_name=company["name"],
        domain=company.get("domain") or "unknown",
        industry=company.get("industry") or "Unknown",
        employees=company.get("employees") or "Unknown",
        revenue=company.get("revenue_eur_m") or "Unknown",
        country=company.get("hq_country") or "Unknown",
        summary=company.get("notes") or "Not available",
        products="Unknown",
        customers="Unknown",
        competitors="Unknown",
        recent_news=news.get("recent_news") or "None",
        funding=news.get("funding") or "None",
        leadership_changes=news.get("leadership_changes") or "None",
        digital_initiatives=news.get("digital_initiatives") or "None",
        revenue_trend=news.get("revenue_trend") or "Unknown",
        growth_signals=news.get("growth_signals") or "None",
        leadership_team=signals.get("leadership_team") or "Unknown",
        ai_transformation_roles=signals.get("ai_transformation_roles") or "None",
        other_hiring_signals=signals.get("other_hiring_signals") or "None",
        eu_grants=signals.get("eu_grants") or "None",
        certifications=signals.get("certifications") or "Unknown",
        regulatory_pressure=signals.get("regulatory_pressure") or "None",
        vendor_partnerships=signals.get("vendor_partnerships") or "Unknown",
        employee_sentiment=signals.get("employee_sentiment") or "Not found",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
@pytest.mark.slow
class TestL2SynthesisSchema:
    """Verify L2 synthesis outputs match expected schema."""

    def test_synthesis_with_pre_enriched_data(self, companies_fixtures,
                                               pre_enriched_fixtures,
                                               anthropic_client, cost_tracker):
        """Synthesis with rich pre-enriched L2 data should produce valid output."""
        company = companies_fixtures["pre_enriched_company"]
        news = pre_enriched_fixtures["rohlik_group_l2_news"]
        signals = pre_enriched_fixtures["rohlik_group_l2_signals"]

        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _format_synthesis_prompt(company, news, signals),
            cost_tracker, "test_l2_synthesis_pre_enriched",
            node_name="l2_synthesis", max_tokens=4000,
        )
        assert isinstance(output, dict), \
            "Expected JSON dict, got: {}".format(type(output).__name__)
        errors = validate_output(output, L2_SYNTHESIS_SCHEMA)
        assert not errors, "Schema validation failed:\n{}".format(
            "\n".join("  - " + e for e in errors))

    def test_synthesis_with_minimal_data(self, companies_fixtures,
                                         anthropic_client, cost_tracker):
        """Synthesis with no research data should still produce valid JSON."""
        company = companies_fixtures["minimal_footprint_manufacturing"]
        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _format_synthesis_prompt(company),
            cost_tracker, "test_l2_synthesis_minimal",
            node_name="l2_synthesis", max_tokens=4000,
        )
        assert isinstance(output, dict), "Expected JSON dict"
        errors = validate_output(output, L2_SYNTHESIS_SCHEMA)
        assert not errors, "Schema validation failed: {}".format(errors)


@pytest.mark.enrichment
@pytest.mark.slow
@pytest.mark.costly
class TestL2SynthesisQuality:
    """Score L2 synthesis output quality."""

    def test_quality_with_rich_data(self, companies_fixtures,
                                    pre_enriched_fixtures,
                                    anthropic_client, cost_tracker):
        """Synthesis with rich data should score >= 7."""
        company = companies_fixtures["pre_enriched_company"]
        news = pre_enriched_fixtures["rohlik_group_l2_news"]
        signals = pre_enriched_fixtures["rohlik_group_l2_signals"]

        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _format_synthesis_prompt(company, news, signals),
            cost_tracker, "test_l2_synthesis_quality_rich",
            node_name="l2_synthesis", max_tokens=4000,
        )
        assert isinstance(output, dict)
        scorer = QualityScorer(anthropic_client, cost_tracker)
        score = scorer.score("l2_synthesis",
                             {"company": company, "news": news, "signals": signals},
                             output,
                             test_name="test_l2_synthesis_quality_rich")
        assert score.overall >= 7, \
            "Quality too low: {}/10 - {}".format(score.overall, score.notes)


@pytest.mark.enrichment
@pytest.mark.slow
class TestL2SynthesisContent:
    """Validate synthesis content quality."""

    def test_quick_wins_structure(self, companies_fixtures,
                                  pre_enriched_fixtures,
                                  anthropic_client, cost_tracker):
        """Quick wins should be a list of dicts with required fields."""
        company = companies_fixtures["pre_enriched_company"]
        news = pre_enriched_fixtures["rohlik_group_l2_news"]
        signals = pre_enriched_fixtures["rohlik_group_l2_signals"]

        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _format_synthesis_prompt(company, news, signals),
            cost_tracker, "test_l2_synthesis_quick_wins",
            node_name="l2_synthesis", max_tokens=4000,
        )
        assert isinstance(output, dict)
        quick_wins = output.get("quick_wins", [])
        assert isinstance(quick_wins, list), "quick_wins should be a list"
        assert len(quick_wins) >= 1, "Expected at least 1 quick win"
        for win in quick_wins:
            assert isinstance(win, dict), "Each quick win should be a dict"
            assert "use_case" in win, "Quick win missing 'use_case'"

    def test_pitch_framing_valid(self, companies_fixtures,
                                  pre_enriched_fixtures,
                                  anthropic_client, cost_tracker):
        """Pitch framing should be one of the valid enum values."""
        company = companies_fixtures["pre_enriched_company"]
        news = pre_enriched_fixtures["rohlik_group_l2_news"]
        signals = pre_enriched_fixtures["rohlik_group_l2_signals"]

        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _format_synthesis_prompt(company, news, signals),
            cost_tracker, "test_l2_synthesis_pitch_framing",
            node_name="l2_synthesis", max_tokens=4000,
        )
        assert isinstance(output, dict), \
            "Expected JSON dict but got {}: {}".format(
                type(output).__name__, repr(output)[:200])
        framing = output.get("pitch_framing", "")
        valid_framings = [
            "growth_acceleration", "efficiency_protection",
            "competitive_catch_up", "compliance_driven",
        ]
        assert framing in valid_framings, \
            "Invalid pitch framing: '{}' not in {}".format(framing, valid_framings)
