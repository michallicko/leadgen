# Sprint 11 — Foundation Spec

> BL-250 (LangGraph Migration), BL-251 (Prompt Layering & Caching), BL-252 (AG-UI Protocol)

## Problem Statement

### BL-250: LangGraph Migration
The current agent executor (`api/services/agent_executor.py`) is a monolithic while-loop that makes raw `requests.post()` calls to the Anthropic API. It has no structured state management, no halt gates for user approval at decision points, and no multi-model routing. This makes it impossible to implement features like "pause and ask the user before proceeding" or "use a cheaper model for simple routing decisions." The loop also tightly couples tool execution, streaming, and conversation management into a single 408-line function.

### BL-251: Prompt Layering & Caching
The system prompt is rebuilt from scratch on every API call by `playbook_service.build_system_prompt()`. This 614-line function concatenates identity, rules, enrichment data, phase instructions, and page context into one massive string. There is no prompt caching — every call sends the full ~3-5K token system prompt, wasting input tokens. There is also no conversation summarization — when history exceeds 20 messages, older messages are simply truncated rather than summarized, losing context.

### BL-252: AG-UI Protocol Adoption
The frontend-backend communication uses custom SSE event types (`chunk`, `done`, `tool_start`, `tool_result`, `thinking`, `analysis_start`, `analysis_chunk`, `analysis_done`). This custom protocol requires maintaining bespoke parsing logic in both `useSSE.ts` and `ChatProvider.tsx`. The AG-UI protocol provides a standardized event vocabulary that enables future features like shared state synchronization and tool call approval flows.

---

## Acceptance Criteria

### BL-250: LangGraph Migration

**AC-1: StateGraph replaces while-loop**
- Given the feature flag `LANGGRAPH_ENABLED=true` is set
- When a user sends a chat message
- Then the request is handled by a LangGraph StateGraph instead of the monolithic `execute_agent_turn()` loop

**AC-2: Typed state schema**
- Given a LangGraph agent turn is executing
- When the agent processes messages and tool calls
- Then all state is managed through a typed `AgentState` TypedDict with fields: messages, tool_calls, phase, model, token_usage, iteration_count

**AC-3: Multi-model routing**
- Given a message is being processed
- When the router node selects a model
- Then simple Q&A/routing uses `claude-haiku-4-5-20251001`, generation tasks use `claude-sonnet-4-5-20241022`, and complex reasoning uses `claude-opus-4-6`

**AC-4: Interrupt halt gates**
- Given the agent reaches a key decision point (scope selection, ICP direction, draft review)
- When the decision requires user input
- Then the graph uses LangGraph `interrupt()` to pause execution and emit a halt event to the frontend

**AC-5: Feature flag fallback**
- Given `LANGGRAPH_ENABLED` is not set or set to `false`
- When a user sends a chat message
- Then the old `execute_agent_turn()` function handles the request (no breaking change)

**AC-6: SSE streaming preserved**
- Given the LangGraph executor is active
- When the agent generates text or executes tools
- Then SSE events are emitted in real-time to the frontend (no degradation in streaming UX)

### BL-251: Prompt Layering & Caching

**AC-7: Layered prompt structure**
- Given a chat request is being processed
- When the system prompt is built
- Then it is composed of 4 layers: Layer 0 (Identity, ~800 tokens), Layer 1 (Capabilities, ~1-2K tokens), Layer 2 (Context, ~1-5K tokens), Layer 3 (Conversation history)

**AC-8: Anthropic prompt caching on static layers**
- Given Layers 0 and 1 are assembled
- When the API call is made
- Then these layers include `cache_control: {"type": "ephemeral"}` markers for Anthropic's prompt caching (5-min TTL)

**AC-9: Phase-filtered tool routing**
- Given the user is in the "strategy" phase
- When tools are selected for the API call
- Then only strategy-relevant tools (~12) are included, not all 24+ registered tools

**AC-10: Conversation summarization**
- Given the conversation history exceeds 15 messages
- When messages are prepared for the API call
- Then the oldest 10 messages are summarized into a ~200-token summary, and only the summary + 5 most recent messages are sent

### BL-252: AG-UI Protocol

**AC-11: AG-UI event types on backend**
- Given the agent is streaming a response
- When events are emitted
- Then they use AG-UI event types: `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END`, `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END`, `STATE_DELTA`, `RUN_STARTED`, `RUN_FINISHED`

**AC-12: Frontend consumes AG-UI events**
- Given the frontend receives SSE events
- When `useSSE.ts` parses them
- Then both legacy event types and AG-UI event types are handled (backward compatible during migration)

**AC-13: STATE_DELTA for shared state**
- Given the agent updates strategy content or research results
- When a tool execution modifies shared state
- Then a `STATE_DELTA` event is emitted with the delta payload (field path + new value)

**AC-14: Backward compatibility**
- Given the feature flag `LANGGRAPH_ENABLED=false`
- When the old executor runs
- Then the original SSE event types are emitted (no change for legacy path)

---

## Data Model Changes

No database schema changes. All changes are in-memory state management and API protocol.

---

## API Contract Changes

### SSE Event Types (New — AG-UI Protocol)

When `LANGGRAPH_ENABLED=true`, the `/api/playbook/chat` POST endpoint emits AG-UI events:

```
data: {"type": "RUN_STARTED", "run_id": "uuid", "thread_id": "uuid"}

data: {"type": "TEXT_MESSAGE_START", "message_id": "uuid", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "uuid", "delta": "Hello"}

data: {"type": "TEXT_MESSAGE_END", "message_id": "uuid"}

data: {"type": "TOOL_CALL_START", "tool_call_id": "id", "tool_name": "web_search", "tool_call_type": "function"}

data: {"type": "TOOL_CALL_ARGS", "tool_call_id": "id", "delta": "{\"query\": ...}"}

data: {"type": "TOOL_CALL_END", "tool_call_id": "id"}

data: {"type": "STATE_DELTA", "delta": [{"op": "replace", "path": "/document_changed", "value": true}]}

data: {"type": "RUN_FINISHED", "run_id": "uuid", "thread_id": "uuid"}
```

Legacy events (`chunk`, `done`, `tool_start`, `tool_result`) continue to work when `LANGGRAPH_ENABLED=false`.

---

## Component Design

### New Directory: `api/agents/`

```
api/agents/
  __init__.py          # Package init, exports create_agent_graph()
  state.py             # AgentState TypedDict
  graph.py             # StateGraph definition + compile
  nodes.py             # Node functions (route, call_model, execute_tools, halt)
  tools.py             # Tool adapter: ToolRegistry → LangGraph @tool format
  prompts.py           # Layered prompt assembly (replaces playbook_service.build_system_prompt)
  streaming.py         # LangGraph → SSE adapter (AG-UI events)
```

### State Schema (`state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    phase: str
    model: str
    tool_calls: list[dict]
    iteration_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: str
    should_halt: bool
    halt_reason: str | None
    document_changed: bool
    run_id: str
```

### Graph Structure (`graph.py`)

```
START → route → call_model → check_tools
                                ├─ (has tools) → execute_tools → check_halt
                                │                                   ├─ (halt) → END
                                │                                   └─ (continue) → call_model
                                └─ (no tools) → END
```

### Prompt Layers (`prompts.py`)

| Layer | Content | Tokens | Cached |
|-------|---------|--------|--------|
| 0 | Identity (CMO role, critical rules, tone) | ~800 | Yes |
| 1 | Capabilities (phase-filtered tool descriptions) | ~1-2K | Yes |
| 2 | Context (objective, document content, enrichment, phase instructions) | ~1-5K | No |
| 3 | Conversation (summary + recent window) | Variable | No |

### Phase → Tool Mapping (`tools.py`)

| Phase | Tools |
|-------|-------|
| strategy | web_search, get_strategy_document, update_strategy_section, set_extracted_field, append_to_section, track_assumption, check_readiness, research_company, get_company_context, analyze_competitors, estimate_enrichment_cost, start_enrichment |
| contacts | get_contacts, filter_contacts, get_company_details, estimate_enrichment_cost, start_enrichment, get_strategy_document, web_search, analyze_icp_fit, bulk_select_contacts |
| messages | get_messages, generate_message, update_message_status, get_strategy_document, get_contact_details, web_search |
| campaign | get_campaigns, create_campaign, add_contacts_to_campaign, get_strategy_document, web_search |

### Streaming Adapter (`streaming.py`)

Converts LangGraph events to AG-UI SSE format:
- `on_chat_model_stream` → `TEXT_MESSAGE_CONTENT`
- `on_tool_start` → `TOOL_CALL_START`
- `on_tool_end` → `TOOL_CALL_END`
- Custom state updates → `STATE_DELTA`

---

## Migration Strategy

1. **Feature flag**: `LANGGRAPH_ENABLED` env var (default: `false`)
2. **Dual path in `_stream_response()`**: Check flag, route to LangGraph or legacy executor
3. **Both paths produce SSE**: Legacy emits old events, LangGraph emits AG-UI events
4. **Frontend handles both**: `dispatchEvent()` in `useSSE.ts` maps both old and AG-UI events to the same callbacks
5. **Gradual rollout**: Enable on staging first, monitor for issues, then enable on production
6. **Old code preserved**: `agent_executor.py` is not modified, only the routing in playbook_routes.py changes

---

## Test Plan

### Unit Tests
- `tests/unit/test_agent_state.py` — AgentState initialization, message accumulation
- `tests/unit/test_agent_prompts.py` — Layered prompt assembly, caching markers, phase filtering
- `tests/unit/test_agent_tools.py` — Tool adapter: ToolRegistry → LangGraph format, phase filtering
- `tests/unit/test_agent_streaming.py` — AG-UI event generation from LangGraph events
- `tests/unit/test_conversation_summary.py` — Summarization trigger at >15 messages

### Integration Tests (manual, staging)
- Send chat message with `LANGGRAPH_ENABLED=true` → verify SSE stream works
- Verify tool calls execute correctly through LangGraph
- Verify prompt caching reduces token usage (check LLM usage logs)
- Verify conversation summarization kicks in after 15+ messages
