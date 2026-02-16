-- LLM usage logging table for per-call cost tracking
CREATE TABLE llm_usage_log (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    user_id      UUID REFERENCES users(id),
    operation    TEXT NOT NULL,
    provider     TEXT NOT NULL DEFAULT 'anthropic',
    model        TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd     NUMERIC(10,6) NOT NULL DEFAULT 0,
    duration_ms  INTEGER,
    metadata     JSONB DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_llm_usage_tenant_created ON llm_usage_log(tenant_id, created_at DESC);
CREATE INDEX idx_llm_usage_tenant_op ON llm_usage_log(tenant_id, operation);
CREATE INDEX idx_llm_usage_created ON llm_usage_log(created_at DESC);
