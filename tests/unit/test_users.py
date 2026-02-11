"""Unit tests for user management API."""
import pytest
from tests.conftest import auth_header


class TestListUsers:
    def test_super_admin_lists_all_users(self, client, seed_super_admin, seed_user_with_role):
        headers = auth_header(client)
        resp = client.get("/api/users", headers=headers)
        assert resp.status_code == 200
        emails = [u["email"] for u in resp.get_json()]
        assert "admin@test.com" in emails
        assert "user@test.com" in emails

    def test_filter_by_tenant(self, client, seed_super_admin, seed_user_with_role, seed_tenant):
        headers = auth_header(client)
        resp = client.get(f"/api/users?tenant_id={seed_tenant.id}", headers=headers)
        assert resp.status_code == 200
        emails = [u["email"] for u in resp.get_json()]
        assert "user@test.com" in emails


class TestCreateUser:
    def test_create_user_with_tenant(self, client, seed_super_admin, seed_tenant):
        headers = auth_header(client)
        resp = client.post("/api/users", headers=headers, json={
            "email": "new@test.com",
            "password": "newpassword123",
            "display_name": "New User",
            "tenant_id": str(seed_tenant.id),
            "role": "editor",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["email"] == "new@test.com"

    def test_create_user_short_password(self, client, seed_super_admin):
        headers = auth_header(client)
        resp = client.post("/api/users", headers=headers, json={
            "email": "short@test.com",
            "password": "short",
            "display_name": "Short Pass",
        })
        assert resp.status_code == 400
        assert "8 characters" in resp.get_json()["error"]

    def test_create_duplicate_email(self, client, seed_super_admin):
        headers = auth_header(client)
        resp = client.post("/api/users", headers=headers, json={
            "email": "admin@test.com",
            "password": "testpass123",
            "display_name": "Duplicate",
        })
        assert resp.status_code == 409


class TestUpdateUser:
    def test_update_display_name(self, client, seed_super_admin, seed_user_with_role):
        headers = auth_header(client)
        resp = client.put(f"/api/users/{seed_user_with_role.id}", headers=headers, json={
            "display_name": "Updated Name",
        })
        assert resp.status_code == 200
        assert resp.get_json()["display_name"] == "Updated Name"

    def test_deactivate_user(self, client, seed_super_admin, seed_user_with_role):
        headers = auth_header(client)
        resp = client.put(f"/api/users/{seed_user_with_role.id}", headers=headers, json={
            "is_active": False,
        })
        assert resp.status_code == 200
        assert resp.get_json()["is_active"] is False


class TestDeleteUser:
    def test_delete_deactivates_user(self, client, seed_super_admin, seed_user_with_role):
        headers = auth_header(client)
        resp = client.delete(f"/api/users/{seed_user_with_role.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


class TestChangePassword:
    def test_admin_can_reset_password(self, client, seed_super_admin, seed_user_with_role):
        headers = auth_header(client)
        resp = client.put(
            f"/api/users/{seed_user_with_role.id}/password",
            headers=headers,
            json={"new_password": "newpass12345"},
        )
        assert resp.status_code == 200

        # Verify new password works
        login_resp = client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "newpass12345",
        })
        assert login_resp.status_code == 200


class TestRemoveUserRole:
    def test_remove_role(self, client, seed_super_admin, seed_user_with_role, seed_tenant):
        headers = auth_header(client)
        resp = client.delete(
            f"/api/users/{seed_user_with_role.id}/roles/{seed_tenant.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
