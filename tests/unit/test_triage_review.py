"""Unit tests for BL-176: Triage Review UI — PATCH /api/companies/<id>/triage + GET /api/companies/triage-queue."""

import json

from api.models import Company, CompanyEnrichmentL1
from tests.conftest import auth_header


def _make_company(db, tenant_id, name, status="new", triage_score=None):
    c = Company(
        tenant_id=tenant_id,
        name=name,
        status=status,
        triage_score=triage_score,
    )
    db.session.add(c)
    db.session.flush()
    return c


def _make_l1(db, company_id, pre_score=7.5, confidence=0.85):
    l1 = CompanyEnrichmentL1(
        company_id=company_id,
        pre_score=pre_score,
        confidence=confidence,
        triage_notes="Auto-triage notes from L1",
    )
    db.session.add(l1)
    db.session.flush()
    return l1


class TestTriageEndpoint:
    def test_triage_pass(self, client, seed_tenant, seed_super_admin, db):
        c = _make_company(db, seed_tenant.id, "Acme Corp", status="new")
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.patch(
            f"/api/companies/{c.id}/triage",
            data=json.dumps({"action": "pass"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["action"] == "pass"
        assert data["status"] == "triage_passed"

    def test_triage_review(self, client, seed_tenant, seed_super_admin, db):
        c = _make_company(db, seed_tenant.id, "Beta Inc", status="new")
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.patch(
            f"/api/companies/{c.id}/triage",
            data=json.dumps({"action": "review", "reason": "Need more info"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["action"] == "review"
        assert data["status"] == "needs_review"

    def test_triage_disqualify_requires_reason(
        self, client, seed_tenant, seed_super_admin, db
    ):
        c = _make_company(db, seed_tenant.id, "Gamma LLC", status="new")
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.patch(
            f"/api/companies/{c.id}/triage",
            data=json.dumps({"action": "disqualify"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "reason" in resp.get_json()["error"].lower()

    def test_triage_disqualify_with_reason(
        self, client, seed_tenant, seed_super_admin, db
    ):
        c = _make_company(db, seed_tenant.id, "Delta Co", status="new")
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.patch(
            f"/api/companies/{c.id}/triage",
            data=json.dumps({"action": "disqualify", "reason": "Too small"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["action"] == "disqualify"
        assert data["status"] == "triage_disqualified"

    def test_triage_invalid_action(self, client, seed_tenant, seed_super_admin, db):
        c = _make_company(db, seed_tenant.id, "Epsilon", status="new")
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.patch(
            f"/api/companies/{c.id}/triage",
            data=json.dumps({"action": "invalid"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_triage_company_not_found(self, client, seed_tenant, seed_super_admin, db):
        db.session.commit()
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.patch(
            "/api/companies/00000000-0000-0000-0000-000000000000/triage",
            data=json.dumps({"action": "pass"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 404


class TestTriageQueue:
    def test_queue_returns_enriched_companies(
        self, client, seed_tenant, seed_super_admin, db
    ):
        c1 = _make_company(db, seed_tenant.id, "Alpha", status="new", triage_score=8.5)
        _make_l1(db, c1.id)
        c2 = _make_company(db, seed_tenant.id, "Beta", status="new", triage_score=6.0)
        _make_l1(db, c2.id)
        # This one is already passed — should NOT appear in queue
        c3 = _make_company(
            db, seed_tenant.id, "Gamma", status="triage_passed", triage_score=9.0
        )
        _make_l1(db, c3.id)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/companies/triage-queue", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 2
        names = [c["name"] for c in data["companies"]]
        assert "Alpha" in names
        assert "Beta" in names
        assert "Gamma" not in names
        # Should be sorted by triage_score DESC
        assert data["companies"][0]["name"] == "Alpha"

    def test_queue_empty_no_l1(self, client, seed_tenant, seed_super_admin, db):
        _make_company(db, seed_tenant.id, "NoL1", status="new")
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/companies/triage-queue", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0

    def test_queue_excludes_disqualified(
        self, client, seed_tenant, seed_super_admin, db
    ):
        c = _make_company(db, seed_tenant.id, "Disq", status="triage_disqualified")
        _make_l1(db, c.id)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/companies/triage-queue", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0
