"""Pipeline engine: background threads that process entities through n8n workflows.

Supports two modes:
1. Single-stage: run_stage() processes a fixed list of entity IDs (individual stage buttons)
2. Reactive parallel: run_stage_reactive() polls for new eligible IDs as predecessors complete
"""

import logging
import threading
import time
from datetime import datetime, timezone

import requests
from flask import current_app
from sqlalchemy import text

from ..models import db

logger = logging.getLogger(__name__)

N8N_WEBHOOK_PATHS = {
    "l1": "/webhook/l1-enrich",
    "l2": "/webhook/l2-enrich",
    "person": "/webhook/person-enrich",
    "generate": "/webhook/generate-messages",
}

# Stages that have n8n workflows wired up
AVAILABLE_STAGES = {"l1", "l2", "person", "generate"}
# Stages that are manual gates (not executable)
COMING_SOON_STAGES = {"review"}

# Stage predecessors for reactive pipeline (which stage feeds into which)
STAGE_PREDECESSORS = {
    "l1": [],           # L1 has no predecessor — processes fixed set
    "l2": ["l1"],       # L2 watches L1 (triage is auto-output of L1)
    "person": ["l2"],   # Person watches L2
    "generate": ["person"],  # Generate watches Person
}

REACTIVE_POLL_INTERVAL = 15  # seconds between re-querying eligible IDs
COORDINATOR_POLL_INTERVAL = 10  # seconds between checking all stage statuses

ELIGIBILITY_QUERIES = {
    "l1": """
        SELECT c.id FROM companies c
        WHERE c.tenant_id = :tenant_id AND c.batch_id = :batch_id
          AND c.status IN ('new', 'enrichment_failed')
          {owner_clause}
        ORDER BY c.name
    """,
    "l2": """
        SELECT c.id FROM companies c
        WHERE c.tenant_id = :tenant_id AND c.batch_id = :batch_id
          AND c.status = 'triage_passed'
          {owner_clause}
          {tier_clause}
        ORDER BY c.name
    """,
    "person": """
        SELECT ct.id FROM contacts ct
        JOIN companies c ON ct.company_id = c.id
        WHERE ct.tenant_id = :tenant_id AND ct.batch_id = :batch_id
          AND c.status = 'enriched_l2' AND NOT ct.processed_enrich
          {owner_clause}
        ORDER BY ct.full_name
    """,
    "generate": """
        SELECT ct.id FROM contacts ct
        JOIN companies c ON ct.company_id = c.id
        WHERE ct.tenant_id = :tenant_id AND ct.batch_id = :batch_id
          AND ct.processed_enrich = true
          AND (ct.message_status IS NULL OR ct.message_status = 'not_started')
          {owner_clause}
        ORDER BY ct.contact_score DESC NULLS LAST
    """,
}


def get_eligible_ids(tenant_id, batch_id, stage, owner_id=None, tier_filter=None):
    """Query PG for eligible company/contact IDs for a given stage."""
    template = ELIGIBILITY_QUERIES.get(stage)
    if not template:
        return []

    params = {"tenant_id": str(tenant_id), "batch_id": str(batch_id)}

    owner_clause = ""
    if owner_id:
        if stage in ("person", "generate"):
            owner_clause = "AND ct.owner_id = :owner_id"
        else:
            owner_clause = "AND c.owner_id = :owner_id"
        params["owner_id"] = str(owner_id)

    tier_clause = ""
    if tier_filter and stage in ("l2",):
        from ..display import tier_db_values
        tier_vals = tier_db_values(tier_filter)
        if tier_vals:
            placeholders = ", ".join(f":tier_{i}" for i in range(len(tier_vals)))
            tier_clause = f"AND c.tier IN ({placeholders})"
            for i, tv in enumerate(tier_vals):
                params[f"tier_{i}"] = tv

    sql = template.format(owner_clause=owner_clause, tier_clause=tier_clause)
    rows = db.session.execute(text(sql), params).fetchall()
    return [str(row[0]) for row in rows]


def call_n8n_webhook(stage, data, timeout=120):
    """Call n8n sub-workflow via webhook. Synchronous -- waits for result."""
    base_url = current_app.config.get("N8N_BASE_URL", "https://n8n.visionvolve.com")
    path = N8N_WEBHOOK_PATHS.get(stage)
    if not path:
        raise ValueError(f"No webhook path for stage: {stage}")

    url = base_url + path
    resp = requests.post(url, json=data, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def update_run(run_id, **kwargs):
    """Update a stage_run record."""
    set_parts = []
    params = {"id": str(run_id)}
    for key, value in kwargs.items():
        set_parts.append(f"{key} = :{key}")
        params[key] = value

    if "completed_at" not in kwargs and kwargs.get("status") in ("completed", "failed", "stopped"):
        set_parts.append("completed_at = now()")

    if not set_parts:
        return

    sql = f"UPDATE stage_runs SET {', '.join(set_parts)} WHERE id = :id"
    db.session.execute(text(sql), params)
    db.session.commit()


def _check_stop_signal(run_id):
    """Check if this stage_run has been requested to stop."""
    row = db.session.execute(
        text("SELECT status FROM stage_runs WHERE id = :id"),
        {"id": str(run_id)},
    ).fetchone()
    return row and row[0] == "stopping"


def _extract_cost(result):
    """Extract enrichment cost from n8n webhook result."""
    if isinstance(result, list) and len(result) > 0:
        return float(result[0].get("enrichment_cost_usd", 0) or 0)
    elif isinstance(result, dict):
        return float(result.get("enrichment_cost_usd", 0) or 0)
    return 0


def _data_key_for_stage(stage):
    """Get the JSON key name for the entity ID sent to n8n."""
    return "contact_id" if stage in ("person", "generate") else "company_id"


# ---------------------------------------------------------------------------
# Single-stage execution (existing — for individual stage buttons)
# ---------------------------------------------------------------------------

def run_stage(app, run_id, stage, entity_ids):
    """Background thread: process entities through n8n workflow one at a time."""
    with app.app_context():
        total_cost = 0.0
        failed = 0

        update_run(run_id, status="running")

        for i, entity_id in enumerate(entity_ids):
            if _check_stop_signal(run_id):
                update_run(run_id, status="stopped", done=i, failed=failed, cost_usd=total_cost)
                logger.info("Stage run %s stopped at item %d/%d", run_id, i, len(entity_ids))
                return

            try:
                result = call_n8n_webhook(stage, {_data_key_for_stage(stage): entity_id})
                total_cost += _extract_cost(result)
                update_run(run_id, done=i + 1, cost_usd=total_cost, failed=failed)
            except Exception as e:
                failed += 1
                logger.warning("Stage %s item %s failed: %s", stage, entity_id, e)
                update_run(run_id, done=i + 1, failed=failed, cost_usd=total_cost,
                           error=str(e)[:500])

        final_status = "completed" if failed == 0 else "failed" if failed == len(entity_ids) else "completed"
        update_run(run_id, status=final_status, done=len(entity_ids), failed=failed, cost_usd=total_cost)
        logger.info("Stage run %s %s: %d done, %d failed, $%.4f cost",
                     run_id, final_status, len(entity_ids), failed, total_cost)


def start_stage_thread(app, run_id, stage, entity_ids):
    """Spawn a background thread to run a pipeline stage."""
    t = threading.Thread(
        target=run_stage,
        args=(app, run_id, stage, entity_ids),
        daemon=True,
        name=f"stage-{stage}-{run_id}",
    )
    t.start()
    return t


# ---------------------------------------------------------------------------
# Reactive stage execution (for run-all pipeline mode)
# ---------------------------------------------------------------------------

def _predecessors_terminal(predecessor_run_ids):
    """Check if all predecessor stage_runs are in a terminal state."""
    if not predecessor_run_ids:
        return True  # No predecessors = always ready

    placeholders = ", ".join(f":pred_{i}" for i in range(len(predecessor_run_ids)))
    params = {f"pred_{i}": str(rid) for i, rid in enumerate(predecessor_run_ids)}
    sql = f"""
        SELECT COUNT(*) FROM stage_runs
        WHERE id IN ({placeholders})
          AND status NOT IN ('completed', 'failed', 'stopped')
    """
    row = db.session.execute(text(sql), params).fetchone()
    return row[0] == 0


def run_stage_reactive(app, run_id, stage, tenant_id, batch_id,
                       owner_id=None, tier_filter=None,
                       predecessor_run_ids=None):
    """Background thread: reactive stage that polls for new eligible IDs.

    - Polls eligible IDs every REACTIVE_POLL_INTERVAL seconds
    - Processes new ones (skipping already-processed IDs)
    - Terminates when predecessors are all terminal AND no new eligible IDs
    - L1 has no predecessors: processes initial set, then finishes
    """
    with app.app_context():
        processed_ids = set()
        total_cost = 0.0
        done_count = 0
        failed_count = 0

        update_run(run_id, status="running")
        logger.info("Reactive stage %s started (run %s)", stage, run_id)

        while True:
            # Check stop signal
            if _check_stop_signal(run_id):
                update_run(run_id, status="stopped", done=done_count,
                           failed=failed_count, cost_usd=total_cost)
                logger.info("Reactive stage %s stopped at %d done", stage, done_count)
                return

            # Query for eligible IDs
            try:
                all_eligible = get_eligible_ids(tenant_id, batch_id, stage,
                                                owner_id, tier_filter)
            except Exception as e:
                logger.error("Reactive stage %s eligibility query failed: %s", stage, e)
                time.sleep(REACTIVE_POLL_INTERVAL)
                continue

            new_ids = [eid for eid in all_eligible if eid not in processed_ids]

            if new_ids:
                # Update total (dynamic: done + failed + new_eligible)
                new_total = done_count + failed_count + len(new_ids)
                update_run(run_id, total=new_total)

                for entity_id in new_ids:
                    # Check stop signal between items
                    if _check_stop_signal(run_id):
                        update_run(run_id, status="stopped", done=done_count,
                                   failed=failed_count, cost_usd=total_cost)
                        logger.info("Reactive stage %s stopped at %d done", stage, done_count)
                        return

                    processed_ids.add(entity_id)
                    try:
                        result = call_n8n_webhook(
                            stage, {_data_key_for_stage(stage): entity_id}
                        )
                        total_cost += _extract_cost(result)
                        done_count += 1
                        update_run(run_id, done=done_count, cost_usd=total_cost,
                                   failed=failed_count)
                    except Exception as e:
                        failed_count += 1
                        logger.warning("Reactive stage %s item %s failed: %s",
                                       stage, entity_id, e)
                        update_run(run_id, done=done_count, failed=failed_count,
                                   cost_usd=total_cost, error=str(e)[:500])
            else:
                # No new items — check termination condition
                preds_done = _predecessors_terminal(predecessor_run_ids)
                if preds_done:
                    # All predecessors are done and no new eligible items
                    final_status = "completed"
                    if failed_count > 0 and done_count == 0:
                        final_status = "failed"
                    update_run(run_id, status=final_status, done=done_count,
                               failed=failed_count, cost_usd=total_cost)
                    logger.info("Reactive stage %s %s: %d done, %d failed, $%.4f cost",
                                stage, final_status, done_count, failed_count, total_cost)
                    return

            # Sleep before next poll cycle
            time.sleep(REACTIVE_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Pipeline coordinator (for run-all)
# ---------------------------------------------------------------------------

def _update_pipeline_run(pipeline_run_id, **kwargs):
    """Update a pipeline_runs record."""
    set_parts = []
    params = {"id": str(pipeline_run_id)}
    for key, value in kwargs.items():
        set_parts.append(f"{key} = :{key}")
        params[key] = value

    if "completed_at" not in kwargs and kwargs.get("status") in ("completed", "failed", "stopped"):
        set_parts.append("completed_at = now()")

    if not set_parts:
        return

    sql = f"UPDATE pipeline_runs SET {', '.join(set_parts)} WHERE id = :id"
    db.session.execute(text(sql), params)
    db.session.commit()


def _update_pipeline_stages_json(pipeline_run_id, stage_run_map):
    """Update the stages JSONB column on pipeline_runs."""
    import json
    stages_json = json.dumps({k: str(v) for k, v in stage_run_map.items()})
    db.session.execute(
        text("UPDATE pipeline_runs SET stages = :stages::jsonb WHERE id = :id"),
        {"id": str(pipeline_run_id), "stages": stages_json},
    )
    db.session.commit()


def coordinate_pipeline(app, pipeline_run_id, stage_run_ids):
    """Coordinator thread: polls all stage statuses and marks pipeline complete.

    Args:
        pipeline_run_id: UUID of the pipeline_runs record
        stage_run_ids: dict of stage_name → stage_run_id
    """
    with app.app_context():
        logger.info("Pipeline coordinator started (run %s)", pipeline_run_id)

        while True:
            time.sleep(COORDINATOR_POLL_INTERVAL)

            try:
                # Check if pipeline was requested to stop
                prow = db.session.execute(
                    text("SELECT status FROM pipeline_runs WHERE id = :id"),
                    {"id": str(pipeline_run_id)},
                ).fetchone()

                if prow and prow[0] == "stopping":
                    # Signal all active stages to stop
                    for stage, run_id in stage_run_ids.items():
                        row = db.session.execute(
                            text("SELECT status FROM stage_runs WHERE id = :id"),
                            {"id": str(run_id)},
                        ).fetchone()
                        if row and row[0] in ("pending", "running"):
                            db.session.execute(
                                text("UPDATE stage_runs SET status = 'stopping' WHERE id = :id"),
                                {"id": str(run_id)},
                            )
                    db.session.commit()

                # Check all stage statuses
                all_terminal = True
                total_cost = 0.0
                any_failed = False

                for stage, run_id in stage_run_ids.items():
                    row = db.session.execute(
                        text("SELECT status, cost_usd FROM stage_runs WHERE id = :id"),
                        {"id": str(run_id)},
                    ).fetchone()
                    if row:
                        if row[0] not in ("completed", "failed", "stopped"):
                            all_terminal = False
                        if row[0] == "failed":
                            any_failed = True
                        total_cost += float(row[1] or 0)

                if all_terminal:
                    final_status = "stopped" if (prow and prow[0] == "stopping") else \
                                   "failed" if any_failed else "completed"
                    _update_pipeline_run(pipeline_run_id, status=final_status,
                                         cost_usd=total_cost)
                    logger.info("Pipeline %s %s, total cost $%.4f",
                                pipeline_run_id, final_status, total_cost)
                    return
                else:
                    # Update running cost
                    _update_pipeline_run(pipeline_run_id, cost_usd=total_cost)

            except Exception as e:
                logger.error("Pipeline coordinator error: %s", e)


def start_pipeline_threads(app, pipeline_run_id, stages_to_run,
                           tenant_id, batch_id, owner_id=None,
                           tier_filter=None, stage_run_ids=None):
    """Spawn reactive stage threads for all stages + coordinator thread.

    Args:
        stages_to_run: list of stage names to run (e.g. ["l1", "l2", "person", "generate"])
        stage_run_ids: dict of stage_name → stage_run_id (pre-created)
    """
    threads = {}

    for stage in stages_to_run:
        run_id = stage_run_ids[stage]
        predecessor_stages = STAGE_PREDECESSORS.get(stage, [])
        predecessor_run_ids = [stage_run_ids[ps] for ps in predecessor_stages
                               if ps in stage_run_ids]

        t = threading.Thread(
            target=run_stage_reactive,
            args=(app, run_id, stage, tenant_id, batch_id),
            kwargs={
                "owner_id": owner_id,
                "tier_filter": tier_filter,
                "predecessor_run_ids": predecessor_run_ids,
            },
            daemon=True,
            name=f"reactive-{stage}-{run_id}",
        )
        t.start()
        threads[stage] = t

    # Coordinator thread
    coord = threading.Thread(
        target=coordinate_pipeline,
        args=(app, pipeline_run_id, stage_run_ids),
        daemon=True,
        name=f"coordinator-{pipeline_run_id}",
    )
    coord.start()

    return threads
