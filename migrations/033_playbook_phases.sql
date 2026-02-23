-- 033: Add multi-phase support to strategy_documents
--
-- phase: tracks current workflow step (strategy -> contacts -> messages -> campaign)
-- playbook_selections: JSONB store for per-phase structured data

BEGIN;

ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS phase VARCHAR(20) NOT NULL DEFAULT 'strategy';

ALTER TABLE strategy_documents
    ADD COLUMN IF NOT EXISTS playbook_selections JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_strategy_documents_phase
    ON strategy_documents(phase);

COMMIT;
