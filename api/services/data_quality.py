"""BL-158: Data Quality service — surface contradictions and research gaps.

Compares L1 vs L2 enrichment data, registry data, and contact fields to
flag contradictions (e.g., different employee counts across sources) and
gaps (missing fields that should exist after a given enrichment stage).

Each indicator has:
- category: "contradiction" | "gap" | "warning"
- severity: "high" | "medium" | "low"
- field: the field name involved
- message: human-readable description
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from ..models import db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Expected fields per enrichment stage
# ---------------------------------------------------------------------------

EXPECTED_AFTER_L1 = [
    "summary",
    "industry",
    "hq_country",
    "company_size",
]

EXPECTED_AFTER_L2 = [
    "company_intel",
    "recent_news",
    "pain_hypothesis",
    "ai_opportunities",
]

EXPECTED_AFTER_PERSON = [
    "person_summary",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_jsonb(val):
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            return json.loads(val) if val else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return val


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _pct_diff(a, b):
    """Percentage difference between two numbers.  Returns None if either is missing."""
    if a is None or b is None:
        return None
    if a == 0 and b == 0:
        return 0.0
    denom = max(abs(a), abs(b))
    if denom == 0:
        return None
    return abs(a - b) / denom * 100


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def analyze_company_data_quality(company_id: str, tenant_id: str) -> dict:
    """Analyze data quality for a single company.

    Returns:
        {
            "company_id": str,
            "company_name": str,
            "score": int (0-100),
            "indicators": [{"category", "severity", "field", "message"}, ...],
            "enrichment_coverage": {"l1": bool, "l2": bool, "registry": bool, "person_count": int},
        }
    """
    indicators: list[dict] = []

    # Load company base data
    company = db.session.execute(
        text("""
            SELECT name, domain, hq_country, industry, company_size, summary,
                   verified_revenue_eur_m, verified_employees, status, tier,
                   data_quality_score
            FROM companies WHERE id = :id AND tenant_id = :tid
        """),
        {"id": company_id, "tid": tenant_id},
    ).fetchone()

    if not company:
        return {"error": "Company not found", "indicators": [], "score": 0}

    company_name = company[0]

    # Load L1 enrichment
    l1 = db.session.execute(
        text("""
            SELECT triage_notes, pre_score, raw_response, confidence,
                   quality_score, qc_flags
            FROM company_enrichment_l1 WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()

    # Load L2 enrichment
    l2 = db.session.execute(
        text("""
            SELECT company_intel, recent_news, ai_opportunities,
                   pain_hypothesis, key_products, customer_segments,
                   competitors, tech_stack, hiring_signals, digital_initiatives,
                   enrichment_cost_usd
            FROM company_enrichment_l2 WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()

    # Load registry (legal profile)
    registry = db.session.execute(
        text("""
            SELECT official_name, registration_status, date_established,
                   registered_address, address_city, match_confidence,
                   match_method, credibility_score, registration_country
            FROM company_legal_profile WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()

    # Load person enrichments count
    person_count = (
        db.session.execute(
            text("""
            SELECT COUNT(*) FROM contact_enrichment ce
            JOIN contacts ct ON ce.contact_id = ct.id
            WHERE ct.company_id = :id AND ct.tenant_id = :tid
        """),
            {"id": company_id, "tid": tenant_id},
        ).scalar()
        or 0
    )

    # Determine coverage
    has_l1 = l1 is not None
    has_l2 = l2 is not None
    has_registry = registry is not None

    enrichment_coverage = {
        "l1": has_l1,
        "l2": has_l2,
        "registry": has_registry,
        "person_count": person_count,
    }

    # ---------------------------------------------------------------
    # 1. Gap checks: missing fields after enrichment stages
    # ---------------------------------------------------------------
    if has_l1:
        for field in EXPECTED_AFTER_L1:
            # Map field to company column index
            col_map = {
                "summary": 5,
                "industry": 3,
                "hq_country": 2,
                "company_size": 4,
            }
            idx = col_map.get(field)
            if idx is not None and not company[idx]:
                indicators.append(
                    {
                        "category": "gap",
                        "severity": "medium",
                        "field": field,
                        "message": f"'{field}' is empty after L1 enrichment — research may have been incomplete.",
                    }
                )

    if has_l2:
        l2_col_map = {
            "company_intel": 0,
            "recent_news": 1,
            "ai_opportunities": 2,
            "pain_hypothesis": 3,
        }
        for field in EXPECTED_AFTER_L2:
            idx = l2_col_map.get(field)
            if idx is not None and not l2[idx]:
                indicators.append(
                    {
                        "category": "gap",
                        "severity": "medium",
                        "field": field,
                        "message": f"'{field}' is empty after L2 deep research — the AI may not have found relevant data.",
                    }
                )

    # ---------------------------------------------------------------
    # 2. Contradiction checks: L1 vs registry
    # ---------------------------------------------------------------
    if has_l1 and has_registry:
        # Country contradiction
        l1_country = company[2]  # hq_country from L1
        reg_country = registry[8]  # registration_country from registry
        if l1_country and reg_country:
            _COUNTRY_MAP = {
                "czech republic": "cz",
                "czechia": "cz",
                "cz": "cz",
                "norway": "no",
                "norge": "no",
                "no": "no",
                "finland": "fi",
                "suomi": "fi",
                "fi": "fi",
                "france": "fr",
                "fr": "fr",
                "germany": "de",
                "deutschland": "de",
                "de": "de",
            }
            l1_norm = _COUNTRY_MAP.get(
                l1_country.strip().lower(), l1_country.strip().lower()
            )
            reg_norm = _COUNTRY_MAP.get(
                reg_country.strip().lower(), reg_country.strip().lower()
            )
            if l1_norm != reg_norm:
                indicators.append(
                    {
                        "category": "contradiction",
                        "severity": "high",
                        "field": "hq_country",
                        "message": f"Country mismatch: L1 says '{l1_country}', registry says '{reg_country}'.",
                    }
                )

        # Name divergence
        if registry[0]:  # official_name
            from .qc_checker import name_similarity

            sim = name_similarity(company_name, registry[0])
            if sim < 0.5:
                indicators.append(
                    {
                        "category": "contradiction",
                        "severity": "medium",
                        "field": "name",
                        "message": f"Name divergence: '{company_name}' vs registry '{registry[0]}' (similarity {sim:.0%}).",
                    }
                )

        # Low registry confidence
        if registry[5] is not None:
            conf = _safe_float(registry[5])
            if conf is not None and conf < 0.7 and (registry[6] or "") != "ico_direct":
                indicators.append(
                    {
                        "category": "warning",
                        "severity": "medium",
                        "field": "registry_match",
                        "message": f"Registry match confidence is low ({conf:.0%}) — the matched entity may be wrong.",
                    }
                )

    # ---------------------------------------------------------------
    # 3. L1 QC flags surfacing
    # ---------------------------------------------------------------
    if has_l1 and l1[5]:  # qc_flags column
        qc_flags = _parse_jsonb(l1[5])
        if isinstance(qc_flags, list):
            for flag in qc_flags:
                if isinstance(flag, str):
                    indicators.append(
                        {
                            "category": "warning",
                            "severity": "low",
                            "field": "qc_flags",
                            "message": f"L1 QC flag: {flag}",
                        }
                    )

    # ---------------------------------------------------------------
    # 4. Missing enrichment stages
    # ---------------------------------------------------------------
    status = company[8]
    if status in ("triage_passed", "enriched_l2") and not has_l2:
        indicators.append(
            {
                "category": "gap",
                "severity": "high",
                "field": "l2_enrichment",
                "message": "Company passed triage but has no L2 deep research data.",
            }
        )

    if status == "enriched_l2" and person_count == 0:
        indicators.append(
            {
                "category": "gap",
                "severity": "medium",
                "field": "person_enrichment",
                "message": "Company is fully enriched at L2 but has no person-level enrichment for contacts.",
            }
        )

    # ---------------------------------------------------------------
    # 5. Compute score (0-100)
    # ---------------------------------------------------------------
    score = 100
    for ind in indicators:
        if ind["severity"] == "high":
            score -= 15
        elif ind["severity"] == "medium":
            score -= 8
        else:
            score -= 3
    score = max(0, min(100, score))

    return {
        "company_id": company_id,
        "company_name": company_name,
        "score": score,
        "indicators": indicators,
        "enrichment_coverage": enrichment_coverage,
    }


def analyze_batch_data_quality(tenant_id: str, tag_id: str, limit: int = 50) -> dict:
    """Analyze data quality across a batch (tag) of companies.

    Returns summary statistics and top issues.
    """
    rows = db.session.execute(
        text("""
            SELECT id FROM companies
            WHERE tenant_id = :tid AND tag_id = :tag_id
            ORDER BY name
            LIMIT :lim
        """),
        {"tid": tenant_id, "tag_id": tag_id, "lim": limit},
    ).fetchall()

    results = []
    total_score = 0
    all_indicators: list[dict] = []

    for row in rows:
        cid = str(row[0])
        analysis = analyze_company_data_quality(cid, tenant_id)
        if "error" not in analysis:
            results.append(
                {
                    "company_id": analysis["company_id"],
                    "company_name": analysis["company_name"],
                    "score": analysis["score"],
                    "indicator_count": len(analysis["indicators"]),
                    "enrichment_coverage": analysis["enrichment_coverage"],
                }
            )
            total_score += analysis["score"]
            all_indicators.extend(analysis["indicators"])

    # Aggregate: count by category and severity
    category_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    field_counts: dict[str, int] = {}

    for ind in all_indicators:
        cat = ind["category"]
        sev = ind["severity"]
        fld = ind["field"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        field_counts[fld] = field_counts.get(fld, 0) + 1

    # Top issues (most common fields)
    top_issues = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    avg_score = total_score / len(results) if results else 0

    return {
        "total_companies": len(results),
        "average_score": round(avg_score, 1),
        "by_category": category_counts,
        "by_severity": severity_counts,
        "top_issues": [{"field": f, "count": c} for f, c in top_issues],
        "companies": results,
    }
