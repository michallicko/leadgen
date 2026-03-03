"""Tests for POST /api/messages/<id>/mark-sent endpoint (BL-175)."""

from tests.conftest import auth_header


class TestMarkMessageSent:
    """BL-175: LinkedIn Send Integration -- mark-sent endpoint."""

    def test_mark_approved_message_as_sent(
        self, client, seed_companies_contacts, seed_tenant, seed_super_admin
    ):
        """Approved messages can be marked as sent via linkedin."""
        from api.models import db, Message

        # Find the existing draft message and set it to approved
        with client.application.app_context():
            msg = Message.query.filter_by(tenant_id=seed_tenant.id).first()
            msg.status = "approved"
            db.session.commit()
            msg_id = str(msg.id)

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/messages/{msg_id}/mark-sent",
            json={"channel": "linkedin"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"] == "sent"
        assert data["channel"] == "linkedin"

        # Verify DB state
        with client.application.app_context():
            updated = Message.query.get(msg_id)
            assert updated.status == "sent"
            assert updated.sent_at is not None

    def test_mark_draft_message_rejected(
        self, client, seed_companies_contacts, seed_tenant, seed_super_admin
    ):
        """Draft messages cannot be marked as sent."""
        from api.models import Message

        with client.application.app_context():
            msg = Message.query.filter_by(
                tenant_id=seed_tenant.id, status="draft"
            ).first()
            msg_id = str(msg.id)

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/messages/{msg_id}/mark-sent",
            json={"channel": "linkedin"},
            headers=headers,
        )
        assert resp.status_code == 409
        assert "approved" in resp.get_json()["error"].lower()

    def test_mark_sent_requires_channel(
        self, client, seed_companies_contacts, seed_tenant, seed_super_admin
    ):
        """Channel field is required."""
        from api.models import db, Message

        with client.application.app_context():
            msg = Message.query.filter_by(tenant_id=seed_tenant.id).first()
            msg.status = "approved"
            db.session.commit()
            msg_id = str(msg.id)

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/messages/{msg_id}/mark-sent",
            json={},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "channel" in resp.get_json()["error"].lower()

    def test_mark_sent_invalid_channel(
        self, client, seed_companies_contacts, seed_tenant, seed_super_admin
    ):
        """Invalid channel values are rejected."""
        from api.models import db, Message

        with client.application.app_context():
            msg = Message.query.filter_by(tenant_id=seed_tenant.id).first()
            msg.status = "approved"
            db.session.commit()
            msg_id = str(msg.id)

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/messages/{msg_id}/mark-sent",
            json={"channel": "telegram"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "invalid" in resp.get_json()["error"].lower()

    def test_mark_sent_not_found(
        self, client, seed_companies_contacts, seed_tenant, seed_super_admin
    ):
        """Non-existent message returns 404."""
        import uuid

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/messages/{uuid.uuid4()}/mark-sent",
            json={"channel": "linkedin"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_mark_sent_idempotent(
        self, client, seed_companies_contacts, seed_tenant, seed_super_admin
    ):
        """Already-sent messages can be marked again (idempotent)."""
        from api.models import db, Message

        with client.application.app_context():
            msg = Message.query.filter_by(tenant_id=seed_tenant.id).first()
            msg.status = "sent"
            db.session.commit()
            msg_id = str(msg.id)

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            f"/api/messages/{msg_id}/mark-sent",
            json={"channel": "linkedin"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
