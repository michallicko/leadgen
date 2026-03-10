# Sprint 20: Pipeline Orchestration + Copilot Agent

**Backlog Item**: BL-269
**Sprint**: 20 (Final agent architecture sprint)
**Status**: Building

## Problem Statement

Sprints 11-19 built all individual agent components (LangGraph core, multi-agent orchestrator, subgraphs for Strategy/Research/Enrichment/Outreach, halt gates, analytics, etc.). However, these components operate independently — there is no unified pipeline that:
1. Tracks which GTM phase the user is in (Strategy → Contacts → Messages → Campaign)
2. Passes context between agents (e.g., research results informing outreach messages)
3. Handles sequential handoffs (enrichment completing before outreach begins)
4. Provides a lightweight assistant for quick questions

## Solution

### 1. Pipeline Orchestrator (`api/agents/pipeline.py`)

A higher-level graph that composes the existing orchestrator with phase management:

- **Phase detection**: Infers current phase from explicit state, page context, or defaults to strategy
- **Phase-aware routing**: Routes intents to the correct specialist while tracking phase progress
- **Cross-agent context**: Builds a context dict that accumulates research results, section completeness, and phase status across turns
- **Pipeline status API**: Returns phase completion for UI rendering

### 2. Copilot Agent (`api/agents/subgraphs/copilot.py`)

A lightweight subgraph for quick questions:
- Uses Haiku model for < 2s response time
- Has 4 read-only tools: get_contact_info, get_company_info, get_pipeline_status, get_recent_activity
- Max 8 iterations (lower than specialist agents)
- Enforces concise responses (100 word max in prompt)
- Default fallback for unrecognized intents

### 3. Intent Classification Update (`api/agents/intent.py`)

- Added `copilot` as the default fallback intent (replaces `quick_answer`)
- Added `enrichment` intent for pipeline/enrichment operations
- Added `outreach` intent (previously `campaign`)
- Keyword fast paths for enrichment and outreach
- Updated LLM classification prompt with all 5 categories

### 4. Enhanced Orchestrator (`api/agents/orchestrator.py`)

- Routes to all 5 specialist subgraphs + passthrough
- Lazy imports for subgraphs not yet merged (graceful fallback to copilot)
- Copilot node replaces quick_response as the default handler

## Acceptance Criteria

Given the pipeline orchestrator is running
When a user sends a message about strategy
Then it routes to the strategy agent AND tracks the strategy phase

Given the user is on the contacts page
When they ask to enrich companies
Then the enrichment agent runs AND the contacts phase is marked in-progress

Given the copilot receives a "how do I" question
When it processes the message
Then it responds in < 2s using Haiku with max 100 words

Given the intent classifier receives a greeting
When it classifies the message
Then it returns "copilot" (not "quick_answer")

Given the pipeline state has research results from a previous turn
When the outreach agent runs
Then it receives the research context for message personalization

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `api/agents/state.py` | Created | AgentState with pipeline fields |
| `api/agents/graph.py` | Created | SSEEvent + graph utilities |
| `api/agents/intent.py` | Created | Intent classifier with 5 categories |
| `api/agents/orchestrator.py` | Created | Multi-agent orchestrator |
| `api/agents/pipeline.py` | Created | Pipeline orchestrator with phase tracking |
| `api/agents/subgraphs/copilot.py` | Created | Copilot subgraph |
| `api/tools/copilot_tools.py` | Created | Read-only copilot tools |
| `tests/unit/test_pipeline.py` | Created | Pipeline tests (22 tests) |
| `tests/unit/test_copilot.py` | Created | Copilot tests (25 tests) |

## Architecture Decisions

- Pipeline graph composes existing subgraphs — does NOT replace them
- Copilot uses Haiku for speed
- Subgraphs imported lazily with graceful fallback (for parallel branch development)
- All DB queries in copilot tools filter by tenant_id
- Phase transitions tracked in state (no separate persistence yet)
- Pipeline context is additive — accumulates across turns
