"""Unit tests for Gmail import routes (fetch, preview, execute Google Contacts)."""
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from api.models import ImportJob, OAuthConnection, UserTenantRole, db
from tests.conftest import auth_header

TEST_FERNET_KEY = Fernet.generate_key().decode()

SAMPLE_PARSED_ROWS = [
    {
        "contact": {
            "first_name": "John",
            "last_name": "Doe",
            "email_address": "john@acme.com",
            "job_title": "CEO",
            "phone_number": "+1234567890",
            "contact_source": "google_contacts",
        },
        "company": {"name": "Acme Corp", "domain": "acme.com"},
    },
    {
        "contact": {
            "first_name": "Jane",
            "last_name": "Smith",
            "email_address": "jane@beta.io",
            "job_title": "CTO",
            "phone_number": "",
            "contact_source": "google_contacts",
        },
        "company": {"name": "Beta Inc", "domain": "beta.io"},
    },
]

SAMPLE_RAW_CONTACTS = [
    {
        "resourceName": "people/c1",
        "names": [{"givenName": "John", "familyName": "Doe"}],
        "emailAddresses": [{"value": "john@acme.com"}],
        "organizations": [{"name": "Acme Corp", "title": "CEO"}],
        "phoneNumbers": [{"value": "+1234567890"}],
    },
    {
        "resourceName": "people/c2",
        "names": [{"givenName": "Jane", "familyName": "Smith"}],
        "emailAddresses": [{"value": "jane@beta.io"}],
        "organizations": [{"name": "Beta Inc", "title": "CTO"}],
    },
]


@pytest.fixture(autouse=True)
def _configure_oauth(app):
    """Set Google OAuth config for route tests."""
    app.config["OAUTH_ENCRYPTION_KEY"] = TEST_FERNET_KEY
    app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
    app.config["GOOGLE_REDIRECT_URI"] = "https://example.com/callback"


def _create_tenant_role(db, user, tenant):
    """Give user admin role on tenant so they can access tenant routes."""
    role = UserTenantRole(
        user_id=user.id,
        tenant_id=tenant.id,
        role="admin",
        granted_by=user.id,
    )
    db.session.add(role)
    db.session.commit()


def _create_oauth_connection(db, user, tenant, provider_email="test@gmail.com"):
    """Create an active OAuth connection for the user."""
    from api.services.google_oauth import encrypt_token

    conn = OAuthConnection(
        user_id=user.id,
        tenant_id=str(tenant.id),
        provider="google",
        provider_account_id="sub123",
        provider_email=provider_email,
        access_token_enc=encrypt_token("ya29.test-access-token"),
        refresh_token_enc=encrypt_token("1//test-refresh-token"),
        token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active",
    )
    db.session.add(conn)
    db.session.flush()
    return conn


def _create_import_job(db, tenant, user, parsed_rows=None, status="mapped"):
    """Create an ImportJob with Google Contacts source."""
    rows = parsed_rows or SAMPLE_PARSED_ROWS
    job = ImportJob(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        filename="google-contacts-test@gmail.com",
        total_rows=len(rows),
        headers=json.dumps(["first_name", "last_name", "email_address", "job_title", "phone_number", "company_name"]),
        sample_rows=json.dumps(rows[:5]),
        raw_csv=json.dumps(rows),
        source="google_contacts",
        status=status,
    )
    db.session.add(job)
    db.session.flush()
    return job


class TestFetchContacts:
    def test_fetch_requires_auth(self, client, db):
        resp = client.post("/api/gmail/contacts/fetch", json={"connection_id": "abc"})
        assert resp.status_code == 401

    def test_fetch_requires_connection_id(self, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post("/api/gmail/contacts/fetch", headers=headers, json={})
        assert resp.status_code == 400
        assert "connection_id" in resp.get_json()["error"]

    def test_fetch_invalid_connection(self, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/gmail/contacts/fetch",
            headers=headers,
            json={"connection_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"].lower()

    @patch("api.routes.gmail_routes.fetch_google_contacts")
    @patch("api.routes.gmail_routes.parse_contacts_to_rows")
    def test_fetch_success(self, mock_parse, mock_fetch, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)
        conn = _create_oauth_connection(db, seed_super_admin, seed_tenant)
        db.session.commit()

        mock_fetch.return_value = SAMPLE_RAW_CONTACTS
        mock_parse.return_value = SAMPLE_PARSED_ROWS

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/gmail/contacts/fetch",
            headers=headers,
            json={"connection_id": str(conn.id)},
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["total_contacts"] == 2
        assert body["job_id"]
        assert len(body["sample"]) == 2

        mock_fetch.assert_called_once_with(conn)
        mock_parse.assert_called_once_with(SAMPLE_RAW_CONTACTS)


class TestPreviewContacts:
    def test_preview_requires_auth(self, client, db):
        resp = client.post("/api/gmail/contacts/some-job-id/preview")
        assert resp.status_code == 401

    @patch("api.routes.gmail_routes.dedup_preview")
    def test_preview_success(self, mock_dedup, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)

        job = _create_import_job(db, seed_tenant, seed_super_admin)
        db.session.commit()

        mock_dedup.return_value = [
            {
                "contact": SAMPLE_PARSED_ROWS[0]["contact"],
                "company": SAMPLE_PARSED_ROWS[0]["company"],
                "contact_status": "new",
                "contact_match_type": None,
                "company_status": "new",
                "company_match_type": None,
            },
            {
                "contact": SAMPLE_PARSED_ROWS[1]["contact"],
                "company": SAMPLE_PARSED_ROWS[1]["company"],
                "contact_status": "duplicate",
                "contact_match_type": "email",
                "company_status": "existing",
                "company_match_type": "domain",
            },
        ]

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(f"/api/gmail/contacts/{job.id}/preview", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()

        assert body["job_id"] == str(job.id)
        assert body["total_rows"] == 2
        assert body["preview_count"] == 2
        assert body["summary"]["new_contacts"] == 1
        assert body["summary"]["duplicate_contacts"] == 1
        assert body["summary"]["new_companies"] == 1
        assert body["summary"]["existing_companies"] == 1

    def test_preview_not_found(self, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/gmail/contacts/00000000-0000-0000-0000-000000000000/preview",
            headers=headers,
        )
        assert resp.status_code == 404


class TestExecuteContactsImport:
    def test_execute_requires_auth(self, client, db):
        resp = client.post("/api/gmail/contacts/some-job-id/execute", json={})
        assert resp.status_code == 401

    @patch("api.routes.gmail_routes.execute_import")
    def test_execute_success(self, mock_exec, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)

        job = _create_import_job(db, seed_tenant, seed_super_admin)
        db.session.commit()

        mock_exec.return_value = {
            "counts": {
                "contacts_created": 2,
                "contacts_updated": 0,
                "contacts_skipped": 0,
                "companies_created": 2,
                "companies_linked": 0,
            },
            "dedup_rows": [
                {"contact_status": "created", "company_status": "created"},
                {"contact_status": "created", "company_status": "created"},
            ],
        }

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/gmail/contacts/{job.id}/execute",
            headers=headers,
            json={"batch_name": "google-import-test", "dedup_strategy": "skip"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "completed"
        assert body["counts"]["contacts_created"] == 2
        assert body["counts"]["companies_created"] == 2
        assert body["batch_name"] == "google-import-test"

        # Verify the mock was called with correct tenant_id and strategy
        call_kwargs = mock_exec.call_args
        assert call_kwargs[1]["strategy"] == "skip" or call_kwargs[0][-1] == "skip"

    def test_execute_already_completed(self, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)

        job = _create_import_job(db, seed_tenant, seed_super_admin, status="completed")
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/gmail/contacts/{job.id}/execute",
            headers=headers,
            json={"batch_name": "dup-test", "dedup_strategy": "skip"},
        )
        assert resp.status_code == 400
        assert "already" in resp.get_json()["error"].lower()

    def test_execute_invalid_strategy(self, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)

        job = _create_import_job(db, seed_tenant, seed_super_admin)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/gmail/contacts/{job.id}/execute",
            headers=headers,
            json={"dedup_strategy": "invalid_strategy"},
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.get_json()["error"]

    def test_execute_not_found(self, client, db, seed_tenant, seed_super_admin):
        _create_tenant_role(db, seed_super_admin, seed_tenant)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/gmail/contacts/00000000-0000-0000-0000-000000000000/execute",
            headers=headers,
            json={"dedup_strategy": "skip"},
        )
        assert resp.status_code == 404
