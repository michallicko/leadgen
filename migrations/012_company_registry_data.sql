-- ============================================================
-- Migration 012: Company registry data (ARES enrichment)
-- ============================================================

-- New table: 1:1 with companies, stores Czech ARES registry data
CREATE TABLE IF NOT EXISTS company_registry_data (
    company_id          UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    ico                 TEXT,
    dic                 TEXT,
    official_name       TEXT,
    legal_form          TEXT,
    legal_form_name     TEXT,
    date_established    DATE,
    date_dissolved      DATE,
    registered_address  TEXT,
    address_city        TEXT,
    address_postal_code TEXT,
    nace_codes          JSONB DEFAULT '[]'::jsonb,
    registration_court  TEXT,
    registration_number TEXT,
    registered_capital  TEXT,
    directors           JSONB DEFAULT '[]'::jsonb,
    registration_status TEXT,
    insolvency_flag     BOOLEAN DEFAULT false,
    raw_response        JSONB DEFAULT '{}'::jsonb,
    raw_vr_response     JSONB DEFAULT '{}'::jsonb,
    match_confidence    NUMERIC(3,2),
    match_method        TEXT,
    ares_updated_at     DATE,
    enriched_at         TIMESTAMPTZ,
    enrichment_cost_usd NUMERIC(10,4) DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_ico ON company_registry_data(ico);

-- Add ICO column to companies for quick filtering
ALTER TABLE companies ADD COLUMN IF NOT EXISTS ico TEXT;
CREATE INDEX IF NOT EXISTS idx_companies_ico ON companies(ico);
