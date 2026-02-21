"""Tests for EmailSendLog, LinkedInSendQueue, and Campaign.sender_config models."""
import json
import pytest


class TestEmailSendLog:
    def test_create_email_send_log(self, app, db, seed_tenant):
        from api.models import Contact, EmailSendLog, Message, Owner

        owner = Owner(tenant_id=seed_tenant.id, name="Test Owner", is_active=True)
        db.session.add(owner)
        db.session.flush()

        contact = Contact(
            tenant_id=seed_tenant.id,
            first_name="Alice",
            last_name="Test",
            email_address="alice@example.com",
        )
        db.session.add(contact)
        db.session.flush()

        message = Message(
            tenant_id=seed_tenant.id,
            contact_id=contact.id,
            owner_id=owner.id,
            channel="email",
            body="Hello Alice!",
            subject="Introduction",
        )
        db.session.add(message)
        db.session.flush()

        log = EmailSendLog(
            tenant_id=seed_tenant.id,
            message_id=message.id,
            status="queued",
            from_email="sender@company.com",
            to_email="alice@example.com",
        )
        db.session.add(log)
        db.session.commit()

        fetched = db.session.get(EmailSendLog, log.id)
        assert fetched is not None
        assert fetched.tenant_id == seed_tenant.id
        assert fetched.message_id == message.id
        assert fetched.status == "queued"
        assert fetched.from_email == "sender@company.com"
        assert fetched.to_email == "alice@example.com"
        assert fetched.resend_message_id is None
        assert fetched.sent_at is None
        assert fetched.delivered_at is None
        assert fetched.error is None

    def test_email_send_log_to_dict(self, app, db, seed_tenant):
        from api.models import Contact, EmailSendLog, Message, Owner

        owner = Owner(tenant_id=seed_tenant.id, name="Test Owner", is_active=True)
        db.session.add(owner)
        db.session.flush()

        contact = Contact(
            tenant_id=seed_tenant.id,
            first_name="Bob",
            last_name="Test",
        )
        db.session.add(contact)
        db.session.flush()

        message = Message(
            tenant_id=seed_tenant.id,
            contact_id=contact.id,
            owner_id=owner.id,
            channel="email",
            body="Hi Bob!",
        )
        db.session.add(message)
        db.session.flush()

        log = EmailSendLog(
            tenant_id=seed_tenant.id,
            message_id=message.id,
            resend_message_id="re_abc123",
            status="sent",
            from_email="sender@company.com",
            to_email="bob@example.com",
        )
        db.session.add(log)
        db.session.commit()

        d = log.to_dict()
        assert d["id"] == str(log.id)
        assert d["tenant_id"] == str(seed_tenant.id)
        assert d["message_id"] == str(message.id)
        assert d["resend_message_id"] == "re_abc123"
        assert d["status"] == "sent"
        assert d["from_email"] == "sender@company.com"
        assert d["to_email"] == "bob@example.com"
        assert d["sent_at"] is None
        assert d["delivered_at"] is None
        assert d["error"] is None
        assert "created_at" in d

    def test_email_send_log_with_error(self, app, db, seed_tenant):
        from api.models import Contact, EmailSendLog, Message, Owner

        owner = Owner(tenant_id=seed_tenant.id, name="Test Owner", is_active=True)
        db.session.add(owner)
        db.session.flush()

        contact = Contact(
            tenant_id=seed_tenant.id,
            first_name="Carol",
            last_name="Test",
        )
        db.session.add(contact)
        db.session.flush()

        message = Message(
            tenant_id=seed_tenant.id,
            contact_id=contact.id,
            owner_id=owner.id,
            channel="email",
            body="Hello!",
        )
        db.session.add(message)
        db.session.flush()

        log = EmailSendLog(
            tenant_id=seed_tenant.id,
            message_id=message.id,
            status="failed",
            error="Resend API error: invalid from address",
        )
        db.session.add(log)
        db.session.commit()

        d = log.to_dict()
        assert d["status"] == "failed"
        assert d["error"] == "Resend API error: invalid from address"


class TestLinkedInSendQueue:
    def test_create_linkedin_send_queue(self, app, db, seed_tenant):
        from api.models import Contact, LinkedInSendQueue, Message, Owner

        owner = Owner(tenant_id=seed_tenant.id, name="Test Owner", is_active=True)
        db.session.add(owner)
        db.session.flush()

        contact = Contact(
            tenant_id=seed_tenant.id,
            first_name="Dave",
            last_name="Test",
            linkedin_url="https://linkedin.com/in/davetest",
        )
        db.session.add(contact)
        db.session.flush()

        message = Message(
            tenant_id=seed_tenant.id,
            contact_id=contact.id,
            owner_id=owner.id,
            channel="linkedin_connect",
            body="Hi Dave, let's connect!",
        )
        db.session.add(message)
        db.session.flush()

        entry = LinkedInSendQueue(
            tenant_id=seed_tenant.id,
            message_id=message.id,
            contact_id=contact.id,
            owner_id=owner.id,
            action_type="connection_request",
            linkedin_url="https://linkedin.com/in/davetest",
            body="Hi Dave, let's connect!",
            status="queued",
        )
        db.session.add(entry)
        db.session.commit()

        fetched = db.session.get(LinkedInSendQueue, entry.id)
        assert fetched is not None
        assert fetched.tenant_id == seed_tenant.id
        assert fetched.message_id == message.id
        assert fetched.contact_id == contact.id
        assert fetched.owner_id == owner.id
        assert fetched.action_type == "connection_request"
        assert fetched.linkedin_url == "https://linkedin.com/in/davetest"
        assert fetched.body == "Hi Dave, let's connect!"
        assert fetched.status == "queued"
        assert fetched.retry_count == 0
        assert fetched.claimed_at is None
        assert fetched.sent_at is None
        assert fetched.error is None

    def test_linkedin_send_queue_to_dict(self, app, db, seed_tenant):
        from api.models import Contact, LinkedInSendQueue, Message, Owner

        owner = Owner(tenant_id=seed_tenant.id, name="Test Owner", is_active=True)
        db.session.add(owner)
        db.session.flush()

        contact = Contact(
            tenant_id=seed_tenant.id,
            first_name="Eve",
            last_name="Test",
            linkedin_url="https://linkedin.com/in/evetest",
        )
        db.session.add(contact)
        db.session.flush()

        message = Message(
            tenant_id=seed_tenant.id,
            contact_id=contact.id,
            owner_id=owner.id,
            channel="linkedin_message",
            body="Following up on our conversation.",
        )
        db.session.add(message)
        db.session.flush()

        entry = LinkedInSendQueue(
            tenant_id=seed_tenant.id,
            message_id=message.id,
            contact_id=contact.id,
            owner_id=owner.id,
            action_type="message",
            linkedin_url="https://linkedin.com/in/evetest",
            body="Following up on our conversation.",
        )
        db.session.add(entry)
        db.session.commit()

        d = entry.to_dict()
        assert d["id"] == str(entry.id)
        assert d["tenant_id"] == str(seed_tenant.id)
        assert d["message_id"] == str(message.id)
        assert d["contact_id"] == str(contact.id)
        assert d["owner_id"] == str(owner.id)
        assert d["action_type"] == "message"
        assert d["linkedin_url"] == "https://linkedin.com/in/evetest"
        assert d["body"] == "Following up on our conversation."
        assert d["status"] == "queued"
        assert d["retry_count"] == 0
        assert d["claimed_at"] is None
        assert d["sent_at"] is None
        assert d["error"] is None
        assert "created_at" in d

    def test_linkedin_send_queue_with_error(self, app, db, seed_tenant):
        from api.models import Contact, LinkedInSendQueue, Message, Owner

        owner = Owner(tenant_id=seed_tenant.id, name="Test Owner", is_active=True)
        db.session.add(owner)
        db.session.flush()

        contact = Contact(
            tenant_id=seed_tenant.id,
            first_name="Frank",
            last_name="Test",
        )
        db.session.add(contact)
        db.session.flush()

        message = Message(
            tenant_id=seed_tenant.id,
            contact_id=contact.id,
            owner_id=owner.id,
            channel="linkedin_connect",
            body="Let's connect!",
        )
        db.session.add(message)
        db.session.flush()

        entry = LinkedInSendQueue(
            tenant_id=seed_tenant.id,
            message_id=message.id,
            contact_id=contact.id,
            owner_id=owner.id,
            action_type="connection_request",
            body="Let's connect!",
            status="failed",
            error="Profile not found",
            retry_count=3,
        )
        db.session.add(entry)
        db.session.commit()

        d = entry.to_dict()
        assert d["status"] == "failed"
        assert d["error"] == "Profile not found"
        assert d["retry_count"] == 3


class TestCampaignSenderConfig:
    def test_campaign_sender_config_default(self, app, db, seed_tenant):
        from api.models import Campaign

        campaign = Campaign(
            tenant_id=seed_tenant.id,
            name="Test Campaign",
        )
        db.session.add(campaign)
        db.session.commit()

        fetched = db.session.get(Campaign, campaign.id)
        assert fetched is not None
        # In SQLite, JSONB is stored as text; handle both cases
        config = fetched.sender_config
        if isinstance(config, str):
            config = json.loads(config)
        assert config == {} or config is None

    def test_campaign_sender_config_serialization(self, app, db, seed_tenant):
        from api.models import Campaign

        sender_config = {
            "from_email": "outreach@company.com",
            "from_name": "Sales Team",
            "reply_to": "replies@company.com",
        }
        campaign = Campaign(
            tenant_id=seed_tenant.id,
            name="Outreach Campaign",
            sender_config=sender_config,
        )
        db.session.add(campaign)
        db.session.commit()

        fetched = db.session.get(Campaign, campaign.id)
        config = fetched.sender_config
        if isinstance(config, str):
            config = json.loads(config)
        assert config["from_email"] == "outreach@company.com"
        assert config["from_name"] == "Sales Team"
        assert config["reply_to"] == "replies@company.com"

    def test_campaign_sender_config_update(self, app, db, seed_tenant):
        from api.models import Campaign

        campaign = Campaign(
            tenant_id=seed_tenant.id,
            name="Updateable Campaign",
            sender_config={"from_email": "old@company.com"},
        )
        db.session.add(campaign)
        db.session.commit()

        # Update sender_config
        campaign.sender_config = {
            "from_email": "new@company.com",
            "from_name": "New Name",
        }
        db.session.commit()

        fetched = db.session.get(Campaign, campaign.id)
        config = fetched.sender_config
        if isinstance(config, str):
            config = json.loads(config)
        assert config["from_email"] == "new@company.com"
        assert config["from_name"] == "New Name"
