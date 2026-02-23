# BL-056: Token Credit System with Per-Namespace Budgets

**Status**: Spec'd
**Priority**: Must Have
**Effort**: L
**Depends on**: BL-055 (LLM cost logging — `LlmUsageLog` model + `llm_logger.py`)
**Theme**: Platform Foundation

---

## Problem Statement

The platform makes LLM calls across multiple features (playbook chat, enrichment, message generation, CSV column mapping) using multiple providers (Anthropic, Perplexity). Today:

1. **No per-tenant metering** — `LlmUsageLog` records usage but nothing enforces limits
2. **No budget controls** — any tenant can consume unlimited LLM resources
3. **No admin visibility** — namespace admins cannot see their own usage; only super admins via `/api/llm-usage/summary`
4. **No cost predictability** — tenants have no way to forecast or control spend
5. **Billing foundation missing** — can't charge tenants for usage without metering + budgets

For a multi-tenant paid product, this is a critical gap. Every LLM-powered feature needs metering and budget awareness.

---

## Token Conversion Model

### Recommendation: Cost-Based Credits (Option B)

**1 credit = $0.001 USD worth of LLM usage**

This is the recommended approach because:

- **Provider-agnostic**: Works the same whether the call goes to Anthropic, Perplexity, or future providers
- **Simple mental model**: 1,000 credits = $1.00 of LLM usage
- **Already computed**: `llm_logger.py` already computes `cost_usd` per call — credits are `cost_usd * 1000`
- **Transparent**: Users can verify credits match actual costs
- **Future-proof**: Adding new models/providers requires only updating `MODEL_PRICING`, not the credit scheme

### Why Not the Alternatives

- **Option A (1 credit = 1 LLM token)**: Misleading — 1 token on Claude Opus costs 19x more than 1 token on Claude Haiku. Users would see wildly different credit consumption for similar tasks depending on which model was used internally.
- **Option C (operation-based credits)**: Rigid — requires redefining credit values whenever we add a new operation or change the underlying model. Also hides cost efficiency improvements from users.

### Credit Display

| Credits | USD Equivalent | Example Usage |
|---------|----------------|---------------|
| 1 | $0.001 | ~1 token on Claude Haiku |
| 10 | $0.01 | Short chat response |
| 100 | $0.10 | Typical chat turn with context |
| 1,000 | $1.00 | Full L2 company enrichment |
| 10,000 | $10.00 | Campaign message generation (50 contacts) |

---

## Data Model

### New Table: `namespace_token_budgets`

Stores the budget configuration and running balance per namespace.

```sql
CREATE TABLE namespace_token_budgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    total_budget INTEGER NOT NULL DEFAULT 0,          -- total credits allocated
    used_credits INTEGER NOT NULL DEFAULT 0,           -- running total of credits consumed
    reserved_credits INTEGER NOT NULL DEFAULT 0,       -- credits reserved by in-flight operations
    reset_period TEXT,                                 -- NULL (one-time), 'monthly', 'quarterly'
    reset_day INTEGER DEFAULT 1,                       -- day of month/quarter to reset
    last_reset_at TIMESTAMPTZ,
    next_reset_at TIMESTAMPTZ,
    enforcement_mode TEXT NOT NULL DEFAULT 'soft',     -- 'hard', 'soft', 'monitor'
    alert_threshold_pct INTEGER DEFAULT 80,            -- warn at this % of budget
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id)
);
```

**Key design decisions:**

- **`reserved_credits`**: Handles in-flight operations (e.g., enrichment pipeline running). Reserved on start, moved to `used_credits` on completion. Prevents budget overruns from concurrent calls.
- **`enforcement_mode`**: Three modes for gradual rollout:
  - `monitor` — log only, no blocking (default for existing tenants)
  - `soft` — warn users at threshold, allow overrun up to 120% of budget
  - `hard` — block LLM calls when budget exhausted (for paid plans)
- **Single row per tenant**: Budget is namespace-level, not per-user. `UNIQUE(tenant_id)` enforces this.

### Extend Existing: `llm_usage_log`

Add a `credits_consumed` column to the existing `LlmUsageLog` table (BL-055).

```sql
ALTER TABLE llm_usage_log
    ADD COLUMN credits_consumed INTEGER NOT NULL DEFAULT 0;
```

Credits are computed at log time: `credits_consumed = ROUND(cost_usd * 1000)`. This denormalizes for query performance — avoids recomputing credits from cost on every dashboard query.

### SQLAlchemy Models

```python
class NamespaceTokenBudget(db.Model):
    __tablename__ = "namespace_token_budgets"

    id = db.Column(UUID(as_uuid=False), primary_key=True,
                   server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id", ondelete="CASCADE"),
                          nullable=False, unique=True)
    total_budget = db.Column(db.Integer, nullable=False, default=0)
    used_credits = db.Column(db.Integer, nullable=False, default=0)
    reserved_credits = db.Column(db.Integer, nullable=False, default=0)
    reset_period = db.Column(db.Text)  # NULL, 'monthly', 'quarterly'
    reset_day = db.Column(db.Integer, default=1)
    last_reset_at = db.Column(db.DateTime(timezone=True))
    next_reset_at = db.Column(db.DateTime(timezone=True))
    enforcement_mode = db.Column(db.Text, nullable=False, default="soft")
    alert_threshold_pct = db.Column(db.Integer, default=80)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    @property
    def remaining_credits(self):
        return max(0, self.total_budget - self.used_credits - self.reserved_credits)

    @property
    def usage_pct(self):
        if self.total_budget == 0:
            return 0
        return round((self.used_credits / self.total_budget) * 100, 1)

    def to_dict(self):
        return {
            "tenant_id": str(self.tenant_id),
            "total_budget": self.total_budget,
            "used_credits": self.used_credits,
            "reserved_credits": self.reserved_credits,
            "remaining_credits": self.remaining_credits,
            "usage_pct": self.usage_pct,
            "reset_period": self.reset_period,
            "enforcement_mode": self.enforcement_mode,
            "alert_threshold_pct": self.alert_threshold_pct,
            "last_reset_at": self.last_reset_at.isoformat() if self.last_reset_at else None,
            "next_reset_at": self.next_reset_at.isoformat() if self.next_reset_at else None,
        }
```

---

## Budget Enforcement

### Architecture

Budget checking is a **decorator/utility function** applied at LLM call sites, not middleware. This gives each call site control over cost estimation and error handling.

```python
# api/services/budget.py

from ..models import NamespaceTokenBudget, db

class BudgetExceededError(Exception):
    """Raised when a namespace has exhausted its token budget."""
    def __init__(self, tenant_id, remaining, required):
        self.tenant_id = tenant_id
        self.remaining = remaining
        self.required = required
        super().__init__(
            f"Token budget exceeded: {remaining} credits remaining, "
            f"{required} required"
        )

def check_budget(tenant_id, estimated_credits=0):
    """Check if tenant has sufficient budget for an LLM operation.

    Args:
        tenant_id: UUID string
        estimated_credits: Estimated credits for the operation (0 = skip estimate)

    Returns:
        NamespaceTokenBudget or None (None = no budget configured, allow all)

    Raises:
        BudgetExceededError: If enforcement_mode='hard' and budget exhausted
    """
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if not budget:
        return None  # No budget = unlimited (monitor mode by default)

    if budget.enforcement_mode == "monitor":
        return budget  # Log only, never block

    remaining = budget.remaining_credits

    if budget.enforcement_mode == "hard":
        if remaining <= 0 or (estimated_credits > 0 and remaining < estimated_credits):
            raise BudgetExceededError(tenant_id, remaining, estimated_credits)

    if budget.enforcement_mode == "soft":
        # Soft mode allows up to 120% of budget
        soft_limit = int(budget.total_budget * 1.2)
        effective_remaining = soft_limit - budget.used_credits - budget.reserved_credits
        if effective_remaining <= 0:
            raise BudgetExceededError(tenant_id, remaining, estimated_credits)

    return budget


def reserve_credits(tenant_id, credits):
    """Reserve credits for an in-flight operation. Returns reservation ID."""
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if budget:
        budget.reserved_credits += credits
        budget.updated_at = db.func.now()
        db.session.flush()
    return credits


def consume_credits(tenant_id, credits, reserved=0):
    """Move credits from reserved to used (or add directly to used).

    Called after an LLM call completes with actual credit count.
    """
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if budget:
        if reserved > 0:
            budget.reserved_credits = max(0, budget.reserved_credits - reserved)
        budget.used_credits += credits
        budget.updated_at = db.func.now()
        db.session.flush()


def release_reservation(tenant_id, credits):
    """Release reserved credits without consuming (operation cancelled/failed)."""
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if budget:
        budget.reserved_credits = max(0, budget.reserved_credits - credits)
        budget.updated_at = db.func.now()
        db.session.flush()
```

### Integration with `log_llm_usage()`

Extend the existing `log_llm_usage()` in `llm_logger.py` to also consume credits:

```python
def log_llm_usage(tenant_id, operation, model, input_tokens, output_tokens,
                  provider="anthropic", user_id=None, duration_ms=None,
                  metadata=None, reserved_credits=0):
    cost = compute_cost(provider, model, input_tokens, output_tokens)
    credits = int(cost * 1000)  # 1 credit = $0.001

    entry = LlmUsageLog(
        tenant_id=str(tenant_id),
        user_id=str(user_id) if user_id else None,
        operation=operation,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        credits_consumed=credits,
        duration_ms=duration_ms,
        extra=metadata or {},
    )
    db.session.add(entry)

    # Consume credits from budget (moves reserved → used)
    from .budget import consume_credits
    consume_credits(tenant_id, credits, reserved=reserved_credits)

    return entry
```

### What Happens When Budget Is Exceeded

| Mode | At Threshold (80%) | At 100% | At 120% |
|------|-------------------|---------|---------|
| `monitor` | Log warning | Log warning | Log warning |
| `soft` | UI warning banner | UI warning + "running low" | Block LLM calls |
| `hard` | UI warning banner | Block LLM calls | Block LLM calls |

**User experience when blocked:**

- **Chat**: "Your workspace has used its token budget for this period. Contact your admin to increase the budget or wait for the next reset."
- **Enrichment**: Pipeline stage skipped with error "insufficient credits". Stage marked as failed with `error = "budget_exceeded"`. Other stages continue.
- **Message generation**: Generation halted, already-generated messages preserved. UI shows "X of Y messages generated before budget limit."

### Pre-Operation Cost Estimates

Key operations provide estimates before execution:

| Operation | Estimate Method |
|-----------|----------------|
| Chat message | Fixed estimate: 50 credits (covers typical turn) |
| L1 enrichment | Per company: 5 credits (1 Perplexity call) |
| L2 enrichment | Per company: 500 credits (2 Perplexity + 1 Anthropic) |
| Person enrichment | Per contact: 200 credits (1 Perplexity + 1 Anthropic) |
| Message generation | Per message: 30 credits (1 Anthropic call) |
| CSV column mapping | Fixed: 20 credits |
| Strategy extraction | Fixed: 100 credits |

These estimates are shown in the UI before execution and used for reservation.

---

## API Endpoints

### Namespace Admin Endpoints

These are accessible to users with `admin` role on the namespace (not just super_admin).

#### `GET /api/admin/tokens`

Current budget status and usage summary.

```json
{
  "budget": {
    "total_budget": 50000,
    "used_credits": 12340,
    "reserved_credits": 500,
    "remaining_credits": 37160,
    "usage_pct": 24.7,
    "enforcement_mode": "soft",
    "reset_period": "monthly",
    "next_reset_at": "2026-03-01T00:00:00Z"
  },
  "current_period": {
    "start": "2026-02-01T00:00:00Z",
    "end": "2026-02-28T23:59:59Z",
    "total_calls": 847,
    "total_credits": 12340,
    "total_cost_usd": 12.34
  },
  "by_operation": [
    {"operation": "playbook_chat", "calls": 312, "credits": 4200, "pct": 34.0},
    {"operation": "l2_enrichment", "calls": 45, "credits": 3800, "pct": 30.8},
    {"operation": "message_generation", "calls": 290, "credits": 2100, "pct": 17.0},
    {"operation": "l1_enrichment", "calls": 150, "credits": 1200, "pct": 9.7},
    {"operation": "person_enrichment", "calls": 30, "credits": 840, "pct": 6.8},
    {"operation": "strategy_extraction", "calls": 10, "credits": 150, "pct": 1.2},
    {"operation": "csv_column_mapping", "calls": 10, "credits": 50, "pct": 0.4}
  ],
  "by_user": [
    {"user_id": "...", "display_name": "Michal", "credits": 8000, "pct": 64.8},
    {"user_id": "...", "display_name": "Anton", "credits": 4340, "pct": 35.2}
  ]
}
```

#### `GET /api/admin/tokens/history`

Usage over time for charts.

**Query params**: `period` (day|week|month), `start_date`, `end_date`

```json
{
  "period": "day",
  "data": [
    {"date": "2026-02-20", "credits": 1200, "calls": 89, "cost_usd": 1.20},
    {"date": "2026-02-21", "credits": 980, "calls": 72, "cost_usd": 0.98},
    {"date": "2026-02-22", "credits": 1500, "calls": 110, "cost_usd": 1.50}
  ]
}
```

#### `GET /api/admin/tokens/breakdown`

Detailed breakdown by operation + model for cost analysis.

```json
{
  "breakdown": [
    {
      "operation": "l2_enrichment",
      "provider": "perplexity",
      "model": "sonar-pro",
      "calls": 90,
      "input_tokens": 45000,
      "output_tokens": 72000,
      "credits": 2100,
      "avg_credits_per_call": 23
    },
    {
      "operation": "l2_enrichment",
      "provider": "anthropic",
      "model": "claude-sonnet-4-5-20250929",
      "calls": 45,
      "input_tokens": 180000,
      "output_tokens": 90000,
      "credits": 1700,
      "avg_credits_per_call": 38
    }
  ]
}
```

### Super Admin Budget Management

#### `PUT /api/admin/tokens/budget`

Set or update a namespace's budget. **Super admin only.**

```json
// Request
{
  "total_budget": 50000,
  "reset_period": "monthly",
  "reset_day": 1,
  "enforcement_mode": "soft",
  "alert_threshold_pct": 80
}

// Response
{
  "budget": { ... },
  "message": "Budget updated successfully"
}
```

#### `POST /api/admin/tokens/topup`

Add credits to a namespace's current budget. **Super admin only.**

```json
// Request
{ "credits": 10000 }

// Response
{
  "budget": { ... },
  "added_credits": 10000,
  "new_total": 60000
}
```

---

## Admin UI: Token Usage Dashboard

### Location

New tab under the existing admin section, accessible to namespace admins (not just super admins). Route: `/{namespace}/admin/tokens` or integrated as a panel in the existing LLM Costs page.

### Components

1. **Budget Meter**: Large circular gauge showing used/total credits with color coding (green < 60%, yellow 60-80%, orange 80-95%, red > 95%)

2. **Current Period Summary**: Cards showing total credits used, remaining credits, days left in period, projected usage at current rate

3. **Usage by Operation**: Horizontal bar chart showing credit consumption per operation type (chat, enrichment, messages, etc.)

4. **Usage Over Time**: Line chart (daily/weekly/monthly) showing credit consumption trend with budget line overlay

5. **Top Consumers**: Table showing per-user credit consumption (if multi-user namespace)

6. **Budget Warning Banner**: Persistent banner at top of all pages when usage exceeds alert threshold:
   - At 80%: "Your workspace has used 80% of its token budget this month."
   - At 100% (soft): "Token budget exceeded. Some AI features may be limited."
   - At 100% (hard): "Token budget exhausted. AI features are paused until [reset date]."

---

## Integration Points

### Where to Add Budget Checks

Every LLM call site needs a pre-check. The integration follows a consistent pattern:

| Call Site | File | Budget Check Location |
|-----------|------|----------------------|
| Playbook chat | `playbook_routes.py:post_chat_message()` | Before `client.stream_query()` |
| L1 enrichment | `l1_enricher.py:enrich_l1()` | Before Perplexity call |
| L2 enrichment | `l2_enricher.py:enrich_l2()` | Before Perplexity + Anthropic calls |
| Person enrichment | `person_enricher.py` | Before LLM calls |
| Message generation | `message_generator.py` | Before each message's Claude call |
| CSV column mapping | `csv_mapper.py` | Before mapping call |
| Strategy extraction | `playbook_routes.py:extract_strategy()` | Before `client.query()` |
| QC checker | `qc_checker.py` | Before LLM calls (if any) |

### Pattern for Integration

```python
# Example: playbook chat budget check
from api.services.budget import check_budget, BudgetExceededError

@playbook_bp.route("/api/playbook/chat", methods=["POST"])
@require_auth
def post_chat_message():
    tenant_id = resolve_tenant()
    # ... existing code ...

    # Budget check before LLM call
    try:
        check_budget(tenant_id, estimated_credits=50)
    except BudgetExceededError as e:
        return jsonify({
            "error": "Token budget exceeded",
            "remaining_credits": e.remaining,
            "enforcement_mode": "hard",
            "message": "Your workspace has used its token budget. "
                       "Contact your admin to increase the budget."
        }), 429

    # ... proceed with LLM call ...
```

### Budget Reset Scheduler

A periodic task (cron or scheduler) resets budgets:

```python
def reset_expired_budgets():
    """Reset budgets where next_reset_at has passed."""
    now = datetime.now(timezone.utc)
    expired = NamespaceTokenBudget.query.filter(
        NamespaceTokenBudget.next_reset_at <= now,
        NamespaceTokenBudget.reset_period.isnot(None)
    ).all()

    for budget in expired:
        budget.used_credits = 0
        budget.reserved_credits = 0
        budget.last_reset_at = now
        budget.next_reset_at = _compute_next_reset(budget.reset_period, budget.reset_day)
        budget.updated_at = now

    db.session.commit()
```

This can run via:
- Flask CLI command (`flask reset-budgets`) invoked by cron
- The existing `scheduler.py` service if it supports periodic tasks
- A lightweight background thread on app startup

---

## User Stories & Acceptance Criteria

### US-1: Namespace Admin Views Token Usage

**As a** namespace admin,
**I want to** see my workspace's token usage and remaining budget,
**So that** I can manage LLM costs and avoid service interruption.

**Acceptance Criteria:**

- **Given** a namespace with a configured budget of 50,000 credits and 12,340 used,
  **When** the admin navigates to the token dashboard,
  **Then** they see a gauge showing 24.7% used, 37,160 remaining, and a breakdown by operation type.

- **Given** usage data spanning 30 days,
  **When** the admin views the usage history chart,
  **Then** they see daily credit consumption with a trend line and the budget limit visualized.

- **Given** the namespace has 3 users,
  **When** the admin views the "Top Consumers" section,
  **Then** they see each user's credit consumption and percentage of total.

### US-2: Budget Warning

**As a** namespace user,
**I want to** see a warning when my workspace is running low on credits,
**So that** I can request a top-up before features are blocked.

**Acceptance Criteria:**

- **Given** a namespace at 82% budget usage with `alert_threshold_pct = 80`,
  **When** any page loads,
  **Then** a persistent yellow banner appears: "Your workspace has used 82% of its token budget this month."

- **Given** a namespace at 100% with `enforcement_mode = 'soft'`,
  **When** the user sends a chat message,
  **Then** the message goes through but a warning appears: "Token budget exceeded. Some features may be limited soon."

### US-3: Hard Budget Enforcement

**As a** platform operator,
**I want to** enforce hard budget limits on tenant LLM usage,
**So that** costs are predictable and tenants pay for what they use.

**Acceptance Criteria:**

- **Given** a namespace with 0 remaining credits and `enforcement_mode = 'hard'`,
  **When** a user tries to send a chat message,
  **Then** the API returns HTTP 429 with a clear error message and the chat UI shows "Token budget exhausted."

- **Given** a namespace with 0 remaining credits and `enforcement_mode = 'hard'`,
  **When** an enrichment pipeline runs,
  **Then** the pipeline stage fails with `error = 'budget_exceeded'` and the next stage continues for non-LLM work.

- **Given** a namespace with 100 remaining credits and an enrichment estimated at 500 credits,
  **When** the user triggers enrichment from the dashboard,
  **Then** the UI shows "Insufficient credits: 500 needed, 100 available" and blocks the action.

### US-4: Super Admin Manages Budgets

**As a** super admin,
**I want to** set and adjust token budgets per namespace,
**So that** I can control platform costs and offer tiered plans.

**Acceptance Criteria:**

- **Given** a new namespace with no budget configured,
  **When** the super admin sets a budget of 50,000 monthly credits,
  **Then** the budget is created with `reset_period = 'monthly'` and `enforcement_mode = 'soft'`.

- **Given** a namespace at 95% budget usage,
  **When** the super admin tops up 10,000 credits,
  **Then** `total_budget` increases by 10,000 and `remaining_credits` reflects the addition.

### US-5: Budget Resets Automatically

**As a** namespace with a monthly budget,
**I want my** credit counter to reset at the start of each month,
**So that** I get a fresh allocation without manual intervention.

**Acceptance Criteria:**

- **Given** a namespace with `reset_period = 'monthly'`, `reset_day = 1`, and `next_reset_at = '2026-03-01'`,
  **When** the reset scheduler runs on March 1st,
  **Then** `used_credits` resets to 0, `last_reset_at` updates, and `next_reset_at` moves to April 1st.

### US-6: Concurrent Operations Don't Overrun Budget

**As a** platform operator,
**I want** concurrent LLM operations to respect budget limits,
**So that** parallel enrichment runs can't collectively exceed the budget.

**Acceptance Criteria:**

- **Given** a namespace with 1,000 remaining credits,
  **When** two L2 enrichment operations start simultaneously (each estimating 500 credits),
  **Then** both reserve 500 credits (`reserved_credits = 1000`), and a third operation is blocked.

- **Given** an enrichment operation reserved 500 credits but only consumed 400,
  **When** the operation completes,
  **Then** `used_credits` increases by 400 and `reserved_credits` decreases by 500 (net: 100 credits returned).

---

## Edge Cases

### Budget Exceeded Mid-Operation

- **Enrichment pipeline**: If budget runs out mid-batch, complete the current item (already paid for), then skip remaining items with `error = 'budget_exceeded'`. Mark the stage run as `partial`.
- **Message generation**: Complete the current message, then stop generation. Already-generated messages are preserved. Campaign status updates to `generation_partial`.
- **Chat streaming**: If budget is exceeded during streaming, complete the current response (it's already being generated). The *next* message will be blocked.

### Concurrent Calls / Race Conditions

- Use `SELECT ... FOR UPDATE` on the budget row when checking + reserving to prevent race conditions
- If the DB doesn't support row locking (e.g., SQLite in tests), fall back to optimistic locking with retry

### Budget Reset Timing

- Reset happens at midnight UTC on `reset_day`
- If `reset_day = 31` and the month has 28 days, reset on the last day of the month
- Operations in-flight during reset: their reservations are cleared (reset sets `reserved_credits = 0`)

### Free Tier / No Budget Configured

- If a namespace has no `NamespaceTokenBudget` row, all LLM calls proceed without limit
- This is the default for existing tenants — budget enforcement is opt-in
- Super admin explicitly creates a budget row to enable metering

### Cost Tracking Without Budget

- `credits_consumed` is always populated in `llm_usage_log` even for tenants without a budget
- This enables retroactive analysis ("how much would tenant X have used?")

---

## Migration Plan

### Phase 1: Schema + Metering (No Enforcement)

1. Migration: Create `namespace_token_budgets` table
2. Migration: Add `credits_consumed` column to `llm_usage_log`
3. Update `log_llm_usage()` to compute and store `credits_consumed`
4. Backfill existing `llm_usage_log` rows: `UPDATE llm_usage_log SET credits_consumed = ROUND(cost_usd * 1000)`
5. Add namespace admin API endpoints (read-only: `/api/admin/tokens`, `/api/admin/tokens/history`)

### Phase 2: Budget Management + Soft Enforcement

6. Add super admin budget management endpoints (`PUT /api/admin/tokens/budget`, `POST /api/admin/tokens/topup`)
7. Implement `budget.py` service (check_budget, reserve, consume, release)
8. Integrate budget checks at all LLM call sites (enforcement_mode = soft initially)
9. Add budget warning banner to frontend
10. Add budget reset scheduler

### Phase 3: Admin Dashboard + Hard Enforcement

11. Build token usage dashboard UI (gauge, charts, breakdown)
12. Enable hard enforcement mode for paid plans
13. Add pre-operation cost estimates to enrichment and generation UI
14. Add budget alert emails/notifications

---

## Relationship to BL-055 (LLM Cost Logging)

BL-056 builds directly on BL-055's infrastructure:

| BL-055 Provides | BL-056 Adds |
|------------------|-------------|
| `LlmUsageLog` model | `credits_consumed` column |
| `log_llm_usage()` function | Credit consumption + budget deduction |
| `compute_cost()` pricing | Credit conversion (`cost * 1000`) |
| `/api/llm-usage/summary` (super admin) | `/api/admin/tokens` (namespace admin) |
| Per-call cost tracking | Per-namespace budget + enforcement |

BL-056 does NOT duplicate BL-055's work. It extends it with budgets, enforcement, and tenant-facing visibility.

---

## Non-Goals (Out of Scope)

- **Billing/payment integration**: No Stripe, no invoicing. Budget is set by super admin manually.
- **Per-user budgets**: Budget is per-namespace, not per-user. Per-user limits are a future enhancement.
- **Real-time WebSocket updates**: Dashboard polls on page load. Real-time push is future work.
- **Credit marketplace**: No ability for tenants to buy credits directly. Super admin allocates.
- **Model selection by users**: Users can't choose cheaper/expensive models. The platform picks the model per operation.
