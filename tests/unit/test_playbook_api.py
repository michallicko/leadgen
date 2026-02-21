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


class TestPlaybookChat:
    def test_get_empty_chat_history(self, client, seed_tenant, seed_super_admin):
        """GET /api/playbook/chat returns empty messages when no chat exists."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook/chat", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["messages"] == []

    def test_post_message_creates_pair(self, client, seed_tenant, seed_super_admin):
        """POST /api/playbook/chat creates user + assistant message pair."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/playbook/chat",
            json={"message": "What is our ICP?"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["content"] == "What is our ICP?"
        assert data["assistant_message"]["role"] == "assistant"
        assert "placeholder" in data["assistant_message"]["content"].lower()

    def test_chat_history_ordered(self, client, seed_tenant, seed_super_admin, db):
        """GET /api/playbook/chat returns messages in chronological order."""
        from datetime import datetime, timedelta
        from api.models import StrategyDocument, StrategyChatMessage

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(tenant_id=seed_tenant.id, status="draft")
        db.session.add(doc)
        db.session.flush()

        now = datetime.utcnow()
        msgs = [
            StrategyChatMessage(
                tenant_id=seed_tenant.id, document_id=doc.id,
                role="user", content="First message",
                created_at=now - timedelta(minutes=2),
            ),
            StrategyChatMessage(
                tenant_id=seed_tenant.id, document_id=doc.id,
                role="assistant", content="First reply",
                created_at=now - timedelta(minutes=1),
            ),
            StrategyChatMessage(
                tenant_id=seed_tenant.id, document_id=doc.id,
                role="user", content="Second message",
                created_at=now,
            ),
        ]
        db.session.add_all(msgs)
        db.session.commit()

        resp = client.get("/api/playbook/chat", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 3
        assert data["messages"][0]["content"] == "First message"
        assert data["messages"][1]["content"] == "First reply"
        assert data["messages"][2]["content"] == "Second message"

    def test_chat_requires_auth(self, client, seed_tenant):
        """GET and POST /api/playbook/chat return 401 without token."""
        headers = {"X-Namespace": seed_tenant.slug}
        resp_get = client.get("/api/playbook/chat", headers=headers)
        assert resp_get.status_code == 401
        resp_post = client.post(
            "/api/playbook/chat",
            json={"message": "hello"},
            headers=headers,
        )
        assert resp_post.status_code == 401

    def test_post_requires_message(self, client, seed_tenant, seed_super_admin):
        """POST /api/playbook/chat returns 400 if no message field."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/chat", json={}, headers=headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "message" in data["error"].lower()
