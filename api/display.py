"""Enum → display translation maps.

The API returns display-format values (matching what the n8n webhooks returned)
so the dashboard JS computePipelineData() needs zero changes.
"""

STATUS_DISPLAY = {
    "new": "New",
    "enrichment_failed": "Enrichment Failed",
    "triage_passed": "Triage: Passed",
    "triage_review": "Triage: Review",
    "triage_disqualified": "Triage: Disqualified",
    "enrichment_l2_failed": "Enrichment L2 Failed",
    "enriched_l2": "Enriched L2",
    "synced": "Synced",
    "needs_review": "Needs Review",
    "enriched": "Enriched",
    "error_pushing_lemlist": "Error pushing to Lemlist",
}

TIER_DISPLAY = {
    "tier_1_platinum": "Tier 1 - Platinum",
    "tier_2_gold": "Tier 2 - Gold",
    "tier_3_silver": "Tier 3 - Silver",
    "tier_4_bronze": "Tier 4 - Bronze",
    "tier_5_copper": "Tier 5 - Copper",
    "deprioritize": "Deprioritize",
}

MESSAGE_STATUS_DISPLAY = {
    "not_started": "not_started",
    "generating": "generating",
    "pending_review": "pending_review",
    "approved": "approved",
    "sent": "sent",
    "replied": "replied",
    "no_channel": "no_channel",
    "generation_failed": "generation_failed",
}

REVIEW_STATUS_DISPLAY = {
    "draft": "draft",
    "approved": "approved",
    "rejected": "rejected",
    "sent": "sent",
    "delivered": "delivered",
    "replied": "replied",
}

ICP_FIT_DISPLAY = {
    "strong_fit": "Strong Fit",
    "moderate_fit": "Moderate Fit",
    "weak_fit": "Weak Fit",
    "unknown": "Unknown",
}

SENIORITY_DISPLAY = {
    "c_level": "C-Level",
    "vp": "VP",
    "director": "Director",
    "manager": "Manager",
    "individual_contributor": "Individual Contributor",
    "founder": "Founder",
    "other": "Other",
}

DEPARTMENT_DISPLAY = {
    "executive": "Executive",
    "engineering": "Engineering",
    "product": "Product",
    "sales": "Sales",
    "marketing": "Marketing",
    "customer_success": "Customer Success",
    "finance": "Finance",
    "hr": "HR",
    "operations": "Operations",
    "other": "Other",
}

BUSINESS_MODEL_DISPLAY = {
    "b2b": "B2B",
    "b2c": "B2C",
    "marketplace": "Marketplace",
    "gov": "Government",
    "non_profit": "Non-Profit",
    "hybrid": "Hybrid",
}

COMPANY_SIZE_DISPLAY = {
    "micro": "Micro",
    "small": "Small",
    "medium": "Medium",
    "mid_market": "Mid-Market",
    "enterprise": "Enterprise",
    # Legacy values for old data
    "startup": "Small",
    "smb": "Medium",
}

GEO_REGION_DISPLAY = {
    "dach": "DACH",
    "nordics": "Nordics",
    "benelux": "Benelux",
    "cee": "CEE",
    "uk_ireland": "UK & Ireland",
    "southern_europe": "Southern Europe",
    "us": "US",
    "other": "Other",
}

INDUSTRY_DISPLAY = {
    "software_saas": "Software / SaaS",
    "it": "IT",
    "professional_services": "Professional Services",
    "financial_services": "Financial Services",
    "healthcare": "Healthcare",
    "pharma_biotech": "Pharma / Biotech",
    "manufacturing": "Manufacturing",
    "automotive": "Automotive",
    "aerospace_defense": "Aerospace & Defense",
    "retail": "Retail",
    "hospitality": "Hospitality",
    "media": "Media",
    "energy": "Energy",
    "telecom": "Telecom",
    "transport": "Transport",
    "construction": "Construction",
    "real_estate": "Real Estate",
    "agriculture": "Agriculture",
    "education": "Education",
    "public_sector": "Public Sector",
    "creative_services": "Creative Services",
    "other": "Other",
}

RELATIONSHIP_STATUS_DISPLAY = {
    "prospect": "Prospect",
    "active": "Active",
    "dormant": "Dormant",
    "former": "Former",
    "partner": "Partner",
    "internal": "Internal",
}

REVENUE_RANGE_DISPLAY = {
    "micro": "Micro",
    "small": "Small",
    "medium": "Medium",
    "mid_market": "Mid-Market",
    "enterprise": "Enterprise",
}

BUYING_STAGE_DISPLAY = {
    "unaware": "Unaware",
    "problem_aware": "Problem Aware",
    "exploring_ai": "Exploring AI",
    "looking_for_partners": "Looking for Partners",
    "in_discussion": "In Discussion",
    "proposal_sent": "Proposal Sent",
    "won": "Won",
    "lost": "Lost",
}

ENGAGEMENT_STATUS_DISPLAY = {
    "cold": "Cold",
    "approached": "Approached",
    "prospect": "Prospect",
    "customer": "Customer",
    "churned": "Churned",
}

CRM_STATUS_DISPLAY = {
    "cold": "Cold",
    "scheduled_for_outreach": "Scheduled for Outreach",
    "outreach": "Outreach",
    "prospect": "Prospect",
    "customer": "Customer",
    "churn": "Churn",
}

BUSINESS_TYPE_DISPLAY = {
    "product_company": "Product Company",
    "saas": "SaaS",
    "service_company": "Service Company",
    "manufacturer": "Manufacturer",
    "distributor": "Distributor",
    "platform": "Platform",
    "hybrid": "Hybrid",
    # Legacy values for old data
    "service_provider": "Service Company",
    "other": "Other",
}

INDUSTRY_CATEGORY_DISPLAY = {
    "technology": "Technology",
    "services": "Services",
    "finance": "Finance",
    "healthcare_life_sci": "Healthcare & Life Sciences",
    "industrial": "Industrial",
    "consumer": "Consumer",
    "infrastructure": "Infrastructure",
    "primary_sector": "Primary Sector",
    "public_education": "Public & Education",
}

OWNERSHIP_TYPE_DISPLAY = {
    "bootstrapped": "Bootstrapped",
    "vc_backed": "VC-Backed",
    "pe_backed": "PE-Backed",
    "public": "Public",
    "family_owned": "Family-Owned",
    "state_owned": "State-Owned",
    "other": "Other",
}

CONFIDENCE_LEVEL_DISPLAY = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}

COHORT_DISPLAY = {
    "a": "A",
    "b": "B",
}

CONTACT_SOURCE_DISPLAY = {
    "inbound": "Inbound",
    "outbound": "Outbound",
    "referral": "Referral",
    "event": "Event",
    "social": "Social",
    "other": "Other",
}

LANGUAGE_DISPLAY = {
    "en": "English",
    "de": "German",
    "nl": "Dutch",
    "cs": "Czech",
}

LINKEDIN_ACTIVITY_DISPLAY = {
    "active": "Active",
    "moderate": "Moderate",
    "quiet": "Quiet",
    "unknown": "Unknown",
}

CAMPAIGN_STATUS_DISPLAY = {
    "draft": "Draft",
    "ready": "Ready",
    "generating": "Generating",
    "review": "Review",
    "approved": "Approved",
    "exported": "Exported",
    "archived": "Archived",
}

CAMPAIGN_CONTACT_STATUS_DISPLAY = {
    "pending": "Pending",
    "enrichment_ok": "Enrichment OK",
    "enrichment_needed": "Enrichment Needed",
    "generating": "Generating",
    "generated": "Generated",
    "failed": "Failed",
    "excluded": "Excluded",
}

ENRICHMENT_STAGE_DISPLAY = {
    "imported": "Imported",
    "researched": "Researched",
    "qualified": "Qualified",
    "enriched": "Enriched",
    "contacts_ready": "Contacts Ready",
    "failed": "Failed",
    "disqualified": "Disqualified",
}


# --- Reverse maps (display value → DB value) ---


def _build_reverse(display_map):
    return {v: k for k, v in display_map.items()}


STATUS_REVERSE = _build_reverse(STATUS_DISPLAY)
TIER_REVERSE = _build_reverse(TIER_DISPLAY)
ICP_FIT_REVERSE = _build_reverse(ICP_FIT_DISPLAY)
MESSAGE_STATUS_REVERSE = _build_reverse(MESSAGE_STATUS_DISPLAY)


TIER_PREFIX_TO_DB = {}
for _db_val, _disp_val in TIER_DISPLAY.items():
    _prefix = _disp_val.split(" - ")[0]  # "Tier 1 - Platinum" -> "Tier 1"
    TIER_PREFIX_TO_DB[_prefix] = _db_val


def tier_db_values(frontend_tiers):
    """Map frontend tier names like ["Tier 1", "Tier 2"] to DB enum values."""
    return [TIER_PREFIX_TO_DB[t] for t in frontend_tiers if t in TIER_PREFIX_TO_DB]


def display_status(v):
    return STATUS_DISPLAY.get(v, v) if v else v


def display_tier(v):
    return TIER_DISPLAY.get(v, v) if v else v


def display_message_status(v):
    return MESSAGE_STATUS_DISPLAY.get(v, v) if v else v


def display_icp_fit(v):
    return ICP_FIT_DISPLAY.get(v, v) if v else v


def display_seniority(v):
    return SENIORITY_DISPLAY.get(v, v) if v else v


def display_department(v):
    return DEPARTMENT_DISPLAY.get(v, v) if v else v


def display_business_model(v):
    return BUSINESS_MODEL_DISPLAY.get(v, v) if v else v


def display_company_size(v):
    return COMPANY_SIZE_DISPLAY.get(v, v) if v else v


def display_geo_region(v):
    return GEO_REGION_DISPLAY.get(v, v) if v else v


def display_industry(v):
    return INDUSTRY_DISPLAY.get(v, v) if v else v


def display_relationship_status(v):
    return RELATIONSHIP_STATUS_DISPLAY.get(v, v) if v else v


def display_revenue_range(v):
    return REVENUE_RANGE_DISPLAY.get(v, v) if v else v


def display_buying_stage(v):
    return BUYING_STAGE_DISPLAY.get(v, v) if v else v


def display_engagement_status(v):
    return ENGAGEMENT_STATUS_DISPLAY.get(v, v) if v else v


def display_crm_status(v):
    return CRM_STATUS_DISPLAY.get(v, v) if v else v


def display_business_type(v):
    return BUSINESS_TYPE_DISPLAY.get(v, v) if v else v


def display_industry_category(v):
    return INDUSTRY_CATEGORY_DISPLAY.get(v, v) if v else v


def display_ownership_type(v):
    return OWNERSHIP_TYPE_DISPLAY.get(v, v) if v else v


def display_confidence(v):
    return CONFIDENCE_LEVEL_DISPLAY.get(v, v) if v else v


def display_cohort(v):
    return COHORT_DISPLAY.get(v, v) if v else v


def display_contact_source(v):
    return CONTACT_SOURCE_DISPLAY.get(v, v) if v else v


def display_language(v):
    return LANGUAGE_DISPLAY.get(v, v) if v else v


def display_linkedin_activity(v):
    return LINKEDIN_ACTIVITY_DISPLAY.get(v, v) if v else v


def display_campaign_status(v):
    return CAMPAIGN_STATUS_DISPLAY.get(v, v) if v else v


def display_campaign_contact_status(v):
    return CAMPAIGN_CONTACT_STATUS_DISPLAY.get(v, v) if v else v


def display_enrichment_stage(v):
    return ENRICHMENT_STAGE_DISPLAY.get(v, v) if v else v


def reverse_lookup(display_map, display_value):
    """Convert a display value back to its DB enum value."""
    reverse = _build_reverse(display_map)
    return reverse.get(display_value, display_value)
