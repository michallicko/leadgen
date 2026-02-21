"""Unit tests for LinkedIn send queue API (Task 7).

Tests cover:
- Queue creation from campaign (POST /campaigns/<id>/queue-linkedin)
- Extension pull (GET /extension/linkedin-queue) — claims items
- Status update (PATCH /extension/linkedin-queue/<id>) — sent, failed, skipped
- Owner isolation (owner A can't see owner B's queue)
- Daily stats calculation (GET /extension/linkedin-queue/stats)
- Idempotency (re-queuing skips existing entries)
- Status propagation to source message
"""
from tests.conftest import auth_header


def _make_campaign_with_linkedin_messages(db, seed):
    """Helper: create a campaign with approved LinkedIn messages for testing."""
    from api.models import Campaign, CampaignContact, Message

    tenant_id = seed["tenant"].id
    owner1 = seed["owners"][0]  # Alice
    owner2 = seed["owners"][1]  # Bob
    contacts = seed["contacts"]

    # Create campaign
    campaign = Campaign(
        tenant_id=tenant_id,
        name="LinkedIn Test Campaign",
        status="approved",
    )
    db.session.add(campaign)
    db.session.flush()

    # Add contacts to campaign (contacts[0] = John/Alice, contacts[4] = Dave/Bob)
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
    cc3 = CampaignContact(
        campaign_id=campaign.id,
        contact_id=contacts[1].id,
        tenant_id=tenant_id,
        status="generated",
    )
    db.session.add_all([cc1, cc2, cc3])
    db.session.flush()

    # LinkedIn connect message for contact[0] (owner=Alice) - approved
    m1 = Message(
        tenant_id=tenant_id,
        contact_id=contacts[0].id,
        owner_id=owner1.id,
        channel="linkedin_connect",
        body="Hi John, let's connect!",
        status="approved",
        campaign_contact_id=cc1.id,
    )
    # LinkedIn message for contact[4] (owner=Bob) - approved
    m2 = Message(
        tenant_id=tenant_id,
        contact_id=contacts[4].id,
        owner_id=owner2.id,
        channel="linkedin_message",
        body="Hi Dave, following up.",
        status="approved",
        campaign_contact_id=cc2.id,
    )
    # Email message (not LinkedIn) - should be skipped
    m3 = Message(
        tenant_id=tenant_id,
        contact_id=contacts[1].id,
        owner_id=owner1.id,
        channel="email",
        body="Email body",
        subject="Hello",
        status="approved",
        campaign_contact_id=cc3.id,
    )
    # LinkedIn message for contact[1] - draft (not approved, should be skipped)
    m4 = Message(
        tenant_id=tenant_id,
        contact_id=contacts[1].id,
        owner_id=owner1.id,
        channel="linkedin_connect",
        body="Draft message",
        status="draft",
        campaign_contact_id=cc3.id,
    )
    db.session.add_all([m1, m2, m3, m4])
    db.session.commit()

    return {
        "campaign": campaign,
        "campaign_contacts": [cc1, cc2, cc3],
        "messages": [m1, m2, m3, m4],
    }


class TestQueueLinkedIn:
    """POST /api/campaigns/<id>/queue-linkedin"""

    def test_queue_creates_entries(self, client, seed_companies_contacts, db):
        """Queuing creates LinkedInSendQueue entries for approved LinkedIn messages."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        data = _make_campaign_with_linkedin_messages(db, seed)

        resp = client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=headers,
        )
        assert resp.status_code == 200
        result = resp.get_json()
        # Should queue 2 LinkedIn messages (m1 and m2), not email (m3) or draft (m4)
        assert result["queued_count"] == 2
        assert "Alice" in result["by_owner"]
        assert "Bob" in result["by_owner"]
        assert result["by_owner"]["Alice"] == 1
        assert result["by_owner"]["Bob"] == 1

    def test_queue_idempotent(self, client, seed_companies_contacts, db):
        """Re-queuing the same campaign skips already-queued messages."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        data = _make_campaign_with_linkedin_messages(db, seed)

        # Queue once
        resp1 = client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=headers,
        )
        assert resp1.get_json()["queued_count"] == 2

        # Queue again — should skip all
        resp2 = client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=headers,
        )
        assert resp2.get_json()["queued_count"] == 0

    def test_queue_empty_campaign(self, client, seed_companies_contacts, db):
        """Queuing a campaign with no approved LinkedIn messages returns 0."""
        from api.models import Campaign

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts

        # Campaign with no messages
        campaign = Campaign(
            tenant_id=seed["tenant"].id,
            name="Empty Campaign",
            status="draft",
        )
        db.session.add(campaign)
        db.session.commit()

        resp = client.post(
            f"/api/campaigns/{campaign.id}/queue-linkedin",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["queued_count"] == 0

    def test_queue_campaign_not_found(self, client, seed_companies_contacts):
        """Queuing a nonexistent campaign returns 404."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/campaigns/00000000-0000-0000-0000-000000000099/queue-linkedin",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_queue_correct_action_types(self, client, seed_companies_contacts, db):
        """Queue entries have correct action_type based on channel."""
        from api.models import LinkedInSendQueue

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        data = _make_campaign_with_linkedin_messages(db, seed)

        client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=headers,
        )

        entries = LinkedInSendQueue.query.filter_by(
            tenant_id=str(seed["tenant"].id)
        ).all()
        action_types = {e.action_type for e in entries}
        assert "connection_request" in action_types
        assert "message" in action_types


class TestExtensionPull:
    """GET /api/extension/linkedin-queue"""

    def _setup_user_with_owner(self, db, seed):
        """Create a user linked to owner[0] (Alice)."""
        from api.models import User, UserTenantRole
        from api.auth import hash_password

        user = User(
            email="alice@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Alice User",
            is_super_admin=False,
            is_active=True,
            owner_id=seed["owners"][0].id,
        )
        db.session.add(user)
        db.session.flush()
        role = UserTenantRole(
            user_id=user.id,
            tenant_id=seed["tenant"].id,
            role="editor",
            granted_by=user.id,
        )
        db.session.add(role)
        db.session.commit()
        return user

    def _setup_user_with_owner_bob(self, db, seed):
        """Create a user linked to owner[1] (Bob)."""
        from api.models import User, UserTenantRole
        from api.auth import hash_password

        user = User(
            email="bob@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Bob User",
            is_super_admin=False,
            is_active=True,
            owner_id=seed["owners"][1].id,
        )
        db.session.add(user)
        db.session.flush()
        role = UserTenantRole(
            user_id=user.id,
            tenant_id=seed["tenant"].id,
            role="editor",
            granted_by=user.id,
        )
        db.session.add(role)
        db.session.commit()
        return user

    def test_pull_returns_own_messages(self, client, seed_companies_contacts, db):
        """Extension pulls only the authenticated user's owner queue items."""
        seed = seed_companies_contacts
        self._setup_user_with_owner(db, seed)
        data = _make_campaign_with_linkedin_messages(db, seed)

        # Queue messages using admin
        admin_headers = auth_header(client)
        admin_headers["X-Namespace"] = "test-corp"
        client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=admin_headers,
        )

        # Pull as Alice — should see only Alice's items
        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/extension/linkedin-queue", headers=alice_headers)
        assert resp.status_code == 200
        items = resp.get_json()
        assert len(items) == 1
        assert items[0]["contact_name"] == "John Doe"
        assert items[0]["action_type"] == "connection_request"
        assert items[0]["body"] == "Hi John, let's connect!"

    def test_pull_marks_as_claimed(self, client, seed_companies_contacts, db):
        """Pulled items are marked as 'claimed' and not returned again."""
        from api.models import LinkedInSendQueue

        seed = seed_companies_contacts
        self._setup_user_with_owner(db, seed)
        data = _make_campaign_with_linkedin_messages(db, seed)

        admin_headers = auth_header(client)
        admin_headers["X-Namespace"] = "test-corp"
        client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=admin_headers,
        )

        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"

        # First pull
        resp1 = client.get("/api/extension/linkedin-queue", headers=alice_headers)
        items1 = resp1.get_json()
        assert len(items1) == 1

        # Verify status changed to claimed
        entry = LinkedInSendQueue.query.filter_by(
            id=items1[0]["id"]
        ).first()
        assert entry.status == "claimed"
        assert entry.claimed_at is not None

        # Second pull — should return empty (item is claimed)
        resp2 = client.get("/api/extension/linkedin-queue", headers=alice_headers)
        items2 = resp2.get_json()
        assert len(items2) == 0

    def test_owner_isolation(self, client, seed_companies_contacts, db):
        """Owner A cannot see owner B's queue items."""
        seed = seed_companies_contacts
        self._setup_user_with_owner(db, seed)
        self._setup_user_with_owner_bob(db, seed)
        data = _make_campaign_with_linkedin_messages(db, seed)

        admin_headers = auth_header(client)
        admin_headers["X-Namespace"] = "test-corp"
        client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=admin_headers,
        )

        # Alice sees only her items
        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"
        resp_alice = client.get("/api/extension/linkedin-queue", headers=alice_headers)
        alice_items = resp_alice.get_json()

        # Bob sees only his items
        bob_headers = auth_header(client, email="bob@test.com")
        bob_headers["X-Namespace"] = "test-corp"
        resp_bob = client.get("/api/extension/linkedin-queue", headers=bob_headers)
        bob_items = resp_bob.get_json()

        # Alice has 1 (John Doe), Bob has 1 (Dave Brown)
        assert len(alice_items) == 1
        assert len(bob_items) == 1
        assert alice_items[0]["contact_name"] == "John Doe"
        assert bob_items[0]["contact_name"] == "Dave Brown"

    def test_pull_with_limit(self, client, seed_companies_contacts, db):
        """Limit parameter caps the number of returned items."""
        seed = seed_companies_contacts
        self._setup_user_with_owner(db, seed)
        data = _make_campaign_with_linkedin_messages(db, seed)

        admin_headers = auth_header(client)
        admin_headers["X-Namespace"] = "test-corp"
        client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=admin_headers,
        )

        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"

        # Request with limit=0 should still work (returns up to 0 items)
        resp = client.get(
            "/api/extension/linkedin-queue?limit=1",
            headers=alice_headers,
        )
        items = resp.get_json()
        assert len(items) <= 1

    def test_pull_no_owner_id(self, client, seed_companies_contacts, db):
        """User without owner_id gets 400 error."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # The default admin user has no owner_id
        resp = client.get("/api/extension/linkedin-queue", headers=headers)
        assert resp.status_code == 400
        assert "owner_id" in resp.get_json()["error"].lower()


class TestStatusUpdate:
    """PATCH /api/extension/linkedin-queue/<id>"""

    def _setup_queued_item(self, client, db, seed):
        """Create a queued item and return its ID + the alice user headers."""
        from api.models import User, UserTenantRole
        from api.auth import hash_password

        alice_user = User(
            email="alice@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Alice User",
            is_super_admin=False,
            is_active=True,
            owner_id=seed["owners"][0].id,
        )
        db.session.add(alice_user)
        db.session.flush()
        role = UserTenantRole(
            user_id=alice_user.id,
            tenant_id=seed["tenant"].id,
            role="editor",
            granted_by=alice_user.id,
        )
        db.session.add(role)
        db.session.commit()

        data = _make_campaign_with_linkedin_messages(db, seed)

        # Queue messages
        admin_headers = auth_header(client)
        admin_headers["X-Namespace"] = "test-corp"
        client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=admin_headers,
        )

        # Pull as Alice to get item IDs
        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/extension/linkedin-queue", headers=alice_headers)
        items = resp.get_json()
        assert len(items) == 1

        return items[0]["id"], alice_headers, data

    def test_mark_as_sent(self, client, seed_companies_contacts, db):
        """Marking as 'sent' sets sent_at and updates source message."""
        from api.models import LinkedInSendQueue, Message

        seed = seed_companies_contacts
        queue_id, alice_headers, data = self._setup_queued_item(client, db, seed)

        resp = client.patch(
            f"/api/extension/linkedin-queue/{queue_id}",
            headers=alice_headers,
            json={"status": "sent"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        # Verify queue item status
        entry = LinkedInSendQueue.query.filter_by(id=queue_id).first()
        assert entry.status == "sent"
        assert entry.sent_at is not None
        assert entry.error is None

        # Verify source message sent_at was also updated
        msg = Message.query.filter_by(id=str(entry.message_id)).first()
        assert msg.sent_at is not None

    def test_mark_as_failed(self, client, seed_companies_contacts, db):
        """Marking as 'failed' increments retry_count and stores error."""
        from api.models import LinkedInSendQueue

        seed = seed_companies_contacts
        queue_id, alice_headers, _ = self._setup_queued_item(client, db, seed)

        resp = client.patch(
            f"/api/extension/linkedin-queue/{queue_id}",
            headers=alice_headers,
            json={"status": "failed", "error": "Profile not found"},
        )
        assert resp.status_code == 200

        entry = LinkedInSendQueue.query.filter_by(id=queue_id).first()
        assert entry.status == "failed"
        assert entry.error == "Profile not found"
        assert entry.retry_count == 1

    def test_mark_as_skipped(self, client, seed_companies_contacts, db):
        """Marking as 'skipped' sets status without retry."""
        from api.models import LinkedInSendQueue

        seed = seed_companies_contacts
        queue_id, alice_headers, _ = self._setup_queued_item(client, db, seed)

        resp = client.patch(
            f"/api/extension/linkedin-queue/{queue_id}",
            headers=alice_headers,
            json={"status": "skipped", "error": "Already connected"},
        )
        assert resp.status_code == 200

        entry = LinkedInSendQueue.query.filter_by(id=queue_id).first()
        assert entry.status == "skipped"
        assert entry.error == "Already connected"
        assert entry.retry_count == 0

    def test_invalid_status(self, client, seed_companies_contacts, db):
        """Invalid status value returns 400."""
        seed = seed_companies_contacts
        queue_id, alice_headers, _ = self._setup_queued_item(client, db, seed)

        resp = client.patch(
            f"/api/extension/linkedin-queue/{queue_id}",
            headers=alice_headers,
            json={"status": "invalid"},
        )
        assert resp.status_code == 400

    def test_update_not_found(self, client, seed_companies_contacts, db):
        """Updating a nonexistent queue item returns 404."""
        from api.models import User, UserTenantRole
        from api.auth import hash_password

        seed = seed_companies_contacts
        user = User(
            email="alice@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Alice",
            is_super_admin=False,
            is_active=True,
            owner_id=seed["owners"][0].id,
        )
        db.session.add(user)
        db.session.flush()
        role = UserTenantRole(
            user_id=user.id,
            tenant_id=seed["tenant"].id,
            role="editor",
            granted_by=user.id,
        )
        db.session.add(role)
        db.session.commit()

        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"

        resp = client.patch(
            "/api/extension/linkedin-queue/00000000-0000-0000-0000-000000000099",
            headers=alice_headers,
            json={"status": "sent"},
        )
        assert resp.status_code == 404

    def test_update_wrong_owner(self, client, seed_companies_contacts, db):
        """User cannot update a queue item belonging to another owner."""
        from api.models import User, UserTenantRole
        from api.auth import hash_password

        seed = seed_companies_contacts
        queue_id, alice_headers, _ = self._setup_queued_item(client, db, seed)

        # Create Bob user linked to owner[1]
        bob = User(
            email="bob@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Bob",
            is_super_admin=False,
            is_active=True,
            owner_id=seed["owners"][1].id,
        )
        db.session.add(bob)
        db.session.flush()
        role = UserTenantRole(
            user_id=bob.id,
            tenant_id=seed["tenant"].id,
            role="editor",
            granted_by=bob.id,
        )
        db.session.add(role)
        db.session.commit()

        bob_headers = auth_header(client, email="bob@test.com")
        bob_headers["X-Namespace"] = "test-corp"

        # Bob tries to update Alice's queue item
        resp = client.patch(
            f"/api/extension/linkedin-queue/{queue_id}",
            headers=bob_headers,
            json={"status": "sent"},
        )
        assert resp.status_code == 403


class TestLinkedInQueueStats:
    """GET /api/extension/linkedin-queue/stats"""

    def test_stats_empty(self, client, seed_companies_contacts, db):
        """Stats for a user with no queue items."""
        from api.models import User, UserTenantRole
        from api.auth import hash_password

        seed = seed_companies_contacts
        user = User(
            email="alice@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Alice",
            is_super_admin=False,
            is_active=True,
            owner_id=seed["owners"][0].id,
        )
        db.session.add(user)
        db.session.flush()
        role = UserTenantRole(
            user_id=user.id,
            tenant_id=seed["tenant"].id,
            role="editor",
            granted_by=user.id,
        )
        db.session.add(role)
        db.session.commit()

        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/extension/linkedin-queue/stats", headers=alice_headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["today"]["sent"] == 0
        assert result["today"]["failed"] == 0
        assert result["today"]["remaining"] == 0
        assert result["limits"]["connections_per_day"] == 15
        assert result["limits"]["messages_per_day"] == 40

    def test_stats_with_queued_items(self, client, seed_companies_contacts, db):
        """Stats reflect queued items."""
        from api.models import User, UserTenantRole
        from api.auth import hash_password

        seed = seed_companies_contacts
        user = User(
            email="alice@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Alice",
            is_super_admin=False,
            is_active=True,
            owner_id=seed["owners"][0].id,
        )
        db.session.add(user)
        db.session.flush()
        role = UserTenantRole(
            user_id=user.id,
            tenant_id=seed["tenant"].id,
            role="editor",
            granted_by=user.id,
        )
        db.session.add(role)
        db.session.commit()

        data = _make_campaign_with_linkedin_messages(db, seed)

        # Queue messages
        admin_headers = auth_header(client)
        admin_headers["X-Namespace"] = "test-corp"
        client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=admin_headers,
        )

        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/extension/linkedin-queue/stats", headers=alice_headers)
        result = resp.get_json()
        assert result["today"]["remaining"] >= 1

    def test_stats_no_owner_id(self, client, seed_companies_contacts, db):
        """User without owner_id gets 400."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.get("/api/extension/linkedin-queue/stats", headers=headers)
        assert resp.status_code == 400


class TestFullLifecycle:
    """End-to-end lifecycle: queue -> pull -> claim -> send -> verify."""

    def test_queue_claim_send_lifecycle(self, client, seed_companies_contacts, db):
        """Full lifecycle: queue messages, pull (claim), mark as sent."""
        from api.models import LinkedInSendQueue, Message, User, UserTenantRole
        from api.auth import hash_password

        seed = seed_companies_contacts
        alice = User(
            email="alice@test.com",
            password_hash=hash_password("testpass123"),
            display_name="Alice",
            is_super_admin=False,
            is_active=True,
            owner_id=seed["owners"][0].id,
        )
        db.session.add(alice)
        db.session.flush()
        role = UserTenantRole(
            user_id=alice.id,
            tenant_id=seed["tenant"].id,
            role="editor",
            granted_by=alice.id,
        )
        db.session.add(role)
        db.session.commit()

        data = _make_campaign_with_linkedin_messages(db, seed)

        # Step 1: Queue messages from campaign
        admin_headers = auth_header(client)
        admin_headers["X-Namespace"] = "test-corp"
        resp = client.post(
            f"/api/campaigns/{data['campaign'].id}/queue-linkedin",
            headers=admin_headers,
        )
        assert resp.get_json()["queued_count"] == 2

        # Step 2: Alice pulls her queue
        alice_headers = auth_header(client, email="alice@test.com")
        alice_headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/extension/linkedin-queue", headers=alice_headers)
        items = resp.get_json()
        assert len(items) == 1
        queue_id = items[0]["id"]

        # Verify claimed status
        entry = LinkedInSendQueue.query.filter_by(id=queue_id).first()
        assert entry.status == "claimed"

        # Step 3: Mark as sent
        resp = client.patch(
            f"/api/extension/linkedin-queue/{queue_id}",
            headers=alice_headers,
            json={"status": "sent"},
        )
        assert resp.status_code == 200

        # Step 4: Verify final state
        entry = LinkedInSendQueue.query.filter_by(id=queue_id).first()
        assert entry.status == "sent"
        assert entry.sent_at is not None

        # Source message should have sent_at set
        msg = Message.query.filter_by(id=str(entry.message_id)).first()
        assert msg.sent_at is not None

        # Queue should now be empty for Alice
        resp = client.get("/api/extension/linkedin-queue", headers=alice_headers)
        assert len(resp.get_json()) == 0
