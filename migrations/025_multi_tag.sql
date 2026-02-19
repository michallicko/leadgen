-- Migration 025: Multi-tag junction tables
-- Moves from single tag_id FK on contacts/companies to many-to-many via junction tables.

-- Junction table for contact ↔ tag (many-to-many)
CREATE TABLE IF NOT EXISTS contact_tag_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(contact_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_cta_contact ON contact_tag_assignments(contact_id);
CREATE INDEX IF NOT EXISTS idx_cta_tag ON contact_tag_assignments(tag_id);
CREATE INDEX IF NOT EXISTS idx_cta_tenant ON contact_tag_assignments(tenant_id);

-- Junction table for company ↔ tag (many-to-many)
CREATE TABLE IF NOT EXISTS company_tag_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(company_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_cota_company ON company_tag_assignments(company_id);
CREATE INDEX IF NOT EXISTS idx_cota_tag ON company_tag_assignments(tag_id);
CREATE INDEX IF NOT EXISTS idx_cota_tenant ON company_tag_assignments(tenant_id);

-- Migrate existing single-tag FKs to junction tables
INSERT INTO contact_tag_assignments (tenant_id, contact_id, tag_id)
SELECT tenant_id, id, tag_id FROM contacts WHERE tag_id IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO company_tag_assignments (tenant_id, company_id, tag_id)
SELECT tenant_id, id, tag_id FROM companies WHERE tag_id IS NOT NULL
ON CONFLICT DO NOTHING;
