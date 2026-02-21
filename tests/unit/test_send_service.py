"""Unit tests for the Resend email send service (Task 6).

Covers:
- Email dispatch via Resend API (mocked)
- Idempotent send (skips already-sent messages)
- Failure handling (one email fails, others continue)
- Missing sender_config returns 400
- Non-email messages excluded
- Send-status endpoint
"""
import json
from unittest.mock import patch

import pytest

from tests.conftest import auth_header


def _setup_campaign_with_approved_emails(db, seed, msg_count=3, include_linkedin=False):
    """Create a campaign with approved email messages and sender_config.

    Returns (campaign, messages, contacts_used).
    """
    from api.models import Campaign, CampaignContact, Message

    tenant_id = seed["tenant"].id
    owner = seed["owners"][0]

    sender_config = {
        "from_email": "outreach@test.com",
        "from_name": "Test Outreach",
        "reply_to": "replies@test.com",
    }
    campaign = Campaign(
        tenant_id=tenant_id,
        name="Send Test Campaign",
        status="review",
        sender_config=json.dumps(sender_config),
    )
    db.session.add(campaign)
    db.session.flush()

    messages = []
    contacts_used = []
    for i in range(min(msg_count, len(seed["contacts"]))):
        contact = seed["contacts"][i]
        contacts_used.append(contact)
        cc = CampaignContact(
            campaign_id=campaign.id,
            contact_id=contact.id,
            tenant_id=tenant_id,
            status="generated",
        )
        db.session.add(cc)
        db.session.flush()

        m = Message(
            tenant_id=tenant_id,
            contact_id=contact.id,
            owner_id=owner.id,
            channel="email",
            sequence_step=1,
            variant="a",
            subject=f"Subject for {contact.first_name}",
            body=f"Hello {contact.first_name}, this is a test message.",
            status="approved",
            campaign_contact_id=cc.id,
        )
        db.session.add(m)
        messages.append(m)

    if include_linkedin:
        # Add a linkedin message that should be excluded from email send
        contact = seed["contacts"][0]
        cc_existing = db.session.execute(
            db.text("""
                SELECT id FROM campaign_contacts
                WHERE campaign_id = :cid AND contact_id = :ctid
            """),
            {"cid": campaign.id, "ctid": contact.id},
        ).fetchone()
        cc_id = cc_existing[0] if cc_existing else None

        if cc_id:
            li_msg = Message(
                tenant_id=tenant_id,
                contact_id=contact.id,
                owner_id=owner.id,
                channel="linkedin_connect",
                sequence_step=1,
                variant="a",
                body="Let's connect!",
                status="approved",
                campaign_contact_id=cc_id,
            )
            db.session.add(li_msg)

    db.session.flush()
    db.session.commit()
    return campaign, messages, contacts_used


def _setup_tenant_with_resend_key(db, seed):
    """Configure the test tenant with a Resend API key."""
    from api.models import Tenant

    tenant = db.session.get(Tenant, seed["tenant"].id)
    tenant.settings = json.dumps({"resend_api_key": "re_test_key_123"})
    db.session.commit()


class TestSendCampaignEmails:
    """Unit tests for send_campaign_emails service function."""

    @patch("api.services.send_service.time.sleep")
    @patch("api.services.send_service._send_single_email")
    def test_send_dispatches_all_approved(
        self, mock_send, mock_sleep, app, db, seed_companies_contacts
    ):
        """Approved email messages are dispatched via Resend."""
        seed = seed_companies_contacts
        _setup_tenant_with_resend_key(db, seed)
        campaign, messages, contacts = _setup_campaign_with_approved_emails(
            db, seed, msg_count=3
        )

        # Mock Resend response
        mock_send.return_value = {"id": "resend_msg_001"}

        from api.services.send_service import send_campaign_emails

        with app.app_context():
            result = send_campaign_emails(
                str(campaign.id), str(seed["tenant"].id)
            )

        # Only contacts with email addresses should be sent
        contacts_with_email = [c for c in contacts if c.email_address]
        assert result["sent_count"] == len(contacts_with_email)
        assert result["total"] == len(contacts)
        assert mock_send.call_count == len(contacts_with_email)

    @patch("api.services.send_service.time.sleep")
    @patch("api.services.send_service._send_single_email")
    def test_send_idempotent_skips_already_sent(
        self, mock_send, mock_sleep, app, db, seed_companies_contacts
    ):
        """Re-sending skips messages that already have a non-failed EmailSendLog."""
        from api.models import EmailSendLog

        seed = seed_companies_contacts
        _setup_tenant_with_resend_key(db, seed)
        campaign, messages, contacts = _setup_campaign_with_approved_emails(
            db, seed, msg_count=2
        )

        # Pre-create a "sent" log for the first message
        log = EmailSendLog(
            tenant_id=seed["tenant"].id,
            message_id=messages[0].id,
            resend_message_id="re_already_sent",
            status="sent",
            from_email="outreach@test.com",
            to_email=contacts[0].email_address or "test@test.com",
        )
        db.session.add(log)
        db.session.commit()

        mock_send.return_value = {"id": "resend_msg_002"}

        from api.services.send_service import send_campaign_emails

        with app.app_context():
            result = send_campaign_emails(
                str(campaign.id), str(seed["tenant"].id)
            )

        assert result["skipped_count"] >= 1
        # The first message was skipped, so send_count should be less
        assert result["sent_count"] < len(messages)

    @patch("api.services.send_service.time.sleep")
    @patch("api.services.send_service._send_single_email")
    def test_send_handles_failure_gracefully(
        self, mock_send, mock_sleep, app, db, seed_companies_contacts
    ):
        """Failed sends are logged but don't stop other sends."""
        seed = seed_companies_contacts
        _setup_tenant_with_resend_key(db, seed)
        campaign, messages, contacts = _setup_campaign_with_approved_emails(
            db, seed, msg_count=3
        )

        # First call succeeds, second raises, third succeeds
        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Resend API error: rate limit exceeded")
            return {"id": f"resend_msg_{call_count[0]:03d}"}

        mock_send.side_effect = side_effect

        from api.services.send_service import send_campaign_emails

        with app.app_context():
            result = send_campaign_emails(
                str(campaign.id), str(seed["tenant"].id)
            )

        # At least one should have succeeded and at least one failed
        assert result["sent_count"] >= 1
        assert result["failed_count"] >= 1
        # Total should account for all attempts
        assert result["total"] == result["sent_count"] + result["failed_count"] + result["skipped_count"]

    @patch("api.services.send_service.time.sleep")
    @patch("api.services.send_service._send_single_email")
    def test_send_excludes_non_email_messages(
        self, mock_send, mock_sleep, app, db, seed_companies_contacts
    ):
        """LinkedIn messages are not sent via Resend."""
        seed = seed_companies_contacts
        _setup_tenant_with_resend_key(db, seed)
        campaign, messages, contacts = _setup_campaign_with_approved_emails(
            db, seed, msg_count=2, include_linkedin=True
        )

        mock_send.return_value = {"id": "resend_msg_001"}

        from api.services.send_service import send_campaign_emails

        with app.app_context():
            send_campaign_emails(
                str(campaign.id), str(seed["tenant"].id)
            )

        # Only email messages should be sent, not linkedin
        for call_args in mock_send.call_args_list:
            # verify we never tried to send a linkedin message
            assert "connect" not in str(call_args).lower()

    def test_send_raises_on_missing_sender_config(self, app, db, seed_companies_contacts):
        """send_campaign_emails raises when sender_config has no from_email."""
        from api.models import Campaign

        seed = seed_companies_contacts
        _setup_tenant_with_resend_key(db, seed)
        tenant_id = seed["tenant"].id

        # Campaign with empty sender_config
        campaign = Campaign(
            tenant_id=tenant_id,
            name="No Sender Campaign",
            status="review",
            sender_config=json.dumps({}),
        )
        db.session.add(campaign)
        db.session.commit()

        from api.services.send_service import send_campaign_emails

        with app.app_context():
            with pytest.raises(ValueError, match="missing from_email"):
                send_campaign_emails(str(campaign.id), str(tenant_id))

    def test_send_raises_on_missing_api_key(self, app, db, seed_companies_contacts):
        """send_campaign_emails raises when tenant has no resend_api_key."""
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id

        # Create campaign with valid sender config but NO Resend API key on tenant
        campaign_data = _setup_campaign_with_approved_emails(db, seed, msg_count=1)
        campaign = campaign_data[0]

        from api.services.send_service import send_campaign_emails

        with app.app_context():
            with pytest.raises(ValueError, match="resend_api_key"):
                send_campaign_emails(str(campaign.id), str(tenant_id))


class TestSendEmailsEndpoint:
    """Integration tests for POST /api/campaigns/<id>/send-emails."""

    def test_send_emails_missing_sender_config(self, client, seed_companies_contacts, db):
        """Returns 400 when campaign has no sender_config."""
        from api.models import Campaign

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        # Create campaign without sender config
        campaign = Campaign(
            tenant_id=seed["tenant"].id,
            name="No Sender",
            status="review",
        )
        db.session.add(campaign)
        db.session.commit()

        resp = client.post(
            f"/api/campaigns/{campaign.id}/send-emails",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "from_email" in resp.get_json()["error"].lower()

    def test_send_emails_missing_resend_key(self, client, seed_companies_contacts, db):
        """Returns 400 when tenant has no Resend API key."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        campaign, messages, _ = _setup_campaign_with_approved_emails(
            db, seed, msg_count=1
        )
        # Do NOT set up resend key on tenant

        resp = client.post(
            f"/api/campaigns/{campaign.id}/send-emails",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "resend_api_key" in resp.get_json()["error"].lower()

    def test_send_emails_no_approved_messages(self, client, seed_companies_contacts, db):
        """Returns 400 when campaign has no approved email messages."""
        from api.models import Campaign

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        _setup_tenant_with_resend_key(db, seed)

        campaign = Campaign(
            tenant_id=seed["tenant"].id,
            name="Empty Campaign",
            status="review",
            sender_config=json.dumps({"from_email": "sender@test.com"}),
        )
        db.session.add(campaign)
        db.session.commit()

        resp = client.post(
            f"/api/campaigns/{campaign.id}/send-emails",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "no approved" in resp.get_json()["error"].lower()

    @patch("api.routes.campaign_routes.send_campaign_emails")
    def test_send_emails_starts_background_send(
        self, mock_send, client, seed_companies_contacts, db
    ):
        """Endpoint starts background send and returns queued count."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        _setup_tenant_with_resend_key(db, seed)
        campaign, messages, _ = _setup_campaign_with_approved_emails(
            db, seed, msg_count=2
        )

        resp = client.post(
            f"/api/campaigns/{campaign.id}/send-emails",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["queued_count"] >= 1
        assert data["sender"]["from_email"] == "outreach@test.com"
        assert data["sender"]["from_name"] == "Test Outreach"

    def test_send_emails_campaign_not_found(self, client, seed_companies_contacts, db):
        """Returns 404 for non-existent campaign."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/send-emails",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_send_emails_requires_auth(self, client, db):
        """Returns 401 without authentication."""
        resp = client.post("/api/campaigns/some-id/send-emails")
        assert resp.status_code == 401


class TestSendStatusEndpoint:
    """Integration tests for GET /api/campaigns/<id>/send-status."""

    def test_send_status_empty(self, client, seed_companies_contacts, db):
        """Returns zero counts for campaign with no sends."""
        from api.models import Campaign

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        campaign = Campaign(
            tenant_id=seed["tenant"].id,
            name="Status Test Campaign",
            status="review",
        )
        db.session.add(campaign)
        db.session.commit()

        resp = client.get(
            f"/api/campaigns/{campaign.id}/send-status",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert data["sent"] == 0
        assert data["delivered"] == 0
        assert data["failed"] == 0
        assert data["bounced"] == 0
        assert data["queued"] == 0

    def test_send_status_with_logs(self, client, seed_companies_contacts, db):
        """Returns correct counts from EmailSendLog entries."""
        from api.models import EmailSendLog

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        campaign, messages, _ = _setup_campaign_with_approved_emails(
            db, seed, msg_count=3
        )

        # Create logs with different statuses
        statuses = ["sent", "delivered", "failed"]
        for i, msg in enumerate(messages):
            if i < len(statuses):
                log = EmailSendLog(
                    tenant_id=seed["tenant"].id,
                    message_id=msg.id,
                    status=statuses[i],
                    from_email="outreach@test.com",
                    to_email=f"contact{i}@test.com",
                )
                db.session.add(log)
        db.session.commit()

        resp = client.get(
            f"/api/campaigns/{campaign.id}/send-status",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 3
        assert data["sent"] == 1
        assert data["delivered"] == 1
        assert data["failed"] == 1

    def test_send_status_campaign_not_found(self, client, seed_companies_contacts, db):
        """Returns 404 for non-existent campaign."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/send-status",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_send_status_requires_auth(self, client, db):
        """Returns 401 without authentication."""
        resp = client.get("/api/campaigns/some-id/send-status")
        assert resp.status_code == 401


class TestRenderBodyHtml:
    """Unit tests for _render_body_html helper."""

    def test_plain_text_to_html(self, app):
        from api.services.send_service import _render_body_html

        result = _render_body_html("Hello World")
        assert "<p>Hello World</p>" in result

    def test_multiline_to_paragraphs(self, app):
        from api.services.send_service import _render_body_html

        result = _render_body_html("First paragraph\n\nSecond paragraph")
        assert "<p>First paragraph</p>" in result
        assert "<p>Second paragraph</p>" in result

    def test_single_newlines_to_br(self, app):
        from api.services.send_service import _render_body_html

        result = _render_body_html("Line one\nLine two")
        assert "<br>" in result

    def test_html_passthrough(self, app):
        from api.services.send_service import _render_body_html

        html = "<p>Already <strong>formatted</strong></p>"
        assert _render_body_html(html) == html

    def test_empty_body(self, app):
        from api.services.send_service import _render_body_html

        result = _render_body_html("")
        assert result == "<p></p>"

    def test_none_body(self, app):
        from api.services.send_service import _render_body_html

        result = _render_body_html(None)
        assert result == "<p></p>"
