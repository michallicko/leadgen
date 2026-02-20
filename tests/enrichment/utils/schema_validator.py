"""JSON schema validation for enrichment node outputs.

Validates required fields, types, enums, and ranges for each
enrichment node's output format.
"""


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

L1_RESEARCH_SCHEMA = {
    "required": [
        "company_name", "summary", "b2b", "hq", "ownership",
        "industry", "revenue_eur_m", "employees", "confidence",
    ],
    "types": {
        "company_name": (str,),
        "summary": (str,),
        "b2b": (bool, type(None)),
        "hq": (str,),
        "markets": (list,),
        "founded": (str, type(None)),
        "ownership": (str,),
        "industry": (str,),
        "business_type": (str,),
        "revenue_eur_m": (int, float, str),
        "revenue_year": (str, int, type(None)),
        "revenue_source": (str, type(None)),
        "employees": (int, float, str),
        "employees_source": (str, type(None)),
        # Phase 2: competitors added to L1 prompt
        "competitors": (str,),
        "confidence": (float, int),
        "flags": (list,),
    },
    "enums": {
        "ownership": [
            "Public", "Private", "Family-owned", "PE-backed",
            "VC-backed", "Government", "Cooperative", "Unknown",
        ],
        "industry": [
            "software_saas", "it", "professional_services",
            "financial_services", "healthcare", "pharma_biotech",
            "manufacturing", "automotive", "aerospace_defense",
            "retail", "hospitality", "media", "energy", "telecom",
            "transport", "construction", "real_estate", "agriculture",
            "education", "public_sector", "creative_services", "other",
        ],
        "business_type": [
            "distributor", "hybrid", "manufacturer", "platform",
            "product_company", "retail", "saas", "service_company",
        ],
    },
    "ranges": {
        "confidence": (0, 1),
    },
}

L2_NEWS_SCHEMA = {
    "required": ["recent_news", "news_confidence"],
    "types": {
        "recent_news": (str,),
        "funding": (str,),
        "leadership_changes": (str,),
        "expansion": (str,),
        "workflow_ai_evidence": (str,),
        "digital_initiatives": (str,),
        "revenue_trend": (str,),
        "growth_signals": (str,),
        # Phase 2: M&A activity added to news prompt
        "ma_activity": (str,),
        "news_confidence": (str,),
    },
    "enums": {
        "revenue_trend": [
            "growing", "stable", "declining", "restructuring", "Unknown",
        ],
        "news_confidence": ["high", "medium", "low", "none"],
    },
}

L2_SIGNALS_SCHEMA = {
    "required": ["data_completeness"],
    "types": {
        "leadership_team": (str,),
        "ai_transformation_roles": (str,),
        "other_hiring_signals": (str,),
        "eu_grants": (str,),
        "certifications": (str,),
        "regulatory_pressure": (str,),
        "vendor_partnerships": (str,),
        "employee_sentiment": (str,),
        # Phase 2: new high-value fields added to signals prompt
        "tech_stack_categories": (str,),
        "fiscal_year_end": (str,),
        "digital_maturity_score": (str, int, float),
        "it_spend_indicators": (str,),
        "data_completeness": (str,),
    },
    "enums": {
        "data_completeness": ["high", "medium", "low"],
    },
}

L2_SYNTHESIS_SCHEMA = {
    "required": [
        "ai_opportunities", "pain_hypothesis", "quick_wins",
        "executive_brief",
    ],
    "types": {
        "ai_opportunities": (str, list),
        "pain_hypothesis": (str,),
        "quick_wins": (list,),
        "industry_pain_points": (str, list),
        "cross_functional_pain": (str, list),
        "adoption_barriers": (str, list),
        "competitor_ai_moves": (str, type(None)),
        # pitch_framing: now stored in L2 table (was previously generated but lost)
        "pitch_framing": (str,),
        "executive_brief": (str,),
    },
    "enums": {
        "pitch_framing": [
            "growth_acceleration", "efficiency_protection",
            "competitive_catch_up", "compliance_driven",
        ],
    },
}

PERSON_PROFILE_SCHEMA = {
    "required": [
        "current_role_verified", "career_trajectory", "data_confidence",
    ],
    "types": {
        "current_role_verified": (bool,),
        "role_verification_source": (str,),
        "role_mismatch_flag": (str, type(None)),
        "career_highlights": (str, list),
        "career_trajectory": (str,),
        "thought_leadership": (str,),
        "thought_leadership_topics": (list,),
        "education": (str,),
        "certifications": (str,),
        "expertise_areas": (list,),
        "public_presence_level": (str,),
        "data_confidence": (str,),
    },
    "enums": {
        "career_trajectory": [
            "ascending", "lateral", "descending", "early_career", "unknown",
        ],
        "public_presence_level": ["high", "medium", "low", "none"],
        "data_confidence": ["high", "medium", "low"],
    },
}

PERSON_SIGNALS_SCHEMA = {
    "required": [
        "ai_champion_score", "authority_level", "data_confidence",
    ],
    "types": {
        "ai_champion_evidence": (str,),
        "ai_champion_score": (int, float, str),
        "authority_signals": (str,),
        "authority_level": (str,),
        "team_size_indication": (str,),
        "budget_signals": (str,),
        "technology_interests": (list,),
        "pain_indicators": (str,),
        "buying_signals": (str,),
        "recent_activity_level": (str,),
        "data_confidence": (str,),
    },
    "enums": {
        "authority_level": ["high", "medium", "low", "unknown"],
        "recent_activity_level": ["active", "moderate", "quiet", "unknown"],
        "data_confidence": ["high", "medium", "low"],
    },
}

PERSON_SYNTHESIS_SCHEMA = {
    "required": [
        "personalization_angle", "connection_points", "pain_connection",
    ],
    "types": {
        "personalization_angle": (str,),
        "connection_points": (list,),
        "pain_connection": (str,),
        "conversation_starters": (str,),
        "objection_prediction": (str,),
    },
}


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------

def validate_output(output, schema):
    """Validate an enrichment output dict against a schema definition.

    Args:
        output: dict parsed from LLM JSON response
        schema: dict with 'required', 'types', 'enums', 'ranges' keys

    Returns:
        list of error strings (empty = valid)
    """
    errors = []

    if not isinstance(output, dict):
        return ["Output is not a dict: got {}".format(type(output).__name__)]

    # Required fields
    for field in schema.get("required", []):
        if field not in output:
            errors.append("Missing required field: {}".format(field))
        elif output[field] is None:
            errors.append("Required field is null: {}".format(field))

    # Type checks
    for field, expected_types in schema.get("types", {}).items():
        if field not in output:
            continue
        value = output[field]
        if value is None and type(None) in expected_types:
            continue
        if value is not None and not isinstance(value, expected_types):
            errors.append(
                "Wrong type for {}: expected {}, got {} ({})".format(
                    field,
                    "/".join(t.__name__ for t in expected_types),
                    type(value).__name__,
                    repr(value)[:50],
                ))

    # Enum checks (case-insensitive for PE-backed variants etc.)
    for field, allowed_values in schema.get("enums", {}).items():
        if field not in output or output[field] is None:
            continue
        value = output[field]
        if not isinstance(value, str):
            continue
        # Check exact match first
        if value in allowed_values:
            continue
        # Check case-insensitive
        lower_allowed = [v.lower() for v in allowed_values]
        if value.lower() in lower_allowed:
            continue
        # Check if it starts with an allowed value (e.g. "PE-backed (Warburg)")
        partial_match = any(value.lower().startswith(a.lower())
                           for a in allowed_values)
        if not partial_match:
            errors.append(
                "Invalid enum value for {}: '{}' not in {}".format(
                    field, value, allowed_values))

    # Range checks
    for field, (min_val, max_val) in schema.get("ranges", {}).items():
        if field not in output or output[field] is None:
            continue
        value = output[field]
        if isinstance(value, (int, float)):
            if value < min_val or value > max_val:
                errors.append(
                    "Out of range for {}: {} not in [{}, {}]".format(
                        field, value, min_val, max_val))

    return errors
