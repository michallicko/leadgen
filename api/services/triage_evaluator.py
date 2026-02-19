"""Rules-based triage evaluation for post-L1 company filtering.

Evaluates a company against configurable rules to determine whether
it should proceed to L2 enrichment or be disqualified. Zero-cost gate
stage — no API calls, pure rule matching.

Usage:
    from api.services.triage_evaluator import evaluate_triage, DEFAULT_RULES

    result = evaluate_triage(company_data, rules)
    # result = {"passed": True, "reasons": []}
    # result = {"passed": False, "reasons": ["Tier tier_3 not in allowlist"]}
"""

import logging

logger = logging.getLogger(__name__)

# Default triage rules — conservative, lets most through
DEFAULT_RULES = {
    "tier_allowlist": [],           # empty = no tier filter
    "tier_blocklist": [],           # these tiers are disqualified
    "industry_blocklist": [],       # disqualify these industries
    "industry_allowlist": [],       # if set, ONLY these industries pass
    "geo_allowlist": [],            # if set, only these regions pass
    "min_revenue_eur_m": None,      # minimum annual revenue (EUR millions)
    "min_employees": None,          # minimum employee count
    "require_b2b": True,            # require B2B classification
    "max_qc_flags": 3,             # max L1 QC flags to pass
}


def evaluate_triage(company_data, rules):
    """Evaluate a company against triage rules.

    Args:
        company_data: dict with keys: tier, industry, geo_region,
            revenue_eur_m, employees, is_b2b, qc_flags
        rules: dict of triage rules (see DEFAULT_RULES for schema)

    Returns:
        dict with 'passed' (bool) and 'reasons' (list of strings)
    """
    reasons = []

    # Tier allowlist
    tier_allowlist = rules.get("tier_allowlist")
    if tier_allowlist:
        tier = company_data.get("tier")
        if tier not in tier_allowlist:
            reasons.append("Tier {} not in allowlist {}".format(tier, tier_allowlist))

    # Tier blocklist
    tier_blocklist = rules.get("tier_blocklist")
    if tier_blocklist:
        tier = company_data.get("tier")
        if tier in tier_blocklist:
            reasons.append("Tier {} is blocklisted".format(tier))

    # Industry blocklist
    industry_blocklist = rules.get("industry_blocklist")
    if industry_blocklist:
        industry = company_data.get("industry")
        if industry in industry_blocklist:
            reasons.append("Industry {} is blocklisted".format(industry))

    # Industry allowlist
    industry_allowlist = rules.get("industry_allowlist")
    if industry_allowlist:
        industry = company_data.get("industry")
        if industry not in industry_allowlist:
            reasons.append("Industry {} not in allowlist {}".format(
                industry, industry_allowlist))

    # Geo allowlist
    geo_allowlist = rules.get("geo_allowlist")
    if geo_allowlist:
        geo = company_data.get("geo_region")
        if geo not in geo_allowlist:
            reasons.append("Geo region {} not in allowlist {}".format(
                geo, geo_allowlist))

    # Min revenue
    min_revenue = rules.get("min_revenue_eur_m")
    if min_revenue is not None:
        revenue = company_data.get("revenue_eur_m")
        if revenue is None or revenue < min_revenue:
            reasons.append("Revenue {} below minimum {}".format(
                revenue, min_revenue))

    # Min employees
    min_employees = rules.get("min_employees")
    if min_employees is not None:
        employees = company_data.get("employees")
        if employees is None or employees < min_employees:
            reasons.append("Employees {} below minimum {}".format(
                employees, min_employees))

    # Require B2B
    if rules.get("require_b2b"):
        is_b2b = company_data.get("is_b2b")
        if not is_b2b:
            reasons.append("Company not classified as B2B")

    # Max QC flags
    max_qc_flags = rules.get("max_qc_flags")
    if max_qc_flags is not None:
        qc_flags = company_data.get("qc_flags") or []
        if len(qc_flags) > max_qc_flags:
            reasons.append("{} QC flags exceeds maximum {}".format(
                len(qc_flags), max_qc_flags))

    return {"passed": len(reasons) == 0, "reasons": reasons}
