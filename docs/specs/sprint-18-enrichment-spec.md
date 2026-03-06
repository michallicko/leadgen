# Sprint 18: Enrichment Framework + Missing Modules

## Problem Statement

The 5 enricher modules (news, social, contact_details, signals, career) exist as standalone services but are not integrated into the AI agent's Research Agent subgraph. Users cannot trigger or monitor enrichment through the chat interface's research flow. Additionally, these modules lack unit tests.

## Scope

### BL-1001: Enrichment Agent Integration (Must Have, L)
Wire enricher modules into the Research Agent subgraph as callable tools.

### BL-128: Enrichment Agent Tools (Must Have, M)
Three chat-accessible tools: `estimate_enrichment_cost`, `start_enrichment`, `check_enrichment_status`.
NOTE: `estimate_enrichment_cost` and `start_enrichment` already exist in `enrichment_trigger_tools.py`. This item adds `check_enrichment_status` and creates enrichment-specific tool wrappers for the Research Agent.

### BL-231 through BL-235: QA + Agent-Wire 5 Enricher Modules (Should Have, S each)
Unit tests and tool wrappers for each enricher module.

### BL-221, BL-222, BL-223: Improve Existing Enricher Quality (Should Have, M each)
Quality improvements to L1 revenue detection, L2 market module, and Person enrichment resilience.

## Technical Approach

### 1. Enrichment Tool Wrappers (`api/tools/enrichment_tools.py`)

Create lightweight tool wrappers that bridge between the tool registry and the enricher services. Each wrapper:
- Accepts entity_id + optional config from the agent
- Calls the underlying enricher function
- Returns structured results suitable for agent consumption
- Handles Flask app context (enrichers need DB access)

Tools:
- `enrich_company_news(company_id)` -- wraps `enrich_news()`
- `enrich_company_signals(company_id)` -- wraps `enrich_signals()`
- `enrich_contact_social(contact_id)` -- wraps `enrich_social()`
- `enrich_contact_career(contact_id)` -- wraps `enrich_career()`
- `enrich_contact_details(contact_id)` -- wraps `enrich_contact_details()`
- `check_enrichment_status(pipeline_run_id)` -- queries pipeline_runs/stage_runs

### 2. Research Agent Integration (`api/agents/subgraphs/research.py`)

Add enrichment tool names to `RESEARCH_TOOL_NAMES` so the Research Agent can call them during research operations. Update the system prompt to mention enrichment capabilities.

### 3. Enrichment Sub-Agent (`api/agents/subgraphs/enrichment.py`)

Create a dedicated enrichment subgraph that coordinates multi-stage enrichment. This subgraph:
- Receives enrichment requests from the orchestrator
- Plans which stages to run based on entity state
- Executes enrichment tools in dependency order
- Reports progress and results

### 4. Unit Tests

For each enricher module, test:
- Success path: returns cost, saves data correctly
- Entity not found: returns error gracefully
- API error: handles Perplexity failures
- Parse error: handles malformed JSON
- Boost mode: selects correct model

## Acceptance Criteria

### Given the Research Agent is active
- When a user asks to enrich a company, Then the agent can call enrichment tools
- When enrichment completes, Then results are stored in the database
- When enrichment fails, Then error is returned without crashing

### Given estimate_enrichment_cost is called
- When tag_name is provided, Then per-stage breakdown is returned
- When tag_name is missing, Then available tags are listed

### Given check_enrichment_status is called
- When valid pipeline_run_id, Then stage statuses and progress are returned
- When invalid id, Then "not found" error is returned

### Given each enricher module
- When called with valid entity, Then enrichment data is saved
- When entity not found, Then error dict is returned
- When Perplexity API fails, Then error is handled gracefully

## Files Created/Modified

### New Files
- `api/tools/__init__.py`
- `api/tools/enrichment_tools.py` -- tool wrappers + check_enrichment_status
- `api/agents/subgraphs/enrichment.py` -- enrichment sub-agent
- `tests/unit/test_enrichment_tools.py`
- `tests/unit/test_news_enricher.py`
- `tests/unit/test_social_enricher.py`
- `tests/unit/test_signals_enricher.py`

### Modified Files
- `api/agents/subgraphs/research.py` -- add enrichment tools
- `api/__init__.py` -- register new tools
