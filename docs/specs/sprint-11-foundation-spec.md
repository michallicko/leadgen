# Sprint 11 — Foundation Spec (BL-250, BL-251, BL-252)

> Consolidated spec covering LangGraph migration, prompt layering with caching, and AG-UI protocol adoption.

---

## BL-250: LangGraph Migration

### Problem Statement

The current agent executor (`api/services/agent_executor.py`) is a monolithic while-loop that directly calls the Anthropic Messages API via `requests.post()`. It has:

- **Implicit state machine** — the loop/nudge logic is ad-hoc, not declarative
- **No halt gates** — no way to pause execution and ask the user for a decision
- **No observability** — no tracing, no per-step cost breakdown, no replay
- **No multi-model routing** — every LLM call uses the same model (Haiku)
- **Tight coupling** — tool execution, SSE streaming, and LLM calls are interleaved in one function

### User Stories

- As a developer, I want the agent flow defined as a directed graph so I can reason about state transitions, add new nodes, and visualize execution flow.
- As a user, I want the agent to pause and ask me to choose when it finds multiple options (halt gates), so I stay in control of strategic decisions.
- As an operator, I want per-step tracing so I can debug failed conversations and optimize token spend.

### Acceptance Criteria

**Given** a user sends a chat message
**When** the message is processed by the new LangGraph-based agent
**Then** the response streams SSE events (tool_start, tool_result, chunk, done) identical to the current behavior

**Given** the LangGraph agent is running
**When** it executes tools (update_strategy_section, web_search, etc.)
**Then** all existing tools work without modification (same input/output contracts)

**Given** the agent encounters an error during tool execution
**When** the error is caught by the graph
**Then** the error is surfaced as a tool_result error event (same as today)

**Given** the agent loop exceeds 25 iterations or 180 seconds
**When** the timeout/iteration guard fires
**Then** the user receives a timeout message and a done event (same as today)

### Success Metrics

- Zero behavioral regression in chat — same streaming, same tool calls, same output
- All existing unit tests pass without modification
- Agent executor is a LangGraph StateGraph instead of a while-loop

### Technical Approach

#### Architecture

```
Flask Route (playbook_routes.py)
  └── _stream_agent_response()
        └── LangGraph StateGraph.stream()
              ├── Node: "agent" (LLM call + tool detection)
              ├── Node: "tools" (tool execution)
              ├── Edge: agent → tools (if tool_use)
              ├── Edge: tools → agent (loop back)
              └── Edge: agent → END (if end_turn)
```

The LangGraph graph replaces the `execute_agent_turn()` generator. The Flask route wraps the graph's async iterator into SSE events, same as today.

#### Files to Create

| File | Purpose |
|------|---------|
| `api/agents/__init__.py` | Package init |
| `api/agents/state.py` | Typed state schema (AgentState TypedDict) |
| `api/agents/tools.py` | LangGraph tool wrappers around existing tool_registry handlers |
| `api/agents/graph.py` | StateGraph definition — agent node, tools node, conditional edges |

#### Files to Modify

| File | Change |
|------|--------|
| `api/services/agent_executor.py` | Keep as-is for now (backward compat); new code in `api/agents/graph.py` |
| `api/routes/playbook_routes.py` | `_stream_agent_response()` calls the new graph instead of `execute_agent_turn()` |
| `requirements.txt` | Add `langgraph`, `langchain-anthropic`, `langchain-core` |

#### Migration Strategy

1. Build the LangGraph graph alongside the existing executor (no deletion)
2. Route `_stream_agent_response()` to use the new graph
3. Keep `execute_agent_turn()` as fallback (feature flag or config toggle)
4. Once validated, deprecate the old executor in a follow-up sprint

#### Risks

- LangGraph uses async patterns; Flask is sync. Mitigation: use `graph.stream()` (sync iterator) not `graph.astream()`.
- LangGraph's ChatAnthropic model wrapper may conflict with our custom AnthropicClient. Mitigation: use LangGraph with `langchain-anthropic` ChatAnthropic which handles prompt caching natively.
- Nudge logic (continuation for incomplete strategy sections) needs to be preserved. Mitigation: implement as a conditional edge in the graph.

#### Test Plan

- Run `make test-changed` — all existing tests must pass
- Manual test: send a chat message, verify streaming works, tool calls work, section updates stream
- Manual test: verify timeout behavior (agent should stop after 180s)
- Manual test: verify nudge behavior (strategy generation continues if sections incomplete)

---

## BL-251: Prompt Layering & Caching

### Problem Statement

The current system prompt is rebuilt from scratch on every `query_with_tools()` call within the agent loop. For a 25-iteration turn, this means sending ~2,500 static tokens 25 times = ~62,500 wasted input tokens. With Anthropic's prompt caching, the static portion would be cached after the first call, reducing input costs by 50-70%.

The system prompt in `playbook_service.py` (`build_system_prompt()`) concatenates ~14 sections into one massive string with no separation between static and dynamic content, making caching impossible.

### User Stories

- As a product owner, I want to reduce LLM API costs by 50-70% per agent turn so the product is economically viable at scale.
- As a developer, I want the system prompt modularized into layers so I can update identity rules without touching dynamic context logic.

### Acceptance Criteria

**Given** the agent runs a multi-iteration turn (e.g., 5+ tool calls)
**When** the system prompt is sent to Anthropic
**Then** the static identity layer (~800 tokens) is marked with `cache_control: {"type": "ephemeral"}` and only sent fresh on the first call

**Given** prompt caching is active
**When** I compare token costs before and after
**Then** cached input tokens appear in the usage response and total input cost decreases by 40%+ for multi-iteration turns

**Given** I modify the phase instructions (dynamic layer)
**When** the agent runs
**Then** the dynamic layer reflects the change while the static layer remains cached

### Success Metrics

- `cache_creation_input_tokens` and `cache_read_input_tokens` appear in Anthropic API responses
- Per-turn cost reduction of 40-70% on multi-iteration turns (measured via API usage)
- System prompt is split into 3 clear layers in code

### Technical Approach

#### Prompt Layers

```
Layer 0: Identity (~800 tokens, cacheable)
  - Role definition, personality, critical rules
  - Response style/tone guidelines
  - Language override
  → cache_control: {"type": "ephemeral"}

Layer 1: Capabilities (~500-1500 tokens, semi-cacheable)
  - Tool usage rules
  - Document editing rules
  - Phase-specific instructions
  → cache_control: {"type": "ephemeral"} (changes per phase, cached within phase)

Layer 2: Context (dynamic, ~1-5K tokens)
  - Current strategy document state
  - Section completeness
  - Enrichment data summary
  - User objective
  - Page context hint
  → No caching (changes every call)
```

#### Files to Create

| File | Purpose |
|------|---------|
| `api/agents/prompts/__init__.py` | Package init |
| `api/agents/prompts/identity.py` | Static identity prompt (Layer 0) |
| `api/agents/prompts/context.py` | Dynamic context builder (Layer 2) |

#### Files to Modify

| File | Change |
|------|--------|
| `api/services/playbook_service.py` | Extract static sections into identity.py; `build_system_prompt()` returns layered structure |
| `api/agents/graph.py` | Use layered prompts with cache_control headers in LLM calls |

#### Migration Strategy

1. Extract static prompt content from `build_system_prompt()` into `identity.py`
2. Refactor `build_system_prompt()` to return a list of content blocks (not a single string) with cache_control markers
3. Update the LangGraph ChatAnthropic model to use the layered prompt structure
4. The old `build_system_prompt()` function signature stays compatible for the sync fallback path

#### Risks

- Anthropic prompt caching requires minimum 1024 tokens in the cached prefix. Our ~800 token identity layer may be too small alone. Mitigation: combine Layer 0 + Layer 1 for caching (>1300 tokens combined).
- `langchain-anthropic` ChatAnthropic must support `cache_control` in system message blocks. Mitigation: verify in langchain-anthropic docs; if not, use raw Anthropic client for the system prompt.

#### Test Plan

- Run `make test-changed` — existing tests pass
- Manual test: inspect API response for `cache_creation_input_tokens` and `cache_read_input_tokens` fields
- Compare token costs: run same conversation before/after, check total_input_tokens reduction

---

## BL-252: AG-UI Protocol Adoption

### Problem Statement

The current SSE event protocol is custom and ad-hoc. Event types like `chunk`, `tool_start`, `tool_result`, `section_update`, `analysis_start`, `analysis_chunk`, `analysis_done`, `research_status`, `section_content_start`, `section_content_chunk`, `section_content_done` were added incrementally as features were built. There is no standard — every new feature requires inventing a new event type on both backend and frontend.

AG-UI (Agent-User Interaction Protocol) is an open standard for agent-frontend communication adopted by LangChain, Microsoft, Oracle, and CrewAI. It provides a standardized event taxonomy that maps directly to our existing events.

### User Stories

- As a developer, I want to use a standardized event protocol so I don't have to invent new event types for each feature.
- As a developer, I want AG-UI compatibility so the frontend can potentially use off-the-shelf AG-UI client libraries in the future.
- As a user, I want a richer streaming experience (run lifecycle, state snapshots) enabled by AG-UI events.

### Acceptance Criteria

**Given** the agent streams a response
**When** the frontend receives SSE events
**Then** events follow the AG-UI taxonomy: `RUN_STARTED`, `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END`, `TOOL_CALL_START`, `TOOL_CALL_END`, `RUN_FINISHED`

**Given** the frontend receives AG-UI events
**When** it processes them in ChatProvider
**Then** existing UI behavior is preserved (streaming text, tool cards, section updates, thinking indicator)

**Given** backward compatibility is needed
**When** the migration is in progress
**Then** the backend supports a transition period where both old and new event formats are emitted (dual-emit)

### Success Metrics

- All SSE events emitted by the backend conform to AG-UI event schema
- Frontend ChatProvider and useSSE hook updated to consume AG-UI events
- Zero visual regression in chat UI

### Technical Approach

#### Event Mapping

| AG-UI Event | Replaces | Data |
|-------------|----------|------|
| `RUN_STARTED` | (new) | `{type, threadId, runId}` |
| `TEXT_MESSAGE_START` | `analysis_start`, `section_content_start` | `{type, messageId}` |
| `TEXT_MESSAGE_CONTENT` | `chunk`, `analysis_chunk`, `section_content_chunk` | `{type, messageId, delta}` |
| `TEXT_MESSAGE_END` | `analysis_done`, `section_content_done`, implicit done text | `{type, messageId}` |
| `TOOL_CALL_START` | `tool_start` | `{type, toolCallId, toolCallName}` |
| `TOOL_CALL_END` | `tool_result` | `{type, toolCallId, result}` |
| `STATE_DELTA` | `section_update` | `{type, delta: [...patches]}` |
| `STATE_SNAPSHOT` | (new) | `{type, snapshot: {...state}}` |
| `RUN_FINISHED` | `done` | `{type, threadId, runId}` |

#### Custom Extensions (AG-UI allows them)

| Event | Purpose |
|-------|---------|
| `CUSTOM:research_status` | Research polling status (in_progress/completed/timeout) |
| `CUSTOM:thinking_status` | Active tool name / thinking text for indicator |

#### Files to Create

| File | Purpose |
|------|---------|
| `api/agents/events.py` | AG-UI event builder functions |

#### Files to Modify

| File | Change |
|------|--------|
| `api/agents/graph.py` | Emit AG-UI events from graph nodes |
| `api/routes/playbook_routes.py` | `_stream_agent_response()` emits AG-UI wire format |
| `frontend/src/hooks/useSSE.ts` | Parse AG-UI event types, dispatch to callbacks |
| `frontend/src/providers/ChatProvider.tsx` | Update callbacks to handle AG-UI event payloads |
| `requirements.txt` | Add `ag-ui-protocol` (if useful for event schemas; optional) |

#### Migration Strategy — Dual-Emit

During transition, the backend emits BOTH old and new event formats:

```python
# Emit AG-UI event
yield format_agui_event("TEXT_MESSAGE_CONTENT", {"messageId": msg_id, "delta": text})
# Also emit old event for backward compat
yield format_sse_event("chunk", {"text": text})
```

The frontend can be updated to consume AG-UI events first, then the old events are removed in a follow-up.

For Sprint 11, we will:
1. Emit AG-UI events from the LangGraph graph
2. Update frontend to consume AG-UI events
3. Remove old event emission (clean break — no dual-emit needed since we control both ends)

#### Risks

- `ag-ui-langgraph` package may not support Flask (it targets FastAPI). Mitigation: build a thin Flask adapter that yields AG-UI events from the LangGraph stream, or emit events manually without the package.
- Event schema changes may break the frontend if not updated simultaneously. Mitigation: deploy backend + frontend together; they're in the same repo.

#### Test Plan

- Run `make test-changed` — existing tests pass
- Run `cd frontend && npx tsc --noEmit` — TypeScript compiles
- Manual test: send chat message, verify streaming text appears, tool cards appear, section updates work
- Manual test: verify ThinkingIndicator works (shows tool names during execution)
- Manual test: verify document changes are detected and refreshed after AI edits

---

## UX Impact (PD Review)

### What Changes for the User

**Nothing visible changes in Sprint 11.** This is a backend infrastructure migration. The same SSE events flow to the same React components.

### What Changes for Development

- AG-UI event types are standardized — future features (halt gates, generative UI, inline approvals) will use AG-UI events
- The useSSE hook event dispatcher becomes cleaner (AG-UI events have consistent structure)
- LangGraph graph visualization enables debugging agent flow without reading code

### Chat Experience Changes

| Aspect | Before | After |
|--------|--------|-------|
| Text streaming | `chunk` events | `TEXT_MESSAGE_CONTENT` events (same UX) |
| Tool calls | `tool_start`/`tool_result` | `TOOL_CALL_START`/`TOOL_CALL_END` (same UX) |
| Section updates | `section_update` + `section_content_*` | `STATE_DELTA` (same UX) |
| Run lifecycle | Implicit | `RUN_STARTED`/`RUN_FINISHED` (enables future progress UI) |

### Error States and Loading States

No changes. The ThinkingIndicator, streaming text accumulation, and error handling remain identical. The `RUN_STARTED` event could enable a future "run in progress" indicator, but this is not implemented in Sprint 11.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `langgraph` | latest | StateGraph, conditional edges, tool nodes |
| `langchain-anthropic` | latest | ChatAnthropic model wrapper with prompt caching |
| `langchain-core` | latest | Base types (messages, tools, callbacks) |

The `ag-ui-langgraph` package will be evaluated but may not be needed if we emit AG-UI events manually (simpler, fewer dependencies).

---

## Implementation Order

1. **BL-250** first — LangGraph graph replaces agent_executor
2. **BL-251** second — layered prompts with caching require the LangGraph model wrapper
3. **BL-252** third — AG-UI events emitted from the graph require both LangGraph and the new prompt structure
