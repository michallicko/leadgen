-- BL-265: PDF + Image Processing / BL-266: HTML + Word Processing
-- File upload metadata and extracted content storage.

CREATE TABLE IF NOT EXISTS file_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    filename TEXT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    page_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS extracted_content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES file_uploads(id) ON DELETE CASCADE,
    content_type VARCHAR(20) NOT NULL DEFAULT 'text',
    content_text TEXT NOT NULL,
    content_summary TEXT,
    page_number INTEGER,
    token_count INTEGER NOT NULL DEFAULT 0,
    model_used VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_file_uploads_tenant ON file_uploads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_file_uploads_status ON file_uploads(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_extracted_content_file ON extracted_content(file_id);
