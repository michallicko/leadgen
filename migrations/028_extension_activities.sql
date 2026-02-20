-- Migration 028: Extension activities table + contacts stub fields
-- Supports browser extension lead import and activity sync

-- New activities table
CREATE TABLE IF NOT EXISTS activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    contact_id UUID REFERENCES contacts(id),
    owner_id UUID REFERENCES owners(id),
    event_type TEXT NOT NULL,
    activity_name TEXT,
    activity_detail TEXT,
    source TEXT NOT NULL DEFAULT 'linkedin_extension',
    external_id TEXT,
    timestamp TIMESTAMPTZ,
    payload JSONB DEFAULT '{}',
    processed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Dedup index: external_id unique per tenant
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_tenant_external_id
    ON activities(tenant_id, external_id) WHERE external_id IS NOT NULL;

-- Query indexes
CREATE INDEX IF NOT EXISTS idx_activities_tenant_contact
    ON activities(tenant_id, contact_id);
CREATE INDEX IF NOT EXISTS idx_activities_tenant_type_ts
    ON activities(tenant_id, event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_activities_tenant_source
    ON activities(tenant_id, source);

-- Contact stub fields
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_stub BOOLEAN DEFAULT false;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS import_source TEXT;

-- Index for finding stub contacts
CREATE INDEX IF NOT EXISTS idx_contacts_is_stub
    ON contacts(tenant_id, is_stub) WHERE is_stub = true;
