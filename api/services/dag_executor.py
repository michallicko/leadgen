"""DAG-based pipeline executor using entity_stage_completions for eligibility.

Replaces the hardcoded ELIGIBILITY_QUERIES with a generic, completion-record-based
eligibility builder. Each stage's eligible entities are determined by checking that
all required dependencies (hard + activated soft) have 'completed' rows.
"""

import logging
import threading
import time
import uuid as _uuid_mod

from flask import current_app
from sqlalchemy import text

from ..models import db
from .stage_registry import STAGE_REGISTRY, get_stage, resolve_deps, topo_sort

logger = logging.getLogger(__name__)

REACTIVE_POLL_INTERVAL = 15  # seconds between re-querying eligible IDs


def record_completion(tenant_id, batch_id, pipeline_run_id, entity_type,
                      entity_id, stage, status="completed", cost_usd=0,
                      error=None):
    """Insert an entity_stage_completions record.

    This is the core dual-write function: called after every entity processing
    to record what stage completed (or failed/skipped) for which entity.
    """
    row_id = str(_uuid_mod.uuid4())
    params = {
        "id": row_id,
        "tenant_id": str(tenant_id),
        "batch_id": str(batch_id),
        "pipeline_run_id": str(pipeline_run_id) if pipeline_run_id else None,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "stage": stage,
        "status": status,
        "cost_usd": cost_usd or 0,
        "error": str(error)[:500] if error else None,
    }
    try:
        # Try PG upsert first
        db.session.execute(
            text("""
                INSERT INTO entity_stage_completions
                    (id, tenant_id, batch_id, pipeline_run_id, entity_type,
                     entity_id, stage, status, cost_usd, error)
                VALUES (:id, :tenant_id, :batch_id, :pipeline_run_id, :entity_type,
                        :entity_id, :stage, :status, :cost_usd, :error)
                ON CONFLICT (pipeline_run_id, entity_id, stage) DO UPDATE
                SET status = EXCLUDED.status, cost_usd = EXCLUDED.cost_usd,
                    error = EXCLUDED.error, completed_at = now()
            """),
            params,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Fallback for SQLite (no ON CONFLICT with partial unique)
        try:
            db.session.execute(
                text("""
                    INSERT INTO entity_stage_completions
                        (id, tenant_id, batch_id, pipeline_run_id, entity_type,
                         entity_id, stage, status, cost_usd, error)
                    VALUES (:id, :tenant_id, :batch_id, :pipeline_run_id, :entity_type,
                            :entity_id, :stage, :status, :cost_usd, :error)
                """),
                params,
            )
            db.session.commit()
        except Exception as e2:
            logger.warning("Failed to record completion for %s/%s/%s: %s",
                            entity_id, stage, status, e2)
            db.session.rollback()


def build_eligibility_query(stage_code, pipeline_run_id, tenant_id, batch_id,
                            owner_id=None, tier_filter=None,
                            soft_deps_enabled=None):
    """Build SQL + params to find entities eligible for a given stage.

    An entity is eligible when:
    1. Belongs to correct tenant/batch
    2. Not already completed/failed/skipped for this stage in this pipeline run
    3. All hard_deps have 'completed' rows for this entity (or its parent company)
    4. All activated soft_deps have 'completed' rows
    5. Country gate passes (if applicable)
    """
    stage_def = get_stage(stage_code)
    if not stage_def:
        return None, {}

    entity_type = stage_def["entity_type"]
    deps = resolve_deps(stage_code, soft_deps_enabled)

    params = {
        "tenant_id": str(tenant_id),
        "batch_id": str(batch_id),
        "pipeline_run_id": str(pipeline_run_id) if pipeline_run_id else None,
        "stage": stage_code,
    }

    if entity_type == "company":
        base_table = "companies"
        id_col = "e.id"
        entity_type_lit = "'company'"
    else:
        # contact entity_type
        base_table = "contacts"
        id_col = "e.id"
        entity_type_lit = "'contact'"

    # Base: select entities in this tenant+batch
    sql_parts = [f"SELECT {id_col} FROM {base_table} e"]
    where_clauses = [
        "e.tenant_id = :tenant_id",
        "e.batch_id = :batch_id",
    ]

    # Not already completed for this stage+run
    where_clauses.append(f"""
        NOT EXISTS (
            SELECT 1 FROM entity_stage_completions esc_self
            WHERE esc_self.entity_id = {id_col}
              AND esc_self.stage = :stage
              AND esc_self.pipeline_run_id = :pipeline_run_id
        )
    """)

    # Dependency checks
    for i, dep in enumerate(deps):
        dep_def = get_stage(dep)
        if not dep_def:
            continue

        dep_entity_type = dep_def["entity_type"]
        param_dep = f"dep_{i}"
        params[param_dep] = dep

        if dep_entity_type == entity_type:
            # Same entity type: check entity_id directly
            where_clauses.append(f"""
                EXISTS (
                    SELECT 1 FROM entity_stage_completions esc_{i}
                    WHERE esc_{i}.entity_id = {id_col}
                      AND esc_{i}.stage = :{param_dep}
                      AND esc_{i}.status = 'completed'
                      AND esc_{i}.pipeline_run_id = :pipeline_run_id
                )
            """)
        elif dep_entity_type == "company" and entity_type == "contact":
            # Cross-entity: contact depends on company stage
            # Check via contacts.company_id
            where_clauses.append(f"""
                EXISTS (
                    SELECT 1 FROM entity_stage_completions esc_{i}
                    WHERE esc_{i}.entity_id = e.company_id
                      AND esc_{i}.stage = :{param_dep}
                      AND esc_{i}.status = 'completed'
                      AND esc_{i}.pipeline_run_id = :pipeline_run_id
                )
            """)

    # Owner filter
    if owner_id:
        where_clauses.append("e.owner_id = :owner_id")
        params["owner_id"] = str(owner_id)

    # Tier filter (company stages only)
    if tier_filter and entity_type == "company":
        from ..display import tier_db_values
        tier_vals = tier_db_values(tier_filter)
        if tier_vals:
            placeholders = ", ".join(f":tier_{i}" for i in range(len(tier_vals)))
            where_clauses.append(f"e.tier IN ({placeholders})")
            for i, tv in enumerate(tier_vals):
                params[f"tier_{i}"] = tv

    # Country gate
    country_gate = stage_def.get("country_gate")
    if country_gate:
        country_conditions = []
        countries = country_gate.get("countries", [])
        tlds = country_gate.get("tlds", [])

        if entity_type == "company":
            if countries:
                c_placeholders = ", ".join(f":cg_country_{i}" for i in range(len(countries)))
                country_conditions.append(f"e.hq_country IN ({c_placeholders})")
                for i, c in enumerate(countries):
                    params[f"cg_country_{i}"] = c
            if tlds:
                for i, tld in enumerate(tlds):
                    country_conditions.append(f"e.domain LIKE :cg_tld_{i}")
                    params[f"cg_tld_{i}"] = f"%{tld}"

            # ISIR also needs ICO
            if stage_code == "isir":
                country_conditions.append("e.ico IS NOT NULL")

            if country_conditions:
                where_clauses.append(f"({' OR '.join(country_conditions)})")

    sql = " ".join(sql_parts)
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY e.name" if entity_type == "company" else " ORDER BY e.last_name, e.first_name"

    return sql, params


def get_dag_eligible_ids(stage_code, pipeline_run_id, tenant_id, batch_id,
                         owner_id=None, tier_filter=None,
                         soft_deps_enabled=None):
    """Query PG for eligible entity IDs using DAG-based eligibility."""
    sql, params = build_eligibility_query(
        stage_code, pipeline_run_id, tenant_id, batch_id,
        owner_id, tier_filter, soft_deps_enabled,
    )
    if sql is None:
        return []

    rows = db.session.execute(text(sql), params).fetchall()
    return [str(row[0]) for row in rows]


def count_dag_eligible(stage_code, pipeline_run_id, tenant_id, batch_id,
                       owner_id=None, tier_filter=None,
                       soft_deps_enabled=None):
    """Count eligible entities without loading IDs."""
    sql, params = build_eligibility_query(
        stage_code, pipeline_run_id, tenant_id, batch_id,
        owner_id, tier_filter, soft_deps_enabled,
    )
    if sql is None:
        return 0

    count_sql = f"SELECT COUNT(*) FROM ({sql}) sub"
    row = db.session.execute(text(count_sql), params).fetchone()
    return row[0] if row else 0


def auto_skip_country_gated(stage_code, pipeline_run_id, tenant_id, batch_id):
    """Batch-insert 'skipped' rows for entities that don't match a country gate.

    Called at stage thread startup. This unblocks downstream stages immediately
    for entities that this stage doesn't apply to.
    """
    stage_def = get_stage(stage_code)
    if not stage_def or not stage_def.get("country_gate"):
        return 0

    entity_type = stage_def["entity_type"]
    if entity_type != "company":
        return 0  # Country gates only apply to companies currently

    country_gate = stage_def["country_gate"]
    countries = country_gate.get("countries", [])
    tlds = country_gate.get("tlds", [])

    # Build the "does NOT match gate" condition
    gate_conditions = []
    params = {
        "tenant_id": str(tenant_id),
        "batch_id": str(batch_id),
        "pipeline_run_id": str(pipeline_run_id) if pipeline_run_id else None,
        "stage": stage_code,
    }

    if countries:
        c_placeholders = ", ".join(f":cg_{i}" for i in range(len(countries)))
        gate_conditions.append(f"c.hq_country IN ({c_placeholders})")
        for i, c in enumerate(countries):
            params[f"cg_{i}"] = c
    if tlds:
        for i, tld in enumerate(tlds):
            gate_conditions.append(f"c.domain LIKE :tld_{i}")
            params[f"tld_{i}"] = f"%{tld}"

    if stage_code == "isir":
        gate_conditions.append("c.ico IS NOT NULL")

    if not gate_conditions:
        return 0

    gate_expr = " OR ".join(gate_conditions)

    # Insert 'skipped' for companies that do NOT match and don't already have a row
    sql = f"""
        INSERT INTO entity_stage_completions
            (tenant_id, batch_id, pipeline_run_id, entity_type, entity_id, stage, status)
        SELECT c.tenant_id, c.batch_id, :pipeline_run_id, 'company', c.id, :stage, 'skipped'
        FROM companies c
        WHERE c.tenant_id = :tenant_id AND c.batch_id = :batch_id
          AND NOT ({gate_expr})
          AND NOT EXISTS (
              SELECT 1 FROM entity_stage_completions esc
              WHERE esc.entity_id = c.id AND esc.stage = :stage
                AND esc.pipeline_run_id = :pipeline_run_id
          )
    """

    try:
        result = db.session.execute(text(sql), params)
        db.session.commit()
        count = result.rowcount
        if count > 0:
            logger.info("Auto-skipped %d companies for stage %s (country gate)",
                        count, stage_code)
        return count
    except Exception as e:
        logger.warning("Auto-skip failed for %s: %s", stage_code, e)
        db.session.rollback()
        return 0


# ---------------------------------------------------------------------------
# DAG-aware reactive stage execution
# ---------------------------------------------------------------------------

def _check_stop_signal(run_id):
    """Check if a stage_run has been requested to stop."""
    row = db.session.execute(
        text("SELECT status FROM stage_runs WHERE id = :id"),
        {"id": str(run_id)},
    ).fetchone()
    return row and row[0] == "stopping"


def _get_entity_name(stage_code, entity_id, tenant_id):
    """Look up display name for the entity being processed."""
    stage_def = get_stage(stage_code)
    if not stage_def:
        return str(entity_id)

    try:
        if stage_def["entity_type"] == "contact":
            row = db.session.execute(
                text("SELECT first_name, last_name FROM contacts WHERE id = :id AND tenant_id = :t"),
                {"id": str(entity_id), "t": str(tenant_id)},
            ).fetchone()
            if row:
                return f"{row[0] or ''} {row[1] or ''}".strip() or str(entity_id)
        else:
            row = db.session.execute(
                text("SELECT name FROM companies WHERE id = :id AND tenant_id = :t"),
                {"id": str(entity_id), "t": str(tenant_id)},
            ).fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    return str(entity_id)


def _update_stage_run(run_id, **kwargs):
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


def _update_current_item(run_id, entity_name, status="processing"):
    """Store the current item being processed in the stage_run config."""
    try:
        import json as _json
        row = db.session.execute(
            text("SELECT config FROM stage_runs WHERE id = :id"),
            {"id": str(run_id)},
        ).fetchone()
        if row:
            config = _json.loads(row[0] or "{}")
            config["current_item"] = {"name": entity_name, "status": status}
            if status != "processing":
                recent = config.get("recent_items", [])
                recent.append({"name": entity_name, "status": status})
                if len(recent) > 20:
                    recent = recent[-20:]
                config["recent_items"] = recent
            db.session.execute(
                text("UPDATE stage_runs SET config = :config WHERE id = :id"),
                {"id": str(run_id), "config": _json.dumps(config)},
            )
            db.session.commit()
    except Exception:
        pass


def run_dag_stage(app, run_id, stage_code, pipeline_run_id, tenant_id, batch_id,
                  owner_id=None, tier_filter=None, soft_deps_enabled=None,
                  predecessor_run_ids=None, sample_size=None):
    """Background thread: DAG-aware reactive stage execution.

    Like run_stage_reactive but uses completion-record-based eligibility
    and records completions after each entity.
    """
    from .pipeline_engine import _process_entity, _extract_cost

    stage_def = get_stage(stage_code)
    if not stage_def:
        _update_stage_run(run_id, status="failed", error=f"Unknown stage: {stage_code}")
        return

    entity_type = stage_def["entity_type"]

    with app.app_context():
        # Auto-skip entities that don't match country gate
        auto_skip_country_gated(stage_code, pipeline_run_id, tenant_id, batch_id)

        processed_ids = set()
        total_cost = 0.0
        done_count = 0
        failed_count = 0
        sample_remaining = sample_size

        _update_stage_run(run_id, status="running")
        logger.info("DAG stage %s started (run %s, pipeline %s)", stage_code, run_id, pipeline_run_id)

        while True:
            if _check_stop_signal(run_id):
                _update_stage_run(run_id, status="stopped", done=done_count,
                                  failed=failed_count, cost_usd=total_cost)
                return

            if sample_remaining is not None and sample_remaining <= 0:
                _update_stage_run(run_id, status="completed", done=done_count,
                                  failed=failed_count, cost_usd=total_cost)
                return

            # Query eligible entities using DAG-based eligibility
            try:
                all_eligible = get_dag_eligible_ids(
                    stage_code, pipeline_run_id, tenant_id, batch_id,
                    owner_id, tier_filter, soft_deps_enabled,
                )
            except Exception as e:
                logger.error("DAG stage %s eligibility query failed: %s", stage_code, e)
                db.session.rollback()
                time.sleep(REACTIVE_POLL_INTERVAL)
                continue

            new_ids = [eid for eid in all_eligible if eid not in processed_ids]

            if sample_remaining is not None and len(new_ids) > sample_remaining:
                new_ids = new_ids[:sample_remaining]

            if new_ids:
                new_total = done_count + failed_count + len(new_ids)
                _update_stage_run(run_id, total=new_total)

                for entity_id in new_ids:
                    if _check_stop_signal(run_id):
                        _update_stage_run(run_id, status="stopped", done=done_count,
                                          failed=failed_count, cost_usd=total_cost)
                        return

                    processed_ids.add(entity_id)
                    entity_name = _get_entity_name(stage_code, entity_id, tenant_id)
                    _update_current_item(run_id, entity_name, "processing")

                    try:
                        result = _process_entity(stage_code, entity_id, tenant_id)
                        cost = _extract_cost(result)
                        total_cost += cost
                        done_count += 1

                        # Record completion
                        record_completion(
                            tenant_id, batch_id, pipeline_run_id,
                            entity_type, entity_id, stage_code,
                            status="completed", cost_usd=cost,
                        )

                        _update_current_item(run_id, entity_name, "ok")
                        _update_stage_run(run_id, done=done_count, cost_usd=total_cost,
                                          failed=failed_count)
                    except Exception as e:
                        db.session.rollback()
                        failed_count += 1

                        # Record failure
                        record_completion(
                            tenant_id, batch_id, pipeline_run_id,
                            entity_type, entity_id, stage_code,
                            status="failed", error=str(e),
                        )

                        _update_current_item(run_id, entity_name, "failed")
                        logger.warning("DAG stage %s item %s failed: %s",
                                       stage_code, entity_id, e)
                        _update_stage_run(run_id, done=done_count, failed=failed_count,
                                          cost_usd=total_cost, error=str(e)[:500])

                    if sample_remaining is not None:
                        sample_remaining -= 1
                        if sample_remaining <= 0:
                            break
            else:
                # No new items — check termination
                preds_done = _predecessors_terminal(predecessor_run_ids)
                if preds_done:
                    final_status = "completed" if done_count > 0 or failed_count == 0 else "failed"
                    _update_stage_run(run_id, status=final_status, done=done_count,
                                      failed=failed_count, cost_usd=total_cost)
                    logger.info("DAG stage %s %s: %d done, %d failed, $%.4f",
                                stage_code, final_status, done_count, failed_count, total_cost)
                    return

            time.sleep(REACTIVE_POLL_INTERVAL)


def _predecessors_terminal(predecessor_run_ids):
    """Check if all predecessor stage_runs are in a terminal state."""
    if not predecessor_run_ids:
        return True

    placeholders = ", ".join(f":pred_{i}" for i in range(len(predecessor_run_ids)))
    params = {f"pred_{i}": str(rid) for i, rid in enumerate(predecessor_run_ids)}
    sql = f"""
        SELECT COUNT(*) FROM stage_runs
        WHERE id IN ({placeholders})
          AND status NOT IN ('completed', 'failed', 'stopped')
    """
    row = db.session.execute(text(sql), params).fetchone()
    return row[0] == 0


# ---------------------------------------------------------------------------
# DAG pipeline coordinator
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


def coordinate_dag_pipeline(app, pipeline_run_id, stage_run_ids):
    """Coordinator thread: polls all stage statuses and marks pipeline complete."""
    with app.app_context():
        logger.info("DAG pipeline coordinator started (run %s)", pipeline_run_id)

        while True:
            time.sleep(10)

            try:
                # Check if pipeline was requested to stop
                prow = db.session.execute(
                    text("SELECT status FROM pipeline_runs WHERE id = :id"),
                    {"id": str(pipeline_run_id)},
                ).fetchone()

                if prow and prow[0] == "stopping":
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
                    logger.info("DAG pipeline %s %s, total cost $%.4f",
                                pipeline_run_id, final_status, total_cost)
                    return
                else:
                    _update_pipeline_run(pipeline_run_id, cost_usd=total_cost)

            except Exception as e:
                logger.error("DAG pipeline coordinator error: %s", e)


def start_dag_pipeline(app, pipeline_run_id, stages_to_run, tenant_id, batch_id,
                       owner_id=None, tier_filter=None, stage_run_ids=None,
                       soft_deps_enabled=None, sample_size=None):
    """Spawn DAG-aware reactive stage threads for all stages + coordinator.

    Unlike start_pipeline_threads, this uses completion-record-based eligibility
    and records completions after each entity.
    """
    sorted_stages = topo_sort(stages_to_run, soft_deps_enabled)
    threads = {}

    for stage_code in sorted_stages:
        run_id = stage_run_ids[stage_code]

        # Build predecessor run IDs from the stage's deps
        deps = resolve_deps(stage_code, soft_deps_enabled)
        predecessor_run_ids = [stage_run_ids[dep] for dep in deps if dep in stage_run_ids]

        t = threading.Thread(
            target=run_dag_stage,
            args=(app, run_id, stage_code, pipeline_run_id, tenant_id, batch_id),
            kwargs={
                "owner_id": owner_id,
                "tier_filter": tier_filter,
                "soft_deps_enabled": soft_deps_enabled,
                "predecessor_run_ids": predecessor_run_ids,
                "sample_size": sample_size,
            },
            daemon=True,
            name=f"dag-{stage_code}-{run_id}",
        )
        t.start()
        threads[stage_code] = t

    # Coordinator thread
    coord = threading.Thread(
        target=coordinate_dag_pipeline,
        args=(app, pipeline_run_id, stage_run_ids),
        daemon=True,
        name=f"dag-coord-{pipeline_run_id}",
    )
    coord.start()

    return threads
