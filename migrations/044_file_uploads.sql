-- 044_file_uploads.sql: Tables for multimodal file upload and content extraction.
-- Supports PDF, images, Word docs, and HTML content processing pipeline.

BEGIN;

-- File upload metadata
CREATE TABLE IF NOT EXISTS file_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(127) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_file_uploads_tenant
    ON file_uploads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_file_uploads_status
    ON file_uploads(processing_status);
CREATE INDEX IF NOT EXISTS idx_file_uploads_user
    ON file_uploads(user_id, created_at DESC);

-- Extracted content from uploaded files (text, summaries, page ranges)
CREATE TABLE IF NOT EXISTS extracted_content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES file_uploads(id) ON DELETE CASCADE,
    content_type VARCHAR(50) NOT NULL DEFAULT 'full_text',
    content_text TEXT,
    content_summary TEXT,
    page_range VARCHAR(50),
    token_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_extracted_content_file
    ON extracted_content(file_id);
CREATE INDEX IF NOT EXISTS idx_extracted_content_type
    ON extracted_content(file_id, content_type);

COMMIT;
