"""Field quality schema — single source of truth for managed field values.

Defines acceptable values, bucketing logic, and prompt instructions for every
enrichment field. Used by l1_enricher, enum_mapper, display, and stage_registry.

Usage:
    from api.services.field_schema import employees_to_size, revenue_to_range
    from api.services.field_schema import industry_to_category, get_prompt_instructions
"""

# ---------------------------------------------------------------------------
# Company Size — headcount-based labels
# ---------------------------------------------------------------------------

COMPANY_SIZE_VALUES = {
    "micro":       {"label": "Micro",       "min": 1,    "max": 10},
    "small":       {"label": "Small",       "min": 11,   "max": 50},
    "medium":      {"label": "Medium",      "min": 51,   "max": 200},
    "mid_market":  {"label": "Mid-Market",  "min": 201,  "max": 1000},
    "enterprise":  {"label": "Enterprise",  "min": 1001, "max": None},
}

# Legacy values that still exist in older data
COMPANY_SIZE_LEGACY = {
    "startup": "small",
    "smb": "medium",
}


def employees_to_size(emp):
    """Map employee count to a company_size value.

    Args:
        emp: Integer employee count, or None.

    Returns:
        One of: micro, small, medium, mid_market, enterprise, or None.
    """
    if emp is None:
        return None
    if emp < 10:
        return "micro"
    if emp < 50:
        return "small"
    if emp < 200:
        return "medium"
    if emp < 1000:
        return "mid_market"
    return "enterprise"


# ---------------------------------------------------------------------------
# Revenue Range — EUR millions
# ---------------------------------------------------------------------------

REVENUE_RANGE_VALUES = {
    "micro":       {"label": "Micro",       "max_eur_m": 1},
    "small":       {"label": "Small",       "max_eur_m": 10},
    "medium":      {"label": "Medium",      "max_eur_m": 50},
    "mid_market":  {"label": "Mid-Market",  "max_eur_m": 200},
    "enterprise":  {"label": "Enterprise",  "max_eur_m": None},
}


def revenue_to_range(rev_m):
    """Map revenue in EUR millions to a revenue_range value.

    Args:
        rev_m: Float revenue in EUR millions, or None.

    Returns:
        One of: micro, small, medium, mid_market, enterprise, or None.
    """
    if rev_m is None:
        return None
    if rev_m < 1:
        return "micro"
    if rev_m < 10:
        return "small"
    if rev_m < 50:
        return "medium"
    if rev_m < 200:
        return "mid_market"
    return "enterprise"


# ---------------------------------------------------------------------------
# Business Type — value chain role
# ---------------------------------------------------------------------------

BUSINESS_TYPE_VALUES = {
    "product_company", "saas", "service_company",
    "manufacturer", "distributor", "platform", "hybrid",
}

# Legacy values preserved for backward compat
BUSINESS_TYPE_LEGACY = {
    "service_provider": "service_company",
    "other": None,  # no longer mapped; stays as-is in old data
}


# ---------------------------------------------------------------------------
# Industry Category — broad sector derived from industry
# ---------------------------------------------------------------------------

INDUSTRY_CATEGORY_VALUES = {
    "technology":         {"industries": {"software_saas", "it"}},
    "services":           {"industries": {"professional_services", "creative_services"}},
    "finance":            {"industries": {"financial_services"}},
    "healthcare_life_sci": {"industries": {"healthcare", "pharma_biotech"}},
    "industrial":         {"industries": {"manufacturing", "automotive",
                                          "aerospace_defense", "construction"}},
    "consumer":           {"industries": {"retail", "hospitality", "media"}},
    "infrastructure":     {"industries": {"telecom", "transport", "real_estate"}},
    "primary_sector":     {"industries": {"agriculture", "energy"}},
    "public_education":   {"industries": {"education", "public_sector"}},
}

# Reverse lookup: industry → category
_INDUSTRY_TO_CATEGORY = {}
for _cat, _meta in INDUSTRY_CATEGORY_VALUES.items():
    for _ind in _meta["industries"]:
        _INDUSTRY_TO_CATEGORY[_ind] = _cat


def industry_to_category(industry):
    """Derive industry_category from an industry value.

    Args:
        industry: A valid industry enum value (e.g., "software_saas").

    Returns:
        Industry category string or None if industry is unknown/other.
    """
    if not industry:
        return None
    return _INDUSTRY_TO_CATEGORY.get(industry)


# ---------------------------------------------------------------------------
# Prompt instructions — injected into LLM prompts per stage
# ---------------------------------------------------------------------------

PROMPT_FIELD_INSTRUCTIONS = {
    "l1": {
        "business_type": (
            "EXACTLY ONE OF: "
            + "|".join(sorted(BUSINESS_TYPE_VALUES))
            + "\n  (product_company = builds/sells own product; "
            "saas = cloud software; service_company = consulting/agency/outsourcing; "
            "manufacturer = physical production; distributor = resale/wholesale; "
            "platform = marketplace/exchange; hybrid = multiple models)"
        ),
        "industry": (
            "EXACTLY ONE OF: software_saas|it|professional_services|"
            "financial_services|healthcare|pharma_biotech|manufacturing|"
            "automotive|aerospace_defense|retail|hospitality|media|energy|"
            "telecom|transport|construction|real_estate|agriculture|"
            "education|public_sector|creative_services|other"
        ),
    },
}


def get_prompt_instructions(stage):
    """Get field-level prompt instructions for a pipeline stage.

    Args:
        stage: Pipeline stage name (e.g., "l1").

    Returns:
        Dict of field_name → instruction string, or empty dict.
    """
    return PROMPT_FIELD_INSTRUCTIONS.get(stage, {})
