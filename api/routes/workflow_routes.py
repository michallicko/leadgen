"""Workflow state machine API routes.

GET  /api/workflow/state   — compute current workflow phase from actual data
POST /api/workflow/advance — record an explicit phase transition
GET  /api/workflow/history — list recent phase transitions
"""

import logging

from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import WorkflowTransition, db
from ..services.workflow_state import (
    WORKFLOW_PHASES,
    compute_workflow_state,
)

logger = logging.getLogger(__name__)

workflow_bp = Blueprint("workflow", __name__)


@workflow_bp.route("/api/workflow/state", methods=["GET"])
@require_auth
def get_workflow_state():
    """Compute and return the current workflow state from actual data.

    Returns:
        {
            current_phase: str,
            current_phase_label: str,
            completed_phases: list[str],
            total_phases: int,
            progress_pct: int,
            next_action: { action, label, route },
            context: { strategy, contacts, enrichment, ... }
        }
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    state = compute_workflow_state(tenant_id)
    return jsonify(state), 200


@workflow_bp.route("/api/workflow/advance", methods=["POST"])
@require_auth
def advance_workflow():
    """Record an explicit phase transition.

    Body: {
        "to_phase": "contacts_imported",
        "trigger": "user_action" | "auto" | "enrichment_complete" | ...,
        "metadata": { ... optional context ... }
    }

    The endpoint validates that `to_phase` is a valid phase and records
    the transition. It does NOT enforce ordering — the computed state
    is the source of truth, and transitions are just an audit log.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    to_phase = data.get("to_phase", "").strip()
    trigger = data.get("trigger", "user_action").strip()
    metadata = data.get("metadata", {})

    if not to_phase:
        return jsonify({"error": "to_phase is required"}), 400

    if to_phase not in WORKFLOW_PHASES:
        return jsonify(
            {"error": f"Invalid phase: {to_phase}", "valid_phases": WORKFLOW_PHASES}
        ), 400

    # Compute current state to record from_phase
    current = compute_workflow_state(tenant_id)
    from_phase = current["current_phase"]

    from flask import g

    transition = WorkflowTransition(
        tenant_id=str(tenant_id),
        from_phase=from_phase,
        to_phase=to_phase,
        trigger=trigger,
        metadata_json=metadata if isinstance(metadata, dict) else {},
        user_id=str(g.current_user.id) if hasattr(g, "current_user") else None,
    )
    db.session.add(transition)
    db.session.commit()

    return jsonify(
        {
            "transition": transition.to_dict(),
            "state": compute_workflow_state(tenant_id),
        }
    ), 201


@workflow_bp.route("/api/workflow/history", methods=["GET"])
@require_auth
def workflow_history():
    """List recent workflow transitions for this namespace.

    Query params:
        limit: int (default 20, max 100)
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    limit = min(int(request.args.get("limit", 20)), 100)

    transitions = (
        WorkflowTransition.query.filter_by(tenant_id=str(tenant_id))
        .order_by(WorkflowTransition.created_at.desc())
        .limit(limit)
        .all()
    )

    return jsonify({"transitions": [t.to_dict() for t in transitions]}), 200
