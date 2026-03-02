-- Migration 039: Workflow Transitions
-- Records explicit workflow phase transitions for audit and context.
-- The current phase is COMPUTED from actual data (not stored).

CREATE TABLE IF NOT EXISTS workflow_transitions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    from_phase TEXT NOT NULL,
    to_phase TEXT NOT NULL,
    trigger TEXT NOT NULL DEFAULT 'auto',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    user_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_transitions_tenant
    ON workflow_transitions (tenant_id, created_at DESC);
