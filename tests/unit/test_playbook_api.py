"""Tests for Playbook API endpoints."""
import json
import pytest
from unittest.mock import patch, MagicMock


def auth_header(client, email="admin@test.com", password="testpass123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestGetPlaybook:
    def test_auto_creates_document(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "draft"
        assert data["version"] == 1
        assert "id" in data

    def test_returns_existing_document(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content={"type": "doc"},
            status="active",
            version=3,
        )
        db.session.add(doc)
        db.session.commit()
        resp = client.get("/api/playbook", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "active"
        assert data["version"] == 3

    def test_tenant_isolation(self, client, seed_tenant, seed_super_admin, db):
        from api.models import Tenant, StrategyDocument
        headers = auth_header(client)
        other = Tenant(name="Other", slug="other-corp", is_active=True)
        db.session.add(other)
        db.session.commit()
        doc = StrategyDocument(tenant_id=other.id, content={"secret": True})
        db.session.add(doc)
        db.session.commit()
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook", headers=headers)
        data = resp.get_json()
        assert data.get("content") != {"secret": True}

    def test_requires_auth(self, client, seed_tenant):
        resp = client.get("/api/playbook", headers={"X-Namespace": seed_tenant.slug})
        assert resp.status_code == 401


class TestUpdatePlaybook:
    def test_save_document(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(tenant_id=seed_tenant.id, version=1)
        db.session.add(doc)
        db.session.commit()
        resp = client.put("/api/playbook", json={
            "content": {"type": "doc", "content": [{"type": "paragraph"}]},
            "version": 1,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == 2

    def test_optimistic_lock_conflict(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(tenant_id=seed_tenant.id, version=3)
        db.session.add(doc)
        db.session.commit()
        resp = client.put("/api/playbook", json={
            "content": {"type": "doc"},
            "version": 1,
        }, headers=headers)
        assert resp.status_code == 409
        data = resp.get_json()
        assert "conflict" in data["error"].lower()

    def test_version_required(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc)
        db.session.commit()
        resp = client.put("/api/playbook", json={"content": {"type": "doc"}}, headers=headers)
        assert resp.status_code == 400
