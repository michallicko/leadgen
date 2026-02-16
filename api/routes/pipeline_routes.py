"""Pipeline API routes: start/stop/status for per-node enrichment runs + run-all/stop-all."""

import json
import uuid as _uuid_mod

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text

from ..auth import require_auth, resolve_tenant
from ..display import display_status, display_tier
from ..models import PipelineRun, StageRun, db
from ..services.pipeline_engine import (
    AVAILABLE_STAGES,
    COMING_SOON_STAGES,
    get_eligible_ids,
    start_pipeline_threads,
    start_stage_thread,
)

pipeline_bp = Blueprint("pipeline", __name__)

ALL_STAGES = ["l1", "triage", "l2", "person", "generate", "review", "ares"]
PIPELINE_STAGES = ["l1", "l2", "person", "generate"]  # stages run by run-all


def _fmt_dt(val):
    """Format a datetime value — handles both datetime objects (PG) and strings (SQLite)."""
    if val is None:
        return None
    return val.isoformat() if hasattr(val, "isoformat") else str(val)


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


@pipeline_bp.route("/api/pipeline/start", methods=["POST"])
@require_auth
def pipeline_start():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    stage = body.get("stage", "")
    batch_name = body.get("batch_name", "")
    owner_name = body.get("owner", "")
    tier_filter = body.get("tier_filter", [])

    if not stage:
        return jsonify({"error": "stage is required"}), 400
    if stage not in AVAILABLE_STAGES:
        if stage in COMING_SOON_STAGES:
            return jsonify({"error": f"Stage '{stage}' is not yet available"}), 400
        return jsonify({"error": f"Unknown stage: {stage}"}), 400
    if not batch_name:
        return jsonify({"error": "batch_name is required"}), 400

    batch_id, err = _resolve_batch(tenant_id, batch_name)
    if err:
        return err

    owner_id = _resolve_owner(tenant_id, owner_name)

    # Check no run already active for this stage+batch
    existing = db.session.execute(
        text("""
            SELECT id FROM stage_runs
            WHERE tenant_id = :t AND batch_id = :b AND stage = :s
              AND status IN ('pending', 'running')
            LIMIT 1
        """),
        {"t": str(tenant_id), "b": str(batch_id), "s": stage},
    ).fetchone()
    if existing:
        return jsonify({"error": f"Stage '{stage}' is already running for this batch"}), 409

    # Get eligible entities
    entity_ids = get_eligible_ids(tenant_id, batch_id, stage, owner_id, tier_filter)
    if not entity_ids:
        return jsonify({"error": "No eligible items found for this stage"}), 400

    # Create stage_run record
    config = {}
    if tier_filter:
        config["tier_filter"] = tier_filter
    if owner_name:
        config["owner"] = owner_name

    run = StageRun(
        tenant_id=str(tenant_id),
        batch_id=str(batch_id),
        owner_id=str(owner_id) if owner_id else None,
        stage=stage,
        status="pending",
        total=len(entity_ids),
        config=json.dumps(config) if config else "{}",
    )
    db.session.add(run)
    db.session.commit()
    run_id = str(run.id)

    # Spawn background thread
    start_stage_thread(current_app._get_current_object(), run_id, stage, entity_ids, tenant_id=tenant_id)

    return jsonify({"run_id": run_id, "total": len(entity_ids)}), 201


@pipeline_bp.route("/api/pipeline/stop", methods=["POST"])
@require_auth
def pipeline_stop():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    run_id = body.get("run_id", "")
    if not run_id:
        return jsonify({"error": "run_id is required"}), 400
    try:
        _uuid_mod.UUID(run_id)
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid run_id format"}), 400

    row = db.session.execute(
        text("SELECT status FROM stage_runs WHERE id = :id AND tenant_id = :t"),
        {"id": run_id, "t": str(tenant_id)},
    ).fetchone()

    if not row:
        return jsonify({"error": "Run not found"}), 404
    if row[0] not in ("pending", "running"):
        return jsonify({"error": f"Cannot stop run with status '{row[0]}'"}), 400

    db.session.execute(
        text("UPDATE stage_runs SET status = 'stopping' WHERE id = :id"),
        {"id": run_id},
    )
    db.session.commit()

    return jsonify({"ok": True})


@pipeline_bp.route("/api/pipeline/status", methods=["GET"])
@require_auth
def pipeline_status():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    batch_name = request.args.get("batch_name", "")
    if not batch_name:
        return jsonify({"error": "batch_name query param required"}), 400

    batch_id, err = _resolve_batch(tenant_id, batch_name)
    if err:
        return err

    stages = {}
    for stage_name in ALL_STAGES:
        if stage_name in COMING_SOON_STAGES:
            stages[stage_name] = {"status": "unavailable"}
            continue

        # Find most recent run for this stage+batch
        row = db.session.execute(
            text("""
                SELECT id, status, total, done, failed, cost_usd, error,
                       started_at, completed_at, updated_at
                FROM stage_runs
                WHERE tenant_id = :t AND batch_id = :b AND stage = :s
                ORDER BY started_at DESC
                LIMIT 1
            """),
            {"t": str(tenant_id), "b": str(batch_id), "s": stage_name},
        ).fetchone()

        if not row:
            stages[stage_name] = {"status": "idle"}
        else:
            stages[stage_name] = {
                "run_id": str(row[0]),
                "status": row[1],
                "total": row[2] or 0,
                "done": row[3] or 0,
                "failed": row[4] or 0,
                "cost": float(row[5] or 0),
                "error": row[6],
                "started_at": _fmt_dt(row[7]),
                "completed_at": _fmt_dt(row[8]),
                "updated_at": _fmt_dt(row[9]),
            }

    # Include pipeline run status if one exists for this batch
    pipeline_obj = None
    prow = db.session.execute(
        text("""
            SELECT id, status, cost_usd, stages, started_at, completed_at, updated_at
            FROM pipeline_runs
            WHERE tenant_id = :t AND batch_id = :b
            ORDER BY started_at DESC
            LIMIT 1
        """),
        {"t": str(tenant_id), "b": str(batch_id)},
    ).fetchone()
    if prow:
        stages_json = prow[3]
        if isinstance(stages_json, str):
            try:
                stages_json = json.loads(stages_json)
            except (json.JSONDecodeError, TypeError):
                stages_json = {}
        pipeline_obj = {
            "run_id": str(prow[0]),
            "status": prow[1],
            "cost": float(prow[2] or 0),
            "stages": stages_json or {},
            "started_at": _fmt_dt(prow[4]),
            "completed_at": _fmt_dt(prow[5]),
            "updated_at": _fmt_dt(prow[6]),
        }

    result = {"stages": stages}
    if pipeline_obj:
        result["pipeline"] = pipeline_obj

    return jsonify(result)


# ---------------------------------------------------------------------------
# Run-all / Stop-all (reactive parallel pipeline)
# ---------------------------------------------------------------------------

@pipeline_bp.route("/api/pipeline/run-all", methods=["POST"])
@require_auth
def pipeline_run_all():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    batch_name = body.get("batch_name", "")
    owner_name = body.get("owner", "")
    tier_filter = body.get("tier_filter", [])

    if not batch_name:
        return jsonify({"error": "batch_name is required"}), 400

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

    # Create pipeline_run record
    config = {}
    if tier_filter:
        config["tier_filter"] = tier_filter
    if owner_name:
        config["owner"] = owner_name

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

    # Create stage_run records for each stage
    stage_run_ids = {}
    for stage in PIPELINE_STAGES:
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
        PIPELINE_STAGES,
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


@pipeline_bp.route("/api/pipeline/stop-all", methods=["POST"])
@require_auth
def pipeline_stop_all():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    pipeline_run_id = body.get("pipeline_run_id", "")

    if not pipeline_run_id:
        return jsonify({"error": "pipeline_run_id is required"}), 400
    try:
        _uuid_mod.UUID(pipeline_run_id)
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid pipeline_run_id format"}), 400

    row = db.session.execute(
        text("SELECT status FROM pipeline_runs WHERE id = :id AND tenant_id = :t"),
        {"id": pipeline_run_id, "t": str(tenant_id)},
    ).fetchone()

    if not row:
        return jsonify({"error": "Pipeline run not found"}), 404
    if row[0] not in ("running",):
        return jsonify({"error": f"Cannot stop pipeline with status '{row[0]}'"}), 400

    # Set pipeline to stopping — coordinator thread will propagate to stage_runs
    db.session.execute(
        text("UPDATE pipeline_runs SET status = 'stopping' WHERE id = :id"),
        {"id": pipeline_run_id},
    )
    db.session.commit()

    return jsonify({"ok": True})
