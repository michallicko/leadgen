-- ============================================================
-- Migration 013: Add registry_country to company_registry_data
-- ============================================================

-- Distinguish which country's register provided the data
ALTER TABLE company_registry_data ADD COLUMN IF NOT EXISTS registry_country TEXT DEFAULT 'CZ';
CREATE INDEX IF NOT EXISTS idx_registry_country ON company_registry_data(registry_country);
