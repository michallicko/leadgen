-- Migration 014: Company insolvency data table for ISIR integration
-- Stores insolvency proceedings from the Czech ISIR (Insolvenční rejstřík)

CREATE TABLE IF NOT EXISTS company_insolvency_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    ico TEXT,
    has_insolvency BOOLEAN DEFAULT FALSE,
    proceedings JSONB DEFAULT '[]'::jsonb,
    total_proceedings INTEGER DEFAULT 0,
    active_proceedings INTEGER DEFAULT 0,
    last_checked_at TIMESTAMPTZ,
    raw_response JSONB DEFAULT '[]'::jsonb,
    enrichment_cost_usd NUMERIC(10,4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_insolvency_company_id ON company_insolvency_data(company_id);
CREATE INDEX IF NOT EXISTS idx_insolvency_tenant_id ON company_insolvency_data(tenant_id);
CREATE INDEX IF NOT EXISTS idx_insolvency_ico ON company_insolvency_data(ico);
CREATE UNIQUE INDEX IF NOT EXISTS idx_insolvency_company_unique ON company_insolvency_data(company_id);
