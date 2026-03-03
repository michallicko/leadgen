"""Unit tests for Sprint 3A Track A2 — BL-072, BL-073, BL-074.

BL-072: Enrichment gaps in cost estimate + skip_unenriched in generate
BL-073: Rejection feedback min-length (frontend-only, no backend tests needed)
BL-074: CSV export with formula injection sanitization
"""

import csv
import io

from api.models import (
    EntityStageCompletion,
    Message,
    db,
)
from tests.conftest import auth_header


# ── Helpers ──────────────────────────────────────────────


def _headers(client):
    h = auth_header(client)
    h["X-Namespace"] = "test-corp"
    return h


def _create_ready_campaign(client, headers, seed, template_config=None):
    """Create a campaign with 2 contacts and template, moved to ready status."""
    resp = client.post("/api/campaigns", headers=headers, json={"name": "Test Campaign"})
    cid = resp.get_json()["id"]

    if template_config is None:
        template_config = [
            {"step": 1, "channel": "linkedin_connect", "label": "LI Invite", "enabled": True},
            {"step": 2, "channel": "email", "label": "Email 1", "enabled": True},
        ]
    client.patch(
        f"/api/campaigns/{cid}",
        headers=headers,
        json={"template_config": template_config},
    )

    contact_ids = [str(seed["contacts"][0].id), str(seed["contacts"][1].id)]
    client.post(
        f"/api/campaigns/{cid}/contacts",
        headers=headers,
        json={"contact_ids": contact_ids},
    )

    client.patch(f"/api/campaigns/{cid}", headers=headers, json={"status": "ready"})
    return cid


# ── BL-072: Enrichment Gaps in Cost Estimate ─────────────


class TestCostEstimateEnrichmentGaps:
    """Cost estimate should include enrichment_gaps with unenriched contacts."""

    def test_cost_estimate_includes_enrichment_gaps_field(self, client, seed_companies_contacts):
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        # enrichment_gaps should always be present
        assert "enrichment_gaps" in data
        gaps = data["enrichment_gaps"]
        assert "total_contacts" in gaps
        assert "enriched_contacts" in gaps
        assert "unenriched_contacts" in gaps
        assert "gap_details" in gaps

    def test_no_enrichment_all_contacts_unenriched(self, client, seed_companies_contacts):
        """Without entity_stage_completions, all contacts are unenriched."""
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        data = resp.get_json()
        gaps = data["enrichment_gaps"]

        assert gaps["total_contacts"] == 2
        assert gaps["enriched_contacts"] == 0
        assert gaps["unenriched_contacts"] == 2
        assert len(gaps["gap_details"]) == 2

        # Each should have missing_stages
        for detail in gaps["gap_details"]:
            assert "contact_id" in detail
            assert "name" in detail
            assert "missing_stages" in detail
            assert "person_enrichment" in detail["missing_stages"]

    def test_enriched_contact_not_in_gaps(self, client, seed_companies_contacts):
        """Contact with completed person_enrichment + company l2 should not be in gaps."""
        headers = _headers(client)
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id
        tag_id = seed["tags"][0].id
        contact = seed["contacts"][0]

        # Create enrichment completions for contact[0] (person) and its company (l2)
        esc_person = EntityStageCompletion(
            tenant_id=tenant_id,
            tag_id=tag_id,
            entity_type="contact",
            entity_id=str(contact.id),
            stage="person_enrichment",
            status="completed",
        )
        esc_company = EntityStageCompletion(
            tenant_id=tenant_id,
            tag_id=tag_id,
            entity_type="company",
            entity_id=str(contact.company_id),
            stage="l2_deep_research",
            status="completed",
        )
        db.session.add_all([esc_person, esc_company])
        db.session.commit()

        cid = _create_ready_campaign(client, headers, seed)

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        data = resp.get_json()
        gaps = data["enrichment_gaps"]

        # Contact[0] is enriched, contact[1] is not
        assert gaps["enriched_contacts"] == 1
        assert gaps["unenriched_contacts"] == 1
        assert len(gaps["gap_details"]) == 1

        # The gap should be contact[1], not contact[0]
        gap_contact_ids = [d["contact_id"] for d in gaps["gap_details"]]
        assert str(contact.id) not in gap_contact_ids

    def test_partial_enrichment_shows_missing_stages(self, client, seed_companies_contacts):
        """Contact with person_enrichment but without company l2 should show l2 missing."""
        headers = _headers(client)
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id
        tag_id = seed["tags"][0].id
        contact = seed["contacts"][0]

        # Only person enrichment, no company l2
        esc = EntityStageCompletion(
            tenant_id=tenant_id,
            tag_id=tag_id,
            entity_type="contact",
            entity_id=str(contact.id),
            stage="person_enrichment",
            status="completed",
        )
        db.session.add(esc)
        db.session.commit()

        cid = _create_ready_campaign(client, headers, seed)

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        data = resp.get_json()
        gaps = data["enrichment_gaps"]

        # Contact[0] is partially enriched (missing l2), still shows as unenriched
        details = [d for d in gaps["gap_details"] if d["contact_id"] == str(contact.id)]
        assert len(details) == 1
        assert "l2_deep_research" in details[0]["missing_stages"]
        assert "person_enrichment" not in details[0]["missing_stages"]


# ── BL-074: CSV Export ───────────────────────────────────


class TestCsvExport:
    """CSV export endpoint with formula injection sanitization."""

    def test_export_csv_returns_csv_response(self, client, seed_companies_contacts):
        """Export endpoint should return CSV with correct Content-Type and Content-Disposition."""
        headers = _headers(client)
        seed = seed_companies_contacts

        # Create campaign with approved messages
        cid = _create_ready_campaign(client, headers, seed)

        # Get campaign contacts
        cc_rows = db.session.execute(
            db.text("SELECT id, contact_id FROM campaign_contacts WHERE campaign_id = :cid"),
            {"cid": cid},
        ).fetchall()

        # Add an approved message
        msg = Message(
            tenant_id=seed["tenant"].id,
            contact_id=str(cc_rows[0][1]),
            channel="email",
            sequence_step=1,
            variant="a",
            body="Hello there",
            status="approved",
            campaign_contact_id=str(cc_rows[0][0]),
        )
        db.session.add(msg)
        db.session.commit()

        resp = client.get(f"/api/campaigns/{cid}/messages/export-csv", headers=headers)
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"
        assert "Content-Disposition" in resp.headers
        assert "attachment" in resp.headers["Content-Disposition"]
        assert ".csv" in resp.headers["Content-Disposition"]

    def test_export_csv_has_correct_headers(self, client, seed_companies_contacts):
        """CSV should have the expected column headers."""
        headers = _headers(client)
        seed = seed_companies_contacts
        cid = _create_ready_campaign(client, headers, seed)

        # Add approved message
        cc_rows = db.session.execute(
            db.text("SELECT id, contact_id FROM campaign_contacts WHERE campaign_id = :cid"),
            {"cid": cid},
        ).fetchall()
        msg = Message(
            tenant_id=seed["tenant"].id,
            contact_id=str(cc_rows[0][1]),
            channel="email",
            sequence_step=1,
            variant="a",
            body="Test",
            status="approved",
            campaign_contact_id=str(cc_rows[0][0]),
        )
        db.session.add(msg)
        db.session.commit()

        resp = client.get(f"/api/campaigns/{cid}/messages/export-csv", headers=headers)
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8")))
        csv_headers = next(reader)

        expected = [
            "First Name", "Last Name", "Email", "LinkedIn URL", "Job Title",
            "Company", "Domain", "Channel", "Step", "Label",
            "Subject", "Body", "Status", "Tone", "Cost (USD)", "Approved At",
        ]
        assert csv_headers == expected

    def test_export_csv_contains_message_data(self, client, seed_companies_contacts):
        """CSV data rows should contain the message and contact data."""
        headers = _headers(client)
        seed = seed_companies_contacts
        cid = _create_ready_campaign(client, headers, seed)

        cc_rows = db.session.execute(
            db.text("SELECT id, contact_id FROM campaign_contacts WHERE campaign_id = :cid"),
            {"cid": cid},
        ).fetchall()
        msg = Message(
            tenant_id=seed["tenant"].id,
            contact_id=str(cc_rows[0][1]),
            channel="linkedin_connect",
            sequence_step=1,
            variant="a",
            subject="Let's connect",
            body="Hi, would love to connect",
            status="approved",
            campaign_contact_id=str(cc_rows[0][0]),
        )
        db.session.add(msg)
        db.session.commit()

        resp = client.get(f"/api/campaigns/{cid}/messages/export-csv", headers=headers)
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8")))
        next(reader)  # skip headers
        rows = list(reader)

        assert len(rows) == 1
        # Body should be present
        row = rows[0]
        assert "Hi, would love to connect" in row[11]  # body column

    def test_export_csv_filters_by_status(self, client, seed_companies_contacts):
        """By default, only approved messages are exported."""
        headers = _headers(client)
        seed = seed_companies_contacts
        cid = _create_ready_campaign(client, headers, seed)

        cc_rows = db.session.execute(
            db.text("SELECT id, contact_id FROM campaign_contacts WHERE campaign_id = :cid"),
            {"cid": cid},
        ).fetchall()

        # Add one approved and one draft message
        msg_approved = Message(
            tenant_id=seed["tenant"].id,
            contact_id=str(cc_rows[0][1]),
            channel="email",
            sequence_step=1,
            variant="a",
            body="Approved msg",
            status="approved",
            campaign_contact_id=str(cc_rows[0][0]),
        )
        msg_draft = Message(
            tenant_id=seed["tenant"].id,
            contact_id=str(cc_rows[1][1]),
            channel="email",
            sequence_step=1,
            variant="a",
            body="Draft msg",
            status="draft",
            campaign_contact_id=str(cc_rows[1][0]),
        )
        db.session.add_all([msg_approved, msg_draft])
        db.session.commit()

        # Default (approved only)
        resp = client.get(f"/api/campaigns/{cid}/messages/export-csv", headers=headers)
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8")))
        next(reader)
        rows = list(reader)
        assert len(rows) == 1
        assert "Approved msg" in rows[0][11]

        # All statuses
        resp = client.get(
            f"/api/campaigns/{cid}/messages/export-csv?status=all", headers=headers,
        )
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8")))
        next(reader)
        rows = list(reader)
        assert len(rows) == 2

    def test_export_csv_campaign_not_found(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.get(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/messages/export-csv",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_export_csv_requires_auth(self, client, db):
        resp = client.get("/api/campaigns/some-id/messages/export-csv")
        assert resp.status_code == 401

    def test_export_csv_empty_when_no_approved_messages(self, client, seed_companies_contacts):
        """Export with no approved messages should return CSV with headers only."""
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        resp = client.get(f"/api/campaigns/{cid}/messages/export-csv", headers=headers)
        assert resp.status_code == 200
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8")))
        csv_headers = next(reader)
        rows = list(reader)
        assert len(csv_headers) == 16
        assert len(rows) == 0


class TestCsvSanitization:
    """Formula injection sanitization for CSV cells."""

    def test_sanitize_formula_prefix_equals(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell("=SUM(A1)") == "'=SUM(A1)"

    def test_sanitize_formula_prefix_plus(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell("+cmd('calc')") == "'+cmd('calc')"

    def test_sanitize_formula_prefix_minus(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell("-1+cmd()") == "'-1+cmd()"

    def test_sanitize_formula_prefix_at(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell("@SUM(A1)") == "'@SUM(A1)"

    def test_sanitize_formula_prefix_tab(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell("\tmalicious") == "'\tmalicious"

    def test_sanitize_formula_prefix_cr(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell("\revil") == "'\revil"

    def test_sanitize_normal_text_unchanged(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell("Hello World") == "Hello World"

    def test_sanitize_none_returns_empty(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell(None) == ""

    def test_sanitize_empty_string_unchanged(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell("") == ""

    def test_sanitize_number_unchanged(self):
        from api.routes.campaign_routes import _sanitize_csv_cell
        assert _sanitize_csv_cell(42) == "42"
