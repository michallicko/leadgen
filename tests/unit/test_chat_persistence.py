"""Tests for chat persistence: thread-aware GET, new-thread endpoint, page_context."""

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_header


@pytest.fixture
def seed_strategy_doc(db, seed_tenant, seed_super_admin):
    """Create a strategy document and assign admin role for the tenant."""
    from api.models import StrategyDocument, UserTenantRole

    # Ensure user has role on tenant
    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=seed_tenant.id,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)

    doc = StrategyDocument(
        tenant_id=seed_tenant.id,
        content="Test strategy content",
        status="draft",
    )
    db.session.add(doc)
    db.session.commit()
    return doc


@pytest.fixture
def seed_chat_messages(db, seed_tenant, seed_super_admin, seed_strategy_doc):
    """Create a mix of chat messages with and without thread boundaries."""
    from api.models import StrategyChatMessage

    now = datetime.now(timezone.utc)
    messages = []

    # Old thread messages (before thread_start marker)
    for i in range(3):
        msg = StrategyChatMessage(
            tenant_id=seed_tenant.id,
            document_id=seed_strategy_doc.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Old message {i}",
            created_at=now - timedelta(hours=10 - i),
            created_by=seed_super_admin.id,
        )
        db.session.add(msg)
        messages.append(msg)

    # Thread start marker
    marker = StrategyChatMessage(
        tenant_id=seed_tenant.id,
        document_id=seed_strategy_doc.id,
        role="system",
        content="--- New conversation started ---",
        thread_start=True,
        created_at=now - timedelta(hours=5),
        created_by=seed_super_admin.id,
    )
    db.session.add(marker)
    messages.append(marker)

    # New thread messages (after thread_start marker)
    for i in range(2):
        msg = StrategyChatMessage(
            tenant_id=seed_tenant.id,
            document_id=seed_strategy_doc.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"New message {i}",
            page_context="contacts" if i == 0 else None,
            created_at=now - timedelta(hours=4 - i),
            created_by=seed_super_admin.id,
        )
        db.session.add(msg)
        messages.append(msg)

    db.session.commit()
    return messages


class TestThreadAwareGet:
    """GET /api/playbook/chat returns only current thread messages."""

    def test_returns_only_current_thread(
        self, client, seed_super_admin, seed_tenant, seed_chat_messages
    ):
        """Messages before the latest thread_start are excluded."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook/chat", headers=headers)
        assert resp.status_code == 200

        data = resp.get_json()
        messages = data["messages"]

        # Should include: thread_start marker + 2 new messages = 3
        assert len(messages) == 3

        # First message should be the thread marker
        assert messages[0]["role"] == "system"
        assert messages[0]["thread_start"] is True

        # Remaining should be the new thread messages
        assert messages[1]["content"] == "New message 0"
        assert messages[2]["content"] == "New message 1"

    def test_returns_all_when_no_thread_start(
        self, client, db, seed_super_admin, seed_tenant, seed_strategy_doc
    ):
        """When no thread_start marker exists, return all messages."""
        from api.models import StrategyChatMessage

        now = datetime.now(timezone.utc)
        for i in range(3):
            msg = StrategyChatMessage(
                tenant_id=seed_tenant.id,
                document_id=seed_strategy_doc.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                created_at=now - timedelta(hours=3 - i),
                created_by=seed_super_admin.id,
            )
            db.session.add(msg)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook/chat", headers=headers)
        assert resp.status_code == 200

        data = resp.get_json()
        assert len(data["messages"]) == 3

    def test_page_context_in_response(
        self, client, seed_super_admin, seed_tenant, seed_chat_messages
    ):
        """page_context is included in message serialization."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook/chat", headers=headers)
        data = resp.get_json()

        # The first new message had page_context="contacts"
        msg_with_context = [m for m in data["messages"] if m.get("page_context")]
        assert len(msg_with_context) >= 1
        assert msg_with_context[0]["page_context"] == "contacts"


class TestNewThread:
    """POST /api/playbook/chat/new-thread creates a thread boundary."""

    def test_creates_thread_marker(
        self, client, seed_super_admin, seed_tenant, seed_strategy_doc
    ):
        """New thread endpoint inserts a system message with thread_start=True."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            "/api/playbook/chat/new-thread",
            json={},
            headers=headers,
        )
        assert resp.status_code == 201

        data = resp.get_json()
        assert "thread_id" in data
        assert "created_at" in data

    def test_subsequent_get_returns_empty_thread(
        self, client, db, seed_super_admin, seed_tenant, seed_strategy_doc
    ):
        """After creating a new thread, GET returns only the marker."""
        from api.models import StrategyChatMessage

        # Add some messages first
        now = datetime.now(timezone.utc)
        for i in range(3):
            db.session.add(
                StrategyChatMessage(
                    tenant_id=seed_tenant.id,
                    document_id=seed_strategy_doc.id,
                    role="user",
                    content=f"Old msg {i}",
                    created_at=now - timedelta(hours=5 - i),
                    created_by=seed_super_admin.id,
                )
            )
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        # Create new thread
        resp = client.post(
            "/api/playbook/chat/new-thread",
            json={},
            headers=headers,
        )
        assert resp.status_code == 201

        # GET should now return only the thread marker
        resp = client.get("/api/playbook/chat", headers=headers)
        data = resp.get_json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["thread_start"] is True

    def test_requires_auth(self, client):
        """Endpoint requires authentication."""
        resp = client.post(
            "/api/playbook/chat/new-thread",
            json={},
        )
        assert resp.status_code == 401


class TestPageContext:
    """POST /api/playbook/chat accepts and stores page_context."""

    def test_page_context_stored(
        self, client, db, seed_super_admin, seed_tenant, seed_strategy_doc
    ):
        """page_context from request body is stored on the user message."""
        from api.models import StrategyChatMessage

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post(
            "/api/playbook/chat",
            json={
                "message": "Test message",
                "page_context": "contacts",
            },
            headers=headers,
        )
        # Should succeed (either 200 for SSE or 201 for sync)
        assert resp.status_code in (200, 201)

        # Verify the user message has page_context stored
        user_msg = (
            StrategyChatMessage.query.filter_by(
                document_id=seed_strategy_doc.id, role="user"
            )
            .order_by(StrategyChatMessage.created_at.desc())
            .first()
        )
        assert user_msg is not None
        assert user_msg.page_context == "contacts"


class TestPageContextHints:
    """System prompt includes page-context hints."""

    def test_contacts_page_hint(self):
        """build_system_prompt includes contacts page context hint."""
        from api.services.playbook_service import build_system_prompt

        class MockTenant:
            name = "TestCo"
            slug = "testco"

        class MockDoc:
            content = "Test content"
            objective = "Test objective"
            phase = "strategy"

        prompt = build_system_prompt(
            MockTenant(), MockDoc(), page_context="contacts"
        )
        assert "Contacts list" in prompt
        assert "Current Page Context" in prompt

    def test_no_hint_for_playbook(self):
        """build_system_prompt does not add page context for playbook page."""
        from api.services.playbook_service import build_system_prompt

        class MockTenant:
            name = "TestCo"
            slug = "testco"

        class MockDoc:
            content = "Test content"
            objective = "Test objective"
            phase = "strategy"

        prompt = build_system_prompt(
            MockTenant(), MockDoc(), page_context="playbook"
        )
        assert "Current Page Context" not in prompt

    def test_no_hint_when_none(self):
        """build_system_prompt works without page_context."""
        from api.services.playbook_service import build_system_prompt

        class MockTenant:
            name = "TestCo"
            slug = "testco"

        class MockDoc:
            content = "Test content"
            objective = "Test objective"
            phase = "strategy"

        prompt = build_system_prompt(MockTenant(), MockDoc(), page_context=None)
        assert "Current Page Context" not in prompt
