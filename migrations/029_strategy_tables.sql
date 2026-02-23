-- 029: Strategy document and chat tables for Playbook feature
--
-- Adds strategy_documents (one per tenant), strategy_chat_messages,
-- and is_self flag on companies for self-enrichment.

BEGIN;

-- ── Self-enrichment flag ──────────────────────
ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS is_self BOOLEAN NOT NULL DEFAULT FALSE;

-- ── Strategy documents ──────────────────────
CREATE TABLE IF NOT EXISTS strategy_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL UNIQUE REFERENCES tenants(id),
    content         JSONB NOT NULL DEFAULT '{}'::jsonb,
    extracted_data  JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
    version         INTEGER NOT NULL DEFAULT 1,
    enrichment_id   UUID REFERENCES companies(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by      UUID REFERENCES users(id)
);

-- ── Strategy chat messages ──────────────────────
CREATE TABLE IF NOT EXISTS strategy_chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    document_id     UUID NOT NULL REFERENCES strategy_documents(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,
    content         TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by      UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_chat_document_time
    ON strategy_chat_messages(document_id, created_at);

COMMIT;
