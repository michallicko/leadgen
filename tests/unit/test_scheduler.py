"""Tests for the enrichment scheduler background service."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest


class TestSchedulerNextRun:
    """Test cron expression → next run time calculation."""

    def test_parse_weekly_cron(self, app):
        from api.services.scheduler import compute_next_run

        # Every Monday at 2am
        next_run = compute_next_run("0 2 * * 1")
        assert next_run is not None
        assert next_run > datetime.now(timezone.utc)
        assert next_run.weekday() == 0  # Monday

    def test_parse_quarterly_cron(self, app):
        from api.services.scheduler import compute_next_run

        # 1st of every 3rd month at 2am
        next_run = compute_next_run("0 2 1 */3 *")
        assert next_run is not None
        assert next_run > datetime.now(timezone.utc)

    def test_invalid_cron_returns_none(self, app):
        from api.services.scheduler import compute_next_run

        assert compute_next_run("not a cron") is None
        assert compute_next_run("") is None
        assert compute_next_run(None) is None


class TestSchedulerCheck:
    """Test the check_due_schedules function."""

    def test_due_cron_schedule_triggers_run(self, app, db, seed_tenant):
        from api.models import EnrichmentConfig, EnrichmentSchedule
        from api.services.scheduler import check_due_schedules

        config = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="Auto L1",
            config=json.dumps({"stages": {"l1": True}}),
        )
        db.session.add(config)
        db.session.commit()

        # Schedule with next_run in the past → should be due
        sched = EnrichmentSchedule(
            tenant_id=seed_tenant.id,
            config_id=config.id,
            schedule_type="cron",
            cron_expression="0 2 * * 1",
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.session.add(sched)
        db.session.commit()

        with patch("api.services.scheduler._trigger_pipeline") as mock_trigger:
            mock_trigger.return_value = True
            triggered = check_due_schedules()

        assert triggered == 1
        # next_run should be updated
        db.session.refresh(sched)
        assert sched.last_run_at is not None

    def test_inactive_schedule_not_triggered(self, app, db, seed_tenant):
        from api.models import EnrichmentConfig, EnrichmentSchedule
        from api.services.scheduler import check_due_schedules

        config = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="Disabled Config",
            config=json.dumps({"stages": {"l1": True}}),
        )
        db.session.add(config)
        db.session.commit()

        sched = EnrichmentSchedule(
            tenant_id=seed_tenant.id,
            config_id=config.id,
            schedule_type="cron",
            cron_expression="0 2 * * 1",
            is_active=False,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.session.add(sched)
        db.session.commit()

        with patch("api.services.scheduler._trigger_pipeline") as mock_trigger:
            triggered = check_due_schedules()

        assert triggered == 0
        mock_trigger.assert_not_called()

    def test_future_schedule_not_triggered(self, app, db, seed_tenant):
        from api.models import EnrichmentConfig, EnrichmentSchedule
        from api.services.scheduler import check_due_schedules

        config = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="Future Config",
            config=json.dumps({"stages": {"l1": True}}),
        )
        db.session.add(config)
        db.session.commit()

        sched = EnrichmentSchedule(
            tenant_id=seed_tenant.id,
            config_id=config.id,
            schedule_type="cron",
            cron_expression="0 2 * * 1",
            is_active=True,
            next_run_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.session.add(sched)
        db.session.commit()

        with patch("api.services.scheduler._trigger_pipeline") as mock_trigger:
            triggered = check_due_schedules()

        assert triggered == 0
        mock_trigger.assert_not_called()


class TestOnNewEntityTrigger:
    """Test the on_new_entity trigger type."""

    def test_check_new_entity_trigger(self, app, db, seed_tenant):
        from api.models import EnrichmentConfig, EnrichmentSchedule
        from api.services.scheduler import check_new_entity_triggers

        config = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="Auto on Import",
            config=json.dumps({"stages": {"l1": True}}),
        )
        db.session.add(config)
        db.session.commit()

        sched = EnrichmentSchedule(
            tenant_id=seed_tenant.id,
            config_id=config.id,
            schedule_type="on_new_entity",
            is_active=True,
        )
        db.session.add(sched)
        db.session.commit()

        with patch("api.services.scheduler._trigger_pipeline") as mock_trigger:
            mock_trigger.return_value = True
            check_new_entity_triggers(seed_tenant.id)

        mock_trigger.assert_called_once()
