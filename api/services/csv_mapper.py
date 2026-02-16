"""AI-powered CSV column mapping using Claude API.

Takes CSV headers + sample rows and returns a structured mapping
to Contact/Company fields with confidence scores and transforms.
"""

import json
import os

TARGET_FIELDS = {
    "contact": [
        "full_name", "job_title", "email_address", "linkedin_url",
        "phone_number", "location_city", "location_country",
        "seniority_level", "department", "contact_source", "language",
    ],
    "company": [
        "name", "domain", "industry", "hq_city", "hq_country",
        "company_size", "business_model",
    ],
}

# Reverse maps for enum normalization (display value → DB value)
ENUM_FIELDS = {
    "seniority_level": {
        "c-level": "c_level", "c level": "c_level", "vp": "vp",
        "vice president": "vp", "director": "director", "manager": "manager",
        "individual contributor": "individual_contributor", "ic": "individual_contributor",
        "founder": "founder", "other": "other",
    },
    "department": {
        "executive": "executive", "engineering": "engineering", "product": "product",
        "sales": "sales", "marketing": "marketing", "customer success": "customer_success",
        "finance": "finance", "hr": "hr", "human resources": "hr",
        "operations": "operations", "other": "other",
    },
    "contact_source": {
        "inbound": "inbound", "outbound": "outbound", "referral": "referral",
        "event": "event", "social": "social", "other": "other",
    },
    "language": {
        "english": "en", "en": "en", "german": "de", "de": "de",
        "dutch": "nl", "nl": "nl", "czech": "cs", "cs": "cs",
    },
    "industry": {
        "software": "software_saas", "saas": "software_saas", "software / saas": "software_saas",
        "it": "it", "professional services": "professional_services",
        "financial services": "financial_services", "healthcare": "healthcare",
        "manufacturing": "manufacturing", "retail": "retail", "media": "media",
        "energy": "energy", "telecom": "telecom", "transport": "transport",
        "construction": "construction", "education": "education",
        "public sector": "public_sector", "other": "other",
    },
    "company_size": {
        "micro": "micro", "startup": "startup", "smb": "smb",
        "mid-market": "mid_market", "mid market": "mid_market",
        "enterprise": "enterprise",
    },
    "business_model": {
        "b2b": "b2b", "b2c": "b2c", "marketplace": "marketplace",
        "government": "gov", "gov": "gov", "non-profit": "non_profit",
        "nonprofit": "non_profit", "hybrid": "hybrid",
    },
}

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
    - "combine_first_last" (for first_name column that should combine with last_name into full_name)
    - "extract_domain" (for company URL/website → domain)
    - "normalize_enum" (for free text → DB enum value)
  - "suggested_custom_field": (optional) if target is null and the column has useful data, suggest a new
    custom field: {{"entity_type": "contact"|"company", "field_key": "snake_case_key",
    "field_label": "Display Name", "field_type": "text"|"number"|"url"|"email"|"date"|"select"}}
- "warnings": array of strings for any issues (missing required fields, ambiguous mappings, etc.)
- "combine_columns": array of objects describing columns to combine, each with:
  - "sources": array of csv_header names to combine
  - "target": the target field
  - "separator": string to join with (e.g. " ")

Rules:
- full_name is required. If you see separate first_name/last_name columns, mark the first one with
  transform "combine_first_last" and map both to contact.full_name in combine_columns.
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
        entry = f"contact.custom.{d['field_key']}" if d["entity_type"] == "contact" \
            else f"company.custom.{d['field_key']}"
        label = d.get("field_label", d["field_key"])
        ft = d.get("field_type", "text")
        contact_custom.append(entry) if d["entity_type"] == "contact" \
            else company_custom.append(entry)

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

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    return json.loads(text)


def normalize_enum(field_name, value):
    """Normalize a free-text value to a DB enum value.

    Returns the DB enum value or the original value if no match.
    """
    if not value or field_name not in ENUM_FIELDS:
        return value
    lookup = ENUM_FIELDS[field_name]
    normalized = value.strip().lower()
    return lookup.get(normalized, value)


def extract_domain(url):
    """Extract domain from a URL (strip protocol, www, trailing path)."""
    if not url:
        return None
    url = url.strip().lower()
    # Strip protocol
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
            break
    # Strip www.
    if url.startswith("www."):
        url = url[4:]
    # Strip trailing path/query
    url = url.split("/")[0].split("?")[0].split("#")[0]
    return url if url else None


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
    combine_columns = mapping_result.get("combine_columns", [])

    # Handle combine_columns first (e.g. first_name + last_name → full_name)
    combined_targets = set()
    for combo in combine_columns:
        sources = combo["sources"]
        target = combo["target"]
        separator = combo.get("separator", " ")
        parts = [str(row.get(s, "")).strip() for s in sources if row.get(s)]
        if parts:
            value = separator.join(parts)
            entity, field = target.split(".", 1)
            if entity == "contact":
                contact[field] = value
            else:
                company[field] = value
            combined_targets.add(target)

    # Apply individual mappings (skip columns already handled by combine)
    for header, value in row.items():
        m = mappings.get(header)
        if not m or not m.get("target"):
            continue
        target = m["target"]
        if target in combined_targets:
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
            contact[field] = value
        else:
            company[field] = value

    return {"contact": contact, "company": company}
