"""Integration tests for the outreach campaign backend (Task 16).

Tests the full outreach workflow through the API endpoints:
- Contact selection with ICP filters (POST /campaigns/<id>/contacts)
- Batch approve/reject (POST /campaigns/<id>/messages/batch-action)
- Send emails (POST /campaigns/<id>/send-emails) -- mocked Resend
- Queue LinkedIn (POST /campaigns/<id>/queue-linkedin)
- Campaign analytics (GET /campaigns/<id>/analytics)
- Generation progress (GET /campaigns/<id>/generation-status)
- Cost estimate (POST /campaigns/<id>/cost-estimate)
- Cancel generation (DELETE /campaigns/<id>/generate)
- Sender config via campaign update (PATCH /campaigns/<id>)

Uses SQLite in-memory via conftest.py. External services (Resend) mocked.
"""
import json
from unittest.mock import patch

from api.models import (
    Campaign,
    CampaignContact,
    EmailSendLog,
    EntityStageCompletion,
    LinkedInSendQueue,
    Message,
    Tenant,
)
from tests.conftest import auth_header


# ── Helpers ──────────────────────────────────────────────────────


def _headers(client):
    """Auth headers with namespace for a super admin."""
    h = auth_header(client)
    h["X-Namespace"] = "test-corp"
    return h


def _create_draft_campaign(client, headers, name="Outreach Campaign", **extra):
    """Create a campaign in draft status. Returns campaign_id."""
    body = {"name": name, **extra}
    resp = client.post("/api/campaigns", headers=headers, json=body)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["id"]


def _transition_campaign(client, headers, campaign_id, status):
    """Update campaign status."""
    resp = client.patch(
        f"/api/campaigns/{campaign_id}",
        headers=headers,
        json={"status": status},
    )
    return resp


def _add_template_config(client, headers, campaign_id, template_config=None):
    """Set template_config on a campaign."""
    if template_config is None:
        template_config = [
            {"step": 1, "channel": "email", "label": "Intro Email", "enabled": True},
            {
                "step": 2,
                "channel": "linkedin_connect",
                "label": "LI Connect",
                "enabled": True,
            },
            {
                "step": 3,
                "channel": "email",
                "label": "Follow-up Email",
                "enabled": True,
            },
        ]
    resp = client.patch(
        f"/api/campaigns/{campaign_id}",
        headers=headers,
        json={"template_config": template_config},
    )
    assert resp.status_code == 200
    return template_config


def _add_contacts_to_campaign(client, headers, campaign_id, contact_ids):
    """Add contacts by explicit IDs."""
    resp = client.post(
        f"/api/campaigns/{campaign_id}/contacts",
        headers=headers,
        json={"contact_ids": contact_ids},
    )
    return resp


def _create_messages_for_campaign(db, campaign_id, tenant_id, contacts, owner_id, tag_id):
    """Create messages linked to existing campaign_contacts.

    Looks up existing campaign_contact rows (created by add_campaign_contacts API)
    and creates draft messages for each. Returns (messages, campaign_contacts) lists.
    """
    messages = []
    campaign_contacts = []

    for contact in contacts:
        # Look up existing campaign_contact (created by the API endpoint)
        cc_row = db.session.execute(
            db.text("""
                SELECT id FROM campaign_contacts
                WHERE campaign_id = :cid AND contact_id = :ctid AND tenant_id = :t
            """),
            {"cid": campaign_id, "ctid": str(contact.id), "t": str(tenant_id)},
        ).fetchone()

        if cc_row:
            cc_id = cc_row[0]
            # Update status to generated
            db.session.execute(
                db.text("UPDATE campaign_contacts SET status = 'generated' WHERE id = :id"),
                {"id": cc_id},
            )
        else:
            # No existing record -- create one
            cc = CampaignContact(
                campaign_id=campaign_id,
                contact_id=contact.id,
                tenant_id=tenant_id,
                status="generated",
            )
            db.session.add(cc)
            db.session.flush()
            cc_id = cc.id

        # Create a lightweight object to hold the id for return value
        class CCRef:
            pass
        cc_ref = CCRef()
        cc_ref.id = cc_id
        cc_ref.contact_id = contact.id
        cc_ref.status = "generated"
        campaign_contacts.append(cc_ref)

        # Email message
        m_email = Message(
            tenant_id=tenant_id,
            contact_id=contact.id,
            owner_id=owner_id,
            channel="email",
            sequence_step=1,
            variant="a",
            subject=f"Hi {contact.first_name}",
            body=f"Hello {contact.first_name}, reaching out about AI.",
            status="draft",
            campaign_contact_id=cc_id,
            tag_id=tag_id,
        )
        db.session.add(m_email)
        messages.append(m_email)

        # LinkedIn message
        m_li = Message(
            tenant_id=tenant_id,
            contact_id=contact.id,
            owner_id=owner_id,
            channel="linkedin_connect",
            sequence_step=1,
            variant="a",
            body=f"Let's connect, {contact.first_name}!",
            status="draft",
            campaign_contact_id=cc_id,
            tag_id=tag_id,
        )
        db.session.add(m_li)
        messages.append(m_li)

    db.session.flush()
    db.session.commit()
    return messages, campaign_contacts


def _setup_ready_campaign(client, db, headers, seed, with_messages=True):
    """Set up a complete campaign in 'review' status with contacts and messages.

    Returns dict with campaign_id, messages, campaign_contacts, contacts_used.
    """
    cid = _create_draft_campaign(client, headers)
    _add_template_config(client, headers, cid)

    tenant_id = seed["tenant"].id
    owner_id = seed["owners"][0].id
    tag_id = seed["tags"][0].id
    # Use first 3 contacts (have both email and linkedin)
    contacts_used = seed["contacts"][:3]
    contact_ids = [str(c.id) for c in contacts_used]

    _add_contacts_to_campaign(client, headers, cid, contact_ids)

    messages = []
    campaign_contacts = []
    if with_messages:
        messages, campaign_contacts = _create_messages_for_campaign(
            db, cid, tenant_id, contacts_used, owner_id, tag_id
        )

    # Transition to ready
    _transition_campaign(client, headers, cid, "ready")

    return {
        "campaign_id": cid,
        "messages": messages,
        "campaign_contacts": campaign_contacts,
        "contacts_used": contacts_used,
    }


# ── Test: Contact Selection with ICP Filters ─────────────────────


class TestContactSelectionICPFilters:
    """POST /api/campaigns/<id>/contacts with owner_id and icp_filters."""

    def test_filter_by_owner_resolves_correct_contacts(
        self, client, seed_companies_contacts
    ):
        """Adding contacts by owner_id should return only that owner's contacts."""
        headers = _headers(client)
        seed = seed_companies_contacts
        cid = _create_draft_campaign(client, headers)

        owner1_id = str(seed["owners"][0].id)  # Alice
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"owner_id": owner1_id},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] > 0
        # All added contacts should belong to Alice (owner[0])
        # Contacts 0,1,2,3,5,6 belong to Alice (owner1)
        alice_contact_ids = {
            str(c.id) for c in seed["contacts"] if str(c.owner_id) == owner1_id
        }
        # Verify none of Bob's contacts slipped through
        resp2 = client.get(f"/api/campaigns/{cid}/contacts", headers=headers)
        campaign_contacts = resp2.get_json()["contacts"]
        for cc in campaign_contacts:
            assert cc["contact_id"] in alice_contact_ids

    def test_filter_by_tier_and_industry(self, client, seed_companies_contacts):
        """ICP filters for tier + industry should intersect correctly."""
        headers = _headers(client)
        cid = _create_draft_campaign(client, headers)

        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={
                "icp_filters": {
                    "tiers": ["tier_1_platinum"],
                    "industries": ["it"],
                }
            },
        )
        assert resp.status_code == 200
        result = resp.get_json()
        # Beta Inc (tier_1_platinum, it) has contacts Bob and Carol
        assert result["added"] == 2

    def test_enrichment_ready_filter_excludes_unenriched(
        self, client, seed_companies_contacts
    ):
        """enrichment_ready=true should exclude contacts without completed stages."""
        headers = _headers(client)
        cid = _create_draft_campaign(client, headers)

        # No enrichment completions in seed data for most contacts
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"enrichment_ready": True}},
        )
        # Should get 400 because no contacts match the enrichment_ready filter
        assert resp.status_code == 400

    def test_enrichment_ready_includes_fully_enriched(
        self, client, seed_companies_contacts, db
    ):
        """Contacts with all enrichment stages completed should be included."""
        headers = _headers(client)
        seed = seed_companies_contacts
        cid = _create_draft_campaign(client, headers)

        # Complete all enrichment stages for contact[0] (John) and company[0] (Acme)
        contact = seed["contacts"][0]
        company = seed["companies"][0]
        tenant_id = seed["tenant"].id
        tag_id = seed["tags"][0].id

        for stage in ["l1_company", "l2_deep_research"]:
            db.session.add(
                EntityStageCompletion(
                    tenant_id=tenant_id,
                    tag_id=tag_id,
                    entity_type="company",
                    entity_id=str(company.id),
                    stage=stage,
                    status="completed",
                )
            )
        db.session.add(
            EntityStageCompletion(
                tenant_id=tenant_id,
                tag_id=tag_id,
                entity_type="contact",
                entity_id=str(contact.id),
                stage="person",
                status="completed",
            )
        )
        db.session.commit()

        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"icp_filters": {"enrichment_ready": True}},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] >= 1  # At least John should be included

    def test_duplicate_prevention_with_filters(self, client, seed_companies_contacts):
        """Adding the same contacts twice by different means should skip duplicates."""
        headers = _headers(client)
        seed = seed_companies_contacts
        cid = _create_draft_campaign(client, headers)

        # Add by explicit IDs
        contact_ids = [str(seed["contacts"][0].id), str(seed["contacts"][1].id)]
        resp1 = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"contact_ids": contact_ids},
        )
        assert resp1.status_code == 200
        assert resp1.get_json()["added"] == 2

        # Add again with owner filter (should overlap with the two already added)
        owner1_id = str(seed["owners"][0].id)
        resp2 = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"owner_id": owner1_id},
        )
        assert resp2.status_code == 200
        result2 = resp2.get_json()
        assert result2["skipped"] >= 2  # At least the original 2 duplicated


# ── Test: Batch Approve / Reject ─────────────────────────────────


class TestBatchApproveReject:
    """POST /api/campaigns/<id>/messages/batch-action."""

    def test_batch_approve_sets_status_and_timestamp(
        self, client, seed_companies_contacts, db
    ):
        """Batch approve should set status='approved' and approved_at for all messages."""
        headers = _headers(client)
        seed = seed_companies_contacts
        setup = _setup_ready_campaign(client, db, headers, seed)

        message_ids = [str(m.id) for m in setup["messages"]][:3]

        resp = client.post(
            f"/api/campaigns/{setup['campaign_id']}/messages/batch-action",
            headers=headers,
            json={"message_ids": message_ids, "action": "approve"},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["updated"] == 3
        assert result["action"] == "approve"

        # Verify in DB
        for mid in message_ids:
            row = db.session.execute(
                db.text("SELECT status, approved_at FROM messages WHERE id = :id"),
                {"id": mid},
            ).fetchone()
            assert row[0] == "approved"
            assert row[1] is not None  # approved_at should be set

    def test_batch_reject_with_reason(self, client, seed_companies_contacts, db):
        """Batch reject should set status='rejected' and review_notes."""
        headers = _headers(client)
        seed = seed_companies_contacts
        setup = _setup_ready_campaign(client, db, headers, seed)

        message_ids = [str(m.id) for m in setup["messages"]][:2]
        reason = "Too generic, needs personalization"

        resp = client.post(
            f"/api/campaigns/{setup['campaign_id']}/messages/batch-action",
            headers=headers,
            json={"message_ids": message_ids, "action": "reject", "reason": reason},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["updated"] == 2
        assert result["action"] == "reject"

        # Verify review_notes in DB
        for mid in message_ids:
            row = db.session.execute(
                db.text("SELECT status, review_notes FROM messages WHERE id = :id"),
                {"id": mid},
            ).fetchone()
            assert row[0] == "rejected"
            assert row[1] == reason

    def test_batch_action_wrong_campaign_returns_errors(
        self, client, seed_companies_contacts, db
    ):
        """Messages from a different campaign should not be updated."""
        headers = _headers(client)
        seed = seed_companies_contacts

        # Create two campaigns with messages
        setup1 = _setup_ready_campaign(client, db, headers, seed)
        cid2 = _create_draft_campaign(client, headers, name="Other Campaign")

        # Try to approve setup1's messages via campaign2
        message_ids = [str(m.id) for m in setup1["messages"]][:2]
        resp = client.post(
            f"/api/campaigns/{cid2}/messages/batch-action",
            headers=headers,
            json={"message_ids": message_ids, "action": "approve"},
        )
        assert resp.status_code == 400
        result = resp.get_json()
        assert result["updated"] == 0
        assert len(result["errors"]) == 2

    def test_batch_action_empty_list_returns_400(
        self, client, seed_companies_contacts, db
    ):
        """Empty message_ids should return 400."""
        headers = _headers(client)
        seed = seed_companies_contacts
        setup = _setup_ready_campaign(client, db, headers, seed)

        resp = client.post(
            f"/api/campaigns/{setup['campaign_id']}/messages/batch-action",
            headers=headers,
            json={"message_ids": [], "action": "approve"},
        )
        assert resp.status_code == 400

    def test_batch_action_invalid_action_returns_400(
        self, client, seed_companies_contacts, db
    ):
        """Invalid action should return 400."""
        headers = _headers(client)
        seed = seed_companies_contacts
        setup = _setup_ready_campaign(client, db, headers, seed)

        message_ids = [str(m.id) for m in setup["messages"]][:1]
        resp = client.post(
            f"/api/campaigns/{setup['campaign_id']}/messages/batch-action",
            headers=headers,
            json={"message_ids": message_ids, "action": "delete"},
        )
        assert resp.status_code == 400


# ── Test: Send Emails (mocked Resend) ────────────────────────────


class TestSendEmails:
    """POST /api/campaigns/<id>/send-emails — mocked Resend."""

    def _setup_campaign_for_send(self, client, db, headers, seed):
        """Create a campaign with approved email messages and sender_config."""
        tenant_id = seed["tenant"].id
        owner = seed["owners"][0]

        # Set Resend API key on tenant
        tenant = db.session.get(Tenant, tenant_id)
        tenant.settings = json.dumps({"resend_api_key": "re_test_fake_key"})
        db.session.commit()

        campaign = Campaign(
            tenant_id=tenant_id,
            name="Email Send Campaign",
            status="review",
            sender_config=json.dumps({
                "from_email": "outreach@test.com",
                "from_name": "Test Outreach",
                "reply_to": "replies@test.com",
            }),
        )
        db.session.add(campaign)
        db.session.flush()

        # Create contacts + campaign_contacts + approved email messages
        messages = []
        contacts_used = [c for c in seed["contacts"][:3] if c.email_address]
        for contact in contacts_used:
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
                subject=f"Hi {contact.first_name}",
                body=f"Hello {contact.first_name}, test email.",
                status="approved",
                campaign_contact_id=cc.id,
            )
            db.session.add(m)
            messages.append(m)

        db.session.commit()
        return campaign, messages, contacts_used

    def test_send_emails_starts_background_thread(
        self, client, seed_companies_contacts, db
    ):
        """POST send-emails should start a background thread and return queued count."""
        headers = _headers(client)
        seed = seed_companies_contacts
        campaign, messages, _ = self._setup_campaign_for_send(
            client, db, headers, seed
        )

        with patch("api.routes.campaign_routes.send_campaign_emails"):
            resp = client.post(
                f"/api/campaigns/{campaign.id}/send-emails",
                headers=headers,
                json={"confirm": True},
            )

        assert resp.status_code == 200
        result = resp.get_json()
        assert result["queued_count"] >= 1
        assert result["sender"]["from_email"] == "outreach@test.com"
        assert result["sender"]["from_name"] == "Test Outreach"

    def test_send_emails_missing_sender_config_returns_400(
        self, client, seed_companies_contacts, db
    ):
        """Campaign without sender_config should return 400."""
        headers = _headers(client)
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id

        campaign = Campaign(
            tenant_id=tenant_id,
            name="No Sender Campaign",
            status="review",
            sender_config=json.dumps({}),  # empty
        )
        db.session.add(campaign)
        db.session.commit()

        resp = client.post(
            f"/api/campaigns/{campaign.id}/send-emails",
            headers=headers,
            json={"confirm": True},
        )
        assert resp.status_code == 400
        assert "sender_config" in resp.get_json()["error"].lower()

    def test_send_emails_missing_resend_key_returns_400(
        self, client, seed_companies_contacts, db
    ):
        """Tenant without resend_api_key should return 400."""
        headers = _headers(client)
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id

        # Ensure tenant settings has no resend key
        tenant = db.session.get(Tenant, tenant_id)
        tenant.settings = json.dumps({})
        db.session.commit()

        campaign = Campaign(
            tenant_id=tenant_id,
            name="No Key Campaign",
            status="review",
            sender_config=json.dumps({"from_email": "test@example.com"}),
        )
        db.session.add(campaign)
        db.session.flush()

        # Need at least one approved email message
        contact = seed["contacts"][0]
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
            owner_id=seed["owners"][0].id,
            channel="email",
            sequence_step=1,
            body="Test",
            status="approved",
            campaign_contact_id=cc.id,
        )
        db.session.add(m)
        db.session.commit()

        resp = client.post(
            f"/api/campaigns/{campaign.id}/send-emails",
            headers=headers,
            json={"confirm": True},
        )
        assert resp.status_code == 400
        assert "resend_api_key" in resp.get_json()["error"].lower()

    def test_send_emails_no_approved_messages_returns_400(
        self, client, seed_companies_contacts, db
    ):
        """Campaign with no approved email messages should return 400."""
        headers = _headers(client)
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id

        tenant = db.session.get(Tenant, tenant_id)
        tenant.settings = json.dumps({"resend_api_key": "re_test_key"})
        db.session.commit()

        campaign = Campaign(
            tenant_id=tenant_id,
            name="No Approved Campaign",
            status="review",
            sender_config=json.dumps({"from_email": "test@example.com"}),
        )
        db.session.add(campaign)
        db.session.commit()

        resp = client.post(
            f"/api/campaigns/{campaign.id}/send-emails",
            headers=headers,
            json={"confirm": True},
        )
        assert resp.status_code == 400
        assert "no approved" in resp.get_json()["error"].lower()


# ── Test: Queue LinkedIn ─────────────────────────────────────────


class TestQueueLinkedIn:
    """POST /api/campaigns/<id>/queue-linkedin."""

    def _setup_campaign_with_linkedin(self, db, seed):
        """Create a campaign with approved LinkedIn messages."""
        tenant_id = seed["tenant"].id
        owner1 = seed["owners"][0]  # Alice
        owner2 = seed["owners"][1]  # Bob

        campaign = Campaign(
            tenant_id=tenant_id,
            name="LinkedIn Campaign",
            status="approved",
        )
        db.session.add(campaign)
        db.session.flush()

        # Contact 0 = John (owner=Alice, has linkedin_url)
        # Contact 4 = Dave (owner=Bob, no linkedin_url)
        contacts = seed["contacts"]
        cc1 = CampaignContact(
            campaign_id=campaign.id,
            contact_id=contacts[0].id,
            tenant_id=tenant_id,
            status="generated",
        )
        cc2 = CampaignContact(
            campaign_id=campaign.id,
            contact_id=contacts[4].id,
            tenant_id=tenant_id,
            status="generated",
        )
        db.session.add_all([cc1, cc2])
        db.session.flush()

        m1 = Message(
            tenant_id=tenant_id,
            contact_id=contacts[0].id,
            owner_id=owner1.id,
            channel="linkedin_connect",
            body="Let's connect!",
            status="approved",
            campaign_contact_id=cc1.id,
        )
        m2 = Message(
            tenant_id=tenant_id,
            contact_id=contacts[4].id,
            owner_id=owner2.id,
            channel="linkedin_message",
            body="Following up",
            status="approved",
            campaign_contact_id=cc2.id,
        )
        # Draft message (should NOT be queued)
        m3 = Message(
            tenant_id=tenant_id,
            contact_id=contacts[0].id,
            owner_id=owner1.id,
            channel="linkedin_connect",
            sequence_step=2,
            body="Second try",
            status="draft",
            campaign_contact_id=cc1.id,
        )
        db.session.add_all([m1, m2, m3])
        db.session.commit()

        return campaign, [m1, m2], [cc1, cc2]

    def test_queue_creates_entries(self, client, seed_companies_contacts, db):
        """Queuing should create LinkedInSendQueue entries for approved messages."""
        headers = _headers(client)
        seed = seed_companies_contacts
        campaign, messages, _ = self._setup_campaign_with_linkedin(db, seed)

        resp = client.post(
            f"/api/campaigns/{campaign.id}/queue-linkedin",
            headers=headers,
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["queued_count"] == 2
        assert "by_owner" in result
        assert "Alice" in result["by_owner"]
        assert "Bob" in result["by_owner"]

    def test_queue_idempotent(self, client, seed_companies_contacts, db):
        """Re-queuing the same messages should skip existing entries."""
        headers = _headers(client)
        seed = seed_companies_contacts
        campaign, _, _ = self._setup_campaign_with_linkedin(db, seed)

        # First queue
        resp1 = client.post(
            f"/api/campaigns/{campaign.id}/queue-linkedin", headers=headers
        )
        assert resp1.get_json()["queued_count"] == 2

        # Second queue -- should skip all
        resp2 = client.post(
            f"/api/campaigns/{campaign.id}/queue-linkedin", headers=headers
        )
        assert resp2.get_json()["queued_count"] == 0

    def test_queue_only_approved_linkedin(self, client, seed_companies_contacts, db):
        """Only approved LinkedIn messages should be queued, not draft or email."""
        headers = _headers(client)
        seed = seed_companies_contacts
        campaign, messages, _ = self._setup_campaign_with_linkedin(db, seed)

        resp = client.post(
            f"/api/campaigns/{campaign.id}/queue-linkedin", headers=headers
        )
        result = resp.get_json()
        # Only 2 approved LinkedIn messages, not the draft one
        assert result["queued_count"] == 2

        # Verify queue entries in DB
        entries = LinkedInSendQueue.query.filter_by(
            tenant_id=seed["tenant"].id
        ).all()
        assert len(entries) == 2
        for entry in entries:
            assert entry.status == "queued"
            assert entry.action_type in ("connection_request", "message")

    def test_queue_campaign_not_found(self, client, seed_companies_contacts):
        """Queue for a nonexistent campaign should return 404."""
        headers = _headers(client)
        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000000/queue-linkedin",
            headers=headers,
        )
        assert resp.status_code == 404


# ── Test: Campaign Analytics ─────────────────────────────────────


class TestCampaignAnalytics:
    """GET /api/campaigns/<id>/analytics."""

    def test_analytics_empty_campaign(self, client, seed_companies_contacts, db):
        """Empty campaign should return zero counts, not errors."""
        headers = _headers(client)
        seed = seed_companies_contacts

        campaign = Campaign(
            tenant_id=seed["tenant"].id,
            name="Empty Analytics Campaign",
            status="draft",
        )
        db.session.add(campaign)
        db.session.commit()

        resp = client.get(
            f"/api/campaigns/{campaign.id}/analytics", headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["messages"]["total"] == 0
        assert data["sending"]["email"]["total"] == 0
        assert data["sending"]["linkedin"]["total"] == 0
        assert data["contacts"]["total"] == 0
        assert data["cost"]["generation_usd"] == 0

    def test_analytics_aggregates_messages(self, client, seed_companies_contacts, db):
        """Analytics should correctly aggregate message counts by status and channel."""
        headers = _headers(client)
        seed = seed_companies_contacts

        setup = _setup_ready_campaign(client, db, headers, seed)
        cid = setup["campaign_id"]
        messages = setup["messages"]

        # Approve some, reject some
        email_msgs = [m for m in messages if m.channel == "email"]
        li_msgs = [m for m in messages if m.channel == "linkedin_connect"]

        if email_msgs:
            email_msgs[0].status = "approved"
        if li_msgs:
            li_msgs[0].status = "approved"
        if len(email_msgs) > 1:
            email_msgs[1].status = "rejected"
        db.session.commit()

        resp = client.get(f"/api/campaigns/{cid}/analytics", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        # Total messages should match what we created
        assert data["messages"]["total"] == len(messages)
        assert "by_status" in data["messages"]
        assert "by_channel" in data["messages"]
        assert "email" in data["messages"]["by_channel"]
        assert "linkedin_connect" in data["messages"]["by_channel"]

    def test_analytics_email_send_stats(self, client, seed_companies_contacts, db):
        """Analytics should include email send log stats."""
        headers = _headers(client)
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id

        campaign = Campaign(
            tenant_id=tenant_id,
            name="Email Stats Campaign",
            status="review",
        )
        db.session.add(campaign)
        db.session.flush()

        contact = seed["contacts"][0]
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
            owner_id=seed["owners"][0].id,
            channel="email",
            sequence_step=1,
            body="Test",
            status="approved",
            campaign_contact_id=cc.id,
        )
        db.session.add(m)
        db.session.flush()

        # Create email send log entries
        sent_log = EmailSendLog(
            tenant_id=tenant_id,
            message_id=m.id,
            status="sent",
            from_email="test@example.com",
            to_email=contact.email_address or "fallback@example.com",
        )
        db.session.add(sent_log)
        db.session.commit()

        resp = client.get(f"/api/campaigns/{campaign.id}/analytics", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["sending"]["email"]["total"] >= 1
        assert data["sending"]["email"]["sent"] >= 1

    def test_analytics_tenant_isolation(self, client, seed_companies_contacts, db):
        """Analytics for a nonexistent campaign should return 404."""
        headers = _headers(client)
        resp = client.get(
            "/api/campaigns/00000000-0000-0000-0000-000000000000/analytics",
            headers=headers,
        )
        assert resp.status_code == 404


# ── Test: Generation Progress ────────────────────────────────────


class TestGenerationProgress:
    """GET /api/campaigns/<id>/generation-status."""

    def test_generation_status_basic_fields(self, client, seed_companies_contacts):
        """Status endpoint should return all expected fields."""
        headers = _headers(client)

        cid = _create_draft_campaign(client, headers)
        template_config = [
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": True},
        ]
        _add_template_config(client, headers, cid, template_config)

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        assert "status" in data
        assert "total_contacts" in data
        assert "generated_count" in data
        assert "generation_cost" in data
        assert "progress_pct" in data
        assert "contact_statuses" in data
        assert "channels" in data
        assert "failed_contacts" in data

    def test_generation_status_channel_breakdown(
        self, client, seed_companies_contacts, db
    ):
        """Status should show per-channel generation progress."""
        headers = _headers(client)
        seed = seed_companies_contacts

        setup = _setup_ready_campaign(client, db, headers, seed)
        cid = setup["campaign_id"]

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        # Template has email and linkedin_connect channels
        channels = data["channels"]
        assert "email" in channels
        assert "linkedin_connect" in channels
        assert "target" in channels["email"]
        assert "generated" in channels["email"]

    def test_generation_status_failed_contacts(
        self, client, seed_companies_contacts, db
    ):
        """Failed contacts should be included with error details."""
        headers = _headers(client)
        seed = seed_companies_contacts

        setup = _setup_ready_campaign(client, db, headers, seed)
        cid = setup["campaign_id"]

        # Mark one campaign_contact as failed (use raw SQL since cc is a reference)
        cc = setup["campaign_contacts"][0]
        db.session.execute(
            db.text(
                "UPDATE campaign_contacts SET status = 'failed', error = :err WHERE id = :id"
            ),
            {"id": str(cc.id), "err": "Enrichment data missing"},
        )
        db.session.commit()

        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["failed_contacts"]) == 1
        assert "Enrichment data missing" in data["failed_contacts"][0]["error"]


# ── Test: Cost Estimate ──────────────────────────────────────────


class TestCostEstimate:
    """POST /api/campaigns/<id>/cost-estimate."""

    def test_cost_estimate_returns_breakdown(self, client, seed_companies_contacts):
        """Cost estimate should return per-step and total cost breakdown."""
        headers = _headers(client)
        seed = seed_companies_contacts

        cid = _create_draft_campaign(client, headers)
        template_config = [
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": True},
            {
                "step": 2,
                "channel": "linkedin_connect",
                "label": "LI Connect",
                "enabled": True,
            },
        ]
        _add_template_config(client, headers, cid, template_config)

        contact_ids = [str(c.id) for c in seed["contacts"][:2]]
        _add_contacts_to_campaign(client, headers, cid, contact_ids)

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_cost" in data
        assert "total_messages" in data
        assert data["total_messages"] == 4  # 2 contacts * 2 steps
        assert data["total_cost"] > 0

    def test_cost_estimate_no_contacts_returns_400(
        self, client, seed_companies_contacts
    ):
        """Cost estimate with no contacts should return 400."""
        headers = _headers(client)
        cid = _create_draft_campaign(client, headers)
        template_config = [
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": True},
        ]
        _add_template_config(client, headers, cid, template_config)

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        assert resp.status_code == 400
        assert "no contacts" in resp.get_json()["error"].lower()

    def test_cost_estimate_no_enabled_steps_returns_400(
        self, client, seed_companies_contacts
    ):
        """Cost estimate with no enabled template steps should return 400."""
        headers = _headers(client)
        seed = seed_companies_contacts

        cid = _create_draft_campaign(client, headers)
        # All steps disabled
        template_config = [
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": False},
        ]
        _add_template_config(client, headers, cid, template_config)
        contact_ids = [str(c.id) for c in seed["contacts"][:2]]
        _add_contacts_to_campaign(client, headers, cid, contact_ids)

        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        assert resp.status_code == 400
        assert "no enabled" in resp.get_json()["error"].lower()


# ── Test: Cancel Generation ──────────────────────────────────────


class TestCancelGeneration:
    """DELETE /api/campaigns/<id>/generate."""

    @patch("api.routes.campaign_routes.start_generation")
    def test_cancel_sets_cancelled_flag(
        self, mock_start, client, seed_companies_contacts, db
    ):
        """Cancelling generation should set cancelled flag and revert to ready."""
        headers = _headers(client)
        seed = seed_companies_contacts

        # Create a campaign and transition to generating
        cid = _create_draft_campaign(client, headers)
        template_config = [
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": True},
        ]
        _add_template_config(client, headers, cid, template_config)
        contact_ids = [str(c.id) for c in seed["contacts"][:2]]
        _add_contacts_to_campaign(client, headers, cid, contact_ids)
        _transition_campaign(client, headers, cid, "ready")

        # Start generation
        client.post(f"/api/campaigns/{cid}/generate", headers=headers)

        # Cancel
        resp = client.delete(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "cancelled"

        # Verify campaign is back to ready with cancelled flag
        row = db.session.execute(
            db.text("SELECT status, generation_config FROM campaigns WHERE id = :id"),
            {"id": cid},
        ).fetchone()
        assert row[0] == "ready"
        gen_config = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
        assert gen_config.get("cancelled") is True

    def test_cancel_requires_generating_status(
        self, client, seed_companies_contacts
    ):
        """Cancelling a non-generating campaign should return 400."""
        headers = _headers(client)
        cid = _create_draft_campaign(client, headers)

        resp = client.delete(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 400
        assert "not generating" in resp.get_json()["error"].lower()


# ── Test: Sender Config ──────────────────────────────────────────


class TestSenderConfig:
    """PATCH /api/campaigns/<id> with sender_config."""

    def test_update_sender_config(self, client, seed_companies_contacts):
        """Updating sender_config should persist the configuration."""
        headers = _headers(client)
        cid = _create_draft_campaign(client, headers)

        sender_config = {
            "from_email": "outreach@company.com",
            "from_name": "Sales Team",
            "reply_to": "replies@company.com",
        }
        resp = client.patch(
            f"/api/campaigns/{cid}",
            headers=headers,
            json={"sender_config": sender_config},
        )
        assert resp.status_code == 200

        # Verify via GET
        resp2 = client.get(f"/api/campaigns/{cid}", headers=headers)
        data = resp2.get_json()
        assert data["sender_config"]["from_email"] == "outreach@company.com"
        assert data["sender_config"]["from_name"] == "Sales Team"
        assert data["sender_config"]["reply_to"] == "replies@company.com"

    def test_sender_config_empty_update(self, client, seed_companies_contacts):
        """Updating sender_config to empty should clear it."""
        headers = _headers(client)
        cid = _create_draft_campaign(client, headers)

        # First set it
        client.patch(
            f"/api/campaigns/{cid}",
            headers=headers,
            json={"sender_config": {"from_email": "test@example.com"}},
        )

        # Then clear it
        resp = client.patch(
            f"/api/campaigns/{cid}",
            headers=headers,
            json={"sender_config": {}},
        )
        assert resp.status_code == 200

        resp2 = client.get(f"/api/campaigns/{cid}", headers=headers)
        data = resp2.get_json()
        assert data["sender_config"] == {}


# ── Test: Full Outreach Workflow Integration ─────────────────────


class TestOutreachWorkflowIntegration:
    """End-to-end integration: create campaign -> select contacts ->
    generate (mocked) -> review -> approve -> send emails -> queue linkedin.
    """

    @patch("api.routes.campaign_routes.start_generation")
    def test_full_outreach_flow(
        self, mock_start, client, seed_companies_contacts, db
    ):
        """Complete outreach workflow from campaign creation to analytics."""
        headers = _headers(client)
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id

        # 1. Create campaign with sender config
        cid = _create_draft_campaign(client, headers, name="Integration Test")
        sender_config = {
            "from_email": "outreach@test.com",
            "from_name": "Test Sender",
        }
        client.patch(
            f"/api/campaigns/{cid}",
            headers=headers,
            json={"sender_config": sender_config},
        )

        # 2. Set template config
        template_config = [
            {"step": 1, "channel": "email", "label": "Intro", "enabled": True},
            {
                "step": 2,
                "channel": "linkedin_connect",
                "label": "LI Connect",
                "enabled": True,
            },
        ]
        _add_template_config(client, headers, cid, template_config)

        # 3. Add contacts by ICP filter (owner=Alice)
        owner1_id = str(seed["owners"][0].id)
        resp = client.post(
            f"/api/campaigns/{cid}/contacts",
            headers=headers,
            json={"owner_id": owner1_id},
        )
        assert resp.status_code == 200
        added_count = resp.get_json()["added"]
        assert added_count > 0

        # 4. Cost estimate
        resp = client.post(f"/api/campaigns/{cid}/cost-estimate", headers=headers)
        assert resp.status_code == 200
        estimate = resp.get_json()
        assert estimate["total_messages"] > 0

        # 5. Transition to ready
        resp = _transition_campaign(client, headers, cid, "ready")
        assert resp.status_code == 200

        # 6. Start generation (mocked)
        resp = client.post(f"/api/campaigns/{cid}/generate", headers=headers)
        assert resp.status_code == 200
        assert mock_start.called

        # 7. Check generation status
        resp = client.get(f"/api/campaigns/{cid}/generation-status", headers=headers)
        assert resp.status_code == 200
        # Status should be Generating
        status_data = resp.get_json()
        assert status_data["total_contacts"] > 0

        # 8. Simulate generation complete: manually create messages and transition
        # (In real usage, the background thread does this)
        db.session.execute(
            db.text(
                "UPDATE campaigns SET status = 'review' WHERE id = :id"
            ),
            {"id": cid},
        )
        db.session.commit()

        # Create messages for the campaign contacts
        cc_rows = db.session.execute(
            db.text(
                "SELECT id, contact_id FROM campaign_contacts WHERE campaign_id = :cid"
            ),
            {"cid": cid},
        ).fetchall()

        msg_ids = []
        email_msg_ids = []
        li_msg_ids = []
        for cc_id, contact_id in cc_rows:
            # Email message
            m_email = Message(
                tenant_id=tenant_id,
                contact_id=contact_id,
                owner_id=owner1_id,
                channel="email",
                sequence_step=1,
                variant="a",
                subject="Hi there",
                body="Hello, this is a test email.",
                status="draft",
                campaign_contact_id=cc_id,
            )
            db.session.add(m_email)
            db.session.flush()
            msg_ids.append(str(m_email.id))
            email_msg_ids.append(str(m_email.id))

            # LinkedIn message
            m_li = Message(
                tenant_id=tenant_id,
                contact_id=contact_id,
                owner_id=owner1_id,
                channel="linkedin_connect",
                sequence_step=2,
                variant="a",
                body="Let's connect!",
                status="draft",
                campaign_contact_id=cc_id,
            )
            db.session.add(m_li)
            db.session.flush()
            msg_ids.append(str(m_li.id))
            li_msg_ids.append(str(m_li.id))

        db.session.commit()

        # 9. Batch approve all messages
        resp = client.post(
            f"/api/campaigns/{cid}/messages/batch-action",
            headers=headers,
            json={"message_ids": msg_ids, "action": "approve"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["updated"] == len(msg_ids)

        # 10. Queue LinkedIn messages
        resp = client.post(
            f"/api/campaigns/{cid}/queue-linkedin", headers=headers
        )
        assert resp.status_code == 200
        li_result = resp.get_json()
        assert li_result["queued_count"] == len(li_msg_ids)

        # 11. Check analytics
        resp = client.get(f"/api/campaigns/{cid}/analytics", headers=headers)
        assert resp.status_code == 200
        analytics = resp.get_json()

        # Verify message counts
        assert analytics["messages"]["total"] == len(msg_ids)
        assert analytics["messages"]["by_status"].get("approved", 0) == len(msg_ids)
        assert "email" in analytics["messages"]["by_channel"]
        assert "linkedin_connect" in analytics["messages"]["by_channel"]

        # Verify LinkedIn queue in analytics
        assert analytics["sending"]["linkedin"]["total"] == len(li_msg_ids)
        assert analytics["sending"]["linkedin"]["queued"] == len(li_msg_ids)

        # Verify contact counts
        assert analytics["contacts"]["total"] == added_count
