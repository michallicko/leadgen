"""Unit tests for IAM-only authentication module."""
import uuid
from unittest.mock import MagicMock, patch

from tests.conftest import auth_header


class TestAuthLogin:
    """Test /api/auth/login — IAM proxy only, no local fallback."""

    def test_login_success_via_iam(self, client, app, seed_super_admin):
        """IAM returns 200 — user is synced and IAM tokens are returned."""
        iam_user_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "iam-access-token",
            "refresh_token": "iam-refresh-token",
            "user": {
                "id": iam_user_id,
                "email": "admin@test.com",
                "name": "Admin User",
                "permissions": [],
            },
        }

        with app.app_context():
            app.config["IAM_BASE_URL"] = "https://iam.test.local"

        with patch("api.routes.auth_routes.requests.post", return_value=mock_resp):
            resp = client.post("/api/auth/login", json={
                "email": "admin@test.com",
                "password": "somepassword",
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["access_token"] == "iam-access-token"
        assert data["refresh_token"] == "iam-refresh-token"
        assert data["user"]["email"] == "admin@test.com"

    def test_login_iam_returns_401(self, client, app, seed_super_admin):
        """IAM returns 401 — no local fallback, return 401."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with app.app_context():
            app.config["IAM_BASE_URL"] = "https://iam.test.local"

        with patch("api.routes.auth_routes.requests.post", return_value=mock_resp):
            resp = client.post("/api/auth/login", json={
                "email": "admin@test.com",
                "password": "wrongpassword",
            })

        assert resp.status_code == 401
        assert "Invalid" in resp.get_json()["error"]

    def test_login_iam_unreachable(self, client, app, seed_super_admin):
        """IAM is unreachable — return 503, no local fallback."""
        import requests as req_lib

        with app.app_context():
            app.config["IAM_BASE_URL"] = "https://iam.test.local"

        with patch(
            "api.routes.auth_routes.requests.post",
            side_effect=req_lib.ConnectionError("refused"),
        ):
            resp = client.post("/api/auth/login", json={
                "email": "admin@test.com",
                "password": "testpass123",
            })

        assert resp.status_code == 503
        assert "unavailable" in resp.get_json()["error"].lower()

    def test_login_no_iam_configured(self, client, app, db):
        """IAM_BASE_URL not set — return 503."""
        with app.app_context():
            app.config.pop("IAM_BASE_URL", None)

        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 503

    def test_login_missing_fields(self, client, db):
        resp = client.post("/api/auth/login", json={"email": "a@b.com"})
        assert resp.status_code == 400

    def test_login_no_body(self, client, db):
        resp = client.post("/api/auth/login")
        assert resp.status_code == 400


class TestAuthRefresh:
    """Test /api/auth/refresh — IAM proxy only."""

    def test_refresh_success(self, client, app, db):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "new-iam-access-token"}

        with app.app_context():
            app.config["IAM_BASE_URL"] = "https://iam.test.local"

        with patch("api.routes.auth_routes.requests.post", return_value=mock_resp):
            resp = client.post("/api/auth/refresh", json={
                "refresh_token": "some-iam-refresh-token",
            })

        assert resp.status_code == 200
        assert resp.get_json()["access_token"] == "new-iam-access-token"

    def test_refresh_iam_failure(self, client, app, db):
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with app.app_context():
            app.config["IAM_BASE_URL"] = "https://iam.test.local"

        with patch("api.routes.auth_routes.requests.post", return_value=mock_resp):
            resp = client.post("/api/auth/refresh", json={
                "refresh_token": "expired-token",
            })

        assert resp.status_code == 401

    def test_refresh_missing_token(self, client, db):
        resp = client.post("/api/auth/refresh", json={})
        assert resp.status_code == 400

    def test_refresh_no_iam_configured(self, client, app, db):
        with app.app_context():
            app.config.pop("IAM_BASE_URL", None)

        resp = client.post("/api/auth/refresh", json={
            "refresh_token": "some-token",
        })
        assert resp.status_code == 503


class TestAuthMe:
    def test_me_returns_user(self, client, seed_super_admin):
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
