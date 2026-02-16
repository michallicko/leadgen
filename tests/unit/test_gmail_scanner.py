"""Tests for gmail_scanner.py: header parsing, signature extraction, aggregation."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from api.services.gmail_scanner import GmailScanner, start_gmail_scan


# ---- Fixtures ----

@pytest.fixture
def scanner():
    """Create a GmailScanner with dummy oauth_connection and job_id."""
    conn = MagicMock()
    conn.id = "conn-123"
    return GmailScanner(conn, "job-456", {"max_messages": 100})


# ---- Display name splitting ----

class TestSplitDisplayName:
    def test_simple_name(self, scanner):
        assert scanner._split_display_name("John Doe") == ("John", "Doe")

    def test_single_name(self, scanner):
        assert scanner._split_display_name("John") == ("John", "")

    def test_empty(self, scanner):
        assert scanner._split_display_name("") == ("", "")

    def test_none(self, scanner):
        assert scanner._split_display_name(None) == ("", "")

    def test_quoted_name(self, scanner):
        assert scanner._split_display_name('"John Doe"') == ("John", "Doe")

    def test_multi_word_last_name(self, scanner):
        assert scanner._split_display_name("John van der Berg") == ("John", "van der Berg")


# ---- Date parsing ----

class TestParseDate:
    def test_rfc2822(self, scanner):
        result = scanner._parse_date("Mon, 15 Jan 2024 10:30:00 +0000")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    def test_empty(self, scanner):
        assert scanner._parse_date("") is None

    def test_none(self, scanner):
        assert scanner._parse_date(None) is None

    def test_invalid(self, scanner):
        assert scanner._parse_date("not a date") is None

    def test_naive_gets_utc(self, scanner):
        """Dates without timezone should get UTC attached."""
        result = scanner._parse_date("Mon, 15 Jan 2024 10:30:00")
        assert result is not None
        assert result.tzinfo is not None


# ---- Text body extraction ----

class TestExtractTextBody:
    def test_plain_text_direct(self, scanner):
        msg = {
            "payload": {
                "mimeType": "text/plain",
                "body": {
                    "data": base64.urlsafe_b64encode(b"Hello world").decode()
                }
            }
        }
        assert scanner._extract_text_body(msg) == "Hello world"

    def test_multipart_finds_plain(self, scanner):
        msg = {
            "payload": {
                "mimeType": "multipart/alternative",
                "body": {},
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(b"Plain text").decode()}},
                    {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<p>HTML</p>").decode()}},
                ]
            }
        }
        assert scanner._extract_text_body(msg) == "Plain text"

    def test_nested_multipart(self, scanner):
        msg = {
            "payload": {
                "mimeType": "multipart/mixed",
                "body": {},
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "body": {},
                        "parts": [
                            {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(b"Nested plain").decode()}},
                        ]
                    }
                ]
            }
        }
        assert scanner._extract_text_body(msg) == "Nested plain"

    def test_no_body(self, scanner):
        msg = {"payload": {"mimeType": "text/html", "body": {}}}
        assert scanner._extract_text_body(msg) is None


# ---- Signature block extraction ----

class TestExtractSignatureBlock:
    def test_double_dash_delimiter(self, scanner):
        body = "Hello,\n\nPlease find attached.\n\n-- \nJohn Doe\nCEO, Acme Inc\n+1 555-1234"
        sig = scanner._extract_signature_block(body)
        assert sig is not None
        assert "John Doe" in sig
        assert "+1 555-1234" in sig

    def test_regards_delimiter(self, scanner):
        body = "Thanks for the update.\n\nBest Regards,\nJane Smith\nVP Engineering\njane@acme.com"
        sig = scanner._extract_signature_block(body)
        assert sig is not None
        assert "Jane Smith" in sig

    def test_phone_pattern_fallback(self, scanner):
        body = "Some content\nMore content\nJohn Doe\nCEO\n+49 176 12345678\nlinkedin.com/in/johndoe"
        sig = scanner._extract_signature_block(body)
        assert sig is not None

    def test_empty_body(self, scanner):
        assert scanner._extract_signature_block("") is None
        assert scanner._extract_signature_block(None) is None

    def test_no_signature(self, scanner):
        body = "Hi,\n\nShort reply.\n\nOK."
        sig = scanner._extract_signature_block(body)
        # Should return None (no sig patterns found)
        assert sig is None


# ---- Message header processing ----

class TestProcessMessageHeaders:
    def test_basic_from_header(self, scanner):
        msg = {
            "id": "msg-1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "John Doe <john@acme.com>"},
                    {"name": "Date", "value": "Mon, 15 Jan 2024 10:30:00 +0000"},
                ]
            }
        }
        scanner._process_message_headers(msg, set())
        assert "john@acme.com" in scanner.contacts
        assert scanner.contacts["john@acme.com"]["first_name"] == "John"
        assert scanner.contacts["john@acme.com"]["last_name"] == "Doe"

    def test_to_cc_headers(self, scanner):
        msg = {
            "id": "msg-2",
            "payload": {
                "headers": [
                    {"name": "From", "value": "me@example.com"},
                    {"name": "To", "value": "Alice <alice@beta.io>, Bob <bob@gamma.co>"},
                    {"name": "Cc", "value": "Carol <carol@delta.de>"},
                ]
            }
        }
        scanner._process_message_headers(msg, set())
        assert "alice@beta.io" in scanner.contacts
        assert "bob@gamma.co" in scanner.contacts
        assert "carol@delta.de" in scanner.contacts

    def test_excludes_domains(self, scanner):
        msg = {
            "id": "msg-3",
            "payload": {
                "headers": [
                    {"name": "From", "value": "John <john@excluded.com>"},
                    {"name": "To", "value": "Jane <jane@allowed.com>"},
                ]
            }
        }
        scanner._process_message_headers(msg, {"excluded.com"})
        assert "john@excluded.com" not in scanner.contacts
        assert "jane@allowed.com" in scanner.contacts

    def test_excludes_service_emails(self, scanner):
        msg = {
            "id": "msg-4",
            "payload": {
                "headers": [
                    {"name": "From", "value": "noreply@example.com"},
                    {"name": "To", "value": "notifications@service.io"},
                ]
            }
        }
        scanner._process_message_headers(msg, set())
        assert "noreply@example.com" not in scanner.contacts
        assert "notifications@service.io" not in scanner.contacts

    def test_message_count_increments(self, scanner):
        for i in range(3):
            msg = {
                "id": f"msg-{i}",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "repeat@acme.com"},
                    ]
                }
            }
            scanner._process_message_headers(msg, set())
        assert scanner.contacts["repeat@acme.com"]["message_count"] == 3

    def test_skips_invalid_emails(self, scanner):
        msg = {
            "id": "msg-5",
            "payload": {
                "headers": [
                    {"name": "From", "value": "not-an-email"},
                    {"name": "To", "value": "valid@acme.com"},
                ]
            }
        }
        scanner._process_message_headers(msg, set())
        assert "valid@acme.com" in scanner.contacts
        assert len(scanner.contacts) == 1

    def test_updates_name_with_newer_message(self, scanner):
        """Most recent message should update name if previously empty."""
        msg1 = {
            "id": "msg-old",
            "payload": {
                "headers": [
                    {"name": "From", "value": "user@acme.com"},
                    {"name": "Date", "value": "Mon, 01 Jan 2024 10:00:00 +0000"},
                ]
            }
        }
        msg2 = {
            "id": "msg-new",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice Wonder <user@acme.com>"},
                    {"name": "Date", "value": "Tue, 15 Jan 2024 10:00:00 +0000"},
                ]
            }
        }
        scanner._process_message_headers(msg1, set())
        assert scanner.contacts["user@acme.com"]["first_name"] == ""
        scanner._process_message_headers(msg2, set())
        assert scanner.contacts["user@acme.com"]["first_name"] == "Alice"


# ---- Save extracted ----

class TestSaveExtracted:
    def test_converts_to_dedup_format(self, scanner, app, db):
        """Verify saved rows match dedup-compatible format."""
        scanner.contacts = {
            "john@acme.com": {
                "email": "john@acme.com",
                "first_name": "John",
                "last_name": "Doe",
                "domain": "acme.com",
                "message_count": 5,
                "last_message_date": None,
                "job_title": "CEO",
                "company_name": "Acme Corp",
                "phone": "+1-555-1234",
            },
            "plain@beta.io": {
                "email": "plain@beta.io",
                "first_name": "",
                "last_name": "",
                "domain": "beta.io",
                "message_count": 1,
                "last_message_date": None,
            },
        }

        with app.app_context():
            from api.models import ImportJob as IJ
            job = IJ(
                tenant_id="t-1",
                user_id="u-1",
                filename="test",
                total_rows=0,
                headers=json.dumps([]),
                status="scanning",
                source="gmail_scan",
            )
            db.session.add(job)
            db.session.commit()
            scanner.job_id = job.id

            scanner._save_extracted()

            db.session.refresh(job)
            rows = json.loads(job.raw_csv)

            assert len(rows) == 2

            # Find John's row
            john_row = [r for r in rows if r["contact"]["email_address"] == "john@acme.com"][0]
            assert john_row["contact"]["first_name"] == "John"
            assert john_row["contact"]["job_title"] == "CEO"
            assert john_row["contact"]["contact_source"] == "gmail_scan"
            assert john_row["company"]["name"] == "Acme Corp"
            assert john_row["company"]["domain"] == "acme.com"

            # Plain contact: falls back to email local part for first_name
            plain_row = [r for r in rows if r["contact"]["email_address"] == "plain@beta.io"][0]
            assert plain_row["contact"]["first_name"] == "plain"


# ---- Claude batch extraction ----

def _make_mock_anthropic(response_text, input_tokens=100, output_tokens=50):
    """Create a mock anthropic module with preset response."""
    import sys
    mock_mod = MagicMock()
    mock_client = MagicMock()
    mock_mod.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = response_text
    mock_response.usage.input_tokens = input_tokens
    mock_response.usage.output_tokens = output_tokens
    mock_client.messages.create.return_value = mock_response
    return mock_mod


class TestBatchExtractWithClaude:
    def test_applies_extracted_data(self, scanner, app, db):
        """Claude response data should be applied to contacts."""
        import sys
        scanner.contacts = {
            "alice@acme.com": {
                "email": "alice@acme.com",
                "first_name": "Alice",
                "last_name": "",
                "domain": "acme.com",
                "message_count": 1,
                "last_message_date": None,
            },
        }

        mock_anthropic = _make_mock_anthropic(json.dumps([
            {
                "index": 0,
                "name": "Alice Smith",
                "job_title": "VP Engineering",
                "company": "Acme Corp",
                "phone": "+1-555-0001",
                "linkedin_url": "https://linkedin.com/in/alicesmith",
            }
        ]))

        with app.app_context():
            from api.models import ImportJob as IJ
            job = IJ(
                tenant_id="t-1",
                user_id="u-1",
                filename="test",
                total_rows=0,
                headers=json.dumps([]),
                status="scanning",
                source="gmail_scan",
            )
            db.session.add(job)
            db.session.commit()
            scanner.job_id = job.id

            old = sys.modules.get("anthropic")
            sys.modules["anthropic"] = mock_anthropic
            try:
                signatures = {"alice@acme.com": "Alice Smith\nVP Engineering\nAcme Corp\n+1-555-0001"}
                scanner._batch_extract_with_claude(app, signatures)
            finally:
                if old is not None:
                    sys.modules["anthropic"] = old
                else:
                    sys.modules.pop("anthropic", None)

            c = scanner.contacts["alice@acme.com"]
            assert c["job_title"] == "VP Engineering"
            assert c["company_name"] == "Acme Corp"
            assert c["phone"] == "+1-555-0001"
            assert c["linkedin_url"] == "https://linkedin.com/in/alicesmith"

    def test_handles_invalid_json(self, scanner, app, db):
        """Should gracefully handle non-JSON Claude response."""
        import sys
        scanner.contacts = {"bob@test.com": {"email": "bob@test.com", "first_name": "Bob", "last_name": "", "domain": "test.com", "message_count": 1, "last_message_date": None}}

        mock_anthropic = _make_mock_anthropic("I couldn't parse the signatures", 50, 10)

        with app.app_context():
            from api.models import ImportJob as IJ
            job = IJ(tenant_id="t-1", user_id="u-1", filename="test", total_rows=0, headers=json.dumps([]), status="scanning", source="gmail_scan")
            db.session.add(job)
            db.session.commit()
            scanner.job_id = job.id

            old = sys.modules.get("anthropic")
            sys.modules["anthropic"] = mock_anthropic
            try:
                signatures = {"bob@test.com": "Some sig text"}
                scanner._batch_extract_with_claude(app, signatures)
            finally:
                if old is not None:
                    sys.modules["anthropic"] = old
                else:
                    sys.modules.pop("anthropic", None)

            assert scanner.contacts["bob@test.com"].get("job_title") is None

    def test_handles_json_in_text(self, scanner, app, db):
        """Should find JSON array embedded in text response."""
        import sys
        scanner.contacts = {"carol@test.com": {"email": "carol@test.com", "first_name": "Carol", "last_name": "", "domain": "test.com", "message_count": 1, "last_message_date": None}}

        mock_anthropic = _make_mock_anthropic(
            'Here are the results: [{"index": 0, "job_title": "CTO", "company": "Test Inc"}]',
            50, 20,
        )

        with app.app_context():
            from api.models import ImportJob as IJ
            job = IJ(tenant_id="t-1", user_id="u-1", filename="test", total_rows=0, headers=json.dumps([]), status="scanning", source="gmail_scan")
            db.session.add(job)
            db.session.commit()
            scanner.job_id = job.id

            old = sys.modules.get("anthropic")
            sys.modules["anthropic"] = mock_anthropic
            try:
                signatures = {"carol@test.com": "Carol\nCTO\nTest Inc"}
                scanner._batch_extract_with_claude(app, signatures)
            finally:
                if old is not None:
                    sys.modules["anthropic"] = old
                else:
                    sys.modules.pop("anthropic", None)

            assert scanner.contacts["carol@test.com"]["job_title"] == "CTO"


# ---- Scan route tests ----

class TestScanRoutes:
    def test_start_scan_requires_auth(self, client):
        resp = client.post("/api/gmail/scan/start", json={"connection_id": "x"})
        assert resp.status_code == 401

    def test_start_scan_requires_connection_id(self, client, seed_super_admin, seed_tenant):
        from tests.conftest import auth_header
        from api.models import UserTenantRole, db as _db
        role = UserTenantRole(user_id=seed_super_admin.id, tenant_id=seed_tenant.id, role="admin", granted_by=seed_super_admin.id)
        _db.session.add(role)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/gmail/scan/start", json={}, headers=headers)
        assert resp.status_code == 400
        assert "connection_id" in resp.get_json()["error"]

    @patch("api.routes.gmail_routes.start_gmail_scan")
    def test_start_scan_creates_job(self, mock_scan, client, seed_super_admin, seed_tenant):
        from tests.conftest import auth_header
        from api.models import OAuthConnection, UserTenantRole, db as _db

        role = UserTenantRole(user_id=seed_super_admin.id, tenant_id=seed_tenant.id, role="admin", granted_by=seed_super_admin.id)
        _db.session.add(role)
        _db.session.flush()

        conn = OAuthConnection(
            user_id=seed_super_admin.id,
            tenant_id=str(seed_tenant.id),
            provider="google",
            provider_email="test@gmail.com",
            status="active",
        )
        _db.session.add(conn)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        headers["Content-Type"] = "application/json"

        resp = client.post("/api/gmail/scan/start", json={
            "connection_id": str(conn.id),
            "date_range": 30,
            "exclude_domains": ["gmail.com"],
        }, headers=headers)

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "scanning"
        assert "job_id" in data
        mock_scan.assert_called_once()

    @patch("api.routes.gmail_routes.start_gmail_scan")
    def test_scan_status(self, mock_scan, client, seed_super_admin, seed_tenant):
        from tests.conftest import auth_header
        from api.models import ImportJob, OAuthConnection, UserTenantRole, db as _db

        role = UserTenantRole(user_id=seed_super_admin.id, tenant_id=seed_tenant.id, role="admin", granted_by=seed_super_admin.id)
        _db.session.add(role)
        _db.session.flush()

        conn = OAuthConnection(
            user_id=seed_super_admin.id,
            tenant_id=str(seed_tenant.id),
            provider="google",
            provider_email="test@gmail.com",
            status="active",
        )
        _db.session.add(conn)
        _db.session.flush()

        job = ImportJob(
            tenant_id=str(seed_tenant.id),
            user_id=seed_super_admin.id,
            filename="gmail-scan-test",
            total_rows=0,
            headers=json.dumps([]),
            source="gmail_scan",
            oauth_connection_id=str(conn.id),
            status="scanning",
            scan_progress=json.dumps({"phase": "scanning_headers", "percent": 25, "messages_scanned": 50, "contacts_found": 12}),
        )
        _db.session.add(job)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get(f"/api/gmail/scan/{job.id}/status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "scanning"
        assert data["scan_progress"]["phase"] == "scanning_headers"
        assert data["scan_progress"]["percent"] == 25

    def test_scan_status_not_found(self, client, seed_super_admin, seed_tenant):
        from tests.conftest import auth_header
        from api.models import UserTenantRole, db as _db

        role = UserTenantRole(user_id=seed_super_admin.id, tenant_id=seed_tenant.id, role="admin", granted_by=seed_super_admin.id)
        _db.session.add(role)
        _db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/gmail/scan/nonexistent-id/status", headers=headers)
        assert resp.status_code == 404
