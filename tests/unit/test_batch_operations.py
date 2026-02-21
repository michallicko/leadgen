"""Unit tests for campaign-scoped batch message operations (Task 5).

Covers: batch approve, batch reject with reason, tenant isolation,
invalid message IDs, and mixed valid/invalid IDs (partial success).
"""
from tests.conftest import auth_header


def _setup_campaign_with_messages(db, seed, msg_count=3, channel="email"):
    """Create a campaign in review status with draft messages linked to contacts."""
    from api.models import Campaign, CampaignContact, Message

    tenant_id = seed["tenant"].id
    owner = seed["owners"][0]

    campaign = Campaign(
        tenant_id=tenant_id,
        name="Batch Action Test Campaign",
        status="review",
    )
    db.session.add(campaign)
    db.session.flush()

    messages = []
    campaign_contacts = []
    for i in range(min(msg_count, len(seed["contacts"]))):
        contact = seed["contacts"][i]
        cc = CampaignContact(
            campaign_id=campaign.id,
            contact_id=contact.id,
            tenant_id=tenant_id,
            status="generated",
        )
        db.session.add(cc)
        db.session.flush()
        campaign_contacts.append(cc)

        m = Message(
            tenant_id=tenant_id,
            contact_id=contact.id,
            owner_id=owner.id,
            channel=channel,
            sequence_step=1,
            variant="a",
            subject=f"Subject for {contact.first_name}",
            body=f"Hello {contact.first_name}, this is a test message.",
            status="draft",
            campaign_contact_id=cc.id,
            tag_id=seed["tags"][0].id,
        )
        db.session.add(m)
        messages.append(m)

    db.session.flush()
    db.session.commit()
    return campaign, campaign_contacts, messages


class TestBatchApprove:
    """POST /api/campaigns/<id>/messages/batch-action with action=approve."""

    def test_batch_approve_sets_status_and_approved_at(
        self, client, seed_companies_contacts, db
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=10)

        message_ids = [str(m.id) for m in msgs]

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            headers=headers,
            json={"message_ids": message_ids, "action": "approve"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["updated"] == 10
        assert data["action"] == "approve"
        assert data["errors"] == []

        # Verify all messages are approved with approved_at set
        for m in msgs:
            row = db.session.execute(
                db.text(
                    "SELECT status, approved_at FROM messages WHERE id = :id"
                ),
                {"id": str(m.id)},
            ).fetchone()
            assert row[0] == "approved"
            assert row[1] is not None

    def test_batch_approve_few_messages(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=5)

        # Approve only 3 of 5
        message_ids = [str(m.id) for m in msgs[:3]]

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            headers=headers,
            json={"message_ids": message_ids, "action": "approve"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["updated"] == 3

        # Remaining 2 should still be draft
        for m in msgs[3:]:
            row = db.session.execute(
                db.text("SELECT status FROM messages WHERE id = :id"),
                {"id": str(m.id)},
            ).fetchone()
            assert row[0] == "draft"


class TestBatchReject:
    """POST /api/campaigns/<id>/messages/batch-action with action=reject."""

    def test_batch_reject_with_reason(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=3)

        message_ids = [str(m.id) for m in msgs]

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            headers=headers,
            json={
                "message_ids": message_ids,
                "action": "reject",
                "reason": "Messages need complete rewrite",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["updated"] == 3
        assert data["action"] == "reject"
        assert data["errors"] == []

        # Verify all messages are rejected with review_notes set
        for m in msgs:
            row = db.session.execute(
                db.text(
                    "SELECT status, review_notes FROM messages WHERE id = :id"
                ),
                {"id": str(m.id)},
            ).fetchone()
            assert row[0] == "rejected"
            assert row[1] == "Messages need complete rewrite"

    def test_batch_reject_without_reason(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        message_ids = [str(m.id) for m in msgs]

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            headers=headers,
            json={"message_ids": message_ids, "action": "reject"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["updated"] == 2

        # review_notes should be empty string (not None)
        for m in msgs:
            row = db.session.execute(
                db.text("SELECT status, review_notes FROM messages WHERE id = :id"),
                {"id": str(m.id)},
            ).fetchone()
            assert row[0] == "rejected"
            assert row[1] == ""


class TestTenantIsolation:
    """Messages from another tenant cannot be batch-updated."""

    def test_cannot_batch_update_other_tenant_messages(
        self, client, seed_companies_contacts, db
    ):
        from api.models import (
            Campaign,
            CampaignContact,
            Contact,
            Message,
            Owner,
            Tenant,
        )

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        # Create a campaign in test-corp tenant
        campaign_own = Campaign(
            tenant_id=seed["tenant"].id,
            name="Own Campaign",
            status="review",
        )
        db.session.add(campaign_own)
        db.session.flush()

        # Create another tenant with its own data
        other_tenant = Tenant(name="Other Corp", slug="other-corp", is_active=True)
        db.session.add(other_tenant)
        db.session.flush()

        other_owner = Owner(
            tenant_id=other_tenant.id, name="Other Owner", is_active=True
        )
        db.session.add(other_owner)
        db.session.flush()

        other_contact = Contact(
            tenant_id=other_tenant.id,
            first_name="Other",
            last_name="Person",
            job_title="CEO",
        )
        db.session.add(other_contact)
        db.session.flush()

        other_campaign = Campaign(
            tenant_id=other_tenant.id,
            name="Other Campaign",
            status="review",
        )
        db.session.add(other_campaign)
        db.session.flush()

        other_cc = CampaignContact(
            campaign_id=other_campaign.id,
            contact_id=other_contact.id,
            tenant_id=other_tenant.id,
            status="generated",
        )
        db.session.add(other_cc)
        db.session.flush()

        other_msg = Message(
            tenant_id=other_tenant.id,
            contact_id=other_contact.id,
            owner_id=other_owner.id,
            channel="email",
            sequence_step=1,
            variant="a",
            body="Other tenant message",
            status="draft",
            campaign_contact_id=other_cc.id,
        )
        db.session.add(other_msg)
        db.session.commit()

        # Try to batch approve the other tenant's message via our campaign
        resp = client.post(
            f"/api/campaigns/{campaign_own.id}/messages/batch-action",
            headers=headers,
            json={
                "message_ids": [str(other_msg.id)],
                "action": "approve",
            },
        )
        # Should return 400 (no valid messages found)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["updated"] == 0
        assert len(data["errors"]) == 1
        assert data["errors"][0]["message_id"] == str(other_msg.id)

        # Verify the other tenant's message was NOT modified
        row = db.session.execute(
            db.text("SELECT status FROM messages WHERE id = :id"),
            {"id": str(other_msg.id)},
        ).fetchone()
        assert row[0] == "draft"


class TestInvalidMessageIds:
    """Invalid or nonexistent message IDs return errors."""

    def test_nonexistent_message_ids(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        fake_id = "00000000-0000-0000-0000-000000000099"

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            headers=headers,
            json={"message_ids": [fake_id], "action": "approve"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["updated"] == 0
        assert len(data["errors"]) == 1
        assert data["errors"][0]["message_id"] == fake_id

    def test_empty_message_ids_rejected(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            headers=headers,
            json={"message_ids": [], "action": "approve"},
        )
        assert resp.status_code == 400
        assert "message_ids" in resp.get_json()["error"]

    def test_invalid_action_rejected(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            headers=headers,
            json={"message_ids": [str(msgs[0].id)], "action": "delete"},
        )
        assert resp.status_code == 400
        assert "action" in resp.get_json()["error"]

    def test_nonexistent_campaign_returns_404(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/messages/batch-action",
            headers=headers,
            json={
                "message_ids": ["00000000-0000-0000-0000-000000000001"],
                "action": "approve",
            },
        )
        assert resp.status_code == 404

    def test_messages_from_wrong_campaign_rejected(
        self, client, seed_companies_contacts, db
    ):
        """Messages that exist but belong to a different campaign are rejected."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        # Create two campaigns with their own messages
        campaign_a, ccs_a, msgs_a = _setup_campaign_with_messages(
            db, seed, msg_count=2
        )

        from api.models import Campaign, CampaignContact, Message

        campaign_b = Campaign(
            tenant_id=seed["tenant"].id,
            name="Campaign B",
            status="review",
        )
        db.session.add(campaign_b)
        db.session.flush()

        # Create a message in campaign_b
        contact = seed["contacts"][5]
        cc_b = CampaignContact(
            campaign_id=campaign_b.id,
            contact_id=contact.id,
            tenant_id=seed["tenant"].id,
            status="generated",
        )
        db.session.add(cc_b)
        db.session.flush()

        msg_b = Message(
            tenant_id=seed["tenant"].id,
            contact_id=contact.id,
            owner_id=seed["owners"][0].id,
            channel="email",
            sequence_step=1,
            variant="a",
            body="Message in campaign B",
            status="draft",
            campaign_contact_id=cc_b.id,
        )
        db.session.add(msg_b)
        db.session.commit()

        # Try to approve campaign_b's message via campaign_a
        resp = client.post(
            f"/api/campaigns/{campaign_a.id}/messages/batch-action",
            headers=headers,
            json={"message_ids": [str(msg_b.id)], "action": "approve"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["updated"] == 0
        assert len(data["errors"]) == 1

        # Message should still be draft
        row = db.session.execute(
            db.text("SELECT status FROM messages WHERE id = :id"),
            {"id": str(msg_b.id)},
        ).fetchone()
        assert row[0] == "draft"


class TestMixedValidInvalid:
    """Mixed valid/invalid message IDs result in partial success."""

    def test_partial_success_with_invalid_ids(
        self, client, seed_companies_contacts, db
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=3)

        valid_ids = [str(m.id) for m in msgs[:2]]
        fake_id = "00000000-0000-0000-0000-000000000099"

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            headers=headers,
            json={
                "message_ids": valid_ids + [fake_id],
                "action": "approve",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["updated"] == 2
        assert data["action"] == "approve"
        assert len(data["errors"]) == 1
        assert data["errors"][0]["message_id"] == fake_id

        # Valid messages should be approved
        for m in msgs[:2]:
            row = db.session.execute(
                db.text("SELECT status FROM messages WHERE id = :id"),
                {"id": str(m.id)},
            ).fetchone()
            assert row[0] == "approved"

        # Third message (not in request) should still be draft
        row = db.session.execute(
            db.text("SELECT status FROM messages WHERE id = :id"),
            {"id": str(msgs[2].id)},
        ).fetchone()
        assert row[0] == "draft"

    def test_partial_success_with_wrong_campaign_ids(
        self, client, seed_companies_contacts, db
    ):
        """Mix of valid IDs from this campaign and IDs from another campaign."""
        from api.models import Campaign, CampaignContact, Message

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        campaign_a, ccs_a, msgs_a = _setup_campaign_with_messages(
            db, seed, msg_count=2
        )

        # Create campaign_b with its own message
        campaign_b = Campaign(
            tenant_id=seed["tenant"].id,
            name="Campaign B Partial",
            status="review",
        )
        db.session.add(campaign_b)
        db.session.flush()

        contact = seed["contacts"][5]
        cc_b = CampaignContact(
            campaign_id=campaign_b.id,
            contact_id=contact.id,
            tenant_id=seed["tenant"].id,
            status="generated",
        )
        db.session.add(cc_b)
        db.session.flush()

        msg_b = Message(
            tenant_id=seed["tenant"].id,
            contact_id=contact.id,
            owner_id=seed["owners"][0].id,
            channel="email",
            sequence_step=1,
            variant="a",
            body="From campaign B",
            status="draft",
            campaign_contact_id=cc_b.id,
        )
        db.session.add(msg_b)
        db.session.commit()

        # Batch approve: 1 valid (campaign_a) + 1 invalid (campaign_b)
        resp = client.post(
            f"/api/campaigns/{campaign_a.id}/messages/batch-action",
            headers=headers,
            json={
                "message_ids": [str(msgs_a[0].id), str(msg_b.id)],
                "action": "reject",
                "reason": "Not good enough",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["updated"] == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["message_id"] == str(msg_b.id)

        # Campaign A message should be rejected
        row = db.session.execute(
            db.text("SELECT status, review_notes FROM messages WHERE id = :id"),
            {"id": str(msgs_a[0].id)},
        ).fetchone()
        assert row[0] == "rejected"
        assert row[1] == "Not good enough"

        # Campaign B message should still be draft
        row = db.session.execute(
            db.text("SELECT status FROM messages WHERE id = :id"),
            {"id": str(msg_b.id)},
        ).fetchone()
        assert row[0] == "draft"


class TestBatchActionAuth:
    """Verify authentication and authorization for batch actions."""

    def test_requires_auth(self, client, seed_companies_contacts, db):
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        resp = client.post(
            f"/api/campaigns/{campaign.id}/messages/batch-action",
            json={"message_ids": [str(msgs[0].id)], "action": "approve"},
        )
        assert resp.status_code == 401
