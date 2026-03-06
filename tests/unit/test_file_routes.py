"""Tests for file upload API routes."""

import io
import uuid

import pytest

from api.auth import create_access_token, hash_password
from api.models import Tenant, User, UserTenantRole


@pytest.fixture
def seed_data(db):
    """Create test user, tenant, and return auth token."""
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    tenant = Tenant(id=tenant_id, name="Test Co", slug="test-files")
    db.session.add(tenant)

    user = User(
        id=user_id,
        email="test-files@example.com",
        password_hash=hash_password("test123"),
        display_name="Test User",
        is_super_admin=False,
    )
    db.session.add(user)

    role = UserTenantRole(
        user_id=user_id,
        tenant_id=tenant_id,
        role="admin",
    )
    db.session.add(role)
    db.session.flush()

    # Generate token
    token = create_access_token(user)

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "slug": "test-files",
        "token": token,
    }


class TestFileUploadRoute:
    def test_upload_no_file(self, client, seed_data):
        resp = client.post(
            "/api/files/upload",
            headers={
                "Authorization": "Bearer {}".format(seed_data["token"]),
                "X-Namespace": seed_data["slug"],
            },
        )
        assert resp.status_code == 400
        assert "No file" in resp.get_json()["error"]

    def test_upload_unsupported_type(self, client, seed_data):
        data = {"file": (io.BytesIO(b"fake content"), "virus.exe")}
        resp = client.post(
            "/api/files/upload",
            data=data,
            content_type="multipart/form-data",
            headers={
                "Authorization": "Bearer {}".format(seed_data["token"]),
                "X-Namespace": seed_data["slug"],
            },
        )
        assert resp.status_code == 415

    def test_upload_no_auth(self, client):
        resp = client.post("/api/files/upload")
        assert resp.status_code == 401


class TestFileListRoute:
    def test_list_empty(self, client, seed_data):
        resp = client.get(
            "/api/files",
            headers={
                "Authorization": "Bearer {}".format(seed_data["token"]),
                "X-Namespace": seed_data["slug"],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["files"] == []


class TestFileDeleteRoute:
    def test_delete_not_found(self, client, seed_data):
        fake_id = str(uuid.uuid4())
        resp = client.delete(
            "/api/files/{}".format(fake_id),
            headers={
                "Authorization": "Bearer {}".format(seed_data["token"]),
                "X-Namespace": seed_data["slug"],
            },
        )
        assert resp.status_code == 404


class TestFromUrlRoute:
    def test_no_url(self, client, seed_data):
        resp = client.post(
            "/api/files/from-url",
            json={},
            headers={
                "Authorization": "Bearer {}".format(seed_data["token"]),
                "X-Namespace": seed_data["slug"],
            },
        )
        assert resp.status_code == 400
        assert "URL is required" in resp.get_json()["error"]

    def test_invalid_url(self, client, seed_data):
        resp = client.post(
            "/api/files/from-url",
            json={"url": "not-a-url"},
            headers={
                "Authorization": "Bearer {}".format(seed_data["token"]),
                "X-Namespace": seed_data["slug"],
            },
        )
        assert resp.status_code == 400
        assert "Invalid URL" in resp.get_json()["error"]
