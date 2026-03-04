"""AI-powered CSV column mapping using Claude API.

Takes CSV headers + sample rows and returns a structured mapping
to Contact/Company fields with confidence scores and transforms.
"""

import json
import os
import re
import time

TARGET_FIELDS = {
    "contact": [
        "first_name",
        "last_name",
        "job_title",
        "email_address",
        "linkedin_url",
        "phone_number",
        "location_city",
        "location_country",
        "seniority_level",
        "department",
        "contact_source",
        "language",
    ],
    "company": [
        "name",
        "domain",
        "industry",
        "hq_city",
        "hq_country",
        "company_size",
        "business_model",
    ],
}

# Reverse maps for enum normalization (display value → DB value).
# These provide friendly aliases (e.g. "vice president" → "vp").
ENUM_ALIASES = {
    "seniority_level": {
        "c-level": "c_level",
        "c level": "c_level",
        "c suite": "c_level",
        "csuite": "c_level",
        "vice president": "vp",
        "individual contributor": "individual_contributor",
        "ic": "individual_contributor",
        "contributor": "individual_contributor",
    },
    "department": {
        "human resources": "hr",
        "customer success": "customer_success",
        "customer service": "customer_success",
        "support": "customer_success",
        "ops": "operations",
        "management": "executive",
        "it": "engineering",
        "technology": "engineering",
        "r&d": "engineering",
    },
    "contact_source": {},
    "language": {
        "english": "en",
        "german": "de",
        "deutsch": "de",
        "dutch": "nl",
        "czech": "cs",
        "spanish": "es",
        "italian": "it",
        "polish": "pl",
        "portuguese": "pt",
        "swedish": "sv",
        "norwegian": "no",
        "finnish": "fi",
        "danish": "da",
        "french": "fr",
    },
    "industry": {
        "software": "software_saas",
        "saas": "software_saas",
        "software / saas": "software_saas",
        "tech": "it",
        "technology": "it",
        "professional services": "professional_services",
        "consulting": "professional_services",
        "financial services": "financial_services",
        "finance": "financial_services",
        "banking": "financial_services",
        "health": "healthcare",
        "pharma": "pharma_biotech",
        "biotech": "pharma_biotech",
        "pharmaceutical": "pharma_biotech",
        "public sector": "public_sector",
        "government": "public_sector",
        "real estate": "real_estate",
        "logistics": "transport",
        "design": "creative_services",
        "advertising": "creative_services",
        "hotel": "hospitality",
        "tourism": "hospitality",
        "defense": "aerospace_defense",
        "aerospace": "aerospace_defense",
        "farming": "agriculture",
    },
    "company_size": {
        "mid-market": "mid_market",
        "mid market": "mid_market",
        "midmarket": "mid_market",
        "large": "enterprise",
    },
    "business_model": {
        "government": "gov",
        "non-profit": "non_profit",
        "nonprofit": "non_profit",
        "ngo": "non_profit",
    },
    "icp_fit": {
        "strong": "strong_fit",
        "moderate": "moderate_fit",
        "weak": "weak_fit",
    },
    "relationship_status": {},
    "message_status": {
        "not started": "not_started",
        "pending review": "pending_review",
        "pending": "pending_review",
        "no channel": "no_channel",
        "generation failed": "generation_failed",
    },
    "linkedin_activity_level": {},
    # Company enum aliases
    "ownership_type": {
        "vc": "vc_backed",
        "venture": "vc_backed",
        "pe": "pe_backed",
        "private equity": "pe_backed",
        "family": "family_owned",
        "state": "state_owned",
    },
    "geo_region": {
        "dach": "dach",
        "nordics": "nordics",
        "uk": "uk_ireland",
        "ireland": "uk_ireland",
        "southern europe": "southern_europe",
        "cee": "cee",
        "benelux": "benelux",
    },
    "revenue_range": {
        "mid-market": "mid_market",
        "mid market": "mid_market",
    },
    "buying_stage": {
        "problem aware": "problem_aware",
        "exploring ai": "exploring_ai",
        "looking for partners": "looking_for_partners",
        "in discussion": "in_discussion",
        "proposal sent": "proposal_sent",
    },
    "engagement_status": {},
    "business_type": {
        "service provider": "service_provider",
        "product company": "product_company",
        "service company": "service_company",
    },
}

# Valid PostgreSQL enum values per field.
# Contacts table enums:
ENUM_VALID_VALUES = {
    "seniority_level": {
        "c_level", "vp", "director", "manager",
        "individual_contributor", "founder", "other",
    },
    "department": {
        "executive", "engineering", "product", "sales", "marketing",
        "customer_success", "finance", "hr", "operations", "other",
    },
    "contact_source": {
        "inbound", "outbound", "referral", "event", "social", "other",
    },
    "language": {
        "en", "de", "nl", "cs", "es", "it", "pl", "pt",
        "sv", "no", "fi", "da", "fr",
    },
    "icp_fit": {"strong_fit", "moderate_fit", "weak_fit", "unknown"},
    "relationship_status": {
        "prospect", "active", "dormant", "former", "partner", "internal",
    },
    "message_status": {
        "not_started", "generating", "pending_review", "approved",
        "sent", "replied", "no_channel", "generation_failed",
    },
    "linkedin_activity_level": {"active", "moderate", "quiet", "unknown"},
    # Companies table enums:
    "industry": {
        "software_saas", "it", "professional_services", "financial_services",
        "healthcare", "manufacturing", "retail", "media", "energy", "telecom",
        "transport", "construction", "education", "public_sector", "other",
        "real_estate", "automotive", "pharma_biotech", "agriculture",
        "hospitality", "aerospace_defense", "creative_services",
    },
    "company_size": {"micro", "startup", "smb", "mid_market", "enterprise", "small", "medium"},
    "business_model": {"b2b", "b2c", "marketplace", "gov", "non_profit", "hybrid"},
    "ownership_type": {
        "bootstrapped", "vc_backed", "pe_backed", "public",
        "family_owned", "state_owned", "other",
    },
    "geo_region": {
        "dach", "nordics", "benelux", "cee", "uk_ireland",
        "southern_europe", "us", "other",
    },
    "revenue_range": {"micro", "small", "medium", "mid_market", "enterprise"},
    "buying_stage": {
        "unaware", "problem_aware", "exploring_ai", "looking_for_partners",
        "in_discussion", "proposal_sent", "won", "lost",
    },
    "engagement_status": {
        "cold", "approached", "prospect", "customer", "churned",
    },
    "business_type": {
        "manufacturer", "distributor", "service_provider", "saas",
        "platform", "other", "hybrid", "product_company", "service_company",
    },
}

# Legacy compat: ENUM_FIELDS used by normalize_enum (alias map + valid values merged)
ENUM_FIELDS = {}
for _field, _valid in ENUM_VALID_VALUES.items():
    merged = {v: v for v in _valid}  # identity map for valid values
    merged.update(ENUM_ALIASES.get(_field, {}))
    ENUM_FIELDS[_field] = merged


def sanitize_enum_value(field, value, custom_fields=None):
    """Validate and sanitize a value for a PostgreSQL enum column.

    Strategy:
    1. Exact match against valid enum values (case-insensitive, underscores normalized)
    2. Alias lookup (e.g. "vice president" → "vp")
    3. Substring match: check if any valid enum value appears in the input
    4. Fallback: store original in custom_fields, return 'other' or None

    Args:
        field: the enum field name (e.g. 'contact_source')
        value: the raw string value from the CSV
        custom_fields: optional dict to store original values when they can't be mapped

    Returns:
        A valid enum value, or None if no match and no 'other' fallback exists.
    """
    if not value:
        return None

    valid = ENUM_VALID_VALUES.get(field)
    if not valid:
        return value  # not an enum field, pass through

    aliases = ENUM_ALIASES.get(field, {})

    # Normalize: strip, lowercase, replace hyphens/spaces with underscores
    cleaned = value.strip().lower()
    normalized = cleaned.replace("-", "_").replace(" ", "_")

    # 1. Direct match against valid values
    if normalized in valid:
        return normalized
    if cleaned in valid:
        return cleaned

    # 2. Alias lookup
    alias_result = aliases.get(cleaned)
    if alias_result and alias_result in valid:
        return alias_result

    # 3. Substring match: check if any valid value is contained in the input
    for v in valid:
        if v in normalized:
            if custom_fields is not None:
                custom_fields[f"original_{field}"] = value
            return v

    # 4. Reverse substring: check if the input is contained in any valid value
    for v in valid:
        if normalized in v:
            if custom_fields is not None:
                custom_fields[f"original_{field}"] = value
            return v

    # 5. No match found: preserve original, fall back to 'other' or None
    if custom_fields is not None:
        custom_fields[f"original_{field}"] = value
    return "other" if "other" in valid else None

SYSTEM_PROMPT = """You are a data mapping assistant. Given CSV headers and sample rows,
map each CSV column to the most appropriate target field.

Target contact fields: {contact_fields}
Target company fields: {company_fields}
{custom_fields_section}
Respond with ONLY valid JSON (no markdown fences). The JSON must be an object with:
- "mappings": array of objects, each with:
  - "csv_header": the original CSV column name
  - "target": the target field name (prefixed with "contact." or "company."), or null if no match
  - "confidence": number 0.0-1.0
  - "transform": null, or one of:
    - "extract_domain" (for company URL/website → domain)
    - "normalize_enum" (for free text → DB enum value)
  - "suggested_custom_field": (optional) if target is null and the column has useful data, suggest a new
    custom field: {{"entity_type": "contact"|"company", "field_key": "snake_case_key",
    "field_label": "Display Name", "field_type": "text"|"number"|"url"|"email"|"date"|"select"}}
- "warnings": array of strings for any issues (missing required fields, ambiguous mappings, etc.)

Rules:
- first_name is required. Map first name columns to contact.first_name and last name columns to
  contact.last_name. These are separate DB columns.
- Company name is required if any company fields are present.
- If a column clearly contains a website URL, map to company.domain with transform "extract_domain".
- Prefer exact matches over fuzzy matches.
- For columns that don't match any standard or existing custom field, suggest a new custom field.
  Use entity_type "contact" for person-level data, "company" for org-level data.
  Custom field targets use the prefix "contact.custom." or "company.custom."
  (e.g., "contact.custom.email_secondary").
- If a column matches an existing custom field, map it using the custom field target.
"""


def build_mapping_prompt(headers, sample_rows):
    """Build the user prompt with headers and samples."""
    lines = ["CSV Headers: " + json.dumps(headers)]
    lines.append("\nSample rows:")
    for i, row in enumerate(sample_rows[:5], 1):
        lines.append(f"Row {i}: {json.dumps(row)}")
    return "\n".join(lines)


def _build_custom_fields_section(custom_defs):
    """Build the custom fields section for the system prompt."""
    if not custom_defs:
        return ""
    contact_custom = []
    company_custom = []
    for d in custom_defs:
        entry = (
            f"contact.custom.{d['field_key']}"
            if d["entity_type"] == "contact"
            else f"company.custom.{d['field_key']}"
        )
        contact_custom.append(entry) if d[
            "entity_type"
        ] == "contact" else company_custom.append(entry)

    lines = ["\nExisting custom fields for this tenant:"]
    if contact_custom:
        lines.append(f"Contact custom fields: {', '.join(contact_custom)}")
    if company_custom:
        lines.append(f"Company custom fields: {', '.join(company_custom)}")
    lines.append("")
    return "\n".join(lines)


def call_claude_for_mapping(headers, sample_rows, custom_defs=None):
    """Call Claude API to get column mapping suggestions.

    Args:
        headers: list of CSV column names
        sample_rows: list of dicts (up to 5 sample rows)
        custom_defs: optional list of custom field definition dicts

    Returns dict with 'mappings', 'warnings', and 'combine_columns'.
    Raises RuntimeError if API call fails.
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed — add to requirements.txt")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    system = SYSTEM_PROMPT.format(
        contact_fields=", ".join(TARGET_FIELDS["contact"]),
        company_fields=", ".join(TARGET_FIELDS["company"]),
        custom_fields_section=_build_custom_fields_section(custom_defs),
    )
    user_msg = build_mapping_prompt(headers, sample_rows)

    start_ms = int(time.time() * 1000)
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    end_ms = int(time.time() * 1000)

    text = response.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    usage_info = {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "duration_ms": end_ms - start_ms,
    }

    return json.loads(text), usage_info


def normalize_enum(field_name, value):
    """Normalize a free-text value to a DB enum value.

    Returns the DB enum value or None if no match. Uses sanitize_enum_value
    for smart matching (aliases, substring, fallback to 'other').
    """
    if not value or field_name not in ENUM_VALID_VALUES:
        return value
    return sanitize_enum_value(field_name, value)


def extract_domain(url):
    """Extract domain from a URL (strip protocol, www, trailing path)."""
    if not url:
        return None
    url = url.strip().lower()
    # Strip protocol
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            url = url[len(prefix) :]
            break
    # Strip www.
    if url.startswith("www."):
        url = url[4:]
    # Strip trailing path/query
    url = url.split("/")[0].split("?")[0].split("#")[0]
    return url if url else None


DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}"),  # 2021-12-04 or 2021-12-04 00:00:00
    re.compile(r"^\d{2}/\d{2}/\d{4}"),  # 12/04/2021
    re.compile(r"^\d{2}\.\d{2}\.\d{4}"),  # 04.12.2021
]


def _extract_domain_from_email(email):
    """Extract domain part from an email address."""
    if not email or "@" not in email:
        return None
    return email.split("@")[1]


def validate_and_fix_company(company_value, email=None):
    """Validate company name and fix obviously bad values.

    Detects dates, pure numbers, empty strings, and very short values.
    Falls back to email domain extraction when the company value is invalid.

    Args:
        company_value: the raw company name string
        email: optional email address for domain fallback

    Returns:
        cleaned company name, or email domain, or "Unknown"
    """
    if not company_value or not company_value.strip():
        return _extract_domain_from_email(email) or "Unknown"

    val = company_value.strip()

    # Check for date patterns
    for pattern in DATE_PATTERNS:
        if pattern.match(val):
            return _extract_domain_from_email(email) or "Unknown"

    # Pure number (integer or decimal)
    if re.match(r"^\d+\.?\d*$", val):
        return _extract_domain_from_email(email) or "Unknown"

    # Too short (1-2 chars, likely garbage)
    if len(val) <= 2:
        return _extract_domain_from_email(email) or "Unknown"

    return val


def apply_mapping(row, mapping_result):
    """Apply a mapping result to a single CSV row dict.

    Args:
        row: dict with CSV headers as keys
        mapping_result: the result from call_claude_for_mapping

    Returns:
        dict with keys 'contact' and 'company', each a dict of mapped fields.
        Custom field values are stored in '_custom_fields' sub-dict on each entity.
    """
    contact = {}
    company = {}
    mappings = {m["csv_header"]: m for m in mapping_result.get("mappings", [])}

    for header, value in row.items():
        m = mappings.get(header)
        if not m or not m.get("target"):
            continue
        target = m["target"]

        # Skip targets that don't contain an entity.field separator
        # (e.g. "skip", "ignore", or frontend names that weren't translated)
        if "." not in target:
            continue

        value = str(value).strip() if value else None
        if not value:
            continue

        transform = m.get("transform")
        entity, field = target.split(".", 1)

        if transform == "extract_domain":
            value = extract_domain(value)
        elif transform == "normalize_enum":
            value = normalize_enum(field, value)

        # Route custom.* fields to _custom_fields sub-dict
        if field.startswith("custom."):
            custom_key = field.split(".", 1)[1]
            bucket = contact if entity == "contact" else company
            bucket.setdefault("_custom_fields", {})[custom_key] = value
        elif entity == "contact":
            # Sanitize enum fields before storing (catches values not handled
            # by normalize_enum transform, e.g. free-text "Event Fest 2025")
            if field in ENUM_VALID_VALUES:
                custom_bucket = contact.setdefault("_custom_fields", {})
                value = sanitize_enum_value(field, value, custom_bucket)
            if value is not None:
                contact[field] = value
        else:
            if field in ENUM_VALID_VALUES:
                custom_bucket = company.setdefault("_custom_fields", {})
                value = sanitize_enum_value(field, value, custom_bucket)
            if value is not None:
                company[field] = value

    # Validate and fix company name (catch dates, numbers, garbage)
    if "name" in company:
        company["name"] = validate_and_fix_company(
            company["name"], email=contact.get("email_address")
        )

    # Validate and fix company name (catch dates, numbers, garbage)
    if "name" in company:
        company["name"] = validate_and_fix_company(
            company["name"], email=contact.get("email_address")
        )

    return {"contact": contact, "company": company}
