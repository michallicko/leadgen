-- Migration 036: Strategy version snapshots for AI tool edits
--
-- Stores full snapshots of the strategy document before each AI edit.
-- Enables undo for AI edits and batch undo (via turn_id grouping).

BEGIN;

CREATE TABLE IF NOT EXISTS strategy_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES strategy_documents(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    version         INTEGER NOT NULL,
    content         TEXT,
    extracted_data  JSONB DEFAULT '{}'::jsonb,
    edit_source     VARCHAR(20) NOT NULL DEFAULT 'ai_tool',
    turn_id         UUID,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_strategy_versions_doc_version
    ON strategy_versions(document_id, version DESC);

CREATE INDEX idx_strategy_versions_turn
    ON strategy_versions(document_id, turn_id);

COMMIT;
