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

    def test_l2_requires_triage_completed(self, app, db, seed_tenant):
        """L2 requires triage completed — only companies with L1+triage are eligible."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)

        with app.app_context():
            # No completions — L2 should have 0 eligible
            ids = get_dag_eligible_ids(
                "l2", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids) == 0

            # Complete L1 for first company — still not eligible (triage missing)
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "l1",
            )

            ids = get_dag_eligible_ids(
                "l2", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids) == 0

            # Complete triage for first company — now eligible for L2
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", data["companies"][0].id, "triage",
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
                               "stages": ["l1", "triage", "l2"],
                               "soft_deps": {},
                           },
                           headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "pipeline_run_id" in data
        assert "stage_run_ids" in data
        assert "l1" in data["stage_run_ids"]
        assert "triage" in data["stage_run_ids"]
        assert "l2" in data["stage_run_ids"]
        assert data["stage_order"] == ["l1", "triage", "l2"]


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
# Triage gate integration
# ---------------------------------------------------------------------------

class TestTriageGateIntegration:
    """Test triage gate stage in DAG pipeline."""

    def _setup_company_for_triage(self, db, company, tier="tier_1",
                                   industry="software_saas", b2b=True):
        """Set company fields + insert L1 enrichment for triage evaluation."""
        from sqlalchemy import text as sa_text

        db.session.execute(sa_text("""
            UPDATE companies
            SET tier = :tier, industry = :industry
            WHERE id = :id
        """), {"tier": tier, "industry": industry, "id": str(company.id)})

        # Insert L1 enrichment with b2b in raw_response
        raw = json.dumps({"b2b": b2b, "company_name": "Test"})
        db.session.execute(sa_text("""
            INSERT INTO company_enrichment_l1 (company_id, raw_response, qc_flags,
                enrichment_cost_usd)
            VALUES (:cid, :raw, '[]', 0)
            ON CONFLICT (company_id) DO UPDATE
            SET raw_response = :raw, qc_flags = '[]'
        """), {"cid": str(company.id), "raw": raw})
        db.session.commit()

    def test_process_entity_triage_passes_good_company(self, app, db, seed_tenant):
        """Triage stage processes a company and returns gate_passed=True."""
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            self._setup_company_for_triage(db, company, tier="tier_1",
                                            industry="software_saas", b2b=True)

            result = _process_entity("triage", str(company.id), str(seed_tenant.id))

            assert isinstance(result, dict)
            assert result["gate_passed"] is True
            assert result["enrichment_cost_usd"] == 0

    def test_process_entity_triage_fails_non_b2b(self, app, db, seed_tenant):
        """Triage disqualifies a non-B2B company."""
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            self._setup_company_for_triage(db, company, b2b=False)

            result = _process_entity("triage", str(company.id), str(seed_tenant.id))

            assert result["gate_passed"] is False
            assert len(result["gate_reasons"]) > 0
            assert result["enrichment_cost_usd"] == 0

    def test_process_entity_triage_uses_custom_rules(self, app, db, seed_tenant):
        """Triage accepts custom rules via triage_rules parameter."""
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            self._setup_company_for_triage(db, company, tier="tier_3",
                                            industry="manufacturing", b2b=True)

            # With tier allowlist that excludes tier_3
            result = _process_entity(
                "triage", str(company.id), str(seed_tenant.id),
                triage_rules={"tier_allowlist": ["tier_1", "tier_2"]},
            )
            assert result["gate_passed"] is False

    def test_triage_disqualified_blocks_l2(self, app, db, seed_tenant):
        """Company with triage status='disqualified' is NOT eligible for L2."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            # Complete L1
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", company.id, "l1",
            )
            # Record triage as disqualified
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", company.id, "triage",
                status="disqualified",
            )

            # L2 should have 0 eligible (triage not "completed")
            ids = get_dag_eligible_ids(
                "l2", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids) == 0

    def test_triage_passed_enables_l2(self, app, db, seed_tenant):
        """Company with triage status='completed' IS eligible for L2."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            # Complete L1
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", company.id, "l1",
            )
            # Record triage as completed (passed)
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", company.id, "triage",
                status="completed",
            )

            ids = get_dag_eligible_ids(
                "l2", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids) == 1
            assert ids[0] == str(company.id)

    def test_triage_sets_company_status_disqualified(self, app, db, seed_tenant):
        """When triage fails, company status is set to triage_disqualified."""
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            self._setup_company_for_triage(db, company, b2b=False)

            _process_entity("triage", str(company.id), str(seed_tenant.id))

            from sqlalchemy import text as sa_text
            row = db.session.execute(sa_text(
                "SELECT status FROM companies WHERE id = :id"
            ), {"id": str(company.id)}).fetchone()
            assert row[0] == "triage_disqualified"


# ---------------------------------------------------------------------------
# L2 enrichment integration
# ---------------------------------------------------------------------------

class TestL2Integration:
    """Test L2 stage dispatch through _process_entity."""

    def _setup_company_for_l2(self, db, company, tenant_id):
        """Set company to triage_passed + insert L1 enrichment data."""
        from sqlalchemy import text as sa_text

        db.session.execute(sa_text("""
            UPDATE companies
            SET status = 'triage_passed', tier = 'tier_1',
                industry = 'software_saas'
            WHERE id = :id
        """), {"id": str(company.id)})

        raw = json.dumps({
            "company_name": company.name,
            "summary": "A B2B SaaS platform",
            "b2b": True,
            "industry": "software_saas",
            "revenue_eur_m": 10.0,
            "employees": 120,
            "hq": "Berlin, Germany",
        })
        db.session.execute(sa_text("""
            INSERT INTO company_enrichment_l1 (company_id, raw_response, qc_flags,
                enrichment_cost_usd)
            VALUES (:cid, :raw, '[]', 0)
            ON CONFLICT (company_id) DO UPDATE
            SET raw_response = :raw, qc_flags = '[]'
        """), {"cid": str(company.id), "raw": raw})
        db.session.commit()

    def test_l2_dispatches_to_direct_enricher(self, app, db, seed_tenant):
        """L2 stage dispatches to enrich_l2 (not n8n webhook)."""
        from unittest.mock import patch, MagicMock
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            self._setup_company_for_l2(db, company, seed_tenant.id)

            with patch("api.services.l2_enricher.enrich_l2") as mock_l2:
                mock_l2.return_value = {"enrichment_cost_usd": 0.009}
                result = _process_entity("l2", str(company.id),
                                         str(seed_tenant.id))

            mock_l2.assert_called_once_with(
                str(company.id), str(seed_tenant.id), previous_data=None,
            )
            assert result["enrichment_cost_usd"] == 0.009

    def test_l2_does_not_call_n8n(self, app, db, seed_tenant):
        """L2 stage should NOT call n8n webhook anymore."""
        from unittest.mock import patch, MagicMock
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            self._setup_company_for_l2(db, company, seed_tenant.id)

            with patch("api.services.l2_enricher.enrich_l2") as mock_l2, \
                 patch("api.services.pipeline_engine.call_n8n_webhook") as mock_n8n:
                mock_l2.return_value = {"enrichment_cost_usd": 0.005}
                _process_entity("l2", str(company.id),
                                str(seed_tenant.id))

            mock_n8n.assert_not_called()

    def test_l2_passes_previous_data(self, app, db, seed_tenant):
        """L2 stage forwards previous_data to enricher."""
        from unittest.mock import patch
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            self._setup_company_for_l2(db, company, seed_tenant.id)

            prev = {"l1": {"summary": "test"}}
            with patch("api.services.l2_enricher.enrich_l2") as mock_l2:
                mock_l2.return_value = {"enrichment_cost_usd": 0.01}
                _process_entity("l2", str(company.id),
                                str(seed_tenant.id),
                                previous_data=prev)

            mock_l2.assert_called_once_with(
                str(company.id), str(seed_tenant.id), previous_data=prev,
            )

    def test_l2_eligible_after_triage_passed(self, app, db, seed_tenant):
        """L2 DAG eligibility requires triage completed."""
        from api.services.dag_executor import get_dag_eligible_ids, record_completion

        data = _seed_dag_data(db, seed_tenant)
        company = data["companies"][0]

        with app.app_context():
            # Before triage: no L2 eligible
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", company.id, "l1",
            )
            ids_before = get_dag_eligible_ids(
                "l2", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids_before) == 0

            # After triage completed: L2 eligible
            record_completion(
                seed_tenant.id, data["tag"].id, data["pipeline_run"].id,
                "company", company.id, "triage",
                status="completed",
            )
            ids_after = get_dag_eligible_ids(
                "l2", data["pipeline_run"].id,
                seed_tenant.id, data["tag"].id,
            )
            assert len(ids_after) == 1
            assert ids_after[0] == str(company.id)


# ---------------------------------------------------------------------------
# Person enrichment integration
# ---------------------------------------------------------------------------

class TestPersonIntegration:
    """Test person stage dispatch through _process_entity."""

    def test_person_dispatches_to_direct_enricher(self, app, db, seed_tenant):
        """Person stage dispatches to enrich_person (not n8n webhook)."""
        from unittest.mock import patch
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        contact = data["contacts"][0]

        with app.app_context():
            with patch("api.services.person_enricher.enrich_person") as mock_person:
                mock_person.return_value = {"enrichment_cost_usd": 0.007}
                result = _process_entity("person", str(contact.id),
                                         str(seed_tenant.id))

            mock_person.assert_called_once_with(
                str(contact.id), str(seed_tenant.id), previous_data=None,
            )
            assert result["enrichment_cost_usd"] == 0.007

    def test_person_does_not_call_n8n(self, app, db, seed_tenant):
        """Person stage should NOT call n8n webhook anymore."""
        from unittest.mock import patch
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        contact = data["contacts"][0]

        with app.app_context():
            with patch("api.services.person_enricher.enrich_person") as mock_person, \
                 patch("api.services.pipeline_engine.call_n8n_webhook") as mock_n8n:
                mock_person.return_value = {"enrichment_cost_usd": 0.005}
                _process_entity("person", str(contact.id),
                                str(seed_tenant.id))

            mock_n8n.assert_not_called()

    def test_person_passes_previous_data(self, app, db, seed_tenant):
        """Person stage forwards previous_data to enricher."""
        from unittest.mock import patch
        from api.services.pipeline_engine import _process_entity

        data = _seed_dag_data(db, seed_tenant)
        contact = data["contacts"][0]

        with app.app_context():
            prev = {"l1": {"summary": "test"}, "l2": {"pain": "growth"}}
            with patch("api.services.person_enricher.enrich_person") as mock_person:
                mock_person.return_value = {"enrichment_cost_usd": 0.01}
                _process_entity("person", str(contact.id),
                                str(seed_tenant.id),
                                previous_data=prev)

            mock_person.assert_called_once_with(
                str(contact.id), str(seed_tenant.id), previous_data=prev,
            )


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
