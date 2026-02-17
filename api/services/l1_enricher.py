"""L1 Company Profile Enrichment via Perplexity sonar API.

Replaces the n8n L1 webhook with native Python for better control,
testability, and cost visibility. After enrichment, companies get
status='triage_passed' (clean) or 'needs_review' (QC flags).
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from decimal import Decimal

import requests
from flask import current_app
from sqlalchemy import text

from ..models import db

# Import llm_logger functions — uses existing pricing if perplexity entries
# are present, otherwise falls back to wildcard pricing
try:
    from .llm_logger import compute_cost, log_llm_usage
except ImportError:
    compute_cost = None
    log_llm_usage = None

logger = logging.getLogger(__name__)

PERPLEXITY_MODEL = "sonar"
PERPLEXITY_MAX_TOKENS = 600
PERPLEXITY_TEMPERATURE = 0.1

# Free-mail domains to skip during domain resolution
FREE_MAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com",
    "aol.com", "icloud.com", "mail.com", "protonmail.com", "proton.me",
    "zoho.com", "yandex.com", "gmx.com", "gmx.de", "web.de",
    "fastmail.com", "tutanota.com",
}

SYSTEM_PROMPT = """You are a B2B sales qualification research assistant. Your task is to gather accurate, verifiable company information.

Source priority (highest to lowest):
1. Official company filings (annual reports, registry entries)
2. Company website (about page, careers, press releases)
3. Third-party business databases (Crunchbase, LinkedIn, Bloomberg)
4. News articles and press coverage

Rules:
- Revenue/employee ratio above EUR 500K per employee should be flagged
- If you cannot verify a data point, use "unverified" — NEVER guess
- For revenue, prefer the most recent fiscal year available
- For employees, prefer LinkedIn headcount or official filings
- Return ONLY valid JSON, no markdown formatting"""

USER_PROMPT_TEMPLATE = """Research the following company and return a JSON object with exactly these fields:

Company: {company_name}
{domain_line}
{contacts_section}
{claims_section}

Return this exact JSON structure (use ONLY the listed enum values — no free text for constrained fields):
{{
  "company_name": "Official company name as found in research",
  "summary": "2-3 sentence description of what the company does",
  "b2b": true/false or null if unclear,
  "hq": "City, Country",
  "markets": ["list", "of", "markets"],
  "founded": "YYYY or null",
  "ownership": "Public|Private|Family-owned|PE-backed (name)|VC-backed|Government|Cooperative|Unknown",
  "industry": "EXACTLY ONE OF: software_saas|it|professional_services|financial_services|healthcare|pharma_biotech|manufacturing|automotive|aerospace_defense|retail|hospitality|media|energy|telecom|transport|construction|real_estate|agriculture|education|public_sector|other",
  "business_model": "EXACTLY ONE OF: manufacturer|distributor|service_provider|saas|platform|other",
  "revenue_eur_m": "Annual revenue in EUR millions (number) or 'unverified'",
  "revenue_year": "YYYY of the revenue figure",
  "revenue_source": "Where the revenue figure comes from",
  "employees": "Headcount (number) or 'unverified'",
  "employees_source": "Where the headcount comes from",
  "confidence": 0.0 to 1.0,
  "flags": ["list of any concerns or data quality issues"]
}}"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def enrich_l1(company_id, tenant_id=None, previous_data=None):
    """Run L1 enrichment for a single company.

    Args:
        company_id: UUID string of the company
        tenant_id: UUID string of the tenant (optional, read from company if not given)
        previous_data: dict of prior enrichment fields for re-enrichment context

    Returns:
        dict with enrichment_cost_usd and qc_flags
    """
    start_time = time.time()

    # 1. Read company from PG
    row = db.session.execute(
        text("""
            SELECT c.id, c.tenant_id, c.name, c.domain, c.industry,
                   c.company_size, c.verified_revenue_eur_m
            FROM companies c
            WHERE c.id = :id
        """),
        {"id": str(company_id)},
    ).fetchone()

    if not row:
        return {"enrichment_cost_usd": 0, "qc_flags": ["company_not_found"]}

    company_id = str(row[0])
    tenant_id = tenant_id or str(row[1])
    company_name = row[2]
    domain = row[3]
    existing_industry = row[4]
    existing_size = row[5]
    existing_revenue = float(row[6]) if row[6] else None

    # 2. Resolve domain and gather contact context
    contact_linkedin_urls = _get_contact_linkedin_urls(company_id, limit=3)
    if not domain:
        domain = _resolve_domain(company_id)

    # 3. Call Perplexity
    try:
        raw_response, usage = _call_perplexity(company_name, domain,
                                                existing_industry, existing_size,
                                                existing_revenue,
                                                contact_linkedin_urls)
    except Exception as e:
        logger.error("Perplexity API error for company %s: %s", company_id, e)
        _set_company_status(company_id, "enrichment_failed",
                            error_message=str(e)[:500])
        return {"enrichment_cost_usd": 0, "qc_flags": ["api_error"]}

    # 4. Parse response
    research = _parse_research_json(raw_response)
    if research is None:
        logger.warning("Failed to parse Perplexity response for company %s", company_id)
        _set_company_status(company_id, "enrichment_failed",
                            error_message="Failed to parse research response")
        return {"enrichment_cost_usd": 0, "qc_flags": ["parse_error"]}

    # 5. Map fields
    mapped = _map_fields(research)

    # 6. QC validation
    qc_flags = _validate_research(research, company_name)

    # 7. Compute cost
    duration_ms = int((time.time() - start_time) * 1000)
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = Decimal("0")
    if compute_cost:
        cost = compute_cost("perplexity", PERPLEXITY_MODEL, input_tokens, output_tokens)
    # Fallback if compute_cost unavailable or returned 0 (no pricing entry)
    if cost == 0 and (input_tokens + output_tokens) > 0:
        # $1/1M tokens for both input and output (sonar pricing)
        cost = (Decimal(str(input_tokens)) + Decimal(str(output_tokens))) / Decimal("1000000")
    cost_float = float(cost)

    # 8. Determine status
    if qc_flags:
        status = "needs_review"
        error_message = json.dumps(qc_flags)
        quality_score = max(0, 100 - len(qc_flags) * 15)
    else:
        status = "triage_passed"
        error_message = None
        quality_score = 100

    confidence_score = _parse_confidence(research.get("confidence"))

    # 9. UPDATE company
    _update_company(company_id, status, mapped, cost_float, error_message)

    # 10. INSERT research_asset (raw SQL — table may not exist in tests)
    _insert_research_asset(
        tenant_id, company_id, PERPLEXITY_MODEL, cost_float,
        research, confidence_score, quality_score,
    )

    # 11. Log LLM usage
    if log_llm_usage:
        log_llm_usage(
            tenant_id=tenant_id,
            operation="l1_enrichment",
            model=PERPLEXITY_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider="perplexity",
            duration_ms=duration_ms,
            metadata={"company_id": company_id, "company_name": company_name},
        )

    db.session.commit()

    return {"enrichment_cost_usd": cost_float, "qc_flags": qc_flags}


# ---------------------------------------------------------------------------
# Domain resolution
# ---------------------------------------------------------------------------

def _resolve_domain(company_id):
    """Try to resolve a company domain from contact email addresses.

    Returns domain string or None.
    """
    rows = db.session.execute(
        text("""
            SELECT DISTINCT email_address
            FROM contacts
            WHERE company_id = :id AND email_address LIKE '%%@%%'
        """),
        {"id": str(company_id)},
    ).fetchall()

    for row in rows:
        email = row[0]
        if not email or "@" not in email:
            continue
        d = email.split("@", 1)[1].strip().lower()
        if d and d not in FREE_MAIL_DOMAINS:
            # Update company domain
            db.session.execute(
                text("UPDATE companies SET domain = :d WHERE id = :id"),
                {"d": d, "id": str(company_id)},
            )
            return d

    return None


def _get_contact_linkedin_urls(company_id, limit=3):
    """Fetch LinkedIn profile URLs for contacts linked to this company.

    Returns list of (name, linkedin_url) tuples (up to limit).
    """
    rows = db.session.execute(
        text("""
            SELECT first_name, last_name, job_title, linkedin_url
            FROM contacts
            WHERE company_id = :id AND linkedin_url IS NOT NULL AND linkedin_url != ''
            LIMIT :lim
        """),
        {"id": str(company_id), "lim": limit},
    ).fetchall()

    results = []
    for row in rows:
        name_parts = [row[0] or "", row[1] or ""]
        name = " ".join(p for p in name_parts if p).strip() or "Unknown"
        title = row[2] or ""
        url = row[3]
        results.append((name, title, url))
    return results


# ---------------------------------------------------------------------------
# Perplexity API call
# ---------------------------------------------------------------------------

def _call_perplexity(company_name, domain, existing_industry, existing_size,
                     existing_revenue, contact_linkedin_urls=None):
    """Call Perplexity sonar API for company research.

    Returns:
        tuple of (content_string, usage_dict)
    """
    api_key = current_app.config.get("PERPLEXITY_API_KEY", "")
    base_url = current_app.config.get("PERPLEXITY_BASE_URL", "https://api.perplexity.ai")

    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY not configured")

    # Build user prompt
    domain_line = f"Domain: {domain}" if domain else "Domain: unknown"

    # Contact LinkedIn context
    contacts_section = ""
    if contact_linkedin_urls:
        lines = []
        for name, title, url in contact_linkedin_urls:
            label = f"{name} ({title})" if title else name
            lines.append(f"- {label}: {url}")
        contacts_section = "Known employees at this company:\n" + "\n".join(lines)

    claims = []
    if existing_industry:
        claims.append(f"Claimed industry: {existing_industry}")
    if existing_size:
        claims.append(f"Claimed size: {existing_size}")
    if existing_revenue:
        claims.append(f"Claimed revenue: EUR {existing_revenue}M")

    claims_section = "Existing claims to verify:\n" + "\n".join(f"- {c}" for c in claims) if claims else ""

    # Build previous data section for re-enrichment
    previous_section = ""
    if previous_data:
        prev_lines = []
        for k, v in previous_data.items():
            if v is not None and v != "":
                prev_lines.append(f"- {k}: {v}")
        if prev_lines:
            previous_section = (
                "\n\nPrevious enrichment data (validate, correct errors, and extend "
                "with new findings — do not discard valid data):\n"
                + "\n".join(prev_lines)
            )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        company_name=company_name,
        domain_line=domain_line,
        contacts_section=contacts_section,
        claims_section=claims_section,
    ) + previous_section

    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": PERPLEXITY_MAX_TOKENS,
        "temperature": PERPLEXITY_TEMPERATURE,
        "search_recency_filter": "month",
    }

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    # Perplexity uses prompt_tokens / completion_tokens
    token_usage = {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }

    return content, token_usage


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_research_json(content):
    """Parse the JSON response from Perplexity, stripping markdown fences if present.

    Returns dict or None on failure.
    """
    if not content:
        return None

    text_content = content.strip()

    # Strip markdown code fences
    if text_content.startswith("```"):
        lines = text_content.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text_content = "\n".join(lines).strip()

    try:
        return json.loads(text_content)
    except (json.JSONDecodeError, ValueError):
        # Try to find JSON object in the text
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text_content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                pass
        return None


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

def _map_fields(research):
    """Map Perplexity research JSON fields to company column values.

    Returns dict of column_name -> value.
    """
    mapped = {}

    # summary
    if research.get("summary"):
        mapped["summary"] = str(research["summary"])[:2000]

    # hq → hq_city, hq_country, geo_region
    hq = research.get("hq")
    if hq and isinstance(hq, str) and "," in hq:
        parts = hq.rsplit(",", 1)
        mapped["hq_city"] = parts[0].strip()
        mapped["hq_country"] = parts[1].strip()
        mapped["geo_region"] = _derive_geo_region(parts[1].strip())
    elif hq and isinstance(hq, str):
        mapped["hq_country"] = hq.strip()
        mapped["geo_region"] = _derive_geo_region(hq.strip())

    # ownership_type
    ownership = research.get("ownership")
    if ownership:
        mapped["ownership_type"] = _map_ownership(ownership)

    # industry
    industry = research.get("industry")
    if industry:
        mapped["industry"] = _map_industry(industry)

    # business_type
    bm = research.get("business_model")
    if bm:
        mapped["business_type"] = _map_business_type(bm)

    # revenue
    revenue = _parse_revenue(research.get("revenue_eur_m"))
    if revenue is not None:
        mapped["verified_revenue_eur_m"] = revenue
        mapped["revenue_range"] = _revenue_to_bucket(revenue)

    # employees
    employees = _parse_employees(research.get("employees"))
    if employees is not None:
        mapped["verified_employees"] = employees
        mapped["company_size"] = _employees_to_bucket(employees)

    # b2b → business_model
    b2b = research.get("b2b")
    if b2b is True:
        mapped["business_model"] = "b2b"
    elif b2b is False:
        mapped["business_model"] = "b2c"

    return mapped


# ---------------------------------------------------------------------------
# Helper functions (ported from n8n JS triage code)
# ---------------------------------------------------------------------------

def _parse_revenue(raw):
    """Parse revenue value from various formats.

    Handles: "42", "42M", "1.5 billion", "unverified", None → float or None
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    s = str(raw).strip().lower()
    if not s or s in ("unverified", "unknown", "n/a", "null", "none"):
        return None

    # Remove currency symbols and "eur"
    s = re.sub(r'[€$£]', '', s)
    s = re.sub(r'\beur\b', '', s, flags=re.IGNORECASE).strip()

    # Handle "billion"
    if "billion" in s:
        num = re.search(r'[\d,.]+', s)
        if num:
            return float(num.group().replace(",", "")) * 1000
        return None

    # Handle "million" or "m"
    if "million" in s or s.endswith("m"):
        s = re.sub(r'million|m$', '', s).strip()

    # Extract number
    num = re.search(r'[\d,.]+', s)
    if num:
        try:
            return float(num.group().replace(",", ""))
        except ValueError:
            return None

    return None


def _parse_employees(raw):
    """Parse employee count from various formats.

    Handles: "500", "200-300", "1,234", "unverified" → int or None
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)

    s = str(raw).strip().lower()
    if not s or s in ("unverified", "unknown", "n/a", "null", "none"):
        return None

    # Handle ranges like "200-300" — take midpoint
    range_match = re.match(r'([\d,]+)\s*[-–]\s*([\d,]+)', s)
    if range_match:
        low = int(range_match.group(1).replace(",", ""))
        high = int(range_match.group(2).replace(",", ""))
        return (low + high) // 2

    # Handle "~500", "approx 500", "about 500"
    s = re.sub(r'^[~≈]|^(approx\.?|about|around|roughly)\s*', '', s).strip()

    # Handle "1,000+" or "500+"
    s = re.sub(r'\+$', '', s).strip()

    # Extract number
    num = re.search(r'[\d,]+', s)
    if num:
        try:
            return int(num.group().replace(",", ""))
        except ValueError:
            return None

    return None


def _derive_geo_region(country_str):
    """Map country name to geo_region enum value."""
    if not country_str:
        return None

    c = country_str.strip().lower()

    region_map = {
        # DACH
        "germany": "dach", "deutschland": "dach", "austria": "dach",
        "österreich": "dach", "switzerland": "dach", "schweiz": "dach",
        "liechtenstein": "dach",
        # Nordics
        "sweden": "nordics", "norway": "nordics", "denmark": "nordics",
        "finland": "nordics", "iceland": "nordics",
        # CEE
        "czech republic": "cee", "czechia": "cee", "poland": "cee",
        "hungary": "cee", "slovakia": "cee", "romania": "cee",
        "bulgaria": "cee", "croatia": "cee", "slovenia": "cee",
        "serbia": "cee", "estonia": "cee", "latvia": "cee",
        "lithuania": "cee",
        # Benelux
        "netherlands": "benelux", "belgium": "benelux", "luxembourg": "benelux",
        # UK/IE
        "uk": "uk_ie", "united kingdom": "uk_ie", "ireland": "uk_ie",
        "england": "uk_ie", "scotland": "uk_ie", "wales": "uk_ie",
        # Southern Europe
        "spain": "southern_europe", "italy": "southern_europe",
        "portugal": "southern_europe", "greece": "southern_europe",
        # France
        "france": "france",
        # North America
        "us": "north_america", "usa": "north_america",
        "united states": "north_america", "canada": "north_america",
    }

    return region_map.get(c)


def _map_ownership(raw):
    """Map ownership description to enum value."""
    if not raw:
        return None

    s = str(raw).strip().lower()

    if "family" in s:
        return "family_owned"
    if "pe" in s or "private equity" in s:
        return "pe_backed"
    if "vc" in s or "venture" in s:
        return "vc_backed"
    if "public" in s or "listed" in s:
        return "public"
    if "government" in s or "state" in s:
        return "state_owned"
    if "cooperative" in s or "coop" in s:
        return "other"
    if "bootstrap" in s:
        return "bootstrapped"
    if "private" in s:
        return "bootstrapped"

    return None


def _map_industry(raw):
    """Map industry description to an industry_enum value."""
    if not raw:
        return None
    s = str(raw).strip().lower()

    VALID_INDUSTRIES = {
        "software_saas", "it", "professional_services", "financial_services",
        "healthcare", "pharma_biotech", "manufacturing", "automotive",
        "aerospace_defense", "retail", "hospitality", "media", "energy",
        "telecom", "transport", "construction", "real_estate", "agriculture",
        "education", "public_sector", "other",
    }
    # Direct match
    if s in VALID_INDUSTRIES:
        return s

    # Keyword mapping — more specific patterns first to avoid false matches
    keywords = {
        "pharma_biotech": ["pharma", "biotech", "life science", "drug", "clinical trial"],
        "aerospace_defense": ["aerospace", "defense", "defence", "military", "space", "satellite", "avionics"],
        "automotive": ["automotive", "car ", "vehicle", "motor", "auto parts", "ev charging"],
        "software_saas": ["software", "saas", "cloud", "app", "digital platform"],
        "it": ["it ", "information tech", "cyber", "data center", "hosting", "tech"],
        "professional_services": ["consult", "advisory", "legal", "accounting", "audit", "staffing", "recruitment"],
        "financial_services": ["financ", "bank", "insur", "invest", "fintech", "payment"],
        "healthcare": ["health", "medical", "hospital", "clinic", "dental", "care"],
        "real_estate": ["real estate", "property", "reit", "commercial space", "office space"],
        "manufacturing": ["manufactur", "industrial", "machinery", "production", "factory", "automation"],
        "retail": ["retail", "e-commerce", "ecommerce", "shop", "consumer goods", "fashion"],
        "hospitality": ["hotel", "restaurant", "hospitality", "tourism", "travel", "food service", "catering"],
        "media": ["media", "entertainment", "broadcast", "publishing", "gaming", "advertising"],
        "energy": ["energy", "oil", "gas", "solar", "wind", "renewable", "power", "utility", "waste-to-energy"],
        "agriculture": ["agricult", "farming", "agri", "food production", "crop", "livestock", "agtech"],
        "telecom": ["telecom", "mobile", "wireless", "network operator"],
        "transport": ["transport", "logistics", "shipping", "freight", "aviation", "rail", "maritime"],
        "construction": ["construct", "building", "architect", "civil engineer"],
        "education": ["education", "university", "school", "training", "e-learning", "edtech"],
        "public_sector": ["government", "public sector", "ngo", "non-profit", "municipal"],
    }
    for enum_val, kws in keywords.items():
        for kw in kws:
            if kw in s:
                return enum_val

    return "other"


def _map_business_type(raw):
    """Map business model/type description to business_type enum value."""
    if not raw:
        return None

    s = str(raw).strip().lower()

    VALID_TYPES = {"manufacturer", "distributor", "service_provider", "saas", "platform", "other"}
    if s in VALID_TYPES:
        return s

    type_map = {
        "saas": "saas",
        "software": "saas",
        "manufactur": "manufacturer",
        "service": "service_provider",
        "consult": "service_provider",
        "distribut": "distributor",
        "wholesale": "distributor",
        "platform": "platform",
        "marketplace": "platform",
    }
    for key, value in type_map.items():
        if key in s:
            return value

    return "other"


def _revenue_to_bucket(rev_m):
    """Map revenue in EUR millions to a bucket."""
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


def _employees_to_bucket(emp):
    """Map employee count to a size bucket."""
    if emp is None:
        return None
    if emp < 10:
        return "micro"
    if emp < 50:
        return "startup"
    if emp < 200:
        return "smb"
    if emp < 1000:
        return "mid_market"
    return "enterprise"


def _parse_confidence(raw):
    """Parse confidence score from various formats → float 0-1 or None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if 0 <= float(raw) <= 1 else None

    s = str(raw).strip().lower()
    if s in ("low", "very low"):
        return 0.3
    if s in ("medium", "moderate"):
        return 0.6
    if s in ("high", "very high"):
        return 0.9

    try:
        v = float(s)
        return v if 0 <= v <= 1 else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# QC validation
# ---------------------------------------------------------------------------

def _validate_research(research, original_name):
    """Run QC checks on parsed research. Returns list of flag strings."""
    flags = []

    # Name mismatch
    research_name = research.get("company_name", "")
    if research_name and original_name:
        similarity = _name_similarity(original_name, research_name)
        if similarity < 0.6:
            flags.append("name_mismatch")

    # Missing critical fields (need at least 4 of 5)
    critical_fields = ["summary", "hq", "industry", "employees", "revenue_eur_m"]
    populated = sum(1 for f in critical_fields
                    if research.get(f) and str(research.get(f)).lower()
                    not in ("unverified", "unknown", "null", "none", "n/a"))
    if populated < 4:
        flags.append("incomplete_research")

    # Revenue sanity
    revenue = _parse_revenue(research.get("revenue_eur_m"))
    employees = _parse_employees(research.get("employees"))
    if revenue is not None:
        if revenue > 50000:  # >50B EUR
            flags.append("revenue_implausible")
        elif employees and employees > 0 and revenue > 0:
            ratio = (revenue * 1_000_000) / employees  # Convert M to absolute
            if ratio > 500_000:
                flags.append("revenue_implausible")

    # Employee sanity
    if employees is not None:
        if employees > 500_000 or employees < 0:
            flags.append("employees_implausible")

    # Low confidence
    confidence = _parse_confidence(research.get("confidence"))
    if confidence is not None and confidence < 0.4:
        flags.append("low_confidence")

    # B2B unclear
    b2b = research.get("b2b")
    if b2b is None:
        flags.append("b2b_unclear")

    # Summary too short
    summary = research.get("summary", "")
    if isinstance(summary, str) and len(summary.strip()) < 30:
        flags.append("summary_too_short")

    # Merge Perplexity's own flags — look for high-severity indicators
    pplx_flags = research.get("flags", [])
    if isinstance(pplx_flags, list):
        for pf in pplx_flags:
            pf_lower = str(pf).lower()
            if any(kw in pf_lower for kw in (
                "not found", "no matching", "non-existent", "defunct",
                "discrepancy", "mismatch", "conflicting",
            )):
                flags.append("source_warning")
                break  # One flag is enough

    return flags


def _name_similarity(name_a, name_b):
    """Simple bigram (Dice coefficient) similarity between two names."""
    if not name_a or not name_b:
        return 0.0

    a = name_a.strip().lower()
    b = name_b.strip().lower()

    if a == b:
        return 1.0

    # Strip common suffixes
    for suffix in (
        " inc", " inc.", " incorporated", " llc", " ltd", " ltd.",
        " limited", " gmbh", " ag", " sa", " se", " plc",
        " corp", " corp.", " corporation", " company",
        " co.", " s.r.o.", " a.s.", " a/s", " oy", " ab",
        " sp. z o.o.", " spol. s r.o.", " s.a.", " s.p.a.",
        " b.v.", " n.v.", " pty", " pty.",
    ):
        a = a.removesuffix(suffix)
        b = b.removesuffix(suffix)

    a = a.strip()
    b = b.strip()

    if a == b:
        return 1.0

    if not a or not b:
        return 0.0

    a_bigrams = set(a[i:i+2] for i in range(len(a) - 1))
    b_bigrams = set(b[i:i+2] for i in range(len(b) - 1))

    if not a_bigrams or not b_bigrams:
        return 0.0

    intersection = a_bigrams & b_bigrams
    return 2 * len(intersection) / (len(a_bigrams) + len(b_bigrams))


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def _insert_research_asset(tenant_id, company_id, model, cost_float,
                           research, confidence_score, quality_score):
    """Insert research_asset row via raw SQL (avoids model import)."""
    try:
        research_json = json.dumps(research) if isinstance(research, dict) else "{}"
        db.session.execute(
            text("""
                INSERT INTO research_assets (
                    tenant_id, entity_type, entity_id, name, tool_name,
                    cost_usd, research_data, confidence_score, quality_score
                ) VALUES (
                    :tenant_id, 'company', :entity_id, 'l1_perplexity_research',
                    :tool_name, :cost_usd, :research_data,
                    :confidence_score, :quality_score
                )
            """),
            {
                "tenant_id": str(tenant_id),
                "entity_id": str(company_id),
                "tool_name": f"perplexity/{model}",
                "cost_usd": cost_float,
                "research_data": research_json,
                "confidence_score": confidence_score,
                "quality_score": quality_score,
            },
        )
    except Exception as e:
        # Table may not exist yet (e.g. during tests before migration)
        logger.warning("Failed to insert research_asset: %s", e)


def _set_company_status(company_id, status, error_message=None):
    """Update company status and optionally set error_message."""
    params = {"id": str(company_id), "status": status}
    if error_message:
        db.session.execute(
            text("UPDATE companies SET status = :status, error_message = :err, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {**params, "err": error_message},
        )
    else:
        db.session.execute(
            text("UPDATE companies SET status = :status, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            params,
        )
    db.session.commit()


def _update_company(company_id, status, mapped, cost, error_message):
    """Update company with enrichment results."""
    set_clauses = ["status = :status", "enrichment_cost_usd = enrichment_cost_usd + :cost",
                   "updated_at = CURRENT_TIMESTAMP"]
    params = {"id": str(company_id), "status": status, "cost": cost}

    if error_message:
        set_clauses.append("error_message = :err")
        params["err"] = error_message
    else:
        set_clauses.append("error_message = NULL")

    # Add mapped fields
    for col, val in mapped.items():
        param_key = f"m_{col}"
        set_clauses.append(f"{col} = :{param_key}")
        params[param_key] = val

    sql = f"UPDATE companies SET {', '.join(set_clauses)} WHERE id = :id"
    db.session.execute(text(sql), params)
