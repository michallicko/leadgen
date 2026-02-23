"""LLM usage tracking API routes (super admin only)."""

from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

from ..auth import require_role
from ..models import db

llm_usage_bp = Blueprint("llm_usage", __name__)


def _require_super_admin():
    """Return error tuple if current user is not super admin, else None."""
    if not g.current_user.is_super_admin:
        return jsonify({"error": "Super admin access required"}), 403
    return None


def _date_filter(args):
    """Build date filter clauses and params from request args.

    Returns (clauses_list, params_dict).
    """
    clauses = []
    params = {}
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    if start_date:
        clauses.append("l.created_at >= :start_date")
        params["start_date"] = start_date
    if end_date:
        clauses.append("l.created_at < :end_date_end")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        params["end_date_end"] = end_dt.strftime("%Y-%m-%dT00:00:00+00:00")
    return clauses, params


def _where(clauses):
    """Build a WHERE string from a list of clauses."""
    if not clauses:
        return ""
    return "WHERE " + " AND ".join(clauses)


@llm_usage_bp.route("/api/llm-usage/summary", methods=["GET"])
@require_role("admin")
def llm_usage_summary():
    """Aggregated LLM usage summary with breakdowns.

    Query params:
        start_date: ISO date (default: 30 days ago)
        end_date: ISO date (default: today)
        group_by: 'day' or 'month' (default: 'day')
    """
    denied = _require_super_admin()
    if denied:
        return denied

    group_by = request.args.get("group_by", "day")
    if group_by not in ("day", "month"):
        group_by = "day"

    clauses, params = _date_filter(request.args)
    where = _where(clauses)

    # Totals
    totals_row = db.session.execute(
        db.text(
            "SELECT COALESCE(SUM(l.cost_usd), 0), "
            "COUNT(*), "
            "COALESCE(SUM(l.input_tokens), 0), "
            "COALESCE(SUM(l.output_tokens), 0) "
            "FROM llm_usage_log l " + where
        ),
        params,
    ).fetchone()

    # By tenant
    by_tenant = db.session.execute(
        db.text(
            "SELECT t.slug, t.name, CAST(l.tenant_id AS TEXT), "
            "COUNT(*), "
            "COALESCE(SUM(l.cost_usd), 0), "
            "COALESCE(SUM(l.input_tokens), 0), "
            "COALESCE(SUM(l.output_tokens), 0) "
            "FROM llm_usage_log l "
            "JOIN tenants t ON t.id = l.tenant_id " + where + " "
            "GROUP BY t.slug, t.name, l.tenant_id "
            "ORDER BY 5 DESC"
        ),
        params,
    ).fetchall()

    # By operation
    by_operation = db.session.execute(
        db.text(
            "SELECT l.operation, COUNT(*), "
            "COALESCE(SUM(l.cost_usd), 0), "
            "COALESCE(SUM(l.input_tokens), 0), "
            "COALESCE(SUM(l.output_tokens), 0) "
            "FROM llm_usage_log l " + where + " "
            "GROUP BY l.operation ORDER BY 3 DESC"
        ),
        params,
    ).fetchall()

    # By model
    by_model = db.session.execute(
        db.text(
            "SELECT l.provider, l.model, COUNT(*), "
            "COALESCE(SUM(l.cost_usd), 0), "
            "COALESCE(SUM(l.input_tokens), 0), "
            "COALESCE(SUM(l.output_tokens), 0) "
            "FROM llm_usage_log l " + where + " "
            "GROUP BY l.provider, l.model ORDER BY 4 DESC"
        ),
        params,
    ).fetchall()

    # Time series (PG-specific date_trunc)
    time_series = []
    try:
        trunc = "day" if group_by == "day" else "month"
        ts_rows = db.session.execute(
            db.text(
                "SELECT date_trunc(:trunc, l.created_at) AS period, "
                "COUNT(*), "
                "COALESCE(SUM(l.cost_usd), 0), "
                "COALESCE(SUM(l.input_tokens), 0), "
                "COALESCE(SUM(l.output_tokens), 0) "
                "FROM llm_usage_log l " + where + " "
                "GROUP BY period ORDER BY period"
            ),
            dict(trunc=trunc, **params),
        ).fetchall()
        time_series = [
            {
                "period": r[0].isoformat() if r[0] else None,
                "calls": r[1],
                "cost": float(r[2]),
                "input_tokens": r[3],
                "output_tokens": r[4],
            }
            for r in ts_rows
        ]
    except Exception:
        # date_trunc not available (e.g. SQLite in tests)
        pass

    return jsonify(
        {
            "total_cost_usd": float(totals_row[0]),
            "total_calls": totals_row[1],
            "total_input_tokens": totals_row[2],
            "total_output_tokens": totals_row[3],
            "by_tenant": [
                {
                    "tenant_slug": r[0],
                    "tenant_name": r[1],
                    "tenant_id": r[2],
                    "calls": r[3],
                    "cost": float(r[4]),
                    "input_tokens": r[5],
                    "output_tokens": r[6],
                }
                for r in by_tenant
            ],
            "by_operation": [
                {
                    "operation": r[0],
                    "calls": r[1],
                    "cost": float(r[2]),
                    "input_tokens": r[3],
                    "output_tokens": r[4],
                }
                for r in by_operation
            ],
            "by_model": [
                {
                    "provider": r[0],
                    "model": r[1],
                    "calls": r[2],
                    "cost": float(r[3]),
                    "input_tokens": r[4],
                    "output_tokens": r[5],
                }
                for r in by_model
            ],
            "time_series": time_series,
        }
    )


@llm_usage_bp.route("/api/llm-usage/logs", methods=["GET"])
@require_role("admin")
def llm_usage_logs():
    """Paginated list of individual LLM usage log entries.

    Query params:
        start_date, end_date: ISO date filters
        tenant_id: filter by tenant
        operation: filter by operation
        model: filter by model
        page: page number (default 1)
        per_page: items per page (default 50, max 200)
    """
    denied = _require_super_admin()
    if denied:
        return denied

    page = max(1, int(request.args.get("page", 1)))
    per_page = min(200, max(1, int(request.args.get("per_page", 50))))

    clauses, params = _date_filter(request.args)

    tenant_id = request.args.get("tenant_id")
    operation = request.args.get("operation")
    model = request.args.get("model")

    if tenant_id:
        clauses.append("CAST(l.tenant_id AS TEXT) = :tenant_id")
        params["tenant_id"] = tenant_id
    if operation:
        clauses.append("l.operation = :operation")
        params["operation"] = operation
    if model:
        clauses.append("l.model = :model")
        params["model"] = model

    where = _where(clauses)

    # Count total
    count_row = db.session.execute(
        db.text("SELECT COUNT(*) FROM llm_usage_log l " + where),
        params,
    ).fetchone()
    total = count_row[0]

    # Fetch page
    offset = (page - 1) * per_page
    rows = db.session.execute(
        db.text(
            "SELECT l.id, CAST(l.tenant_id AS TEXT), t.slug, "
            "CAST(l.user_id AS TEXT), l.operation, l.provider, l.model, "
            "l.input_tokens, l.output_tokens, l.cost_usd, "
            "l.duration_ms, l.metadata, l.created_at "
            "FROM llm_usage_log l "
            "LEFT JOIN tenants t ON t.id = l.tenant_id " + where + " "
            "ORDER BY l.created_at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        dict(limit=per_page, offset=offset, **params),
    ).fetchall()

    logs = [
        {
            "id": str(r[0]),
            "tenant_id": r[1],
            "tenant_slug": r[2],
            "user_id": r[3],
            "operation": r[4],
            "provider": r[5],
            "model": r[6],
            "input_tokens": r[7],
            "output_tokens": r[8],
            "cost_usd": float(r[9]) if r[9] else 0,
            "duration_ms": r[10],
            "metadata": r[11] if isinstance(r[11], dict) else {},
            "created_at": r[12].isoformat() if hasattr(r[12], "isoformat") else r[12],
        }
        for r in rows
    ]

    return jsonify(
        {
            "logs": logs,
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    )
