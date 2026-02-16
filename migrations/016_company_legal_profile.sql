-- Migration 016: Unified company legal profile table
-- Replaces separate company_registry_data + company_insolvency_data with
-- a single company_legal_profile that aggregates all registry + insolvency data.

-- New unified table
CREATE TABLE IF NOT EXISTS company_legal_profile (
    company_id UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,

    -- Core unified fields
    registration_id TEXT,
    registration_country TEXT NOT NULL,
    tax_id TEXT,
    official_name TEXT,
    legal_form TEXT,
    legal_form_name TEXT,
    registration_status TEXT,
    date_established DATE,
    date_dissolved DATE,
    registered_address TEXT,
    address_city TEXT,
    address_postal_code TEXT,
    nace_codes JSONB DEFAULT '[]',
    directors JSONB DEFAULT '[]',
    registered_capital TEXT,
    registration_court TEXT,
    registration_number TEXT,

    -- Insolvency (merged from ISIR)
    insolvency_flag BOOLEAN DEFAULT false,
    insolvency_details JSONB DEFAULT '[]',
    active_insolvency_count INTEGER DEFAULT 0,

    -- Match quality
    match_confidence NUMERIC(3,2),
    match_method TEXT,

    -- Credibility
    credibility_score SMALLINT,
    credibility_factors JSONB DEFAULT '{}',

    -- Raw data keyed by source
    source_data JSONB DEFAULT '{}',

    -- Metadata
    enriched_at TIMESTAMPTZ,
    registry_updated_at DATE,
    enrichment_cost_usd NUMERIC(10,4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Promoted core attributes on companies table
ALTER TABLE companies ADD COLUMN IF NOT EXISTS official_name TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS tax_id TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS legal_form TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS registration_status TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS date_established DATE;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS has_insolvency BOOLEAN DEFAULT false;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS credibility_score SMALLINT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS credibility_factors JSONB DEFAULT '{}';

-- Index for filtering companies by credibility
CREATE INDEX IF NOT EXISTS idx_companies_credibility_score
    ON companies (credibility_score) WHERE credibility_score IS NOT NULL;

-- Index for filtering by insolvency
CREATE INDEX IF NOT EXISTS idx_companies_has_insolvency
    ON companies (has_insolvency) WHERE has_insolvency = true;

-- Index for filtering legal profiles by country
CREATE INDEX IF NOT EXISTS idx_legal_profile_country
    ON company_legal_profile (registration_country);
