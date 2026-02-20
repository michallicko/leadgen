"""Isolated tests for Person Synthesis (Anthropic Claude) node.

These tests call REAL Anthropic APIs. Run with:
    pytest tests/enrichment/test_person_synthesis.py -v --tb=short

Requires: ANTHROPIC_API_KEY env var
"""

import pytest

from tests.enrichment.conftest import call_anthropic
from tests.enrichment.utils.schema_validator import validate_output, PERSON_SYNTHESIS_SCHEMA
from tests.enrichment.utils.quality_scorer import QualityScorer

# ---------------------------------------------------------------------------
# Production prompts (from api/services/person_enricher.py)
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """\
You are a B2B sales intelligence specialist preparing personalization data \
for outreach.

## RULES
1. Every recommendation must connect to EVIDENCE from the research
2. Personalization must feel genuine, not creepy
3. Connect person's interests to their company's pain hypothesis
4. If data is thin, provide fewer but higher-quality recommendations

## PERSONALIZATION ANGLES
- **Thought Leader**: Reference their public content
- **Tech Enthusiast**: Lead with innovation
- **Business Results**: Lead with ROI
- **Rising Star**: Acknowledge career momentum

## OUTPUT FORMAT
Return ONLY valid JSON. Start with {.

{
  "personalization_angle": "Why this person matters and how to approach them",
  "connection_points": ["point1", "point2", "point3"],
  "pain_connection": "How their role connects to company's pain hypothesis",
  "conversation_starters": "2-3 questions that show you've done research",
  "objection_prediction": "Likely objection and how to address it"
}"""

SYNTHESIS_USER_TEMPLATE = """\
Create personalized outreach strategy for this contact:

## Contact
Name: {full_name}
Title: {job_title}
Company: {company_name}

## Scores
Contact Score: {contact_score}/100
ICP Fit: {icp_fit}
AI Champion Score: {ai_champion_score}/10
Authority Score: {authority_score}/10
Seniority: {seniority}
Department: {department}

## Research Findings
Career Trajectory: {career_trajectory}
Thought Leadership: {thought_leadership}
Expertise Areas: {expertise_areas}
AI Champion Evidence: {ai_champion_evidence}
Authority Signals: {authority_signals}
Pain Indicators: {pain_indicators}
Technology Interests: {technology_interests}

## Company Context
Pain Hypothesis: {pain_hypothesis}
AI Opportunities: {ai_opportunities}
Strategic Signals: {strategic_signals}
Tier: {tier}
Industry: {industry}

Create compelling, evidence-based personalization that connects their \
interests to the company's needs."""


def _build_synthesis_prompt(contact, profile_data=None, signals_data=None,
                            scores=None, company=None, l2_data=None):
    """Build synthesis prompt from contact and research data."""
    profile = profile_data or {}
    signals = signals_data or {}
    sc = scores or {}
    co = company or {}
    l2 = l2_data or {}

    full_name = "{} {}".format(
        contact.get("first_name", ""), contact.get("last_name", "")).strip()

    expertise = profile.get("expertise_areas", [])
    if isinstance(expertise, list):
        expertise = ", ".join(expertise)
    tech = signals.get("technology_interests", [])
    if isinstance(tech, list):
        tech = ", ".join(tech)

    return SYNTHESIS_USER_TEMPLATE.format(
        full_name=full_name,
        job_title=contact.get("job_title") or "Unknown",
        company_name=contact.get("company_name") or "Unknown",
        contact_score=sc.get("contact_score", 50),
        icp_fit=sc.get("icp_fit", "Unknown"),
        ai_champion_score=sc.get("ai_champion_score", 0),
        authority_score=sc.get("authority_score", 5),
        seniority=sc.get("seniority", "Unknown"),
        department=sc.get("department", "Unknown"),
        career_trajectory=profile.get("career_trajectory", "Unknown"),
        thought_leadership=profile.get("thought_leadership", "None found"),
        expertise_areas=expertise,
        ai_champion_evidence=signals.get("ai_champion_evidence", "None found"),
        authority_signals=signals.get("authority_signals", "None found"),
        pain_indicators=signals.get("pain_indicators", "None found"),
        technology_interests=tech,
        pain_hypothesis=l2.get("pain_hypothesis", "Unknown"),
        ai_opportunities=l2.get("ai_opportunities", "Unknown"),
        strategic_signals=l2.get("company_intel", "None"),
        tier=co.get("tier", ""),
        industry=co.get("industry", ""),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
@pytest.mark.slow
class TestPersonSynthesisSchema:
    """Verify person synthesis outputs match expected schema."""

    def test_synthesis_with_rich_data(self, contacts_fixtures,
                                      companies_fixtures,
                                      pre_enriched_fixtures,
                                      anthropic_client, cost_tracker):
        """Synthesis with rich pre-enriched data should produce valid output."""
        contact = contacts_fixtures["pre_enriched_contact"]
        company = companies_fixtures["pre_enriched_company"]
        profile = pre_enriched_fixtures["tomas_cupr_profile"]
        signals = pre_enriched_fixtures["tomas_cupr_signals"]
        l2_data = {
            "pain_hypothesis": "Scaling automated operations across 6 markets",
            "ai_opportunities": "Warehouse automation, demand forecasting",
            "company_intel": "Series E funded, AI-first strategy",
        }
        scores = {
            "contact_score": 85,
            "icp_fit": "Strong Fit",
            "ai_champion_score": 8,
            "authority_score": 10,
            "seniority": "C-Level",
            "department": "Executive",
        }

        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _build_synthesis_prompt(contact, profile, signals, scores,
                                   company, l2_data),
            cost_tracker, "test_person_synthesis_rich",
            node_name="person_synthesis",
            model="claude-sonnet-4-5-20250929",
            max_tokens=800, temperature=0.7,
        )
        assert isinstance(output, dict), \
            "Expected JSON dict, got: {}".format(type(output).__name__)
        errors = validate_output(output, PERSON_SYNTHESIS_SCHEMA)
        assert not errors, "Schema validation failed:\n{}".format(
            "\n".join("  - " + e for e in errors))

    def test_synthesis_with_minimal_data(self, contacts_fixtures,
                                         anthropic_client, cost_tracker):
        """Synthesis with no research data should still produce valid JSON."""
        contact = contacts_fixtures["minimal_footprint_1"]
        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _build_synthesis_prompt(contact),
            cost_tracker, "test_person_synthesis_minimal",
            node_name="person_synthesis",
            model="claude-sonnet-4-5-20250929",
            max_tokens=800, temperature=0.7,
        )
        assert isinstance(output, dict), "Expected JSON dict"
        errors = validate_output(output, PERSON_SYNTHESIS_SCHEMA)
        assert not errors, "Schema validation failed: {}".format(errors)


@pytest.mark.enrichment
@pytest.mark.slow
@pytest.mark.costly
class TestPersonSynthesisQuality:
    """Score person synthesis output quality."""

    def test_quality_with_rich_data(self, contacts_fixtures,
                                    companies_fixtures,
                                    pre_enriched_fixtures,
                                    anthropic_client, cost_tracker):
        """Rich data synthesis should score >= 7."""
        contact = contacts_fixtures["pre_enriched_contact"]
        company = companies_fixtures["pre_enriched_company"]
        profile = pre_enriched_fixtures["tomas_cupr_profile"]
        signals = pre_enriched_fixtures["tomas_cupr_signals"]
        l2_data = {
            "pain_hypothesis": "Scaling automated operations across 6 markets",
            "ai_opportunities": "Warehouse automation, demand forecasting",
            "company_intel": "Series E funded, AI-first strategy",
        }
        scores = {
            "contact_score": 85,
            "icp_fit": "Strong Fit",
            "ai_champion_score": 8,
            "authority_score": 10,
            "seniority": "C-Level",
            "department": "Executive",
        }

        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _build_synthesis_prompt(contact, profile, signals, scores,
                                   company, l2_data),
            cost_tracker, "test_person_synthesis_quality_rich",
            node_name="person_synthesis",
            model="claude-sonnet-4-5-20250929",
            max_tokens=800, temperature=0.7,
        )
        assert isinstance(output, dict)
        scorer = QualityScorer(anthropic_client, cost_tracker)
        score = scorer.score(
            "person_synthesis",
            {"contact": contact, "profile": profile, "signals": signals},
            output,
            test_name="test_person_synthesis_quality_rich",
        )
        assert score.overall >= 7, \
            "Quality too low: {}/10 - {}".format(score.overall, score.notes)


@pytest.mark.enrichment
@pytest.mark.slow
class TestPersonSynthesisContent:
    """Validate synthesis content quality."""

    def test_connection_points_non_empty(self, contacts_fixtures,
                                         companies_fixtures,
                                         pre_enriched_fixtures,
                                         anthropic_client, cost_tracker):
        """Connection points should be a non-empty list of strings."""
        contact = contacts_fixtures["pre_enriched_contact"]
        company = companies_fixtures["pre_enriched_company"]
        profile = pre_enriched_fixtures["tomas_cupr_profile"]
        signals = pre_enriched_fixtures["tomas_cupr_signals"]
        scores = {
            "contact_score": 85, "icp_fit": "Strong Fit",
            "ai_champion_score": 8, "authority_score": 10,
            "seniority": "C-Level", "department": "Executive",
        }

        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _build_synthesis_prompt(contact, profile, signals, scores, company),
            cost_tracker, "test_person_synthesis_connection_points",
            node_name="person_synthesis",
            model="claude-sonnet-4-5-20250929",
            max_tokens=800, temperature=0.7,
        )
        assert isinstance(output, dict)
        points = output.get("connection_points", [])
        assert isinstance(points, list), "connection_points should be a list"
        assert len(points) >= 2, \
            "Expected at least 2 connection points, got {}".format(len(points))
        for p in points:
            assert isinstance(p, str) and len(p) > 10, \
                "Connection point should be a meaningful string: {}".format(
                    repr(p)[:50])

    def test_pain_connection_references_company(self, contacts_fixtures,
                                                 companies_fixtures,
                                                 pre_enriched_fixtures,
                                                 anthropic_client,
                                                 cost_tracker):
        """Pain connection should reference the company's pain hypothesis."""
        contact = contacts_fixtures["pre_enriched_contact"]
        company = companies_fixtures["pre_enriched_company"]
        profile = pre_enriched_fixtures["tomas_cupr_profile"]
        signals = pre_enriched_fixtures["tomas_cupr_signals"]
        l2_data = {
            "pain_hypothesis": "Scaling automated operations across 6 European markets while managing last-mile delivery costs",
        }
        scores = {
            "contact_score": 85, "icp_fit": "Strong Fit",
            "ai_champion_score": 8, "authority_score": 10,
            "seniority": "C-Level", "department": "Executive",
        }

        output = call_anthropic(
            anthropic_client, SYNTHESIS_SYSTEM_PROMPT,
            _build_synthesis_prompt(contact, profile, signals, scores,
                                   company, l2_data),
            cost_tracker, "test_person_synthesis_pain_connection",
            node_name="person_synthesis",
            model="claude-sonnet-4-5-20250929",
            max_tokens=800, temperature=0.7,
        )
        assert isinstance(output, dict)
        pain = output.get("pain_connection", "")
        assert len(pain) > 20, \
            "Pain connection too short: {}".format(repr(pain)[:50])
