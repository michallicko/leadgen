-- 006_pipeline_stages.sql
-- Extend pipeline_runs to support reactive parallel pipeline with stage tracking

-- Add stages JSONB column (maps stage name → stage_run_id)
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS stages JSONB DEFAULT '{}';

-- Expand status CHECK to include stopping/stopped
ALTER TABLE pipeline_runs DROP CONSTRAINT IF EXISTS pipeline_runs_status_check;
ALTER TABLE pipeline_runs ADD CONSTRAINT pipeline_runs_status_check
  CHECK (status IN ('running', 'completed', 'failed', 'stopping', 'stopped'));

-- Add updated_at trigger (reuse function from 005_stage_runs.sql)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'set_pipeline_runs_updated_at'
  ) THEN
    CREATE TRIGGER set_pipeline_runs_updated_at
      BEFORE UPDATE ON pipeline_runs
      FOR EACH ROW
      EXECUTE FUNCTION update_updated_at_column();
  END IF;
END;
$$;
