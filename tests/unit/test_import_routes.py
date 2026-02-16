"""Unit tests for import routes."""
import io
import json
from unittest.mock import patch

import pytest
from openpyxl import Workbook

from api.models import Contact, CustomFieldDefinition, ImportJob, db
from tests.conftest import auth_header


SAMPLE_CSV = "First Name,Last Name,Email,Company,Title\nJohn,Doe,john@test.com,TestCo,CEO\nJane,Smith,jane@other.com,OtherCo,CTO\n"


def _create_xlsx_bytes(headers, rows):
    """Create an in-memory XLSX file and return its bytes."""
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

MOCK_MAPPING = {
    "mappings": [
        {"csv_header": "First Name", "target": "contact.first_name", "confidence": 0.95, "transform": None},
        {"csv_header": "Last Name", "target": "contact.last_name", "confidence": 0.95, "transform": None},
        {"csv_header": "Email", "target": "contact.email_address", "confidence": 0.95, "transform": None},
        {"csv_header": "Company", "target": "company.name", "confidence": 0.90, "transform": None},
        {"csv_header": "Title", "target": "contact.job_title", "confidence": 0.85, "transform": None},
    ],
    "warnings": [],
}

MOCK_USAGE_INFO = {
    "model": "claude-sonnet-4-5-20250929",
    "input_tokens": 500,
    "output_tokens": 200,
    "duration_ms": 1500,
}


class TestUploadCSV:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_upload_success(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["total_rows"] == 2
        assert body["job_id"]
        assert body["mapping"]["mappings"][0]["target"] == "contact.first_name"
        assert body["mapping_confidence"] > 0

    def test_upload_no_file(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/imports/upload", headers=headers, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_upload_unsupported_format(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        data = {"file": (io.BytesIO(b"not csv"), "data.txt")}
        resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert "CSV" in resp.get_json()["error"] or "XLSX" in resp.get_json()["error"]

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_upload_xlsx_success(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        xlsx_bytes = _create_xlsx_bytes(
            ["First Name", "Last Name", "Email", "Company", "Title"],
            [
                {"First Name": "John", "Last Name": "Doe", "Email": "john@test.com", "Company": "TestCo", "Title": "CEO"},
                {"First Name": "Jane", "Last Name": "Smith", "Email": "jane@other.com", "Company": "OtherCo", "Title": "CTO"},
            ],
        )
        data = {"file": (io.BytesIO(xlsx_bytes), "contacts.xlsx")}
        resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["total_rows"] == 2
        assert body["job_id"]
        assert body["headers"] == ["First Name", "Last Name", "Email", "Company", "Title"]
        assert body["mapping_confidence"] > 0

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
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
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
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
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
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
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
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
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
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
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

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_upload_xlsx_preview_and_execute(self, mock_claude, client, seed_companies_contacts):
        """Full XLSX flow: upload → preview → execute."""
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        xlsx_bytes = _create_xlsx_bytes(
            ["First Name", "Last Name", "Email", "Company", "Title"],
            [
                {"First Name": "Xls", "Last Name": "One", "Email": "xls1@test.com", "Company": "XlsCo", "Title": "VP"},
                {"First Name": "Xls", "Last Name": "Two", "Email": "xls2@test.com", "Company": "XlsCo", "Title": "Dir"},
            ],
        )
        data = {"file": (io.BytesIO(xlsx_bytes), "team.xlsx")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        assert upload_resp.status_code == 201
        job_id = upload_resp.get_json()["job_id"]

        # Preview
        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        preview_resp = client.post(
            f"/api/imports/{job_id}/preview",
            headers=json_headers,
            json={"mapping": MOCK_MAPPING},
        )
        assert preview_resp.status_code == 200
        assert preview_resp.get_json()["total_rows"] == 2

        # Execute
        exec_resp = client.post(
            f"/api/imports/{job_id}/execute",
            headers=json_headers,
            json={"batch_name": "xlsx-import", "dedup_strategy": "skip"},
        )
        assert exec_resp.status_code == 200
        body = exec_resp.get_json()
        assert body["status"] == "completed"
        assert body["counts"]["contacts_created"] == 2


class TestImportStatus:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_status_returns_job(self, mock_claude, client, seed_companies_contacts):
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
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
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
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


class TestImportResults:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_results_after_execute(self, mock_claude, client, seed_companies_contacts):
        """Results endpoint returns dedup details after import."""
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        client.post(f"/api/imports/{job_id}/execute", headers=json_headers,
                    json={"batch_name": "results-test", "dedup_strategy": "skip"})

        resp = client.get(f"/api/imports/{job_id}/results", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert "summary" in body
        assert body["summary"]["contacts_created"] == 2
        assert body["total"] >= 2
        assert body["filter"] == "all"
        assert body["page"] == 1

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_results_filter_skipped(self, mock_claude, client, seed_companies_contacts):
        """Filter=skipped only returns skipped rows."""
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        client.post(f"/api/imports/{job_id}/execute", headers=json_headers,
                    json={"batch_name": "filter-test", "dedup_strategy": "skip"})

        resp = client.get(f"/api/imports/{job_id}/results?filter=skipped", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["filter"] == "skipped"
        # All rows are "created" in this test, so no skipped
        assert body["total"] == 0

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_results_stores_dedup_results_on_job(self, mock_claude, client, seed_companies_contacts):
        """dedup_results JSONB is populated on ImportJob after execute."""
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        client.post(f"/api/imports/{job_id}/execute", headers=json_headers,
                    json={"batch_name": "dedup-store-test", "dedup_strategy": "skip"})

        job = ImportJob.query.filter_by(id=job_id).first()
        dedup = job.dedup_results
        if isinstance(dedup, str):
            dedup = json.loads(dedup)
        assert "summary" in dedup
        assert "rows" in dedup
        assert dedup["summary"]["contacts_created"] == 2

    def test_results_not_found(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/imports/00000000-0000-0000-0000-000000000000/results", headers=headers)
        assert resp.status_code == 404

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_results_before_execute(self, mock_claude, client, seed_companies_contacts):
        """Results endpoint returns 400 if import not yet completed."""
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        resp = client.get(f"/api/imports/{job_id}/results", headers=headers)
        assert resp.status_code == 400


MOCK_REMAPPED = {
    "mappings": [
        {"csv_header": "First Name", "target": "contact.first_name", "confidence": 0.95, "transform": None},
        {"csv_header": "Last Name", "target": "contact.last_name", "confidence": 0.95, "transform": None},
        {"csv_header": "Email", "target": "contact.email_address", "confidence": 0.95, "transform": None},
        {"csv_header": "Company", "target": "company.name", "confidence": 0.90, "transform": None},
        {"csv_header": "Title", "target": "contact.job_title", "confidence": 0.85, "transform": None,
         "suggested_custom_field": {"entity_type": "contact", "field_key": "title_note",
                                    "field_label": "Title Note", "field_type": "text"}},
    ],
    "warnings": [],
}


class TestRemapImport:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_remap_updates_mapping(self, mock_claude, client, seed_companies_contacts):
        """Re-analyze should update the job's column mapping."""
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        # Now remap with a different mock response
        mock_claude.return_value = (MOCK_REMAPPED, MOCK_USAGE_INFO)
        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        resp = client.post(f"/api/imports/{job_id}/remap", headers=json_headers, json={})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["mapping"]["mappings"][4].get("suggested_custom_field") is not None

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_remap_completed_fails(self, mock_claude, client, seed_companies_contacts):
        """Cannot remap a completed import."""
        mock_claude.return_value = (MOCK_MAPPING, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "contacts.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        client.post(f"/api/imports/{job_id}/execute", headers=json_headers,
                    json={"batch_name": "remap-test", "dedup_strategy": "skip"})

        resp = client.post(f"/api/imports/{job_id}/remap", headers=json_headers, json={})
        assert resp.status_code == 400


MOCK_MAPPING_WITH_CUSTOM = {
    "mappings": [
        {"csv_header": "First Name", "target": "contact.first_name", "confidence": 0.95, "transform": None},
        {"csv_header": "Last Name", "target": "contact.last_name", "confidence": 0.95, "transform": None},
        {"csv_header": "Email", "target": "contact.email_address", "confidence": 0.95, "transform": None},
        {"csv_header": "Company", "target": "company.name", "confidence": 0.90, "transform": None},
        {"csv_header": "Alt Email", "target": "contact.custom.email_secondary", "confidence": 0.80, "transform": None},
        {"csv_header": "Tax ID", "target": "company.custom.tax_id", "confidence": 0.75, "transform": None},
    ],
    "warnings": [],
}

SAMPLE_CSV_WITH_CUSTOM = (
    "First Name,Last Name,Email,Company,Alt Email,Tax ID\n"
    "John,Doe,john@newco.com,NewCo,alt@john.com,DE123\n"
    "Jane,Smith,jane@newco.com,NewCo,alt@jane.com,DE123\n"
)


class TestCustomFieldImport:
    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_execute_creates_custom_field_defs(self, mock_claude, client, seed_companies_contacts):
        """Custom field definitions should be auto-created on execute."""
        mock_claude.return_value = (MOCK_MAPPING_WITH_CUSTOM, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV_WITH_CUSTOM.encode()), "custom.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        resp = client.post(
            f"/api/imports/{job_id}/execute",
            headers=json_headers,
            json={"batch_name": "custom-test", "dedup_strategy": "skip"},
        )
        assert resp.status_code == 200

        # Check that custom field definitions were created
        tenant_id = seed_companies_contacts["tenant"].id
        defs = CustomFieldDefinition.query.filter_by(tenant_id=str(tenant_id)).all()
        def_keys = {(d.entity_type, d.field_key) for d in defs}
        assert ("contact", "email_secondary") in def_keys
        assert ("company", "tax_id") in def_keys

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_execute_stores_custom_field_values(self, mock_claude, client, seed_companies_contacts):
        """Custom field values should be stored in contacts/companies JSONB."""
        mock_claude.return_value = (MOCK_MAPPING_WITH_CUSTOM, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV_WITH_CUSTOM.encode()), "custom.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        resp = client.post(
            f"/api/imports/{job_id}/execute",
            headers=json_headers,
            json={"batch_name": "custom-val-test", "dedup_strategy": "skip"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["counts"]["contacts_created"] == 2

        # Check the stored custom_fields on contacts
        tenant_id = seed_companies_contacts["tenant"].id
        ct = Contact.query.filter_by(
            tenant_id=str(tenant_id), first_name="John", last_name="Doe", email_address="john@newco.com",
        ).first()
        assert ct is not None
        cf = ct.custom_fields
        if isinstance(cf, str):
            cf = json.loads(cf)
        assert cf.get("email_secondary") == "alt@john.com"

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_execute_doesnt_duplicate_existing_defs(self, mock_claude, client, seed_companies_contacts):
        """If a custom field def already exists, don't create a duplicate."""
        tenant_id = seed_companies_contacts["tenant"].id
        # Pre-create a custom field definition
        cfd = CustomFieldDefinition(
            tenant_id=str(tenant_id), entity_type="contact",
            field_key="email_secondary", field_label="Secondary Email",
            field_type="email",
        )
        db.session.add(cfd)
        db.session.commit()

        mock_claude.return_value = (MOCK_MAPPING_WITH_CUSTOM, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV_WITH_CUSTOM.encode()), "custom.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        resp = client.post(
            f"/api/imports/{job_id}/execute",
            headers=json_headers,
            json={"batch_name": "no-dup-test", "dedup_strategy": "skip"},
        )
        assert resp.status_code == 200

        # Should still be only 1 contact email_secondary def (not duplicated)
        count = CustomFieldDefinition.query.filter_by(
            tenant_id=str(tenant_id), entity_type="contact", field_key="email_secondary",
        ).count()
        assert count == 1

    @patch("api.routes.import_routes.call_claude_for_mapping")
    def test_execute_uses_user_edited_label(self, mock_claude, client, seed_companies_contacts):
        """User-edited field_label in suggested_custom_field should be used for definition."""
        mapping_with_label = {
            "mappings": [
                {"csv_header": "First Name", "target": "contact.first_name", "confidence": 0.95, "transform": None},
                {"csv_header": "Last Name", "target": "contact.last_name", "confidence": 0.95, "transform": None},
                {"csv_header": "Email", "target": "contact.email_address", "confidence": 0.95, "transform": None},
                {"csv_header": "Company", "target": "company.name", "confidence": 0.90, "transform": None},
                {"csv_header": "Alt Email", "target": "contact.custom.email_secondary", "confidence": 0.80,
                 "transform": None, "suggested_custom_field": {
                     "entity_type": "contact", "field_key": "email_secondary",
                     "field_label": "Secondary Email Address", "field_type": "email",
                 }},
            ],
            "warnings": [],
        }
        mock_claude.return_value = (mapping_with_label, MOCK_USAGE_INFO)
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        data = {"file": (io.BytesIO(SAMPLE_CSV_WITH_CUSTOM.encode()), "custom.csv")}
        upload_resp = client.post("/api/imports/upload", headers=headers, data=data, content_type="multipart/form-data")
        job_id = upload_resp.get_json()["job_id"]

        # Override mapping with user-edited label before execute
        json_headers = dict(headers)
        json_headers["Content-Type"] = "application/json"
        client.post(f"/api/imports/{job_id}/preview", headers=json_headers, json={"mapping": mapping_with_label})

        resp = client.post(
            f"/api/imports/{job_id}/execute",
            headers=json_headers,
            json={"batch_name": "label-test", "dedup_strategy": "skip"},
        )
        assert resp.status_code == 200

        tenant_id = seed_companies_contacts["tenant"].id
        cfd = CustomFieldDefinition.query.filter_by(
            tenant_id=str(tenant_id), entity_type="contact", field_key="email_secondary",
        ).first()
        assert cfd is not None
        assert cfd.field_label == "Secondary Email Address"
        assert cfd.field_type == "email"
