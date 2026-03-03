# Playbook (GTM Strategy Co-Creation) Design

**Date**: 2026-02-20
**Status**: Approved

## Overview

A Playbook page (`/:namespace/playbook`) that combines a Tiptap block editor (left pane) with an AI chat panel (right pane). The system auto-researches the namespace's own company via the existing L1/L2 enrichment pipeline, then uses Claude Opus 4.6 to draft a full GTM strategy. Users refine via chat or direct editing. On save, structured data is extracted to configure the rest of the app (ICP filters, message generation, campaign defaults, analytics benchmarks).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Entry point** | Chat-first with research pre-loaded | AI acts as a prepared consultant, not a blank slate |
| **Editor** | Tiptap v2 (full block editor) | Rich editing, JSON storage, extensible, future collab-ready |
| **AI model** | Claude Opus 4.6 via Anthropic API | Complex strategic reasoning over business context |
| **Streaming** | SSE (not WebSocket) | One-directional, works through Caddy, no new infra |
| **Storage** | Single JSONB document + extracted_data | Simple, one strategy per namespace |
| **Concurrency** | Optimistic locking (version counter) | Rare conflicts, minimal complexity |
| **Self-enrichment** | Existing L1/L2 pipeline on own domain | Reuse infrastructure, no new research workflows |
| **Extraction** | LLM call on save, outputs structured JSON | Powers ICP filters, message gen, campaigns, analytics |

## User Journey

### Namespace creation (existing flow, extended)

1. Admin creates namespace, specifies company domain
2. System triggers L1/L2 enrichment on that domain (new: self-enrichment)
3. Enrichment results land in a company record flagged with `is_self = true`
4. Creates `strategy_documents` record in `draft` status with template skeleton

### First Playbook visit

1. If enrichment still running: progress indicator "Researching your company..."
2. If enrichment complete: Chat opens with research summary + first clarifying question
3. AI asks 3-5 targeted questions it could not answer from research alone:
   - "Who is your primary buyer persona -- technical decision-maker or business executive?"
   - "What is your average deal size and sales cycle length?"
   - "Which pain points resonate most with your current wins?"
4. After Q&A, AI generates a full draft strategy in the block editor
5. User refines via chat ("make the ICP more specific to mid-market") or direct editing

### Returning visits

- Strategy document persists, fully editable
- Chat history preserved
- User can request updates ("update messaging for a new product launch") and AI revises relevant sections

## Strategy Document Structure

The AI generates a GTM strategy with these best-practice sections:

| Section | Content | Extracts To |
|---------|---------|-------------|
| Executive Summary | Company overview, market position, strategic thesis | -- |
| Ideal Customer Profile | Industry, company size, geo, tech stack, triggers, disqualifiers | ICP filter criteria for contacts/companies |
| Buyer Personas | 2-3 personas with title patterns, pain points, goals, objections | Message generation persona targeting |
| Value Proposition | Core value prop, differentiators, proof points per persona | Message tone/angles/talking points |
| Competitive Positioning | Key competitors, advantages, landmines to avoid | Objection handling in messages |
| Channel Strategy | Primary/secondary channels, cadence, sequence logic | Campaign default channels + sequence templates |
| Messaging Framework | Key themes, subject line angles, CTA patterns, tone guidelines | Message generation config |
| Success Metrics | Pipeline targets, reply rate goals, conversion benchmarks, timeline | Echo analytics benchmarks |

Each section is a Tiptap block group (headings, rich text, lists, callout boxes, tables). The template skeleton shows these sections with placeholder text explaining what each should contain.

## Database Schema

### New tables (migration 005)

```sql
-- One strategy document per namespace
CREATE TABLE strategy_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL UNIQUE REFERENCES tenants(id),
    content         JSONB NOT NULL DEFAULT '{}',
    extracted_data  JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft | active | archived
    version         INTEGER NOT NULL DEFAULT 1,
    enrichment_id   UUID REFERENCES companies(id),          -- self-enrichment company record
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_by      UUID REFERENCES users(id)
);

-- Chat history for strategy co-creation
CREATE TABLE strategy_chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    document_id     UUID NOT NULL REFERENCES strategy_documents(id),
    role            VARCHAR(20) NOT NULL,  -- user | assistant | system
    content         TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',  -- model, tokens, cost, suggested_edits
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by      UUID REFERENCES users(id)
);
CREATE INDEX idx_strategy_chat_messages_document
    ON strategy_chat_messages(document_id, created_at);
```

### Companies table change

Add `is_self BOOLEAN NOT NULL DEFAULT FALSE` to the `companies` table. When a namespace is created with a domain, a company record is created with `is_self = true` and linked from `strategy_documents.enrichment_id`.

### extracted_data JSONB structure

Written on save, consumed by other features:

```json
{
  "icp": {
    "industries": ["SaaS", "FinTech"],
    "company_size": {"min": 50, "max": 500},
    "geographies": ["DACH", "Nordics"],
    "tech_signals": ["uses Salesforce", "hiring SDRs"],
    "triggers": ["Series A+", "new CRO hire"],
    "disqualifiers": ["< 20 employees", "no web presence"]
  },
  "personas": [
    {
      "title_patterns": ["VP Sales", "Head of Revenue"],
      "pain_points": ["manual pipeline tracking", "low rep productivity"],
      "goals": ["predictable revenue", "scale team efficiently"]
    }
  ],
  "messaging": {
    "tone": "consultative",
    "themes": ["AI-driven efficiency", "pipeline predictability"],
    "angles": ["ROI calculator", "competitive displacement"],
    "proof_points": ["3x pipeline velocity for similar companies"]
  },
  "channels": {
    "primary": "email",
    "secondary": ["linkedin"],
    "cadence": "3-touch over 10 days"
  },
  "metrics": {
    "reply_rate_target": 0.15,
    "meeting_rate_target": 0.05,
    "pipeline_goal_eur": 500000,
    "timeline_months": 6
  }
}
```

## API Endpoints

```
GET    /api/playbook              -- get strategy doc (auto-create if missing)
PUT    /api/playbook              -- save document content + bump version
POST   /api/playbook/extract      -- trigger extraction from content -> writes extracted_data
GET    /api/playbook/chat         -- get chat history
POST   /api/playbook/chat         -- send message, get AI response (SSE streaming)
POST   /api/playbook/research     -- trigger L1/L2 enrichment on namespace domain
GET    /api/playbook/research     -- check enrichment status + get results summary
```

All endpoints require JWT auth + `X-Namespace` header (standard tenant resolution).

### POST /api/playbook/chat

Request:

```json
{
  "message": "Make the ICP more specific to mid-market SaaS"
}
```

Response: SSE stream (`text/event-stream`).

```
data: {"type": "token", "content": "I'll narrow"}
data: {"type": "token", "content": " the ICP to"}
...
data: {"type": "done", "message_id": "uuid", "metadata": {"tokens": 450, "suggested_edits": [...]}}
```

Flow:

1. Receive user message
2. Build context window:
   - Self-enrichment data (L1 + L2 results for own company)
   - Current strategy document content (Tiptap JSON converted to plaintext)
   - Chat history (last N messages)
   - System prompt with GTM best practices + extraction schema
3. Call Claude Opus 4.6 API (streaming)
4. Stream response back via SSE
5. If response contains suggested edits, return structured edit operations in metadata

### PUT /api/playbook (optimistic locking)

Request:

```json
{
  "content": { "...tiptap json..." },
  "version": 3
}
```

Behavior:

```sql
UPDATE strategy_documents
SET content = $1, version = version + 1, updated_at = NOW(), updated_by = $2
WHERE tenant_id = $3 AND version = $4;
-- 0 rows affected -> 409 Conflict
```

On 409, frontend shows conflict modal: "Someone else edited. Reload to see their changes, or force-save to overwrite."

## Frontend Architecture

### Layout

```
+----------------------------------------------------------+
|  Nav bar                                    [Save] [...]  |
+---------------------------------+------------------------+
|                                 |                        |
|   Strategy Document             |   AI Chat              |
|   (Tiptap block editor)        |                        |
|                                 |   +------------------+ |
|   ## Executive Summary          |   | I've researched  | |
|   Acme Corp is a...             |   | Acme Corp...     | |
|                                 |   +------------------+ |
|   ## Ideal Customer Profile     |                        |
|   - Industry: SaaS, FinTech    |   +------------------+ |
|   - Size: 50-500 employees     |   | What's your avg  | |
|                                 |   | deal size?       | |
|   ## Buyer Personas             |   +------------------+ |
|   ...                           |                        |
|                                 |   +--------------+     |
|                                 |   | Type here... | [>] |
|                                 |   +--------------+     |
+---------------------------------+------------------------+
|  Status: Draft  |  Last saved 2m ago by michal           |
+----------------------------------------------------------+
```

### Key components

| Component | Responsibility |
|-----------|---------------|
| `PlaybookPage.tsx` | Layout shell, resizable split pane |
| `StrategyEditor.tsx` | Tiptap editor with custom blocks (callout, metric card, persona card) |
| `PlaybookChat.tsx` | Chat panel with SSE streaming, suggested-edit buttons |
| `usePlaybook.ts` | TanStack Query hooks for document + chat + research status |
| `usePlaybookChat.ts` | SSE stream handler, message state management |

### Editor: Tiptap v2

- MIT licensed, React-first, extensible block system
- Built-in: headings, lists, tables, code blocks, task lists
- Custom extensions: callout blocks, metric cards, persona cards
- JSON serialization matches JSONB storage directly
- Collaboration extension available for future real-time upgrade

### Chat-to-editor integration

- AI responses can include `suggested_edits` in metadata
- These render as clickable "Apply to document" buttons in the chat
- Clicking applies a Tiptap transaction (insert/replace specific section)
- User can select text in editor and say "improve this section" -- selection context sent to chat

### Save flow

1. User clicks Save (or auto-save after 30s idle)
2. PUT /api/playbook with current Tiptap JSON + version
3. On success: trigger POST /api/playbook/extract in background
4. Extraction completes: extracted_data written, toast "Strategy data updated across the app"
5. On 409 conflict: modal with reload/force-save options

## Self-Enrichment Trigger

When a namespace is created with a domain:

1. POST /api/tenants (existing) -- after creating tenant, creates company record with `is_self = true`
2. Triggers POST /api/playbook/research -- kicks off existing L1/L2 pipeline against that domain
3. Creates `strategy_documents` record in `draft` status with template skeleton
4. When enrichment completes, document is ready for AI to draft

Reuses the existing orchestrator workflow (`N00qr21DCnGoh32D`) and sub-workflows. No new n8n workflows required.

## AI Model Integration

Claude Opus 4.6 via direct Anthropic API (`anthropic` Python SDK).

System prompt includes:
- GTM strategy best practices and section structure
- The `extracted_data` JSON schema (so the model knows what structured output to produce)
- The user's enrichment research summary (company intel, market signals, competitive landscape)
- Instructions to ask clarifying questions before generating, not after

SSE streaming from Flask: yields `data:` events as tokens arrive from the Anthropic streaming API. Frontend uses `fetch` with `ReadableStream`. No WebSocket infrastructure needed. Caddy proxies SSE natively.

## Concurrency Model

- Optimistic locking via `version` counter on `strategy_documents`
- On save: `UPDATE ... WHERE version = N`; if 0 rows affected, return 409
- Conflict resolution: reload (see other person's changes) or force-save (overwrite)
- No real-time cursors, presence, or CRDT -- unnecessary for target user base (small teams, freelancers)
- Upgrade path: Tiptap Collaboration extension if multi-user editing becomes a requirement

## Downstream Consumers

The `extracted_data` JSONB is the contract between Playbook and the rest of the app:

| Consumer | Reads | Purpose |
|----------|-------|---------|
| Contact/Company filtering | `icp.industries`, `icp.company_size`, `icp.geographies` | Pre-filter lists, lead scoring |
| Message generation | `messaging.tone`, `messaging.themes`, `personas` | Configure AI message drafting |
| Campaign defaults | `channels.primary`, `channels.cadence` | Pre-set campaign channel + sequence |
| Echo analytics | `metrics.*` | Set benchmark targets for performance dashboards |
| Enrichment focus | `icp.tech_signals`, `icp.triggers` | Prioritize enrichment research areas |

## Data Flow

### Initial setup (namespace creation)

```
Admin creates namespace with domain
    |
    v
POST /api/tenants -> creates tenant
    |
    v
Creates company record (is_self=true) + strategy_documents (draft)
    |
    v
POST /api/playbook/research -> triggers L1/L2 enrichment
    |
    v
Orchestrator workflow runs against own domain
    |
    v
Enrichment results written to company record
```

### Strategy co-creation

```
User visits /:namespace/playbook
    |
    v
GET /api/playbook -> returns doc + enrichment status
    |
    +-- enrichment running --> progress indicator
    |
    +-- enrichment complete --> chat opens with research summary
            |
            v
        AI asks 3-5 clarifying questions
            |
            v
        User answers via chat
            |
            v
        POST /api/playbook/chat (SSE) -> AI generates strategy
            |
            v
        Strategy rendered in Tiptap editor
            |
            v
        User refines (chat or direct edit)
            |
            v
        Save -> PUT /api/playbook (version check)
            |
            v
        POST /api/playbook/extract -> extracted_data written
            |
            v
        Downstream consumers read extracted_data
```
