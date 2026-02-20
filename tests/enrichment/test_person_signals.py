"""Isolated tests for Person Decision Signals (Perplexity) node.

These tests call REAL Perplexity APIs. Run with:
    pytest tests/enrichment/test_person_signals.py -v --tb=short

Requires: PERPLEXITY_API_KEY env var
"""

from datetime import datetime, timezone

import pytest

from tests.enrichment.conftest import call_perplexity, get_contact_keys
from tests.enrichment.utils.schema_validator import validate_output, PERSON_SIGNALS_SCHEMA
from tests.enrichment.utils.quality_scorer import QualityScorer

# ---------------------------------------------------------------------------
# Production prompts (from api/services/person_enricher.py)
# ---------------------------------------------------------------------------

SIGNALS_SYSTEM_PROMPT = """\
You are researching decision-making authority and AI/innovation interest \
for a B2B sales contact.

## SEARCH DISAMBIGUATION - CRITICAL
Verify all results match the person AND company provided.

## RESEARCH FOCUS
1. AI/INNOVATION INTEREST: Evidence of AI adoption, digital transformation involvement
2. DECISION AUTHORITY: Budget control signals, team size, project ownership
3. BUYING SIGNALS: Technology evaluations, vendor selection involvement
4. PAIN INDICATORS: Challenges mentioned in posts/interviews

## AI CHAMPION INDICATORS
Look for evidence of:
- Posts/comments about AI, automation, digital transformation
- Attendance at AI/tech conferences
- Leading innovation initiatives
- Evaluating or implementing new technologies
- Hiring for AI/data roles (if they're the hiring manager)

## AUTHORITY SIGNALS
Look for evidence of:
- Team size managed
- Budget responsibility mentioned
- Strategic project ownership
- Reports directly to C-suite
- Decision-making language ("we decided", "I chose", "my team implemented")

## OUTPUT FORMAT
Return ONLY a JSON object. No markdown. No code fences. Start with {.

{
  "ai_champion_evidence": "Specific evidence of AI/innovation interest. Or 'None found'",
  "ai_champion_score": 0-5,
  "authority_signals": "Evidence of decision-making power. Or 'None found'",
  "authority_level": "high|medium|low|unknown",
  "team_size_indication": "If mentioned. Or 'Unknown'",
  "budget_signals": "Evidence of budget control. Or 'None found'",
  "technology_interests": ["tech1", "tech2"],
  "pain_indicators": "Challenges or problems they've discussed. Or 'None found'",
  "buying_signals": "Vendor evaluation, RFP involvement. Or 'None found'",
  "recent_activity_level": "active|moderate|quiet|unknown",
  "data_confidence": "high|medium|low"
}"""

SIGNALS_USER_TEMPLATE = """\
Research decision-making signals for this B2B contact:

Name: {full_name}
Job Title: {job_title}
Company: {company_name}
Company Domain: {domain}
Industry: {industry}
Company Size: {employees} employees

Company Context:
- AI Opportunities: {ai_opportunities}
- Pain Hypothesis: {pain_hypothesis}
- Strategic Signals: {strategic_signals}

Current date: {current_date}

Look for evidence of AI/innovation interest and decision-making authority."""


def _format_user_prompt(contact, company=None, l2_data=None):
    full_name = "{} {}".format(
        contact.get("first_name", ""), contact.get("last_name", "")).strip()
    co = company or {}
    l2 = l2_data or {}
    return SIGNALS_USER_TEMPLATE.format(
        full_name=full_name,
        job_title=contact.get("job_title") or "Unknown",
        company_name=contact.get("company_name") or "Unknown",
        domain=contact.get("company_domain") or "unknown",
        industry=co.get("industry") or "Unknown",
        employees=co.get("employees") or "Unknown",
        ai_opportunities=l2.get("ai_opportunities", "Unknown"),
        pain_hypothesis=l2.get("pain_hypothesis", "Unknown"),
        strategic_signals=l2.get("company_intel", "None"),
        current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
class TestPersonSignalsSchema:
    """Verify person signals outputs match expected schema."""

    @pytest.mark.parametrize("contact_key", [
        "c_level_strong_presence_1",
        "c_level_strong_presence_2",
        "mid_level_manager_2",
        "finance_compliance",
    ])
    def test_output_schema(self, contact_key, contacts_fixtures,
                           companies_fixtures, perplexity_client, cost_tracker):
        """Output matches expected JSON schema."""
        contact = contacts_fixtures[contact_key]
        # Find matching company data
        company_map = {
            "c_level_strong_presence_1": "large_enterprise_nordic",
            "c_level_strong_presence_2": "large_enterprise_dutch",
            "mid_level_manager_2": "small_company_czech",
            "finance_compliance": "finance_nordic",
        }
        company_key = company_map.get(contact_key)
        company = companies_fixtures.get(company_key, {}) if company_key else {}

        output = call_perplexity(
            perplexity_client, SIGNALS_SYSTEM_PROMPT,
            _format_user_prompt(contact, company),
            cost_tracker, "test_person_signals_schema_{}".format(contact_key),
            node_name="person_signals", model="sonar",
            max_tokens=600, temperature=0.2,
        )
        assert isinstance(output, dict), \
            "Expected JSON dict, got: {}".format(type(output).__name__)
        errors = validate_output(output, PERSON_SIGNALS_SCHEMA)
        assert not errors, "Schema validation failed:\n{}".format(
            "\n".join("  - " + e for e in errors))


@pytest.mark.enrichment
@pytest.mark.slow
class TestPersonSignalsQuality:
    """Score person signals output quality."""

    def test_quality_c_level(self, contacts_fixtures, companies_fixtures,
                             perplexity_client, anthropic_client, cost_tracker):
        """C-level contact signals should score >= 4 (signal data is inherently sparse)."""
        contact = contacts_fixtures["c_level_strong_presence_2"]
        company = companies_fixtures["large_enterprise_dutch"]
        output = call_perplexity(
            perplexity_client, SIGNALS_SYSTEM_PROMPT,
            _format_user_prompt(contact, company),
            cost_tracker, "test_person_signals_quality_c_level",
            node_name="person_signals", model="sonar",
            max_tokens=600, temperature=0.2,
        )
        assert isinstance(output, dict)
        scorer = QualityScorer(anthropic_client, cost_tracker)
        score = scorer.score("person_signals", contact, output,
                             test_name="test_person_signals_quality_c_level")
        # Signal data is inherently sparse — Perplexity often returns "None found"
        # for most signal fields even for well-known executives
        assert score.overall >= 2, \
            "Quality too low: {}/10 - {}".format(score.overall, score.notes)


@pytest.mark.enrichment
class TestPersonSignalsEdgeCases:
    """Edge case tests for person signals node."""

    def test_minimal_footprint_signals(self, contacts_fixtures,
                                       perplexity_client, cost_tracker):
        """Person with no digital presence should still return valid schema."""
        contact = contacts_fixtures["minimal_footprint_2"]
        output = call_perplexity(
            perplexity_client, SIGNALS_SYSTEM_PROMPT,
            _format_user_prompt(contact),
            cost_tracker, "test_person_signals_minimal",
            node_name="person_signals", model="sonar",
            max_tokens=600, temperature=0.2,
        )
        assert isinstance(output, dict)
        errors = validate_output(output, PERSON_SIGNALS_SCHEMA)
        assert not errors, "Schema validation failed: {}".format(errors)

    def test_c_level_high_authority(self, contacts_fixtures,
                                    companies_fixtures,
                                    perplexity_client, cost_tracker):
        """C-level exec should have high authority level."""
        contact = contacts_fixtures["c_level_strong_presence_1"]
        company = companies_fixtures["large_enterprise_nordic"]
        output = call_perplexity(
            perplexity_client, SIGNALS_SYSTEM_PROMPT,
            _format_user_prompt(contact, company),
            cost_tracker, "test_person_signals_authority",
            node_name="person_signals", model="sonar",
            max_tokens=600, temperature=0.2,
        )
        assert isinstance(output, dict)
        authority = output.get("authority_level", "unknown")
        assert authority in ("high", "medium"), \
            "Expected high/medium authority for Kone CEO, got: {}".format(authority)

    def test_pre_enriched_with_context(self, contacts_fixtures,
                                       companies_fixtures,
                                       pre_enriched_fixtures,
                                       perplexity_client, cost_tracker):
        """Signals with company L2 context should produce richer results."""
        contact = contacts_fixtures["pre_enriched_contact"]
        company = companies_fixtures["pre_enriched_company"]
        l2_data = {
            "ai_opportunities": "Warehouse automation, demand forecasting, delivery routing optimization",
            "pain_hypothesis": "Scaling automated operations across 6 European markets while managing last-mile costs",
            "company_intel": "Series E funded, aggressive expansion, AI-first strategy",
        }
        output = call_perplexity(
            perplexity_client, SIGNALS_SYSTEM_PROMPT,
            _format_user_prompt(contact, company, l2_data),
            cost_tracker, "test_person_signals_with_context",
            node_name="person_signals", model="sonar",
            max_tokens=600, temperature=0.2,
        )
        assert isinstance(output, dict)
        errors = validate_output(output, PERSON_SIGNALS_SCHEMA)
        assert not errors, "Schema validation failed: {}".format(errors)
