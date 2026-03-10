# Sprint 17: Operational Concerns Spec

> BL-270, BL-271, BL-272, BL-273 — Agent testing, error handling, analytics, cost controls

## Problem Statement

The LangGraph agent (Sprint 11) has no operational infrastructure: no testing framework for agent conversations, no resilient error handling for LLM/tool failures, no token tracking or cost analytics, and no per-tenant budget controls. These are prerequisites for production readiness.

## Scope

### BL-270: Agent Testing Framework

**Problem:** No way to regression-test agent behavior after prompt or tool changes.

**Solution:** Snapshot-based testing framework with golden conversations, configurable assertion levels, and quality scoring.

**Acceptance Criteria:**
- Given a golden conversation fixture, when replayed against the agent, then:
  1. All tool calls match expected (name + args structure)
  2. Response structure matches (sections, formatting)
  3. Quality metrics computed (relevance, completeness)
  4. Regressions detected and reported
  5. Summary report generated

**Data Model:** No DB changes. Fixtures stored as JSON in `tests/fixtures/agent_conversations/`.

**Fixture format:**
```json
{
  "name": "research-flow",
  "description": "Tests research -> strategy generation flow",
  "model": "claude-haiku-4-5-20251001",
  "system_prompt": "...",
  "turns": [
    {
      "user_message": "Research Acme Corp",
      "expected_tool_calls": [{"name": "research_own_company", "args_contains": {"query": "Acme"}}],
      "expected_response": {"contains": ["research", "Acme"], "format": "markdown"},
      "assertion_level": "structural"
    }
  ]
}
```

**Assertion levels:**
- `strict`: Exact match on tool calls and response text
- `semantic`: Meaning match (contains keywords, same intent)
- `structural`: Format match (has markdown, has tool calls of expected type)

### BL-271: Error Handling & Retry

**Problem:** LLM API failures, tool timeouts, and rate limits cause unrecoverable errors.

**Solution:** Model fallback chain, exponential backoff for tools, circuit breaker, and graceful degradation.

**Acceptance Criteria:**
- Given a model API failure, when fallback triggers, then:
  1. Alternate model used transparently
  2. User notified of fallback via SSE event
  3. Retry count tracked
- Given a tool timeout, when retry triggers, then:
  1. Exponential backoff applied (1s, 2s, 4s)
  2. Max 3 retries respected
  3. Circuit breaker activates after 5 failures in 10 minutes

**Components:**
- `ModelFallbackChain`: Ordered list of models, tries next on failure
- `RetryPolicy`: Configurable backoff, max retries, timeout per tool
- `CircuitBreaker`: Per-tool failure tracking, auto-disable after threshold

### BL-272: Analytics Integration

**Problem:** No visibility into token usage, cost, tool performance, or agent behavior.

**Solution:** Lightweight self-hosted metrics recording to PostgreSQL. No paid observability.

**Acceptance Criteria:**
- Given an agent turn, when completed, then:
  1. Token counts recorded (input, output, by model)
  2. Cost computed and stored
  3. Tool calls logged with duration
  4. Trace ID links all events
  5. Metrics queryable per tenant

**Data Model:** New `agent_metrics` table (see migration 046).

### BL-273: Cost Controls Per Tenant

**Problem:** No budget limits, no cost warnings, no pre-operation estimates.

**Solution:** Per-tenant monthly token budgets with threshold warnings and pre-operation cost estimation.

**Acceptance Criteria:**
- Given a tenant approaching budget limit, when at 75%, then:
  1. Warning shown in chat
  2. Operations still allowed
  3. At 100%, hard block with upgrade prompt
- Given an expensive operation, when initiated, then:
  1. Estimated cost shown
  2. User confirms before proceeding
  3. All models remain available

**Data Model:** New `tenant_token_budgets` table (see migration 046).

## Migration 046: agent_metrics + tenant_token_budgets

```sql
-- agent_metrics: per-turn token and cost tracking
CREATE TABLE agent_metrics (
  id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  user_id uuid REFERENCES users(id),
  trace_id text NOT NULL,
  turn_index integer NOT NULL DEFAULT 0,
  model text NOT NULL,
  input_tokens integer NOT NULL DEFAULT 0,
  output_tokens integer NOT NULL DEFAULT 0,
  cost_usd numeric(12,8) NOT NULL DEFAULT 0,
  tool_calls jsonb DEFAULT '[]',
  duration_ms integer,
  created_at timestamptz DEFAULT now()
);

-- tenant_token_budgets: monthly budget configuration
CREATE TABLE tenant_token_budgets (
  id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id) UNIQUE,
  monthly_token_limit bigint NOT NULL DEFAULT 1000000,
  warn_at_percent integer NOT NULL DEFAULT 75,
  hard_limit_percent integer NOT NULL DEFAULT 100,
  current_period_start date NOT NULL DEFAULT date_trunc('month', now()),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
```

## Files

| File | Purpose |
|------|---------|
| `api/agents/testing/__init__.py` | Package init |
| `api/agents/testing/framework.py` | Test runner, snapshot comparison, quality scoring |
| `api/agents/testing/fixtures.py` | Fixture loading, golden conversation format |
| `api/agents/resilience.py` | Error handling, retry, circuit breaker, model fallback |
| `api/agents/analytics.py` | Token tracking, metrics recording, cost computation |
| `api/agents/cost_controls.py` | Tenant budgets, warnings, pre-operation estimates |
| `migrations/046_agent_metrics.sql` | DB schema for metrics + budgets |
| `tests/unit/test_agent_resilience.py` | Resilience unit tests |
| `tests/unit/test_agent_analytics.py` | Analytics unit tests |
| `tests/unit/test_agent_cost_controls.py` | Cost controls unit tests |
| `tests/unit/test_agent_testing_framework.py` | Testing framework unit tests |
| `tests/fixtures/agent_conversations/` | Golden conversation fixtures |

## Design Decisions

- No paid observability (no LangSmith cloud, no Datadog) until revenue
- No model gatekeeping -- all users get all models, warn before expensive ops
- Token budgets are soft by default -- warnings at thresholds, hard block only at 100%
- Circuit breaker is per-tool, resets after 10 minutes
- Metrics stored in PG, not external service
