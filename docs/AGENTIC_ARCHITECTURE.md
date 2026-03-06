# Agentic Architecture Reference

> Developer reference for the agentic features in leadgen-pipeline.
> For design rationale and decision history, see `docs/plans/2026-03-06-agent-prompt-architecture.md`.
> For the visual architecture diagram, see `docs/plans/2026-03-06-agent-architecture-diagram.html`.

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Agent Taxonomy](#2-agent-taxonomy)
3. [LangGraph Architecture](#3-langgraph-architecture)
4. [Prompt Architecture](#4-prompt-architecture)
5. [Communication Protocols](#5-communication-protocols)
6. [Memory and Context Management](#6-memory-and-context-management)
7. [Multimodal Processing](#7-multimodal-processing)
8. [Enrichment System](#8-enrichment-system)
9. [Operational Concerns](#9-operational-concerns)
10. [Sprint Roadmap](#10-sprint-roadmap)
11. [Developer Guide](#11-developer-guide)

---

## 1. System Overview

### What the System Does

The agentic system powers the **Playbook chat** -- a conversational AI interface that guides users through the full Go-To-Market (GTM) workflow: developing strategy, researching prospects, enriching contacts, generating outreach messages, and managing campaigns.

The Playbook implements an 8-phase GTM workflow:

| # | Phase | Purpose |
|---|-------|---------|
| 1 | Contacts | Import and organize target contacts/companies |
| 2 | Strategy | Develop GTM strategy with AI assistance |
| 3 | Playbook | Refine ICP, personas, messaging framework |
| 4 | Enrichment | Run L1/L2/Person enrichment pipeline |
| 5 | Messages | Generate personalized outreach messages |
| 6 | Campaigns | Configure campaign structure and templates |
| 7 | Generation | Bulk message generation with cost estimation |
| 8 | Ready | Final review, approval gate, export |

### How It Fits Into the Product

```
User
  |
  v
Playbook Chat (ChatSidebar / ChatInput)
  |
  v
ChatProvider (React context, SSE streaming)
  |
  v
POST /api/playbook/chat
  |
  v
playbook_service.build_system_prompt() --> agent_executor.execute_agent_turn()
  |                                           |
  v                                           v
System prompt assembly                   Tool-use loop (up to 25 iterations)
  |                                           |
  v                                           v
Claude API (Haiku/Sonnet/Opus)           tool_registry -> strategy_tools, etc.
  |
  v
SSE events --> ChatProvider --> UI updates
```

### Current State vs Target

| Aspect | Current (Sprint 10) | Target (Sprint 20) |
|--------|--------------------|--------------------|
| Agent executor | Monolithic loop (`agent_executor.py`) | LangGraph StateGraph with subgraphs |
| Tools | All 24 sent every call | Phase-filtered (6-12 per call) |
| Prompts | Full rebuild per call (8-20K tokens) | Layered with cache_control (3-7K tokens) |
| History | Hard window (20 messages, no summarization) | RAG + floating window with compaction |
| Streaming | Custom SSE events | AG-UI standardized events |
| Halt gates | Not implemented | LangGraph `interrupt()` with approval UI |
| Multi-model | Single model per call | Haiku for routing, Sonnet for generation, Opus for reasoning |
| Agent-to-agent | None | A2A protocol between specialist agents |

---

## 2. Agent Taxonomy

### Current: Monolithic Agent

Today, a single `agent_executor.py` loop handles all tasks -- research, strategy writing, enrichment, and campaign planning. All 24 tools are available on every call regardless of context.

### Target: Orchestrator + Specialist Agents

```
User <-> Orchestrator (Chat Agent)
           |-- Strategy Agent        (playbook editing, section generation, ICP/persona)
           |-- Research Agent        (web search, company research, enrichment coordination)
           |     |-- Company Profiler      (search_web, scrape_website, enrich_company_api)
           |     |-- Contact Enricher      (enrich_contact_api, search_linkedin, verify_email)
           |     |-- Market Analyst        (search_web, analyze_document, search_news)
           |     |-- Document Processor    (extract_pdf, extract_excel, analyze_image)
           |-- Outreach Agent        (message generation, personalization, campaign planning)
           |-- Data Agent            (contact management, enrichment pipeline, CRM queries)
```

### Agent Responsibilities

**Orchestrator Agent**
- Intent detection: classifies user message into action category
- Agent selection: routes to the appropriate specialist
- Context routing: passes only relevant context to sub-agents
- Result synthesis: combines specialist outputs into user-facing response
- Halt gates: decides when to pause and confirm with the user

**Strategy Agent** (Sprint 12, BL-253)
- Tools: `update_strategy_section`, `append_to_section`, `set_extracted_field`, `track_assumption`, `check_readiness`, `set_icp_tiers`, `set_buyer_personas`, `web_search`, `research_own_company`, `get_strategy_document`, `count_contacts`, `count_companies`
- System prompt: focused (~200 tokens) on strategy consulting
- Model: Sonnet for generation, Haiku for quick answers

**Research Agent** (Sprint 12, BL-254)
- Tools: `web_search`, `research_own_company`, `analyze_document`, `analyze_image`
- Orchestrates sub-agents for parallel research (Company Profiler + Contact Enricher)
- Model: Haiku for coordination, Sonnet for synthesis

**Outreach Agent** (Sprint 19, BL-1002)
- Tools: `create_campaign`, `filter_contacts`, `get_strategy_document`, `list_contacts`
- References ICP, personas, and strategy for message grounding
- Model: Sonnet for message generation

**Data Agent** (Sprint 20, BL-1004)
- Tools: `filter_contacts`, `apply_icp_filters`, `get_enrichment_gaps`, `estimate_enrichment_cost`, `start_enrichment`, `analyze_enrichment_insights`
- Manages enrichment pipeline orchestration from chat
- Model: Haiku for queries, Sonnet for analysis

### Orchestration Patterns

1. **Sequential handoff**: Research Agent completes --> results pass to Strategy Agent
2. **Parallel fan-out**: Company Profiler + Contact Enricher run simultaneously (via LangGraph `Send()`)
3. **Hierarchical delegation**: Research Agent orchestrates its own sub-agents

---

## 3. LangGraph Architecture

### Migration Status

**Status: Decided, not yet implemented (Sprint 11, BL-250)**

LangGraph replaces the custom `agent_executor.py` with a `StateGraph`. The migration is internal -- no API changes, no frontend changes initially.

### StateGraph Design

```python
from langgraph.graph import StateGraph, interrupt

# Each agent = a subgraph
# Orchestrator = parent graph with conditional edges

graph = StateGraph(AgentState)

# Nodes
graph.add_node("research", research_node)      # Haiku
graph.add_node("scope_gate", scope_gate_node)   # interrupt()
graph.add_node("position", position_node)       # Sonnet
graph.add_node("direction_gate", direction_gate_node)  # interrupt()
graph.add_node("draft", draft_node)             # Sonnet
graph.add_node("review_gate", review_gate_node) # interrupt()
graph.add_node("finalize", finalize_node)       # Haiku

# Conditional edges
graph.add_conditional_edges("research", check_multiple_scopes,
    {"multiple": "scope_gate", "single": "position"})
graph.add_conditional_edges("position", check_multiple_icps,
    {"multiple": "direction_gate", "single": "draft"})

graph.add_edge("scope_gate", "position")
graph.add_edge("direction_gate", "draft")
graph.add_edge("draft", "review_gate")
graph.add_edge("review_gate", "finalize")
```

### Typed State Schema

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    research_results: dict | None
    scope: str | None
    icp_direction: str | None
    draft_approved: bool
    phase: str                    # strategy, contacts, messages, campaign
    tool_executions: list[dict]
    total_tokens: int
    total_cost_usd: float
```

### How `interrupt()` Works

LangGraph's `interrupt()` pauses graph execution, serializes state, and resumes when the user responds.

```python
def scope_gate(state):
    """Pause and ask user which product to focus on."""
    products = state["research_results"]["products"]
    if len(products) > 1:
        decision = interrupt({
            "question": f"Found {len(products)} products. Focus on which?",
            "options": [p["name"] for p in products],
            "gate_type": "scope"
        })
        state["scope"] = decision
    return state
```

The graph pauses at `interrupt()`, serializes state to the checkpointer, and resumes when the user's choice arrives as input. No custom protocol needed.

### Subgraph Pattern

Each specialist agent is implemented as a LangGraph subgraph. The orchestrator graph invokes subgraphs via node functions:

```python
# Orchestrator graph
orchestrator = StateGraph(OrchestratorState)
orchestrator.add_node("strategy_agent", strategy_subgraph)
orchestrator.add_node("research_agent", research_subgraph)
orchestrator.add_node("outreach_agent", outreach_subgraph)
orchestrator.add_node("data_agent", data_subgraph)

# Conditional routing based on intent
orchestrator.add_conditional_edges("intent_classifier", route_to_agent, {
    "strategy_edit": "strategy_agent",
    "research_task": "research_agent",
    "campaign_action": "outreach_agent",
    "data_query": "data_agent",
    "quick_answer": "quick_answer_node",
})
```

### Multi-Model Routing

Different nodes use different models based on task complexity:

| Node Type | Model | Rationale |
|-----------|-------|-----------|
| Intent classification | Haiku | Fast, cheap, sufficient for classification |
| Simple Q&A | Haiku | No tools needed, streaming response |
| Strategy generation | Sonnet | Strong reasoning, good value |
| Research synthesis | Sonnet | Multi-source analysis |
| Complex reasoning | Opus | When task warrants premium quality |

### Feature Flag

The LangGraph migration runs behind the `USE_LANGGRAPH` environment variable. When disabled, the system falls back to the current `agent_executor.py` loop.

```python
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "false").lower() == "true"
```

---

## 4. Prompt Architecture

### Current State

Every API call rebuilds the full system prompt from scratch. ~14 sections, 3K-10K tokens per call. With up to 25 tool iterations per turn, worst case is 500K input tokens per turn.

### Target: Layered Prompt with Caching

```
+---------------------------------------------+
|  LAYER 0: IDENTITY (cacheable, ~800 tok)    |
|  - Role definition                          |
|  - Critical rules                           |
|  - Response style/tone                      |
|  - Question format rules                    |
|  - Language override                        |
|  [cache_control: ephemeral]                 |
+---------------------------------------------+
|  LAYER 1: CAPABILITIES (cacheable, ~1-2K)   |
|  - Tool descriptions (phase-filtered)       |
|  - Tool usage rules                         |
|  - Document editing rules                   |
|  [cache_control: ephemeral]                 |
+---------------------------------------------+
|  LAYER 2: CONTEXT (dynamic, ~1-5K)          |
|  - Current phase instructions (1 of 4)      |
|  - Section completeness status              |
|  - User objective                           |
|  - Page context hint                        |
|  - Enrichment summary (compressed)          |
|  - Document excerpt (relevant sections)     |
+---------------------------------------------+
|  LAYER 3: CONVERSATION (dynamic, ~1-4K)     |
|  - Summarized older messages                |
|  - Recent messages (last 6-10 verbatim)     |
|  - Previous turn tool results (compressed)  |
+---------------------------------------------+
```

### Token Budget Comparison

| Component | Current | Target |
|-----------|---------|--------|
| System prompt | 3K-10K | 800 (cached) + 1-3K dynamic |
| Tool schemas | 2.5K (all 24) | 600-1K (phase-filtered 6-10) |
| History | 2-4K (raw 20 messages) | 1-2K (summarized + recent) |
| Turn context | 0-5K (tools) | 0-3K (compressed) |
| **Per-call total** | **8-20K** | **3-7K** |
| **25-iteration turn** | **200-500K** | **~50K cached + 75-175K** |
| **Savings** | -- | **50-70% input token reduction** |

### Anthropic Prompt Caching

```python
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": STATIC_SYSTEM_PROMPT,  # ~800 tokens
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": TOOL_RULES,  # ~500 tokens
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": dynamic_context  # changes each call
            }
        ]
    }
]
```

Cache hit rate: within a single turn's tool loop (up to 25 iterations), the static portion is cached after the first call. Saves ~1,300 tokens x 24 iterations = ~31,200 cached input tokens per turn. Cache lives for 5 minutes between turns.

### Phase-Filtered Tool Routing

Only tools relevant to the current phase are sent to the API:

| Phase | Active Tools | Count |
|-------|-------------|-------|
| strategy | update_strategy_section, append_to_section, set_extracted_field, track_assumption, check_readiness, set_icp_tiers, set_buyer_personas, web_search, research_own_company, get_strategy_document, count_contacts, count_companies | 12 |
| contacts | list_contacts, count_contacts, filter_contacts, apply_icp_filters, get_enrichment_gaps, estimate_enrichment_cost, start_enrichment, get_strategy_document, analyze_enrichment_insights | 9 |
| messages | create_campaign, filter_contacts, get_strategy_document, list_contacts | 4 |
| campaign | create_campaign, assign_to_campaign, check_strategy_conflicts, get_campaign_summary, filter_contacts, get_strategy_document | 6 |

### Smart Document Context

Instead of embedding the full strategy document in every prompt (500-5000 tokens), the system includes:
- The section the user is actively working on (full content)
- Completeness status for all sections (names + word counts)
- Full document available via `get_strategy_document` tool call when needed

---

## 5. Communication Protocols

### AG-UI: Agent to Frontend (Sprint 11, BL-252)

AG-UI is an open protocol that streams JSON events over HTTP/SSE. It replaces the current custom SSE event types.

**Current custom events --> AG-UI mapping:**

| AG-UI Event | Replaces | Purpose |
|-------------|----------|---------|
| `RUN_STARTED` | (new) | Agent begins processing |
| `RUN_FINISHED` | (new) | Agent completes |
| `TEXT_MESSAGE_START` | `analysis_start` | Begin streaming text |
| `TEXT_MESSAGE_CONTENT` | `analysis_chunk`, `section_content_chunk` | Stream text tokens |
| `TEXT_MESSAGE_END` | `analysis_done`, `section_content_done` | End streaming text |
| `TOOL_CALL_START` | `tool_start` | Agent begins tool execution |
| `TOOL_CALL_ARGS` | (new) | Stream tool arguments |
| `TOOL_CALL_END` | `tool_result` | Tool execution complete |
| `STATE_DELTA` | (new) | Incremental state update |
| `STATE_SNAPSHOT` | (new) | Full state sync |

**What AG-UI enables that we lack today:**
- **Generative UI**: Agent sends `STATE_DELTA` patches, frontend renders rich components (tables, charts, approval forms) inline in chat
- **Inline approval gates**: `TOOL_CALL_START` event pauses and shows approve/reject UI
- **Shared state**: Agent and frontend share synchronized state; agent updates company data --> frontend table updates in real-time
- **Tool approval UX**: "Agent wants to enrich 50 contacts (est. 500 tokens). Approve?" with a real button

**Frontend consumption (current):**

```
ChatSidebar (UI) <---> ChatProvider (state) <---> Flask API (backend)
                                |
                        SSE callbacks:
                          onChunk --> ChatMessages (renders text)
                          onToolStart --> WorkingState (thinking UI)
                          onToolResult --> ToolCallCard
                          onSectionStart --> StrategyEditor (typewriter)
                          onSectionChunk --> useTypewriter
                          onSectionDone --> invalidate react-query
```

Key frontend files:
- `frontend/src/providers/ChatProvider.tsx` -- state management, SSE consumption
- `frontend/src/hooks/useSSE.ts` -- SSE transport (fetch + ReadableStream, not EventSource)
- `frontend/src/components/chat/ChatMessages.tsx` -- message rendering
- `frontend/src/components/chat/ChatInput.tsx` -- user input
- `frontend/src/components/chat/ChatSidebar.tsx` -- sliding panel container

### A2A: Agent to Agent (Sprint 12+)

A2A protocol handles communication between specialist agents in the multi-agent setup.

```
Frontend <-[AG-UI]-> Orchestrator <-[A2A]-> Research Agent
                                   <-[A2A]-> Strategy Agent
                                   <-[A2A]-> Outreach Agent
                                   <-[A2A]-> Data Agent
```

In the LangGraph implementation, A2A maps to inter-subgraph communication via shared state and `Send()` API for parallel fan-out.

### Halt Gates in the UI

When a halt gate fires (via LangGraph `interrupt()` or tool-based `request_user_decision`):

1. Backend emits a decision request event (via AG-UI `TOOL_CALL_START` with approval semantics)
2. Frontend renders interactive buttons in the chat bubble
3. User clicks an option
4. User's choice is sent as the next message
5. LangGraph resumes from the interrupt point with the decision

**Gate taxonomy:**

| Gate Type | Trigger | Example |
|-----------|---------|---------|
| Scope | Multiple valid scopes found | "Which product line?" |
| Direction | Mutually exclusive strategies | "Broad or narrow ICP?" |
| Assumption | AI made a guess it's unsure about | "I assumed B2B only -- correct?" |
| Review | Major deliverable complete | "Strategy draft ready -- review?" |
| Resource | Expensive action about to happen | "Enrichment will cost 450 credits -- proceed?" |

**Gate frequency guidelines:**

| Task Size | Gates |
|-----------|-------|
| Full strategy generation | 3-4 (scope, direction, draft review, final review) |
| Section rewrite | 1 (review gate after draft) |
| Quick edit | 0 (just do it) |
| Research task | 1 (scope gate: what to research) |
| Campaign create | 2 (scope gate, message review) |

Gate frequency is adaptive and configurable per user/namespace. Some users prefer tight control (more halts), others prefer autonomy (fewer halts).

---

## 6. Memory and Context Management

### Current: Hard Window

```
Message 1  --+
Message 2    |  DROPPED (lost forever after position 20)
...          |
Message 15 --+
Message 16 --- kept (raw)
...
Message 35 --- kept (raw, latest)
```

Defined in `playbook_service.py`:
```python
MAX_HISTORY_MESSAGES = 20
```

### Target: RAG + Floating Window

**Cross-session memory** (RAG, Sprint 14, BL-262):
- Embed key decisions, preferences, and outcomes using pgvector
- Retrieve relevant context via similarity search when a new session starts
- Agent remembers: approved ICP, messaging angles that worked, past strategy decisions
- Storage: `pgvector` extension on PostgreSQL (RDS)

**Within-session memory** (floating window, Sprint 14, BL-263):
- When history exceeds 15 messages, summarize oldest 10 into ~200 tokens
- Keep last 8 messages verbatim
- Re-summarize as conversation grows

**What summaries preserve:**
- User decisions and preferences
- Approved strategies/content
- Rejected suggestions
- Key constraints mentioned
- Tool results that inform future decisions

**What summaries drop:**
- Filler ("looks good", "thanks")
- Intermediate drafts that were replaced
- Tool execution details (keep outcomes only)

### Auto-Save Important Decisions

The agent auto-saves key decisions to long-term memory:
- ICP definition approvals
- Persona selections
- Strategy direction choices
- Budget/scope constraints
- Rejected approaches (so they're not repeated)

### Intent-Aware Context Loading

Context injection varies based on detected intent:

| Intent | Context Loaded |
|--------|---------------|
| Quick answer | Document summary only |
| Strategy edit | Active section (full) + completeness status |
| Research task | Enrichment data + company context |
| Campaign action | Contact filters + campaign state |

---

## 7. Multimodal Processing

### Overview (Sprints 15-16)

The agent can extract strategic intelligence from uploaded files: pitch decks, annual reports, competitor screenshots, product demos.

### Processing Pipeline

```
User Input (drag-drop, URL paste, file picker)
    |
    v
INGESTION LAYER
  1. Upload to S3 (or local /uploads in dev)
  2. Store metadata in PG (file_uploads table)
  3. Dispatch to format-specific extractor
    |
    +--- Text Extractor (PDF text, DOCX, XLSX, HTML)
    +--- Visual Extractor (PDF scanned, images, screenshots)
    +--- A/V Extractor (video frames, audio -> text)
    |
    v
CONTENT STORE (PG)
  - extracted_content table
  - content_text, content_summary, token_count
    |
    v
CONTEXT INJECTION (per agent turn)
  - Check token budget
  - Inject summary (default) or full text (on drill-down)
  - Cache -- don't re-extract on every message
```

### Supported Formats

| Format | Library | Sprint | Use Case |
|--------|---------|--------|----------|
| PDF (text) | pdfplumber / PyMuPDF | 15 (BL-265) | Reports, whitepapers, case studies |
| PDF (image) | Claude vision API | 15 (BL-265) | Pitch decks, brochures |
| Images | Claude vision API | 15 (BL-265) | Screenshots, org charts |
| HTML | trafilatura + BeautifulSoup | 15 (BL-266) | Competitor websites, landing pages |
| Word (.docx) | python-docx | 15 (BL-266) | Proposals, contracts |
| Excel (.xlsx) | openpyxl | 16 (BL-267) | Financial data, contact lists |
| Video | ffmpeg + Whisper + vision | 16 (BL-268) | Product demos, webinars |

### Progressive Detail Levels

| Level | Description | Tokens | When Used |
|-------|-------------|--------|-----------|
| L0: Mention | "User uploaded: pitch-deck.pdf (12 pages, PDF)" | ~20 | All files, always |
| L1: Summary | 200-500 word summary of key findings | ~300-700 | Most recently discussed file |
| L2: Deep dive | Full extracted text or specific sections | up to 4K | On-demand via tool call |

Default injection is L0 for all files, L1 for the most recently discussed file. L2 only when the agent explicitly requests it.

### Token Budget

```
Existing budget:
  System prompt        3K - 10K tokens
  Conversation         2K - 4K tokens
  Tool schemas         ~2.5K tokens

Multimodal budget:     <= 8K tokens total
  Per-file summary     ~500 - 1,500 tokens
  Per-image            ~1,600 tokens
  Drill-down           up to 4K tokens

Total per call:        <= 25K input tokens
```

### Multimodal Tools

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `analyze_document` | file_id, query | summary, relevant_sections, confidence | Query-focused document analysis |
| `extract_data` | file_id, schema | rows, unmapped_columns, warnings | Structured extraction from tabular data |
| `analyze_image` | file_id, query | description, extracted_text, analysis | Image analysis via Claude vision |
| `analyze_video` | url, query, max_duration | transcript_summary, visual_summary, key_moments | Full video processing (async) |
| `fetch_and_analyze_url` | url, query, include_screenshot | content_text, summary, screenshot_analysis | URL content extraction |

---

## 8. Enrichment System

### Pipeline Stages

The enrichment pipeline runs as Python-native code (n8n fully removed). Stages execute sequentially:

```
L1 (Company Profile)
  |
  v
Triage (tier classification)
  |
  v
L2 (Deep Research)
  |
  v
Person (Contact Enrichment)
```

**L1 Company Enrichment** (`api/services/l1_enricher.py`):
- Perplexity API for company profiling
- EU government registry adapters (ARES, BRREG, PRH, recherche-entreprises, ISIR)
- Outputs: company description, employee count, revenue estimate, industry, tier classification

**L2 Deep Research**: Market analysis, competitive landscape, technology stack (migration to Python-native in progress)

**Person Enrichment**: Contact-level data -- role verification, LinkedIn profile, email validation

### Additional Enricher Modules (Sprint 18)

| Module | Backlog | Purpose |
|--------|---------|---------|
| News & PR | BL-231 | Recent company news, press releases, funding events |
| Social & Online | BL-232 | Social media presence, online activity signals |
| Contact Details | BL-233 | Direct phone, verified email, alternative contacts |
| Strategic Signals | BL-234 | Hiring patterns, tech adoption, expansion signals |
| Career History | BL-235 | Employment timeline, role transitions, seniority mapping |

### Research Agent Integration (Sprint 18, BL-1001)

Enricher modules wire into the Research Agent subgraph. The Research Agent coordinates enrichment alongside web search and document analysis:

```
Research Agent
  |-- Company Profiler (L1 enricher + web search)
  |-- Contact Enricher (Person enricher + LinkedIn)
  |-- Market Analyst (L2 enricher + news/signals)
```

### Enrichment Tools (for Chat, BL-128)

| Tool | Purpose |
|------|---------|
| `estimate_enrichment_cost` | Show token cost before starting enrichment |
| `start_enrichment` | Trigger enrichment pipeline for selected contacts |
| `check_enrichment_status` | Poll pipeline progress |
| `get_enrichment_gaps` | Identify contacts/companies missing enrichment data |
| `analyze_enrichment_insights` | Summarize enrichment results for strategy |

### DAG Executor

`api/services/dag_executor.py` manages stage orchestration:
- Stage definitions as Python classes (L1Enrichment, L2Enrichment, PersonEnrichment)
- DB-backed queue with completion-record eligibility tracking
- Built-in cost tracking (credit consumption calculated before/during execution)
- Tenant-isolated execution contexts

---

## 9. Operational Concerns

### Error Handling

**LLM failures:**
- Exponential backoff with fallback model chain: primary fails --> retry same (1x) --> fallback to next tier --> surface error to user
- Never silently swallow errors

**Tool failures:**
- AG-UI `TOOL_CALL_END` with error status shows error inline in chat
- Agent decides: retry, try alternative approach, or ask user
- Max 2 retries per tool call, then escalate

**Sub-agent failures:**
- Orchestrator catches failures from specialist agents
- Can reassign to different agent or surface to user
- Partial results are preserved -- successful sub-agent outputs are not discarded

**Timeout handling:**
- Per-agent time budgets (research: 60s, strategy: 120s)
- Global turn timeout: `MAX_TURN_SECONDS = 180` (in `agent_executor.py`)
- Orchestrator kills stuck sub-agents and reports partial results

### Cost Controls

**Per-request warnings:**
- Before expensive operations, show estimated token cost
- File processing (multimodal): show estimated cost before processing
- No surprise bills -- users always know what they're paying for

**Token budgets per tenant:**
- Namespace admins set monthly token limits
- Dashboard shows usage vs budget in credits (not USD)
- Soft warning at 80% usage, hard cap at 100% (configurable)
- 1 credit = $0.001 USD

**Model access:**
- All models available to all users -- no tier restrictions
- Warning before expensive model usage but user always decides
- No model gatekeeping: quality over cost

**Per-turn rate limits** (in `agent_executor.py`):
```python
TOOL_RATE_LIMITS: dict[str, int] = {
    "web_search": 5,
}
DEFAULT_TOOL_RATE_LIMIT = 15
```

### Analytics and Metrics

| Metric | Purpose | Source |
|--------|---------|--------|
| Token cost per conversation | Billing, budget tracking | LLM API response |
| Token cost per agent | Identify expensive agents | LangSmith traces |
| Agent routing accuracy | Is orchestrator picking the right specialist? | Manual eval + user feedback |
| Halt gate effectiveness | How often do users override vs accept? | Frontend events |
| Time to completion | Per phase, per agent | LangSmith traces |
| Tool success rate | Which tools fail most? | Tool call results |
| User satisfaction signals | Edits after agent writes, thumbs up/down | Frontend events |

LLM usage is logged per call via `api/services/llm_logger.py` into the `llm_usage_log` table: input tokens, output tokens, model, cost (USD), operation type.

### Testing Strategy

**Prompt testing:**
- Snapshot tests: save expected outputs for known inputs, flag regressions
- Golden conversation sets: curated input/output pairs per agent type
- LangSmith evaluation datasets (when adopted)

**Tool testing:**
- Unit tests per tool (mock external APIs, assert output shape)
- Established pattern in `tests/unit/`
- Each new tool gets a corresponding test file

**Integration testing:**
- Record real agent conversations --> replay as regression tests
- LangGraph `replay` mode for deterministic re-execution
- Test orchestrator routing: given intent X, does it pick agent Y?

**Eval metrics:**
- Task completion rate (did the agent achieve the user's goal?)
- Hallucination rate (did it fabricate company/contact data?)
- Halt gate accuracy (did it stop when it should? Did it stop unnecessarily?)
- Tool selection accuracy (did it pick the right tool?)

### Observability

- No paid observability until revenue
- Use LangSmith free tier if sufficient; evaluate self-hosted LangSmith
- Build lightweight tracing as fallback
- Current: basic logging via Python `logging` module

---

## 10. Sprint Roadmap

### Sprint 11: Foundation (BL-250, BL-251, BL-252)

| Item | Description | Status |
|------|-------------|--------|
| BL-250 | LangGraph Migration -- Replace `agent_executor.py` with StateGraph | Idea |
| BL-251 | Prompt Layering -- Static/dynamic split with `cache_control` | Idea |
| BL-252 | AG-UI Protocol -- Replace custom SSE with standardized events | Idea |
| BL-241 | Chat: Use L1 enrichment for strategy research | Done |

### Sprint 12: Subgraphs (BL-253, BL-254, BL-255, BL-256)

| Item | Description | Status |
|------|-------------|--------|
| BL-253 | Strategy Agent Subgraph | Idea |
| BL-254 | Research Agent Subgraph | Idea |
| BL-255 | Orchestrator Graph -- Intent detection, routing, synthesis | Idea |
| BL-256 | Research Sub-Agents -- Company Profiler, Contact Enricher, Market Analyst | Idea |

### Sprint 13: Halt Gates + Generative UI (BL-257 - BL-261)

| Item | Description | Status |
|------|-------------|--------|
| BL-257 | Adaptive Halt Gates -- `interrupt()` with AG-UI approval UI | Idea |
| BL-258 | Generative UI -- STATE_DELTA patches for inline components | Idea |
| BL-259 | Shared State Sync -- Agent-frontend synchronized state | Idea |
| BL-260 | Agent Document Editing -- Surgical Tiptap edits via AG-UI | Idea |
| BL-261 | Accept/Reject Changes -- Tiptap collaboration + suggestion mode | Idea |

### Sprint 14: Memory + Tool Routing (BL-262 - BL-264)

| Item | Description | Status |
|------|-------------|--------|
| BL-262 | RAG Long-Term Memory -- pgvector embeddings for cross-session | Idea |
| BL-263 | Conversation Summarization -- Floating window with compaction | Idea |
| BL-264 | Intent-Aware Tool Routing -- Phase-filtered tool registration | Idea |

### Sprint 15: Multimodal Phase 1-2 (BL-265, BL-266)

| Item | Description | Status |
|------|-------------|--------|
| BL-265 | PDF + Image Processing -- pdfplumber + Claude vision | Idea |
| BL-266 | HTML + Word Processing -- trafilatura + python-docx | Idea |

### Sprint 16: Multimodal Phase 3-4 + Copilot (BL-267 - BL-269)

| Item | Description | Status |
|------|-------------|--------|
| BL-267 | Excel Processing -- openpyxl schema mapping | Idea |
| BL-268 | Video Processing -- ffmpeg + Whisper + vision | Idea |
| BL-269 | Inline AI Copilot -- Tiptap autocompletion with Haiku | Idea |

### Sprint 17: Operational (BL-270 - BL-273)

| Item | Description | Status |
|------|-------------|--------|
| BL-270 | Agent Testing Framework -- Snapshot tests + golden conversations | Idea |
| BL-271 | Error Handling & Retry -- Fallback model chain + circuit breaker | Idea |
| BL-272 | Analytics Integration -- Token tracking + routing metrics | Idea |
| BL-273 | Cost Controls Per Tenant -- Token budgets + warnings + dashboard | Idea |

### Sprint 18: Enrichment Framework (BL-1001, BL-128, BL-221 - BL-235)

Wire 5 enricher modules into Research Agent subgraph + improve existing L1/L2/Person enrichers.

### Sprint 19: Message Generation (BL-1002, BL-1003, BL-057, BL-167, BL-200)

Outreach Agent subgraph for strategy-grounded message generation, personalization quality, and messaging framework.

### Sprint 20: End-to-End Pipeline (BL-1004 - BL-1007, BL-132)

Data Agent subgraph, full pipeline runner (strategy --> enrichment --> messages --> campaign), auto-enrichment with cost approval halt gate, campaign auto-setup.

---

## 11. Developer Guide

### Key Files and Their Responsibilities

**Backend (api/):**

| File | Purpose |
|------|---------|
| `api/services/agent_executor.py` | Agentic loop -- yields SSE events, manages tool iterations |
| `api/services/playbook_service.py` | System prompt construction, message formatting |
| `api/services/strategy_tools.py` | Strategy document tool handlers (update, append, extract) |
| `api/services/tool_registry.py` | Tool registration framework (`ToolDefinition`, `ToolContext`) |
| `api/services/anthropic_client.py` | Claude API wrapper |
| `api/services/llm_logger.py` | Token usage logging per API call |
| `api/routes/playbook_routes.py` | `/api/playbook/*` endpoints (chat, strategy, phases) |
| `api/services/l1_enricher.py` | L1 company enrichment (Perplexity API) |
| `api/services/dag_executor.py` | Pipeline stage orchestration |

**Frontend (frontend/src/):**

| File | Purpose |
|------|---------|
| `providers/ChatProvider.tsx` | Chat state management, SSE consumption, tool call tracking |
| `hooks/useSSE.ts` | SSE transport layer (fetch + ReadableStream) |
| `components/chat/ChatSidebar.tsx` | Sliding chat panel container |
| `components/chat/ChatMessages.tsx` | Message rendering |
| `components/chat/ChatInput.tsx` | User input with placeholder suggestions |
| `components/playbook/ToolCallCard.tsx` | Tool execution display cards |

### How to Add a New Tool

1. **Define the tool handler** in the appropriate service file (or create a new one):

```python
# api/services/my_tools.py
from .tool_registry import ToolContext, ToolDefinition, register_tool

def handle_my_tool(args: dict, ctx: ToolContext) -> dict:
    """Execute the tool action. Returns JSON-serializable dict."""
    # args contains the tool input from Claude
    # ctx provides tenant_id, user_id, document_id, turn_id
    result = do_something(args["param1"], tenant_id=ctx.tenant_id)
    return {"status": "success", "data": result}
```

2. **Create the tool definition** with JSON Schema for input validation:

```python
MY_TOOL = ToolDefinition(
    name="my_tool",
    description="Brief description for Claude (what the tool does, when to use it)",
    input_schema={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "What this parameter is for"},
        },
        "required": ["param1"],
    },
    handler=handle_my_tool,
    requires_confirmation=False,  # True for destructive/expensive operations
)
```

3. **Register at app startup** -- add to the module's init or a registration function:

```python
register_tool(MY_TOOL)
```

4. **Add to phase routing** (once implemented) -- specify which phases should have access to this tool.

5. **Write unit tests** in `tests/unit/test_my_tools.py`:

```python
def test_my_tool_success(mock_db):
    ctx = ToolContext(tenant_id="test-tenant")
    result = handle_my_tool({"param1": "value"}, ctx)
    assert result["status"] == "success"
```

### How to Add a New Agent Subgraph (Post-LangGraph Migration)

1. **Define the subgraph state:**

```python
class MyAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    # agent-specific state fields
    my_result: dict | None
```

2. **Create node functions** (each node = one step in the agent's workflow):

```python
def research_node(state: MyAgentState) -> MyAgentState:
    """Node that calls tools and updates state."""
    # Use appropriate model for this node
    response = call_llm(model="haiku", tools=[...], messages=state["messages"])
    state["my_result"] = process_response(response)
    return state
```

3. **Build the subgraph:**

```python
my_agent = StateGraph(MyAgentState)
my_agent.add_node("research", research_node)
my_agent.add_node("synthesize", synthesize_node)
my_agent.add_edge("research", "synthesize")
my_agent.set_entry_point("research")
my_agent_graph = my_agent.compile()
```

4. **Register with the orchestrator** by adding the subgraph as a node in the parent graph.

### How to Add a New Halt Gate

1. **Define the gate node:**

```python
def my_gate(state):
    if state["needs_confirmation"]:
        decision = interrupt({
            "question": "Should we proceed with X?",
            "options": ["Yes, proceed", "No, change approach", "Show me more details"],
            "context": "Brief explanation of why this matters",
            "gate_type": "scope"  # scope, direction, assumption, review, resource
        })
        state["user_decision"] = decision
    return state
```

2. **Wire into the graph** with conditional edges.

3. **Frontend handling**: AG-UI events surface the interrupt as an approval request. The ChatProvider routes it to an inline button UI.

### How to Add a New Multimodal Format

1. **Create an extractor** in `api/services/extractors/`:

```python
class MyFormatExtractor:
    def can_handle(self, mime_type: str) -> bool:
        return mime_type == "application/my-format"

    def extract(self, file_path: str) -> ExtractedContent:
        # Parse the file
        text = parse_my_format(file_path)
        return ExtractedContent(
            content_text=text,
            token_count=estimate_tokens(text),
        )
```

2. **Register the extractor** in the extraction dispatcher.

3. **Create/extend a tool** (e.g., `analyze_document`) to handle the new format.

4. **Add token cost estimation** for the new format.

### How to Test Agent Behavior

**Unit testing tools:**
```bash
make test-changed  # runs only tests matching changed files
```

**Golden conversation testing** (post Sprint 17):
```python
# tests/agent/test_strategy_flow.py
def test_strategy_generation_flow():
    """Replay a recorded conversation and verify agent behavior."""
    recording = load_golden_conversation("strategy_basic")
    result = replay_agent_flow(recording)
    assert result.completed_sections == ["Executive Summary", "Value Proposition"]
    assert result.halt_gates_fired == ["scope_gate", "review_gate"]
```

**Testing orchestrator routing:**
```python
def test_intent_routing():
    """Verify orchestrator picks the right specialist agent."""
    assert classify_intent("Rewrite the positioning section") == "strategy_edit"
    assert classify_intent("Find competitors for Acme") == "research_task"
    assert classify_intent("What's our ICP?") == "quick_answer"
```

**Manual testing with `make dev`:**
1. Start local servers: `make dev`
2. Open `http://localhost:5173`, login with `test@staging.local` / `staging123`
3. Navigate to Playbook
4. Test chat interactions, observe tool calls in browser console
5. Check SSE events in Network tab (filter by `EventStream`)

---

## Appendix: Architecture Decision Records

Pending ADRs (decisions made, need formal write-up):

| ADR | Decision |
|-----|----------|
| LangGraph adoption | Adopt now, before building custom halt gates. ~1 week migration. |
| AG-UI + A2A protocol | AG-UI replaces custom SSE. A2A for inter-agent communication. |
| Multi-agent orchestration | Orchestrator + 4 specialist agents (Strategy, Research, Outreach, Data). |
| Prompt layering + caching | 4-layer system with Anthropic cache_control. 50-70% token savings. |
| Model selection policy | Best model for the job. Users pay tokens. Quality over cost. No gatekeeping. |
| Multimodal processing | Phased rollout: PDF+Images, HTML+Word, Excel, Video. |
| Tiptap AI Toolkit | Keep Tiptap, add copilot suggestions and agent document editing. |

Full decision context: `docs/plans/2026-03-06-agent-prompt-architecture.md` (Sections 10-17).
