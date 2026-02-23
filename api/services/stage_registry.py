"""Stage registry: configurable DAG of enrichment stages.

Defines each stage's dependencies, entity type, execution mode, and
country gates. Provides utility functions for topological sorting and
stage lookup used by the DAG executor and eligibility builder.
"""

from collections import deque
from typing import Dict, List, Optional

STAGE_REGISTRY = {
    "l1": {
        "entity_type": "company",
        "hard_deps": [],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "L1 Company Profile",
        "cost_default_usd": 0.02,
        "country_gate": None,
    },
    "l2": {
        "entity_type": "company",
        "hard_deps": ["triage"],
        "soft_deps": [],
        "execution_mode": "webhook",
        "display_name": "L2 Deep Research",
        "cost_default_usd": 0.08,
        "country_gate": None,
    },
    "signals": {
        "entity_type": "company",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Strategic Signals",
        "cost_default_usd": 0.05,
        "country_gate": None,
    },
    "registry": {
        "entity_type": "company",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Legal & Registry",
        "cost_default_usd": 0.00,
        "country_gate": {
            "countries": [
                "CZ",
                "Czech Republic",
                "Czechia",
                "NO",
                "Norway",
                "Norge",
                "FI",
                "Finland",
                "Suomi",
                "FR",
                "France",
            ],
            "tlds": [".cz", ".no", ".fi", ".fr"],
        },
    },
    "news": {
        "entity_type": "company",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "News & PR",
        "cost_default_usd": 0.04,
        "country_gate": None,
    },
    "person": {
        "entity_type": "contact",
        "hard_deps": ["l1"],
        "soft_deps": ["l2", "signals"],
        "execution_mode": "webhook",
        "display_name": "Role & Employment",
        "cost_default_usd": 0.04,
        "country_gate": None,
    },
    "social": {
        "entity_type": "contact",
        "hard_deps": ["l1"],
        "soft_deps": ["l2", "signals"],
        "execution_mode": "native",
        "display_name": "Social & Online",
        "cost_default_usd": 0.03,
        "country_gate": None,
    },
    "career": {
        "entity_type": "contact",
        "hard_deps": ["l1"],
        "soft_deps": ["l2"],
        "execution_mode": "native",
        "display_name": "Career History",
        "cost_default_usd": 0.03,
        "country_gate": None,
    },
    "contact_details": {
        "entity_type": "contact",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Contact Details",
        "cost_default_usd": 0.01,
        "country_gate": None,
    },
    "triage": {
        "entity_type": "company",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Triage",
        "cost_default_usd": 0.00,
        "country_gate": None,
        "is_gate": True,
    },
    "qc": {
        "entity_type": "company",
        "hard_deps": [],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Quality Check",
        "cost_default_usd": 0.00,
        "country_gate": None,
        "is_terminal": True,
    },
}

# ---------------------------------------------------------------------------
# Boost model mapping: standard vs upgraded models per stage
# ---------------------------------------------------------------------------

BOOST_MODELS = {
    "l1": {"standard": "sonar", "boost": "sonar-pro", "cost_boost": 0.06},
    "l2": {"standard": "sonar-pro", "boost": "sonar-reasoning-pro", "cost_boost": 0.30},
    "person": {"standard": "sonar", "boost": "sonar-pro", "cost_boost": 0.20},
    "signals": {"standard": "sonar", "boost": "sonar-pro", "cost_boost": 0.10},
    "news": {"standard": "sonar", "boost": "sonar-pro", "cost_boost": 0.08},
    "social": {"standard": "sonar", "boost": "sonar-pro", "cost_boost": 0.06},
    "career": {"standard": "sonar", "boost": "sonar-pro", "cost_boost": 0.06},
    "contact_details": {"standard": "sonar", "boost": "sonar-pro", "cost_boost": 0.02},
}

ANTHROPIC_BOOST = {
    "standard": "claude-haiku-4-5-20251001",
    "boost": "claude-sonnet-4-5-20241022",
}

STAGE_FIELDS: Dict[str, List[dict]] = {
    "l1": [
        {"key": "summary", "label": "Summary", "type": "text", "table": "companies"},
        {"key": "industry", "label": "Industry", "type": "enum", "table": "companies"},
        {
            "key": "business_model",
            "label": "B2B/B2C",
            "type": "enum",
            "table": "companies",
        },
        {
            "key": "business_type",
            "label": "Business Type",
            "type": "enum",
            "table": "companies",
        },
        {
            "key": "ownership_type",
            "label": "Ownership",
            "type": "enum",
            "table": "companies",
        },
        {
            "key": "verified_revenue_eur_m",
            "label": "Revenue (EUR M)",
            "type": "number",
            "table": "companies",
        },
        {
            "key": "revenue_range",
            "label": "Revenue Range",
            "type": "enum",
            "table": "companies",
        },
        {
            "key": "verified_employees",
            "label": "Employees",
            "type": "number",
            "table": "companies",
        },
        {
            "key": "company_size",
            "label": "Company Size",
            "type": "enum",
            "table": "companies",
        },
        {"key": "hq_city", "label": "HQ City", "type": "text", "table": "companies"},
        {
            "key": "hq_country",
            "label": "HQ Country",
            "type": "text",
            "table": "companies",
        },
        {"key": "geo_region", "label": "Region", "type": "enum", "table": "companies"},
        {
            "key": "industry_category",
            "label": "Industry Category",
            "type": "enum",
            "table": "companies",
        },
        {
            "key": "triage_score",
            "label": "Triage Score",
            "type": "number",
            "table": "companies",
        },
        {
            "key": "pre_score",
            "label": "Pre-Score",
            "type": "number",
            "table": "company_enrichment_l1",
        },
        {
            "key": "triage_notes",
            "label": "Triage Notes",
            "type": "text",
            "table": "company_enrichment_l1",
        },
        {
            "key": "research_query",
            "label": "Research Query",
            "type": "text",
            "table": "company_enrichment_l1",
        },
        {
            "key": "raw_response",
            "label": "Raw Response",
            "type": "json",
            "table": "company_enrichment_l1",
        },
        {
            "key": "confidence",
            "label": "Confidence",
            "type": "number",
            "table": "company_enrichment_l1",
        },
        {
            "key": "quality_score",
            "label": "Quality Score",
            "type": "number",
            "table": "company_enrichment_l1",
        },
        {
            "key": "qc_flags",
            "label": "QC Flags",
            "type": "json",
            "table": "company_enrichment_l1",
        },
    ],
    "l2": [
        # Profile module
        {
            "key": "company_intel",
            "label": "Company Intel",
            "type": "text",
            "table": "company_enrichment_profile",
        },
        {
            "key": "key_products",
            "label": "Key Products",
            "type": "text",
            "table": "company_enrichment_profile",
        },
        {
            "key": "customer_segments",
            "label": "Customers",
            "type": "text",
            "table": "company_enrichment_profile",
        },
        {
            "key": "competitors",
            "label": "Competitors",
            "type": "text",
            "table": "company_enrichment_profile",
        },
        {
            "key": "tech_stack",
            "label": "Tech Stack",
            "type": "text",
            "table": "company_enrichment_profile",
        },
        {
            "key": "leadership_team",
            "label": "Leadership",
            "type": "text",
            "table": "company_enrichment_profile",
        },
        {
            "key": "certifications",
            "label": "Certifications",
            "type": "text",
            "table": "company_enrichment_profile",
        },
        # Market module
        {
            "key": "recent_news",
            "label": "Recent News",
            "type": "text",
            "table": "company_enrichment_market",
        },
        {
            "key": "funding_history",
            "label": "Funding",
            "type": "text",
            "table": "company_enrichment_market",
        },
        {
            "key": "eu_grants",
            "label": "EU Grants",
            "type": "text",
            "table": "company_enrichment_market",
        },
        {
            "key": "media_sentiment",
            "label": "Media Sentiment",
            "type": "text",
            "table": "company_enrichment_market",
        },
        {
            "key": "press_releases",
            "label": "Press Releases",
            "type": "text",
            "table": "company_enrichment_market",
        },
        {
            "key": "thought_leadership",
            "label": "Thought Leadership",
            "type": "text",
            "table": "company_enrichment_market",
        },
        # Opportunity module
        {
            "key": "pain_hypothesis",
            "label": "Pain Hypothesis",
            "type": "text",
            "table": "company_enrichment_opportunity",
        },
        {
            "key": "relevant_case_study",
            "label": "Case Studies",
            "type": "text",
            "table": "company_enrichment_opportunity",
        },
        {
            "key": "ai_opportunities",
            "label": "AI Opportunities",
            "type": "text",
            "table": "company_enrichment_opportunity",
        },
        {
            "key": "quick_wins",
            "label": "Quick Wins",
            "type": "json",
            "table": "company_enrichment_opportunity",
        },
        {
            "key": "industry_pain_points",
            "label": "Industry Pains",
            "type": "text",
            "table": "company_enrichment_opportunity",
        },
        {
            "key": "cross_functional_pain",
            "label": "Cross-Functional Pain",
            "type": "text",
            "table": "company_enrichment_opportunity",
        },
        {
            "key": "adoption_barriers",
            "label": "Adoption Barriers",
            "type": "text",
            "table": "company_enrichment_opportunity",
        },
    ],
    "registry": [
        {
            "key": "registration_id",
            "label": "Registration ID",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "registration_country",
            "label": "Registry Country",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "tax_id",
            "label": "Tax ID",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "official_name",
            "label": "Official Name",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "legal_form",
            "label": "Legal Form",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "legal_form_name",
            "label": "Legal Form Name",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "registration_status",
            "label": "Reg. Status",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "date_established",
            "label": "Established",
            "type": "date",
            "table": "company_legal_profile",
        },
        {
            "key": "date_dissolved",
            "label": "Dissolved",
            "type": "date",
            "table": "company_legal_profile",
        },
        {
            "key": "registered_address",
            "label": "Address",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "address_city",
            "label": "City",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "address_postal_code",
            "label": "Postal Code",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "nace_codes",
            "label": "NACE Codes",
            "type": "json",
            "table": "company_legal_profile",
        },
        {
            "key": "directors",
            "label": "Directors",
            "type": "json",
            "table": "company_legal_profile",
        },
        {
            "key": "registered_capital",
            "label": "Capital",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "registration_court",
            "label": "Reg. Court",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "registration_number",
            "label": "Reg. Number",
            "type": "text",
            "table": "company_legal_profile",
        },
        {
            "key": "insolvency_flag",
            "label": "Insolvency",
            "type": "boolean",
            "table": "company_legal_profile",
        },
        {
            "key": "insolvency_details",
            "label": "Insolvency Details",
            "type": "json",
            "table": "company_legal_profile",
        },
        {
            "key": "active_insolvency_count",
            "label": "Active Insolvencies",
            "type": "number",
            "table": "company_legal_profile",
        },
        {
            "key": "match_confidence",
            "label": "Match Confidence",
            "type": "number",
            "table": "company_legal_profile",
        },
        {
            "key": "credibility_score",
            "label": "Credibility Score",
            "type": "number",
            "table": "company_legal_profile",
        },
        {
            "key": "credibility_factors",
            "label": "Credibility Factors",
            "type": "json",
            "table": "company_legal_profile",
        },
    ],
    "signals": [
        {
            "key": "digital_initiatives",
            "label": "Digital Initiatives",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "leadership_changes",
            "label": "Leadership Changes",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "hiring_signals",
            "label": "Hiring Patterns",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "ai_hiring",
            "label": "AI Hiring Signals",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "tech_partnerships",
            "label": "Tech Partnerships",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "competitor_ai_moves",
            "label": "Competitor AI Moves",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "ai_adoption_level",
            "label": "AI Adoption Level",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "news_confidence",
            "label": "News Confidence",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "growth_indicators",
            "label": "Growth Indicators",
            "type": "text",
            "table": "company_enrichment_signals",
        },
        {
            "key": "job_posting_count",
            "label": "Job Posting Count",
            "type": "number",
            "table": "company_enrichment_signals",
        },
        {
            "key": "hiring_departments",
            "label": "Hiring Departments",
            "type": "json",
            "table": "company_enrichment_signals",
        },
    ],
    "news": [
        {
            "key": "media_mentions",
            "label": "Media Mentions",
            "type": "json",
            "table": "company_news",
        },
        {
            "key": "press_releases",
            "label": "Press Releases",
            "type": "json",
            "table": "company_news",
        },
        {
            "key": "sentiment_score",
            "label": "Sentiment",
            "type": "number",
            "table": "company_news",
        },
        {
            "key": "thought_leadership",
            "label": "Thought Leadership",
            "type": "text",
            "table": "company_news",
        },
        {
            "key": "news_summary",
            "label": "News Summary",
            "type": "text",
            "table": "company_news",
        },
    ],
    "person": [
        {
            "key": "job_title",
            "label": "Current Title",
            "type": "text",
            "table": "contacts",
        },
        {
            "key": "seniority_level",
            "label": "Seniority",
            "type": "enum",
            "table": "contacts",
        },
        {
            "key": "department",
            "label": "Department",
            "type": "enum",
            "table": "contacts",
        },
        {"key": "location_city", "label": "City", "type": "text", "table": "contacts"},
        {
            "key": "location_country",
            "label": "Country",
            "type": "text",
            "table": "contacts",
        },
        {
            "key": "linkedin_url",
            "label": "LinkedIn",
            "type": "text",
            "table": "contacts",
        },
        {"key": "email_address", "label": "Email", "type": "text", "table": "contacts"},
        {"key": "phone_number", "label": "Phone", "type": "text", "table": "contacts"},
        {"key": "language", "label": "Language", "type": "enum", "table": "contacts"},
        {
            "key": "ai_champion",
            "label": "AI Champion",
            "type": "boolean",
            "table": "contact_enrichment",
        },
        {
            "key": "ai_champion_score",
            "label": "Champion Score",
            "type": "number",
            "table": "contact_enrichment",
        },
        {
            "key": "authority_score",
            "label": "Authority Score",
            "type": "number",
            "table": "contact_enrichment",
        },
        {
            "key": "contact_score",
            "label": "Contact Score",
            "type": "number",
            "table": "contacts",
        },
        {"key": "icp_fit", "label": "ICP Fit", "type": "enum", "table": "contacts"},
        {
            "key": "person_summary",
            "label": "Person Summary",
            "type": "text",
            "table": "contact_enrichment",
        },
        {
            "key": "linkedin_profile_summary",
            "label": "LinkedIn Summary",
            "type": "text",
            "table": "contact_enrichment",
        },
        {
            "key": "relationship_synthesis",
            "label": "Relationship Fit",
            "type": "text",
            "table": "contact_enrichment",
        },
    ],
    "social": [
        {
            "key": "linkedin_url",
            "label": "LinkedIn Profile",
            "type": "text",
            "table": "contacts",
        },
        {
            "key": "twitter_handle",
            "label": "Twitter/X",
            "type": "text",
            "table": "contact_enrichment",
        },
        {
            "key": "speaking_engagements",
            "label": "Speaking Events",
            "type": "text",
            "table": "contact_enrichment",
        },
        {
            "key": "publications",
            "label": "Publications",
            "type": "text",
            "table": "contact_enrichment",
        },
        {
            "key": "github_username",
            "label": "GitHub",
            "type": "text",
            "table": "contact_enrichment",
        },
    ],
    "career": [
        {
            "key": "career_trajectory",
            "label": "Career Trajectory",
            "type": "text",
            "table": "contact_enrichment",
        },
        {
            "key": "previous_companies",
            "label": "Previous Companies",
            "type": "json",
            "table": "contact_enrichment",
        },
        {
            "key": "industry_experience",
            "label": "Industry Experience",
            "type": "json",
            "table": "contact_enrichment",
        },
        {
            "key": "total_experience_years",
            "label": "Experience Years",
            "type": "number",
            "table": "contact_enrichment",
        },
    ],
    "contact_details": [
        {"key": "email_address", "label": "Email", "type": "text", "table": "contacts"},
        {"key": "phone_number", "label": "Phone", "type": "text", "table": "contacts"},
        {
            "key": "linkedin_url",
            "label": "LinkedIn",
            "type": "text",
            "table": "contacts",
        },
        {
            "key": "profile_photo_url",
            "label": "Photo URL",
            "type": "text",
            "table": "contacts",
        },
    ],
    "qc": [
        {
            "key": "error_message",
            "label": "Quality Flags",
            "type": "text",
            "table": "companies",
        },
        {"key": "status", "label": "Data Status", "type": "enum", "table": "companies"},
    ],
}

VALID_FIELD_TYPES = {"text", "number", "boolean", "enum", "json", "date"}


def get_stage_labels(stage_code: str) -> List[str]:
    """Return just the display labels for a stage (backward-compat with old flat list)."""
    return [f["label"] for f in STAGE_FIELDS.get(stage_code, [])]


def get_stage_field_defs(stage_code: str) -> List[dict]:
    """Return full typed field definitions for a stage."""
    return STAGE_FIELDS.get(stage_code, [])


def get_stage(code: str) -> Optional[dict]:
    """Look up a stage by its code. Returns None if not found."""
    entry = STAGE_REGISTRY.get(code)
    if entry is None:
        return None
    return {"code": code, **entry}


def get_all_stages() -> List[dict]:
    """Return all stages with their codes."""
    return [{"code": k, **v} for k, v in STAGE_REGISTRY.items()]


def get_stages_for_entity_type(entity_type: str) -> List[dict]:
    """Return stages that operate on a given entity type ('company' or 'contact')."""
    return [
        {"code": k, **v}
        for k, v in STAGE_REGISTRY.items()
        if v["entity_type"] == entity_type
    ]


def topo_sort(
    stage_codes: List[str], soft_deps_enabled: Optional[Dict[str, bool]] = None
) -> List[str]:
    """Topological sort of stage codes respecting hard + activated soft dependencies.

    Args:
        stage_codes: list of stage codes to sort (subset of STAGE_REGISTRY keys)
        soft_deps_enabled: dict of stage_code -> bool for soft deps. If None, all soft deps ON.

    Returns:
        Sorted list of stage codes (dependencies first).

    Raises:
        ValueError: if a cycle is detected or unknown stages are referenced.
    """
    if soft_deps_enabled is None:
        soft_deps_enabled = {}

    codes_set = set(stage_codes)

    # Build adjacency: dep -> [dependents]
    in_degree = {code: 0 for code in codes_set}
    graph = {code: [] for code in codes_set}

    for code in codes_set:
        entry = STAGE_REGISTRY.get(code)
        if entry is None:
            raise ValueError(f"Unknown stage: {code}")

        # Hard deps
        for dep in entry["hard_deps"]:
            if dep in codes_set:
                graph[dep].append(code)
                in_degree[code] += 1

        # Soft deps (only if enabled)
        for dep in entry.get("soft_deps", []):
            enabled = soft_deps_enabled.get(code, True)  # default ON
            if enabled and dep in codes_set:
                graph[dep].append(code)
                in_degree[code] += 1

        # Terminal stages (QC): depend on all other enabled stages
        if entry.get("is_terminal"):
            for other in codes_set:
                if other != code and other not in entry["hard_deps"]:
                    # Don't double-count if already a hard dep
                    graph[other].append(code)
                    in_degree[code] += 1

    # Kahn's algorithm
    queue = deque(code for code, deg in in_degree.items() if deg == 0)
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(codes_set):
        raise ValueError("Cycle detected in stage dependency graph")

    return result


def resolve_deps(
    stage_code: str, soft_deps_enabled: Optional[Dict[str, bool]] = None
) -> List[str]:
    """Return the effective dependency list for a stage (hard + activated soft).

    Args:
        stage_code: the stage to resolve dependencies for
        soft_deps_enabled: dict of stage_code -> bool. If None, all soft deps ON.

    Returns:
        List of stage codes this stage depends on.
    """
    if soft_deps_enabled is None:
        soft_deps_enabled = {}

    entry = STAGE_REGISTRY.get(stage_code)
    if entry is None:
        return []

    deps = list(entry["hard_deps"])

    enabled = soft_deps_enabled.get(stage_code, True)
    if enabled:
        deps.extend(entry.get("soft_deps", []))

    return deps


def get_model_for_stage(stage_code, boost=False, provider="perplexity"):
    """Get the model name for a stage based on boost flag and provider.

    Args:
        stage_code: Stage code (e.g., "l1", "l2")
        boost: Whether boost mode is enabled
        provider: "perplexity" or "anthropic"

    Returns:
        Model name string
    """
    if provider == "anthropic":
        key = "boost" if boost else "standard"
        return ANTHROPIC_BOOST[key]

    # Perplexity models
    cfg = BOOST_MODELS.get(stage_code)
    if cfg is None:
        return "sonar-pro" if boost else "sonar"

    key = "boost" if boost else "standard"
    return cfg[key]


def estimate_cost(stage_codes: List[str], entity_count: int) -> float:
    """Estimate total cost for running stages on N entities."""
    total = 0.0
    for code in stage_codes:
        entry = STAGE_REGISTRY.get(code)
        if entry:
            total += entry["cost_default_usd"] * entity_count
    return round(total, 4)
