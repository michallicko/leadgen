"""Unit tests for generation progress endpoints (Task 4).

Tests cover:
- POST /api/campaigns/<id>/generate (start generation)
- GET /api/campaigns/<id>/generation-status (poll progress with channels + failed)
- POST /api/campaigns/<id>/cost-estimate (estimate cost)
- DELETE /api/campaigns/<id>/generate (cancel generation)
"""

import json
from unittest.mock import patch

from api.models import Campaign, CampaignContact, Message, db
from tests.conftest import auth_header


# ── Helpers ──────────────────────────────────────────────


def _headers(client):
    h = auth_header(client)
    h["X-Namespace"] = "test-corp"
    return h


def _create_ready_campaign(client, headers, seed, template_config=None):
    """Create a campaign with contacts and template, moved to ready status."""
    resp = client.post("/api/campaigns", headers=headers, json={"name": "Gen Test"})
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


# ── POST /generate ──────────────────────────────────────


class TestStartGeneration:
    @patch("api.routes.campaign_routes.start_generation")
    def test_start_generation_success(self, mock_start, client, seed_companies_contacts):
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        resp = client.post(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "generating"
        assert data["ok"] is True
        mock_start.assert_called_once()

    @patch("api.routes.campaign_routes.start_generation")
    def test_start_generation_transitions_status(self, mock_start, client, seed_companies_contacts):
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        client.post(f"/api/campaigns/{cid}/generate", headers=headers)

        # Verify campaign status changed
        resp = client.get(f"/api/campaigns/{cid}", headers=headers)
        assert resp.get_json()["status"] == "Generating"

    def test_start_generation_requires_ready_status(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post("/api/campaigns", headers=headers, json={"name": "Draft"})
        cid = resp.get_json()["id"]

        resp = client.post(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 400
        assert "ready" in resp.get_json()["error"].lower()

    def test_start_generation_requires_contacts(self, client, seed_companies_contacts):
        headers = _headers(client)

        # Create campaign with template but no contacts, then move to ready
        resp = client.post("/api/campaigns", headers=headers, json={"name": "No Contacts"})
        cid = resp.get_json()["id"]
        template_config = [
            {"step": 1, "channel": "email", "label": "Email", "enabled": True},
        ]
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={
            "template_config": template_config,
        })
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={"status": "ready"})

        resp = client.post(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 400
        assert "contacts" in resp.get_json()["error"].lower()

    def test_start_generation_requires_enabled_steps(self, client, seed_companies_contacts):
        headers = _headers(client)
        seed = seed_companies_contacts

        # Create campaign with all-disabled template
        resp = client.post("/api/campaigns", headers=headers, json={"name": "No Steps"})
        cid = resp.get_json()["id"]
        template_config = [
            {"step": 1, "channel": "email", "label": "Email", "enabled": False},
        ]
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={
            "template_config": template_config,
        })
        contact_ids = [str(seed["contacts"][0].id)]
        client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "contact_ids": contact_ids,
        })
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={"status": "ready"})

        resp = client.post(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 400
        assert "enabled" in resp.get_json()["error"].lower()

    def test_start_generation_campaign_not_found(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/generate",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_start_generation_requires_auth(self, client, db):
        resp = client.post("/api/campaigns/some-id/generate")
        assert resp.status_code == 401


# ── GET /generation-status ──────────────────────────────


class TestGenerationStatus:
    def test_status_basic_fields(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post("/api/campaigns", headers=headers, json={"name": "Status Test"})
        cid = resp.get_json()["id"]

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data
        assert "total_contacts" in data
        assert "generated_count" in data
        assert "progress_pct" in data
        assert "contact_statuses" in data
        assert "channels" in data
        assert "failed_contacts" in data

    def test_status_shows_channel_breakdown(self, client, seed_companies_contacts):
        """When a campaign has template steps and contacts, channels should show target counts."""
        headers = _headers(client)
        seed = seed_companies_contacts

        cid = _create_ready_campaign(client, headers, seed, template_config=[
            {"step": 1, "channel": "linkedin_connect", "label": "LI", "enabled": True},
            {"step": 2, "channel": "email", "label": "Email 1", "enabled": True},
            {"step": 3, "channel": "email", "label": "Email 2", "enabled": True},
        ])

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        data = resp.get_json()
        channels = data["channels"]

        # 2 contacts * 1 linkedin step = 2, 2 contacts * 2 email steps = 4
        assert channels["linkedin_connect"]["target"] == 2
        assert channels["linkedin_connect"]["generated"] == 0
        assert channels["email"]["target"] == 4
        assert channels["email"]["generated"] == 0

    def test_status_counts_generated_messages(self, client, seed_companies_contacts, db):
        """When messages exist, channel generated counts should reflect them."""
        headers = _headers(client)
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id

        cid = _create_ready_campaign(client, headers, seed)

        # Get campaign contacts
        cc_rows = db.session.execute(
            db.text("SELECT id, contact_id FROM campaign_contacts WHERE campaign_id = :cid"),
            {"cid": cid},
        ).fetchall()

        # Insert a message for the first contact
        msg = Message(
            tenant_id=tenant_id,
            contact_id=str(cc_rows[0][1]),
            channel="email",
            sequence_step=1,
            variant="a",
            body="Test message",
            status="draft",
            campaign_contact_id=str(cc_rows[0][0]),
        )
        db.session.add(msg)
        db.session.commit()

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        data = resp.get_json()

        assert data["channels"]["email"]["generated"] == 1

    def test_status_includes_failed_contacts(self, client, seed_companies_contacts, db):
        """Failed campaign contacts should appear in failed_contacts list."""
        headers = _headers(client)
        seed = seed_companies_contacts

        cid = _create_ready_campaign(client, headers, seed)

        # Mark one campaign_contact as failed
        db.session.execute(
            db.text("""
                UPDATE campaign_contacts
                SET status = 'failed', error = 'API timeout'
                WHERE campaign_id = :cid
                LIMIT 1
            """),
            {"cid": cid},
        )
        db.session.commit()

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        data = resp.get_json()
        failed = data["failed_contacts"]
        assert len(failed) >= 1
        assert failed[0]["error"] == "API timeout"
        assert "name" in failed[0]
        assert "contact_id" in failed[0]

    def test_status_empty_channels_when_no_template(self, client, seed_companies_contacts):
        """Campaigns without template steps should have empty channels."""
        headers = _headers(client)
        resp = client.post("/api/campaigns", headers=headers, json={"name": "Bare"})
        cid = resp.get_json()["id"]

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        data = resp.get_json()
        assert data["channels"] == {}
        assert data["failed_contacts"] == []

    def test_status_campaign_not_found(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.get(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/generation-status",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_status_requires_auth(self, client, db):
        resp = client.get("/api/campaigns/some-id/generation-status")
        assert resp.status_code == 401

    def test_progress_percentage(self, client, seed_companies_contacts, db):
        """Progress percentage should be computed from generated_count / total_contacts."""
        headers = _headers(client)
        seed = seed_companies_contacts
        cid = _create_ready_campaign(client, headers, seed)

        # Manually set generated_count = 1 out of 2 contacts
        db.session.execute(
            db.text("UPDATE campaigns SET generated_count = 1 WHERE id = :id"),
            {"id": cid},
        )
        db.session.commit()

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        data = resp.get_json()
        assert data["progress_pct"] == 50


# ── POST /cost-estimate ─────────────────────────────────


class TestCostEstimate:
    def test_cost_estimate_basic(self, client, seed_companies_contacts):
        headers = _headers(client)
        seed = seed_companies_contacts

        cid = _create_ready_campaign(client, headers, seed)

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["total_contacts"] == 2
        assert data["enabled_steps"] == 2
        assert data["total_messages"] == 4  # 2 contacts x 2 steps
        assert data["total_cost"] > 0
        # Frontend-compatible aliases
        assert data["estimated_cost"] == data["total_cost"]
        assert "by_step" in data
        assert len(data["by_step"]) == 2

    def test_cost_estimate_by_step_has_count_and_cost(self, client, seed_companies_contacts):
        headers = _headers(client)
        seed = seed_companies_contacts

        cid = _create_ready_campaign(client, headers, seed, template_config=[
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": True},
        ])

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        data = resp.get_json()

        step = data["by_step"][0]
        assert step["step"] == 1
        assert step["label"] == "Email 1"
        assert step["channel"] == "email"
        assert step["count"] == 2  # 2 contacts
        assert step["cost"] > 0

    def test_cost_estimate_no_contacts(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post("/api/campaigns", headers=headers, json={"name": "Empty"})
        cid = resp.get_json()["id"]

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        assert resp.status_code == 400

    def test_cost_estimate_no_enabled_steps(self, client, seed_companies_contacts):
        headers = _headers(client)
        seed = seed_companies_contacts

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Disabled"})
        cid = resp.get_json()["id"]

        # Add contacts but all steps disabled
        client.patch(f"/api/campaigns/{cid}", headers=headers, json={
            "template_config": [{"step": 1, "channel": "email", "enabled": False}],
        })
        contact_ids = [str(seed["contacts"][0].id)]
        client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "contact_ids": contact_ids,
        })

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        assert resp.status_code == 400

    def test_cost_estimate_campaign_not_found(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/cost-estimate",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_cost_estimate_requires_auth(self, client, db):
        resp = client.post("/api/campaigns/some-id/cost-estimate")
        assert resp.status_code == 401


# ── DELETE /generate (cancel) ───────────────────────────


class TestCancelGeneration:
    @patch("api.routes.campaign_routes.start_generation")
    def test_cancel_generation_success(self, mock_start, client, seed_companies_contacts):
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        # Start generation first
        client.post(f"/api/campaigns/{cid}/generate", headers=headers)

        # Cancel it
        resp = client.delete(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"] == "cancelled"

    @patch("api.routes.campaign_routes.start_generation")
    def test_cancel_sets_cancelled_flag(self, mock_start, client, seed_companies_contacts, db):
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        # Start generation
        client.post(f"/api/campaigns/{cid}/generate", headers=headers)

        # Cancel
        client.delete(f"/api/campaigns/{cid}/generate", headers=headers)

        # Verify generation_config has cancelled=True
        row = db.session.execute(
            db.text("SELECT generation_config FROM campaigns WHERE id = :id"),
            {"id": cid},
        ).fetchone()
        config = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
        assert config.get("cancelled") is True

    @patch("api.routes.campaign_routes.start_generation")
    def test_cancel_reverts_status_to_ready(self, mock_start, client, seed_companies_contacts):
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        # Start generation, then cancel
        client.post(f"/api/campaigns/{cid}/generate", headers=headers)
        client.delete(f"/api/campaigns/{cid}/generate", headers=headers)

        # Status should be back to ready
        resp = client.get(f"/api/campaigns/{cid}", headers=headers)
        assert resp.get_json()["status"] == "Ready"

    def test_cancel_requires_generating_status(self, client, seed_companies_contacts):
        headers = _headers(client)
        cid = _create_ready_campaign(client, headers, seed_companies_contacts)

        # Try to cancel without starting generation (status = ready)
        resp = client.delete(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 400
        assert "not generating" in resp.get_json()["error"].lower()

    def test_cancel_campaign_not_found(self, client, seed_companies_contacts):
        headers = _headers(client)
        resp = client.delete(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/generate",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_cancel_requires_auth(self, client, db):
        resp = client.delete("/api/campaigns/some-id/generate")
        assert resp.status_code == 401


# ── Message generator cancellation check ────────────────


class TestGeneratorCancellation:
    """Verify the background generator respects the cancelled flag."""

    def test_estimate_generation_cost_includes_by_step(self):
        """estimate_generation_cost should include by_step and estimated_cost."""
        from api.services.message_generator import estimate_generation_cost

        template = [
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": True},
            {"step": 2, "channel": "linkedin_connect", "label": "LI", "enabled": True},
            {"step": 3, "channel": "email", "label": "Email 2", "enabled": False},
        ]
        result = estimate_generation_cost(template, 10)

        # Core fields
        assert result["total_contacts"] == 10
        assert result["enabled_steps"] == 2
        assert result["total_messages"] == 20

        # Frontend-compatible fields
        assert result["estimated_cost"] == result["total_cost"]
        assert "by_step" in result
        assert len(result["by_step"]) == 2

        # Each step entry has count and cost
        step1 = result["by_step"][0]
        assert step1["step"] == 1
        assert step1["count"] == 10
        assert step1["cost"] > 0
