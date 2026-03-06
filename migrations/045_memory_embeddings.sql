-- 045_memory_embeddings.sql: RAG long-term memory with pgvector embeddings.
-- Stores decisions, preferences, insights, and constraints for cross-session retrieval.
--
-- NOTE: Requires pgvector extension. On RDS, enable via:
--   CREATE EXTENSION IF NOT EXISTS vector;
-- On local dev without pgvector, the embedding column will be TEXT (fallback).

BEGIN;

-- Enable pgvector extension (no-op if already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    content_type VARCHAR(50) NOT NULL DEFAULT 'decision',
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    source_message_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_tenant
    ON memory_embeddings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_type
    ON memory_embeddings(tenant_id, content_type);

-- IVFFlat index for approximate nearest neighbor search.
-- Requires at least ~100 rows before it becomes effective.
-- For small datasets, exact scan is used automatically.
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_vector
    ON memory_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

COMMIT;
