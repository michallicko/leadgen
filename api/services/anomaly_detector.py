"""BL-172: AI Anomaly Detection — rule-based proactive problem flagging.

Detects unusual patterns in enrichment data:
- Duplicate data (e.g., all contacts at one company have same title)
- Missing required fields at high rates
- Cost outliers (enrichment cost spikes)
- High failure rates per stage
- Stale data (enrichment older than threshold)

Returns structured alerts with severity and actionable descriptions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from ..models import db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

DUPLICATE_TITLE_THRESHOLD = 3  # flag if N+ contacts share the same title at a company
COST_OUTLIER_MULTIPLIER = 3.0  # flag if company cost > N× the batch average
FAILURE_RATE_THRESHOLD = 0.3  # flag if stage failure rate > 30%
STALE_DAYS = 90  # flag if enrichment older than N days
MISSING_FIELD_RATE_THRESHOLD = 0.5  # flag if >50% of batch missing a critical field


def _parse_jsonb(val):
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            return json.loads(val) if val else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return val


# ---------------------------------------------------------------------------
# Individual anomaly checks
# ---------------------------------------------------------------------------


def _check_duplicate_titles(tenant_id: str, tag_id: str) -> list[dict]:
    """Find companies where multiple contacts share the exact same job title."""
    rows = db.session.execute(
        text("""
            SELECT c.name, c.id, ct.job_title, COUNT(*) as cnt
            FROM contacts ct
            JOIN companies c ON ct.company_id = c.id
            WHERE ct.tenant_id = :tid AND ct.tag_id = :tag_id
              AND ct.job_title IS NOT NULL AND ct.job_title != ''
              AND (ct.is_disqualified = false OR ct.is_disqualified IS NULL)
            GROUP BY c.id, c.name, ct.job_title
            HAVING COUNT(*) >= :threshold
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """),
        {"tid": tenant_id, "tag_id": tag_id, "threshold": DUPLICATE_TITLE_THRESHOLD},
    ).fetchall()

    alerts = []
    for row in rows:
        alerts.append(
            {
                "type": "duplicate_titles",
                "severity": "medium",
                "entity_type": "company",
                "entity_id": str(row[1]),
                "entity_name": row[0],
                "message": f"{row[3]} contacts share title '{row[2]}' at {row[0]} — possible data quality issue.",
                "details": {"title": row[2], "count": row[3]},
            }
        )
    return alerts


def _check_cost_outliers(tenant_id: str, tag_id: str) -> list[dict]:
    """Find companies with enrichment costs far above the batch average."""
    # Get batch average (no STDDEV — not all DBs support it)
    try:
        avg_row = db.session.execute(
            text("""
                SELECT AVG(enrichment_cost_usd)
                FROM companies
                WHERE tenant_id = :tid AND tag_id = :tag_id
                  AND enrichment_cost_usd > 0
            """),
            {"tid": tenant_id, "tag_id": tag_id},
        ).fetchone()
    except Exception:
        return []

    if not avg_row or avg_row[0] is None:
        return []

    avg_cost = float(avg_row[0])
    if avg_cost == 0:
        return []

    threshold = avg_cost * COST_OUTLIER_MULTIPLIER

    outliers = db.session.execute(
        text("""
            SELECT id, name, enrichment_cost_usd
            FROM companies
            WHERE tenant_id = :tid AND tag_id = :tag_id
              AND enrichment_cost_usd > :threshold
            ORDER BY enrichment_cost_usd DESC
            LIMIT 10
        """),
        {"tid": tenant_id, "tag_id": tag_id, "threshold": threshold},
    ).fetchall()

    alerts = []
    for row in outliers:
        if row[2] is None:
            continue
        cost = float(row[2])
        ratio = cost / avg_cost if avg_cost > 0 else 0
        alerts.append(
            {
                "type": "cost_outlier",
                "severity": "low",
                "entity_type": "company",
                "entity_id": str(row[0]),
                "entity_name": row[1] or "Unknown",
                "message": f"{row[1] or 'Unknown'} enrichment cost ${cost:.4f} is {ratio:.1f}x the batch average (${avg_cost:.4f}).",
                "details": {
                    "cost": cost,
                    "avg_cost": avg_cost,
                    "ratio": round(ratio, 1),
                },
            }
        )
    return alerts


def _check_high_failure_rates(tenant_id: str, tag_id: str) -> list[dict]:
    """Check for stages with high failure rates in recent runs."""
    try:
        rows = db.session.execute(
            text("""
                SELECT stage, status, total, done, failed, started_at
                FROM stage_runs
                WHERE tenant_id = :tid AND tag_id = :tag_id
                  AND status IN ('completed', 'failed')
                  AND total > 0
                ORDER BY started_at DESC
                LIMIT 20
            """),
            {"tid": tenant_id, "tag_id": tag_id},
        ).fetchall()
    except Exception:
        return []

    alerts = []
    seen_stages = set()
    for row in rows:
        stage = row[0]
        if not stage or stage in seen_stages:
            continue
        seen_stages.add(stage)

        total = int(row[2]) if row[2] is not None else 0
        failed = int(row[4]) if row[4] is not None else 0
        if total > 0:
            failure_rate = failed / total
            if failure_rate > FAILURE_RATE_THRESHOLD:
                alerts.append(
                    {
                        "type": "high_failure_rate",
                        "severity": "high",
                        "entity_type": "stage",
                        "entity_id": stage,
                        "entity_name": stage,
                        "message": f"Stage '{stage}' has {failure_rate:.0%} failure rate ({failed}/{total} items failed).",
                        "details": {
                            "stage": stage,
                            "total": total,
                            "failed": failed,
                            "rate": round(failure_rate, 2),
                        },
                    }
                )
    return alerts


def _check_missing_critical_fields(tenant_id: str, tag_id: str) -> list[dict]:
    """Check if a high percentage of enriched companies are missing critical fields."""
    try:
        total_row = db.session.execute(
            text("""
                SELECT COUNT(*) FROM companies
                WHERE tenant_id = :tid AND tag_id = :tag_id
                  AND status NOT IN ('new', 'enrichment_failed')
            """),
            {"tid": tenant_id, "tag_id": tag_id},
        ).fetchone()
    except Exception:
        return []

    total = total_row[0] if total_row else 0
    if total == 0:
        return []

    # Use IS NULL only for enum columns (can't compare with empty string)
    fields_to_check = [
        ("industry", "Industry", False),
        ("hq_country", "HQ Country", False),
        ("summary", "Company Summary", False),
        ("company_size", "Company Size", True),  # enum column
    ]

    alerts = []
    for field, label, is_enum in fields_to_check:
        try:
            if is_enum:
                null_check = f"{field} IS NULL"
            else:
                null_check = f"({field} IS NULL OR CAST({field} AS TEXT) = '')"
            missing_row = db.session.execute(
                text(f"""
                    SELECT COUNT(*) FROM companies
                    WHERE tenant_id = :tid AND tag_id = :tag_id
                      AND status NOT IN ('new', 'enrichment_failed')
                      AND {null_check}
                """),
                {"tid": tenant_id, "tag_id": tag_id},
            ).fetchone()
        except Exception:
            continue

        missing = missing_row[0] if missing_row else 0
        if total > 0 and missing / total > MISSING_FIELD_RATE_THRESHOLD:
            rate = missing / total
            alerts.append(
                {
                    "type": "missing_critical_field",
                    "severity": "medium",
                    "entity_type": "batch",
                    "entity_id": tag_id,
                    "entity_name": label,
                    "message": f"{rate:.0%} of enriched companies ({missing}/{total}) are missing '{label}'.",
                    "details": {
                        "field": field,
                        "missing": missing,
                        "total": total,
                        "rate": round(rate, 2),
                    },
                }
            )
    return alerts


def _check_stale_enrichment(tenant_id: str, tag_id: str) -> list[dict]:
    """Find companies with enrichment data older than STALE_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)

    try:
        rows = db.session.execute(
            text("""
                SELECT c.id, c.name, c.last_enriched_at
                FROM companies c
                WHERE c.tenant_id = :tid AND c.tag_id = :tag_id
                  AND c.last_enriched_at IS NOT NULL
                  AND c.last_enriched_at < :cutoff
                ORDER BY c.last_enriched_at ASC
                LIMIT 10
            """),
            {"tid": tenant_id, "tag_id": tag_id, "cutoff": cutoff.isoformat()},
        ).fetchall()
    except Exception:
        return []

    alerts = []
    for row in rows:
        if row[0] is None:
            continue
        enriched_at = row[2]
        if enriched_at is None:
            continue
        if hasattr(enriched_at, "isoformat"):
            try:
                age_days = (
                    datetime.now(timezone.utc)
                    - enriched_at.replace(tzinfo=timezone.utc)
                ).days
            except Exception:
                age_days = STALE_DAYS + 1
        else:
            age_days = STALE_DAYS + 1  # fallback

        alerts.append(
            {
                "type": "stale_enrichment",
                "severity": "low",
                "entity_type": "company",
                "entity_id": str(row[0]),
                "entity_name": row[1] or "Unknown",
                "message": f"{row[1] or 'Unknown'} enrichment data is {age_days} days old — consider re-enriching.",
                "details": {"days_old": age_days},
            }
        )
    return alerts


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def detect_anomalies(tenant_id: str, tag_id: str) -> dict:
    """Run all anomaly checks for a batch.

    Returns:
        {
            "total_alerts": int,
            "by_severity": {"high": N, "medium": N, "low": N},
            "by_type": {"duplicate_titles": N, ...},
            "alerts": [{"type", "severity", "entity_type", "entity_id", "entity_name", "message", "details"}, ...],
        }
    """
    all_alerts: list[dict] = []

    checks = [
        _check_duplicate_titles,
        _check_cost_outliers,
        _check_high_failure_rates,
        _check_missing_critical_fields,
        _check_stale_enrichment,
    ]
    for check_fn in checks:
        try:
            all_alerts.extend(check_fn(tenant_id, tag_id))
        except Exception as e:
            logger.warning("Anomaly check %s failed: %s", check_fn.__name__, e)

    # Sort: high severity first, then medium, then low
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_alerts.sort(key=lambda a: severity_order.get(a["severity"], 9))

    # Aggregate
    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for a in all_alerts:
        by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1

    return {
        "total_alerts": len(all_alerts),
        "by_severity": by_severity,
        "by_type": by_type,
        "alerts": all_alerts,
    }
