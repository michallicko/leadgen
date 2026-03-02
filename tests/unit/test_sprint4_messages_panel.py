"""Tests for BL-118: Messages phase panel endpoints.

Covers 6 endpoints:
- POST /api/playbook/<id>/messages/setup
- POST /api/playbook/<id>/generate-messages
- GET  /api/playbook/<id>/messages
- PATCH /api/playbook/<id>/messages/<message_id>
- POST /api/playbook/<id>/messages/batch
- POST /api/playbook/<id>/confirm-messages
"""

import json
import uuid
from unittest.mock import patch


from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin):
    """Create a strategy document with selected contacts in playbook_selections."""
    from api.models import (
        Company,
        Contact,
        StrategyDocument,
        UserTenantRole,
    )

    # Give admin a tenant role
    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=seed_tenant.id,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)

    # Create company + contacts
    company = Company(
        tenant_id=seed_tenant.id,
        name="TestCo",
        domain="testco.com",
        status="enriched_l2",
    )
    db.session.add(company)
    db.session.flush()

    contacts = []
    for i in range(3):
        c = Contact(
            tenant_id=seed_tenant.id,
            first_name=f"Contact{i}",
            last_name="Test",
            job_title=f"Role {i}",
            email_address=f"c{i}@testco.com",
            company_id=company.id,
        )
        db.session.add(c)
        contacts.append(c)
    db.session.flush()

    contact_ids = [str(c.id) for c in contacts]

    # Create strategy document with selections
    doc = StrategyDocument(
        tenant_id=seed_tenant.id,
        status="active",
        phase="messages",
        playbook_selections=json.dumps({
            "contacts": {"selected_ids": contact_ids},
        }),
        extracted_data=json.dumps({
            "messaging": {"tone": "professional", "angles": ["pain_point"]},
            "channels": {"primary": "email"},
        }),
    )
    db.session.add(doc)
    db.session.commit()

    return {
        "doc": doc,
        "company": company,
        "contacts": contacts,
        "contact_ids": contact_ids,
    }


def _setup_with_campaign(db, seed_tenant, seed_super_admin, with_messages=False):
    """Create full setup including a campaign linked to the strategy."""
    from api.models import Campaign, CampaignContact, Message

    data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)

    campaign = Campaign(
        tenant_id=seed_tenant.id,
        name="Test Campaign",
        strategy_id=data["doc"].id,
        status="review",
        channel="email",
        template_config=json.dumps([
            {"step": 1, "label": "outreach", "channel": "email", "enabled": True}
        ]),
    )
    db.session.add(campaign)
    db.session.flush()

    for cid in data["contact_ids"]:
        cc = CampaignContact(
            campaign_id=campaign.id,
            contact_id=cid,
            tenant_id=seed_tenant.id,
            status="pending",
        )
        db.session.add(cc)
    db.session.flush()

    messages = []
    if with_messages:
        for i, cid in enumerate(data["contact_ids"]):
            msg = Message(
                tenant_id=seed_tenant.id,
                contact_id=cid,
                channel="email",
                sequence_step=1,
                variant="a",
                subject=f"Subject {i}",
                body=f"Hello Contact{i}, this is message {i}.",
                status="draft",
            )
            db.session.add(msg)
            messages.append(msg)
        db.session.flush()

    db.session.commit()

    data["campaign"] = campaign
    data["messages"] = messages
    return data


# ---------------------------------------------------------------------------
# Test: POST /api/playbook/<id>/messages/setup
# ---------------------------------------------------------------------------


class TestSetupMessages:
    def test_creates_campaign_and_assigns_contacts(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/messages/setup",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["created"] is True
        assert body["campaign_id"] is not None
        assert body["total_contacts"] == 3
        assert body["contacts_added"] == 3
        assert body["campaign_status"] == "draft"

    def test_loads_existing_campaign(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(db, seed_tenant, seed_super_admin)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/messages/setup",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["created"] is False
        assert body["campaign_id"] == str(data["campaign"].id)

    def test_no_contacts_returns_400(
        self, client, db, seed_tenant, seed_super_admin
    ):
        from api.models import StrategyDocument, UserTenantRole

        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            status="active",
            phase="messages",
            playbook_selections=json.dumps({"contacts": {"selected_ids": []}}),
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{doc.id}/messages/setup",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "No contacts" in resp.get_json()["error"]

    def test_persists_campaign_id_in_selections(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/messages/setup",
            headers=headers,
        )
        assert resp.status_code == 200
        campaign_id = resp.get_json()["campaign_id"]

        # Verify selections were updated in DB
        db.session.refresh(data["doc"])
        sel = json.loads(data["doc"].playbook_selections)
        assert sel["messages"]["campaign_id"] == campaign_id

    def test_caps_at_500_contacts(
        self, client, db, seed_tenant, seed_super_admin
    ):
        from api.models import Company, Contact, StrategyDocument, UserTenantRole

        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)

        company = Company(
            tenant_id=seed_tenant.id,
            name="BigCo",
            domain="bigco.com",
            status="enriched_l2",
        )
        db.session.add(company)
        db.session.flush()

        # Create 510 contacts
        contact_ids = []
        for i in range(510):
            c = Contact(
                tenant_id=seed_tenant.id,
                first_name=f"Contact{i}",
                last_name="Test",
                email_address=f"c{i}@bigco.com",
                company_id=company.id,
            )
            db.session.add(c)
            db.session.flush()
            contact_ids.append(str(c.id))

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            status="active",
            phase="messages",
            playbook_selections=json.dumps({
                "contacts": {"selected_ids": contact_ids},
            }),
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{doc.id}/messages/setup",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # Capped at 500
        assert body["total_contacts"] == 500
        assert body["contacts_added"] == 500

    def test_requires_auth(self, client, db, seed_tenant, seed_super_admin):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        resp = client.post(f"/api/playbook/{data['doc'].id}/messages/setup")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: POST /api/playbook/<id>/generate-messages
# ---------------------------------------------------------------------------


class TestGenerateMessages:
    def test_creates_campaign_and_starts_generation(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        with patch("api.services.message_generator.start_generation") as mock_gen:
            resp = client.post(
                f"/api/playbook/{data['doc'].id}/generate-messages",
                headers=headers,
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "generating"
        assert body["total_contacts"] == 3
        assert body["campaign_id"] is not None
        mock_gen.assert_called_once()

    def test_reuses_existing_campaign(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(db, seed_tenant, seed_super_admin)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        with patch("api.services.message_generator.start_generation"):
            resp = client.post(
                f"/api/playbook/{data['doc'].id}/generate-messages",
                headers=headers,
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["campaign_id"] == str(data["campaign"].id)

    def test_no_contacts_returns_400(
        self, client, db, seed_tenant, seed_super_admin
    ):
        from api.models import StrategyDocument, UserTenantRole

        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            status="active",
            phase="messages",
            playbook_selections=json.dumps({"contacts": {"selected_ids": []}}),
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{doc.id}/generate-messages",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "No contacts" in resp.get_json()["error"]

    def test_requires_auth(self, client, db, seed_tenant, seed_super_admin):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        resp = client.post(f"/api/playbook/{data['doc'].id}/generate-messages")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: GET /api/playbook/<id>/messages
# ---------------------------------------------------------------------------


class TestGetPlaybookMessages:
    def test_returns_messages_with_contact_info(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get(
            f"/api/playbook/{data['doc'].id}/messages",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total"] == 3
        assert len(body["messages"]) == 3
        assert body["campaign_id"] == str(data["campaign"].id)
        assert body["campaign_status"] == "review"

        # Check contact info is populated
        msg = body["messages"][0]
        assert "contact" in msg
        assert msg["contact"]["full_name"]

    def test_filters_by_status(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        # Approve one message
        data["messages"][0].status = "approved"
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get(
            f"/api/playbook/{data['doc'].id}/messages?status=approved",
            headers=headers,
        )
        body = resp.get_json()
        assert body["total"] == 1
        assert all(m["status"] == "approved" for m in body["messages"])

    def test_returns_status_counts(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        data["messages"][0].status = "approved"
        data["messages"][1].status = "rejected"
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get(
            f"/api/playbook/{data['doc'].id}/messages",
            headers=headers,
        )
        body = resp.get_json()
        assert body["status_counts"]["approved"] == 1
        assert body["status_counts"]["rejected"] == 1
        assert body["status_counts"]["draft"] == 1

    def test_returns_empty_when_no_campaign(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get(
            f"/api/playbook/{data['doc'].id}/messages",
            headers=headers,
        )
        body = resp.get_json()
        assert body["total"] == 0
        assert body["campaign_id"] is None
        assert body["messages"] == []

    def test_requires_auth(self, client, db, seed_tenant, seed_super_admin):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        resp = client.get(f"/api/playbook/{data['doc'].id}/messages")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: PATCH /api/playbook/<id>/messages/<message_id>
# ---------------------------------------------------------------------------


class TestUpdatePlaybookMessage:
    def test_approve_message(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        msg = data["messages"][0]
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.patch(
            f"/api/playbook/{data['doc'].id}/messages/{msg.id}",
            headers=headers,
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "approved"
        assert body["updated"] is True

    def test_reject_message(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        msg = data["messages"][0]
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.patch(
            f"/api/playbook/{data['doc'].id}/messages/{msg.id}",
            headers=headers,
            json={"status": "rejected"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "rejected"

    def test_edit_body_and_subject(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        msg = data["messages"][0]
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.patch(
            f"/api/playbook/{data['doc'].id}/messages/{msg.id}",
            headers=headers,
            json={"body": "New body text", "subject": "New subject"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["body"] == "New body text"
        assert body["subject"] == "New subject"

    def test_message_not_found(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        fake_id = str(uuid.uuid4())
        resp = client.patch(
            f"/api/playbook/{data['doc'].id}/messages/{fake_id}",
            headers=headers,
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    def test_requires_auth(self, client, db, seed_tenant, seed_super_admin):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        msg = data["messages"][0]
        resp = client.patch(
            f"/api/playbook/{data['doc'].id}/messages/{msg.id}",
            json={"status": "approved"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: POST /api/playbook/<id>/messages/batch
# ---------------------------------------------------------------------------


class TestBatchUpdateMessages:
    def test_approve_all(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/messages/batch",
            headers=headers,
            json={"action": "approve_all"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["updated"] == 3
        assert body["status"] == "approved"

    def test_reject_all(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/messages/batch",
            headers=headers,
            json={"action": "reject_all"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["updated"] == 3
        assert body["status"] == "rejected"

    def test_invalid_action(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/messages/batch",
            headers=headers,
            json={"action": "invalid"},
        )
        assert resp.status_code == 400

    def test_only_updates_draft_messages(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        # Set one message as already approved
        data["messages"][0].status = "approved"
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/messages/batch",
            headers=headers,
            json={"action": "approve_all"},
        )
        body = resp.get_json()
        # Only the 2 remaining drafts should be updated
        assert body["updated"] == 2


# ---------------------------------------------------------------------------
# Test: POST /api/playbook/<id>/confirm-messages
# ---------------------------------------------------------------------------


class TestConfirmMessages:
    def test_confirms_and_advances_phase(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        # Approve all messages
        for m in data["messages"]:
            m.status = "approved"
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/confirm-messages",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["confirmed"] is True
        assert body["approved_count"] == 3
        assert body["phase"] == "campaign"
        assert body["campaign_status"] == "ready"

    def test_rejects_when_no_approved_messages(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/confirm-messages",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "No approved" in resp.get_json()["error"]

    def test_no_campaign_returns_404(
        self, client, db, seed_tenant, seed_super_admin
    ):
        data = _setup_playbook_with_contacts(db, seed_tenant, seed_super_admin)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            f"/api/playbook/{data['doc'].id}/confirm-messages",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_requires_auth(self, client, db, seed_tenant, seed_super_admin):
        data = _setup_with_campaign(
            db, seed_tenant, seed_super_admin, with_messages=True
        )
        resp = client.post(
            f"/api/playbook/{data['doc'].id}/confirm-messages",
        )
        assert resp.status_code == 401
