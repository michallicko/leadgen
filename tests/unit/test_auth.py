"""Unit tests for authentication module."""
import pytest
from api.auth import hash_password, verify_password


class TestPasswordHashing:
    def test_hash_returns_bcrypt_string(self):
        h = hash_password("mypassword")
        assert h.startswith("$2b$")

    def test_verify_correct_password(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("mypassword")
        assert verify_password("wrongpassword", h) is False

    def test_different_passwords_different_hashes(self):
        h1 = hash_password("password1")
        h2 = hash_password("password2")
        assert h1 != h2

    def test_same_password_different_salts(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestAuthLogin:
    def test_login_success(self, client, seed_super_admin):
        resp = client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "admin@test.com"
        assert data["user"]["is_super_admin"] is True

    def test_login_wrong_password(self, client, seed_super_admin):
        resp = client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "Invalid" in resp.get_json()["error"]

    def test_login_nonexistent_user(self, client, db):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client, db):
        resp = client.post("/api/auth/login", json={"email": "a@b.com"})
        assert resp.status_code == 400

    def test_login_no_body(self, client, db):
        resp = client.post("/api/auth/login")
        assert resp.status_code == 400

    def test_login_inactive_user(self, client, db):
        from api.models import User
        user = User(
            email="inactive@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Inactive",
            is_active=False,
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post("/api/auth/login", json={
            "email": "inactive@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 401
        assert "disabled" in resp.get_json()["error"]


class TestAuthRefresh:
    def test_refresh_success(self, client, seed_super_admin):
        # Login first
        login_resp = client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "testpass123",
        })
        refresh_token = login_resp.get_json()["refresh_token"]

        # Refresh
        resp = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()

    def test_refresh_with_access_token_fails(self, client, seed_super_admin):
        login_resp = client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "testpass123",
        })
        access_token = login_resp.get_json()["access_token"]

        resp = client.post("/api/auth/refresh", json={
            "refresh_token": access_token,
        })
        assert resp.status_code == 401

    def test_refresh_missing_token(self, client, db):
        resp = client.post("/api/auth/refresh", json={})
        assert resp.status_code == 400


class TestAuthMe:
    def test_me_returns_user(self, client, seed_super_admin):
        from tests.conftest import auth_header
        headers = auth_header(client)
        resp = client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == "admin@test.com"

    def test_me_no_token(self, client, db):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client, db):
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert resp.status_code == 401
