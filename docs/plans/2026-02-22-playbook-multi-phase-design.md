# Playbook Multi-Phase Design

**Date**: 2026-02-22
**Status**: Draft
**Depends on**: [2026-02-20-playbook-design.md](./2026-02-20-playbook-design.md) (implemented)

---

## Table of Contents

1. [Overview](#overview)
2. [North Star](#north-star-the-ai-marketing-strategist)
3. [Phase Definitions](#phase-definitions)
4. [Phase State Model](#1-phase-state-model)
5. [System Prompt Evolution](#2-system-prompt-evolution)
6. [Left Panel Component Switching](#3-left-panel-component-switching)
7. [Readiness Gates](#4-readiness-gates)
8. [Chat Continuity](#5-chat-continuity)
9. [Data Flow Between Phases](#6-data-flow-between-phases)
10. [URL Routing](#7-url-routing)
11. [Phase Indicator UI](#8-phase-indicator-ui)
12. [Chat Action Items](#9-chat-action-items)
13. [Topic & Intent Detection](#10-topic--intent-detection)
14. [Frustration & Sentiment Detection](#11-frustration--sentiment-detection)
15. [API Changes Summary](#api-changes-summary)
16. [Database Migration](#database-migration)
17. [File Map](#file-map)
18. [Implementation Increments](#implementation-increments)
19. [Edge Cases](#edge-cases)
20. [Testing Strategy](#testing-strategy)

---

## Overview

The current Playbook is a single-phase tool: a Tiptap strategy editor on the left, an AI chat on the right. This design extends it into a **four-phase guided workflow** where:

- The **right panel (AI chat)** persists across ALL phases. Full conversation history is always visible. The AI adapts its persona and instructions per phase.
- The **left panel** transitions through four distinct components, one per phase.
- The AI proactively guides users through each phase and detects when they are ready to transition.

The founder's role is to approve and steer. The AI's role is to do the work.

---

## North Star: The AI Marketing Strategist

The Playbook tool should behave like you just hired a top-tier marketing strategist. Not a chatbot. Not a form. A proactive professional who:

1. **Asks the right questions proactively** -- doesn't wait to be told. Probes for context: "Who's your best client? Why did they buy? What almost killed the deal?"
2. **Does the homework without being asked** -- researches your company, market, and competitors autonomously
3. **Reports back with findings** -- "I've analyzed 40 companies in DACH manufacturing. Here are the 8 that match your ICP. Three have active hiring signals."
4. **Makes recommendations** -- "I'd prioritize these 3. Here's why, here's the angle, here's a draft outreach message."
5. **Checks in, doesn't check out** -- comes back with progress updates, asks for approval at key decision points, never disappears into a black hole
6. **Knows when they have enough** -- doesn't ask 50 questions. Gets what they need, gets to work, delivers results.

### Anti-Pattern: The Current Tool

The current tool is passive. It waits for instructions, dumps raw data, and expects the founder to be the strategist. This is backwards.

### Target Dynamic

- **AI** = the strategist who does the work, asks smart questions, delivers recommendations
- **Founder** = the CEO who approves, steers, and decides

The founder's time is the scarcest resource. Every interaction should either gather a key decision or deliver a result. Never busy-work, never "click Save", never "now go figure out what to do next."

---

## Phase Definitions

| Phase | Left Panel | AI Role | Key Output |
|-------|-----------|---------|------------|
| **1. Strategy** | Tiptap editor (existing `StrategyEditor`) | ICP strategist -- asks probing questions, synthesizes answers into the document | `extracted_data` (ICP, personas, value props) |
| **2. Contact Selection** | Filterable company/contact table | Account selector -- recommends which contacts to target and why | `playbook_selections` (selected contact IDs) |
| **3. Message Generation** | Message editor/preview list | Copywriter -- drafts personalized outreach per contact using strategy + enrichment data | Generated messages (in `messages` table) |
| **4. Campaign** | Campaign dashboard / send queue | Campaign manager -- helps configure sequencing, timing, A/B testing | Campaign configuration |

---

## 1. Phase State Model

### Database

Add a `phase` column to `strategy_documents`:

```sql
ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS phase VARCHAR(20) NOT NULL DEFAULT 'strategy';
```

Valid values: `strategy`, `contacts`, `messages`, `campaign`.

The phase represents the **highest unlocked phase**, not necessarily where the user is currently looking. Users can navigate backwards freely. Forward navigation requires passing a readiness gate (see section 4).

### State Transitions

```
strategy ──[gate]──> contacts ──[gate]──> messages ──[gate]──> campaign
    ^                    ^                    ^
    |                    |                    |
    └────── free nav ────┴──── free nav ──────┘
```

- **Forward**: Only via `POST /api/playbook/advance-phase`. Requires passing the readiness gate for the current phase.
- **Backward**: Always allowed. Navigating back does NOT reset the phase column. The user simply views a previous phase.
- **Skip**: Not allowed. Phases must be unlocked sequentially.

### Phase Ordering (Backend)

```python
PHASE_ORDER = ['strategy', 'contacts', 'messages', 'campaign']

def can_advance(current_phase: str, target_phase: str) -> bool:
    current_idx = PHASE_ORDER.index(current_phase)
    target_idx = PHASE_ORDER.index(target_phase)
    return target_idx == current_idx + 1
```

---

## 2. System Prompt Evolution

### Architecture

The system prompt is already rebuilt per-request in `playbook_routes.py` (line ~587). The current `build_system_prompt(tenant, doc, enrichment_data)` function gains a `phase` parameter:

```python
def build_system_prompt(
    tenant, document, enrichment_data=None, phase='strategy'
) -> str:
```

### Phase Instructions

A `PHASE_INSTRUCTIONS` dict provides the phase-specific instruction block. The base prompt (tenant context, enrichment data summary, document content) remains the same across all phases. Only the behavioral instructions change.

```python
PHASE_INSTRUCTIONS = {
    'strategy': """
You are an ICP strategy advisor. Your job is to help the founder define their
ideal customer profile, buyer personas, and go-to-market positioning.

BEHAVIORS:
- Ask probing questions about their best customers, why deals close, what
  objections arise. Don't ask more than 2-3 questions at a time.
- After gathering enough context (usually 3-5 exchanges), synthesize your
  understanding into concrete recommendations.
- When you believe the strategy is solid enough to start selecting contacts,
  say so explicitly: include the marker [STRATEGY_READY] in your response
  along with a summary of what's been defined.
- You can suggest edits to the strategy document on the left. Reference
  specific sections by name.

PHASE CONTEXT:
- Current phase: Strategy (1 of 4)
- Next phase: Contact Selection
- The strategy document on the left is editable. The founder may edit it
  directly or ask you to suggest changes.

TOPIC AWARENESS:
- If the user asks about contacts, messaging, or campaigns, acknowledge their
  question. You may answer briefly, but suggest moving to the appropriate phase
  if the strategy is ready. Never block them.
- If they seem frustrated, match their language and simplify your approach.
""",

    'contacts': """
You are a contact selection advisor. The ICP strategy has been defined.
Your job is to help the founder select the right companies and contacts
to target.

BEHAVIORS:
- Reference the ICP criteria from the strategy when making recommendations.
- Explain WHY specific contacts match (or don't match) the ICP.
- Suggest filtering criteria and help narrow the list.
- When the founder has selected their target list, confirm readiness with
  the marker [CONTACTS_READY] and a summary of the selection.

AVAILABLE DATA:
- The contact table on the left shows all available contacts with company
  data and enrichment results.
- You can see which contacts the founder has selected/deselected.
- Reference enrichment data (L1 tier, L2 details) to support recommendations.
""",

    'messages': """
You are an outreach copywriter. The ICP strategy is defined and target
contacts are selected. Your job is to help craft personalized outreach
messages.

BEHAVIORS:
- Draft messages that reference specific company details from enrichment.
- Suggest different angles (pain point, value prop, social proof).
- Help with subject lines, opening hooks, and CTAs.
- Offer A/B variants when appropriate.
- When messages are drafted for all selected contacts, confirm with
  [MESSAGES_READY].

CONTEXT:
- The message editor on the left shows drafts per contact.
- Each message should feel personal, not templated.
- Reference the buyer personas from the strategy phase.
""",

    'campaign': """
You are a campaign manager. Strategy is defined, contacts selected,
messages drafted. Your job is to help configure and launch the campaign.

BEHAVIORS:
- Help with sequencing (how many touchpoints, what intervals).
- Suggest timing (best days/times for outreach).
- Advise on A/B testing strategy.
- Review the full campaign before launch.
- Help interpret results after sending.
""",
}
```

### Base Prompt Structure

```
[Tenant context: company name, domain, industry]
[Enrichment data summary: L1/L2 results, if available]
[Strategy document content: current markdown]
[Phase-specific extracted data: ICP, personas, selections depending on phase]
---
[PHASE_INSTRUCTIONS[phase]]
---
[Action items context: any open action items from previous messages]
[Conversation history summary: if history exceeds context window]
```

### How the Phase is Determined Per-Request

The chat POST handler reads `doc.phase` from the database. The frontend also sends the `view_phase` (which tab the user is currently viewing) as a request parameter. The backend uses:

- `doc.phase` to know what's unlocked
- `view_phase` to know what the user is looking at right now
- If `view_phase < doc.phase` (user navigated back), the system prompt includes a note: "The user is reviewing the {view_phase} phase. They have already progressed to {doc.phase}."

---

## 3. Left Panel Component Switching

### Architecture

`PlaybookPage` becomes a phase-aware router. Instead of always rendering `StrategyEditor`, it renders the appropriate component based on the active view phase.

```tsx
// PlaybookPage.tsx — simplified structure
function PlaybookPage() {
  const { phase: urlPhase } = useParams<{ phase: string }>()
  const viewPhase = urlPhase || 'strategy'

  // ... existing hooks ...

  return (
    <div className="flex flex-col h-full min-h-0">
      <PlaybookHeader phase={viewPhase} unlockedPhase={doc.phase} ... />
      <PhaseIndicator current={viewPhase} unlocked={doc.phase} />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left: Phase-specific panel */}
        <div className="flex-[3] min-w-0 flex flex-col min-h-0">
          <PhasePanel phase={viewPhase} doc={doc} />
        </div>

        {/* Right: Chat (always present) */}
        <div className="flex-[2] min-w-0 flex flex-col min-h-0">
          <PlaybookChat
            messages={allMessages}
            onSendMessage={handleSendMessage}
            isStreaming={sse.isStreaming}
            streamingText={streamingText}
            activePhase={viewPhase}
          />
        </div>
      </div>
    </div>
  )
}
```

### PhasePanel Component

```tsx
function PhasePanel({ phase, doc }: { phase: string; doc: StrategyDocument }) {
  switch (phase) {
    case 'strategy':
      return <StrategyEditor content={doc.content} onUpdate={...} editable />
    case 'contacts':
      return <ContactSelector
               extractedData={doc.extracted_data}
               selections={doc.playbook_selections}
               onSelectionChange={...}
             />
    case 'messages':
      return <MessageComposer
               selections={doc.playbook_selections}
               extractedData={doc.extracted_data}
             />
    case 'campaign':
      return <CampaignDashboard
               selections={doc.playbook_selections}
             />
    default:
      return <StrategyEditor ... />
  }
}
```

### New Components (Stubs for Phase 2-4)

Phase 2-4 left panel components are **not designed in this document**. Each will get its own design document when its implementation is planned. For the initial multi-phase implementation, they render placeholder UIs:

- `ContactSelector` -- placeholder with "Contact selection coming soon" and the extracted ICP summary
- `MessageComposer` -- placeholder with "Message generation coming soon"
- `CampaignDashboard` -- placeholder with "Campaign management coming soon"

The chat panel is fully functional in all phases from day one. The left panel components are built incrementally.

---

## 4. Readiness Gates

### Mechanism

Readiness gates are **AI-driven**, not form-validated. The AI decides when the user has provided enough information to move forward. The AI signals readiness by including a **marker** in its response.

### Markers

| Phase Transition | Marker | Meaning |
|-----------------|--------|---------|
| Strategy -> Contacts | `[STRATEGY_READY]` | ICP, at least one persona, and value props are defined |
| Contacts -> Messages | `[CONTACTS_READY]` | At least one contact is selected |
| Messages -> Campaign | `[MESSAGES_READY]` | At least one message is drafted and approved |

### Backend Detection

When the SSE streaming completes and the assistant message is saved, the backend scans for markers:

```python
import re

READINESS_MARKERS = {
    'strategy': '[STRATEGY_READY]',
    'contacts': '[CONTACTS_READY]',
    'messages': '[MESSAGES_READY]',
}

def check_readiness_marker(content: str, current_phase: str) -> bool:
    """Check if the AI response contains a readiness marker for the current phase."""
    marker = READINESS_MARKERS.get(current_phase)
    if not marker:
        return False
    return marker in content
```

When a marker is detected:

1. The marker text is stripped from the saved message content (the user never sees the raw marker).
2. The message `metadata` gets `"phase_ready": true`.
3. The response includes a `phase_ready` flag in the SSE metadata so the frontend can render a transition prompt.

### Frontend Rendering

When `phase_ready: true` is detected (either from SSE metadata or from a message's metadata), the chat renders a **phase transition card** below the message:

```
┌─────────────────────────────────────────────┐
│  Ready to move on                           │
│                                             │
│  Your ICP strategy looks solid. Ready to    │
│  start selecting target contacts?           │
│                                             │
│  [Continue to Contact Selection]  [Not yet] │
└─────────────────────────────────────────────┘
```

- **"Continue"** calls `POST /api/playbook/advance-phase` and navigates to the next phase URL.
- **"Not yet"** dismisses the card. The user can continue chatting. The AI can re-suggest later.

### Manual Override

The user can also advance manually via the phase indicator (section 8), but only if:
1. The `extracted_data` has the minimum required fields for the current phase, OR
2. The AI has previously sent a readiness marker (stored in message metadata).

This prevents bypassing the gate entirely while still giving the user control.

---

## 5. Chat Continuity

### Single Conversation Thread

All chat messages go into the same `strategy_chat_messages` table regardless of phase. There is **no per-phase conversation split**. The AI sees the full history.

### Phase Dividers

When the phase advances, a **system message** is inserted into the chat:

```python
# When phase advances from 'strategy' to 'contacts':
system_msg = StrategyChatMessage(
    tenant_id=tenant.id,
    document_id=doc.id,
    role='system',
    content=f'--- Phase transition: Strategy -> Contact Selection ---',
    extra={'phase_transition': {'from': 'strategy', 'to': 'contacts'}},
    created_by=user.id,
)
db.session.add(system_msg)
```

The frontend renders these as visual dividers in the chat:

```
────────── Contact Selection Phase ──────────
```

### Context Window Management

As conversations grow long, the system prompt + full history may exceed the context window. Strategy:

1. **Always include**: System prompt + phase instructions + last 20 messages
2. **Summarize older messages**: When history exceeds 30 messages, the backend generates a summary of older messages and prepends it as a system message. This is done lazily (only when needed for a chat request).
3. **Phase transition summaries**: Each phase transition system message includes a brief summary of what was accomplished in the previous phase, providing natural compression points.

### Chat Awareness of Phase

The `PlaybookChat` component gains an `activePhase` prop that affects:

- **Placeholder text**: "Ask about your ICP strategy..." vs "Which contacts should we target?" vs "Let's craft your outreach messages..."
- **Phase divider rendering**: System messages with `phase_transition` metadata render as visual separators, not chat bubbles.

---

## 6. Data Flow Between Phases

### The Bridge: `extracted_data`

The `extracted_data` JSONB column on `strategy_documents` is the primary data bridge. It is populated by the Extract action (existing) and consumed by subsequent phases.

```
Phase 1 (Strategy)
    │
    ├── User writes strategy doc
    ├── AI helps refine via chat
    ├── Extract button → extracted_data populated
    │
    ▼
extracted_data: {
    "icp": { "industry": [...], "size": "...", "geo": "..." },
    "personas": [{ "title": "...", "pain_points": [...] }],
    "messaging": { "value_props": [...], "differentiators": [...] },
    "channels": [...],
    "metrics": { "target_accounts": N, "conversion_target": "..." }
}
    │
    ▼
Phase 2 (Contacts)
    │
    ├── ContactSelector shows contacts matching ICP criteria
    ├── AI recommends specific contacts referencing extracted_data
    ├── User selects contacts → playbook_selections
    │
    ▼
playbook_selections: {
    "contact_ids": ["uuid1", "uuid2", ...],
    "selected_at": "2026-02-22T...",
    "selection_criteria": "..."
}
    │
    ▼
Phase 3 (Messages)
    │
    ├── MessageComposer shows selected contacts
    ├── AI drafts messages using extracted_data + contact enrichment
    ├── Messages saved to messages table
    │
    ▼
Phase 4 (Campaign)
    │
    ├── Campaign config references messages + contacts
    └── AI helps with sequencing and launch
```

### `playbook_selections` Column

Add a JSONB column for storing phase 2 selections:

```sql
ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS playbook_selections JSONB NOT NULL DEFAULT '{}'::jsonb;
```

This stores the selected contact IDs atomically with the document, avoiding a separate join table. The selections are small (typically < 100 IDs) so JSONB is appropriate.

### Auto-Extract on Phase Advance

When advancing from Strategy to Contacts, the backend automatically runs extraction if `extracted_data` is empty or stale:

```python
@bp.route('/playbook/advance-phase', methods=['POST'])
def advance_phase():
    # ... auth, get doc ...
    target = request.json.get('target_phase')

    if doc.phase == 'strategy' and target == 'contacts':
        # Auto-extract if needed
        if not doc.extracted_data or doc.extracted_data == {}:
            extracted = extract_strategy_data(doc.content)
            doc.extracted_data = extracted

    if can_advance(doc.phase, target):
        doc.phase = target
        doc.version += 1
        # Insert phase transition system message
        # ...
        db.session.commit()
        return jsonify({'phase': doc.phase, 'version': doc.version})
    else:
        return jsonify({'error': 'Cannot advance to this phase'}), 400
```

---

## 7. URL Routing

### Route Structure

```
/playbook           → redirect to /playbook/strategy
/playbook/strategy  → Phase 1 (Strategy)
/playbook/contacts  → Phase 2 (Contact Selection)
/playbook/messages  → Phase 3 (Message Generation)
/playbook/campaign  → Phase 4 (Campaign)
```

### React Router Changes

In `App.tsx`:

```tsx
// Before:
<Route path="playbook" element={<PlaybookPage />} />

// After:
<Route path="playbook" element={<Navigate to="playbook/strategy" replace />} />
<Route path="playbook/:phase" element={<PlaybookPage />} />
```

### URL vs State

The URL determines which left panel component renders (`viewPhase`). The database `phase` column determines what is **unlocked**. The URL can be behind the unlocked phase (user navigated back) but never ahead of it.

```tsx
const { phase: urlPhase } = useParams<{ phase: string }>()
const viewPhase = urlPhase || 'strategy'
const unlockedPhase = doc.phase

// Guard: don't let URL go ahead of unlocked phase
const viewIdx = PHASE_ORDER.indexOf(viewPhase)
const unlockedIdx = PHASE_ORDER.indexOf(unlockedPhase)
if (viewIdx > unlockedIdx) {
  return <Navigate to={`/playbook/${unlockedPhase}`} replace />
}
```

### Navigation

Phase changes happen via:
1. **Phase indicator clicks** (section 8) -- only for unlocked phases
2. **Transition card** (section 4) -- advances phase and navigates
3. **Direct URL** -- guarded by unlock check

All navigation uses `navigate(`/playbook/${phase}`)` (React Router), not full page reloads.

---

## 8. Phase Indicator UI

### Design

A horizontal stepper bar between the header and the split panels:

```
  ● Strategy    ○─── Contacts    ○─── Messages    ○─── Campaign
  ▲ active      ▲ locked         ▲ locked          ▲ locked


  ✓ Strategy    ● Contacts       ○─── Messages    ○─── Campaign
  ▲ completed   ▲ active         ▲ locked          ▲ locked
```

### Component

```tsx
interface PhaseIndicatorProps {
  current: string          // currently viewed phase (from URL)
  unlocked: string         // highest unlocked phase (from DB)
  onNavigate: (phase: string) => void
}

const PHASES = [
  { key: 'strategy', label: 'Strategy', icon: '1' },
  { key: 'contacts', label: 'Contacts', icon: '2' },
  { key: 'messages', label: 'Messages', icon: '3' },
  { key: 'campaign', label: 'Campaign', icon: '4' },
]

function PhaseIndicator({ current, unlocked, onNavigate }: PhaseIndicatorProps) {
  const unlockedIdx = PHASES.findIndex(p => p.key === unlocked)

  return (
    <div className="flex items-center gap-0 mb-3 px-2">
      {PHASES.map((phase, idx) => {
        const isUnlocked = idx <= unlockedIdx
        const isCurrent = phase.key === current
        const isCompleted = idx < unlockedIdx

        return (
          <Fragment key={phase.key}>
            {idx > 0 && (
              <div className={`flex-1 h-px mx-2 ${
                isCompleted ? 'bg-success' : 'bg-border-solid'
              }`} />
            )}
            <button
              onClick={() => isUnlocked && onNavigate(phase.key)}
              disabled={!isUnlocked}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs
                font-medium transition-colors cursor-pointer
                ${isCurrent
                  ? 'bg-accent/15 text-accent border border-accent/30'
                  : isCompleted
                    ? 'text-success hover:bg-success/10'
                    : isUnlocked
                      ? 'text-text-muted hover:bg-surface-alt'
                      : 'text-text-dim opacity-50 cursor-not-allowed'
                }`}
            >
              <span className={`w-5 h-5 rounded-full flex items-center
                justify-center text-[10px] font-bold
                ${isCompleted
                  ? 'bg-success text-white'
                  : isCurrent
                    ? 'bg-accent text-white'
                    : 'bg-surface-alt text-text-dim'
                }`}>
                {isCompleted ? '\u2713' : phase.icon}
              </span>
              {phase.label}
            </button>
          </Fragment>
        )
      })}
    </div>
  )
}
```

### Interaction

- **Click unlocked phase**: Navigate to that phase (URL change, left panel switches, chat stays)
- **Click locked phase**: No action (disabled)
- **Current phase**: Highlighted with accent color
- **Completed phases**: Green checkmark, clickable to revisit

---

## 9. Chat Action Items

### Requirement

When the AI suggests steps or tasks during the conversation, they should become trackable action items -- not just chat text that scrolls away.

### Implementation: Markdown Checklists in Metadata

The AI is instructed (via system prompt) to format action items as markdown checklists:

```markdown
Here's your action plan:
- [ ] Finalize ICP targeting criteria
- [ ] Define 3 buyer personas
- [ ] Draft cold email angle
```

### Storage

Action items are parsed from the AI's response and stored in the message's `metadata` (the `extra` JSONB column):

```python
def extract_action_items(content: str) -> list[dict]:
    """Parse markdown checklist items from AI response."""
    items = []
    for match in re.finditer(r'- \[([ x])\] (.+)', content):
        items.append({
            'id': str(uuid.uuid4()),
            'text': match.group(2).strip(),
            'completed': match.group(1) == 'x',
        })
    return items

# After saving assistant message:
action_items = extract_action_items(assistant_content)
if action_items:
    msg.extra = {**(msg.extra or {}), 'action_items': action_items}
```

### Frontend Rendering

Messages with `metadata.action_items` render the items as interactive checkboxes below the message text:

```tsx
function ActionItemList({ items, messageId, onToggle }) {
  return (
    <div className="mt-3 space-y-1.5 border-t border-border pt-3">
      {items.map(item => (
        <label key={item.id} className="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={item.completed}
            onChange={() => onToggle(messageId, item.id)}
            className="mt-0.5"
          />
          <span className={item.completed ? 'line-through text-text-dim' : ''}>
            {item.text}
          </span>
        </label>
      ))}
    </div>
  )
}
```

### Toggle API

```
PATCH /api/playbook/chat/:messageId/action-item
Body: { "item_id": "uuid", "completed": true }
```

Updates the specific action item's `completed` flag in the message metadata. The AI is informed of open action items via the system prompt context block.

### AI Awareness

The system prompt includes a summary of open action items:

```
OPEN ACTION ITEMS (from previous messages):
- Finalize ICP targeting criteria (from Feb 22)
- Define 3 buyer personas (from Feb 22)

You may reference these items. If the user has addressed one, mark it complete
by including "Completed: [item text]" in your response.
```

---

## 10. Topic & Intent Detection

### Approach: Prompt-Based (No Classifier)

Topic detection is handled entirely via the system prompt. Adding a separate classifier would add latency, complexity, and another model to maintain. The main LLM is already excellent at detecting conversational context shifts.

### System Prompt Instructions

Each phase's instructions include a `TOPIC AWARENESS` block (shown in the Strategy example in section 2). The key behaviors:

1. **Adapt**: If the user asks about a different phase's topic, the AI answers helpfully without forcing them back.
2. **Suggest transition**: If the question strongly indicates readiness for the next phase, the AI suggests moving forward.
3. **Bridge**: For brief tangential questions, the AI answers and gently notes the phase context.

### Phase Context in Prompt

The system prompt includes:

```
CURRENT PHASE: Strategy (1 of 4)
USER IS VIEWING: Strategy
UNLOCKED UP TO: Strategy
PHASES AHEAD: Contacts, Messages, Campaign

If the user asks about topics relevant to a future phase, you may:
1. Answer briefly and note which phase handles that in depth
2. Suggest advancing if the current phase feels complete
3. Never refuse to help — just provide context
```

### Cross-Phase Signal Logging

When the AI detects a topic shift, it can include metadata in its response (parsed by the backend):

```
[TOPIC_SIGNAL: contacts]
```

This is logged to `playbook_logs` for analytics but does not trigger any automatic behavior. It helps the product team understand when users are mentally ready to move on.

---

## 11. Frustration & Sentiment Detection

### Approach: Prompt-Based

Like topic detection, frustration detection is handled via the system prompt. The AI is instructed to watch for signals and adapt.

### System Prompt Block (Included in All Phases)

```
SENTIMENT AWARENESS:
- If the user switches languages (e.g., English to Czech), match their language
  immediately and change your approach. Language switching is a strong
  frustration signal.
- If messages get shorter/more terse, simplify your responses.
- If the user repeats a request, you failed to deliver what they needed.
  Try a completely different approach.
- Never over-apologize. Acknowledge briefly, then deliver better output.
- Never respond to frustration with more of what caused it.
```

### Event Logging

The backend detects potential frustration signals and logs them:

```python
def detect_frustration_signals(message: str, history: list) -> dict | None:
    """Lightweight heuristic for frustration signals."""
    signals = {}

    # Language switch detection (simple heuristic)
    if history and len(history) >= 2:
        prev_lang = detect_language(history[-1].content)
        curr_lang = detect_language(message)
        if prev_lang != curr_lang:
            signals['language_switch'] = {'from': prev_lang, 'to': curr_lang}

    # Message length trending down
    if len(history) >= 3:
        recent_lengths = [len(m.content) for m in history[-3:]]
        if all(recent_lengths[i] > recent_lengths[i+1] for i in range(2)):
            signals['shortening_messages'] = True

    # Explicit frustration keywords
    frustration_words = ['wrong', 'not what i', 'already said', 'again']
    if any(w in message.lower() for w in frustration_words):
        signals['explicit_frustration'] = True

    return signals if signals else None
```

When detected, a `PlaybookLog` entry is created:

```python
if signals:
    log = PlaybookLog(
        tenant_id=tenant.id,
        user_id=user.id,
        doc_id=doc.id,
        event_type='frustration_signal',
        payload=signals,
    )
    db.session.add(log)
```

This data feeds into the continuous learning loop (BL-048) for product improvement.

---

## API Changes Summary

### New Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/playbook/advance-phase` | Advance to next phase (with gate check) |
| PATCH | `/api/playbook/chat/:id/action-item` | Toggle action item completion |

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| GET | `/api/playbook` | Response includes `phase` and `playbook_selections` |
| PUT | `/api/playbook` | Accepts `playbook_selections` in body |
| POST | `/api/playbook/chat` | Accepts `view_phase` param; response includes `phase_ready` flag; detects readiness markers |

### `POST /api/playbook/advance-phase`

```
Request:  { "target_phase": "contacts" }
Response: { "phase": "contacts", "version": 12 }
Error:    { "error": "Cannot advance: strategy extraction incomplete" }, 400
```

### `PATCH /api/playbook/chat/:id/action-item`

```
Request:  { "item_id": "uuid", "completed": true }
Response: { "action_items": [...updated list...] }
```

---

## Database Migration

File: `migrations/033_playbook_phases.sql`

```sql
-- 033: Add multi-phase support to Playbook
--
-- Adds phase tracking and contact selections to strategy_documents.

BEGIN;

-- Phase column (highest unlocked phase)
ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS phase VARCHAR(20) NOT NULL DEFAULT 'strategy';

-- Contact selections for Phase 2
ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS playbook_selections JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Index for phase-based queries
CREATE INDEX IF NOT EXISTS idx_strategy_documents_phase
    ON strategy_documents(phase);

COMMIT;
```

Note: The migration number 033 assumes 031 and 032 may be claimed by other work. Adjust as needed.

---

## File Map

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/components/playbook/PhaseIndicator.tsx` | Horizontal stepper UI |
| `frontend/src/components/playbook/PhasePanel.tsx` | Left panel phase switcher |
| `frontend/src/components/playbook/ContactSelector.tsx` | Phase 2 left panel (stub initially) |
| `frontend/src/components/playbook/MessageComposer.tsx` | Phase 3 left panel (stub initially) |
| `frontend/src/components/playbook/CampaignDashboard.tsx` | Phase 4 left panel (stub initially) |
| `frontend/src/components/playbook/ActionItemList.tsx` | Checkbox list for chat action items |
| `frontend/src/components/playbook/PhaseTransitionCard.tsx` | "Ready to advance" prompt card |
| `migrations/033_playbook_phases.sql` | Database migration |

### Modified Files

| File | Changes |
|------|---------|
| `api/models.py` | Add `phase`, `playbook_selections` columns to `StrategyDocument` |
| `api/routes/playbook_routes.py` | Add `advance_phase` endpoint, `action_item` toggle, `view_phase` param on chat, readiness marker detection |
| `api/services/playbook_service.py` | Add `PHASE_INSTRUCTIONS`, update `build_system_prompt` with `phase` param, add `extract_action_items`, add `check_readiness_marker` |
| `frontend/src/pages/playbook/PlaybookPage.tsx` | Phase-aware routing, `PhasePanel` integration, `PhaseIndicator` integration |
| `frontend/src/components/playbook/PlaybookChat.tsx` | `activePhase` prop, action item rendering, phase divider rendering, phase transition card |
| `frontend/src/api/queries/usePlaybook.ts` | Add `useAdvancePhase`, `useToggleActionItem` hooks; update `StrategyDocument` type |
| `frontend/src/App.tsx` | Route change: `playbook` -> `playbook/:phase` with redirect |

---

## Implementation Increments

### Increment 1: Phase State Foundation

**Goal**: Phase tracking works end-to-end but only Strategy phase has real content.

- Migration 033 (add `phase`, `playbook_selections` columns)
- Update `StrategyDocument` model
- `PhaseIndicator` component (renders but only Strategy is unlocked)
- URL routing (`/playbook/:phase` with redirect)
- Phase guard (prevent URL access to locked phases)
- Stub components for Phase 2-4 left panels

### Increment 2: AI Phase Awareness

**Goal**: Chat adapts behavior per phase.

- `PHASE_INSTRUCTIONS` dict in `playbook_service.py`
- `build_system_prompt` gains `phase` parameter
- `view_phase` parameter on chat POST
- Phase divider system messages
- Phase-aware placeholder text in chat input

### Increment 3: Readiness Gates & Transitions

**Goal**: AI can signal readiness; users can advance phases.

- Readiness marker detection in chat response handler
- `POST /api/playbook/advance-phase` endpoint
- `PhaseTransitionCard` component
- Auto-extract on Strategy -> Contacts transition
- Phase transition system message insertion

### Increment 4: Action Items

**Goal**: AI suggestions become trackable checklists.

- `extract_action_items` function
- Action items stored in message metadata
- `ActionItemList` component
- `PATCH /api/playbook/chat/:id/action-item` endpoint
- `useToggleActionItem` hook
- Action items context in system prompt

---

## Edge Cases

### Multiple Users Same Tenant

The `strategy_documents` table has a `UNIQUE` constraint on `tenant_id`. All users in a tenant share one document and one conversation. Phase state is per-tenant, not per-user. If two users are in different phases, the URL routing handles this gracefully (each sees the left panel they navigated to, but the unlocked phase is shared).

### Onboarding and Phase 1

The existing `PlaybookOnboarding` flow (domain + objective form, background research) runs BEFORE Phase 1. It gates on `enrichment_id` being null. The phase system starts at `strategy` after onboarding completes. No conflict.

### Phase Regression

If a user is in Phase 3 and edits the strategy document (Phase 1), it does NOT reset the phase. The strategy may have evolved, but the phase represents progress, not validity. The AI can note if strategy changes significantly affect downstream phases.

### Empty Phases

If the user advances but hasn't done meaningful work (e.g., no contacts selected), that's allowed by the readiness gate system -- the AI won't emit the readiness marker until real work is done. The manual override requires minimum `extracted_data` presence.

### Context Window Overflow

With a long conversation spanning 4 phases, history can get very long. The summarization strategy (section 5) handles this. Phase transition messages serve as natural summarization boundaries.

### Concurrent Chat + Phase Advance

If a user sends a chat message while a phase advance is in flight, the backend uses the phase at the time of the chat request. The optimistic locking on `version` prevents race conditions on document state.

---

## Testing Strategy

### Unit Tests (pytest)

- `test_phase_advance`: Verify phase transitions follow ordering rules
- `test_phase_advance_blocked`: Verify locked phases cannot be skipped
- `test_readiness_marker_detection`: Verify markers are found/stripped correctly
- `test_action_item_extraction`: Verify markdown checklist parsing
- `test_action_item_toggle`: Verify PATCH updates metadata correctly
- `test_build_system_prompt_phases`: Verify system prompt includes correct phase instructions
- `test_auto_extract_on_advance`: Verify extraction runs when advancing from Strategy

### E2E Tests (Playwright)

- `test_phase_indicator_navigation`: Click through unlocked phases, verify left panel changes, chat persists
- `test_phase_locked`: Click locked phase, verify no navigation
- `test_url_guard`: Navigate to locked phase URL, verify redirect
- `test_phase_transition_card`: Simulate readiness, verify card renders, click advance
- `test_chat_continuity`: Send messages in Phase 1, advance to Phase 2, verify messages still visible
- `test_action_items`: Verify checkboxes render, toggling works, state persists across reload
