"""QC (Quality Check) stage: end-of-pipeline field conflict detection.

Runs after all other enabled stages complete. Compares data across sources
(L1 research, registry, insolvency) and flags conflicts or anomalies.

Follows the enricher handler interface:
    run_qc(entity_id, tenant_id) -> {"enrichment_cost_usd": float, "qc_flags": list}
"""

import logging

from sqlalchemy import text

from api.models import db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name similarity (reused from l1_enricher — extracted here for cross-module use)
# ---------------------------------------------------------------------------

_LEGAL_SUFFIXES = (
    " inc", " inc.", " incorporated", " llc", " ltd", " ltd.",
    " limited", " gmbh", " ag", " sa", " se", " plc",
    " corp", " corp.", " corporation", " company",
    " co.", " s.r.o.", " a.s.", " a/s", " oy", " ab",
    " sp. z o.o.", " spol. s r.o.", " s.a.", " s.p.a.",
    " b.v.", " n.v.", " pty", " pty.",
)


def name_similarity(name_a, name_b):
    """Bigram (Dice coefficient) similarity between two names, stripping legal suffixes."""
    if not name_a or not name_b:
        return 0.0

    a = name_a.strip().lower()
    b = name_b.strip().lower()

    if a == b:
        return 1.0

    for suffix in _LEGAL_SUFFIXES:
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
# Thresholds
# ---------------------------------------------------------------------------

NAME_SIMILARITY_THRESHOLD = 0.5
REVENUE_CONFLICT_RATIO = 0.50   # >50% difference between sources
EMPLOYEE_CONFLICT_RATIO = 1.00  # >100% difference between sources


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_registry_name_mismatch(company_name, registry_rows):
    """Compare L1 company name against registry official_name(s)."""
    flags = []
    for reg in registry_rows:
        official = reg.get("official_name")
        country = reg.get("registry_country", "?")
        if not official:
            continue
        sim = name_similarity(company_name, official)
        if sim < NAME_SIMILARITY_THRESHOLD:
            flags.append(
                "registry_name_mismatch:%s:%.2f" % (country, sim)
            )
    return flags


def _check_hq_country_conflict(hq_country, registry_rows):
    """Compare L1 hq_country against registry country data."""
    if not hq_country:
        return []

    flags = []
    hq_lower = hq_country.strip().lower()

    # Normalize common country names to ISO codes
    country_map = {
        "czech republic": "cz", "czechia": "cz", "cz": "cz",
        "norway": "no", "norge": "no", "no": "no",
        "finland": "fi", "suomi": "fi", "fi": "fi",
        "france": "fr", "fr": "fr",
        "germany": "de", "deutschland": "de", "de": "de",
        "sweden": "se", "sverige": "se", "se": "se",
        "denmark": "dk", "danmark": "dk", "dk": "dk",
        "austria": "at", "osterreich": "at", "at": "at",
        "switzerland": "ch", "schweiz": "ch", "ch": "ch",
        "poland": "pl", "polska": "pl", "pl": "pl",
        "united kingdom": "gb", "uk": "gb", "gb": "gb",
        "united states": "us", "usa": "us", "us": "us",
        "netherlands": "nl", "nl": "nl",
    }
    hq_norm = country_map.get(hq_lower, hq_lower)

    for reg in registry_rows:
        reg_country = reg.get("registry_country", "")
        if not reg_country:
            continue
        reg_norm = country_map.get(reg_country.strip().lower(), reg_country.strip().lower())
        if hq_norm != reg_norm:
            flags.append(
                "hq_country_conflict:%s_vs_%s" % (hq_country, reg_country)
            )
    return flags


def _check_active_insolvency(insolvency_rows):
    """Flag companies with active insolvency proceedings."""
    flags = []
    for ins in insolvency_rows:
        if ins.get("has_insolvency") and ins.get("active_proceedings", 0) > 0:
            flags.append(
                "active_insolvency:%d_proceedings" % ins["active_proceedings"]
            )
    return flags


def _check_dissolved(registry_rows):
    """Flag companies marked as dissolved in registry data."""
    for reg in registry_rows:
        status = (reg.get("registration_status") or "").upper()
        if reg.get("date_dissolved") is not None:
            return ["company_dissolved"]
        if status in ("ZANIKLÝ", "VYMAZANÝ", "DISSOLVED", "INACTIVE"):
            return ["company_dissolved"]
    return []


def _check_data_completeness(company, has_l2, has_registry, completed_stages):
    """Flag missing expected data based on what stages were run."""
    flags = []

    # If L1 completed but critical fields still missing
    if "l1" in completed_stages:
        if not company.get("summary"):
            flags.append("missing_summary_after_l1")
        if not company.get("hq_country"):
            flags.append("missing_hq_after_l1")
        if not company.get("industry"):
            flags.append("missing_industry_after_l1")

    # If L2 completed but no L2 record exists
    if "l2" in completed_stages and not has_l2:
        flags.append("l2_completed_but_no_data")

    return flags


def _check_low_registry_confidence(registry_rows):
    """Flag registry matches with low confidence."""
    flags = []
    for reg in registry_rows:
        confidence = reg.get("match_confidence")
        method = reg.get("match_method", "")
        if confidence is not None and float(confidence) < 0.7 and method != "ico_direct":
            flags.append(
                "low_registry_confidence:%s:%.2f" % (
                    reg.get("registry_country", "?"), float(confidence)
                )
            )
    return flags


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_qc(entity_id, tenant_id):
    """Run QC checks for a company entity. Returns handler-compatible dict.

    Args:
        entity_id: company UUID
        tenant_id: tenant UUID

    Returns:
        {"enrichment_cost_usd": 0.0, "qc_flags": ["flag1", "flag2", ...]}
    """
    qc_flags = []

    # Load company data
    row = db.session.execute(
        text("""
            SELECT name, hq_country, hq_city, industry, summary,
                   verified_revenue_eur_m, verified_employees, status
            FROM companies WHERE id = :id AND tenant_id = :tid
        """),
        {"id": str(entity_id), "tid": str(tenant_id)},
    ).mappings().first()

    if not row:
        return {"enrichment_cost_usd": 0.0, "qc_flags": ["entity_not_found"]}

    company = dict(row)

    # Load registry data
    registry_rows = [
        dict(r) for r in db.session.execute(
            text("""
                SELECT official_name, registry_country, registration_status,
                       date_dissolved, match_confidence, match_method
                FROM company_registry_data WHERE company_id = :id
            """),
            {"id": str(entity_id)},
        ).mappings().all()
    ]

    # Load insolvency data
    insolvency_rows = [
        dict(r) for r in db.session.execute(
            text("""
                SELECT has_insolvency, active_proceedings, total_proceedings
                FROM company_insolvency_data WHERE company_id = :id
            """),
            {"id": str(entity_id)},
        ).mappings().all()
    ]

    # Check if L2 enrichment exists
    l2_row = db.session.execute(
        text("SELECT 1 FROM company_enrichment_l2 WHERE company_id = :id"),
        {"id": str(entity_id)},
    ).first()
    has_l2 = l2_row is not None

    # Determine which stages have completed for this entity
    completed_stages = set()
    stage_rows = db.session.execute(
        text("""
            SELECT stage FROM entity_stage_completions
            WHERE entity_id = :id AND tenant_id = :tid AND status = 'completed'
        """),
        {"id": str(entity_id), "tid": str(tenant_id)},
    ).all()
    for sr in stage_rows:
        completed_stages.add(sr[0])

    # Run all checks
    qc_flags.extend(_check_registry_name_mismatch(company.get("name"), registry_rows))
    qc_flags.extend(_check_hq_country_conflict(company.get("hq_country"), registry_rows))
    qc_flags.extend(_check_active_insolvency(insolvency_rows))
    qc_flags.extend(_check_dissolved(registry_rows))
    qc_flags.extend(_check_data_completeness(company, has_l2, bool(registry_rows), completed_stages))
    qc_flags.extend(_check_low_registry_confidence(registry_rows))

    logger.info(
        "QC for company %s: %d flags%s",
        entity_id,
        len(qc_flags),
        " — " + ", ".join(qc_flags) if qc_flags else "",
    )

    return {
        "enrichment_cost_usd": 0.0,
        "qc_flags": qc_flags,
    }
