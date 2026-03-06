# Agentic Architecture

**Last updated**: 2026-03-06

This document is the definitive reference for the agentic features of the leadgen-pipeline. It covers the LangGraph-based agent framework, multi-agent orchestration, AG-UI streaming protocol, halt gates, generative UI, shared state synchronization, and the prompt layering strategy.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Core Framework](#2-core-framework)
3. [Prompt Layering](#3-prompt-layering)
4. [AG-UI Protocol](#4-ag-ui-protocol)
5. [Multi-Agent Orchestration](#5-multi-agent-orchestration)
6. [Agent Types](#6-agent-types)
7. [Halt Gates](#7-halt-gates)
8. [Generative UI](#8-generative-ui)
9. [Shared State](#9-shared-state)
10. [Agent Document Editing](#10-agent-document-editing)
11. [Memory & RAG](#11-memory--rag)
12. [Multimodal Processing](#12-multimodal-processing)
13. [Tool Routing](#13-tool-routing)
14. [Cost Controls](#14-cost-controls)
15. [Feature Flags](#15-feature-flags)
16. [Sprint Roadmap](#16-sprint-roadmap)

---

## 1. Overview

The agentic architecture powers the Playbook chat -- a conversational AI interface where a "fractional CMO" agent helps founders build GTM strategies. The system replaces a monolithic agent executor loop with a declarative LangGraph StateGraph, enabling multi-agent orchestration, typed state management, and streaming events via the AG-UI protocol.

### Design Principles

- **AI as strategist, not tool** -- the agent proactively researches, writes, and recommends. Users approve decisions, not keystrokes.
- **Halt at decision points** -- the agent pauses at critical junctures (scope, direction, cost) rather than guessing wrong.
- **Specialist agents** -- focused prompt + focused tools = better output and lower cost per call.
- **Zero busywork** -- auto-save, auto-extract, guided flow. Every interaction gathers a decision or delivers a result.

### Key Files

| File | Purpose |
|------|---------|
| `api/agents/graph.py` | Main LangGraph StateGraph, agent/tools nodes, execution entry point |
| `api/agents/state.py` | `AgentState` TypedDict for graph state |
| `api/agents/tools.py` | Bridge from tool_registry to LangChain StructuredTool |
| `api/agents/events.py` | AG-UI event types and SSE-to-AG-UI mapping |
| `api/agents/halt_gates.py` | Halt gate types, factory functions, frequency config |
| `api/agents/shared_state.py` | JSON Patch state sync between agent and frontend |
| `api/agents/prompts/identity.py` | Layer 0+1: static identity + capability prompt |
| `api/agents/prompts/context.py` | Layer 2: dynamic context (document, enrichment, phase) |
| `api/agents/orchestrator.py` | Top-level intent classification and routing |
| `api/agents/intent.py` | Keyword fast-path + Haiku fallback classifier |
| `api/agents/subgraphs/strategy.py` | Strategy Agent subgraph (Sonnet, 8 tools) |
| `api/agents/subgraphs/research.py` | Research Agent subgraph (Haiku, 7 tools) |

---

## 2. Core Framework

### LangGraph StateGraph

The agent framework is built on LangGraph's `StateGraph`, replacing a while-loop executor with a declarative graph. The graph is compiled once per turn and streamed via `stream_mode="custom"`.

**Graph structure** (monolithic, Sprint 11):

```
                ┌──────────────┐
                │  agent_node  │  (call Claude with messages + tools)
                └──────┬───────┘
                       │
              ┌────────▼────────┐
              │ should_continue  │  (check for tool_calls or END)
              └───┬─────────┬───┘
                  │         │
           tools ─┘         └─ end
                  │              │
          ┌───────▼───────┐     │
          │  tools_node   │     │
          └───────┬───────┘     │
                  │             │
                  └──────┐      │
                         ▼      ▼
                  (loop back)  END
```

The `agent_node` calls `ChatAnthropic` with the full message history and tool definitions. If the response contains `tool_calls`, the graph routes to `tools_node` which executes each tool and returns `ToolMessage` objects. The loop continues until the agent responds without tool calls or hits the iteration limit.

### AgentState

Defined in `api/agents/state.py`:

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]  # LangChain messages
    tool_context: dict[str, Any]     # tenant_id, user_id, document_id, turn_id
    iteration: int                    # current loop count (max 25)
    total_input_tokens: int           # accumulated across LLM calls
    total_output_tokens: int
    total_cost_usd: str               # Decimal as string
    model: str                        # e.g. "claude-haiku-4-5-20251001"
```

The `messages` field uses LangGraph's `add_messages` reducer, which handles deduplication and append semantics.

### Node Functions

**`agent_node`** (`api/agents/graph.py:54`):
- Builds `ChatAnthropic` with the configured model and temperature 0.4
- Binds tools from `get_tools_for_api()` (Claude API format dicts)
- Invokes the model, tracks token usage and cost
- Emits `chunk` SSE events for streaming text to the frontend
- Returns updated messages, iteration count, and token/cost accumulators

**`tools_node`** (`api/agents/graph.py:110`):
- Iterates over `tool_calls` from the last `AIMessage`
- For each tool: emits `tool_start` event, executes handler, emits `tool_result` event
- Special handling for `update_strategy_section` and `append_to_section`: emits `section_update` + `section_content_*` events for live document animation
- Creates `ToolMessage` objects for the next agent iteration
- Runs tool handlers inside Flask `app.app_context()` when needed for DB access

### Conditional Routing

**`should_continue`** (`api/agents/graph.py:279`):
- Returns `"tools"` if the last message is an `AIMessage` with tool calls
- Returns `"end"` if max iterations (25) reached or no tool calls
- The graph routes to `tools_node` or `END` based on this decision

### Execution Entry Point

**`execute_graph_turn`** (`api/agents/graph.py:387`):
- Generator function that yields `SSEEvent` objects (drop-in replacement for the old `execute_agent_turn`)
- Converts Anthropic-format message dicts to LangChain message objects
- Builds initial `AgentState` with tool context, model, and counters
- Streams the graph with `stream_mode="custom"`, collecting events from `get_stream_writer()`
- Enforces a 180-second turn timeout
- Yields a final `done` event with accumulated metadata (tool calls, tokens, cost)

### Safety Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| `MAX_TOOL_ITERATIONS` | 25 | Prevent infinite loops |
| `MAX_TURN_SECONDS` | 180 | Prevent runaway turns |
| `web_search` rate limit | 5/turn | Cap expensive API calls |
| Default tool rate limit | 15/turn | General tool throttle |

---

## 3. Prompt Layering

The system prompt is split into cacheable and dynamic layers for token efficiency. Over a 25-iteration tool loop, the static layers are cached after the first call, saving significant input tokens.

### Layer Architecture

| Layer | Content | Tokens | Cacheable | File |
|-------|---------|--------|-----------|------|
| **L0: Identity** | Role definition, critical rules, tone, response style, length limits | ~800 | Yes (`cache_control: ephemeral`) | `prompts/identity.py` |
| **L1: Capabilities** | Research workflow, tool usage rules, document editing rules, ICP/persona rules | ~500 | Yes (`cache_control: ephemeral`) | `prompts/identity.py` |
| **L2: Context** | User objective, strategy document content, section completeness, enrichment data, phase instructions, page context, language override | ~1-5K | No (changes per call) | `prompts/context.py` |
| **L3: Conversation** | Message history (managed by LangGraph `add_messages`) | ~1-4K | No | Handled by state |

### L0: Identity (`IDENTITY_PROMPT`)

Static across all calls. Defines:
- **Critical rules**: Never use negative language about companies. Write comprehensive content. No filler.
- **Tone rules**: Encouraging and collaborative. Forbidden phrases listed explicitly.
- **Response length**: Hard limit of 150 words (400 for explicit deep-dive requests).
- **Response style**: Fractional CMO persona. Action-oriented. Bullet points over paragraphs.
- **Question behavior**: Ask ONE question at a time with 3-4 quick-select options.
- **Generation rule**: Always produce strategy even with limited data.

### L1: Capabilities (`CAPABILITY_PROMPT`)

Static per session, changes with tool set:
- **Research workflow**: Call `research_own_company` first, then `web_search` for follow-ups.
- **Tool use for editing**: MUST call `update_strategy_section` to write. Never describe without calling.
- **ICP/persona rules**: Use `set_icp_tiers` and `set_buyer_personas` for structured data. Never write ICP content into document sections.
- **Sparse data handling**: Insert `**TODO**: [description]` markers.

### L2: Context (`build_context_block`)

Dynamic, rebuilt each call:
- User objective from the strategy document
- Full strategy document content (markdown)
- Section completeness status (EMPTY / NEEDS WORK / PARTIAL / COMPLETE with word counts)
- ICP tier and buyer persona status (triggers URGENT prompt if empty)
- Enrichment data (formatted from company research)
- Phase-specific instructions (strategy/contacts/messages/campaign)
- Page context hints (adapts behavior based on which page user is viewing)
- Language override (responds in user's configured language)

### System Message Construction

`build_system_messages()` in `graph.py` combines layers into a single `SystemMessage` with multiple content blocks:

```python
[
    {"type": "text", "text": L0 + L1, "cache_control": {"type": "ephemeral"}},  # cached
    {"type": "text", "text": L1_capabilities, "cache_control": {"type": "ephemeral"}},  # cached
    {"type": "text", "text": L2_context},  # not cached, changes per call
]
```

**Expected savings**: 50-70% input token reduction on subsequent calls in the same turn. Over a 25-iteration tool loop, approximately 31K cached input tokens saved per turn.

---

## 4. AG-UI Protocol

AG-UI (Agent-User Interaction) is the streaming protocol between the agent backend and the React frontend. Events flow as JSON over Server-Sent Events (SSE).

### Event Types

**Standard AG-UI events** (defined in `api/agents/events.py`):

| Event | Purpose | Key Fields |
|-------|---------|------------|
| `RUN_STARTED` | Agent begins processing a turn | `threadId`, `runId` |
| `RUN_FINISHED` | Agent completes a turn | `threadId`, `runId`, cost/token metadata |
| `TEXT_MESSAGE_START` | Agent begins streaming text | `messageId` |
| `TEXT_MESSAGE_CONTENT` | Text chunk from agent | `messageId`, `delta` |
| `TEXT_MESSAGE_END` | Agent finishes streaming text | `messageId` |
| `TOOL_CALL_START` | Tool execution begins | `toolCallId`, `toolCallName`, `input` |
| `TOOL_CALL_END` | Tool execution completes | `toolCallId`, `status`, `summary`, `durationMs` |
| `STATE_DELTA` | Incremental state update (JSON Patch) | `delta` |
| `STATE_SNAPSHOT` | Full state for sync/reconnect | `snapshot` |

**Custom extensions** (prefixed with `CUSTOM:`):

| Event | Purpose |
|-------|---------|
| `CUSTOM:halt_gate_request` | Pause agent, present decision UI to user |
| `CUSTOM:halt_gate_response` | User's choice sent back to agent |
| `CUSTOM:document_edit` | Surgical document edit for Tiptap integration |
| `CUSTOM:generative_ui` | Render rich component inline in chat |
| `CUSTOM:research_status` | Research polling status update |
| `CUSTOM:thinking_status` | Agent thinking indicator |

### SSE Wire Format

Each event serializes to:
```
data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "abc", "delta": "Here is..."}\n\n
```

### Internal-to-AG-UI Mapping

The `sse_to_agui()` function (`events.py:266`) bridges internal `SSEEvent` types from the LangGraph graph to AG-UI protocol events:

| Internal Type | AG-UI Type |
|---------------|------------|
| `chunk` | `TEXT_MESSAGE_CONTENT` |
| `tool_start` | `TOOL_CALL_START` |
| `tool_result` | `TOOL_CALL_END` |
| `section_update` | `STATE_DELTA` |
| `section_content_start` | `TEXT_MESSAGE_START` (with section context) |
| `section_content_chunk` | `TEXT_MESSAGE_CONTENT` (section stream) |
| `section_content_done` | `TEXT_MESSAGE_END` |
| `done` | `RUN_FINISHED` |
| `halt_gate_request` | `CUSTOM:halt_gate_request` |
| `document_edit` | `CUSTOM:document_edit` |
| `generative_ui` | `CUSTOM:generative_ui` |

### Frontend Integration

Frontend components consuming AG-UI events:

| Component | File | Responsibility |
|-----------|------|----------------|
| `ChatMessages` | `frontend/src/components/chat/ChatMessages.tsx` | Renders streaming text, tool calls |
| `StateSync` | `frontend/src/components/chat/StateSync.tsx` | Applies STATE_DELTA/SNAPSHOT to React context |
| `HaltGateUI` | `frontend/src/components/chat/HaltGateUI.tsx` | Renders halt gate decision cards |
| `GenerativeUI` | `frontend/src/components/chat/GenerativeUI.tsx` | Renders inline rich components |
| `WorkflowProgressStrip` | `frontend/src/components/chat/WorkflowProgressStrip.tsx` | Phase progress indicator |

---

## 5. Multi-Agent Orchestration

### Architecture (Sprint 12)

The monolithic single-agent graph is replaced by an orchestrator that classifies user intent and routes to specialist subgraphs:

```
User message
     │
     ▼
┌────────────┐
│  classify   │  (intent classification: keyword fast-path + Haiku fallback)
└─────┬──────┘
      │
      ├── strategy_edit ──► Strategy Agent (Sonnet, 8 tools, max 15 iterations)
      │
      ├── research ────────► Research Agent (Haiku, 7 tools, max 15 iterations)
      │
      ├── quick_answer ────► Quick Response (Haiku, no tools, 2048 max tokens)
      │
      └── campaign ────────► Passthrough (placeholder for future Campaign Agent)
      │
      ▼
     END
```

### Orchestrator Graph (`api/agents/orchestrator.py`)

Built as a `StateGraph(AgentState)` with these nodes:

1. **`classify`** -- Calls `classify_intent()` to determine which specialist handles the request. Emits an `intent_classified` SSE event with the result and latency.

2. **`strategy_node`** -- Builds and streams the strategy subgraph. Passes back messages, tokens, costs, and section completeness.

3. **`research_node`** -- Builds and streams the research subgraph. Accumulates research results in shared state for cross-agent use.

4. **`quick_response_node`** -- Direct Haiku call with minimal prompt (no tools). Fast path for greetings, clarifications, and simple questions.

5. **`passthrough_node`** -- Placeholder for future agent types (Campaign, Outreach). Currently falls back to `quick_response_node`.

### Intent Classification (`api/agents/intent.py`)

Two-tier classification for speed:

**Tier 1: Keyword fast-path** (0ms, no LLM call):
- Short messages (<10 chars) -> `quick_answer`
- Greetings (hi, hello, thanks) -> `quick_answer`
- Keyword matches: `STRATEGY_KEYWORDS` -> `strategy_edit`, `RESEARCH_KEYWORDS` -> `research`, `CAMPAIGN_KEYWORDS` -> `campaign`

**Tier 2: Haiku classification** (<500ms):
- Minimal prompt (~100 tokens): "Classify into exactly one category"
- Temperature 0.0, max_tokens 20
- Regex cleanup on response
- Falls back to `quick_answer` on parse failure or exception

### Data Flow Between Agents

Research results flow to Strategy Agent through shared state:

```
Research Agent
  └── research_tools_node accumulates results
       └── state["research_results"] = {"web_search": {...}, "research_own_company": {...}}

Strategy Agent
  └── strategy_agent_node reads state.get("research_results")
       └── Injected into system prompt as "--- Research Context ---"
```

---

## 6. Agent Types

### Strategy Agent (`api/agents/subgraphs/strategy.py`)

**Purpose**: Writes, updates, and refines GTM strategy document sections.

| Property | Value |
|----------|-------|
| Model | Sonnet (`claude-sonnet-4-5-20241022`) |
| Temperature | 0.4 |
| Max tokens | 8192 |
| Max iterations | 15 |
| System prompt | ~200 tokens (focused on document editing) |

**Tools** (8 -- strategy-only):
- `update_strategy_section` -- Replace section content
- `append_to_section` -- Add content without replacing
- `set_extracted_field` -- Set structured metadata
- `track_assumption` -- Flag assumptions needing validation
- `check_readiness` -- Assess document completeness
- `set_icp_tiers` -- Structured ICP tier data
- `set_buyer_personas` -- Structured persona data
- `get_strategy_document` -- Read full document

**Tool enforcement**: The `strategy_tools_node` explicitly rejects tool calls not in `STRATEGY_TOOL_NAMES`, returning an error message to the agent.

### Research Agent (`api/agents/subgraphs/research.py`)

**Purpose**: Web searches, company research, CRM queries, enrichment analysis.

| Property | Value |
|----------|-------|
| Model | Haiku (`claude-haiku-4-5-20251001`) by default |
| Temperature | 0.3 |
| Max tokens | 4096 |
| Max iterations | 15 |
| System prompt | ~150 tokens (focused on finding/analyzing data) |

**Tools** (7 -- research-only):
- `web_search` -- Internet search
- `research_own_company` -- Deep company intelligence (cached)
- `count_contacts` / `count_companies` -- CRM aggregate queries
- `list_contacts` -- Detailed contact data
- `filter_contacts` -- Criteria-based contact filtering
- `analyze_enrichment_insights` -- Enrichment data analysis

**Result accumulation**: The `research_tools_node` stores tool results in `state["research_results"]` as a dict keyed by tool name, with data, timestamp, and input for each result.

### Quick Response (inline in orchestrator)

**Purpose**: Simple questions, greetings, status checks.

| Property | Value |
|----------|-------|
| Model | Haiku |
| Temperature | 0.4 |
| Max tokens | 2048 |
| Tools | None |
| System prompt | ~50 tokens |

### Future Agents (Planned)

| Agent | Sprint | Purpose | Model |
|-------|--------|---------|-------|
| Enrichment Agent | Sprint 14+ | Contact/company enrichment pipeline | Haiku |
| Outreach Agent | Sprint 14+ | Message generation, campaign planning | Sonnet |
| Data Agent | Sprint 15+ | Document processing, CRM queries, imports | Haiku |

---

## 7. Halt Gates

Halt gates pause agent execution at critical decision points. The user sees approval UI with options and the agent resumes with their choice.

### Gate Types (`api/agents/halt_gates.py`)

| Type | When | Example |
|------|------|---------|
| `scope` | Multiple valid scopes found | "Which product line should we focus on?" |
| `direction` | Mutually exclusive strategies | "Broad ICP or narrow ICP?" |
| `assumption` | AI made an uncertain guess | "I'm assuming B2B SaaS. Correct?" |
| `review` | Major deliverable complete | "Strategy draft ready. Approve or adjust?" |
| `resource` | Expensive operation ahead | "Enrich 50 contacts for ~500 tokens?" |

### Frequency Control

Users configure halt gate frequency via preferences:

| Frequency | Behavior |
|-----------|----------|
| `always` | Halt at every gate (default) |
| `major_only` | Halt only for `scope`, `direction`, and `resource` gates |
| `autonomous` | Never halt -- agent decides everything |

Configuration stored in user's `preferences` JSONB column:
```json
{
  "halt_gates": {
    "frequency": "major_only",
    "disabled_types": ["assumption"]
  }
}
```

### Gate Decision Logic

```python
def should_halt(gate, config) -> bool:
    if config.frequency == AUTONOMOUS: return False
    if gate.gate_type in config.disabled_types: return False
    if config.frequency == MAJOR_ONLY: return gate.gate_type in MAJOR_GATE_TYPES
    return True  # ALWAYS mode
```

### Factory Functions

Convenience builders for common scenarios:

- `scope_gate(question, options, context)` -- Multiple valid scopes
- `direction_gate(question, options, context)` -- Mutually exclusive paths
- `review_gate(question, context, options=None)` -- Deliverable review (default: approve/adjust/review_full)
- `resource_gate(question, estimated_tokens, estimated_cost_usd, context)` -- Cost confirmation (approve/skip/cancel)

### AG-UI Integration

Gates emit `CUSTOM:halt_gate_request` events via SSE:
```json
{
  "type": "CUSTOM:halt_gate_request",
  "gateId": "uuid",
  "gateType": "scope",
  "question": "Which product line should we focus on?",
  "options": [
    {"label": "Enterprise SaaS", "value": "enterprise", "description": "B2B focus"},
    {"label": "SMB Tools", "value": "smb", "description": "Self-serve focus"}
  ],
  "context": "Your company has two distinct product lines...",
  "metadata": {}
}
```

The frontend renders this via `HaltGateUI.tsx` and sends back a `CUSTOM:halt_gate_response`.

---

## 8. Generative UI

The agent can render rich interactive components inline in the chat stream using `CUSTOM:generative_ui` events.

### Event Format

```json
{
  "type": "CUSTOM:generative_ui",
  "componentType": "data_table",
  "componentId": "contacts-preview-1",
  "props": { "columns": [...], "rows": [...] },
  "action": "add"
}
```

Actions: `add` (insert new component), `update` (merge props), `remove` (delete component).

### Component Types (Planned)

| Type | Use Case |
|------|----------|
| `data_table` | Contact lists, company comparisons |
| `progress_card` | Enrichment pipeline progress |
| `comparison_view` | Side-by-side strategy alternatives |
| `chart` | Metrics visualization |
| `approval_card` | Inline approve/reject for halt gates |

### Frontend Rendering

`GenerativeUI.tsx` maps `componentType` to React components and manages the component lifecycle (add/update/remove) based on events. Components are rendered inline within the chat message stream.

### Shared State Integration

Generative UI components are tracked in `AgentSharedState.components`:
```python
state.components = [
    {"id": "contacts-preview-1", "type": "data_table", "props": {...}},
]
```

The `SharedStateManager` provides `add_component()`, `update_component()`, and `remove_component()` methods that return JSON Patch deltas for STATE_DELTA events.

---

## 9. Shared State

Shared state synchronizes the agent's internal state with the frontend via AG-UI `STATE_DELTA` and `STATE_SNAPSHOT` events.

### AgentSharedState (`api/agents/shared_state.py`)

```python
@dataclass
class AgentSharedState:
    current_phase: str = "strategy"         # Active workflow phase
    active_section: Optional[str] = None    # Section agent is working on
    doc_completeness: dict[str, int] = {}   # Per-section completion %
    enrichment_status: str = "idle"         # Pipeline state
    context_summary: str = ""               # What agent knows/has done
    halt_gates_pending: list[str] = []      # Pending gate IDs
    components: list[dict] = []             # Active generative UI components
```

### JSON Patch Synchronization (RFC 6902)

State changes are transmitted as JSON Patch operations:

```json
[
  {"op": "replace", "path": "/activeSection", "value": "Executive Summary"},
  {"op": "replace", "path": "/docCompleteness", "value": {"Executive Summary": 85}}
]
```

**`generate_json_patch(old, new)`** -- Computes top-level replace/remove operations between two state dicts.

**`apply_json_patch(state, operations)`** -- Applies operations to a state dict (deep-copied, not mutated). Supports `replace`, `add`, and `remove` operations.

### SharedStateManager

Manages per-thread state with snapshot/delta tracking:

- **`get_snapshot()`** -- Returns full state for `STATE_SNAPSHOT` event. Resets delta baseline.
- **`update(**kwargs)`** -- Updates state fields, returns JSON Patch delta. Accepts both camelCase (matching AG-UI format) and snake_case field names.
- **`add_component(type, id, props)`** -- Adds a generative UI component. Returns delta.
- **`update_component(id, props)`** -- Merges props into existing component. Returns delta.
- **`remove_component(id)`** -- Removes a component. Returns delta.

### Frontend State Sync

`StateSync.tsx` consumes `STATE_DELTA` and `STATE_SNAPSHOT` events:
- On `STATE_SNAPSHOT`: replaces React context state entirely
- On `STATE_DELTA`: applies JSON Patch operations incrementally
- State is also persisted in `sessionStorage` for tab restore

---

## 10. Agent Document Editing

The agent edits the strategy document through tool calls that produce `CUSTOM:document_edit` events for the Tiptap rich text editor.

### Edit Events

```json
{
  "type": "CUSTOM:document_edit",
  "editId": "uuid",
  "section": "Executive Summary",
  "operation": "replace",
  "content": "New section content...",
  "position": "end"
}
```

| Field | Values |
|-------|--------|
| `operation` | `insert`, `replace`, `delete` |
| `position` | `start`, `end`, or character offset |
| `section` | H2 heading text identifying the target section |

### Section Update Animation

When the agent calls `update_strategy_section` or `append_to_section`, the tools node emits a sequence of events for typewriter animation:

1. `section_update` -- Signals which section is being modified
2. `section_content_start` -- Marks the beginning of content streaming
3. `section_content_chunk` -- Streams content in 10-character chunks
4. `section_content_done` -- Marks the end of content streaming

### Frontend Components

| Component | File | Role |
|-----------|------|------|
| `AgentEditing.tsx` | `frontend/src/components/editor/AgentEditing.tsx` | Tracks pending edits, shows accept/reject UI |
| `SuggestionMode.tsx` | `frontend/src/components/editor/SuggestionMode.tsx` | Diff highlighting for proposed changes |

### Accept/Reject Workflow (Planned)

The full Tiptap AI Toolkit integration will enable:
1. Agent proposes section edits as tracked changes
2. User sees inline diff highlighting
3. User can accept or reject each proposed change
4. Accepted changes are committed to the strategy document

---

## 11. Memory & RAG

### Current: Fixed Window

The conversation history is managed by LangGraph's `add_messages` reducer. Messages accumulate during a session with no eviction.

### Planned: Hybrid Memory

**Within-session** (floating window):
- When history exceeds 15 messages, summarize the oldest 10 into ~200 tokens
- Preserve: decisions, preferences, tool outcomes
- Keep last 8 messages verbatim

**Cross-session** (RAG):
- Embed key decisions, preferences, and outcomes
- Retrieve relevant context via vector similarity when a new session starts
- The agent remembers: approved ICP, effective messaging angles, past strategy decisions

---

## 12. Multimodal Processing

### Planned Pipeline

Users will upload files (pitch decks, reports, screenshots) that the agent extracts strategic intelligence from.

**Phased rollout**:

| Phase | Formats | Value |
|-------|---------|-------|
| 1 | PDF + Images | Pitch decks, reports, screenshots |
| 2 | HTML + Word | Competitor websites, proposals |
| 3 | Excel | Structured data, contact imports |
| 4 | Video | Product demos, webinars |

**Architecture**: Upload -> S3/local storage -> format-specific extractor -> cached summary -> inject into agent context on demand.

**Progressive detail levels**:
- L0: Mention (~20 tokens) -- "User uploaded pitch_deck.pdf"
- L1: Summary (~300-700 tokens) -- Key points extracted
- L2: Deep dive (up to 4K tokens) -- Full extraction via tool call

---

## 13. Tool Routing

### Phase-Filtered Tools

Each specialist agent receives only its relevant tools:

| Agent | Tools | Schema Tokens |
|-------|-------|---------------|
| Strategy | 8 strategy tools | ~600 |
| Research | 7 research tools | ~500 |
| Quick Response | 0 tools | 0 |
| Monolithic (legacy) | 24 tools | ~2,500 |

This reduces schema tokens by 75% and eliminates irrelevant tool selection.

### Tool Registry Bridge

`api/agents/tools.py` bridges the existing `tool_registry` to LangGraph:

1. Each `ToolDefinition` from `TOOL_REGISTRY` is wrapped into a LangChain `StructuredTool`
2. A `tool_context_holder` (mutable list) carries `ToolContext` (tenant_id, user_id, document_id) into handlers
3. Dynamic Pydantic models are generated from JSON Schema `input_schema` for proper tool calling format
4. Flask `app.app_context()` is wrapped around handlers when database access is needed

### Tool Access Control

The subgraph tools nodes enforce whitelists:
- `strategy_tools_node` only allows tools in `STRATEGY_TOOL_NAMES`
- `research_tools_node` only allows tools in `RESEARCH_TOOL_NAMES`
- Unauthorized tool calls return error messages to the agent

---

## 14. Cost Controls

### Token Tracking

Every LLM call tracks input/output tokens and estimates cost:

```python
def _estimate_cost(model, input_tokens, output_tokens):
    MODEL_PRICING = {
        "claude-haiku-4-5-20251001": {"input_per_m": 0.80, "output_per_m": 4.0},
        "claude-sonnet-4-5-20241022": {"input_per_m": 3.0, "output_per_m": 15.0},
        "claude-opus-4-6": {"input_per_m": 15.0, "output_per_m": 75.0},
    }
```

Costs accumulate across all LLM calls in a turn and are reported in the `RUN_FINISHED` event.

### Cost Display Rules

- All user-facing displays show tokens/credits, never raw USD
- Only super_admin sees raw USD breakdown
- 1 credit = $0.001 USD

### Resource Gates

Before expensive operations, the agent emits a `resource` halt gate:
```python
resource_gate(
    question="Enrich 50 contacts?",
    estimated_tokens=5000,
    estimated_cost_usd="0.50",
    context="This will use web search and AI analysis for each contact."
)
```

Users see estimated cost and can approve, skip, or cancel.

### Model Selection Strategy

Quality over cost -- use the best model for the job:
- **Haiku**: Intent classification, quick Q&A, research queries
- **Sonnet**: Strategy document generation, complex analysis
- **Opus**: Complex multi-step reasoning (when warranted)

---

## 15. Feature Flags

### USE_LANGGRAPH Toggle

The migration from monolithic executor to LangGraph uses a feature flag for safe rollout:

| Flag | Effect |
|------|--------|
| `USE_LANGGRAPH=true` | Routes to `execute_graph_turn()` (LangGraph) |
| `USE_LANGGRAPH=false` | Routes to legacy `execute_agent_turn()` |

The integration layer (`api/agents/integration.py`) provides a drop-in replacement that checks the flag and delegates to the appropriate executor. Both paths produce identical SSE event streams, ensuring zero frontend changes during migration.

### Rollout Strategy

1. **Phase 1**: LangGraph behind flag, opt-in per tenant
2. **Phase 2**: Default on, legacy available as fallback
3. **Phase 3**: Legacy code removed

---

## 16. Sprint Roadmap

| Sprint | Capabilities | Status |
|--------|-------------|--------|
| **Sprint 11** | LangGraph StateGraph, prompt layering (L0/L1/L2), AG-UI events, tool adapter, feature flag toggle | Done |
| **Sprint 12** | Multi-agent orchestrator, intent classification, Strategy Agent subgraph, Research Agent subgraph | Done |
| **Sprint 13** | Halt gates (5 types + frequency control), generative UI events, shared state sync (JSON Patch), document edit events | Done |
| **Sprint 14** | Enrichment Agent, outreach message generation, multimodal Phase 1 (PDF + images) | Planned |
| **Sprint 15** | RAG memory, cross-session context retrieval, floating conversation window, Data Agent | Planned |
| **Sprint 16+** | Tiptap AI Toolkit (accept/reject edits), A2A protocol, Campaign Agent, video processing | Planned |

---

## Appendix: Data Flow Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     React Frontend                        │
│                                                          │
│  ChatMessages  StateSync  HaltGateUI  GenerativeUI       │
│       │            │          │            │              │
│       └────────────┴──────────┴────────────┘              │
│                        │                                  │
│                   SSE (AG-UI events)                      │
└────────────────────────┼─────────────────────────────────┘
                         │
┌────────────────────────┼─────────────────────────────────┐
│                  Flask API Layer                           │
│                        │                                  │
│              execute_graph_turn()                         │
│                        │                                  │
│              ┌─────────▼──────────┐                      │
│              │    Orchestrator     │                      │
│              │  (classify_node)    │                      │
│              └──┬──┬──┬──┬───────┘                      │
│                 │  │  │  │                                │
│    ┌────────┘  │  │  └────────┐                         │
│    ▼            ▼  ▼           ▼                          │
│ Strategy    Research  Quick   Passthrough                 │
│  Agent       Agent   Response  (future)                  │
│    │            │                                         │
│    ▼            ▼                                         │
│ Strategy    Research                                      │
│  Tools       Tools     ←── tool_registry handlers        │
│    │            │                                         │
│    ▼            ▼                                         │
│  SQLAlchemy  Web APIs                                     │
│  (PostgreSQL) (Search, Enrichment)                        │
└──────────────────────────────────────────────────────────┘
```
