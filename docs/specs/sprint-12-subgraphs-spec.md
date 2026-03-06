# Sprint 12: Multi-Agent Subgraphs Spec

> Sprint 12 builds on Sprint 11's LangGraph foundation to decompose the monolithic agent into specialist subgraphs with an orchestrator.

## Problem Statement

The current `graph.py` runs a single agent loop with all 24+ tools bound to every LLM call. This causes:
- **Prompt bloat**: Every call sends all tool schemas (~2.5K tokens) regardless of intent
- **No specialization**: The agent must reason about strategy, research, campaigns, and data in one context
- **No routing**: Simple questions get the same heavyweight processing as complex research tasks
- **Context pollution**: Research results, strategy edits, and contact queries all share one conversation

## Backlog Items

| ID | Title | Priority | Effort |
|----|-------|----------|--------|
| BL-253 | Strategy Agent Subgraph | Should Have | M |
| BL-254 | Research Agent Subgraph | Should Have | M |
| BL-255 | Orchestrator Graph | Should Have | L |

## Architecture

```
User Message
    |
    v
Orchestrator Graph (Haiku — intent classification)
    |
    +-- intent: "strategy_edit" --> Strategy Subgraph (Sonnet)
    |       Tools: update_strategy_section, append_to_section,
    |              set_extracted_field, track_assumption,
    |              check_readiness, set_icp_tiers,
    |              set_buyer_personas, get_strategy_document
    |
    +-- intent: "research" -------> Research Subgraph (Haiku/Sonnet)
    |       Tools: web_search, research_own_company,
    |              count_contacts, count_companies,
    |              list_contacts, filter_contacts,
    |              analyze_enrichment_insights
    |
    +-- intent: "quick_answer" ---> Direct response (Haiku, no tools)
    |
    +-- intent: "campaign" -------> Passthrough to existing graph (future)
```

### State Schema Extensions

```python
class AgentState(TypedDict):
    # Existing fields
    messages: Annotated[Sequence[BaseMessage], add_messages]
    tool_context: dict[str, Any]
    iteration: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: str
    model: str

    # New fields for multi-agent orchestration
    intent: str                    # Classified intent (strategy_edit, research, quick_answer, campaign)
    active_agent: str              # Which subgraph is currently running
    research_results: dict         # Research agent outputs, shared with strategy agent
    section_completeness: dict     # Strategy section status, shared across agents
```

## BL-253: Strategy Agent Subgraph

### User Stories

- As the AI strategist, I want a focused system prompt so my strategy edits are high quality with less token waste.
- As the system, I want strategy tools isolated so only strategy-related tools are available during document editing.

### Acceptance Criteria

```gherkin
Given a strategy-related message
When routed to Strategy Agent
Then:
  1. Only 8 strategy tools are available (not all 24+)
  2. System prompt is ~200 tokens (focused, not full monolith)
  3. Document editing via update_strategy_section works
  4. Section completeness tracking works via check_readiness
  5. Research results from shared state are accessible in context
  6. SSE events (tool_start, tool_result, chunk, section_update) stream correctly
```

### Technical Approach

- File: `api/agents/subgraphs/strategy.py`
- Subgraph with `agent_node` + `tools_node` (same pattern as current graph.py)
- Focused system prompt: role + strategy-specific instructions only
- Tool binding: only strategy tools from `STRATEGY_TOOLS` list
- Reads `research_results` from state for grounding
- Model: `claude-sonnet-4-5-20241022` for generation quality

### Strategy Tools (8 total)

| Tool | Source Module |
|------|-------------|
| `update_strategy_section` | `strategy_tools.py` |
| `append_to_section` | `strategy_tools.py` |
| `set_extracted_field` | `strategy_tools.py` |
| `track_assumption` | `strategy_tools.py` |
| `check_readiness` | `strategy_tools.py` |
| `set_icp_tiers` | `strategy_tools.py` |
| `set_buyer_personas` | `strategy_tools.py` |
| `get_strategy_document` | `strategy_tools.py` |

## BL-254: Research Agent Subgraph

### User Stories

- As the AI researcher, I want focused tools for web search and data queries so I produce better research results.
- As the system, I want research results stored in shared state so the strategy agent can use them.

### Acceptance Criteria

```gherkin
Given a research-related message
When routed to Research Agent
Then:
  1. Only 7 research tools are available
  2. Web search and company research work correctly
  3. Results are stored in state["research_results"]
  4. Contact/company queries return filtered data
  5. SSE events stream via AG-UI protocol
  6. Model selection: Haiku for simple queries, Sonnet for complex
```

### Technical Approach

- File: `api/agents/subgraphs/research.py`
- Same agent+tools subgraph pattern
- Focused prompt: research/discovery identity
- Stores results in `research_results` state field
- Model: starts with Haiku, orchestrator can escalate to Sonnet

### Research Tools (7 total)

| Tool | Source Module |
|------|-------------|
| `web_search` | `search_tools.py` |
| `research_own_company` | `company_research_tool.py` |
| `count_contacts` | `analyze_tools.py` |
| `count_companies` | `analyze_tools.py` |
| `list_contacts` | `analyze_tools.py` |
| `filter_contacts` | `campaign_tools.py` |
| `analyze_enrichment_insights` | `strategy_refinement_tools.py` |

## BL-255: Orchestrator Graph

### User Stories

- As a user, I want my messages automatically routed to the right specialist so I get faster, better responses.
- As the system, I want intent classification under 500ms so routing feels instant.

### Acceptance Criteria

```gherkin
Given any user message
When processed by the orchestrator
Then:
  1. Intent classified into: quick_answer, strategy_edit, research, campaign
  2. Correct specialist subgraph selected based on intent
  3. Relevant context (research_results, section_completeness) passed to agent
  4. Results synthesized and streamed via SSE
  5. Multi-step handoffs work (research -> strategy)
  6. Haiku routing completes in <500ms
  7. Fallback: unclassified intent routes to existing monolithic graph
```

### Technical Approach

- File: `api/agents/orchestrator.py` (parent graph)
- File: `api/agents/intent.py` (intent classification)
- Parent StateGraph with conditional routing edges
- Intent node: Haiku call with ~100 token prompt, returns intent category
- Agent nodes: Strategy subgraph, Research subgraph, passthrough node
- Context distribution: orchestrator injects relevant state into subgraph
- Result synthesis: subgraph output flows back through orchestrator to user

### Intent Classification

```python
INTENT_PROMPT = """Classify the user's intent into exactly one category:
- strategy_edit: Writing, updating, or reviewing strategy document sections
- research: Web search, company research, market analysis, data queries
- quick_answer: Simple questions about the strategy, status checks, greetings
- campaign: Message generation, outreach planning, contact filtering for campaigns

Respond with ONLY the category name, nothing else."""
```

### Routing Logic

```
classify_intent --> route_to_agent
                       |
    +------------------+------------------+------------------+
    |                  |                  |                  |
strategy_agent    research_agent    quick_response    passthrough
    |                  |                  |                  |
    +------------------+------------------+------------------+
                       |
                   synthesize --> END
```

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `api/agents/subgraphs/__init__.py` | CREATE | Package init |
| `api/agents/subgraphs/strategy.py` | CREATE | Strategy agent subgraph |
| `api/agents/subgraphs/research.py` | CREATE | Research agent subgraph |
| `api/agents/orchestrator.py` | CREATE | Top-level orchestrator graph |
| `api/agents/intent.py` | CREATE | Intent classification logic |
| `api/agents/state.py` | MODIFY | Add subgraph state fields |
| `api/agents/graph.py` | MODIFY | Wire orchestrator as alternative entry point |
| `tests/unit/test_subgraphs.py` | CREATE | Unit tests for subgraphs and orchestrator |

## Test Plan

1. **Strategy subgraph**: Verify only strategy tools are bound; mock LLM call returns tool_use for update_strategy_section; verify SSE events emitted
2. **Research subgraph**: Verify only research tools are bound; mock LLM call returns tool_use for web_search; verify research_results stored in state
3. **Intent classification**: Test each intent category with sample messages; verify Haiku model used; verify classification accuracy
4. **Orchestrator routing**: Test end-to-end routing from user message to correct subgraph; verify context passing; verify result synthesis
5. **Fallback**: Verify unclassified intents route to existing graph
6. **SSE streaming**: Verify all subgraph events flow through orchestrator to SSE output

## Non-Goals (Sprint 12)

- Outreach Agent subgraph (future sprint)
- Data Agent subgraph (future sprint)
- Parallel fan-out with Send() API (future — requires multiple agents running simultaneously)
- A2A protocol between agents (future)
- LangGraph interrupt() for halt gates (future — requires checkpoint persistence)
