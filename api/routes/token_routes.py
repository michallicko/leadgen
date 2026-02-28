"""Token credit system API routes.

Namespace admin endpoints: view credit usage and budget status.
Super admin endpoints: manage budgets, view cost breakdowns.
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, request

from ..auth import require_role, resolve_tenant
from ..models import NamespaceTokenBudget, db
from ..services.budget import _compute_next_reset

token_bp = Blueprint("tokens", __name__)


# ── Namespace Admin Endpoints (credits only, no USD) ────────────────


@token_bp.route("/api/admin/tokens", methods=["GET"])
@require_role("admin")
def get_token_dashboard():
    """Current budget status and usage summary for the namespace."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Namespace required"}), 400

    budget = NamespaceTokenBudget.query.filter_by(
        tenant_id=str(tenant_id)
    ).first()

    # Period dates
    now = datetime.now(timezone.utc)
    if budget and budget.last_reset_at:
        period_start = budget.last_reset_at
    else:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = now

    # Usage by operation (credits only)
    by_op_rows = db.session.execute(
        db.text(
            "SELECT l.operation, COUNT(*), "
            "COALESCE(SUM(l.credits_consumed), 0) "
            "FROM llm_usage_log l "
            "WHERE CAST(l.tenant_id AS TEXT) = :tid "
            "AND l.created_at >= :start "
            "GROUP BY l.operation ORDER BY 3 DESC"
        ),
        {"tid": str(tenant_id), "start": period_start},
    ).fetchall()

    total_credits = sum(r[2] for r in by_op_rows)
    total_calls = sum(r[1] for r in by_op_rows)

    by_operation = []
    for r in by_op_rows:
        pct = round((r[2] / total_credits) * 100, 1) if total_credits > 0 else 0
        by_operation.append({
            "operation": r[0],
            "calls": r[1],
            "credits": r[2],
            "pct": pct,
        })

    # Usage by user (credits only)
    by_user_rows = db.session.execute(
        db.text(
            "SELECT CAST(l.user_id AS TEXT), "
            "COALESCE(u.display_name, 'System'), "
            "COALESCE(SUM(l.credits_consumed), 0) "
            "FROM llm_usage_log l "
            "LEFT JOIN users u ON u.id = l.user_id "
            "WHERE CAST(l.tenant_id AS TEXT) = :tid "
            "AND l.created_at >= :start "
            "GROUP BY l.user_id, u.display_name ORDER BY 3 DESC"
        ),
        {"tid": str(tenant_id), "start": period_start},
    ).fetchall()

    by_user = []
    for r in by_user_rows:
        pct = round((r[2] / total_credits) * 100, 1) if total_credits > 0 else 0
        by_user.append({
            "user_id": r[0],
            "display_name": r[1],
            "credits": r[2],
            "pct": pct,
        })

    result = {
        "budget": budget.to_dict() if budget else None,
        "current_period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "total_calls": total_calls,
            "total_credits": total_credits,
        },
        "by_operation": by_operation,
        "by_user": by_user,
    }
    return jsonify(result)


@token_bp.route("/api/admin/tokens/status", methods=["GET"])
@require_role("admin")
def get_token_status():
    """Lightweight budget status for the warning banner.

    Returns just the budget info needed by useTokenBudget() hook.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Namespace required"}), 400

    budget = NamespaceTokenBudget.query.filter_by(
        tenant_id=str(tenant_id)
    ).first()

    if not budget:
        return jsonify({"budget": None})

    return jsonify({
        "budget": {
            "total_budget": budget.total_budget,
            "used_credits": budget.used_credits,
            "reserved_credits": budget.reserved_credits,
            "remaining_credits": budget.remaining_credits,
            "usage_pct": budget.usage_pct,
            "enforcement_mode": budget.enforcement_mode,
            "alert_threshold_pct": budget.alert_threshold_pct,
            "next_reset_at": budget.next_reset_at.isoformat() if budget.next_reset_at else None,
        }
    })


@token_bp.route("/api/admin/tokens/history", methods=["GET"])
@require_role("admin")
def get_token_history():
    """Usage over time for charts (credits only)."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Namespace required"}), 400

    period = request.args.get("period", "day")
    if period not in ("day", "week", "month"):
        period = "day"

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    clauses = ["CAST(l.tenant_id AS TEXT) = :tid"]
    params = {"tid": str(tenant_id)}

    if start_date:
        clauses.append("l.created_at >= :start_date")
        params["start_date"] = start_date
    else:
        # Default to last 30 days
        clauses.append("l.created_at >= :start_date")
        params["start_date"] = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).isoformat()

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        clauses.append("l.created_at < :end_date_end")
        params["end_date_end"] = end_dt.strftime("%Y-%m-%dT00:00:00+00:00")

    where = "WHERE " + " AND ".join(clauses)

    data = []
    try:
        trunc = period if period != "week" else "week"
        rows = db.session.execute(
            db.text(
                "SELECT date_trunc(:trunc, l.created_at) AS period, "
                "COUNT(*), "
                "COALESCE(SUM(l.credits_consumed), 0) "
                "FROM llm_usage_log l " + where + " "
                "GROUP BY period ORDER BY period"
            ),
            dict(trunc=trunc, **params),
        ).fetchall()
        data = [
            {
                "date": r[0].strftime("%Y-%m-%d") if r[0] else None,
                "calls": r[1],
                "credits": r[2],
            }
            for r in rows
        ]
    except Exception:
        # date_trunc not available (SQLite in tests)
        pass

    return jsonify({"period": period, "data": data})


# ── Super Admin Endpoints ───────────────────────────────────────────


def _require_super_admin():
    if not g.current_user.is_super_admin:
        return jsonify({"error": "Super admin access required"}), 403
    return None


@token_bp.route("/api/admin/tokens/budget", methods=["PUT"])
@require_role("admin")
def set_budget():
    """Set or update a namespace's budget. Super admin only."""
    denied = _require_super_admin()
    if denied:
        return denied

    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Namespace required"}), 400

    data = request.get_json() or {}
    total_budget = data.get("total_budget")
    if total_budget is None or not isinstance(total_budget, int) or total_budget < 0:
        return jsonify({"error": "total_budget must be a non-negative integer"}), 400

    budget = NamespaceTokenBudget.query.filter_by(
        tenant_id=str(tenant_id)
    ).first()

    now = datetime.now(timezone.utc)

    if not budget:
        budget = NamespaceTokenBudget(tenant_id=str(tenant_id))
        db.session.add(budget)

    budget.total_budget = total_budget
    budget.enforcement_mode = data.get("enforcement_mode", budget.enforcement_mode or "soft")
    budget.alert_threshold_pct = data.get("alert_threshold_pct", budget.alert_threshold_pct or 80)

    reset_period = data.get("reset_period")
    if reset_period in ("monthly", "quarterly", None):
        budget.reset_period = reset_period
    reset_day = data.get("reset_day")
    if reset_day and isinstance(reset_day, int) and 1 <= reset_day <= 31:
        budget.reset_day = reset_day

    # Compute next_reset_at if reset_period is set
    if budget.reset_period:
        budget.next_reset_at = _compute_next_reset(
            budget.reset_period, budget.reset_day, now
        )
    else:
        budget.next_reset_at = None

    budget.updated_at = now
    db.session.commit()

    return jsonify({"budget": budget.to_dict(), "message": "Budget updated successfully"})


@token_bp.route("/api/admin/tokens/topup", methods=["POST"])
@require_role("admin")
def topup_credits():
    """Add credits to a namespace's current budget. Super admin only."""
    denied = _require_super_admin()
    if denied:
        return denied

    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Namespace required"}), 400

    data = request.get_json() or {}
    credits = data.get("credits")
    if credits is None or not isinstance(credits, int) or credits <= 0:
        return jsonify({"error": "credits must be a positive integer"}), 400

    budget = NamespaceTokenBudget.query.filter_by(
        tenant_id=str(tenant_id)
    ).first()
    if not budget:
        return jsonify({"error": "No budget configured for this namespace"}), 404

    budget.total_budget += credits
    budget.updated_at = db.func.now()
    db.session.commit()

    return jsonify({
        "budget": budget.to_dict(),
        "added_credits": credits,
        "new_total": budget.total_budget,
    })


@token_bp.route("/api/admin/tokens/cost-breakdown", methods=["GET"])
@require_role("admin")
def cost_breakdown():
    """Detailed breakdown by operation + provider + model with USD. Super admin only."""
    denied = _require_super_admin()
    if denied:
        return denied

    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Namespace required"}), 400

    clauses = ["CAST(l.tenant_id AS TEXT) = :tid"]
    params = {"tid": str(tenant_id)}

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if start_date:
        clauses.append("l.created_at >= :start_date")
        params["start_date"] = start_date
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        clauses.append("l.created_at < :end_date_end")
        params["end_date_end"] = end_dt.strftime("%Y-%m-%dT00:00:00+00:00")

    where = "WHERE " + " AND ".join(clauses)

    rows = db.session.execute(
        db.text(
            "SELECT l.operation, l.provider, l.model, COUNT(*), "
            "COALESCE(SUM(l.input_tokens), 0), "
            "COALESCE(SUM(l.output_tokens), 0), "
            "COALESCE(SUM(l.cost_usd), 0), "
            "COALESCE(SUM(l.credits_consumed), 0) "
            "FROM llm_usage_log l " + where + " "
            "GROUP BY l.operation, l.provider, l.model ORDER BY 7 DESC"
        ),
        params,
    ).fetchall()

    breakdown = []
    for r in rows:
        calls = r[3]
        credits = r[7]
        breakdown.append({
            "operation": r[0],
            "provider": r[1],
            "model": r[2],
            "calls": calls,
            "input_tokens": r[4],
            "output_tokens": r[5],
            "cost_usd": float(r[6]),
            "credits": credits,
            "avg_credits_per_call": round(credits / calls) if calls > 0 else 0,
        })

    return jsonify({"breakdown": breakdown})
