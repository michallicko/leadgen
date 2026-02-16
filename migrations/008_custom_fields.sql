-- Migration 008: Custom fields system
-- Allows tenants to define custom fields for contacts and companies
-- Values stored as JSONB on the entity tables for efficient storage

CREATE TABLE custom_field_definitions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('contact', 'company')),
    field_key       TEXT NOT NULL,
    field_label     TEXT NOT NULL,
    field_type      TEXT NOT NULL DEFAULT 'text'
                    CHECK (field_type IN ('text', 'number', 'url', 'email', 'date', 'select')),
    options         JSONB DEFAULT '[]'::jsonb,
    is_active       BOOLEAN DEFAULT true,
    display_order   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, entity_type, field_key)
);

CREATE INDEX idx_custom_field_defs_tenant ON custom_field_definitions(tenant_id, entity_type);

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS custom_fields JSONB DEFAULT '{}'::jsonb;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS custom_fields JSONB DEFAULT '{}'::jsonb;

CREATE INDEX idx_contacts_custom_fields ON contacts USING gin(custom_fields);
CREATE INDEX idx_companies_custom_fields ON companies USING gin(custom_fields);
