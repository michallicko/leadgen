-- 016_entity_stage_completions.sql
-- Per-entity, per-stage completion tracking for the enrichment DAG.
-- Replaces the linear company.status model with a completion-record pattern
-- that supports parallel stages, field provenance, and dynamic eligibility.

CREATE TABLE entity_stage_completions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    batch_id        UUID NOT NULL REFERENCES batches(id),
    pipeline_run_id UUID REFERENCES pipeline_runs(id),
    entity_type     TEXT NOT NULL,            -- 'company' | 'contact'
    entity_id       UUID NOT NULL,
    stage           TEXT NOT NULL,            -- 'l1','l2','signals','ares','brreg','prh','recherche','isir','person','generate','qc'
    status          TEXT NOT NULL DEFAULT 'completed',  -- completed | failed | skipped
    cost_usd        NUMERIC(10,4) DEFAULT 0,
    error           TEXT,
    completed_at    TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT uq_esc_run_entity_stage UNIQUE (pipeline_run_id, entity_id, stage)
);

CREATE INDEX idx_esc_entity_stage ON entity_stage_completions(entity_id, stage, status);
CREATE INDEX idx_esc_batch_stage  ON entity_stage_completions(batch_id, stage, status);
CREATE INDEX idx_esc_pipeline_run ON entity_stage_completions(pipeline_run_id);
CREATE INDEX idx_esc_tenant       ON entity_stage_completions(tenant_id);

-- auto-update trigger (reuses function from 005_stage_runs.sql)
CREATE TRIGGER set_esc_updated_at
  BEFORE UPDATE ON entity_stage_completions
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ---------------------------------------------------------------------------
-- Backfill from existing data
-- ---------------------------------------------------------------------------

-- L1 completions: any company not in 'new' status has been through L1
INSERT INTO entity_stage_completions (tenant_id, batch_id, entity_type, entity_id, stage, status, cost_usd, completed_at)
SELECT c.tenant_id, c.batch_id, 'company', c.id, 'l1',
    CASE WHEN c.status = 'enrichment_failed' THEN 'failed' ELSE 'completed' END,
    COALESCE(c.enrichment_cost_usd, 0),
    c.updated_at
FROM companies c
WHERE c.batch_id IS NOT NULL
  AND c.status IS NOT NULL
  AND c.status != 'new';

-- L2 completions: companies that reached enriched_l2 or beyond
INSERT INTO entity_stage_completions (tenant_id, batch_id, entity_type, entity_id, stage, status, cost_usd, completed_at)
SELECT c.tenant_id, c.batch_id, 'company', c.id, 'l2',
    CASE WHEN c.status = 'enrichment_l2_failed' THEN 'failed' ELSE 'completed' END,
    COALESCE(el2.enrichment_cost_usd, 0),
    COALESCE(el2.enriched_at, c.updated_at)
FROM companies c
LEFT JOIN company_enrichment_l2 el2 ON el2.company_id = c.id
WHERE c.batch_id IS NOT NULL
  AND c.status IN ('enriched_l2', 'enrichment_l2_failed', 'enriched', 'synced', 'error_pushing_lemlist');

-- Person completions: contacts with processed_enrich = true
INSERT INTO entity_stage_completions (tenant_id, batch_id, entity_type, entity_id, stage, status, cost_usd, completed_at)
SELECT ct.tenant_id, ct.batch_id, 'contact', ct.id, 'person', 'completed',
    COALESCE(ce.enrichment_cost_usd, 0),
    COALESCE(ce.enriched_at, ct.updated_at)
FROM contacts ct
LEFT JOIN contact_enrichment ce ON ce.contact_id = ct.id
WHERE ct.batch_id IS NOT NULL
  AND ct.processed_enrich = true;

-- ARES/registry completions: from company_registry_data by country
INSERT INTO entity_stage_completions (tenant_id, batch_id, entity_type, entity_id, stage, status, cost_usd, completed_at)
SELECT c.tenant_id, c.batch_id, 'company', c.id,
    CASE crd.registry_country
        WHEN 'CZ' THEN 'ares'
        WHEN 'NO' THEN 'brreg'
        WHEN 'FI' THEN 'prh'
        WHEN 'FR' THEN 'recherche'
        ELSE 'ares'  -- fallback
    END,
    'completed', 0, crd.enriched_at
FROM company_registry_data crd
JOIN companies c ON c.id = crd.company_id
WHERE c.batch_id IS NOT NULL;

-- ISIR completions: from company_insolvency_data
INSERT INTO entity_stage_completions (tenant_id, batch_id, entity_type, entity_id, stage, status, cost_usd, completed_at)
SELECT c.tenant_id, c.batch_id, 'company', c.id, 'isir', 'completed', 0, cid.last_checked_at
FROM company_insolvency_data cid
JOIN companies c ON c.id = cid.company_id
WHERE c.batch_id IS NOT NULL;
