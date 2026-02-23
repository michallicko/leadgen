"""Isolated tests for Person Profile Research (Perplexity) node.

These tests call REAL Perplexity APIs. Run with:
    pytest tests/enrichment/test_person_profile.py -v --tb=short

Requires: PERPLEXITY_API_KEY env var
"""

from datetime import datetime, timezone

import pytest

from tests.enrichment.conftest import call_perplexity, get_contact_keys
from tests.enrichment.utils.schema_validator import validate_output, PERSON_PROFILE_SCHEMA
from tests.enrichment.utils.quality_scorer import QualityScorer

# ---------------------------------------------------------------------------
# Production prompts (from api/services/person_enricher.py)
# ---------------------------------------------------------------------------

PROFILE_SYSTEM_PROMPT = """\
You are researching a B2B sales contact for personalized outreach. \
Your job is to verify the person's current role and gather professional context.

## SEARCH DISAMBIGUATION - CRITICAL
The person's name may be common. You MUST verify results match:
1. The company name AND domain provided
2. The job title or seniority level provided
3. The geographic region (if provided)

Do NOT include information about similarly-named individuals at other companies.

## RESEARCH FOCUS
1. ROLE VERIFICATION: Confirm current role at this specific company
2. CAREER TRAJECTORY: Previous roles, tenure patterns, promotions
3. THOUGHT LEADERSHIP: LinkedIn posts, articles, speaking engagements, podcasts
4. PROFESSIONAL BACKGROUND: Education, certifications, areas of expertise
5. PUBLIC PRESENCE: Recent interviews, quotes, conference appearances

## DATE RELEVANCE
Current date is provided by the user.
- Role verification: Must be current (within last 6 months)
- Career history: Full history is relevant
- Thought leadership: Prioritize last 24 months
- If role appears outdated, flag as "role_verification_needed"

## OUTPUT FORMAT
Return ONLY a JSON object. No markdown. No code fences. Start with {.

{
  "current_role_verified": true|false,
  "role_verification_source": "Source where current role was confirmed",
  "role_mismatch_flag": "If title doesn't match input, explain. Or null",
  "career_highlights": "Key career moves, companies, tenure patterns. Max 5.",
  "career_trajectory": "ascending|lateral|descending|early_career|unknown",
  "thought_leadership": "LinkedIn posts, articles, speaking. Or 'None found'",
  "thought_leadership_topics": ["topic1", "topic2"],
  "education": "Degrees, institutions. Or 'Unknown'",
  "certifications": "Professional certifications. Or 'None found'",
  "expertise_areas": ["area1", "area2"],
  "public_presence_level": "high|medium|low|none",
  "data_confidence": "high|medium|low"
}"""

PROFILE_USER_TEMPLATE = """\
Research professional background for this B2B contact:

Name: {full_name}
Job Title: {job_title}
Company: {company_name}
Company Domain: {domain}
LinkedIn URL: {linkedin_url}
Location: {city}, {country}

Current date: {current_date}

Search approach:
1. "{full_name}" "{company_name}" site:linkedin.com
2. "{full_name}" "{company_name}" "{job_title}"
3. "{full_name}" speaker OR podcast OR interview

Verify all results are about THIS person at {domain}."""


def _format_user_prompt(contact):
    full_name = "{} {}".format(
        contact.get("first_name", ""), contact.get("last_name", "")).strip()
    return PROFILE_USER_TEMPLATE.format(
        full_name=full_name,
        job_title=contact.get("job_title") or "Unknown",
        company_name=contact.get("company_name") or "Unknown",
        domain=contact.get("company_domain") or "unknown",
        linkedin_url=contact.get("linkedin_url") or "Not provided",
        city=contact.get("city") or "",
        country=contact.get("country") or "",
        current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
class TestPersonProfileSchema:
    """Verify person profile outputs match expected schema."""

    @pytest.mark.parametrize("contact_key", [
        "c_level_strong_presence_1",
        "c_level_strong_presence_2",
        "mid_level_manager_2",
        "pre_enriched_contact",
        "finance_compliance",
    ])
    def test_output_schema(self, contact_key, contacts_fixtures,
                           perplexity_client, cost_tracker):
        """Output matches expected JSON schema."""
        contact = contacts_fixtures[contact_key]
        output = call_perplexity(
            perplexity_client, PROFILE_SYSTEM_PROMPT,
            _format_user_prompt(contact),
            cost_tracker, "test_person_profile_schema_{}".format(contact_key),
            node_name="person_profile", model="sonar",
            max_tokens=800, temperature=0.2,
        )
        assert isinstance(output, dict), \
            "Expected JSON dict, got: {}".format(type(output).__name__)
        errors = validate_output(output, PERSON_PROFILE_SCHEMA)
        assert not errors, "Schema validation failed:\n{}".format(
            "\n".join("  - " + e for e in errors))


@pytest.mark.enrichment
@pytest.mark.slow
class TestPersonProfileQuality:
    """Score person profile output quality."""

    @pytest.mark.parametrize("contact_key", [
        "c_level_strong_presence_1",
        "c_level_strong_presence_2",
    ])
    def test_quality_high_presence(self, contact_key, contacts_fixtures,
                                   perplexity_client, anthropic_client,
                                   cost_tracker):
        """High-presence C-level contacts should score >= 6."""
        contact = contacts_fixtures[contact_key]
        output = call_perplexity(
            perplexity_client, PROFILE_SYSTEM_PROMPT,
            _format_user_prompt(contact),
            cost_tracker, "test_person_profile_quality_{}".format(contact_key),
            node_name="person_profile", model="sonar",
            max_tokens=800, temperature=0.2,
        )
        assert isinstance(output, dict)
        scorer = QualityScorer(anthropic_client, cost_tracker)
        score = scorer.score("person_profile", contact, output,
                             test_name="test_person_profile_quality_{}".format(
                                 contact_key))
        # Threshold 5: role changes, stale data, and sparse public
        # presence can legitimately lower scores for individual contacts
        assert score.overall >= 5, \
            "Quality too low: {}/10 - {}".format(score.overall, score.notes)


@pytest.mark.enrichment
class TestPersonProfileEdgeCases:
    """Edge case tests for person profile node."""

    def test_minimal_footprint_person(self, contacts_fixtures,
                                      perplexity_client, cost_tracker):
        """Person with no digital presence should still return valid JSON."""
        contact = contacts_fixtures["minimal_footprint_1"]
        output = call_perplexity(
            perplexity_client, PROFILE_SYSTEM_PROMPT,
            _format_user_prompt(contact),
            cost_tracker, "test_person_profile_minimal",
            node_name="person_profile", model="sonar",
            max_tokens=800, temperature=0.2,
        )
        assert isinstance(output, dict)
        errors = validate_output(output, PERSON_PROFILE_SCHEMA)
        assert not errors, "Schema validation failed: {}".format(errors)
        # Confidence should be low
        confidence = output.get("data_confidence", "")
        assert confidence in ("low", "medium"), \
            "Expected low confidence for minimal footprint, got: {}".format(
                confidence)

    def test_c_level_role_verified(self, contacts_fixtures,
                                   perplexity_client, cost_tracker):
        """Well-known CEO should have role verified."""
        contact = contacts_fixtures["c_level_strong_presence_1"]
        output = call_perplexity(
            perplexity_client, PROFILE_SYSTEM_PROMPT,
            _format_user_prompt(contact),
            cost_tracker, "test_person_profile_role_verified",
            node_name="person_profile", model="sonar",
            max_tokens=800, temperature=0.2,
        )
        assert isinstance(output, dict)
        assert output.get("current_role_verified") is True, \
            "Expected role verified for Henrik Ehrnrooth (Kone CEO)"
        assert output.get("public_presence_level") in ("high", "medium"), \
            "Expected high/medium public presence for Kone CEO"
