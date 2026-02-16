-- Migration 007: Import Jobs table for CSV contact list import
-- Tracks upload → AI mapping → preview → execute workflow

CREATE TABLE import_jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    batch_id        UUID REFERENCES batches(id),
    owner_id        UUID REFERENCES owners(id),
    filename        TEXT NOT NULL,
    file_size_bytes INTEGER,
    total_rows      INTEGER NOT NULL DEFAULT 0,
    headers         JSONB NOT NULL DEFAULT '[]',
    sample_rows     JSONB DEFAULT '[]',
    raw_csv         TEXT,
    column_mapping  JSONB DEFAULT '{}',
    mapping_confidence NUMERIC(3,2),
    contacts_created    INTEGER DEFAULT 0,
    contacts_updated    INTEGER DEFAULT 0,
    contacts_skipped    INTEGER DEFAULT 0,
    companies_created   INTEGER DEFAULT 0,
    companies_linked    INTEGER DEFAULT 0,
    enrichment_depth    TEXT,
    estimated_cost_usd  NUMERIC(10,4) DEFAULT 0,
    actual_cost_usd     NUMERIC(10,4) DEFAULT 0,
    dedup_strategy      TEXT DEFAULT 'skip',
    dedup_results       JSONB DEFAULT '{}',
    status          TEXT DEFAULT 'uploaded',
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_import_jobs_tenant ON import_jobs(tenant_id);
CREATE INDEX idx_import_jobs_status ON import_jobs(status);

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS import_job_id UUID REFERENCES import_jobs(id);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS import_job_id UUID REFERENCES import_jobs(id);
