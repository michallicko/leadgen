# Playbook Multi-Phase Feature: Implementation Backlog

**Date**: 2026-02-22
**Status**: Draft
**Depends on**: Existing Playbook v1 (strategy editor + chat, migration 029-030)

---

## Overview

Evolve the Playbook from a single-phase strategy editor into a multi-phase guided workflow:
**Strategy** (current) -> **Contacts** -> **Messages** -> **Campaign**.

Each phase builds on the previous, using extracted data to pre-populate and guide the next step. The chat assistant adapts its system prompt per phase, and a visual phase indicator shows progress.

---

## Bucket 1: Phase Infrastructure (Foundation)

Everything in this bucket must be completed before any other bucket can begin. These items establish the database schema, API contract, routing, and UI scaffolding that all subsequent phases depend on.

> **Note**: PB-035 through PB-037 supersede the old explicit save/extract pattern. Auto-save replaces the save button, real-time collaboration replaces version conflict detection, and intelligent auto-extraction replaces the manual extract button. These must land before the multi-phase work (PB-001+) since the editor UX they establish is foundational to every phase.

---

### PB-035: Auto-Save (Debounced)

**Description**: Replace the explicit save button with debounced auto-save that triggers 1-2 seconds after the user stops typing. Remove the version conflict detection UI — CRDT-based collaboration (PB-036) handles conflicts natively. This is a prerequisite for real-time collaboration and eliminates a class of "unsaved changes lost" bugs.

**Files to create/modify**:
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx` (or StrategyPanel after PB-009)
- Modify: `frontend/src/api/queries/usePlaybook.ts` (debounced mutation)
- Modify: `frontend/src/components/playbook/PlaybookTopBar.tsx` (remove save button, add save status indicator)

**Dependencies**: None (foundational UX change)

**Effort**: S

**Exact changes**:

In the editor component, replace the manual save handler with a debounced auto-save:

```tsx
// useAutoSave.ts — new hook
import { useRef, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'

export function useAutoSave(saveFn: (content: string) => Promise<void>, delayMs = 1500) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  const debouncedSave = useCallback((content: string) => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      setStatus('saving')
      try {
        await saveFn(content)
        setStatus('saved')
      } catch {
        setStatus('error')
      }
    }, delayMs)
  }, [saveFn, delayMs])

  return { debouncedSave, status }
}
```

Remove the Save button from PlaybookTopBar. Replace with a subtle status indicator: "Saving...", "Saved", or "Save failed — retrying".

**Acceptance criteria**:

- **Given** the user types in the editor, **When** they stop typing for 1.5s, **Then** the content is saved automatically without clicking any button.
- **Given** auto-save is in progress, **When** the user types again, **Then** the debounce timer resets and a new save is scheduled.
- **Given** the save succeeds, **When** the status indicator updates, **Then** it shows "Saved" briefly before fading.
- **Given** the save fails, **When** the status indicator updates, **Then** it shows "Save failed" and retries on the next edit.
- **Given** the old Save button, **When** this feature lands, **Then** the button is removed from the UI.

**Test cases**:

1. Type in the editor, wait 2s -> verify API save call was made.
2. Type continuously for 5s -> verify only one save call is made (after typing stops).
3. Simulate network error on save -> verify "Save failed" indicator appears.
4. Verify no Save button exists in the PlaybookTopBar.
5. Verify version conflict detection UI is removed.

---

### PB-036: Real-Time Collaboration (GDocs-style)

**Description**: Full cursor presence and live document sync using Yjs + Hocuspocus (Tiptap's native CRDT stack). Multiple users editing the same playbook simultaneously see each other's cursors, selections, and changes in real time. A WebSocket sync server manages document state. Backend persists the CRDT document state (binary Yjs update format), replacing the current `content` column approach for collaborative documents.

**Files to create/modify**:
- Create: `api/services/hocuspocus_server.py` (or separate Node.js service)
- Create: `frontend/src/hooks/useCollaboration.ts`
- Modify: `frontend/src/components/playbook/StrategyEditor.tsx` (Tiptap Collaboration + CollaborationCursor extensions)
- Modify: `api/models.py` (add `ydoc_state` BYTEA column to strategy_documents)
- Create: `migrations/034_ydoc_state.sql`

**Dependencies**: PB-035 (auto-save must be in place first; CRDT replaces the save mechanism)

**Effort**: L

**Exact changes**:

Database migration:
```sql
-- 034: Add CRDT document state for real-time collaboration
BEGIN;
ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS ydoc_state BYTEA;
COMMIT;
```

Frontend Tiptap setup:
```tsx
import { HocuspocusProvider } from '@hocuspocus/provider'
import Collaboration from '@tiptap/extension-collaboration'
import CollaborationCursor from '@tiptap/extension-collaboration-cursor'

const provider = new HocuspocusProvider({
  url: `wss://${window.location.host}/ws/collab`,
  name: `playbook-${documentId}`,
  token: jwtToken,
})

const editor = useEditor({
  extensions: [
    ...existingExtensions,
    Collaboration.configure({ document: provider.document }),
    CollaborationCursor.configure({
      provider,
      user: { name: currentUser.name, color: userColor },
    }),
  ],
})
```

**Acceptance criteria**:

- **Given** two users open the same playbook, **When** user A types, **Then** user B sees the change in real time (< 200ms latency).
- **Given** two users are editing, **When** user A moves their cursor, **Then** user B sees a colored cursor label with user A's name.
- **Given** both users edit the same paragraph simultaneously, **When** changes merge, **Then** no content is lost (CRDT conflict resolution).
- **Given** a user goes offline, **When** they reconnect, **Then** their local changes merge with the server state.
- **Given** the CRDT state is persisted, **When** all users close the document and one reopens it, **Then** the full content is restored from `ydoc_state`.

**Test cases**:

1. Two browser tabs editing same document -> verify real-time sync.
2. Disconnect one tab's WebSocket, type in both, reconnect -> verify merge without data loss.
3. Verify cursor presence shows correct user names and colors.
4. Close all tabs, reopen -> verify content matches last collaborative state.
5. Verify `ydoc_state` column is populated after collaborative editing session.

---

### PB-037: Intelligent Auto-Extraction

**Description**: Instead of requiring the user to click an "Extract" button, the system detects when meaningful edits have been made to the strategy document and re-extracts structured data (ICP, personas, value propositions) in the background. Tracks the document diff from the last extraction to determine if changes are significant enough to warrant re-extraction. Runs asynchronously without blocking the user.

**Files to create/modify**:
- Create: `api/services/extraction_trigger.py` (change detection + trigger logic)
- Modify: `api/services/playbook_service.py` (extract_structured_data gains diffing awareness)
- Modify: `api/routes/playbook_routes.py` (remove explicit extract endpoint, add background trigger on save)
- Modify: `frontend/src/components/playbook/PlaybookTopBar.tsx` (remove Extract button, add extraction status indicator)

**Dependencies**: PB-035 (needs stable auto-save state to diff against)

**Effort**: M

**Exact changes**:

Extraction trigger service:
```python
# api/services/extraction_trigger.py
import difflib

# Minimum change ratio to trigger re-extraction (0.0 to 1.0)
SIGNIFICANCE_THRESHOLD = 0.05  # 5% change from last extraction

def should_extract(current_content: str, last_extracted_content: str | None) -> bool:
    """Determine if content has changed enough to warrant re-extraction."""
    if not last_extracted_content:
        return bool(current_content and len(current_content.strip()) > 50)

    ratio = difflib.SequenceMatcher(None, last_extracted_content, current_content).ratio()
    change_ratio = 1.0 - ratio
    return change_ratio >= SIGNIFICANCE_THRESHOLD


def trigger_extraction_if_needed(doc_id: str, tenant_id: str):
    """Check if extraction is warranted and queue it as a background job."""
    doc = StrategyDocument.query.get(doc_id)
    if not doc:
        return

    if should_extract(doc.content, doc.last_extracted_content):
        # Queue background extraction (threading or Celery)
        import threading
        t = threading.Thread(target=_run_extraction, args=(doc_id, tenant_id))
        t.daemon = True
        t.start()
```

Add `last_extracted_content` column to track the content snapshot at last extraction time.

Wire into the auto-save endpoint: after every successful save, call `trigger_extraction_if_needed()`.

**Acceptance criteria**:

- **Given** the user makes substantial edits (>5% change), **When** auto-save fires, **Then** extraction runs in the background without any user action.
- **Given** the user makes trivial edits (fixing a typo), **When** auto-save fires, **Then** extraction does NOT re-run.
- **Given** extraction is running in the background, **When** the user continues editing, **Then** they are not blocked or interrupted.
- **Given** extraction completes, **When** the status indicator updates, **Then** it briefly shows "Data extracted" before fading.
- **Given** the old Extract button, **When** this feature lands, **Then** the button is removed from the UI.
- **Given** this is the first save (no prior extraction), **When** auto-save fires with >50 chars of content, **Then** extraction runs.

**Test cases**:

1. Save with 10% content change -> verify extraction triggers.
2. Save with 1% content change (typo fix) -> verify extraction does NOT trigger.
3. Save empty document -> verify extraction does NOT trigger.
4. First save with substantial content -> verify extraction triggers.
5. Verify extraction runs in background thread (does not block save response).
6. Verify `last_extracted_content` is updated after extraction completes.
7. Verify no Extract button exists in the PlaybookTopBar.

---

### PB-001: DB migration — add `phase` and `playbook_selections` to strategy_documents

**Description**: Add a `phase` column (VARCHAR, default `'strategy'`) and a `playbook_selections` column (JSONB, default `'{}'`) to the `strategy_documents` table. The `phase` tracks which step the user is on; `playbook_selections` stores per-phase structured choices (selected contact IDs, message configuration, campaign settings).

**Files to create/modify**:
- Create: `migrations/033_playbook_phases.sql`

**Dependencies**: None

**Effort**: S

**Exact changes**:

```sql
-- 033: Add multi-phase support to strategy_documents
--
-- phase: tracks current workflow step (strategy -> contacts -> messages -> campaign)
-- playbook_selections: JSONB store for per-phase structured data
--   e.g., { "contacts": { "selected_ids": [...], "filters": {...} },
--           "messages": { "config": {...} },
--           "campaign": { "settings": {...} } }

BEGIN;

ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS phase VARCHAR(20) NOT NULL DEFAULT 'strategy';

ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS playbook_selections JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
```

**Acceptance criteria**:

- **Given** the migration has been applied, **When** I query `strategy_documents`, **Then** every row has `phase = 'strategy'` and `playbook_selections = '{}'`.
- **Given** a new `strategy_documents` row is inserted without specifying `phase`, **When** I read it back, **Then** `phase` is `'strategy'`.
- **Given** `playbook_selections` is set to `{"contacts": {"selected_ids": ["uuid1"]}}`, **When** I query with `playbook_selections->'contacts'->'selected_ids'`, **Then** it returns the array.

**Test cases**:

1. Run migration on a DB with existing strategy_documents rows. Verify all rows have `phase = 'strategy'` and `playbook_selections = '{}'`.
2. Insert a new row with `phase = 'contacts'` and verify it persists.
3. Insert a new row without specifying `phase` and verify default is `'strategy'`.
4. Store nested JSONB in `playbook_selections` and query individual keys.
5. Verify the migration is idempotent (`IF NOT EXISTS`).

---

### PB-002: Model update — StrategyDocument gains `phase` and `playbook_selections`

**Description**: Add `phase` and `playbook_selections` columns to the `StrategyDocument` SQLAlchemy model in `api/models.py`. Update `to_dict()` to include both fields. Define the valid phase enum values as a module-level constant.

**Files to create/modify**:
- Modify: `api/models.py` (StrategyDocument class)
- Create: `tests/unit/test_playbook_phases.py`

**Dependencies**: PB-001

**Effort**: S

**Exact changes**:

Add to `api/models.py`, inside the `StrategyDocument` class (after the `objective` column):

```python
    phase = db.Column(
        db.String(20), nullable=False, server_default=db.text("'strategy'"), default="strategy"
    )
    playbook_selections = db.Column(
        JSONB, server_default=db.text("'{}'::jsonb"), nullable=False, default=dict
    )
```

Add a module-level constant above or near the class:

```python
PLAYBOOK_PHASES = ["strategy", "contacts", "messages", "campaign"]
```

Update `to_dict()` to include:

```python
    def to_dict(self):
        return {
            ...existing fields...
            "phase": self.phase,
            "playbook_selections": self.playbook_selections or {},
        }
```

**Acceptance criteria**:

- **Given** a StrategyDocument is created without specifying `phase`, **When** I call `to_dict()`, **Then** `phase` is `"strategy"` and `playbook_selections` is `{}`.
- **Given** a StrategyDocument with `phase="contacts"`, **When** serialized, **Then** `to_dict()["phase"]` equals `"contacts"`.
- **Given** `playbook_selections={"contacts": {"selected_ids": ["abc"]}}`, **When** serialized, **Then** the nested structure is preserved.

**Test cases**:

```python
class TestPlaybookPhases:
    def test_default_phase_is_strategy(self, app, db, seed_tenant):
        doc = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc)
        db.session.commit()
        assert doc.phase == "strategy"
        assert doc.playbook_selections == {}

    def test_phase_persists(self, app, db, seed_tenant):
        doc = StrategyDocument(tenant_id=seed_tenant.id, phase="contacts")
        db.session.add(doc)
        db.session.commit()
        fetched = db.session.get(StrategyDocument, doc.id)
        assert fetched.phase == "contacts"

    def test_playbook_selections_stores_json(self, app, db, seed_tenant):
        selections = {"contacts": {"selected_ids": ["id1", "id2"], "filters": {"industry": "SaaS"}}}
        doc = StrategyDocument(tenant_id=seed_tenant.id, playbook_selections=selections)
        db.session.add(doc)
        db.session.commit()
        fetched = db.session.get(StrategyDocument, doc.id)
        assert fetched.playbook_selections["contacts"]["selected_ids"] == ["id1", "id2"]

    def test_to_dict_includes_phase_fields(self, app, db, seed_tenant):
        doc = StrategyDocument(tenant_id=seed_tenant.id, phase="messages")
        db.session.add(doc)
        db.session.commit()
        d = doc.to_dict()
        assert d["phase"] == "messages"
        assert "playbook_selections" in d
```

---

### PB-003: API — `PUT /api/playbook/phase` endpoint with per-phase validation

**Description**: New endpoint to advance or navigate the playbook phase. Validates that forward transitions meet readiness gates (e.g., strategy -> contacts requires non-empty `extracted_data`). Backward navigation is always allowed. Stores the phase on the `StrategyDocument`.

**Files to create/modify**:
- Modify: `api/routes/playbook_routes.py`
- Modify: `tests/unit/test_playbook_api.py` (or `tests/unit/test_playbook_phases.py`)

**Dependencies**: PB-002

**Effort**: M

**Exact changes**:

Add to `api/routes/playbook_routes.py`:

```python
from ..models import PLAYBOOK_PHASES

@playbook_bp.route("/api/playbook/phase", methods=["PUT"])
@require_auth
def update_phase():
    """Advance or rewind the playbook phase.

    Forward transitions are gated:
      strategy -> contacts: requires non-empty extracted_data
      contacts -> messages: requires at least 1 selected contact
      messages -> campaign: requires at least 1 generated message

    Backward transitions are always allowed.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    target_phase = data.get("phase")
    if target_phase not in PLAYBOOK_PHASES:
        return jsonify({
            "error": "Invalid phase. Must be one of: {}".format(", ".join(PLAYBOOK_PHASES))
        }), 400

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    current_idx = PLAYBOOK_PHASES.index(doc.phase) if doc.phase in PLAYBOOK_PHASES else 0
    target_idx = PLAYBOOK_PHASES.index(target_phase)

    # Forward transition validation
    if target_idx > current_idx:
        error = _validate_phase_transition(doc, doc.phase, target_phase)
        if error:
            return jsonify({"error": error, "current_phase": doc.phase}), 422

    doc.phase = target_phase
    db.session.commit()

    return jsonify(doc.to_dict()), 200


def _validate_phase_transition(doc, current_phase, target_phase):
    """Validate that a forward phase transition is allowed.

    Returns an error message string if blocked, or None if allowed.
    """
    if target_phase == "contacts":
        # Must have extracted strategy data (ICP at minimum)
        extracted = doc.extracted_data or {}
        if not extracted.get("icp"):
            return "Strategy must have extracted ICP data before moving to Contacts. Save and extract first."
        return None

    if target_phase == "messages":
        # Must have selected contacts
        selections = doc.playbook_selections or {}
        contact_ids = selections.get("contacts", {}).get("selected_ids", [])
        if not contact_ids:
            return "Select at least one contact before moving to Messages."
        return None

    if target_phase == "campaign":
        # Must have generated messages (checked via DB)
        from ..models import Message
        selections = doc.playbook_selections or {}
        contact_ids = selections.get("contacts", {}).get("selected_ids", [])
        if not contact_ids:
            return "No contacts selected."
        msg_count = Message.query.filter(
            Message.tenant_id == doc.tenant_id,
            Message.contact_id.in_(contact_ids),
        ).count()
        if msg_count == 0:
            return "Generate messages for selected contacts before launching a campaign."
        return None

    return None
```

**Acceptance criteria**:

- **Given** a document in `strategy` phase with empty `extracted_data`, **When** I PUT `{"phase": "contacts"}`, **Then** I get 422 with an error about needing ICP data.
- **Given** a document in `strategy` phase with valid `extracted_data.icp`, **When** I PUT `{"phase": "contacts"}`, **Then** the phase updates to `"contacts"` and I get 200.
- **Given** a document in `messages` phase, **When** I PUT `{"phase": "strategy"}`, **Then** backward navigation succeeds with 200.
- **Given** an invalid phase value, **When** I PUT `{"phase": "invalid"}`, **Then** I get 400.

**Test cases**:

```python
class TestPlaybookPhaseTransition:
    def test_forward_blocked_without_extracted_data(self, client, seed_tenant, seed_super_admin, db):
        doc = StrategyDocument(tenant_id=seed_tenant.id, phase="strategy")
        db.session.add(doc); db.session.commit()
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.put("/api/playbook/phase", json={"phase": "contacts"}, headers=headers)
        assert resp.status_code == 422

    def test_forward_allowed_with_icp(self, client, seed_tenant, seed_super_admin, db):
        doc = StrategyDocument(
            tenant_id=seed_tenant.id, phase="strategy",
            extracted_data={"icp": {"industries": ["SaaS"]}}
        )
        db.session.add(doc); db.session.commit()
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.put("/api/playbook/phase", json={"phase": "contacts"}, headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["phase"] == "contacts"

    def test_backward_always_allowed(self, client, seed_tenant, seed_super_admin, db):
        doc = StrategyDocument(tenant_id=seed_tenant.id, phase="messages")
        db.session.add(doc); db.session.commit()
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.put("/api/playbook/phase", json={"phase": "strategy"}, headers=headers)
        assert resp.status_code == 200

    def test_invalid_phase_rejected(self, client, seed_tenant, seed_super_admin, db):
        doc = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc); db.session.commit()
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.put("/api/playbook/phase", json={"phase": "invalid"}, headers=headers)
        assert resp.status_code == 400
```

---

### PB-004: API — `POST /api/playbook/chat` gains `phase` parameter

**Description**: Extend the chat endpoint to accept an optional `phase` parameter in the request body. The system prompt is constructed using phase-specific instructions from `PHASE_INSTRUCTIONS` (PB-005). When `phase` is provided, it overrides the document's current phase for prompt construction only (does not change the document's phase).

**Files to create/modify**:
- Modify: `api/routes/playbook_routes.py` (post_chat_message function)

**Dependencies**: PB-005

**Effort**: S

**Exact changes**:

In `post_chat_message()`, after parsing `message_text`, add:

```python
    phase = data.get("phase") or doc.phase or "strategy"
```

Update the `build_system_prompt` call to pass `phase`:

```python
    system_prompt = build_system_prompt(tenant, doc, enrichment_data=enrichment_data, phase=phase)
```

**Acceptance criteria**:

- **Given** a chat request with `{"message": "...", "phase": "contacts"}`, **When** the system prompt is built, **Then** it includes contacts-phase instructions.
- **Given** a chat request without `phase`, **When** the system prompt is built, **Then** it uses the document's current `phase`.
- **Given** the document is in `strategy` phase but the request sends `phase: "contacts"`, **When** processed, **Then** the document's `phase` field is NOT changed.

**Test cases**:

1. POST chat with `phase: "contacts"` and verify system prompt includes contacts instructions (mock the LLM, inspect the prompt).
2. POST chat without `phase` and verify it defaults to the document's stored phase.
3. Verify the document's `phase` column is unchanged after the request.

---

### PB-005: Service — `PHASE_INSTRUCTIONS` dict with per-phase system prompt additions

**Description**: Add a `PHASE_INSTRUCTIONS` dictionary to `playbook_service.py` that maps each phase to additional system prompt text. Modify `build_system_prompt()` to accept an optional `phase` parameter and append the phase-specific instructions.

**Files to create/modify**:
- Modify: `api/services/playbook_service.py`
- Create: `tests/unit/test_playbook_phase_prompts.py`

**Dependencies**: PB-002

**Effort**: M

**Exact changes**:

Add to `api/services/playbook_service.py`:

```python
PHASE_INSTRUCTIONS = {
    "strategy": (
        "You are in the STRATEGY phase. Focus on helping the user define their "
        "GTM strategy: ICP, buyer personas, value proposition, competitive "
        "positioning, channel strategy, messaging framework, and success metrics.\n\n"
        "When the strategy feels specific enough (ICP has concrete disqualifiers, "
        "personas have real title patterns, metrics have numbers), suggest moving "
        "to the Contacts phase by saying: \"Your strategy looks ready. Want to "
        "move to the Contacts phase to select your target contacts?\""
    ),
    "contacts": (
        "You are in the CONTACTS phase. The user's ICP and personas have been "
        "defined. Help them select and filter contacts that match their strategy.\n\n"
        "Available ICP criteria from extracted data:\n{icp_summary}\n\n"
        "Guide the user to:\n"
        "- Review the pre-applied ICP filters\n"
        "- Adjust filters based on their priorities\n"
        "- Select specific contacts for outreach\n"
        "- Consider contact quality and engagement signals\n\n"
        "When contacts are selected, suggest moving to Messages phase."
    ),
    "messages": (
        "You are in the MESSAGES phase. The user has selected contacts and now "
        "needs to generate and review personalized outreach messages.\n\n"
        "Selected contacts: {contact_count}\n\n"
        "Help the user:\n"
        "- Review generated messages for quality and personalization\n"
        "- Adjust tone, length, and angle based on their preferences\n"
        "- Approve or regenerate individual messages\n"
        "- Ensure messaging aligns with the strategy's messaging framework\n\n"
        "When messages are reviewed, suggest launching the campaign."
    ),
    "campaign": (
        "You are in the CAMPAIGN phase. Messages have been reviewed and the user "
        "is ready to launch their outreach campaign.\n\n"
        "Help the user:\n"
        "- Configure campaign settings (channels, cadence, timing)\n"
        "- Review the final contact list and message assignments\n"
        "- Set expectations for response rates and follow-up\n"
        "- Launch the campaign or schedule it for later"
    ),
}
```

Modify `build_system_prompt()` signature and body:

```python
def build_system_prompt(tenant, document, enrichment_data=None, phase=None):
    """Build the system prompt. Appends phase-specific instructions when phase is given."""
    ...existing logic...

    # Append phase-specific instructions
    active_phase = phase or getattr(document, "phase", "strategy") or "strategy"
    phase_instructions = PHASE_INSTRUCTIONS.get(active_phase, "")

    if phase_instructions:
        # Interpolate phase-specific context variables
        selections = getattr(document, "playbook_selections", {}) or {}
        extracted = getattr(document, "extracted_data", {}) or {}

        format_vars = {
            "icp_summary": _format_icp_summary(extracted.get("icp", {})),
            "contact_count": len(selections.get("contacts", {}).get("selected_ids", [])),
        }
        try:
            phase_text = phase_instructions.format(**format_vars)
        except (KeyError, IndexError):
            phase_text = phase_instructions

        parts.extend(["", "--- Phase-Specific Instructions ---", phase_text])

    return "\n".join(parts)
```

Add a helper:

```python
def _format_icp_summary(icp):
    """Format extracted ICP data as a concise summary for the contacts phase prompt."""
    if not icp:
        return "No ICP criteria extracted yet."
    parts = []
    if icp.get("industries"):
        parts.append("Industries: {}".format(", ".join(icp["industries"])))
    if icp.get("company_size"):
        size = icp["company_size"]
        parts.append("Company size: {}-{} employees".format(size.get("min", "?"), size.get("max", "?")))
    if icp.get("geographies"):
        parts.append("Geographies: {}".format(", ".join(icp["geographies"])))
    if icp.get("triggers"):
        parts.append("Triggers: {}".format(", ".join(icp["triggers"])))
    if icp.get("disqualifiers"):
        parts.append("Disqualifiers: {}".format(", ".join(icp["disqualifiers"])))
    return "\n".join(parts) if parts else "No ICP criteria extracted yet."
```

**Acceptance criteria**:

- **Given** `build_system_prompt()` is called with `phase="strategy"`, **When** I inspect the output, **Then** it contains "STRATEGY phase" and the readiness suggestion.
- **Given** `phase="contacts"` with ICP extracted data, **When** the prompt is built, **Then** it contains the formatted ICP summary.
- **Given** `phase=None`, **When** the prompt is built, **Then** it defaults to the document's `phase` field.
- **Given** `phase="messages"` with 5 selected contacts, **When** the prompt is built, **Then** it says "Selected contacts: 5".

**Test cases**:

```python
class TestPhaseInstructions:
    def test_strategy_phase_prompt(self):
        prompt = build_system_prompt(mock_tenant, mock_doc, phase="strategy")
        assert "STRATEGY phase" in prompt
        assert "Contacts phase" in prompt

    def test_contacts_phase_includes_icp(self):
        mock_doc.extracted_data = {"icp": {"industries": ["SaaS", "FinTech"]}}
        prompt = build_system_prompt(mock_tenant, mock_doc, phase="contacts")
        assert "CONTACTS phase" in prompt
        assert "SaaS" in prompt

    def test_default_phase_from_document(self):
        mock_doc.phase = "messages"
        prompt = build_system_prompt(mock_tenant, mock_doc)
        assert "MESSAGES phase" in prompt
```

---

### PB-006: Frontend route — `playbook/:phase` with redirect

**Description**: Update the React router to use `playbook/:phase?` (optional phase parameter). When no phase is specified (`/playbook`), redirect to `/playbook/strategy`. The PlaybookPage reads the phase from the URL and passes it to child components.

**Files to create/modify**:
- Modify: `frontend/src/App.tsx` (route definition)
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx` (read phase from URL)

**Dependencies**: PB-003 (API must support phase)

**Effort**: S

**Exact changes**:

In `App.tsx`, replace:
```tsx
<Route path="playbook" element={<PlaybookPage />} />
```
with:
```tsx
<Route path="playbook" element={<Navigate to="strategy" replace />} />
<Route path="playbook/:phase" element={<PlaybookPage />} />
```

In `PlaybookPage.tsx`, add:
```tsx
import { useParams, useNavigate } from 'react-router-dom'

// Inside PlaybookPage:
const { phase = 'strategy' } = useParams<{ phase: string }>()
const navigate = useNavigate()

const handlePhaseChange = useCallback((newPhase: string) => {
  navigate(`../${newPhase}`, { relative: 'path' })
}, [navigate])
```

**Acceptance criteria**:

- **Given** user navigates to `/:namespace/playbook`, **When** the page loads, **Then** they are redirected to `/:namespace/playbook/strategy`.
- **Given** user navigates to `/:namespace/playbook/contacts`, **When** the page loads, **Then** PlaybookPage receives `phase="contacts"`.
- **Given** `handlePhaseChange("messages")` is called, **When** navigation occurs, **Then** the URL updates to `/:namespace/playbook/messages`.

**Test cases**:

1. Navigate to `/visionvolve/playbook` -> verify redirect to `/visionvolve/playbook/strategy`.
2. Navigate to `/visionvolve/playbook/contacts` -> verify phase param is `"contacts"`.
3. Click phase indicator step -> verify URL changes.

---

### PB-007: `PhaseIndicator` component

**Description**: Horizontal stepper component showing the four playbook phases (Strategy, Contacts, Messages, Campaign) with visual states: active (current phase), completed (phases before current), locked (phases that fail validation), and unlocked (phases that pass validation). Clicking a completed or unlocked phase navigates to it.

**Files to create/modify**:
- Create: `frontend/src/components/playbook/PhaseIndicator.tsx`

**Dependencies**: PB-006

**Effort**: M

**Exact changes**:

```tsx
// PhaseIndicator.tsx
interface PhaseIndicatorProps {
  currentPhase: string
  onPhaseChange: (phase: string) => void
  canAdvanceTo: Record<string, boolean>  // e.g., { contacts: true, messages: false, campaign: false }
}

const PHASES = [
  { key: 'strategy', label: 'Strategy', icon: '1' },
  { key: 'contacts', label: 'Contacts', icon: '2' },
  { key: 'messages', label: 'Messages', icon: '3' },
  { key: 'campaign', label: 'Campaign', icon: '4' },
]
```

Each step renders as: circle (numbered) + label + connector line to next step. States are derived from `currentPhase` position and `canAdvanceTo` map.

**Acceptance criteria**:

- **Given** `currentPhase="strategy"`, **When** rendered, **Then** Strategy step is active (highlighted), others are dimmed.
- **Given** `currentPhase="contacts"`, **When** rendered, **Then** Strategy is completed (checkmark), Contacts is active.
- **Given** `canAdvanceTo.messages=false`, **When** the user clicks Messages, **Then** nothing happens (step is locked).
- **Given** `canAdvanceTo.contacts=true`, **When** the user clicks Contacts, **Then** `onPhaseChange("contacts")` is called.

**Test cases**:

1. Render with `currentPhase="strategy"` -> Strategy circle has active styling.
2. Render with `currentPhase="messages"` -> Strategy and Contacts have completed checkmarks.
3. Click a locked step -> no callback fired.
4. Click a completed step -> `onPhaseChange` called with that phase.

---

### PB-008: `PlaybookTopBar` component

**Description**: Extract the top bar from PlaybookPage into a standalone component that houses the PhaseIndicator, page title, and phase-specific action buttons (Save/Extract for Strategy, Select All for Contacts, Generate for Messages, Launch for Campaign).

**Files to create/modify**:
- Create: `frontend/src/components/playbook/PlaybookTopBar.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx` (use PlaybookTopBar)

**Dependencies**: PB-007

**Effort**: M

**Exact changes**:

The component receives:
```tsx
interface PlaybookTopBarProps {
  currentPhase: string
  onPhaseChange: (phase: string) => void
  canAdvanceTo: Record<string, boolean>
  // Phase-specific action props
  onSave?: () => void
  onExtract?: () => void
  isSaving?: boolean
  isExtracting?: boolean
  isDirty?: boolean
  // Generic
  version?: number
  status?: string
}
```

Layout: `[Title] [PhaseIndicator (centered)] [Action buttons (right-aligned)]`

**Acceptance criteria**:

- **Given** `currentPhase="strategy"`, **When** rendered, **Then** Save and Extract buttons are visible.
- **Given** `currentPhase="contacts"`, **When** rendered, **Then** Save/Extract are hidden, "Generate Messages" button appears.
- **Given** `isDirty=true`, **When** rendered, **Then** "Unsaved changes" indicator is visible.

**Test cases**:

1. Render in strategy phase -> Save + Extract buttons present.
2. Render in contacts phase -> Generate Messages button present.
3. Render with isDirty=true -> unsaved indicator visible.

---

### PB-009: `StrategyPanel` component — extracted from PlaybookPage

**Description**: Extract the current editor view (StrategyEditor + its state management) from PlaybookPage into a standalone `StrategyPanel` component. PlaybookPage becomes a phase router that shows StrategyPanel when phase="strategy", and placeholder panels for other phases. This is a refactor with no behavior changes.

**Files to create/modify**:
- Create: `frontend/src/components/playbook/StrategyPanel.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

**Dependencies**: PB-008

**Effort**: M

**Exact changes**:

Move the editor-related state and handlers (editedContent, isDirty, handleEditorUpdate, handleSave, handleExtract) from PlaybookPage into StrategyPanel. PlaybookPage becomes:

```tsx
function PlaybookPage() {
  const { phase } = useParams()
  // ...shared state (doc, chat, SSE)...

  return (
    <div className="flex flex-col h-full min-h-0">
      <PlaybookTopBar ... />
      <div className="flex gap-4 flex-1 min-h-0">
        <div className="flex-[3] min-w-0 flex flex-col min-h-0">
          {phase === 'strategy' && <StrategyPanel doc={doc} onSave={handleSave} ... />}
          {phase === 'contacts' && <div>Contacts phase coming soon</div>}
          {phase === 'messages' && <div>Messages phase coming soon</div>}
          {phase === 'campaign' && <div>Campaign phase coming soon</div>}
        </div>
        <div className="flex-[2] min-w-0 flex flex-col min-h-0">
          <PlaybookChat ... phase={phase} />
        </div>
      </div>
    </div>
  )
}
```

**Acceptance criteria**:

- **Given** the refactor is complete, **When** I visit `/playbook/strategy`, **Then** the editor and chat work exactly as before.
- **Given** I navigate to `/playbook/contacts`, **Then** the editor is replaced by a placeholder panel.
- **Given** the chat is visible in all phases, **Then** it remains on the right side regardless of phase.

**Test cases**:

1. All existing Playbook E2E tests continue to pass.
2. Save/extract/chat functionality works identically.
3. Phase switching shows different left panels.

---

### PB-010: Phase guard — forward navigation blocked until unlocked

**Description**: Implement client-side validation that determines whether each forward phase is reachable. Compute `canAdvanceTo` based on document state and pass it to PhaseIndicator. Also add server-side validation via the PUT /api/playbook/phase endpoint (PB-003). Backward navigation is always allowed.

**Files to create/modify**:
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`
- Modify: `frontend/src/api/queries/usePlaybook.ts` (add `useUpdatePhase` mutation hook)

**Dependencies**: PB-003, PB-007

**Effort**: S

**Exact changes**:

Add to `usePlaybook.ts`:

```tsx
export function useUpdatePhase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { phase: string }) =>
      apiFetch<StrategyDocument>('/playbook/phase', { method: 'PUT', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
    },
  })
}
```

In PlaybookPage, compute `canAdvanceTo`:

```tsx
const canAdvanceTo = useMemo(() => {
  const extracted = docQuery.data?.extracted_data || {}
  const selections = docQuery.data?.playbook_selections || {}
  return {
    strategy: true,  // always reachable
    contacts: !!extracted.icp,
    messages: (selections.contacts?.selected_ids?.length || 0) > 0,
    campaign: false,  // computed later when messages exist
  }
}, [docQuery.data])
```

**Acceptance criteria**:

- **Given** `extracted_data` is empty, **When** PhaseIndicator renders, **Then** Contacts step is locked.
- **Given** `extracted_data.icp` exists, **When** PhaseIndicator renders, **Then** Contacts step is unlocked.
- **Given** the user clicks a locked step, **When** nothing happens on the client, **Then** the phase does not change.
- **Given** the user clicks an unlocked forward step, **When** the PUT request fires, **Then** the phase updates on success and shows an error toast on 422.

**Test cases**:

1. Document with no extracted_data -> contacts locked.
2. Document with ICP -> contacts unlocked.
3. Document with selected contacts -> messages unlocked.
4. PUT /api/playbook/phase with invalid transition -> 422 error shown in toast.

---

## Bucket 2: Contact Selection (Phase 2)

### PB-011: `ContactSelectionPanel` component with ICP-derived filter pre-population

**Description**: New panel shown when `phase="contacts"`. Displays a filterable, selectable contact list. On mount, pre-populates filters from `extracted_data.icp` (industries, company size, geographies). Uses the existing contacts API with filter query parameters. Includes a search bar, industry/size/geo filter dropdowns, select-all/none toggle, and a count badge.

**Files to create/modify**:
- Create: `frontend/src/components/playbook/ContactSelectionPanel.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx` (render in contacts phase)

**Dependencies**: PB-009, PB-010

**Effort**: L

---

### PB-012: API — store selected contact IDs in `playbook_selections`

**Description**: Add a `PATCH /api/playbook/selections` endpoint that merges partial updates into the `playbook_selections` JSONB field. Used by the contact selection panel to store `{"contacts": {"selected_ids": [...], "filters": {...}}}`. Uses JSONB `||` merge operator for atomic updates.

**Files to create/modify**:
- Modify: `api/routes/playbook_routes.py`
- Modify: `tests/unit/test_playbook_phases.py`

**Dependencies**: PB-002

**Effort**: S

---

### PB-013: Wire Phase 1->2 transition — readiness gate

**Description**: When the user clicks the "Next: Select Contacts" button (or the Contacts step in PhaseIndicator), validate that `extracted_data.icp` contains at least industries and one other field. If extraction hasn't been run, auto-trigger extraction before transitioning. Show a toast if extraction fails.

**Files to create/modify**:
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`
- Modify: `frontend/src/components/playbook/PlaybookTopBar.tsx`

**Dependencies**: PB-010, PB-011

**Effort**: S

---

### PB-014: AI prompt — contacts phase instructions with ICP context

**Description**: Already implemented as part of PB-005 (`PHASE_INSTRUCTIONS["contacts"]`). This item covers testing the full flow: when the user is in the contacts phase and sends a chat message, the system prompt includes ICP criteria and the AI helps refine contact selection.

**Files to create/modify**:
- Modify: `tests/unit/test_playbook_phase_prompts.py`

**Dependencies**: PB-005, PB-011

**Effort**: S

---

### PB-015: Generate Messages button — triggers Phase 2->3 transition

**Description**: Add a "Generate Messages" action button in the PlaybookTopBar when in the contacts phase. Clicking it validates that contacts are selected, stores them, transitions to the messages phase, and triggers message generation for the selected contacts via existing campaign message generation APIs.

**Files to create/modify**:
- Modify: `frontend/src/components/playbook/PlaybookTopBar.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

**Dependencies**: PB-012, PB-013

**Effort**: M

---

## Bucket 3: Message Review (Phase 3)

### PB-016: `MessageReviewPanel` component

**Description**: New panel for `phase="messages"`. Adapted from the existing MessagesPage/MessageCard components but scoped to contacts selected in the playbook. Shows messages grouped by contact, with approve/edit/regenerate actions. Reuses the existing `PATCH /api/messages/:id` API for edits.

**Files to create/modify**:
- Create: `frontend/src/components/playbook/MessageReviewPanel.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

**Dependencies**: PB-015

**Effort**: L

---

### PB-017: Message generation trigger — on Phase 3 entry

**Description**: When the user enters the messages phase for the first time (no messages yet for selected contacts), automatically trigger message generation using the strategy's messaging framework, personas, and selected contacts. Uses the existing campaign message generation service. Shows a progress indicator while generation runs.

**Files to create/modify**:
- Modify: `api/routes/playbook_routes.py` (or new endpoint)
- Create: `api/services/playbook_message_service.py`

**Dependencies**: PB-012, PB-016

**Effort**: L

---

### PB-018: Wire Phase 2->3 transition — contact selection gate

**Description**: Before transitioning from contacts to messages, validate that at least 1 contact is selected (client-side + server-side via PB-003). Persist the selections via the PATCH endpoint (PB-012) before triggering the transition.

**Files to create/modify**:
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

**Dependencies**: PB-012, PB-015

**Effort**: S

---

### PB-019: AI prompt — messages phase instructions

**Description**: Already implemented as part of PB-005 (`PHASE_INSTRUCTIONS["messages"]`). This item covers testing and refinement: the AI should help users review messages, suggest tone/length adjustments, and reference the strategy's messaging framework.

**Files to create/modify**:
- Modify: `tests/unit/test_playbook_phase_prompts.py`

**Dependencies**: PB-005, PB-016

**Effort**: S

---

### PB-020: Launch Campaign button — triggers Phase 3->4 transition

**Description**: Add a "Launch Campaign" action button in the PlaybookTopBar when in the messages phase. Validates that messages are approved, transitions to the campaign phase, and either creates a new campaign or links to the existing campaign flow.

**Files to create/modify**:
- Modify: `frontend/src/components/playbook/PlaybookTopBar.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

**Dependencies**: PB-016, PB-018

**Effort**: M

---

## Bucket 4: Chat Enhancements

### PB-021: Action items — parse `- [ ]` from AI responses

**Description**: When the AI includes markdown task items (`- [ ] Do X`), parse them from the response content and store as structured action items in the chat message's `metadata` field. Render them as interactive checkboxes in the chat UI.

**Files to create/modify**:
- Modify: `api/routes/playbook_routes.py` (_stream_response, _sync_response)
- Modify: `api/services/playbook_service.py` (add parse function)

**Dependencies**: None (can be done in parallel with Bucket 1)

**Effort**: M

---

### PB-022: `ActionItemList` component with interactive checkboxes

**Description**: React component that renders action items extracted from AI messages as a checklist. Checking an item calls the API to toggle its state. Items are persisted in the chat message's metadata JSONB.

**Files to create/modify**:
- Create: `frontend/src/components/playbook/ActionItemList.tsx`
- Modify: `frontend/src/components/playbook/PlaybookChat.tsx`

**Dependencies**: PB-021

**Effort**: M

---

### PB-023: API — `PATCH /api/playbook/chat/:id/actions` for toggling action items

**Description**: New endpoint that updates the `metadata.action_items[N].checked` field on a specific chat message. Validates that the message belongs to the tenant's strategy document.

**Files to create/modify**:
- Modify: `api/routes/playbook_routes.py`
- Modify: `tests/unit/test_playbook_api.py`

**Dependencies**: PB-021

**Effort**: S

---

### PB-024: `PhaseTransitionCard` component

**Description**: A special card rendered in the chat history when the AI suggests advancing to the next phase (detected via keyword matching or explicit markers in the response). Shows a CTA button like "Ready for Contacts Phase ->" that, when clicked, triggers the phase transition.

**Files to create/modify**:
- Create: `frontend/src/components/playbook/PhaseTransitionCard.tsx`
- Modify: `frontend/src/components/playbook/PlaybookChat.tsx`

**Dependencies**: PB-005, PB-010

**Effort**: M

---

### PB-025: `PhaseDivider` component

**Description**: Visual separator in chat history between phases. When the phase changes, a divider is inserted showing "-- Strategy Phase Complete --" or similar. Stored as a `system` role message in the chat history.

**Files to create/modify**:
- Create: `frontend/src/components/playbook/PhaseDivider.tsx`
- Modify: `frontend/src/components/playbook/PlaybookChat.tsx`
- Modify: `api/routes/playbook_routes.py` (insert system message on phase change)

**Dependencies**: PB-003

**Effort**: S

---

### PB-026: Topic/intent detection — phase-aware instructions in system prompt

**Description**: Enhance the system prompt to detect when the user is asking about a different phase than the current one (e.g., asking about messaging while in strategy phase). The AI should acknowledge it but redirect: "Great question about messaging -- we'll get to that in the Messages phase. For now, let's finalize your ICP."

**Files to create/modify**:
- Modify: `api/services/playbook_service.py` (PHASE_INSTRUCTIONS additions)

**Dependencies**: PB-005

**Effort**: S

---

## Bucket 5: Intelligence & Polish

### PB-027: Frustration/sentiment detection in system prompt

**Description**: Add system prompt instructions for the AI to detect user frustration (short replies, complaints, repeated questions) and respond with empathy and concrete help rather than generic encouragement. Include examples of frustrated inputs and appropriate responses.

**Files to create/modify**:
- Modify: `api/services/playbook_service.py`

**Dependencies**: None

**Effort**: S

---

### PB-028: Language matching

**Description**: Detect the user's language from their chat messages and instruct the AI to respond in the same language. Add language detection logic (simple heuristic: if last 3 user messages are in non-English, switch). Add to system prompt: "Respond in the same language the user writes in."

**Files to create/modify**:
- Modify: `api/services/playbook_service.py`
- Modify: `api/routes/playbook_routes.py`

**Dependencies**: None

**Effort**: S

---

### PB-029: Strategy readiness assessment

**Description**: Add logic for the AI to evaluate whether the strategy document is "ready" (ICP has disqualifiers, personas have title patterns, metrics have numbers). The AI periodically assesses readiness and suggests moving to the next phase when criteria are met. Readiness score is computed server-side and included in the system prompt.

**Files to create/modify**:
- Modify: `api/services/playbook_service.py`
- Modify: `api/routes/playbook_routes.py`

**Dependencies**: PB-005

**Effort**: M

---

### PB-030: Improved enrichment prompts grounded in website scraping data

**Description**: When building the system prompt for the playbook chat, include website scraping data from the self-enrichment research (company's own website content, key pages, product descriptions). This gives the AI richer context to make strategy recommendations that reference the company's actual language and positioning.

**Files to create/modify**:
- Modify: `api/services/playbook_service.py` (_format_enrichment_for_prompt)
- Modify: `api/routes/playbook_routes.py` (_load_enrichment_data)

**Dependencies**: None

**Effort**: M

---

## Bucket 6: Future Vision (Not for Immediate Implementation)

### PB-031: Voice Dialog Mode (BL-047)

**Description**: Allow users to speak to the playbook AI via browser microphone. Transcribe speech to text, send to chat, and optionally read the AI response aloud using text-to-speech. Requires Web Speech API or a third-party transcription service.

**Files to create/modify**: TBD

**Dependencies**: PB-005

**Effort**: XL

---

### PB-032: AI Avatar / Virtual Team Member (BL-047)

**Description**: Present the AI assistant as a visual avatar (animated character or video) that speaks and gestures while helping the user build their strategy. Replaces or augments the text chat panel with a more human-like interaction.

**Files to create/modify**: TBD

**Dependencies**: PB-031

**Effort**: XL

---

### PB-033: Continuous Learning Loop (BL-048)

**Description**: Track which AI suggestions users accept, reject, or modify. Feed this data back into the system prompt as preference context so the AI adapts over time. Store feedback in a new `strategy_feedback` table and use it to improve future conversations.

**Files to create/modify**: TBD

**Dependencies**: PB-005

**Effort**: XL

---

### PB-034: Campaign phase (Phase 4) full implementation

**Description**: Complete implementation of the Campaign phase panel, including: campaign creation from playbook context, channel selection, cadence configuration, schedule picker, integration with existing campaign and outreach infrastructure (Lemlist, email, LinkedIn). This is the final phase of the playbook workflow.

**Files to create/modify**: TBD

**Dependencies**: PB-020

**Effort**: XL

---

## Summary Table

| ID | Title | Bucket | Depends On | Effort | Files |
|----|-------|--------|------------|--------|-------|
| PB-035 | Auto-Save (Debounced) | 1 | -- | S | PlaybookPage.tsx, usePlaybook.ts, PlaybookTopBar.tsx |
| PB-036 | Real-Time Collaboration (GDocs-style) | 1 | PB-035 | L | hocuspocus_server, StrategyEditor.tsx, models.py, migration |
| PB-037 | Intelligent Auto-Extraction | 1 | PB-035 | M | extraction_trigger.py, playbook_service.py, playbook_routes.py |
| PB-001 | DB migration: phase + selections | 1 | -- | S | migrations/033_playbook_phases.sql |
| PB-002 | Model update: StrategyDocument | 1 | PB-001 | S | api/models.py, tests/unit/test_playbook_phases.py |
| PB-003 | API: PUT /api/playbook/phase | 1 | PB-002 | M | api/routes/playbook_routes.py, tests/ |
| PB-004 | API: POST /chat gains phase param | 1 | PB-005 | S | api/routes/playbook_routes.py |
| PB-005 | Service: PHASE_INSTRUCTIONS | 1 | PB-002 | M | api/services/playbook_service.py, tests/ |
| PB-006 | Frontend route: playbook/:phase | 1 | PB-003 | S | frontend/src/App.tsx, PlaybookPage.tsx |
| PB-007 | PhaseIndicator component | 1 | PB-006 | M | frontend/src/components/playbook/PhaseIndicator.tsx |
| PB-008 | PlaybookTopBar component | 1 | PB-007 | M | frontend/src/components/playbook/PlaybookTopBar.tsx |
| PB-009 | StrategyPanel extraction | 1 | PB-008 | M | frontend/src/components/playbook/StrategyPanel.tsx |
| PB-010 | Phase guard logic | 1 | PB-003, PB-007 | S | PlaybookPage.tsx, usePlaybook.ts |
| PB-011 | ContactSelectionPanel | 2 | PB-009, PB-010 | L | frontend/src/components/playbook/ContactSelectionPanel.tsx |
| PB-012 | API: store selections | 2 | PB-002 | S | api/routes/playbook_routes.py |
| PB-013 | Phase 1->2 readiness gate | 2 | PB-010, PB-011 | S | PlaybookPage.tsx, PlaybookTopBar.tsx |
| PB-014 | Contacts phase AI prompt | 2 | PB-005, PB-011 | S | tests/ |
| PB-015 | Generate Messages button | 2 | PB-012, PB-013 | M | PlaybookTopBar.tsx, PlaybookPage.tsx |
| PB-016 | MessageReviewPanel | 3 | PB-015 | L | frontend/src/components/playbook/MessageReviewPanel.tsx |
| PB-017 | Message generation trigger | 3 | PB-012, PB-016 | L | api/services/playbook_message_service.py |
| PB-018 | Phase 2->3 gate | 3 | PB-012, PB-015 | S | PlaybookPage.tsx |
| PB-019 | Messages phase AI prompt | 3 | PB-005, PB-016 | S | tests/ |
| PB-020 | Launch Campaign button | 3 | PB-016, PB-018 | M | PlaybookTopBar.tsx |
| PB-021 | Action item parsing | 4 | -- | M | playbook_routes.py, playbook_service.py |
| PB-022 | ActionItemList component | 4 | PB-021 | M | frontend/src/components/playbook/ActionItemList.tsx |
| PB-023 | API: toggle action items | 4 | PB-021 | S | api/routes/playbook_routes.py |
| PB-024 | PhaseTransitionCard | 4 | PB-005, PB-010 | M | frontend/src/components/playbook/PhaseTransitionCard.tsx |
| PB-025 | PhaseDivider component | 4 | PB-003 | S | frontend/src/components/playbook/PhaseDivider.tsx |
| PB-026 | Topic/intent detection | 4 | PB-005 | S | api/services/playbook_service.py |
| PB-027 | Frustration detection | 5 | -- | S | api/services/playbook_service.py |
| PB-028 | Language matching | 5 | -- | S | playbook_service.py, playbook_routes.py |
| PB-029 | Strategy readiness assessment | 5 | PB-005 | M | playbook_service.py, playbook_routes.py |
| PB-030 | Website scraping in prompts | 5 | -- | M | playbook_service.py, playbook_routes.py |
| PB-031 | Voice Dialog Mode | 6 | PB-005 | XL | TBD |
| PB-032 | AI Avatar | 6 | PB-031 | XL | TBD |
| PB-033 | Continuous Learning Loop | 6 | PB-005 | XL | TBD |
| PB-034 | Campaign phase full impl | 6 | PB-020 | XL | TBD |

## Dependency Graph (Bucket 1 Critical Path)

```
PB-035 (auto-save) ─────────────────────────────────
  ├── PB-036 (real-time collaboration)              │
  └── PB-037 (intelligent auto-extraction)          │
                                                     │
PB-001 (migration) ──── can start in parallel ───────
  └── PB-002 (model)
        ├── PB-003 (phase API)
        │     ├── PB-006 (frontend route)
        │     │     └── PB-007 (PhaseIndicator)
        │     │           └── PB-008 (TopBar)
        │     │                 └── PB-009 (StrategyPanel)
        │     └── PB-010 (phase guard) ←── also depends on PB-007
        └── PB-005 (PHASE_INSTRUCTIONS)
              └── PB-004 (chat phase param)
```

**Bucket 1 parallelism**: PB-035 (auto-save) and PB-001 (migration) have no dependencies on each other and can start in parallel. PB-036 and PB-037 both depend on PB-035. PB-005 and PB-003 can start in parallel once PB-002 is done. PB-006+PB-007+PB-008+PB-009 are sequential (each builds on the previous). PB-010 merges the two branches.

## Effort Summary

| Bucket | Items | S | M | L | XL | Total Story Points (S=1, M=2, L=3, XL=5) |
|--------|-------|---|---|---|----|--------------------------------------------|
| 1: Phase Infrastructure | 13 | 5 | 6 | 1 | 0 | 20 |
| 2: Contact Selection | 5 | 3 | 1 | 1 | 0 | 8 |
| 3: Message Review | 5 | 2 | 1 | 2 | 0 | 10 |
| 4: Chat Enhancements | 6 | 3 | 3 | 0 | 0 | 9 |
| 5: Intelligence & Polish | 4 | 2 | 2 | 0 | 0 | 6 |
| 6: Future Vision | 4 | 0 | 0 | 0 | 4 | 20 |
| **Total** | **37** | **15** | **13** | **4** | **4** | **73** |
