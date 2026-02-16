"""Unit tests for Google OAuth service (token encryption, auth flow, refresh, revocation)."""
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from tests.conftest import auth_header

# Generate a stable test key once
TEST_FERNET_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _configure_oauth(app):
    """Set Google OAuth config values for all tests in this module."""
    app.config["OAUTH_ENCRYPTION_KEY"] = TEST_FERNET_KEY
    app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
    app.config["GOOGLE_REDIRECT_URI"] = "https://example.com/callback"


class TestTokenEncryption:
    def test_encrypt_decrypt_roundtrip(self, app):
        from api.services.google_oauth import encrypt_token, decrypt_token
        with app.app_context():
            original = "ya29.some-access-token-value"
            encrypted = encrypt_token(original)
            assert encrypted is not None
            assert encrypted != original
            decrypted = decrypt_token(encrypted)
            assert decrypted == original

    def test_encrypt_none_returns_none(self, app):
        from api.services.google_oauth import encrypt_token
        with app.app_context():
            assert encrypt_token(None) is None

    def test_decrypt_none_returns_none(self, app):
        from api.services.google_oauth import decrypt_token
        with app.app_context():
            assert decrypt_token(None) is None

    def test_encrypt_empty_string_returns_none(self, app):
        from api.services.google_oauth import encrypt_token
        with app.app_context():
            assert encrypt_token("") is None

    def test_decrypt_empty_string_returns_none(self, app):
        from api.services.google_oauth import decrypt_token
        with app.app_context():
            assert decrypt_token("") is None

    def test_encrypt_requires_key(self, app):
        from api.services.google_oauth import encrypt_token
        with app.app_context():
            app.config["OAUTH_ENCRYPTION_KEY"] = ""
            with pytest.raises(ValueError, match="OAUTH_ENCRYPTION_KEY"):
                encrypt_token("some-token")


class TestGetGoogleAuthUrl:
    def test_url_contains_params(self, app):
        from api.services.google_oauth import get_google_auth_url
        with app.app_context():
            scopes = ["https://www.googleapis.com/auth/contacts.readonly"]
            state = "opaque-state-string"
            url = get_google_auth_url(state, scopes)

            assert "https://accounts.google.com/o/oauth2/v2/auth?" in url
            assert "client_id=test-client-id" in url
            assert "redirect_uri=https" in url
            assert "scope=" in url
            assert "contacts.readonly" in url
            assert "state=opaque-state-string" in url
            assert "access_type=offline" in url
            assert "prompt=consent" in url
            assert "response_type=code" in url

    def test_url_joins_multiple_scopes(self, app):
        from api.services.google_oauth import get_google_auth_url
        with app.app_context():
            scopes = [
                "https://www.googleapis.com/auth/contacts.readonly",
                "https://www.googleapis.com/auth/gmail.readonly",
            ]
            url = get_google_auth_url("state", scopes)
            # Scopes should be space-joined (URL-encoded as +)
            assert "contacts.readonly" in url
            assert "gmail.readonly" in url


class TestExchangeCode:
    def test_exchange_code_success(self, app, monkeypatch):
        from api.services import google_oauth

        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "ya29.new-access-token",
            "refresh_token": "1//refresh-token",
            "expires_in": 3600,
        }
        mock_token_response.raise_for_status = MagicMock()

        mock_userinfo_response = MagicMock()
        mock_userinfo_response.status_code = 200
        mock_userinfo_response.json.return_value = {
            "email": "user@gmail.com",
            "sub": "google-sub-123",
        }
        mock_userinfo_response.raise_for_status = MagicMock()

        call_count = {"n": 0}

        def mock_post(url, **kwargs):
            return mock_token_response

        def mock_get(url, **kwargs):
            return mock_userinfo_response

        monkeypatch.setattr(google_oauth.requests, "post", mock_post)
        monkeypatch.setattr(google_oauth.requests, "get", mock_get)

        with app.app_context():
            result = google_oauth.exchange_code("auth-code-123")

        assert result["access_token"] == "ya29.new-access-token"
        assert result["refresh_token"] == "1//refresh-token"
        assert result["expires_in"] == 3600
        assert result["email"] == "user@gmail.com"
        assert result["sub"] == "google-sub-123"


class TestRefreshAccessToken:
    def test_refresh_access_token_success(self, app, monkeypatch):
        from api.services import google_oauth

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "ya29.refreshed-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        monkeypatch.setattr(google_oauth.requests, "post", lambda url, **kw: mock_response)

        with app.app_context():
            # Encrypt a refresh token to pass in
            encrypted_refresh = google_oauth.encrypt_token("1//original-refresh-token")
            result = google_oauth.refresh_access_token(encrypted_refresh)

        assert result["access_token"] == "ya29.refreshed-token"
        assert result["expires_in"] == 3600


class TestGetValidToken:
    def test_returns_cached_when_not_expired(self, app, db, seed_tenant, seed_super_admin):
        from api.services import google_oauth
        from api.models import OAuthConnection

        with app.app_context():
            access_enc = google_oauth.encrypt_token("ya29.cached-token")
            refresh_enc = google_oauth.encrypt_token("1//refresh")

            conn = OAuthConnection(
                user_id=seed_super_admin.id,
                tenant_id=seed_tenant.id,
                provider="google",
                provider_account_id="sub-1",
                provider_email="test@gmail.com",
                access_token_enc=access_enc,
                refresh_token_enc=refresh_enc,
                token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
                status="active",
            )
            db.session.add(conn)
            db.session.flush()

            token = google_oauth.get_valid_token(conn)
            assert token == "ya29.cached-token"

    def test_refreshes_expired_token(self, app, db, seed_tenant, seed_super_admin, monkeypatch):
        from api.services import google_oauth
        from api.models import OAuthConnection

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "ya29.fresh-from-refresh",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()
        monkeypatch.setattr(google_oauth.requests, "post", lambda url, **kw: mock_response)

        with app.app_context():
            access_enc = google_oauth.encrypt_token("ya29.old-expired")
            refresh_enc = google_oauth.encrypt_token("1//refresh-token")

            conn = OAuthConnection(
                user_id=seed_super_admin.id,
                tenant_id=seed_tenant.id,
                provider="google",
                provider_account_id="sub-2",
                provider_email="test2@gmail.com",
                access_token_enc=access_enc,
                refresh_token_enc=refresh_enc,
                token_expiry=datetime.now(timezone.utc) - timedelta(hours=1),  # expired
                status="active",
            )
            db.session.add(conn)
            db.session.flush()

            token = google_oauth.get_valid_token(conn)
            assert token == "ya29.fresh-from-refresh"
            # Verify the connection was updated with new encrypted token
            assert conn.access_token_enc is not None
            assert conn.token_expiry > datetime.now(timezone.utc)


class TestRevokeConnection:
    def test_revoke_marks_revoked_and_clears_tokens(self, app, db, seed_tenant, seed_super_admin, monkeypatch):
        from api.services import google_oauth
        from api.models import OAuthConnection

        # Mock the revoke POST (best-effort, should not fail test)
        monkeypatch.setattr(google_oauth.requests, "post", lambda url, **kw: MagicMock())

        with app.app_context():
            access_enc = google_oauth.encrypt_token("ya29.to-revoke")
            refresh_enc = google_oauth.encrypt_token("1//to-revoke")

            conn = OAuthConnection(
                user_id=seed_super_admin.id,
                tenant_id=seed_tenant.id,
                provider="google",
                provider_account_id="sub-3",
                provider_email="revoke@gmail.com",
                access_token_enc=access_enc,
                refresh_token_enc=refresh_enc,
                status="active",
            )
            db.session.add(conn)
            db.session.flush()

            google_oauth.revoke_connection(conn)

            assert conn.status == "revoked"
            assert conn.access_token_enc is None
            assert conn.refresh_token_enc is None
