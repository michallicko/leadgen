-- BL-262: RAG Long-Term Memory
-- Stores key facts extracted from conversations for cross-session retrieval.

CREATE TABLE IF NOT EXISTS memory_facts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    playbook_id UUID REFERENCES strategy_documents(id),
    source_message_id UUID REFERENCES strategy_chat_messages(id),
    chunk_text TEXT NOT NULL,
    chunk_type VARCHAR(20) NOT NULL DEFAULT 'fact',
    keywords TEXT[] DEFAULT '{}',
    session_id VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_facts_tenant ON memory_facts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_memory_facts_keywords ON memory_facts USING gin(keywords);
CREATE INDEX IF NOT EXISTS idx_memory_facts_created ON memory_facts(tenant_id, created_at DESC);
