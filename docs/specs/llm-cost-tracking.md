# Spec: LLM Cost Logging & Breakdown Dashboard (BL-055)

**Date**: 2026-02-23 | **Status**: Spec'd
**Priority**: Should Have | **Effort**: M
**Dependencies**: None (existing infrastructure covers most of the data model)

---

## Problem Statement

The leadgen pipeline makes LLM calls across multiple subsystems — enrichment (L1/L2/Person), playbook chat, strategy extraction, message generation, CSV import mapping, and Gmail signature extraction. Cost tracking is partially implemented: enrichment and message generation calls log to `llm_usage_log` via `log_llm_usage()`, but **playbook chat and strategy extraction calls are completely invisible** — no tokens, no cost, no latency recorded.

This means:
- The highest-frequency LLM call site (playbook chat, multiple calls per session) generates zero cost data.
- Strategy extraction (potentially large documents) is untracked.
- There is no UI to view cost breakdowns — the existing `/api/llm-usage/summary` endpoint exists but has no frontend consumer.
- Operators cannot answer "how much did AI cost us this month?" without querying the database directly.
- Per-tenant cost allocation is impossible for playbook chat, making pricing decisions guesswork.

## Current State Audit

### Call Sites and Tracking Status

| Call Site | Provider | Model(s) | Tracked? | Logger |
|-----------|----------|----------|----------|--------|
| **L1 Enrichment** | Perplexity | sonar, sonar-pro | Yes | `log_llm_usage()` in `l1_enricher.py:334` |
| **L2 Enrichment — News** | Perplexity | sonar-pro | Partial | Cost tracked on response object, but `log_llm_usage()` only called once for aggregate L2 at line 311 |
| **L2 Enrichment — Strategic** | Perplexity | sonar-pro | Partial | Same aggregate log as News |
| **L2 Enrichment — Synthesis** | Anthropic | claude-sonnet-4-5 | Partial | Same aggregate log — individual call tokens not broken out |
| **Person Enrichment — Profile** | Perplexity | sonar-pro | **No** | `log_llm_usage` imported but never called |
| **Person Enrichment — Signals** | Perplexity | sonar-pro | **No** | Same — never called |
| **Person Enrichment — Synthesis** | Anthropic | claude-sonnet-4-5 | **No** | Same — never called |
| **Playbook Chat (streaming)** | Anthropic | claude-haiku-4-5 | **No** | `stream_query()` returns no usage data; no logging |
| **Playbook Chat (sync)** | Anthropic | claude-haiku-4-5 | **No** | Same — `stream_query()` used for both paths |
| **Strategy Extraction** | Anthropic | claude-haiku-4-5 | **No** | `client.query()` returns `AnthropicResponse` with tokens, but not logged |
| **Message Generation** | Anthropic | claude-haiku-3-5 | Yes | `log_llm_usage()` in `message_generator.py:476` |
| **Message Regeneration** | Anthropic | claude-haiku-3-5 | Yes | `log_llm_usage()` in `message_generator.py:739` |
| **CSV Column Mapping** | Anthropic | claude-haiku-3-5 | Yes | `log_llm_usage()` in `import_routes.py:207` |
| **CSV Column Remap** | Anthropic | claude-haiku-3-5 | Yes | `log_llm_usage()` in `import_routes.py:289` |
| **Gmail Signature Extraction** | Anthropic | claude-haiku-3-5 | Yes | `log_llm_usage()` in `gmail_scanner.py:373` |

### Existing Infrastructure

**Already built:**
- `LlmUsageLog` model (`api/models.py:791`) — complete schema with tenant_id, user_id, operation, provider, model, input_tokens, output_tokens, cost_usd, duration_ms, metadata JSONB
- `log_llm_usage()` function (`api/services/llm_logger.py`) — creates log entries, computes cost from pricing table
- `compute_cost()` function — Decimal-based pricing calculator with per-model and wildcard fallback rates
- `MODEL_PRICING` dict in `llm_logger.py` — covers Anthropic (Sonnet 4.5, Haiku 3.5, Opus 4) and Perplexity (sonar, sonar-pro)
- API endpoints:
  - `GET /api/llm-usage/summary` — aggregated totals, by_tenant, by_operation, by_model, time_series
  - `GET /api/llm-usage/logs` — paginated individual log entries with filters
- Both endpoints require super_admin role

### Gaps

1. **Playbook chat streaming** — `AnthropicClient.stream_query()` does not return token usage (SSE streaming doesn't include usage in delta events; it arrives in `message_stop` event which is currently discarded)
2. **Person enrichment** — `log_llm_usage` is imported but never called after any of the 3 LLM calls
3. **Strategy extraction** — `AnthropicResponse` contains token data but it's never logged
4. **L2 enrichment granularity** — logs one aggregate entry instead of 3 separate entries (news/strategic/synthesis)
5. **No frontend** — API exists but no UI consumes it
6. **No sonar-reasoning models** in `llm_logger.py` pricing — `sonar-reasoning-pro` and `sonar-reasoning` are in `perplexity_client.py` but missing from `llm_logger.py`

---

## User Stories

### Cost Visibility
1. As an operator, I want to see total AI cost broken down by source (enrichment, chat, messages, imports) so I can understand where money goes.
2. As an operator, I want to see cost trends over time (daily/weekly/monthly) so I can detect anomalies and forecast spending.
3. As an operator, I want to filter costs by date range, operation, provider, and model so I can drill into specific areas.

### Per-Call Tracking
4. As a developer, I want every LLM call to automatically log tokens and cost so I never have to remember to add logging manually.
5. As an operator, I want to see individual call logs with latency data so I can identify slow or expensive calls.

### Dashboard
6. As an operator, I want a "Costs" tab or section in the admin area showing a summary card (total spend, call count, avg cost) and breakdown charts so I have at-a-glance visibility.

---

## Acceptance Criteria

### AC-1: Playbook Chat Cost Logging

**Given** a user sends a message in the playbook chat
**When** the AI responds (streaming or sync)
**Then**:
1. An `llm_usage_log` entry is created with `operation='playbook_chat'`
2. `input_tokens` and `output_tokens` are populated (from `message_stop` SSE event for streaming, or from response for sync)
3. `cost_usd` is computed using `compute_cost()`
4. `user_id` is set to the authenticated user
5. `metadata` includes `{document_id, message_length}`
6. `duration_ms` is recorded

### AC-2: Strategy Extraction Cost Logging

**Given** the `/api/playbook/extract` endpoint is called
**When** the LLM extraction completes
**Then**:
1. An `llm_usage_log` entry is created with `operation='strategy_extraction'`
2. Token counts from `AnthropicResponse` are logged
3. `user_id` is set to the authenticated user

### AC-3: Person Enrichment Cost Logging

**Given** a person enrichment runs for a contact
**When** each LLM call completes (profile research, signals research, synthesis)
**Then**:
1. Three separate `llm_usage_log` entries are created:
   - `operation='person_profile_research'` (Perplexity)
   - `operation='person_signals_research'` (Perplexity)
   - `operation='person_synthesis'` (Anthropic)
2. Each entry has accurate per-call token counts and costs

### AC-4: L2 Enrichment Granular Logging

**Given** an L2 enrichment runs for a company
**When** each LLM call completes
**Then**:
1. Three separate `llm_usage_log` entries are created:
   - `operation='l2_news_research'` (Perplexity)
   - `operation='l2_strategic_research'` (Perplexity)
   - `operation='l2_synthesis'` (Anthropic)
2. The existing single aggregate log is replaced by per-call logs

### AC-5: Cost Dashboard UI

**Given** a super_admin user navigates to the cost dashboard
**When** the page loads
**Then**:
1. A summary card shows: total cost (period), total calls, average cost per call
2. A breakdown table shows cost by operation (descending)
3. A breakdown table shows cost by model/provider (descending)
4. A time-series chart shows daily cost trend for the selected period
5. Date range picker defaults to last 30 days
6. All data comes from the existing `/api/llm-usage/summary` endpoint

### AC-6: Pricing Table Completeness

**Given** the `MODEL_PRICING` in `llm_logger.py`
**When** any model used in the codebase is looked up
**Then** it returns accurate pricing (no wildcard fallback needed for known models)

Specifically, add:
- `perplexity/sonar-reasoning-pro` ($2.00 / $8.00 per 1M)
- `perplexity/sonar-reasoning` ($1.00 / $5.00 per 1M)
- `anthropic/claude-sonnet-4-5-20250929` (alias — already covered by the `claude-sonnet-4-5-*` pattern but should be explicit)

---

## Implementation Approach

### Phase 1: Instrument Missing Call Sites (Backend Only)

**Estimated effort: S (1-2 days)**

1. **Playbook chat streaming** — Parse `message_stop` SSE event in `AnthropicClient.stream_query()` to capture `usage` data. Return it alongside the text chunks (or accumulate and expose via a callback/return value). Add `log_llm_usage()` call in `_stream_response()` and `_sync_response()` in `playbook_routes.py`.

2. **Strategy extraction** — Add `log_llm_usage()` after `client.query()` in the `/api/playbook/extract` route handler, using `result.input_tokens` and `result.output_tokens` which already exist on `AnthropicResponse`.

3. **Person enrichment** — Add `log_llm_usage()` calls after each of the 3 LLM calls in `person_enricher.py` (`_research_profile`, `_research_signals`, `_synthesize`). Token data is already available on the response objects.

4. **L2 enrichment granularity** — Replace the single aggregate `_log_usage()` call with 3 per-call `log_llm_usage()` invocations, one after each research/synthesis phase. Token data already available on response objects.

5. **Pricing table** — Add missing sonar-reasoning models to `MODEL_PRICING` in `llm_logger.py`.

### Phase 2: Cost Dashboard UI

**Estimated effort: S-M (2-3 days)**

1. **New admin page** — `costs.html` (or React component in `frontend/`) accessible from the admin nav.
2. **Summary cards** — Total cost, total calls, avg cost/call for the selected period.
3. **Breakdown tables** — By operation, by model/provider. Sortable, filterable.
4. **Time-series chart** — Daily cost trend using a lightweight chart library (Chart.js or similar, already may be available).
5. **Date range picker** — Default 30 days, custom range selection.
6. **Data source** — Consumes existing `GET /api/llm-usage/summary` endpoint (no new API work needed).

### Future Considerations (Not in Scope)

- **Per-tenant cost budgets and alerts** — Useful for SaaS pricing but not needed for MVP
- **Real-time cost streaming** — WebSocket push of cost events
- **Cost attribution to campaigns** — Link LLM costs to specific campaign ROI

---

## Data Model

No schema changes needed. The existing `llm_usage_log` table covers all requirements:

```sql
CREATE TABLE llm_usage_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    operation TEXT NOT NULL,           -- e.g. 'playbook_chat', 'l2_news_research'
    provider TEXT NOT NULL DEFAULT 'anthropic',
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Operation Names (Standardized)

| Operation | Provider | Description |
|-----------|----------|-------------|
| `l1_enrichment` | perplexity | L1 company profile research |
| `l2_news_research` | perplexity | L2 news & signals research |
| `l2_strategic_research` | perplexity | L2 strategic intelligence research |
| `l2_synthesis` | anthropic | L2 AI opportunity synthesis |
| `person_profile_research` | perplexity | Person professional profile research |
| `person_signals_research` | perplexity | Person decision signals research |
| `person_synthesis` | anthropic | Person personalization synthesis |
| `playbook_chat` | anthropic | Playbook AI strategist chat |
| `strategy_extraction` | anthropic | Extract structured data from strategy doc |
| `message_generation` | anthropic | Campaign message generation |
| `message_regeneration` | anthropic | Single message regeneration |
| `csv_column_mapping` | anthropic | Import CSV column mapping |
| `csv_column_remap` | anthropic | Import CSV re-mapping |
| `gmail_signature_extraction` | anthropic | Gmail signature parsing |

---

## API Endpoints

No new endpoints needed. Existing endpoints cover the requirements:

- `GET /api/llm-usage/summary` — Aggregated view with by_tenant, by_operation, by_model, time_series
- `GET /api/llm-usage/logs` — Paginated individual entries with filters

Both already require super_admin role via `@require_role("admin")` + `_require_super_admin()`.

---

## Technical Notes

### Streaming Token Capture

The Anthropic Messages API includes usage in the `message_start` event (input tokens) and `message_delta` event (output tokens) during streaming. The current `AnthropicClient.stream_query()` discards these events. The fix is to:

1. Parse `message_start` to capture `usage.input_tokens`
2. Parse `message_delta` (final event before `message_stop`) to capture `usage.output_tokens`
3. Either return a summary object after the generator completes, or accept a callback that receives usage data

### Decorator/Wrapper Pattern (Future)

A future enhancement could wrap all LLM client methods with automatic logging via a decorator, eliminating the need to manually add `log_llm_usage()` at each call site. This is out of scope for this spec but worth noting as a pattern to reduce future maintenance burden.
