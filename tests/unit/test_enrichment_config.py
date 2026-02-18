"""Tests for EnrichmentConfig and EnrichmentSchedule models + API endpoints."""
import json
import uuid

import pytest

from tests.conftest import auth_header


class TestEnrichmentConfigModel:
    """Test the EnrichmentConfig SQLAlchemy model."""

    def test_create_config(self, app, db, seed_tenant):
        """Create a basic enrichment config."""
        from api.models import EnrichmentConfig

        config = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="Default L1+L2",
            config=json.dumps({
                "stages": {"l1": True, "triage": True, "l2": True, "person": False},
                "boost": {"l1": False, "l2": True},
                "re_enrich": {"l1": {"enabled": True, "horizon": "30d"}},
            }),
        )
        db.session.add(config)
        db.session.commit()

        fetched = db.session.get(EnrichmentConfig, config.id)
        assert fetched is not None
        assert fetched.name == "Default L1+L2"
        assert fetched.tenant_id == seed_tenant.id

    def test_unique_name_per_tenant(self, app, db, seed_tenant):
        """Config names must be unique within a tenant."""
        from api.models import EnrichmentConfig
        from sqlalchemy.exc import IntegrityError

        c1 = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="My Config",
            config=json.dumps({"stages": {}}),
        )
        c2 = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="My Config",
            config=json.dumps({"stages": {}}),
        )
        db.session.add(c1)
        db.session.commit()
        db.session.add(c2)
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_to_dict(self, app, db, seed_tenant):
        """to_dict returns expected structure."""
        from api.models import EnrichmentConfig

        config = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="Test Config",
            description="A test config",
            config=json.dumps({"stages": {"l1": True}}),
            is_default=True,
        )
        db.session.add(config)
        db.session.commit()

        d = config.to_dict()
        assert d["name"] == "Test Config"
        assert d["description"] == "A test config"
        assert d["is_default"] is True
        assert "id" in d
        assert "config" in d
        assert "created_at" in d


class TestEnrichmentConfigAPI:
    """Test CRUD API endpoints for enrichment configs."""

    def _make_config_payload(self, name="Test Config"):
        return {
            "name": name,
            "description": "Test description",
            "config": {
                "stages": {"l1": True, "triage": True, "l2": False},
                "boost": {"l1": False},
                "soft_deps": {},
                "re_enrich": {},
            },
        }

    def test_create_config(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        payload = self._make_config_payload()
        resp = client.post("/api/enrichment-configs", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Test Config"
        assert "id" in data

    def test_list_configs(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        # Create two configs
        client.post("/api/enrichment-configs", json=self._make_config_payload("Config A"), headers=headers)
        client.post("/api/enrichment-configs", json=self._make_config_payload("Config B"), headers=headers)

        resp = client.get("/api/enrichment-configs", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 2
        names = [c["name"] for c in data]
        assert "Config A" in names
        assert "Config B" in names

    def test_get_config(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/enrichment-configs", json=self._make_config_payload(), headers=headers)
        config_id = resp.get_json()["id"]

        resp = client.get(f"/api/enrichment-configs/{config_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Test Config"

    def test_update_config(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/enrichment-configs", json=self._make_config_payload(), headers=headers)
        config_id = resp.get_json()["id"]

        resp = client.patch(
            f"/api/enrichment-configs/{config_id}",
            json={"name": "Updated Name", "config": {"stages": {"l1": True, "l2": True}}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Updated Name"

    def test_delete_config(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/enrichment-configs", json=self._make_config_payload(), headers=headers)
        config_id = resp.get_json()["id"]

        resp = client.delete(f"/api/enrichment-configs/{config_id}", headers=headers)
        assert resp.status_code == 204

        resp = client.get(f"/api/enrichment-configs/{config_id}", headers=headers)
        assert resp.status_code == 404

    def test_create_requires_name(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/enrichment-configs", json={"config": {}}, headers=headers)
        assert resp.status_code == 400

    def test_tenant_isolation(self, client, seed_tenant, seed_super_admin, db):
        """Config from one tenant not visible to another."""
        from api.models import Tenant
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/enrichment-configs", json=self._make_config_payload(), headers=headers)
        config_id = resp.get_json()["id"]

        # Create another tenant
        other = Tenant(name="Other Corp", slug="other-corp")
        db.session.add(other)
        db.session.commit()

        headers["X-Namespace"] = "other-corp"
        resp = client.get(f"/api/enrichment-configs/{config_id}", headers=headers)
        assert resp.status_code == 404

    def test_set_default(self, client, seed_tenant, seed_super_admin):
        """Setting is_default on one config clears it on others."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp1 = client.post("/api/enrichment-configs",
                            json={**self._make_config_payload("Config A"), "is_default": True},
                            headers=headers)
        id1 = resp1.get_json()["id"]

        resp2 = client.post("/api/enrichment-configs",
                            json={**self._make_config_payload("Config B"), "is_default": True},
                            headers=headers)
        id2 = resp2.get_json()["id"]

        # Config A should no longer be default
        resp = client.get(f"/api/enrichment-configs/{id1}", headers=headers)
        assert resp.get_json()["is_default"] is False

        resp = client.get(f"/api/enrichment-configs/{id2}", headers=headers)
        assert resp.get_json()["is_default"] is True


class TestEnrichmentScheduleModel:
    """Test the EnrichmentSchedule model."""

    def test_create_schedule(self, app, db, seed_tenant):
        from api.models import EnrichmentConfig, EnrichmentSchedule

        config = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="Quarterly L1",
            config=json.dumps({"stages": {"l1": True}}),
        )
        db.session.add(config)
        db.session.commit()

        schedule = EnrichmentSchedule(
            tenant_id=seed_tenant.id,
            config_id=config.id,
            schedule_type="cron",
            cron_expression="0 2 1 */3 *",  # quarterly at 2am
            is_active=True,
        )
        db.session.add(schedule)
        db.session.commit()

        fetched = db.session.get(EnrichmentSchedule, schedule.id)
        assert fetched is not None
        assert fetched.schedule_type == "cron"
        assert fetched.cron_expression == "0 2 1 */3 *"
        assert fetched.is_active

    def test_schedule_to_dict(self, app, db, seed_tenant):
        from api.models import EnrichmentConfig, EnrichmentSchedule

        config = EnrichmentConfig(
            tenant_id=seed_tenant.id,
            name="Monthly",
            config=json.dumps({"stages": {"l1": True}}),
        )
        db.session.add(config)
        db.session.commit()

        schedule = EnrichmentSchedule(
            tenant_id=seed_tenant.id,
            config_id=config.id,
            schedule_type="on_new_entity",
            is_active=True,
        )
        db.session.add(schedule)
        db.session.commit()

        d = schedule.to_dict()
        assert d["schedule_type"] == "on_new_entity"
        assert d["config_id"] == str(config.id)
        assert d["is_active"] is True
        assert "id" in d


class TestEnrichmentScheduleAPI:
    """Test CRUD API endpoints for enrichment schedules."""

    def _create_config(self, client, headers, name="Sched Config"):
        resp = client.post("/api/enrichment-configs", json={
            "name": name,
            "config": {"stages": {"l1": True}},
        }, headers=headers)
        return resp.get_json()["id"]

    def test_create_schedule(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        config_id = self._create_config(client, headers)

        resp = client.post("/api/enrichment-schedules", json={
            "config_id": config_id,
            "schedule_type": "cron",
            "cron_expression": "0 2 * * 1",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["schedule_type"] == "cron"

    def test_list_schedules(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        config_id = self._create_config(client, headers)

        client.post("/api/enrichment-schedules", json={
            "config_id": config_id,
            "schedule_type": "cron",
            "cron_expression": "0 2 * * 1",
        }, headers=headers)

        resp = client.get("/api/enrichment-schedules", headers=headers)
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 1

    def test_delete_schedule(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        config_id = self._create_config(client, headers)

        resp = client.post("/api/enrichment-schedules", json={
            "config_id": config_id,
            "schedule_type": "on_new_entity",
        }, headers=headers)
        sched_id = resp.get_json()["id"]

        resp = client.delete(f"/api/enrichment-schedules/{sched_id}", headers=headers)
        assert resp.status_code == 204

    def test_toggle_schedule(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        config_id = self._create_config(client, headers)

        resp = client.post("/api/enrichment-schedules", json={
            "config_id": config_id,
            "schedule_type": "cron",
            "cron_expression": "0 0 * * *",
        }, headers=headers)
        sched_id = resp.get_json()["id"]

        resp = client.patch(f"/api/enrichment-schedules/{sched_id}",
                            json={"is_active": False}, headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["is_active"] is False
