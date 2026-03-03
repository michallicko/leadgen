# Playbook (GTM Strategy) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Playbook page where AI co-creates a GTM strategy using the namespace's own company research, with a Tiptap block editor + streaming chat panel.

**Architecture:** Flask API with new playbook routes, Anthropic Claude Opus 4.6 for chat (SSE streaming), Tiptap v2 block editor in React, optimistic locking for concurrent edits, LLM extraction on save to power downstream features.

**Tech Stack:** Flask, SQLAlchemy, PostgreSQL (JSONB), Anthropic Messages API (streaming), SSE, React 19, Tiptap v2, TanStack Query v5, Tailwind CSS v4.

---

## Phase 1: Database & Models

### Task 1: Migration — strategy tables + is_self flag

**Files:**
- Create: `migrations/029_strategy_tables.sql`

**Step 1: Write the migration**

```sql
-- 029: Strategy document and chat tables for Playbook feature
--
-- Adds strategy_documents (one per tenant), strategy_chat_messages,
-- and is_self flag on companies for self-enrichment.

BEGIN;

-- ── Self-enrichment flag ──────────────────────
ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS is_self BOOLEAN NOT NULL DEFAULT FALSE;

-- ── Strategy documents ──────────────────────
CREATE TABLE IF NOT EXISTS strategy_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL UNIQUE REFERENCES tenants(id),
    content         JSONB NOT NULL DEFAULT '{}'::jsonb,
    extracted_data  JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
    version         INTEGER NOT NULL DEFAULT 1,
    enrichment_id   UUID REFERENCES companies(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by      UUID REFERENCES users(id)
);

-- ── Strategy chat messages ──────────────────────
CREATE TABLE IF NOT EXISTS strategy_chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    document_id     UUID NOT NULL REFERENCES strategy_documents(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,
    content         TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by      UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_chat_document_time
    ON strategy_chat_messages(document_id, created_at);

COMMIT;
```

**Step 2: Verify migration syntax**

Run: `python -c "open('migrations/029_strategy_tables.sql').read(); print('OK')"`
Expected: OK (file exists and is readable)

**Step 3: Commit**

```bash
git add migrations/029_strategy_tables.sql
git commit -m "feat(playbook): add strategy_documents and chat tables migration"
```

---

### Task 2: SQLAlchemy models

**Files:**
- Modify: `api/models.py` (add StrategyDocument and StrategyChatMessage classes)
- Test: `tests/unit/test_playbook_model.py`

**Step 1: Write the failing test**

Create `tests/unit/test_playbook_model.py`:

```python
"""Tests for StrategyDocument and StrategyChatMessage models."""
import json
import pytest


class TestStrategyDocumentModel:
    """Test the StrategyDocument SQLAlchemy model."""

    def test_create_document(self, app, db, seed_tenant):
        from api.models import StrategyDocument

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content={"type": "doc", "content": []},
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        fetched = db.session.get(StrategyDocument, doc.id)
        assert fetched is not None
        assert fetched.tenant_id == seed_tenant.id
        assert fetched.status == "draft"
        assert fetched.version == 1
        assert fetched.content == {"type": "doc", "content": []}

    def test_one_document_per_tenant(self, app, db, seed_tenant):
        from api.models import StrategyDocument
        from sqlalchemy.exc import IntegrityError

        doc1 = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc1)
        db.session.commit()

        doc2 = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc2)
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_to_dict(self, app, db, seed_tenant):
        from api.models import StrategyDocument

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content={"sections": []},
            extracted_data={"icp": {"industries": ["SaaS"]}},
            status="active",
        )
        db.session.add(doc)
        db.session.commit()

        d = doc.to_dict()
        assert d["status"] == "active"
        assert d["version"] == 1
        assert "id" in d
        assert "content" in d
        assert "extracted_data" in d


class TestStrategyChatMessageModel:
    """Test the StrategyChatMessage model."""

    def test_create_message(self, app, db, seed_tenant):
        from api.models import StrategyDocument, StrategyChatMessage

        doc = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc)
        db.session.commit()

        msg = StrategyChatMessage(
            tenant_id=seed_tenant.id,
            document_id=doc.id,
            role="user",
            content="Help me define my ICP",
        )
        db.session.add(msg)
        db.session.commit()

        fetched = db.session.get(StrategyChatMessage, msg.id)
        assert fetched is not None
        assert fetched.role == "user"
        assert fetched.content == "Help me define my ICP"
        assert fetched.document_id == doc.id
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_model.py -v`
Expected: FAIL with ImportError (StrategyDocument not defined)

**Step 3: Write the models**

Add to `api/models.py` (after the existing model classes, before any bottom-of-file code):

```python
class StrategyDocument(db.Model):
    __tablename__ = "strategy_documents"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("gen_random_uuid()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False, unique=True)
    content = db.Column(JSONB, server_default=db.text("'{}'::jsonb"), nullable=False)
    extracted_data = db.Column(JSONB, server_default=db.text("'{}'::jsonb"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    version = db.Column(db.Integer, nullable=False, default=1)
    enrichment_id = db.Column(UUID(as_uuid=False), db.ForeignKey("companies.id"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_by = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"))

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "content": self.content or {},
            "extracted_data": self.extracted_data or {},
            "status": self.status,
            "version": self.version,
            "enrichment_id": self.enrichment_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }


class StrategyChatMessage(db.Model):
    __tablename__ = "strategy_chat_messages"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("gen_random_uuid()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    document_id = db.Column(UUID(as_uuid=False), db.ForeignKey("strategy_documents.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    metadata = db.Column(JSONB, server_default=db.text("'{}'::jsonb"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    created_by = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"))

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }
```

Also add `is_self` to the Company model (find the Company class and add):
```python
    is_self = db.Column(db.Boolean, nullable=False, default=False)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_model.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add api/models.py tests/unit/test_playbook_model.py
git commit -m "feat(playbook): add StrategyDocument and StrategyChatMessage models"
```

---

## Phase 2: Playbook API Routes

### Task 3: GET /api/playbook — fetch or auto-create strategy document

**Files:**
- Create: `api/routes/playbook_routes.py`
- Modify: `api/__init__.py` (register blueprint)
- Test: `tests/unit/test_playbook_api.py`

**Step 1: Write the failing test**

Create `tests/unit/test_playbook_api.py`:

```python
"""Tests for Playbook API endpoints."""
import pytest


def auth_header(client, email="admin@test.com", password="testpass123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestGetPlaybook:
    """GET /api/playbook"""

    def test_auto_creates_document(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "draft"
        assert data["version"] == 1
        assert "id" in data

    def test_returns_existing_document(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content={"type": "doc", "content": [{"type": "heading", "content": [{"type": "text", "text": "ICP"}]}]},
            status="active",
            version=3,
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.get("/api/playbook", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "active"
        assert data["version"] == 3

    def test_tenant_isolation(self, client, seed_tenant, seed_super_admin, db):
        from api.models import Tenant, StrategyDocument
        headers = auth_header(client)

        other = Tenant(name="Other", slug="other-corp", is_active=True)
        db.session.add(other)
        db.session.commit()

        doc = StrategyDocument(tenant_id=other.id, content={"secret": True})
        db.session.add(doc)
        db.session.commit()

        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook", headers=headers)
        data = resp.get_json()
        assert data.get("content") != {"secret": True}

    def test_requires_auth(self, client, seed_tenant):
        resp = client.get("/api/playbook", headers={"X-Namespace": seed_tenant.slug})
        assert resp.status_code == 401
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py -v`
Expected: FAIL (404 — route not registered)

**Step 3: Implement the route**

Create `api/routes/playbook_routes.py`:

```python
"""Playbook (GTM Strategy) API routes."""
from flask import Blueprint, jsonify, request
from ..auth import require_auth, resolve_tenant
from ..models import StrategyDocument, db

bp = Blueprint("playbook", __name__)


@bp.route("/api/playbook", methods=["GET"])
@require_auth
def get_playbook():
    """Get strategy document for current namespace. Auto-creates if missing."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        doc = StrategyDocument(tenant_id=tenant_id, status="draft")
        db.session.add(doc)
        db.session.commit()

    return jsonify(doc.to_dict()), 200
```

Register the blueprint in `api/__init__.py` — find the section where other blueprints are registered (look for `app.register_blueprint`) and add:

```python
from .routes.playbook_routes import bp as playbook_bp
app.register_blueprint(playbook_bp)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add api/routes/playbook_routes.py api/__init__.py tests/unit/test_playbook_api.py
git commit -m "feat(playbook): add GET /api/playbook with auto-create"
```

---

### Task 4: PUT /api/playbook — save with optimistic locking

**Files:**
- Modify: `api/routes/playbook_routes.py`
- Test: `tests/unit/test_playbook_api.py` (add to existing)

**Step 1: Write the failing test**

Add to `tests/unit/test_playbook_api.py`:

```python
class TestUpdatePlaybook:
    """PUT /api/playbook"""

    def test_save_document(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(tenant_id=seed_tenant.id, version=1)
        db.session.add(doc)
        db.session.commit()

        resp = client.put("/api/playbook", json={
            "content": {"type": "doc", "content": [{"type": "paragraph"}]},
            "version": 1,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == 2

    def test_optimistic_lock_conflict(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(tenant_id=seed_tenant.id, version=3)
        db.session.add(doc)
        db.session.commit()

        resp = client.put("/api/playbook", json={
            "content": {"type": "doc"},
            "version": 1,
        }, headers=headers)
        assert resp.status_code == 409
        data = resp.get_json()
        assert "conflict" in data["error"].lower()

    def test_version_required(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc)
        db.session.commit()

        resp = client.put("/api/playbook", json={
            "content": {"type": "doc"},
        }, headers=headers)
        assert resp.status_code == 400
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py::TestUpdatePlaybook -v`
Expected: FAIL (405 Method Not Allowed — PUT not implemented)

**Step 3: Implement PUT endpoint**

Add to `api/routes/playbook_routes.py`:

```python
@bp.route("/api/playbook", methods=["PUT"])
@require_auth
def update_playbook():
    """Save strategy document with optimistic locking."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    if "version" not in data:
        return jsonify({"error": "version is required"}), 400

    content = data.get("content", {})
    version = data["version"]
    status = data.get("status")

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    if doc.version != version:
        return jsonify({
            "error": "Conflict: document was edited by someone else",
            "current_version": doc.version,
            "updated_by": doc.updated_by,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }), 409

    doc.content = content
    doc.version = doc.version + 1
    doc.updated_by = getattr(request, "user_id", None)
    if status:
        doc.status = status

    db.session.commit()
    return jsonify(doc.to_dict()), 200
```

**Step 4: Run tests**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add api/routes/playbook_routes.py tests/unit/test_playbook_api.py
git commit -m "feat(playbook): add PUT /api/playbook with optimistic locking"
```

---

### Task 5: Chat history endpoints — GET + POST /api/playbook/chat

**Files:**
- Modify: `api/routes/playbook_routes.py`
- Test: `tests/unit/test_playbook_api.py` (add to existing)

**Step 1: Write the failing test**

Add to `tests/unit/test_playbook_api.py`:

```python
class TestPlaybookChat:
    """GET/POST /api/playbook/chat"""

    def _setup_doc(self, db, tenant_id):
        from api.models import StrategyDocument
        doc = StrategyDocument(tenant_id=tenant_id)
        db.session.add(doc)
        db.session.commit()
        return doc

    def test_get_empty_chat(self, client, seed_tenant, seed_super_admin, db):
        self._setup_doc(db, seed_tenant.id)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook/chat", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["messages"] == []

    def test_post_user_message(self, client, seed_tenant, seed_super_admin, db):
        self._setup_doc(db, seed_tenant.id)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/playbook/chat", json={
            "content": "Help me define my ICP",
            "stream": False,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["role"] == "assistant"
        assert len(data["content"]) > 0

    def test_chat_history_ordered(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyChatMessage
        doc = self._setup_doc(db, seed_tenant.id)
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        for i, (role, text) in enumerate([("user", "Q1"), ("assistant", "A1"), ("user", "Q2")]):
            msg = StrategyChatMessage(
                tenant_id=seed_tenant.id,
                document_id=doc.id,
                role=role,
                content=text,
            )
            db.session.add(msg)
        db.session.commit()

        resp = client.get("/api/playbook/chat", headers=headers)
        data = resp.get_json()
        assert len(data["messages"]) == 3
        assert [m["content"] for m in data["messages"]] == ["Q1", "A1", "Q2"]
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py::TestPlaybookChat -v`
Expected: FAIL (404)

**Step 3: Implement chat endpoints**

Add to `api/routes/playbook_routes.py`:

```python
from ..models import StrategyDocument, StrategyChatMessage, db

@bp.route("/api/playbook/chat", methods=["GET"])
@require_auth
def get_chat_history():
    """Get chat history for current namespace's strategy document."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"messages": []}), 200

    messages = (
        StrategyChatMessage.query
        .filter_by(document_id=doc.id)
        .order_by(StrategyChatMessage.created_at.asc())
        .all()
    )
    return jsonify({"messages": [m.to_dict() for m in messages]}), 200


@bp.route("/api/playbook/chat", methods=["POST"])
@require_auth
def post_chat_message():
    """Send a message and get AI response. Non-streaming for now (Task 7 adds SSE)."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        doc = StrategyDocument(tenant_id=tenant_id)
        db.session.add(doc)
        db.session.commit()

    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    # Save user message
    user_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="user",
        content=content,
        created_by=getattr(request, "user_id", None),
    )
    db.session.add(user_msg)
    db.session.commit()

    # Build context and call LLM (placeholder — Task 7 implements full LLM integration)
    ai_content = _generate_response(doc, content, tenant_id)

    # Save assistant message
    assistant_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="assistant",
        content=ai_content,
        metadata={},
    )
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify(assistant_msg.to_dict()), 200


def _generate_response(doc, user_message, tenant_id):
    """Placeholder LLM call. Task 7 replaces with real Anthropic streaming."""
    return f"[Placeholder] I received your message about your strategy. This will be replaced with Claude Opus 4.6 in Task 7."
```

**Step 4: Run tests**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add api/routes/playbook_routes.py tests/unit/test_playbook_api.py
git commit -m "feat(playbook): add chat history GET/POST endpoints"
```

---

## Phase 3: Anthropic Streaming + SSE

### Task 6: Add streaming support to AnthropicClient

**Files:**
- Modify: `api/services/anthropic_client.py`
- Test: `tests/unit/test_anthropic_streaming.py`

**Step 1: Write the failing test**

Create `tests/unit/test_anthropic_streaming.py`:

```python
"""Tests for AnthropicClient streaming support."""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestAnthropicStreaming:

    def test_stream_query_yields_chunks(self, app):
        from api.services.anthropic_client import AnthropicClient

        # Mock the requests.post to return a streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'event: content_block_delta',
            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}',
            b'',
            b'event: content_block_delta',
            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}',
            b'',
            b'event: message_delta',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}',
            b'',
            b'event: message_start',
            b'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}',
        ]
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with app.app_context():
            client = AnthropicClient(api_key="test-key")
            with patch("requests.post", return_value=mock_response):
                chunks = list(client.stream_query(
                    system_prompt="You are helpful",
                    messages=[{"role": "user", "content": "Hi"}],
                ))

        text_chunks = [c for c in chunks if c["type"] == "text"]
        assert len(text_chunks) == 2
        assert text_chunks[0]["text"] == "Hello"
        assert text_chunks[1]["text"] == " world"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_anthropic_streaming.py -v`
Expected: FAIL (stream_query not defined)

**Step 3: Add stream_query method to AnthropicClient**

Add to `api/services/anthropic_client.py` — add a `stream_query` method to the `AnthropicClient` class:

```python
def stream_query(self, system_prompt, messages, model=None, max_tokens=4096, temperature=0.3):
    """Stream a response from the Anthropic Messages API. Yields dicts with type and content."""
    payload = {
        "model": model or self.default_model,
        "system": system_prompt,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    headers = {
        "x-api-key": self.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        f"{self.base_url}/v1/messages",
        headers=headers,
        json=payload,
        stream=True,
        timeout=self.timeout,
    )
    resp.raise_for_status()

    input_tokens = 0
    output_tokens = 0

    for line in resp.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8") if isinstance(line, bytes) else line
        if line_str.startswith("data: "):
            data = json.loads(line_str[6:])
            event_type = data.get("type", "")

            if event_type == "message_start":
                usage = data.get("message", {}).get("usage", {})
                input_tokens = usage.get("input_tokens", 0)

            elif event_type == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    yield {"type": "text", "text": delta["text"]}

            elif event_type == "message_delta":
                usage = data.get("usage", {})
                output_tokens = usage.get("output_tokens", 0)

    # Yield final usage summary
    model_used = model or self.default_model
    pricing = self.MODEL_PRICING.get(model_used, {"input_per_m": 0, "output_per_m": 0})
    cost = (input_tokens * pricing["input_per_m"] + output_tokens * pricing["output_per_m"]) / 1_000_000
    yield {
        "type": "done",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "model": model_used,
    }
```

Also add Opus 4.6 pricing to `MODEL_PRICING`:
```python
"claude-opus-4-6":              {"input_per_m": 15.0, "output_per_m": 75.0},
```

**Step 4: Run tests**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_anthropic_streaming.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add api/services/anthropic_client.py tests/unit/test_anthropic_streaming.py
git commit -m "feat(playbook): add streaming support to AnthropicClient"
```

---

### Task 7: Wire LLM into chat endpoint with SSE streaming

**Files:**
- Modify: `api/routes/playbook_routes.py`
- Create: `api/services/playbook_service.py` (strategy system prompt + context builder)
- Test: `tests/unit/test_playbook_api.py` (update chat test)

**Step 1: Create playbook service with system prompt and context builder**

Create `api/services/playbook_service.py`:

```python
"""Playbook strategy service — LLM context building and system prompts."""
import json

STRATEGY_SYSTEM_PROMPT = """You are an expert GTM (Go-To-Market) strategy consultant. You have deeply researched the user's company and are helping them create a comprehensive outreach strategy.

Your role:
- Ask targeted clarifying questions about things you CANNOT infer from the company research (buyer persona preferences, deal size, sales cycle, internal priorities)
- Generate specific, actionable strategy sections based on research data + user answers
- When suggesting edits to the strategy document, be specific about which section to update
- Use data from the company research to back up your recommendations

Strategy sections you help create:
1. Executive Summary
2. Ideal Customer Profile (ICP) — industries, company size, geography, tech signals, triggers, disqualifiers
3. Buyer Personas — title patterns, pain points, goals, objections
4. Value Proposition — core value prop, differentiators, proof points
5. Competitive Positioning — competitors, advantages, landmines
6. Channel Strategy — primary/secondary channels, cadence, sequence
7. Messaging Framework — themes, angles, CTAs, tone
8. Success Metrics — reply rate, meeting rate, pipeline targets, timeline

Best practices you enforce:
- ICP must be specific enough to disqualify, not just describe
- Personas need real title patterns, not vague roles
- Value props must reference specific customer pain, not features
- Metrics must be measurable with specific targets and timelines
- Channel choice must match buyer behavior, not seller preference

Be conversational but substantive. Ask one question at a time. After gathering enough context (usually 3-5 questions), offer to generate the full strategy draft.

Current strategy document:
{document_content}

Company research data:
{enrichment_data}
"""


def build_chat_context(doc, tenant_id):
    """Build the system prompt with current document and enrichment data."""
    from ..models import Company, CompanyEnrichmentL1, CompanyEnrichmentL2

    # Get self-enrichment data
    enrichment_data = "No company research available yet."
    if doc.enrichment_id:
        company = Company.query.get(doc.enrichment_id)
        if company:
            parts = [f"Company: {company.name}", f"Domain: {company.domain}"]
            l1 = CompanyEnrichmentL1.query.get(company.id)
            if l1:
                parts.append(f"L1 Research: {json.dumps({k: v for k, v in l1.to_dict().items() if v}, default=str)}")
            l2 = CompanyEnrichmentL2.query.get(company.id)
            if l2:
                parts.append(f"L2 Research: {json.dumps({k: v for k, v in l2.to_dict().items() if v}, default=str)}")
            enrichment_data = "\n".join(parts)

    doc_content = json.dumps(doc.content, default=str) if doc.content else "Empty — no strategy drafted yet."

    return STRATEGY_SYSTEM_PROMPT.format(
        document_content=doc_content,
        enrichment_data=enrichment_data,
    )
```

**Step 2: Update chat POST to use real LLM with SSE streaming**

Replace the `_generate_response` placeholder and the `post_chat_message` function in `api/routes/playbook_routes.py`:

```python
import json
import os
from flask import Response, stream_with_context
from ..services.anthropic_client import AnthropicClient
from ..services.playbook_service import build_chat_context

def _get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return AnthropicClient(api_key=api_key, default_model="claude-opus-4-6")


@bp.route("/api/playbook/chat", methods=["POST"])
@require_auth
def post_chat_message():
    """Send a message and get AI response. Supports SSE streaming."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        doc = StrategyDocument(tenant_id=tenant_id)
        db.session.add(doc)
        db.session.commit()

    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    stream = data.get("stream", True)

    # Save user message
    user_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="user",
        content=content,
        created_by=getattr(request, "user_id", None),
    )
    db.session.add(user_msg)
    db.session.commit()

    # Build conversation history
    history = (
        StrategyChatMessage.query
        .filter_by(document_id=doc.id)
        .order_by(StrategyChatMessage.created_at.asc())
        .all()
    )
    messages = [{"role": m.role, "content": m.content} for m in history if m.role in ("user", "assistant")]

    system_prompt = build_chat_context(doc, tenant_id)

    if not stream:
        # Non-streaming (for tests)
        client = _get_anthropic_client()
        resp = client.query(system_prompt, content, model="claude-opus-4-6", max_tokens=4096)
        assistant_msg = StrategyChatMessage(
            tenant_id=tenant_id,
            document_id=doc.id,
            role="assistant",
            content=resp.content,
            metadata={"model": resp.model, "input_tokens": resp.input_tokens,
                       "output_tokens": resp.output_tokens, "cost_usd": float(resp.cost_usd)},
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify(assistant_msg.to_dict()), 200

    # SSE streaming
    def generate():
        client = _get_anthropic_client()
        full_text = []
        final_meta = {}

        for chunk in client.stream_query(system_prompt, messages, model="claude-opus-4-6", max_tokens=4096):
            if chunk["type"] == "text":
                full_text.append(chunk["text"])
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk["type"] == "done":
                final_meta = chunk
                yield f"data: {json.dumps(chunk)}\n\n"

        # Save complete assistant message
        assistant_msg = StrategyChatMessage(
            tenant_id=tenant_id,
            document_id=doc.id,
            role="assistant",
            content="".join(full_text),
            metadata=final_meta,
        )
        db.session.add(assistant_msg)
        db.session.commit()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**Step 3: Update the test for non-streaming mode**

The existing `test_post_user_message` already passes `stream: False`, so it should work with the new implementation. You may need to mock the AnthropicClient for tests:

Add to `tests/unit/test_playbook_api.py` at the top:
```python
from unittest.mock import patch, MagicMock
```

Update `test_post_user_message` to mock the Anthropic call:
```python
def test_post_user_message(self, client, seed_tenant, seed_super_admin, db):
    self._setup_doc(db, seed_tenant.id)
    headers = auth_header(client)
    headers["X-Namespace"] = seed_tenant.slug

    mock_resp = MagicMock()
    mock_resp.content = "Based on your company research, I recommend focusing on mid-market SaaS."
    mock_resp.model = "claude-opus-4-6"
    mock_resp.input_tokens = 100
    mock_resp.output_tokens = 50
    mock_resp.cost_usd = 0.005

    with patch("api.routes.playbook_routes._get_anthropic_client") as mock_client:
        mock_client.return_value.query.return_value = mock_resp
        resp = client.post("/api/playbook/chat", json={
            "content": "Help me define my ICP",
            "stream": False,
        }, headers=headers)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["role"] == "assistant"
    assert "mid-market SaaS" in data["content"]
```

**Step 4: Run tests**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add api/routes/playbook_routes.py api/services/playbook_service.py tests/unit/test_playbook_api.py
git commit -m "feat(playbook): wire Claude Opus 4.6 into chat with SSE streaming"
```

---

### Task 8: POST /api/playbook/extract — strategy data extraction

**Files:**
- Modify: `api/routes/playbook_routes.py`
- Modify: `api/services/playbook_service.py`
- Test: `tests/unit/test_playbook_api.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_playbook_api.py`:

```python
class TestPlaybookExtraction:
    """POST /api/playbook/extract"""

    def test_extract_from_document(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content={"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Our ICP targets SaaS companies with 50-500 employees in DACH"}]}]},
        )
        db.session.add(doc)
        db.session.commit()

        mock_extraction = {
            "icp": {"industries": ["SaaS"], "company_size": {"min": 50, "max": 500}, "geographies": ["DACH"]},
            "personas": [],
            "messaging": {"tone": "consultative"},
            "channels": {"primary": "email"},
            "metrics": {"reply_rate_target": 0.15},
        }
        mock_resp = MagicMock()
        mock_resp.content = json.dumps(mock_extraction)
        mock_resp.model = "claude-opus-4-6"
        mock_resp.input_tokens = 200
        mock_resp.output_tokens = 100
        mock_resp.cost_usd = 0.01

        with patch("api.routes.playbook_routes._get_anthropic_client") as mock_client:
            mock_client.return_value.query.return_value = mock_resp
            resp = client.post("/api/playbook/extract", headers=headers)

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["extracted_data"]["icp"]["industries"] == ["SaaS"]

    def test_extract_requires_document(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/playbook/extract", headers=headers)
        assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py::TestPlaybookExtraction -v`
Expected: FAIL

**Step 3: Implement extraction endpoint**

Add extraction prompt to `api/services/playbook_service.py`:

```python
EXTRACTION_PROMPT = """Extract structured data from this GTM strategy document. Return ONLY valid JSON matching this exact schema (no markdown, no explanation):

{
  "icp": {
    "industries": ["string"],
    "company_size": {"min": number, "max": number},
    "geographies": ["string"],
    "tech_signals": ["string"],
    "triggers": ["string"],
    "disqualifiers": ["string"]
  },
  "personas": [
    {"title_patterns": ["string"], "pain_points": ["string"], "goals": ["string"]}
  ],
  "messaging": {
    "tone": "string",
    "themes": ["string"],
    "angles": ["string"],
    "proof_points": ["string"]
  },
  "channels": {
    "primary": "string",
    "secondary": ["string"],
    "cadence": "string"
  },
  "metrics": {
    "reply_rate_target": number,
    "meeting_rate_target": number,
    "pipeline_goal_eur": number,
    "timeline_months": number
  }
}

If a field cannot be determined from the document, use null for that field. Infer reasonable defaults from context when possible.

Strategy document:
{document_content}
"""
```

Add extraction route to `api/routes/playbook_routes.py`:

```python
from ..services.playbook_service import build_chat_context, EXTRACTION_PROMPT

@bp.route("/api/playbook/extract", methods=["POST"])
@require_auth
def extract_strategy():
    """Extract structured data from the strategy document via LLM."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    doc_content = json.dumps(doc.content, default=str)
    prompt = EXTRACTION_PROMPT.format(document_content=doc_content)

    client = _get_anthropic_client()
    resp = client.query(
        system_prompt="You are a data extraction assistant. Return only valid JSON.",
        user_prompt=prompt,
        model="claude-opus-4-6",
        max_tokens=2048,
        temperature=0.0,
    )

    try:
        extracted = json.loads(resp.content)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse extraction result"}), 500

    doc.extracted_data = extracted
    db.session.commit()

    return jsonify(doc.to_dict()), 200
```

**Step 4: Run tests**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add api/routes/playbook_routes.py api/services/playbook_service.py tests/unit/test_playbook_api.py
git commit -m "feat(playbook): add strategy extraction endpoint"
```

---

## Phase 4: Frontend — Tiptap Editor

### Task 9: Install Tiptap dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install Tiptap packages**

Run: `cd /Users/michal/git/leadgen-pipeline/frontend && npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-placeholder @tiptap/extension-table @tiptap/extension-table-row @tiptap/extension-table-cell @tiptap/extension-table-header @tiptap/extension-task-list @tiptap/extension-task-item @tiptap/extension-highlight @tiptap/pm`

**Step 2: Verify install**

Run: `cd /Users/michal/git/leadgen-pipeline/frontend && node -e "require('@tiptap/react'); console.log('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add Tiptap v2 editor dependencies"
```

---

### Task 10: Create StrategyEditor component

**Files:**
- Create: `frontend/src/components/playbook/StrategyEditor.tsx`
- Create: `frontend/src/components/playbook/strategy-template.ts`

**Step 1: Create the strategy template (default document skeleton)**

Create `frontend/src/components/playbook/strategy-template.ts`:

```typescript
/**
 * Default strategy document template shown to new users.
 * Each section maps to a key extraction area.
 */
export const STRATEGY_TEMPLATE = {
  type: 'doc',
  content: [
    {
      type: 'heading',
      attrs: { level: 1 },
      content: [{ type: 'text', text: 'GTM Strategy' }],
    },
    {
      type: 'heading',
      attrs: { level: 2 },
      content: [{ type: 'text', text: 'Executive Summary' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'Describe your company, market position, and strategic thesis for this outreach campaign.' }],
    },
    {
      type: 'heading',
      attrs: { level: 2 },
      content: [{ type: 'text', text: 'Ideal Customer Profile (ICP)' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'Define your target companies: industry, size (employee count / revenue), geography, technology signals, buying triggers, and disqualifiers.' }],
    },
    {
      type: 'heading',
      attrs: { level: 2 },
      content: [{ type: 'text', text: 'Buyer Personas' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'List 2-3 personas with job title patterns, key pain points, goals, and common objections.' }],
    },
    {
      type: 'heading',
      attrs: { level: 2 },
      content: [{ type: 'text', text: 'Value Proposition' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'Your core value proposition, differentiators vs. competitors, and proof points for each persona.' }],
    },
    {
      type: 'heading',
      attrs: { level: 2 },
      content: [{ type: 'text', text: 'Competitive Positioning' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'Key competitors, your advantages, and positioning landmines to avoid.' }],
    },
    {
      type: 'heading',
      attrs: { level: 2 },
      content: [{ type: 'text', text: 'Channel Strategy' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'Primary and secondary outreach channels, cadence/sequence logic, and rationale based on buyer behavior.' }],
    },
    {
      type: 'heading',
      attrs: { level: 2 },
      content: [{ type: 'text', text: 'Messaging Framework' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'Key themes, subject line angles, CTA patterns, and tone guidelines.' }],
    },
    {
      type: 'heading',
      attrs: { level: 2 },
      content: [{ type: 'text', text: 'Success Metrics' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'Pipeline targets (EUR), reply rate goals, meeting conversion benchmarks, and campaign timeline.' }],
    },
  ],
}
```

**Step 2: Create the StrategyEditor component**

Create `frontend/src/components/playbook/StrategyEditor.tsx`:

```typescript
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Table from '@tiptap/extension-table'
import TableRow from '@tiptap/extension-table-row'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import Highlight from '@tiptap/extension-highlight'
import { useCallback, useEffect } from 'react'
import type { JSONContent } from '@tiptap/react'

interface StrategyEditorProps {
  content: JSONContent
  onChange: (content: JSONContent) => void
  editable?: boolean
}

export function StrategyEditor({ content, onChange, editable = true }: StrategyEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder: 'Start writing your strategy...',
      }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      TaskList,
      TaskItem.configure({ nested: true }),
      Highlight,
    ],
    content,
    editable,
    onUpdate: ({ editor }) => {
      onChange(editor.getJSON())
    },
  })

  // Sync external content changes (e.g., from AI applying edits)
  useEffect(() => {
    if (editor && content) {
      const currentJson = JSON.stringify(editor.getJSON())
      const newJson = JSON.stringify(content)
      if (currentJson !== newJson) {
        editor.commands.setContent(content)
      }
    }
  }, [editor, content])

  const insertTable = useCallback(() => {
    editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
  }, [editor])

  if (!editor) return null

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-neutral-200 bg-neutral-50 text-sm flex-shrink-0">
        <button
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          className={`px-2 py-1 rounded ${editor.isActive('heading', { level: 2 }) ? 'bg-neutral-200' : 'hover:bg-neutral-100'}`}
        >
          H2
        </button>
        <button
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          className={`px-2 py-1 rounded ${editor.isActive('heading', { level: 3 }) ? 'bg-neutral-200' : 'hover:bg-neutral-100'}`}
        >
          H3
        </button>
        <span className="w-px h-5 bg-neutral-300 mx-1" />
        <button
          onClick={() => editor.chain().focus().toggleBold().run()}
          className={`px-2 py-1 rounded font-bold ${editor.isActive('bold') ? 'bg-neutral-200' : 'hover:bg-neutral-100'}`}
        >
          B
        </button>
        <button
          onClick={() => editor.chain().focus().toggleItalic().run()}
          className={`px-2 py-1 rounded italic ${editor.isActive('italic') ? 'bg-neutral-200' : 'hover:bg-neutral-100'}`}
        >
          I
        </button>
        <button
          onClick={() => editor.chain().focus().toggleHighlight().run()}
          className={`px-2 py-1 rounded ${editor.isActive('highlight') ? 'bg-yellow-200' : 'hover:bg-neutral-100'}`}
        >
          Highlight
        </button>
        <span className="w-px h-5 bg-neutral-300 mx-1" />
        <button
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          className={`px-2 py-1 rounded ${editor.isActive('bulletList') ? 'bg-neutral-200' : 'hover:bg-neutral-100'}`}
        >
          List
        </button>
        <button
          onClick={() => editor.chain().focus().toggleTaskList().run()}
          className={`px-2 py-1 rounded ${editor.isActive('taskList') ? 'bg-neutral-200' : 'hover:bg-neutral-100'}`}
        >
          Tasks
        </button>
        <button
          onClick={insertTable}
          className="px-2 py-1 rounded hover:bg-neutral-100"
        >
          Table
        </button>
      </div>

      {/* Editor area */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <EditorContent
          editor={editor}
          className="prose prose-sm max-w-none focus:outline-none [&_.ProseMirror]:outline-none [&_.ProseMirror]:min-h-full"
        />
      </div>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/playbook/StrategyEditor.tsx frontend/src/components/playbook/strategy-template.ts
git commit -m "feat(playbook): add Tiptap StrategyEditor component with toolbar"
```

---

### Task 11: Create PlaybookChat component

**Files:**
- Create: `frontend/src/components/playbook/PlaybookChat.tsx`
- Create: `frontend/src/hooks/useSSE.ts`

**Step 1: Create SSE hook**

Create `frontend/src/hooks/useSSE.ts`:

```typescript
import { useCallback, useRef, useState } from 'react'
import { getAuthHeaders } from '../lib/auth'

interface SSEOptions {
  url: string
  body: Record<string, unknown>
  onChunk: (chunk: { type: string; text?: string; [key: string]: unknown }) => void
  onDone: (meta: Record<string, unknown>) => void
  onError: (error: Error) => void
}

export function useSSE() {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const startStream = useCallback(async ({ url, body, onChunk, onDone, onError }: SSEOptions) => {
    setIsStreaming(true)
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const headers = getAuthHeaders()
      const resp = await fetch(url, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'done') {
              onDone(data)
            } else {
              onChunk(data)
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onError(err as Error)
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [])

  const cancelStream = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { startStream, cancelStream, isStreaming }
}
```

**Step 2: Create PlaybookChat component**

Create `frontend/src/components/playbook/PlaybookChat.tsx`:

```typescript
import { useState, useRef, useEffect, useCallback } from 'react'
import { useSSE } from '../../hooks/useSSE'
import { getNamespaceFromPath } from '../../lib/auth'

interface ChatMessage {
  id?: string
  role: 'user' | 'assistant' | 'system'
  content: string
  metadata?: Record<string, unknown>
  created_at?: string
}

interface PlaybookChatProps {
  messages: ChatMessage[]
  onNewMessage: (msg: ChatMessage) => void
  onApplyEdit?: (content: string) => void
  apiBasePath: string
}

export function PlaybookChat({ messages, onNewMessage, onApplyEdit, apiBasePath }: PlaybookChatProps) {
  const [input, setInput] = useState('')
  const [streamingText, setStreamingText] = useState('')
  const { startStream, cancelStream, isStreaming } = useSSE()
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, streamingText])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isStreaming) return

    setInput('')
    onNewMessage({ role: 'user', content: text })
    setStreamingText('')

    await startStream({
      url: `${apiBasePath}/playbook/chat`,
      body: { content: text, stream: true },
      onChunk: (chunk) => {
        if (chunk.type === 'text' && chunk.text) {
          setStreamingText((prev) => prev + chunk.text)
        }
      },
      onDone: (meta) => {
        setStreamingText((prev) => {
          onNewMessage({ role: 'assistant', content: prev, metadata: meta })
          return ''
        })
      },
      onError: (err) => {
        onNewMessage({ role: 'assistant', content: `Error: ${err.message}` })
        setStreamingText('')
      },
    })
  }, [input, isStreaming, startStream, onNewMessage, apiBasePath])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Chat header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex-shrink-0">
        <h3 className="text-sm font-semibold text-neutral-700">Strategy Assistant</h3>
        <p className="text-xs text-neutral-500">AI-powered GTM strategy co-creation</p>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={msg.id || i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white'
                : 'bg-neutral-100 text-neutral-800'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}

        {/* Streaming indicator */}
        {streamingText && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-neutral-100 text-neutral-800 whitespace-pre-wrap">
              {streamingText}
              <span className="inline-block w-2 h-4 bg-neutral-400 animate-pulse ml-0.5" />
            </div>
          </div>
        )}

        {isStreaming && !streamingText && (
          <div className="flex justify-start">
            <div className="rounded-lg px-3 py-2 text-sm bg-neutral-100 text-neutral-500">
              Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-neutral-200 flex-shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your strategy..."
            rows={1}
            className="flex-1 resize-none rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
          />
          <button
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium disabled:opacity-50 hover:bg-indigo-700 transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/playbook/PlaybookChat.tsx frontend/src/hooks/useSSE.ts
git commit -m "feat(playbook): add PlaybookChat component with SSE streaming"
```

---

### Task 12: Create usePlaybook query hooks

**Files:**
- Create: `frontend/src/api/queries/usePlaybook.ts`

**Step 1: Create the hooks file**

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'
import type { JSONContent } from '@tiptap/react'

// ── Types ──────────────────────

export interface StrategyDocument {
  id: string
  tenant_id: string
  content: JSONContent
  extracted_data: Record<string, unknown>
  status: 'draft' | 'active' | 'archived'
  version: number
  enrichment_id: string | null
  created_at: string
  updated_at: string
  updated_by: string | null
}

export interface ChatMessage {
  id: string
  document_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  metadata: Record<string, unknown>
  created_at: string
  created_by: string | null
}

interface ChatHistoryResponse {
  messages: ChatMessage[]
}

// ── Document hooks ──────────────────────

export function usePlaybookDocument() {
  return useQuery({
    queryKey: ['playbook', 'document'],
    queryFn: () => apiFetch<StrategyDocument>('/playbook'),
  })
}

export function useSavePlaybook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ content, version, status }: { content: JSONContent; version: number; status?: string }) =>
      apiFetch<StrategyDocument>('/playbook', {
        method: 'PUT',
        body: { content, version, status },
      }),
    onSuccess: (data) => {
      qc.setQueryData(['playbook', 'document'], data)
    },
  })
}

export function useExtractStrategy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<StrategyDocument>('/playbook/extract', { method: 'POST' }),
    onSuccess: (data) => {
      qc.setQueryData(['playbook', 'document'], data)
    },
  })
}

// ── Chat hooks ──────────────────────

export function usePlaybookChat() {
  return useQuery({
    queryKey: ['playbook', 'chat'],
    queryFn: () => apiFetch<ChatHistoryResponse>('/playbook/chat'),
  })
}

// ── Research hooks ──────────────────────

export function useTriggerResearch() {
  return useMutation({
    mutationFn: () => apiFetch<{ status: string }>('/playbook/research', { method: 'POST' }),
  })
}

export function useResearchStatus() {
  return useQuery({
    queryKey: ['playbook', 'research'],
    queryFn: () => apiFetch<{ status: string; company_name?: string }>('/playbook/research'),
    refetchInterval: (query) => {
      const data = query.state.data
      return data?.status === 'running' ? 5000 : false
    },
  })
}
```

**Step 2: Commit**

```bash
git add frontend/src/api/queries/usePlaybook.ts
git commit -m "feat(playbook): add TanStack Query hooks for playbook API"
```

---

## Phase 5: Frontend — Playbook Page

### Task 13: Create PlaybookPage and register route

**Files:**
- Create: `frontend/src/pages/playbook/PlaybookPage.tsx`
- Modify: `frontend/src/App.tsx` (add route)

**Step 1: Create the PlaybookPage**

Create `frontend/src/pages/playbook/PlaybookPage.tsx`:

```typescript
import { useState, useCallback, useRef, useMemo } from 'react'
import { StrategyEditor } from '../../components/playbook/StrategyEditor'
import { PlaybookChat } from '../../components/playbook/PlaybookChat'
import { usePlaybookDocument, useSavePlaybook, useExtractStrategy, usePlaybookChat } from '../../api/queries/usePlaybook'
import { useToast } from '../../components/ui/Toast'
import { STRATEGY_TEMPLATE } from '../../components/playbook/strategy-template'
import type { JSONContent } from '@tiptap/react'

export function PlaybookPage() {
  const { toast } = useToast()
  const { data: doc, isLoading: docLoading } = usePlaybookDocument()
  const { data: chatData } = usePlaybookChat()
  const saveMutation = useSavePlaybook()
  const extractMutation = useExtractStrategy()

  // Local editor content (optimistic)
  const [localContent, setLocalContent] = useState<JSONContent | null>(null)
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string; metadata?: Record<string, unknown> }>>([])
  const [isDirty, setIsDirty] = useState(false)
  const autoSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Merge server chat history with local messages
  const allMessages = useMemo(() => {
    const server = chatData?.messages || []
    return [...server, ...chatMessages]
  }, [chatData, chatMessages])

  // Content to show in editor
  const editorContent = useMemo(() => {
    if (localContent) return localContent
    if (doc?.content && Object.keys(doc.content).length > 0) return doc.content as JSONContent
    return STRATEGY_TEMPLATE as JSONContent
  }, [localContent, doc])

  const handleEditorChange = useCallback((content: JSONContent) => {
    setLocalContent(content)
    setIsDirty(true)

    // Auto-save after 30s idle
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current)
    autoSaveRef.current = setTimeout(() => {
      handleSave(content)
    }, 30_000)
  }, [doc])

  const handleSave = useCallback(async (content?: JSONContent) => {
    if (!doc) return
    const saveContent = content || localContent || doc.content

    try {
      await saveMutation.mutateAsync({
        content: saveContent as JSONContent,
        version: doc.version,
      })
      setIsDirty(false)
      toast('Strategy saved', 'success')

      // Trigger extraction in background
      extractMutation.mutate()
    } catch (err: unknown) {
      const error = err as { status?: number }
      if (error.status === 409) {
        toast('Conflict: someone else edited the strategy. Reload to see their changes.', 'error')
      } else {
        toast('Failed to save strategy', 'error')
      }
    }
  }, [doc, localContent, saveMutation, extractMutation, toast])

  const handleNewChatMessage = useCallback((msg: { role: 'user' | 'assistant'; content: string; metadata?: Record<string, unknown> }) => {
    setChatMessages((prev) => [...prev, msg])
  }, [])

  if (docLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-neutral-500">Loading strategy...</div>
      </div>
    )
  }

  const apiBase = '/api'

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-neutral-200 bg-white flex-shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-neutral-800">Playbook</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            doc?.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-neutral-100 text-neutral-500'
          }`}>
            {doc?.status || 'draft'}
          </span>
          {isDirty && <span className="text-xs text-neutral-400">Unsaved changes</span>}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleSave()}
            disabled={saveMutation.isPending || !isDirty}
            className="px-3 py-1.5 text-sm rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {saveMutation.isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Split pane */}
      <div className="flex flex-1 min-h-0">
        {/* Editor (left) */}
        <div className="flex-1 min-w-0 border-r border-neutral-200">
          <StrategyEditor
            content={editorContent}
            onChange={handleEditorChange}
          />
        </div>

        {/* Chat (right) */}
        <div className="w-96 flex-shrink-0">
          <PlaybookChat
            messages={allMessages}
            onNewMessage={handleNewChatMessage}
            apiBasePath={apiBase}
          />
        </div>
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-1.5 border-t border-neutral-200 bg-neutral-50 text-xs text-neutral-500 flex-shrink-0">
        <span>
          {doc?.status === 'active' ? 'Active strategy' : 'Draft'} &middot; v{doc?.version || 1}
        </span>
        <span>
          {doc?.updated_at ? `Last saved ${new Date(doc.updated_at).toLocaleString()}` : 'Not yet saved'}
          {doc?.updated_by ? ` by ${doc.updated_by}` : ''}
        </span>
      </div>
    </div>
  )
}
```

**Step 2: Register the route**

In `frontend/src/App.tsx`, find the route section with the `/playbook` placeholder and replace it:

```typescript
import { PlaybookPage } from './pages/playbook/PlaybookPage'

// In the routes (replace the existing placeholder):
<Route path="playbook" element={<PlaybookPage />} />
```

**Step 3: Commit**

```bash
git add frontend/src/pages/playbook/PlaybookPage.tsx frontend/src/App.tsx
git commit -m "feat(playbook): add PlaybookPage with split editor + chat layout"
```

---

## Phase 6: Self-Enrichment & Research Endpoints

### Task 14: Research trigger and status API

**Files:**
- Modify: `api/routes/playbook_routes.py`
- Test: `tests/unit/test_playbook_api.py`

**Step 1: Write failing tests**

Add to `tests/unit/test_playbook_api.py`:

```python
class TestPlaybookResearch:
    """POST/GET /api/playbook/research"""

    def test_trigger_research_creates_self_company(self, client, seed_tenant, seed_super_admin, db):
        from api.models import Tenant
        headers = auth_header(client)

        # Update tenant to have a domain
        tenant = db.session.get(Tenant, seed_tenant.id)
        tenant.domain = "testcorp.com"
        db.session.commit()

        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/research", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] in ("started", "already_exists")

    def test_get_research_status(self, client, seed_tenant, seed_super_admin, db):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook/research", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data

    def test_trigger_research_without_domain(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.post("/api/playbook/research", headers=headers)
        assert resp.status_code == 400
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py::TestPlaybookResearch -v`
Expected: FAIL

**Step 3: Implement research endpoints**

Add to `api/routes/playbook_routes.py`:

```python
from ..models import StrategyDocument, StrategyChatMessage, Company, Tenant, db

@bp.route("/api/playbook/research", methods=["POST"])
@require_auth
def trigger_research():
    """Trigger self-enrichment for the namespace's own company."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant or not tenant.domain:
        return jsonify({"error": "Namespace has no domain configured"}), 400

    # Check if self-company already exists
    self_company = Company.query.filter_by(tenant_id=tenant_id, is_self=True).first()
    if self_company:
        return jsonify({"status": "already_exists", "company_id": self_company.id, "company_name": self_company.name}), 200

    # Create self-company record
    self_company = Company(
        tenant_id=tenant_id,
        name=tenant.name,
        domain=tenant.domain,
        is_self=True,
        status="new",
    )
    db.session.add(self_company)
    db.session.commit()

    # Link to strategy document
    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if doc:
        doc.enrichment_id = self_company.id
        db.session.commit()

    # TODO: Trigger L1→L2 enrichment pipeline via n8n webhook
    # For now, just create the company record

    return jsonify({"status": "started", "company_id": self_company.id}), 200


@bp.route("/api/playbook/research", methods=["GET"])
@require_auth
def get_research_status():
    """Check self-enrichment status."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    self_company = Company.query.filter_by(tenant_id=tenant_id, is_self=True).first()
    if not self_company:
        return jsonify({"status": "not_started"}), 200

    # Check enrichment status based on company fields
    from ..models import CompanyEnrichmentL1, CompanyEnrichmentL2
    l1 = CompanyEnrichmentL1.query.get(self_company.id)
    l2 = CompanyEnrichmentL2.query.get(self_company.id)

    if l2:
        status = "complete"
    elif l1:
        status = "l1_complete"
    else:
        status = "pending"

    return jsonify({
        "status": status,
        "company_id": self_company.id,
        "company_name": self_company.name,
    }), 200
```

**Step 4: Run tests**

Run: `cd /Users/michal/git/leadgen-pipeline && python -m pytest tests/unit/test_playbook_api.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add api/routes/playbook_routes.py tests/unit/test_playbook_api.py
git commit -m "feat(playbook): add self-enrichment research trigger and status endpoints"
```

---

## Phase 7: Integration & Polish

### Task 15: Add `domain` field to Tenant model if missing

Check if `Tenant` model has a `domain` field. If not, add it via migration and model update. The research endpoint depends on `tenant.domain`.

**Files:**
- Create: `migrations/030_tenant_domain.sql` (if needed)
- Modify: `api/models.py` (if needed)

This is a conditional task — check first, only implement if `domain` doesn't exist on Tenant.

### Task 16: E2E smoke test

**Files:**
- Create: `tests/e2e/test_playbook.spec.ts`

Write a Playwright test that:
1. Logs in
2. Navigates to `/:namespace/playbook`
3. Verifies the editor and chat panel are visible
4. Types a message in the chat
5. Verifies a response appears

Follow existing Playwright patterns in `tests/e2e/`.

### Task 17: Run full test suite and lint

Run:
```bash
cd /Users/michal/git/leadgen-pipeline && make lint
cd /Users/michal/git/leadgen-pipeline && make test
```

Fix any lint errors or test failures before marking complete.

---

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| 1: Database & Models | 1-2 | Migration + SQLAlchemy models |
| 2: API Routes | 3-5 | GET/PUT playbook + chat endpoints |
| 3: Streaming | 6-8 | Anthropic SSE streaming + extraction |
| 4: Frontend Editor | 9-11 | Tiptap editor + chat components |
| 5: Frontend Page | 12-13 | Full PlaybookPage + route registration |
| 6: Self-Enrichment | 14-15 | Research trigger + status |
| 7: Integration | 16-17 | E2E test + full suite validation |

Total: **17 tasks**, approximately **17 commits**.
