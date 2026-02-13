-- 005_stage_runs.sql
-- Per-node pipeline run tracking (replaces n8n in-memory progress store)

CREATE TABLE stage_runs (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id),
  batch_id      UUID REFERENCES batches(id),
  owner_id      UUID REFERENCES owners(id),
  stage         TEXT NOT NULL,      -- 'l1', 'triage', 'l2', 'person', 'generate', 'review'
  status        TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, stopping, stopped
  total         INT DEFAULT 0,
  done          INT DEFAULT 0,
  failed        INT DEFAULT 0,
  cost_usd      NUMERIC(10,4) DEFAULT 0,
  config        JSONB DEFAULT '{}', -- tier_filter, job_title_filter, etc.
  error         TEXT,
  started_at    TIMESTAMPTZ DEFAULT now(),
  completed_at  TIMESTAMPTZ,
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_stage_runs_tenant ON stage_runs(tenant_id, stage, status);
CREATE INDEX idx_stage_runs_batch ON stage_runs(batch_id, stage);

-- Function to auto-update updated_at (idempotent)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER set_stage_runs_updated_at
  BEFORE UPDATE ON stage_runs
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
