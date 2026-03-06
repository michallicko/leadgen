# Sprint 19: Outreach Agent Subgraph

## Problem Statement

The multi-agent architecture (Sprints 11-18) has Strategy, Research, and Enrichment
subgraphs but lacks a dedicated agent for message generation and outreach management.
Users requesting "write a message for this contact" are currently routed to the
passthrough/quick_response node, which cannot access message tools or contact
enrichment data.

## Solution

Add an **Outreach Agent** subgraph that handles message generation, personalization,
A/B variant creation, and message lifecycle management (draft -> review -> approve).

## Architecture

### Outreach Subgraph (`api/agents/subgraphs/outreach.py`)

- LangGraph StateGraph with `outreach_agent` and `outreach_tools` nodes
- Conditional routing: tool_calls -> tools node, else -> END
- Max 15 iterations safety limit
- Model: Sonnet (claude-sonnet-4-5-20241022) for generation quality
- Temperature: 0.5 (slightly creative for message drafting)
- Focused system prompt (~200 tokens) emphasizing personalization
- Emits `message_generated` SSE event for UI updates

### Message Tools (`api/tools/message_tools.py`)

5 tools registered with the tool registry:

| Tool | Purpose | Required Args |
|------|---------|---------------|
| `generate_message` | Create personalized outreach for a contact | `contact_id` |
| `list_messages` | List messages by contact/tag/status | none (all optional filters) |
| `update_message` | Edit body/subject, approve/reject | `message_id` |
| `get_message_templates` | Return available message frameworks | none |
| `generate_variants` | Create A/B variant of existing message | `message_id` |

### Intent Classification (`api/agents/intent.py`)

- Added `outreach` as a 5th intent category
- Keyword fast path: "generate message", "write message", "outreach message",
  "linkedin message", "approve message", etc.
- Separated `outreach` (message generation) from `campaign` (campaign management)
- Outreach keywords checked before campaign keywords (more specific first)

### Orchestrator Integration (`api/agents/orchestrator.py`)

- Added `outreach_node()` that runs the outreach subgraph
- Routes `outreach` intent to `outreach_node`
- Strategy/research/campaign remain on passthrough (handled by other sprints)

## Message Templates

5 built-in frameworks for message generation:

1. **Pain Point** — Lead with prospect's pain, then position solution
2. **Mutual Connection** — Build rapport via shared context
3. **Insight-Led** — Share industry insight, connect to offering
4. **Trigger Event** — Reference recent company news
5. **Value First** — Offer something valuable before asking

## Security

- All DB queries filter by `tenant_id` (multi-tenant isolation)
- Tool allowlist prevents outreach agent from calling strategy/research tools
- Message status transitions validated (only draft/approved/rejected accepted)
- Original content tracked before edits (audit trail)

## Acceptance Criteria

- Given a user says "write a message for [contact]", the intent classifier routes to outreach
- Given a valid contact_id, generate_message creates a draft in the messages table
- Given a message_id, generate_variants creates a linked A/B variant
- Given an outreach tool call, strategy/research tools are blocked
- Given max iterations reached, the agent loop terminates gracefully

## Files Created

- `api/agents/subgraphs/outreach.py` — Outreach Agent subgraph
- `api/agents/orchestrator.py` — Updated orchestrator with outreach routing
- `api/agents/intent.py` — Updated intent classifier with outreach intent
- `api/agents/state.py` — Agent state (includes outreach intent)
- `api/agents/graph.py` — SSEEvent and helpers
- `api/tools/message_tools.py` — 5 message tool handlers + definitions
- `tests/unit/test_outreach_subgraph.py` — Subgraph tests
- `tests/unit/test_message_tools.py` — Tool handler tests
- `docs/specs/sprint-19-messaging-spec.md` — This spec
