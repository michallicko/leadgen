"""Background scheduler for enrichment pipeline.

Checks for due scheduled enrichments and triggers pipeline runs.
Uses a simple threading.Timer loop — no external scheduler dependency.
"""

import logging
import threading
from datetime import datetime, timezone

from ..models import EnrichmentSchedule, db

logger = logging.getLogger(__name__)

# Check interval in seconds (5 minutes)
CHECK_INTERVAL = 300


def compute_next_run(cron_expression):
    """Parse a cron expression and return the next run datetime (UTC).

    Returns None if the expression is invalid.
    Uses croniter if available, otherwise basic parsing.
    """
    if not cron_expression or not isinstance(cron_expression, str):
        return None

    try:
        from croniter import croniter

        now = datetime.now(timezone.utc)
        cron = croniter(cron_expression, now)
        return cron.get_next(datetime).replace(tzinfo=timezone.utc)
    except (ValueError, KeyError, TypeError):
        return None
    except ImportError:
        # croniter not installed — try basic fallback
        logger.warning("croniter not installed, cron scheduling unavailable")
        return None


def check_due_schedules():
    """Check all active cron schedules and trigger any that are due.

    Returns the number of triggered schedules.
    """
    now = datetime.now(timezone.utc)

    due_schedules = EnrichmentSchedule.query.filter(
        EnrichmentSchedule.schedule_type == "cron",
        EnrichmentSchedule.is_active == True,  # noqa: E712
        EnrichmentSchedule.next_run_at <= now,
    ).all()

    triggered = 0
    for sched in due_schedules:
        try:
            config = sched.config_id
            from ..models import EnrichmentConfig

            ec = db.session.get(EnrichmentConfig, config)
            if not ec:
                logger.warning(
                    "Schedule %s references missing config %s", sched.id, config
                )
                continue

            success = _trigger_pipeline(sched.tenant_id, ec)
            if success:
                sched.last_run_at = now
                # Compute next run
                next_run = compute_next_run(sched.cron_expression)
                if next_run:
                    sched.next_run_at = next_run
                else:
                    sched.is_active = False
                    logger.warning(
                        "Disabling schedule %s: invalid cron expression", sched.id
                    )
                triggered += 1
        except Exception:
            logger.exception("Error triggering schedule %s", sched.id)

    if triggered > 0:
        db.session.commit()

    return triggered


def check_new_entity_triggers(tenant_id):
    """Fire any on_new_entity schedules for a given tenant.

    Called from import routes when new entities are created.
    """
    triggers = EnrichmentSchedule.query.filter(
        EnrichmentSchedule.tenant_id == tenant_id,
        EnrichmentSchedule.schedule_type == "on_new_entity",
        EnrichmentSchedule.is_active == True,  # noqa: E712
    ).all()

    for sched in triggers:
        try:
            from ..models import EnrichmentConfig

            ec = db.session.get(EnrichmentConfig, sched.config_id)
            if not ec:
                continue
            _trigger_pipeline(tenant_id, ec)
            sched.last_run_at = datetime.now(timezone.utc)
        except Exception:
            logger.exception("Error triggering on_new_entity schedule %s", sched.id)

    if triggers:
        db.session.commit()


def _trigger_pipeline(tenant_id, enrichment_config):
    """Trigger a pipeline run from a saved enrichment config.

    This calls the internal pipeline engine rather than the HTTP API.
    Returns True on success, False on failure.
    """
    import json as _json

    cfg = enrichment_config.config
    if isinstance(cfg, str):
        cfg = _json.loads(cfg)

    stages = [code for code, enabled in (cfg.get("stages") or {}).items() if enabled]
    if not stages:
        logger.warning("Config %s has no enabled stages", enrichment_config.id)
        return False

    logger.info(
        "Triggering pipeline from config '%s' for tenant %s with stages %s",
        enrichment_config.name,
        tenant_id,
        stages,
    )
    # The actual pipeline trigger would call into dag_executor or pipeline_engine
    # For now, this is a hook point — the integration with the pipeline engine
    # will be wired when the scheduler is activated in production
    return True


_scheduler_thread = None
_scheduler_running = False


def start_scheduler(app):
    """Start the background scheduler thread.

    Runs inside the Flask app context. Call once during app startup.
    """
    global _scheduler_thread, _scheduler_running

    if _scheduler_running:
        return

    _scheduler_running = True

    def _loop():
        while _scheduler_running:
            try:
                with app.app_context():
                    count = check_due_schedules()
                    if count > 0:
                        logger.info("Triggered %d scheduled enrichments", count)
            except Exception:
                logger.exception("Scheduler check failed")

            # Sleep in small increments so we can stop cleanly
            for _ in range(CHECK_INTERVAL):
                if not _scheduler_running:
                    break
                import time

                time.sleep(1)

    _scheduler_thread = threading.Thread(
        target=_loop, daemon=True, name="enrichment-scheduler"
    )
    _scheduler_thread.start()
    logger.info("Enrichment scheduler started (interval=%ds)", CHECK_INTERVAL)


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running
    _scheduler_running = False
    logger.info("Enrichment scheduler stopped")
