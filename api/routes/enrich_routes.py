"""Enrich API routes: estimate costs and start enrichment pipeline."""

import json

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text

from ..auth import require_auth, resolve_tenant
from ..models import PipelineRun, StageRun, db
from ..services.pipeline_engine import (
    AVAILABLE_STAGES,
    count_eligible,
    start_pipeline_threads,
)

enrich_bp = Blueprint("enrich", __name__)

ENRICHMENT_STAGES = ["l1", "l2", "person", "generate"]

# Static cost defaults (USD per item) — used when no historical data exists
STATIC_COST_DEFAULTS = {
    "l1": 0.02,
    "l2": 0.08,
    "person": 0.04,
    "generate": 0.03,
}


def _resolve_batch(tenant_id, batch_name):
    """Look up batch by name, return (batch_id, error_response)."""
    row = db.session.execute(
        text("SELECT id FROM batches WHERE tenant_id = :t AND name = :n"),
        {"t": str(tenant_id), "n": batch_name},
    ).fetchone()
    if not row:
        return None, (jsonify({"error": "Batch not found"}), 404)
    return row[0], None


def _resolve_owner(tenant_id, owner_name):
    """Look up owner by name, return owner_id or None."""
    if not owner_name:
        return None
    row = db.session.execute(
        text("SELECT id FROM owners WHERE tenant_id = :t AND name = :n"),
        {"t": str(tenant_id), "n": owner_name},
    ).fetchone()
    return row[0] if row else None


def _get_cost_per_item(tenant_id, stage):
    """Get average cost per item from historical stage_runs, falling back to static default."""
    row = db.session.execute(
        text("""
            SELECT AVG(cost_usd / NULLIF(done, 0))
            FROM stage_runs
            WHERE tenant_id = :t AND stage = :s
              AND status = 'completed' AND done > 0 AND cost_usd > 0
        """),
        {"t": str(tenant_id), "s": stage},
    ).fetchone()
    if row and row[0] is not None:
        return round(float(row[0]), 4)
    return STATIC_COST_DEFAULTS.get(stage, 0.05)


@enrich_bp.route("/api/enrich/estimate", methods=["POST"])
@require_auth
def enrich_estimate():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    batch_name = body.get("batch_name", "")
    owner_name = body.get("owner_name", "")
    tier_filter = body.get("tier_filter", [])
    stages = body.get("stages", [])

    if not batch_name:
        return jsonify({"error": "batch_name is required"}), 400
    if not stages:
        return jsonify({"error": "stages is required"}), 400

    # Validate stages
    invalid = [s for s in stages if s not in ENRICHMENT_STAGES]
    if invalid:
        return jsonify({"error": f"Invalid stages: {', '.join(invalid)}"}), 400

    batch_id, err = _resolve_batch(tenant_id, batch_name)
    if err:
        return err

    owner_id = _resolve_owner(tenant_id, owner_name)

    result = {}
    total_cost = 0.0

    for stage in stages:
        eligible = count_eligible(tenant_id, batch_id, stage, owner_id, tier_filter)
        cost_per_item = _get_cost_per_item(tenant_id, stage)
        estimated_cost = round(eligible * cost_per_item, 2)
        total_cost += estimated_cost
        result[stage] = {
            "eligible_count": eligible,
            "cost_per_item": cost_per_item,
            "estimated_cost": estimated_cost,
        }

    return jsonify({
        "stages": result,
        "total_estimated_cost": round(total_cost, 2),
    })


@enrich_bp.route("/api/enrich/start", methods=["POST"])
@require_auth
def enrich_start():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    batch_name = body.get("batch_name", "")
    owner_name = body.get("owner_name", "")
    tier_filter = body.get("tier_filter", [])
    stages = body.get("stages", [])
    sample_size = body.get("sample_size")

    if not batch_name:
        return jsonify({"error": "batch_name is required"}), 400
    if not stages:
        return jsonify({"error": "stages is required"}), 400

    # Validate stages
    invalid = [s for s in stages if s not in ENRICHMENT_STAGES]
    if invalid:
        return jsonify({"error": f"Invalid stages: {', '.join(invalid)}"}), 400

    batch_id, err = _resolve_batch(tenant_id, batch_name)
    if err:
        return err

    owner_id = _resolve_owner(tenant_id, owner_name)

    # Check no pipeline already running for this batch
    existing = db.session.execute(
        text("""
            SELECT id FROM pipeline_runs
            WHERE tenant_id = :t AND batch_id = :b
              AND status IN ('running', 'stopping')
            LIMIT 1
        """),
        {"t": str(tenant_id), "b": str(batch_id)},
    ).fetchone()
    if existing:
        return jsonify({"error": "A pipeline is already running for this batch"}), 409

    # Build config
    config = {}
    if tier_filter:
        config["tier_filter"] = tier_filter
    if owner_name:
        config["owner"] = owner_name
    if sample_size:
        config["sample_size"] = int(sample_size)

    # Create pipeline_run record
    pipeline_run = PipelineRun(
        tenant_id=str(tenant_id),
        batch_id=str(batch_id),
        owner_id=str(owner_id) if owner_id else None,
        status="running",
        config=json.dumps(config) if config else "{}",
    )
    db.session.add(pipeline_run)
    db.session.flush()
    pipeline_run_id = str(pipeline_run.id)

    # Create stage_run records for requested stages only
    stage_run_ids = {}
    for stage in stages:
        stage_config = dict(config)
        stage_config["pipeline_run_id"] = pipeline_run_id

        sr = StageRun(
            tenant_id=str(tenant_id),
            batch_id=str(batch_id),
            owner_id=str(owner_id) if owner_id else None,
            stage=stage,
            status="pending",
            total=0,
            config=json.dumps(stage_config),
        )
        db.session.add(sr)
        db.session.flush()
        stage_run_ids[stage] = str(sr.id)

    # Update pipeline_run with stage mapping
    pipeline_run.stages = json.dumps(stage_run_ids)
    db.session.commit()

    # Spawn threads
    start_pipeline_threads(
        current_app._get_current_object(),
        pipeline_run_id,
        stages,
        tenant_id,
        batch_id,
        owner_id=owner_id,
        tier_filter=tier_filter,
        stage_run_ids=stage_run_ids,
    )

    return jsonify({
        "pipeline_run_id": pipeline_run_id,
        "stage_run_ids": stage_run_ids,
    }), 201
