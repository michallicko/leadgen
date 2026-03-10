-- Migration 046: Agent metrics and tenant token budgets
-- Sprint 17: Operational Concerns (BL-272, BL-273)

-- Per-turn token and cost tracking
CREATE TABLE IF NOT EXISTS agent_metrics (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    user_id uuid REFERENCES users(id),
    trace_id text NOT NULL,
    turn_index integer NOT NULL DEFAULT 0,
    model text NOT NULL,
    input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    cost_usd numeric(12, 8) NOT NULL DEFAULT 0,
    tool_calls jsonb DEFAULT '[]'::jsonb,
    duration_ms integer,
    created_at timestamptz DEFAULT now()
);

-- Indexes for querying by tenant, time range, and trace
CREATE INDEX IF NOT EXISTS idx_agent_metrics_tenant_created
    ON agent_metrics (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_trace
    ON agent_metrics (trace_id);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_user
    ON agent_metrics (user_id);

-- Tenant monthly token budgets
CREATE TABLE IF NOT EXISTS tenant_token_budgets (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id) UNIQUE,
    monthly_token_limit bigint NOT NULL DEFAULT 1000000,
    warn_at_percent integer NOT NULL DEFAULT 75,
    hard_limit_percent integer NOT NULL DEFAULT 100,
    current_period_start date NOT NULL DEFAULT date_trunc('month', now()),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_token_budgets_tenant
    ON tenant_token_budgets (tenant_id);
