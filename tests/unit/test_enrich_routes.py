"""Tests for the enrich estimate + start API endpoints."""

import uuid
from unittest.mock import patch

import pytest

from tests.conftest import auth_header


def _uuid():
    return str(uuid.uuid4())


@pytest.fixture
def seed_enrich_data(db, seed_tenant, seed_super_admin):
    """Create batch, owner, companies, and contacts for enrich tests."""
    from api.models import Batch, Company, Contact, Owner

    owner = Owner(tenant_id=seed_tenant.id, name="Michal", is_active=True)
    db.session.add(owner)
    db.session.flush()

    batch = Batch(tenant_id=seed_tenant.id, name="enrich-batch", is_active=True)
    db.session.add(batch)
    db.session.flush()

    # 5 companies eligible for L1 (status=new)
    companies_new = []
    for i in range(5):
        c = Company(
            tenant_id=seed_tenant.id,
            name=f"New Co {i}",
            domain=f"newco{i}.com",
            batch_id=batch.id,
            owner_id=owner.id,
            status="new",
        )
        db.session.add(c)
        companies_new.append(c)

    # 2 companies eligible for L2 (status=triage_passed)
    companies_l2 = []
    for i in range(2):
        c = Company(
            tenant_id=seed_tenant.id,
            name=f"Passed Co {i}",
            domain=f"passed{i}.com",
            batch_id=batch.id,
            owner_id=owner.id,
            status="triage_passed",
        )
        db.session.add(c)
        companies_l2.append(c)

    # 1 company eligible for person stage (status=enriched_l2)
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

    # 3 contacts eligible for person stage (unprocessed, enriched_l2 company)
    contacts_person = []
    for i in range(3):
        ct = Contact(
            tenant_id=seed_tenant.id,
            first_name=f"Person Contact {i}",
            company_id=c_enriched.id,
            batch_id=batch.id,
            owner_id=owner.id,
            processed_enrich=False,
        )
        db.session.add(ct)
        contacts_person.append(ct)

    # 1 contact eligible for generate stage (processed, not_started)
    ct_gen = Contact(
        tenant_id=seed_tenant.id,
        first_name="Gen",
        last_name="Contact",
        company_id=c_enriched.id,
        batch_id=batch.id,
        owner_id=owner.id,
        processed_enrich=True,
        message_status="not_started",
        contact_score=85,
    )
    db.session.add(ct_gen)

    db.session.commit()
    return {
        "tenant": seed_tenant,
        "batch": batch,
        "owner": owner,
        "companies_new": companies_new,
        "companies_l2": companies_l2,
        "c_enriched": c_enriched,
        "contacts_person": contacts_person,
    }


class TestEnrichEstimate:
    def test_estimate_all_stages(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/estimate",
            json={
                "batch_name": "enrich-batch",
                "stages": ["l1", "l2", "person", "generate"],
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stages" in data
        assert "total_estimated_cost" in data

        # L1: 5 eligible at $0.02 = $0.10
        assert data["stages"]["l1"]["eligible_count"] == 5
        assert data["stages"]["l1"]["cost_per_item"] == 0.02
        assert data["stages"]["l1"]["estimated_cost"] == 0.10

        # L2: 2 eligible at $0.08 = $0.16
        assert data["stages"]["l2"]["eligible_count"] == 2
        assert data["stages"]["l2"]["cost_per_item"] == 0.08
        assert data["stages"]["l2"]["estimated_cost"] == 0.16

        # Person: 3 eligible at $0.04 = $0.12
        assert data["stages"]["person"]["eligible_count"] == 3
        assert data["stages"]["person"]["cost_per_item"] == 0.04
        assert data["stages"]["person"]["estimated_cost"] == 0.12

        # Generate: 1 eligible at $0.03 = $0.03
        assert data["stages"]["generate"]["eligible_count"] == 1
        assert data["stages"]["generate"]["cost_per_item"] == 0.03
        assert data["stages"]["generate"]["estimated_cost"] == 0.03

        # Total: 0.10 + 0.16 + 0.12 + 0.03 = 0.41
        assert data["total_estimated_cost"] == pytest.approx(0.41, abs=0.01)

    def test_estimate_single_stage(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/estimate",
            json={
                "batch_name": "enrich-batch",
                "stages": ["l1"],
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["stages"]) == 1
        assert data["stages"]["l1"]["eligible_count"] == 5

    def test_estimate_with_owner_filter(self, client, db, seed_enrich_data):
        """Owner filter should narrow eligible counts."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/estimate",
            json={
                "batch_name": "enrich-batch",
                "owner_name": "Michal",
                "stages": ["l1"],
            },
            headers=headers,
        )
        assert resp.status_code == 200
        # All 5 belong to Michal
        assert resp.get_json()["stages"]["l1"]["eligible_count"] == 5

    def test_estimate_missing_batch(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/estimate",
            json={"stages": ["l1"]},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "batch_name" in resp.get_json()["error"]

    def test_estimate_missing_stages(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/estimate",
            json={"batch_name": "enrich-batch"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "stages" in resp.get_json()["error"]

    def test_estimate_invalid_stage(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/estimate",
            json={"batch_name": "enrich-batch", "stages": ["bogus"]},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Invalid stages" in resp.get_json()["error"]

    def test_estimate_nonexistent_batch(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/estimate",
            json={"batch_name": "no-such-batch", "stages": ["l1"]},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_estimate_unauthenticated(self, client):
        resp = client.post(
            "/api/enrich/estimate",
            json={"batch_name": "test", "stages": ["l1"]},
        )
        assert resp.status_code == 401

    def test_estimate_uses_historical_cost(self, client, db, seed_enrich_data):
        """When historical stage_runs exist, use average cost instead of static default."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        # Insert a completed stage_run with known cost
        db.session.execute(
            db.text("""
                INSERT INTO stage_runs (id, tenant_id, batch_id, stage, status, total, done, cost_usd)
                VALUES (:id, :t, :b, 'l1', 'completed', 10, 10, 0.50)
            """),
            {
                "id": _uuid(),
                "t": str(seed_enrich_data["tenant"].id),
                "b": str(seed_enrich_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.post(
            "/api/enrich/estimate",
            json={"batch_name": "enrich-batch", "stages": ["l1"]},
            headers=headers,
        )
        assert resp.status_code == 200
        # Historical average: $0.50 / 10 = $0.05 per item
        assert resp.get_json()["stages"]["l1"]["cost_per_item"] == 0.05


class TestEnrichStart:
    def test_start_success(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        with patch("api.routes.enrich_routes.start_pipeline_threads") as mock_threads:
            resp = client.post(
                "/api/enrich/start",
                json={
                    "batch_name": "enrich-batch",
                    "owner_name": "Michal",
                    "stages": ["l1", "l2"],
                },
                headers=headers,
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert "pipeline_run_id" in data
        assert "stage_run_ids" in data
        assert set(data["stage_run_ids"].keys()) == {"l1", "l2"}
        mock_threads.assert_called_once()

    def test_start_all_stages(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        with patch("api.routes.enrich_routes.start_pipeline_threads") as mock_threads:
            resp = client.post(
                "/api/enrich/start",
                json={
                    "batch_name": "enrich-batch",
                    "stages": ["l1", "l2", "person", "generate"],
                },
                headers=headers,
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert set(data["stage_run_ids"].keys()) == {"l1", "l2", "person", "generate"}

    def test_start_with_sample_size(self, client, db, seed_enrich_data):
        """Sample size should be stored in config."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        with patch("api.routes.enrich_routes.start_pipeline_threads"):
            resp = client.post(
                "/api/enrich/start",
                json={
                    "batch_name": "enrich-batch",
                    "stages": ["l1"],
                    "sample_size": 10,
                },
                headers=headers,
            )

        assert resp.status_code == 201
        pipeline_run_id = resp.get_json()["pipeline_run_id"]

        # Verify sample_size stored in config
        import json
        row = db.session.execute(
            db.text("SELECT config FROM pipeline_runs WHERE id = :id"),
            {"id": pipeline_run_id},
        ).fetchone()
        config = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        assert config["sample_size"] == 10

    def test_start_duplicate_blocked(self, client, db, seed_enrich_data):
        """Cannot start when a pipeline is already running for this batch."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        db.session.execute(
            db.text("""
                INSERT INTO pipeline_runs (id, tenant_id, batch_id, status)
                VALUES (:id, :t, :b, 'running')
            """),
            {
                "id": _uuid(),
                "t": str(seed_enrich_data["tenant"].id),
                "b": str(seed_enrich_data["batch"].id),
            },
        )
        db.session.commit()

        resp = client.post(
            "/api/enrich/start",
            json={"batch_name": "enrich-batch", "stages": ["l1"]},
            headers=headers,
        )
        assert resp.status_code == 409
        assert "already running" in resp.get_json()["error"]

    def test_start_missing_batch(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/start",
            json={"stages": ["l1"]},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_start_missing_stages(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/start",
            json={"batch_name": "enrich-batch"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_start_invalid_stage(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/start",
            json={"batch_name": "enrich-batch", "stages": ["review"]},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Invalid stages" in resp.get_json()["error"]

    def test_start_nonexistent_batch(self, client, seed_enrich_data):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_enrich_data["tenant"].slug

        resp = client.post(
            "/api/enrich/start",
            json={"batch_name": "no-such-batch", "stages": ["l1"]},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_start_unauthenticated(self, client):
        resp = client.post(
            "/api/enrich/start",
            json={"batch_name": "test", "stages": ["l1"]},
        )
        assert resp.status_code == 401
