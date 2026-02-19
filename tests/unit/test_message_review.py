"""Unit tests for the message review workflow (BL-047).

Covers: edit with version tracking, disqualification, review queue,
review summary, and approval gate.
"""
import json

from tests.conftest import auth_header


def _setup_campaign_with_messages(db, seed, status="review", msg_count=3):
    """Create a campaign in review status with draft messages linked to contacts."""
    from api.models import Campaign, CampaignContact, Message

    tenant_id = seed["tenant"].id
    owner = seed["owners"][0]

    campaign = Campaign(
        tenant_id=tenant_id,
        name="Review Test Campaign",
        status=status,
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
            channel="linkedin_connect",
            sequence_step=1,
            variant="a",
            subject=f"Subject for {contact.first_name}",
            body=f"Hello {contact.first_name}, this is the original message body.",
            status="draft",
            campaign_contact_id=cc.id,
            tag_id=seed["tags"][0].id,
        )
        db.session.add(m)
        messages.append(m)

    db.session.flush()
    db.session.commit()
    return campaign, campaign_contacts, messages


class TestEditWithVersionTracking:
    """Message edit preserves original body and requires edit_reason."""

    def test_edit_body_saves_original(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)
        original_body = msgs[0].body

        # Edit body with reason
        resp = client.patch(f"/api/messages/{msg_id}", headers=headers, json={
            "body": "Completely new message body",
            "edit_reason": "too_formal",
        })
        assert resp.status_code == 200

        # Verify original was saved
        row = db.session.execute(
            db.text("SELECT body, original_body, edit_reason FROM messages WHERE id = :id"),
            {"id": msg_id},
        ).fetchone()
        assert row[0] == "Completely new message body"
        assert row[1] == original_body
        assert row[2] == "too_formal"

    def test_edit_body_requires_edit_reason(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)

        # Edit without reason - should fail
        resp = client.patch(f"/api/messages/{msg_id}", headers=headers, json={
            "body": "New body without reason",
        })
        assert resp.status_code == 400
        assert "edit_reason" in resp.get_json()["error"]

    def test_edit_invalid_reason_rejected(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)

        resp = client.patch(f"/api/messages/{msg_id}", headers=headers, json={
            "body": "New body",
            "edit_reason": "not_a_valid_reason",
        })
        assert resp.status_code == 400
        assert "Invalid edit_reason" in resp.get_json()["error"]

    def test_original_body_immutable_on_second_edit(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)
        first_body = msgs[0].body

        # First edit
        client.patch(f"/api/messages/{msg_id}", headers=headers, json={
            "body": "Second version",
            "edit_reason": "too_casual",
        })

        # Second edit
        resp = client.patch(f"/api/messages/{msg_id}", headers=headers, json={
            "body": "Third version",
            "edit_reason": "too_long",
        })
        assert resp.status_code == 200

        # original_body should still be the first body, not the second
        row = db.session.execute(
            db.text("SELECT body, original_body, edit_reason FROM messages WHERE id = :id"),
            {"id": msg_id},
        ).fetchone()
        assert row[0] == "Third version"
        assert row[1] == first_body  # Immutable — stays as original
        assert row[2] == "too_long"

    def test_edit_status_without_body_no_reason_needed(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)

        # Changing only status — no edit_reason required
        resp = client.patch(f"/api/messages/{msg_id}", headers=headers, json={
            "status": "approved",
        })
        assert resp.status_code == 200

    def test_edit_subject_saves_original_subject(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)
        original_subject = msgs[0].subject

        resp = client.patch(f"/api/messages/{msg_id}", headers=headers, json={
            "subject": "New Subject Line",
            "edit_reason": "off_topic",
        })
        assert resp.status_code == 200

        row = db.session.execute(
            db.text("SELECT subject, original_subject FROM messages WHERE id = :id"),
            {"id": msg_id},
        ).fetchone()
        assert row[0] == "New Subject Line"
        assert row[1] == original_subject

    def test_edit_reason_text_saved(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)

        resp = client.patch(f"/api/messages/{msg_id}", headers=headers, json={
            "body": "Updated body",
            "edit_reason": "other",
            "edit_reason_text": "Custom reason explanation",
        })
        assert resp.status_code == 200

        row = db.session.execute(
            db.text("SELECT edit_reason, edit_reason_text FROM messages WHERE id = :id"),
            {"id": msg_id},
        ).fetchone()
        assert row[0] == "other"
        assert row[1] == "Custom reason explanation"


class TestDisqualifyContact:
    """Disqualify a contact from a campaign (campaign-only or global)."""

    def test_disqualify_campaign_only(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        contact_id = str(seed["contacts"][0].id)

        resp = client.post(f"/api/campaigns/{campaign.id}/disqualify-contact", headers=headers, json={
            "contact_id": contact_id,
            "scope": "campaign",
            "reason": "Not relevant",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["scope"] == "campaign"
        assert data["messages_rejected"] >= 1

        # Verify campaign_contact is excluded
        cc_status = db.session.execute(
            db.text("""
                SELECT status FROM campaign_contacts
                WHERE campaign_id = :cid AND contact_id = :ctid
            """),
            {"cid": campaign.id, "ctid": contact_id},
        ).fetchone()
        assert cc_status[0] == "excluded"

        # Contact itself should NOT be globally disqualified
        contact_dq = db.session.execute(
            db.text("SELECT is_disqualified FROM contacts WHERE id = :id"),
            {"id": contact_id},
        ).fetchone()
        assert contact_dq[0] is None or contact_dq[0] is False or contact_dq[0] == 0

    def test_disqualify_global(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        contact_id = str(seed["contacts"][0].id)

        resp = client.post(f"/api/campaigns/{campaign.id}/disqualify-contact", headers=headers, json={
            "contact_id": contact_id,
            "scope": "global",
            "reason": "Bad lead",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["scope"] == "global"

        # Contact should be globally disqualified
        row = db.session.execute(
            db.text("SELECT is_disqualified, disqualified_reason FROM contacts WHERE id = :id"),
            {"id": contact_id},
        ).fetchone()
        assert row[0] in (True, 1)
        assert row[1] == "Bad lead"

    def test_disqualify_rejects_draft_messages(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        contact_id = str(seed["contacts"][0].id)
        msg_id = str(msgs[0].id)

        resp = client.post(f"/api/campaigns/{campaign.id}/disqualify-contact", headers=headers, json={
            "contact_id": contact_id,
            "scope": "campaign",
        })
        assert resp.status_code == 200
        assert resp.get_json()["messages_rejected"] == 1

        # Verify message was rejected
        msg_status = db.session.execute(
            db.text("SELECT status, review_notes FROM messages WHERE id = :id"),
            {"id": msg_id},
        ).fetchone()
        assert msg_status[0] == "rejected"
        assert "excluded" in msg_status[1].lower()

    def test_disqualify_requires_contact_id(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        resp = client.post(f"/api/campaigns/{campaign.id}/disqualify-contact", headers=headers, json={
            "scope": "campaign",
        })
        assert resp.status_code == 400
        assert "contact_id" in resp.get_json()["error"]

    def test_disqualify_invalid_scope(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        contact_id = str(seed["contacts"][0].id)

        resp = client.post(f"/api/campaigns/{campaign.id}/disqualify-contact", headers=headers, json={
            "contact_id": contact_id,
            "scope": "invalid",
        })
        assert resp.status_code == 400

    def test_disqualify_contact_not_in_campaign(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        # Contact[5] not added to campaign
        contact_id = str(seed["contacts"][5].id)

        resp = client.post(f"/api/campaigns/{campaign.id}/disqualify-contact", headers=headers, json={
            "contact_id": contact_id,
            "scope": "campaign",
        })
        assert resp.status_code == 404


class TestDisqualifiedContactFilter:
    """Adding contacts to campaigns filters out disqualified contacts."""

    def test_add_contacts_excludes_disqualified(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        # Globally disqualify contact[0]
        db.session.execute(
            db.text("UPDATE contacts SET is_disqualified = true WHERE id = :id"),
            {"id": str(seed["contacts"][0].id)},
        )
        db.session.commit()

        # Create a campaign
        resp = client.post("/api/campaigns", headers=headers, json={"name": "DQ Filter Test"})
        cid = resp.get_json()["id"]

        # Try to add both contact[0] (disqualified) and contact[1] (active)
        resp = client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "contact_ids": [str(seed["contacts"][0].id), str(seed["contacts"][1].id)],
        })
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 1  # Only contact[1] added

    def test_add_by_company_excludes_disqualified(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        # Acme Corp has contact[0] and contact[1] — disqualify contact[0]
        db.session.execute(
            db.text("UPDATE contacts SET is_disqualified = true WHERE id = :id"),
            {"id": str(seed["contacts"][0].id)},
        )
        db.session.commit()

        resp = client.post("/api/campaigns", headers=headers, json={"name": "Company DQ Test"})
        cid = resp.get_json()["id"]

        resp = client.post(f"/api/campaigns/{cid}/contacts", headers=headers, json={
            "company_ids": [str(seed["companies"][0].id)],
        })
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["added"] == 1  # Only contact[1] (Jane) added


class TestReviewSummary:
    """GET /campaigns/<id>/review-summary — message counts and approval readiness."""

    def test_review_summary_all_draft(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=3)

        resp = client.get(f"/api/campaigns/{campaign.id}/review-summary", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["draft"] == 3
        assert data["approved"] == 0
        assert data["rejected"] == 0
        assert data["can_approve_outreach"] is False
        assert "pending" in data["pending_reason"].lower()

    def test_review_summary_all_reviewed(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        # Approve both messages
        for m in msgs:
            db.session.execute(
                db.text("UPDATE messages SET status = 'approved' WHERE id = :id"),
                {"id": str(m.id)},
            )
        db.session.commit()

        resp = client.get(f"/api/campaigns/{campaign.id}/review-summary", headers=headers)
        data = resp.get_json()
        assert data["draft"] == 0
        assert data["approved"] == 2
        assert data["can_approve_outreach"] is True
        assert data["pending_reason"] is None

    def test_review_summary_mixed_statuses(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=3)

        # Approve first, reject second, leave third as draft
        db.session.execute(
            db.text("UPDATE messages SET status = 'approved' WHERE id = :id"),
            {"id": str(msgs[0].id)},
        )
        db.session.execute(
            db.text("UPDATE messages SET status = 'rejected' WHERE id = :id"),
            {"id": str(msgs[1].id)},
        )
        db.session.commit()

        resp = client.get(f"/api/campaigns/{campaign.id}/review-summary", headers=headers)
        data = resp.get_json()
        assert data["approved"] == 1
        assert data["rejected"] == 1
        assert data["draft"] == 1
        assert data["can_approve_outreach"] is False

    def test_review_summary_excluded_contacts(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        # Exclude first contact
        db.session.execute(
            db.text("UPDATE campaign_contacts SET status = 'excluded' WHERE id = :id"),
            {"id": str(ccs[0].id)},
        )
        db.session.commit()

        resp = client.get(f"/api/campaigns/{campaign.id}/review-summary", headers=headers)
        data = resp.get_json()
        assert data["excluded_contacts"] == 1

    def test_review_summary_channel_breakdown(self, client, seed_companies_contacts, db):
        from api.models import Campaign, CampaignContact, Message

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id
        owner = seed["owners"][0]

        campaign = Campaign(tenant_id=tenant_id, name="Channel Test", status="review")
        db.session.add(campaign)
        db.session.flush()

        contact = seed["contacts"][0]
        cc = CampaignContact(
            campaign_id=campaign.id, contact_id=contact.id,
            tenant_id=tenant_id, status="generated",
        )
        db.session.add(cc)
        db.session.flush()

        # Two channels
        m1 = Message(
            tenant_id=tenant_id, contact_id=contact.id, owner_id=owner.id,
            channel="linkedin_connect", sequence_step=1, variant="a",
            body="LI msg", status="approved", campaign_contact_id=cc.id,
        )
        m2 = Message(
            tenant_id=tenant_id, contact_id=contact.id, owner_id=owner.id,
            channel="email", sequence_step=2, variant="a",
            subject="Email", body="Email msg", status="draft", campaign_contact_id=cc.id,
        )
        db.session.add_all([m1, m2])
        db.session.commit()

        resp = client.get(f"/api/campaigns/{campaign.id}/review-summary", headers=headers)
        data = resp.get_json()
        assert "linkedin_connect" in data["by_channel"]
        assert data["by_channel"]["linkedin_connect"]["approved"] == 1
        assert "email" in data["by_channel"]
        assert data["by_channel"]["email"]["draft"] == 1


class TestApprovalGate:
    """Campaign review -> approved transition blocked when draft messages exist."""

    def test_approval_blocked_with_drafts(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        # Try to approve — should fail because draft messages exist
        resp = client.patch(f"/api/campaigns/{campaign.id}", headers=headers, json={
            "status": "approved",
        })
        assert resp.status_code == 400
        assert "draft" in resp.get_json()["error"].lower()
        assert resp.get_json()["pending_count"] == 2

    def test_approval_allowed_all_reviewed(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        # Review all messages (approve/reject)
        db.session.execute(
            db.text("UPDATE messages SET status = 'approved' WHERE id = :id"),
            {"id": str(msgs[0].id)},
        )
        db.session.execute(
            db.text("UPDATE messages SET status = 'rejected' WHERE id = :id"),
            {"id": str(msgs[1].id)},
        )
        db.session.commit()

        resp = client.patch(f"/api/campaigns/{campaign.id}", headers=headers, json={
            "status": "approved",
        })
        assert resp.status_code == 200

        # Verify status changed
        detail = client.get(f"/api/campaigns/{campaign.id}", headers=headers)
        assert detail.get_json()["status"] == "Approved"


class TestReviewQueue:
    """GET /campaigns/<id>/review-queue — ordered messages with full context."""

    def test_queue_returns_ordered_messages(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=3)

        resp = client.get(
            f"/api/campaigns/{campaign.id}/review-queue?status=draft",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["queue"]) == 3
        assert data["stats"]["draft"] == 3

        # Each item has position, message, contact, company
        item = data["queue"][0]
        assert item["position"] == 1
        assert item["total"] == 3
        assert "id" in item["message"]
        assert "body" in item["message"]
        assert "full_name" in item["contact"]
        assert item["contact"]["contact_score"] is not None

    def test_queue_ordered_by_contact_score_desc(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=3)

        resp = client.get(
            f"/api/campaigns/{campaign.id}/review-queue?status=draft",
            headers=headers,
        )
        queue = resp.get_json()["queue"]
        scores = [item["contact"]["contact_score"] for item in queue]
        assert scores == sorted(scores, reverse=True)

    def test_queue_excludes_excluded_contacts(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        # Exclude first contact
        db.session.execute(
            db.text("UPDATE campaign_contacts SET status = 'excluded' WHERE id = :id"),
            {"id": str(ccs[0].id)},
        )
        db.session.commit()

        resp = client.get(
            f"/api/campaigns/{campaign.id}/review-queue?status=draft",
            headers=headers,
        )
        queue = resp.get_json()["queue"]
        assert len(queue) == 1  # Only non-excluded contact

    def test_queue_filter_by_channel(self, client, seed_companies_contacts, db):
        from api.models import Campaign, CampaignContact, Message

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        tenant_id = seed["tenant"].id
        owner = seed["owners"][0]

        campaign = Campaign(tenant_id=tenant_id, name="Channel Queue", status="review")
        db.session.add(campaign)
        db.session.flush()

        contact = seed["contacts"][0]
        cc = CampaignContact(
            campaign_id=campaign.id, contact_id=contact.id,
            tenant_id=tenant_id, status="generated",
        )
        db.session.add(cc)
        db.session.flush()

        m_li = Message(
            tenant_id=tenant_id, contact_id=contact.id, owner_id=owner.id,
            channel="linkedin_connect", sequence_step=1, variant="a",
            body="LI msg", status="draft", campaign_contact_id=cc.id,
        )
        m_email = Message(
            tenant_id=tenant_id, contact_id=contact.id, owner_id=owner.id,
            channel="email", sequence_step=2, variant="a",
            subject="Email", body="Email msg", status="draft", campaign_contact_id=cc.id,
        )
        db.session.add_all([m_li, m_email])
        db.session.commit()

        # Filter by linkedin only
        resp = client.get(
            f"/api/campaigns/{campaign.id}/review-queue?status=draft&channel=linkedin_connect",
            headers=headers,
        )
        queue = resp.get_json()["queue"]
        assert len(queue) == 1
        assert queue[0]["message"]["channel"] == "linkedin_connect"

    def test_queue_includes_version_tracking_fields(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        resp = client.get(
            f"/api/campaigns/{campaign.id}/review-queue?status=draft",
            headers=headers,
        )
        msg = resp.get_json()["queue"][0]["message"]
        assert "original_body" in msg
        assert "original_subject" in msg
        assert "edit_reason" in msg
        assert "regen_count" in msg
        assert msg["regen_count"] == 0

    def test_queue_stats_reflect_all_statuses(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=3)

        # Approve one message
        db.session.execute(
            db.text("UPDATE messages SET status = 'approved' WHERE id = :id"),
            {"id": str(msgs[0].id)},
        )
        db.session.commit()

        # Request only draft messages
        resp = client.get(
            f"/api/campaigns/{campaign.id}/review-queue?status=draft",
            headers=headers,
        )
        data = resp.get_json()
        assert len(data["queue"]) == 2  # Only drafts in queue
        # But stats show all statuses
        assert data["stats"]["approved"] == 1
        assert data["stats"]["draft"] == 2


class TestRegenerationValidation:
    """Validate regeneration endpoint input checks (without calling LLM)."""

    def test_regen_invalid_formality(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)

        resp = client.post(f"/api/messages/{msg_id}/regenerate", headers=headers, json={
            "formality": "super_casual",
        })
        assert resp.status_code == 400
        assert "formality" in resp.get_json()["error"]

    def test_regen_instruction_too_long(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)

        resp = client.post(f"/api/messages/{msg_id}/regenerate", headers=headers, json={
            "instruction": "x" * 201,
        })
        assert resp.status_code == 400
        assert "200" in resp.get_json()["error"]

    def test_regen_blocked_while_generating(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=1)

        msg_id = str(msgs[0].id)

        # Set message to generating status
        db.session.execute(
            db.text("UPDATE messages SET status = 'generating' WHERE id = :id"),
            {"id": msg_id},
        )
        db.session.commit()

        resp = client.post(f"/api/messages/{msg_id}/regenerate", headers=headers, json={})
        assert resp.status_code == 409
        assert "being generated" in resp.get_json()["error"].lower()

    def test_regen_nonexistent_message(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/messages/00000000-0000-0000-0000-000000000099/regenerate",
            headers=headers,
            json={},
        )
        assert resp.status_code == 404


class TestBuildPromptFormality:
    """Unit test for formality and per-message instruction in prompt builder."""

    def test_formality_instruction_injected(self):
        from api.services.generation_prompts import build_generation_prompt

        prompt = build_generation_prompt(
            channel="email",
            step_label="Email 1",
            contact_data={"first_name": "Jan", "last_name": "Novak"},
            company_data={"name": "Czech Corp"},
            enrichment_data={"l2": {}, "person": {}},
            generation_config={"tone": "professional", "language": "cs"},
            step_number=1,
            total_steps=1,
            formality="informal",
        )
        # Czech informal uses "tykání – ty" form
        assert "tyk" in prompt.lower() or "informal" in prompt.lower()

    def test_per_message_instruction_appended(self):
        from api.services.generation_prompts import build_generation_prompt

        prompt = build_generation_prompt(
            channel="linkedin_connect",
            step_label="LI Invite",
            contact_data={"first_name": "Maria"},
            company_data={"name": "Test GmbH"},
            enrichment_data={"l2": {}, "person": {}},
            generation_config={},
            step_number=1,
            total_steps=1,
            per_message_instruction="Mention we met at Web Summit",
        )
        assert "Mention we met at Web Summit" in prompt
