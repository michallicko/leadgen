"""Unit tests for tenant management API."""
import pytest
from tests.conftest import auth_header


class TestListTenants:
    def test_super_admin_sees_all_tenants(self, client, seed_super_admin, seed_tenant):
        headers = auth_header(client)
        resp = client.get("/api/tenants", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1
        slugs = [t["slug"] for t in data]
        assert "test-corp" in slugs

    def test_unauthenticated_blocked(self, client, db):
        resp = client.get("/api/tenants")
        assert resp.status_code == 401


class TestCreateTenant:
    def test_create_tenant(self, client, seed_super_admin):
        headers = auth_header(client)
        resp = client.post("/api/tenants", headers=headers, json={
            "name": "Acme Inc",
            "slug": "acme",
            "domain": "acme.com",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["slug"] == "acme"
        assert data["name"] == "Acme Inc"
        assert data["is_active"] is True

    def test_create_tenant_missing_name(self, client, seed_super_admin):
        headers = auth_header(client)
        resp = client.post("/api/tenants", headers=headers, json={
            "slug": "no-name",
        })
        assert resp.status_code == 400

    def test_create_tenant_duplicate_slug(self, client, seed_super_admin, seed_tenant):
        headers = auth_header(client)
        resp = client.post("/api/tenants", headers=headers, json={
            "name": "Duplicate",
            "slug": "test-corp",
        })
        assert resp.status_code == 409

    def test_non_super_admin_blocked(self, client, seed_user_with_role):
        headers = auth_header(client, email="user@test.com")
        resp = client.post("/api/tenants", headers=headers, json={
            "name": "Blocked",
            "slug": "blocked",
        })
        assert resp.status_code == 403


class TestGetTenant:
    def test_get_existing_tenant(self, client, seed_super_admin, seed_tenant):
        headers = auth_header(client)
        resp = client.get(f"/api/tenants/{seed_tenant.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["slug"] == "test-corp"

    def test_get_nonexistent_tenant(self, client, seed_super_admin):
        headers = auth_header(client)
        resp = client.get("/api/tenants/00000000-0000-0000-0000-000000000000", headers=headers)
        assert resp.status_code == 404


class TestUpdateTenant:
    def test_update_tenant_name(self, client, seed_super_admin, seed_tenant):
        headers = auth_header(client)
        resp = client.put(f"/api/tenants/{seed_tenant.id}", headers=headers, json={
            "name": "Updated Corp",
        })
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Updated Corp"


class TestListTenantUsers:
    def test_list_users_in_tenant(self, client, seed_user_with_role, seed_tenant):
        headers = auth_header(client, email="admin@test.com")
        resp = client.get(f"/api/tenants/{seed_tenant.id}/users", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        emails = [u["email"] for u in data]
        assert "user@test.com" in emails
