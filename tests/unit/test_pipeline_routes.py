"""Tests for the pipeline start/stop/status API endpoints + run-all/stop-all."""

import uuid
from unittest.mock import patch

import pytest

from tests.conftest import auth_header


def _uuid():
    return str(uuid.uuid4())


@pytest.fixture
def seed_pipeline_data(db, seed_tenant, seed_super_admin):
    """Create batch, owner, and some companies for pipeline tests."""
    from api.models import Batch, Company, Contact, Owner

    owner = Owner(tenant_id=seed_tenant.id, name="Michal", is_active=True)
    db.session.add(owner)
    db.session.flush()

    batch = Batch(tenant_id=seed_tenant.id, name="batch-test", is_active=True)
    db.session.add(batch)
    db.session.flush()

    companies = []
    for i in range(5):
        c = Company(
            tenant_id=seed_tenant.id,
            name=f"Company {i}",
            domain=f"company{i}.com",
            batch_id=batch.id,
            owner_id=owner.id,
            status="new",
        )
        db.session.add(c)
        companies.append(c)

    # Add some ineligible companies
    c_passed = Company(
        tenant_id=seed_tenant.id,
        name="Already Passed",
        domain="passed.com",
        batch_id=batch.id,
        owner_id=owner.id,
        status="triage_passed",
    )
    db.session.add(c_passed)

    # Add enriched_l2 company with contacts for person/generate stages
    c_enriched = Company(
        tenant_id=seed_tenant.id,
        name="Enriched Co",
        domain="enriched.com",
        batch_id=batch.id,
        owner_id=owner.id,
        status="enriched_l2",
    )
    db.session.add(c_enriched)
    db.session.flush()

    # Add contacts for person stage
    contacts = []
    for i in range(3):
        ct = Contact(
            tenant_id=seed_tenant.id,
            first_name=f"Contact", last_name=f"{i}",
            company_id=c_enriched.id,
            batch_id=batch.id,
            owner_id=owner.id,
            processed_enrich=False,
        )
        db.session.add(ct)
        contacts.append(ct)

    # Add contacts eligible for generate stage (processed, not_started)
    ct_gen = Contact(
        tenant_id=seed_tenant.id,
        first_name="Gen", last_name="Contact",
        company_id=c_enriched.id,
        batch_id=batch.id,
        owner_id=owner.id,
        processed_enrich=True,
        message_status="not_started",
        contact_score=90,
    )
    db.session.add(ct_gen)
    contacts.append(ct_gen)

    db.session.commit()
    return {
        "tenant": seed_tenant,
        "batch": batch,
        "owner": owner,
        "companies": companies,
        "contacts": contacts,
        "c_passed": c_passed,
        "c_enriched": c_enriched,
    }


class TestPipelineStart:
    def test_start_l1_success(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        with patch("api.routes.pipeline_routes.start_stage_thread") as mock_thread:
            resp = client.post(
                "/api/pipeline/start",
                json={
                    "stage": "l1",
                    "batch_name": "batch-test",
                    "owner": "Michal",
                },
                headers=headers,
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert "run_id" in data
        assert data["total"] == 5  # 5 companies with status=new
        mock_thread.assert_called_once()

    def test_start_l2_success(self, client, seed_pipeline_data):
        """L2 is now available — should work for triage_passed companies."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        with patch("api.routes.pipeline_routes.start_stage_thread") as mock_thread:
            resp = client.post(
                "/api/pipeline/start",
                json={
                    "stage": "l2",
                    "batch_name": "batch-test",
                },
                headers=headers,
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total"] == 1  # 1 company with status=triage_passed
        mock_thread.assert_called_once()

    def test_start_person_success(self, client, seed_pipeline_data):
        """Person stage should find contacts with enriched_l2 company."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        with patch("api.routes.pipeline_routes.start_stage_thread") as mock_thread:
            resp = client.post(
                "/api/pipeline/start",
                json={
                    "stage": "person",
                    "batch_name": "batch-test",
                },
                headers=headers,
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total"] == 3  # 3 contacts not yet processed
        mock_thread.assert_called_once()

    def test_start_generate_rejected(self, client, seed_pipeline_data):
        """Generate stage was removed — should be rejected as invalid."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/start",
            json={
                "stage": "generate",
                "batch_name": "batch-test",
            },
            headers=headers,
        )

        assert resp.status_code == 400

    def test_start_missing_stage(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/start",
            json={"batch_name": "batch-test"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "stage is required" in resp.get_json()["error"]

    def test_start_coming_soon_stage(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/start",
            json={"stage": "review", "batch_name": "batch-test"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "not yet available" in resp.get_json()["error"]

    def test_start_unknown_stage(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/start",
            json={"stage": "bogus", "batch_name": "batch-test"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Unknown stage" in resp.get_json()["error"]

    def test_start_missing_batch(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/start",
            json={"stage": "l1"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "batch_name is required" in resp.get_json()["error"]

    def test_start_nonexistent_batch(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/start",
            json={"stage": "l1", "batch_name": "no-such-batch"},
            headers=headers,
        )
        assert resp.status_code == 404
        assert "Batch not found" in resp.get_json()["error"]

    def test_start_no_eligible(self, client, db, seed_pipeline_data):
        """All companies already past L1 — none eligible."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        # Mark all new companies as triage_passed
        for c in seed_pipeline_data["companies"]:
            db.session.execute(
                db.text("UPDATE companies SET status = 'triage_passed' WHERE id = :id"),
                {"id": str(c.id)},
            )
        db.session.commit()

        resp = client.post(
            "/api/pipeline/start",
            json={"stage": "l1", "batch_name": "batch-test"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "No eligible" in resp.get_json()["error"]

    def test_start_duplicate_run_blocked(self, client, db, seed_pipeline_data):
        """Cannot start a stage that's already running."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        # Insert a running stage_run manually
        db.session.execute(
            db.text("""
                INSERT INTO stage_runs (id, tenant_id, batch_id, stage, status, total)
                VALUES (:id, :t, :b, 'l1', 'running', 5)
            """),
            {
                "id": _uuid(),
                "t": str(seed_pipeline_data["tenant"].id),
                "b": str(seed_pipeline_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.post(
            "/api/pipeline/start",
            json={"stage": "l1", "batch_name": "batch-test"},
            headers=headers,
        )
        assert resp.status_code == 409
        assert "already running" in resp.get_json()["error"]

    def test_start_unauthenticated(self, client, seed_pipeline_data):
        resp = client.post(
            "/api/pipeline/start",
            json={"stage": "l1", "batch_name": "batch-test"},
        )
        assert resp.status_code == 401


class TestPipelineStop:
    def test_stop_running_run(self, client, db, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        # Insert a running stage_run
        run_id = _uuid()
        db.session.execute(
            db.text("""
                INSERT INTO stage_runs (id, tenant_id, batch_id, stage, status, total)
                VALUES (:id, :t, :b, 'l1', 'running', 5)
            """),
            {
                "id": run_id,
                "t": str(seed_pipeline_data["tenant"].id),
                "b": str(seed_pipeline_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.post(
            "/api/pipeline/stop",
            json={"run_id": run_id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        # Verify status changed to stopping
        row = db.session.execute(
            db.text("SELECT status FROM stage_runs WHERE id = :id"),
            {"id": run_id},
        ).fetchone()
        assert row[0] == "stopping"

    def test_stop_completed_run_fails(self, client, db, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        run_id = _uuid()
        db.session.execute(
            db.text("""
                INSERT INTO stage_runs (id, tenant_id, batch_id, stage, status, total, done)
                VALUES (:id, :t, :b, 'l1', 'completed', 5, 5)
            """),
            {
                "id": run_id,
                "t": str(seed_pipeline_data["tenant"].id),
                "b": str(seed_pipeline_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.post(
            "/api/pipeline/stop",
            json={"run_id": run_id},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Cannot stop" in resp.get_json()["error"]

    def test_stop_missing_run_id(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/stop",
            json={},
            headers=headers,
        )
        assert resp.status_code == 400


class TestPipelineStatus:
    def test_status_no_runs(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.get(
            "/api/pipeline/status?batch_name=batch-test",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stages" in data
        assert data["stages"]["l1"]["status"] == "idle"
        # L2, person, generate are now available (idle, not unavailable)
        assert data["stages"]["l2"]["status"] == "idle"
        assert data["stages"]["person"]["status"] == "idle"
        assert data["stages"]["generate"]["status"] == "idle"
        # Only review is unavailable
        assert data["stages"]["review"]["status"] == "unavailable"

    def test_status_with_running_run(self, client, db, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        db.session.execute(
            db.text("""
                INSERT INTO stage_runs (id, tenant_id, batch_id, stage, status, total, done, failed, cost_usd)
                VALUES (:id, :t, :b, 'l1', 'running', 10, 3, 1, 0.0234)
            """),
            {
                "id": _uuid(),
                "t": str(seed_pipeline_data["tenant"].id),
                "b": str(seed_pipeline_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.get(
            "/api/pipeline/status?batch_name=batch-test",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        l1 = data["stages"]["l1"]
        assert l1["status"] == "running"
        assert l1["total"] == 10
        assert l1["done"] == 3
        assert l1["failed"] == 1
        assert l1["cost"] == pytest.approx(0.0234, abs=0.001)

    def test_status_includes_pipeline_run(self, client, db, seed_pipeline_data):
        """Status should include pipeline object when a pipeline_run exists."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        pipeline_id = _uuid()
        db.session.execute(
            db.text("""
                INSERT INTO pipeline_runs (id, tenant_id, batch_id, status, cost_usd, stages)
                VALUES (:id, :t, :b, 'running', 0.5, :stages)
            """),
            {
                "id": pipeline_id,
                "t": str(seed_pipeline_data["tenant"].id),
                "b": str(seed_pipeline_data["batch"].id),
                "stages": '{"l1": "fake-id-1", "l2": "fake-id-2"}',
            },
        )
        db.session.commit()

        resp = client.get(
            "/api/pipeline/status?batch_name=batch-test",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "pipeline" in data
        assert data["pipeline"]["status"] == "running"
        assert data["pipeline"]["cost"] == pytest.approx(0.5)
        assert data["pipeline"]["run_id"] == pipeline_id

    def test_status_missing_batch_name(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.get("/api/pipeline/status", headers=headers)
        assert resp.status_code == 400

    def test_status_unauthenticated(self, client):
        resp = client.get("/api/pipeline/status?batch_name=test")
        assert resp.status_code == 401


class TestPipelineRunAll:
    def test_run_all_success(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        with patch("api.routes.pipeline_routes.start_pipeline_threads") as mock_threads:
            resp = client.post(
                "/api/pipeline/run-all",
                json={
                    "batch_name": "batch-test",
                    "owner": "Michal",
                },
                headers=headers,
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert "pipeline_run_id" in data
        assert "stage_run_ids" in data
        assert set(data["stage_run_ids"].keys()) == {"l1", "l2", "person", "generate"}
        mock_threads.assert_called_once()

    def test_run_all_missing_batch(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/run-all",
            json={},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "batch_name is required" in resp.get_json()["error"]

    def test_run_all_duplicate_blocked(self, client, db, seed_pipeline_data):
        """Cannot run-all when a pipeline is already running."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        db.session.execute(
            db.text("""
                INSERT INTO pipeline_runs (id, tenant_id, batch_id, status)
                VALUES (:id, :t, :b, 'running')
            """),
            {
                "id": _uuid(),
                "t": str(seed_pipeline_data["tenant"].id),
                "b": str(seed_pipeline_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.post(
            "/api/pipeline/run-all",
            json={"batch_name": "batch-test"},
            headers=headers,
        )
        assert resp.status_code == 409
        assert "already running" in resp.get_json()["error"]

    def test_run_all_unauthenticated(self, client, seed_pipeline_data):
        resp = client.post(
            "/api/pipeline/run-all",
            json={"batch_name": "batch-test"},
        )
        assert resp.status_code == 401


class TestPipelineStopAll:
    def test_stop_all_success(self, client, db, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        pipeline_id = _uuid()
        db.session.execute(
            db.text("""
                INSERT INTO pipeline_runs (id, tenant_id, batch_id, status)
                VALUES (:id, :t, :b, 'running')
            """),
            {
                "id": pipeline_id,
                "t": str(seed_pipeline_data["tenant"].id),
                "b": str(seed_pipeline_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.post(
            "/api/pipeline/stop-all",
            json={"pipeline_run_id": pipeline_id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        # Verify pipeline status changed to stopped (force-kill)
        row = db.session.execute(
            db.text("SELECT status FROM pipeline_runs WHERE id = :id"),
            {"id": pipeline_id},
        ).fetchone()
        assert row[0] == "stopped"

    def test_stop_all_completed_fails(self, client, db, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        pipeline_id = _uuid()
        db.session.execute(
            db.text("""
                INSERT INTO pipeline_runs (id, tenant_id, batch_id, status)
                VALUES (:id, :t, :b, 'completed')
            """),
            {
                "id": pipeline_id,
                "t": str(seed_pipeline_data["tenant"].id),
                "b": str(seed_pipeline_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.post(
            "/api/pipeline/stop-all",
            json={"pipeline_run_id": pipeline_id},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "already finished" in resp.get_json()["error"]

    def test_stop_all_missing_id(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/stop-all",
            json={},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_stop_all_invalid_id(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/stop-all",
            json={"pipeline_run_id": "not-a-uuid"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.get_json()["error"]

    def test_stop_all_not_found(self, client, seed_pipeline_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_pipeline_data["tenant"].slug

        resp = client.post(
            "/api/pipeline/stop-all",
            json={"pipeline_run_id": _uuid()},
            headers=headers,
        )
        assert resp.status_code == 404
