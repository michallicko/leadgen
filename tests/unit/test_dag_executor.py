"""Tests for the DAG executor: eligibility queries, completion recording, and API endpoints."""
import json
import uuid

import pytest

from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_dag_data(db, seed_tenant):
    """Seed companies, contacts, and tags for DAG testing."""
    from api.models import Tag, Company, Contact, EntityStageCompletion, Owner, PipelineRun

    owner = Owner(tenant_id=seed_tenant.id, name="Alice", is_active=True)
    db.session.add(owner)
    db.session.flush()

    tag = Tag(tenant_id=seed_tenant.id, name="dag-batch", is_active=True)
    db.session.add(tag)
    db.session.flush()

    # Companies with different countries
    companies = []
    company_data = [
        ("Czech Co", "czech.cz", "CZ", "12345678"),
        ("Norway Co", "norway.no", "NO", None),
        ("Finland Co", "finland.fi", "FI", None),
        ("USA Co", "usa.com", "US", None),
        ("France Co", "france.fr", "FR", None),
    ]
    for name, domain, country, ico in company_data:
        c = Company(
            tenant_id=seed_tenant.id, name=name, domain=domain,
            tag_id=tag.id, owner_id=owner.id, hq_country=country,
            status="new", ico=ico,
        )
        db.session.add(c)
        companies.append(c)
    db.session.flush()

    # Contacts for the first two companies
    contacts = []
    for company in companies[:2]:
        ct = Contact(
            tenant_id=seed_tenant.id, first_name="Person",
            last_name=f"At {company.name}",
            company_id=company.id, tag_id=tag.id, owner_id=owner.id,
        )
        db.session.add(ct)
        contacts.append(ct)
    db.session.flush()

    # Pipeline run
    pipeline_run = PipelineRun(
        tenant_id=seed_tenant.id, tag_id=tag.id,
        owner_id=owner.id, status="running",
        config=json.dumps({"mode": "dag"}),
    )
    db.session.add(pipeline_run)
    db.session.flush()

    db.session.commit()

    return {
        "owner": owner,
        "tag": tag,
        "companies": companies,
        "contacts": contacts,
        "pipeline_run": pipeline_run,
    }


# ---------------------------------------------------------------------------
# record_completion tests
# ---------------------------------------------------------------------------

class TestRecordCompletion:
    def test_record_completed(self, app, db, seed_tenant):
        from api.models import EntityStageCompletion
        from api.services.dag_executor import record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "l1",
                status="completed", cost_usd=0.02,
            )

        result = db.session.query(EntityStageCompletion).filter_by(
            entity_id=data["companies"][0].id, stage="l1",
        ).first()
        assert result is not None
        assert result.status == "completed"
        assert float(result.cost_usd) == 0.02

    def test_record_failed(self, app, db, seed_tenant):
        from api.models import EntityStageCompletion
        from api.services.dag_executor import record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "l1",
                status="failed", error="Timeout",
            )

        result = db.session.query(EntityStageCompletion).filter_by(
            entity_id=data["companies"][0].id, stage="l1",
        ).first()
        assert result.status == "failed"
        assert result.error == "Timeout"

    def test_record_skipped(self, app, db, seed_tenant):
        from api.models import EntityStageCompletion
        from api.services.dag_executor import record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][3].id, "registry",
                status="skipped",
            )

        result = db.session.query(EntityStageCompletion).filter_by(
            entity_id=data["companies"][3].id, stage="registry",
        ).first()
        assert result.status == "skipped"


# ---------------------------------------------------------------------------
# build_eligibility_query tests
# ---------------------------------------------------------------------------

class TestBuildEligibilityQuery:
    def test_l1_no_deps(self, app, db, seed_tenant):
        """L1 has no deps — all companies in batch are eligible."""
        from api.services.dag_executor import get_dag_eligible_ids

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            ids = get_dag_eligible_ids(
                "l1", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
        assert len(ids) == 5  # All 5 companies

    def test_l2_requires_l1_completed(self, app, db, seed_tenant):
        """L2 requires L1 completed — only companies with L1 completion are eligible."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            # No L1 completions — L2 should have 0 eligible
            ids = get_dag_eligible_ids(
                "l2", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids) == 0

            # Complete L1 for first company
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "l1",
            )

            ids = get_dag_eligible_ids(
                "l2", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids) == 1
            assert ids[0] == str(data["companies"][0].id)

    def test_cross_entity_dep_person_needs_company_l1(self, app, db, seed_tenant):
        """Person (contact) depends on L1 (company) — cross-entity check via company_id."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            # No L1 completions — person should have 0 eligible
            ids = get_dag_eligible_ids(
                "person", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
                soft_deps_enabled={"person": False},  # disable soft deps for this test
            )
            assert len(ids) == 0

            # Complete L1 for first company
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "l1",
            )

            ids = get_dag_eligible_ids(
                "person", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
                soft_deps_enabled={"person": False},
            )
            # Should find contact(s) for first company
            assert len(ids) == 1

    def test_registry_country_gate(self, app, db, seed_tenant):
        """Registry returns companies matching CZ, NO, FI, or FR — not US."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            # Complete L1 for all companies
            for c in data["companies"]:
                record_completion(
                    seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                    "company", c.id, "l1",
                )

            ids = get_dag_eligible_ids(
                "registry", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            # CZ, NO, FI, FR match — US does not
            company_ids = {str(c.id) for c in data["companies"]}
            us_id = str(data["companies"][3].id)  # USA Co
            assert len(ids) == 4
            assert us_id not in ids

    def test_already_completed_excluded(self, app, db, seed_tenant):
        """Entities that already have a completion for this stage are excluded."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            ids_before = get_dag_eligible_ids(
                "l1", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids_before) == 5

            # Record L1 completion for first company
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "l1",
            )

            ids_after = get_dag_eligible_ids(
                "l1", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids_after) == 4  # One less

    def test_soft_deps_enabled(self, app, db, seed_tenant):
        """Person with soft deps enabled requires L2 + signals completion."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            # Complete L1 for first company
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "l1",
            )

            # With soft deps ON (default) — also needs l2 and signals
            ids = get_dag_eligible_ids(
                "person", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids) == 0  # Missing l2 and signals

            # Complete l2 and signals
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "l2",
            )
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "signals",
            )

            ids = get_dag_eligible_ids(
                "person", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids) == 1

    def test_unknown_stage(self, app, db, seed_tenant):
        from api.services.dag_executor import get_dag_eligible_ids

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            ids = get_dag_eligible_ids(
                "bogus", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert ids == []


# ---------------------------------------------------------------------------
# DAG API endpoint tests
# ---------------------------------------------------------------------------

class TestDagRunEndpoint:
    def test_dag_run_requires_auth(self, client):
        resp = client.post("/api/pipeline/dag-run", json={"tag_name": "x", "stages": ["l1"]})
        assert resp.status_code == 401

    def test_dag_run_requires_batch(self, client, seed_tenant, seed_super_admin):
        from api.models import UserTenantRole
        from api.models import db as _db

        role = UserTenantRole(
            user_id=seed_super_admin.id, tenant_id=seed_tenant.id,
            role="admin", granted_by=seed_super_admin.id,
        )
        _db.session.add(role)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/pipeline/dag-run",
                           json={"stages": ["l1"]},
                           headers=headers)
        assert resp.status_code == 400
        assert "tag_name" in resp.get_json()["error"]

    def test_dag_run_requires_stages(self, client, seed_tenant, seed_super_admin):
        from api.models import UserTenantRole
        from api.models import db as _db

        role = UserTenantRole(
            user_id=seed_super_admin.id, tenant_id=seed_tenant.id,
            role="admin", granted_by=seed_super_admin.id,
        )
        _db.session.add(role)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/pipeline/dag-run",
                           json={"tag_name": "b", "stages": []},
                           headers=headers)
        assert resp.status_code == 400
        assert "stages" in resp.get_json()["error"]

    def test_dag_run_validates_stages(self, client, seed_tenant, seed_super_admin):
        from api.models import Tag, UserTenantRole
        from api.models import db as _db

        role = UserTenantRole(
            user_id=seed_super_admin.id, tenant_id=seed_tenant.id,
            role="admin", granted_by=seed_super_admin.id,
        )
        _db.session.add(role)
        tag = Tag(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        _db.session.add(tag)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/pipeline/dag-run",
                           json={"tag_name": "test-batch", "stages": ["l1", "bogus"]},
                           headers=headers)
        assert resp.status_code == 400
        assert "Unknown stages" in resp.get_json()["error"]

    def test_dag_run_creates_pipeline(self, client, seed_tenant, seed_super_admin):
        from api.models import Tag, UserTenantRole
        from api.models import db as _db

        role = UserTenantRole(
            user_id=seed_super_admin.id, tenant_id=seed_tenant.id,
            role="admin", granted_by=seed_super_admin.id,
        )
        _db.session.add(role)
        tag = Tag(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        _db.session.add(tag)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/pipeline/dag-run",
                           json={
                               "tag_name": "test-batch",
                               "stages": ["l1", "l2"],
                               "soft_deps": {},
                           },
                           headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "pipeline_run_id" in data
        assert "stage_run_ids" in data
        assert "l1" in data["stage_run_ids"]
        assert "l2" in data["stage_run_ids"]
        assert data["stage_order"] == ["l1", "l2"]


class TestDagStatusEndpoint:
    def test_dag_status_not_found(self, client, seed_tenant, seed_super_admin):
        from api.models import Tag, UserTenantRole
        from api.models import db as _db

        role = UserTenantRole(
            user_id=seed_super_admin.id, tenant_id=seed_tenant.id,
            role="admin", granted_by=seed_super_admin.id,
        )
        _db.session.add(role)
        tag = Tag(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        _db.session.add(tag)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/pipeline/dag-status?tag_name=test-batch",
                          headers=headers)
        assert resp.status_code == 404


class TestDagStopEndpoint:
    def test_dag_stop_requires_pipeline_run_id(self, client, seed_tenant, seed_super_admin):
        from api.models import UserTenantRole
        from api.models import db as _db

        role = UserTenantRole(
            user_id=seed_super_admin.id, tenant_id=seed_tenant.id,
            role="admin", granted_by=seed_super_admin.id,
        )
        _db.session.add(role)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/pipeline/dag-stop",
                           json={},
                           headers=headers)
        assert resp.status_code == 400

    def test_dag_stop_not_found(self, client, seed_tenant, seed_super_admin):
        from api.models import UserTenantRole
        from api.models import db as _db

        role = UserTenantRole(
            user_id=seed_super_admin.id, tenant_id=seed_tenant.id,
            role="admin", granted_by=seed_super_admin.id,
        )
        _db.session.add(role)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/pipeline/dag-stop",
                           json={"pipeline_run_id": str(uuid.uuid4())},
                           headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Old endpoints still work
# ---------------------------------------------------------------------------

class TestOldEndpointsUnchanged:
    def test_pipeline_start_still_works(self, client, seed_companies_contacts, seed_super_admin):
        """Old /api/pipeline/start endpoint still functions."""
        headers = auth_header(client)
        seed_data = seed_companies_contacts
        headers["X-Namespace"] = seed_data["tenant"].slug

        resp = client.post("/api/pipeline/start",
                           json={
                               "tag_name": "batch-1",
                               "stage": "l1",
                           },
                           headers=headers)
        # Should succeed (201) since there's eligible items
        assert resp.status_code == 201

    def test_pipeline_status_still_works(self, client, seed_companies_contacts, seed_super_admin):
        """Old /api/pipeline/status endpoint still functions."""
        headers = auth_header(client)
        seed_data = seed_companies_contacts
        headers["X-Namespace"] = seed_data["tenant"].slug

        resp = client.get("/api/pipeline/status?tag_name=batch-1",
                          headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stages" in data
