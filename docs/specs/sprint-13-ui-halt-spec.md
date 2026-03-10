# Sprint 13 — Halt Gates, Generative UI, Shared State & Editor Integration

## Overview

Sprint 13 builds the user-facing interaction layer on top of Sprint 11's AG-UI protocol foundation. It introduces adaptive halt gates (interrupt-and-resume), generative UI components rendered inline in chat, synchronized agent-frontend state, and surgical Tiptap editor integration with suggestion mode.

## Problem Statement

The current agent runs autonomously for up to 25 tool iterations without any checkpoints. Users cannot intervene at critical decision points (wrong product scope, wrong ICP direction), leading to wasted tokens and discarded strategies. Additionally, all agent output is plain text streamed into chat — there is no way to render rich components (tables, progress cards, approval buttons) inline. The strategy editor receives full-document replacements via `setContent()`, which is jarring and prevents incremental review.

---

## BL-257: Adaptive Halt Gates

### User Stories

**US-1**: As a user, I want the agent to pause and ask me when it finds multiple products or ICP segments, so I can steer the strategy before it invests tokens in the wrong direction.

**US-2**: As a user, I want to configure how often the agent asks for confirmation (always, big decisions only, or fully autonomous), so I can balance control vs speed.

### Acceptance Criteria

```
Given the agent reaches a decision point with multiple valid options
When a halt gate fires
Then:
  1. Execution pauses via LangGraph interrupt()
  2. Frontend renders an approval UI with options (buttons, not chat text)
  3. User can approve, reject, or modify the choice
  4. Agent resumes with the user's choice injected into state
  5. Halt gate frequency respects user preference setting

Given a resource gate fires before an expensive operation
When the gate UI appears
Then the estimated token cost is displayed alongside approve/reject buttons
```

### Technical Approach

**Backend** (`api/agents/halt_gates.py`):
- Define `HaltGate` dataclass with: gate_type (scope/direction/assumption/review/resource), question, options, context, metadata
- Define `HaltGateConfig` with frequency levels: "always", "major_only", "autonomous"
- `check_halt_gate()` function evaluates whether to interrupt based on gate type + user config
- Integration point: called from agent nodes before critical decisions, uses LangGraph `interrupt()` to pause

**Backend** (`api/agents/events.py`):
- Add `HALT_GATE_REQUEST` and `HALT_GATE_RESPONSE` custom AG-UI event types
- `halt_gate_request()` factory emits the gate UI data
- `halt_gate_response()` maps user choice back into agent state

**Frontend** (`frontend/src/components/chat/HaltGateUI.tsx`):
- Renders inline in chat when HALT_GATE_REQUEST event arrives
- Shows: context text, question, option buttons
- Resource gates show token estimate badge
- Calls API to resume with user choice

**Frontend** (`frontend/src/hooks/useHaltGate.ts`):
- Hook manages pending halt gate state
- `respondToGate(gateId, choice)` sends response to backend
- Clears gate state after response

### Data Model

No database changes. Halt gate config stored in user preferences (existing `preferences` JSONB column on users table).

### API Contract

**Resume endpoint**: `POST /api/agents/halt-gate/respond`
```json
{
  "thread_id": "string",
  "run_id": "string",
  "gate_id": "string",
  "choice": "string",
  "custom_input": "string | null"
}
```

---

## BL-258: Generative UI

### User Stories

**US-1**: As a user, I want to see rich components inline in chat (tables, progress cards, comparison views) instead of just plain text, so I can quickly understand structured data.

### Acceptance Criteria

```
Given the agent streams structured data via STATE_DELTA events
When the delta contains a `component` field
Then:
  1. The appropriate rich component renders inline in chat
  2. Components update incrementally via subsequent STATE_DELTA patches
  3. Data tables render with sortable columns
  4. Progress cards show completion percentage
  5. Comparison views show side-by-side options
  6. When rich rendering is not possible, graceful text fallback is shown
```

### Technical Approach

**Backend** (`api/agents/events.py`):
- Extend `state_delta()` to support component payloads: `{component: "data_table", props: {...}}`
- Component types: `data_table`, `progress_card`, `comparison_view`, `approval_buttons`
- Each component type has a defined props schema

**Frontend** (`frontend/src/components/chat/GenerativeUI.tsx`):
- `GenerativeUIRenderer` component dispatches on `component` field
- `DataTable` — renders sortable table from rows/columns props
- `ProgressCard` — shows phase name, progress bar, status text
- `ComparisonView` — side-by-side cards for comparing options
- Text fallback: if component type unknown, render JSON as formatted text

**Frontend** (`frontend/src/types/agui.ts`):
- TypeScript types for all AG-UI events and component props
- Strict typing for STATE_DELTA component payloads

---

## BL-259: Shared State Sync

### User Stories

**US-1**: As a user, I want the frontend to stay in sync with the agent's internal state (current phase, document completeness, enrichment status) without manual refresh.

### Acceptance Criteria

```
Given a user connects to a chat session
When the connection is established
Then a STATE_SNAPSHOT event delivers the full current state

Given the agent updates its internal state
When a state change occurs
Then a STATE_DELTA event with JSON Patch operations updates the frontend

Given the user navigates away and returns
When the page loads
Then state is restored from the last STATE_SNAPSHOT
```

### Technical Approach

**Backend** (`api/agents/shared_state.py`):
- `AgentSharedState` dataclass: current_phase, active_section, doc_completeness (dict of section -> percentage), enrichment_status, context_summary, halt_gates_pending
- `SharedStateManager` class: holds state per thread, emits snapshots and deltas
- `apply_delta()` method generates JSON Patch (RFC 6902) operations
- `get_snapshot()` returns full state dict

**Frontend** (`frontend/src/hooks/useAgentState.ts`):
- `useAgentState()` hook subscribes to STATE_SNAPSHOT and STATE_DELTA events
- Maintains local state copy, applies JSON Patch deltas
- `selectState(path)` for subscribing to specific state slices
- State persists in sessionStorage for navigation resilience

**Frontend** (`frontend/src/components/chat/StateSync.tsx`):
- Provider component wrapping the chat that manages state sync lifecycle
- Emits STATE_SNAPSHOT request on mount/reconnect
- Applies STATE_DELTA patches as they arrive

---

## BL-260: Agent Document Editing

### User Stories

**US-1**: As a user, I want the agent to make surgical edits to the strategy document (insert, replace, delete at specific positions) instead of replacing the entire document.

### Acceptance Criteria

```
Given the agent wants to update a section
When it emits STATE_DELTA with edit operations
Then:
  1. Tiptap applies edits in real-time at the correct positions
  2. Insert operations add content at the specified location
  3. Replace operations swap content at the specified range
  4. Delete operations remove content at the specified range
  5. Multiple edits in sequence apply correctly
  6. Edit operations are reversible via undo
```

### Technical Approach

**Backend** (`api/agents/events.py`):
- Add `DOCUMENT_EDIT` event type (custom AG-UI extension)
- Edit operations: `{op: "insert", section: "executive_summary", position: "end", content: "..."}`
- Operations: insert (at position), replace (range), delete (range)
- Section-based addressing (H2 headings as anchors)

**Frontend** (`frontend/src/components/editor/AgentEditing.tsx`):
- `useAgentEditing(editor)` hook processes DOCUMENT_EDIT events
- Maps section names to Tiptap node positions via heading text search
- `applyInsert()`: `editor.commands.insertContentAt(pos, content)`
- `applyReplace()`: `editor.chain().deleteRange(range).insertContentAt(pos, content).run()`
- `applyDelete()`: `editor.commands.deleteRange(range)`
- All operations wrapped in a single transaction for undo support

---

## BL-261: Accept/Reject Changes

### User Stories

**US-1**: As a user, I want agent edits to appear as suggestions I can accept or reject individually, like Google Docs suggestion mode.

### Acceptance Criteria

```
Given the agent makes edits to the strategy document
When edits are applied via AgentEditing
Then:
  1. Edits appear as highlighted suggestions (green for additions, strikethrough for deletions)
  2. Each suggestion has accept/reject buttons
  3. Batch "Accept All" / "Reject All" buttons are available
  4. Accepting a change commits it to the document
  5. Rejecting a change reverts to the previous content
  6. Visual diff highlighting clearly shows proposed vs current content
```

### Technical Approach

**Frontend** (`frontend/src/components/editor/SuggestionMode.tsx`):
- Custom Tiptap extension `SuggestionMark` that wraps agent edits in decorations
- Mark types: `suggestion-add` (green highlight), `suggestion-delete` (strikethrough + red)
- Each suggestion has a unique ID for individual accept/reject
- `SuggestionToolbar` renders inline accept/reject buttons next to each suggestion
- `SuggestionBanner` shows batch controls at top of editor when suggestions are pending

**State Management**:
- `useSuggestions()` hook tracks pending suggestions
- Suggestions stored as Tiptap marks with metadata (suggestion_id, type, original_content)
- Accept: remove mark, keep content (for add) or remove content (for delete)
- Reject: remove mark and content (for add) or restore content (for delete)

---

## Dependencies

```
BL-250 (LangGraph) ──┐
BL-252 (AG-UI)  ─────┤
                      ├── BL-257 (Halt Gates)
                      ├── BL-258 (Generative UI)
                      ├── BL-259 (Shared State)
                      └── BL-260 (Agent Doc Editing) ── BL-261 (Accept/Reject)
```

## Test Plan

### Unit Tests
- `tests/unit/test_halt_gates.py`: Gate evaluation logic, config filtering, event formatting
- `tests/unit/test_shared_state.py`: State snapshot/delta generation, JSON Patch correctness
- Frontend: TypeScript compilation check (`npx tsc --noEmit`)

### Integration Tests
- Halt gate round-trip: fire gate -> render UI -> respond -> agent resumes
- State sync: snapshot on connect -> delta updates -> state consistency
- Document editing: emit edit events -> verify Tiptap content changes

### Manual Verification
- Visual check of halt gate UI in chat
- Verify generative UI components render inline
- Verify suggestion mode highlights in strategy editor
