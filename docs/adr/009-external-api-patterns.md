# ADR-009: External API Patterns for Agent Tools

**Date**: 2026-02-28 | **Status**: Accepted

## Context

Sprint 3A introduces the AI agent's first external API integration: web search via the Perplexity sonar API. This creates precedent for how the agent interacts with external services, handling API keys, timeouts, rate limits, error surfaces, and cost tracking. Future tools (LinkedIn enrichment, email sending, CRM lookups) will follow the same patterns.

Key constraints:

1. **Never expose raw API errors** -- Users interact with the agent through a chat interface. API stack traces, HTTP status codes, and vendor-specific error formats must never leak into the conversation. The agent should see only human-friendly error messages.
2. **Cost visibility** -- Every external API call has a cost. The platform must track per-call costs for tenant billing and admin monitoring.
3. **Rate limiting is non-negotiable** -- Without limits, the AI agent could burn through API quotas and budget in a single turn. Limits must be enforced at the executor level, not trusted to the model's behavior.
4. **Graceful degradation** -- Missing API keys, expired credentials, or service outages should produce helpful guidance, not crash the agent loop.

## Decision

### 1. API Key Management

External API keys are stored as environment variables (e.g., `PERPLEXITY_API_KEY`) and read at tool execution time, not at import time. This means:

- Missing keys don't prevent server startup
- Keys can be rotated without restarting the container
- The tool handler checks for the key and returns a structured error if missing

**Alternatives considered:**
- Database-stored credentials: Adds encryption complexity and migration overhead for a single-tenant MVP. Will revisit when multi-tenant credential management is needed (BL-099).
- Config file: Less secure than env vars, harder to manage in Docker deployments.

### 2. Timeout Strategy

External API calls use a **10-second hard timeout** with **no retries** for interactive search. The rationale:

- The agent loop is synchronous from the user's perspective (SSE stream). A 60-second retry loop blocks the entire conversation.
- 10 seconds is long enough for most sonar queries but short enough that the user doesn't think the chat is frozen.
- The agent receives a structured timeout error and can suggest the user try a more specific query.

For background/batch operations (enrichment pipelines), the existing `PerplexityClient` defaults (60s timeout, 2 retries) remain appropriate.

### 3. Rate Limiting

Rate limiting is enforced at the **agent executor level** (`agent_executor.py`), not in individual tool handlers. This provides:

- A single enforcement point that can't be bypassed by adding new tools
- Per-tool configurable limits via `TOOL_RATE_LIMITS` dict
- Default limit of 5 calls per tool per agent turn
- Custom limit of 3 calls per turn for `web_search` (cost control)

When a limit is hit, the executor returns an error result to Claude with the message "Rate limit: {tool} can be called at most {N} times per turn." Claude then uses the data it already has to answer the question.

**Alternatives considered:**
- Token bucket / sliding window: Over-engineered for the current agent loop model (one user, synchronous turns). The per-turn counter is simpler and sufficient.
- Model-side instruction: "Don't call search more than 3 times." Unreliable -- models don't consistently follow tool-use count instructions.

### 4. Cost Tracking

Every successful external API call creates an `LlmUsageLog` entry with:
- `operation`: identifies the tool (e.g., `agent_web_search`)
- `provider`: identifies the vendor (e.g., `perplexity`)
- `model`, `input_tokens`, `output_tokens`: for cost calculation
- `duration_ms`: for performance monitoring
- `metadata`: additional context (e.g., query length)

Failed calls (timeout, HTTP error) do **not** create log entries because no tokens were consumed.

## Consequences

- All future agent tools that call external APIs should follow this pattern: env var for key, 10s timeout (interactive) or 60s (batch), structured error returns, LlmUsageLog entry on success.
- The `TOOL_RATE_LIMITS` dict in `agent_executor.py` must be updated when adding new cost-bearing tools.
- The `llm_logger.py` pricing table must be updated when adding new providers/models.
