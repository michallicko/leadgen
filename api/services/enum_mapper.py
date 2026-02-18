"""Fuzzy enum mapper for LLM output normalization.

LLMs return free-text values that may not match PostgreSQL enum constraints.
This module provides a mapping layer: exact match → synonym lookup → None.

Usage:
    from api.services.enum_mapper import map_enum_value
    mapped = map_enum_value("ownership_type", "Private")  # → "bootstrapped"
    mapped = map_enum_value("geo_region", "uk_ie")         # → "uk_ireland"
"""

ENUM_CONFIGS = {
    "ownership_type": {
        "valid_values": {
            "bootstrapped", "vc_backed", "pe_backed", "public",
            "family_owned", "state_owned", "other",
        },
        "synonyms": {
            # Private / generic
            "private": "bootstrapped",
            "privately held": "bootstrapped",
            "privately-held": "bootstrapped",
            "private company": "bootstrapped",
            "independent": "bootstrapped",
            "self-funded": "bootstrapped",
            # Government
            "government": "state_owned",
            "government-owned": "state_owned",
            "government owned": "state_owned",
            "gov": "state_owned",
            "state": "state_owned",
            "state owned": "state_owned",
            "municipal": "state_owned",
            # Public
            "publicly traded": "public",
            "publicly-traded": "public",
            "listed": "public",
            "stock exchange": "public",
            "ipo": "public",
            # VC
            "venture-backed": "vc_backed",
            "venture backed": "vc_backed",
            "venture capital": "vc_backed",
            "vc": "vc_backed",
            "vc funded": "vc_backed",
            # PE
            "pe-owned": "pe_backed",
            "pe owned": "pe_backed",
            "private equity": "pe_backed",
            "pe": "pe_backed",
            "buyout": "pe_backed",
            # Family
            "family": "family_owned",
            "family-owned": "family_owned",
            "family owned": "family_owned",
            "family business": "family_owned",
            # Other
            "non-profit": "other",
            "nonprofit": "other",
            "non profit": "other",
            "cooperative": "other",
            "coop": "other",
            "co-op": "other",
            "ngo": "other",
            "charity": "other",
            "foundation": "other",
            "unknown": "other",
            "subsidiary": "other",
        },
    },
    "geo_region": {
        "valid_values": {
            "dach", "nordics", "benelux", "cee", "uk_ireland",
            "southern_europe", "us", "other",
        },
        "synonyms": {
            # UK/Ireland fixes (the primary bug)
            "uk_ie": "uk_ireland",
            "uk": "uk_ireland",
            "ireland": "uk_ireland",
            "united kingdom": "uk_ireland",
            "england": "uk_ireland",
            "scotland": "uk_ireland",
            "wales": "uk_ireland",
            "great britain": "uk_ireland",
            "gb": "uk_ireland",
            # US fixes
            "north_america": "us",
            "usa": "us",
            "united states": "us",
            "america": "us",
            "canada": "us",
            # DACH
            "germany": "dach",
            "deutschland": "dach",
            "austria": "dach",
            "switzerland": "dach",
            "schweiz": "dach",
            "liechtenstein": "dach",
            # Nordics
            "sweden": "nordics",
            "norway": "nordics",
            "denmark": "nordics",
            "finland": "nordics",
            "iceland": "nordics",
            # CEE
            "czech": "cee",
            "czech republic": "cee",
            "czechia": "cee",
            "poland": "cee",
            "hungary": "cee",
            "slovakia": "cee",
            "romania": "cee",
            "bulgaria": "cee",
            "croatia": "cee",
            "slovenia": "cee",
            "serbia": "cee",
            "estonia": "cee",
            "latvia": "cee",
            "lithuania": "cee",
            # Benelux
            "netherlands": "benelux",
            "belgium": "benelux",
            "luxembourg": "benelux",
            "holland": "benelux",
            # Southern Europe
            "france": "southern_europe",
            "spain": "southern_europe",
            "italy": "southern_europe",
            "portugal": "southern_europe",
            "greece": "southern_europe",
        },
    },
    "industry": {
        "valid_values": {
            "software_saas", "it", "professional_services", "financial_services",
            "healthcare", "pharma_biotech", "manufacturing", "automotive",
            "aerospace_defense", "retail", "hospitality", "media", "energy",
            "telecom", "transport", "construction", "real_estate", "agriculture",
            "education", "public_sector", "creative_services", "other",
        },
        "synonyms": {
            # Creative/arts (the United Arts gap)
            "arts": "creative_services",
            "arts & entertainment": "creative_services",
            "arts and entertainment": "creative_services",
            "entertainment": "creative_services",
            "events": "creative_services",
            "event management": "creative_services",
            "event production": "creative_services",
            "culture": "creative_services",
            "cultural": "creative_services",
            "performing arts": "creative_services",
            "music": "creative_services",
            "film": "creative_services",
            "film production": "creative_services",
            "digital media": "creative_services",
            "advertising": "creative_services",
            "design": "creative_services",
            "creative": "creative_services",
            "creative agency": "creative_services",
            "marketing agency": "creative_services",
            "pr": "creative_services",
            "public relations": "creative_services",
            # Tech
            "software": "software_saas",
            "saas": "software_saas",
            "technology": "it",
            "information technology": "it",
            "tech": "it",
            "cybersecurity": "it",
            # Services
            "consulting": "professional_services",
            "legal": "professional_services",
            "accounting": "professional_services",
            "staffing": "professional_services",
            "recruitment": "professional_services",
            # Finance
            "banking": "financial_services",
            "insurance": "financial_services",
            "fintech": "financial_services",
            # Health
            "medical": "healthcare",
            "hospital": "healthcare",
            "pharma": "pharma_biotech",
            "biotech": "pharma_biotech",
            "life sciences": "pharma_biotech",
            # Other industries
            "automotive": "automotive",
            "aerospace": "aerospace_defense",
            "defense": "aerospace_defense",
            "defence": "aerospace_defense",
            "retail": "retail",
            "e-commerce": "retail",
            "ecommerce": "retail",
            "hotel": "hospitality",
            "tourism": "hospitality",
            "travel": "hospitality",
            "restaurant": "hospitality",
            "catering": "hospitality",
            "food service": "hospitality",
            "media": "media",
            "broadcasting": "media",
            "publishing": "media",
            "gaming": "media",
            "oil and gas": "energy",
            "renewable energy": "energy",
            "utilities": "energy",
            "logistics": "transport",
            "shipping": "transport",
            "freight": "transport",
            "aviation": "transport",
            "real estate": "real_estate",
            "property": "real_estate",
            "agriculture": "agriculture",
            "farming": "agriculture",
            "agtech": "agriculture",
            "telecommunications": "telecom",
            "education": "education",
            "e-learning": "education",
            "edtech": "education",
            "government": "public_sector",
            "non-profit": "public_sector",
            "ngo": "public_sector",
            "construction": "construction",
            "building": "construction",
        },
    },
    "business_type": {
        "valid_values": {
            "product_company", "saas", "service_company",
            "manufacturer", "distributor", "platform", "hybrid",
        },
        "synonyms": {
            "software": "saas",
            "software company": "product_company",
            "cloud": "saas",
            "cloud software": "saas",
            "manufacturing": "manufacturer",
            "production": "manufacturer",
            "service": "service_company",
            "services": "service_company",
            "consulting": "service_company",
            "consultancy": "service_company",
            "agency": "service_company",
            "outsourcing": "service_company",
            # Legacy → new mapping
            "service_provider": "service_company",
            "service provider": "service_company",
            "product": "product_company",
            "product company": "product_company",
            "distribution": "distributor",
            "wholesale": "distributor",
            "wholesaler": "distributor",
            "marketplace": "platform",
            "exchange": "platform",
            "mixed": "hybrid",
            "multi-model": "hybrid",
            "other": "service_company",
        },
    },
    "company_size": {
        "valid_values": {
            "micro", "small", "medium", "mid_market", "enterprise",
        },
        "synonyms": {
            # Legacy → new mapping
            "startup": "small",
            "smb": "medium",
            "start-up": "small",
            "start up": "small",
            "small business": "small",
            "midsize": "medium",
            "mid-size": "medium",
            "mid size": "medium",
            "mid market": "mid_market",
            "mid-market": "mid_market",
            "large": "enterprise",
            "large enterprise": "enterprise",
            "corporation": "enterprise",
            "corporate": "enterprise",
            "very small": "micro",
            "tiny": "micro",
        },
    },
    "industry_category": {
        "valid_values": {
            "technology", "services", "finance", "healthcare_life_sci",
            "industrial", "consumer", "infrastructure", "primary_sector",
            "public_education",
        },
        "synonyms": {
            "tech": "technology",
            "it": "technology",
            "software": "technology",
            "consulting": "services",
            "professional services": "services",
            "creative": "services",
            "financial": "finance",
            "banking": "finance",
            "insurance": "finance",
            "health": "healthcare_life_sci",
            "healthcare": "healthcare_life_sci",
            "pharma": "healthcare_life_sci",
            "biotech": "healthcare_life_sci",
            "life sciences": "healthcare_life_sci",
            "manufacturing": "industrial",
            "automotive": "industrial",
            "aerospace": "industrial",
            "defense": "industrial",
            "construction": "industrial",
            "retail": "consumer",
            "hospitality": "consumer",
            "media": "consumer",
            "entertainment": "consumer",
            "telecom": "infrastructure",
            "transport": "infrastructure",
            "logistics": "infrastructure",
            "real estate": "infrastructure",
            "energy": "primary_sector",
            "agriculture": "primary_sector",
            "education": "public_education",
            "public sector": "public_education",
            "government": "public_education",
        },
    },
    "business_model": {
        "valid_values": {
            "b2b", "b2c", "marketplace", "gov", "non_profit", "hybrid",
        },
        "synonyms": {
            "business to business": "b2b",
            "business-to-business": "b2b",
            "enterprise": "b2b",
            "business to consumer": "b2c",
            "business-to-consumer": "b2c",
            "consumer": "b2c",
            "direct to consumer": "b2c",
            "d2c": "b2c",
            "dtc": "b2c",
            "government": "gov",
            "public sector": "gov",
            "nonprofit": "non_profit",
            "non-profit": "non_profit",
            "charity": "non_profit",
            "b2b2c": "hybrid",
            "mixed": "hybrid",
        },
    },
}


def map_enum_value(field_name, raw_value):
    """Map a raw LLM output to a valid DB enum value.

    Resolution order:
    1. None/empty → None
    2. Exact match against valid_values (case-insensitive)
    3. Synonym lookup (case-insensitive)
    4. No match → None

    Args:
        field_name: The enum field name (e.g., "ownership_type", "geo_region")
        raw_value: The raw string from LLM output

    Returns:
        Valid DB enum string, or None if no mapping found
    """
    if raw_value is None:
        return None

    config = ENUM_CONFIGS.get(field_name)
    if not config:
        return None

    s = str(raw_value).strip().lower()
    if not s:
        return None

    valid = config["valid_values"]
    synonyms = config.get("synonyms", {})

    # 1. Exact match (case-insensitive)
    if s in valid:
        return s

    # 2. Synonym lookup
    if s in synonyms:
        return synonyms[s]

    return None
