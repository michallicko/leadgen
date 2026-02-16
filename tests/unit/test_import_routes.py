"""Unit tests for import routes."""
import io
import json
from unittest.mock import patch

import pytest

from api.models import ImportJob, db
from tests.conftest import auth_header


SAMPLE_CSV = "Name,Email,Company,Title\nJohn Doe,john@test.com,TestCo,CEO\nJane Smith,jane@other.com,OtherCo,CTO\n"

MOCK_MAPPING = {
    "mappings": [
        {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.95, "transform": None},
        {"csv_header": "Email", "target": "contact.email_address", "confidence": 0.95, "transform": None},
        {"csv_header": "Company", "target": "company.name", "confidence": 0.90, "transform": None},
        {"csv_header": "Title", "target": "contact.job_title", "confidence": 0.85, "transform": None},
    ],
    "warnings": [],
    "combine_columns": [],
}


class TestUploadCSV:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_upload_success(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = MOCK_MAPPING
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["total_rows"] == 2
        assert body["job_id"]
        assert body["mapping"]["mappings"][0]["target"] == "contact.full_name"
        assert body["mapping_confidence"] > 0

    def test_upload_no_file(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/imports/upload", headers=headers, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_upload_non_csv(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = {"file": (io.BytesIO(b"not csv"), "data.txt")}
        resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert "CSV" in resp.get_json()["error"]

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_upload_ai_failure_graceful(self, mock_claude, client, seed_companies_contacts):
        mock_claude.side_effect = RuntimeError("API key invalid")
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        # Should still succeed with empty mapping and a warning
        assert resp.status_code == 201
        body = resp.get_json()
        assert "AI mapping failed" in body["mapping"]["warnings"][0]

    def test_upload_requires_auth(self, client, db):
        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        resp = client.post("/api/imports/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 401


class TestPreviewImport:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_preview_returns_dedup_results(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = MOCK_MAPPING
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Upload first
        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        # Preview
        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        resp = client.post(
            f"/api/imports/{job_id}/preview",
            headers=json_headers,
            json={"mapping": MOCK_MAPPING},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total_rows"] == 2
        assert len(body["preview_rows"]) == 2
        assert "summary" in body
        assert body["summary"]["new_contacts"] >= 0

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_preview_detects_existing(self, mock_claude, client, seed_companies_contacts):
        """CSV with email matching existing contact should show duplicate."""
        csv = "Name,Email,Company,Title\nJohn Doe,john@acme.com,Acme Corp,CEO\n"
        mock_claude.return_value = MOCK_MAPPING
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(csv.encode()), "dup.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        resp = client.post(
            f"/api/imports/{job_id}/preview",
            headers=json_headers,
            json={"mapping": MOCK_MAPPING},
        )
        body = resp.get_json()
        assert body["preview_rows"][0]["contact_status"] == "duplicate"
        assert body["summary"]["duplicate_contacts"] == 1

    def test_preview_not_found(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        headers["Content-Type"] = "application/json"
        resp = client.post("/api/imports/00000000-0000-0000-0000-000000000000/preview", headers=headers, json={})
        assert resp.status_code == 404


class TestExecuteImport:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_execute_creates_records(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = MOCK_MAPPING
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        resp = client.post(
            f"/api/imports/{job_id}/execute",
            headers=json_headers,
            json={"batch_name": "test-import", "dedup_strategy": "skip"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "completed"
        assert body["counts"]["contacts_created"] == 2
        assert body["counts"]["companies_created"] == 2

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_execute_idempotent(self, mock_claude, client, seed_companies_contacts):
        """Second execute should fail (already completed)."""
        mock_claude.return_value = MOCK_MAPPING
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        client.post(f"/api/imports/{job_id}/execute", headers=json_headers, json={"batch_name": "test-import"})
        resp2 = client.post(f"/api/imports/{job_id}/execute", headers=json_headers, json={"batch_name": "test-import"})
        assert resp2.status_code == 400
        assert "already" in resp2.get_json()["error"].lower()

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_execute_invalid_strategy(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = MOCK_MAPPING
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        resp = client.post(
            f"/api/imports/{job_id}/execute",
            headers=json_headers,
            json={"dedup_strategy": "invalid"},
        )
        assert resp.status_code == 400


class TestImportStatus:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_status_returns_job(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = MOCK_MAPPING
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        resp = client.get(f"/api/imports/{job_id}/status", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["id"] == job_id
        assert body["status"] == "mapped"


class TestListImports:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_list_returns_jobs(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = MOCK_MAPPING
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Upload a CSV
        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")

        resp = client.get("/api/imports", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["imports"]) >= 1
        assert body["imports"][0]["filename"] == "contacts.csv"

    def test_list_empty(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/imports", headers=headers)
        assert resp.status_code == 200
        assert body_imports_empty_or_valid(resp)


def body_imports_empty_or_valid(resp):
    body = resp.get_json()
    return "imports" in body
