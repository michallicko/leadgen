-- 020: Create company_enrichment_l1 table
-- BL-045: Enrichment Field Audit (Task 2)

BEGIN;

CREATE TABLE company_enrichment_l1 (
    company_id          UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    triage_notes        TEXT,
    pre_score           NUMERIC(4,1),
    research_query      TEXT,
    raw_response        JSONB DEFAULT '{}',
    confidence          NUMERIC(3,2),
    quality_score       SMALLINT,
    qc_flags            JSONB DEFAULT '[]',
    enriched_at         TIMESTAMP WITH TIME ZONE,
    enrichment_cost_usd NUMERIC(10,4) DEFAULT 0,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Migrate existing data from companies table
INSERT INTO company_enrichment_l1 (company_id, triage_notes, pre_score, enriched_at)
SELECT id, triage_notes, pre_score, updated_at
FROM companies
WHERE triage_notes IS NOT NULL OR pre_score IS NOT NULL;

COMMIT;
