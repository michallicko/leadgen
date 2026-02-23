-- 030: Convert strategy document content to markdown text, add objective and playbook_logs
--
-- Changes content from JSONB to TEXT for markdown storage.
-- Adds objective field for user's stated GTM objective.
-- Creates playbook_logs table for conversation and research event logging.

BEGIN;

-- Convert content from JSONB to TEXT (markdown storage)
ALTER TABLE strategy_documents ALTER COLUMN content TYPE TEXT USING content::text;
ALTER TABLE strategy_documents ALTER COLUMN content SET DEFAULT '';

-- Add objective field
ALTER TABLE strategy_documents ADD COLUMN IF NOT EXISTS objective TEXT;

-- ── Playbook event logs ──────────────────────
CREATE TABLE IF NOT EXISTS playbook_logs (
    id              SERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    doc_id          UUID REFERENCES strategy_documents(id),
    event_type      VARCHAR(50) NOT NULL,
    payload         JSONB,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_playbook_logs_doc_time
    ON playbook_logs(doc_id, created_at);

COMMIT;
