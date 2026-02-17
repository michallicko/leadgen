-- 019: Rename batches -> tags + add new entity fields
-- BL-045: Enrichment Field Audit (Task 1)

BEGIN;

-- ── Rename batches table to tags ──────────────────────────────
ALTER TABLE batches RENAME TO tags;

-- Rename batch_id columns across all tables
ALTER TABLE companies RENAME COLUMN batch_id TO tag_id;
ALTER TABLE contacts RENAME COLUMN batch_id TO tag_id;
ALTER TABLE campaigns RENAME COLUMN batch_id TO tag_id;
ALTER TABLE messages RENAME COLUMN batch_id TO tag_id;
ALTER TABLE stage_runs RENAME COLUMN batch_id TO tag_id;
ALTER TABLE pipeline_runs RENAME COLUMN batch_id TO tag_id;
ALTER TABLE entity_stage_completions RENAME COLUMN batch_id TO tag_id;
ALTER TABLE import_jobs RENAME COLUMN batch_id TO tag_id;

-- Rename FK constraints (PostgreSQL auto-renames the FK reference target,
-- but constraint names keep old prefix — rename for clarity)
ALTER INDEX IF EXISTS batches_pkey RENAME TO tags_pkey;

-- Rename any indexes that reference old name
DO $$
BEGIN
    -- Rename indexes if they exist (names vary by migration version)
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_companies_batch_id') THEN
        ALTER INDEX idx_companies_batch_id RENAME TO idx_companies_tag_id;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contacts_batch_id') THEN
        ALTER INDEX idx_contacts_batch_id RENAME TO idx_contacts_tag_id;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_stage_runs_batch_id') THEN
        ALTER INDEX idx_stage_runs_batch_id RENAME TO idx_stage_runs_tag_id;
    END IF;
END $$;

-- ── New company fields ────────────────────────────────────────
ALTER TABLE companies ADD COLUMN IF NOT EXISTS website_url TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS logo_url TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS last_enriched_at TIMESTAMPTZ;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS data_quality_score SMALLINT;

-- ── New contact fields ────────────────────────────────────────
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS last_enriched_at TIMESTAMPTZ;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS employment_verified_at TIMESTAMPTZ;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS employment_status TEXT;

COMMIT;
