-- Token credit system: per-namespace budgets + credit tracking
-- BL-056: 1 credit = $0.001 USD worth of LLM usage

-- Namespace token budgets table
CREATE TABLE namespace_token_budgets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    total_budget    INTEGER NOT NULL DEFAULT 0,
    used_credits    INTEGER NOT NULL DEFAULT 0,
    reserved_credits INTEGER NOT NULL DEFAULT 0,
    reset_period    TEXT,                          -- NULL, 'monthly', 'quarterly'
    reset_day       INTEGER DEFAULT 1,
    last_reset_at   TIMESTAMPTZ,
    next_reset_at   TIMESTAMPTZ,
    enforcement_mode TEXT NOT NULL DEFAULT 'soft', -- 'hard', 'soft', 'monitor'
    alert_threshold_pct INTEGER DEFAULT 80,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id)
);

CREATE INDEX idx_token_budgets_tenant ON namespace_token_budgets(tenant_id);

-- Add credits_consumed column to existing llm_usage_log
ALTER TABLE llm_usage_log ADD COLUMN credits_consumed INTEGER NOT NULL DEFAULT 0;

-- Backfill existing rows: credits = ROUND(cost_usd * 1000)
UPDATE llm_usage_log SET credits_consumed = ROUND(cost_usd * 1000);
