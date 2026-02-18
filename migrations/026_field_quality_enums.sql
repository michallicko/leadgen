-- Migration 026: Field quality enum updates (BL-045)
--
-- Adds new enum values for company_size and business_type.
-- Migrates legacy values (startup→small, smb→medium, service_provider→service_company).
-- Backfills industry_category from industry.
--
-- NOTE: PostgreSQL enums cannot remove values. Old values (startup, smb,
-- service_provider, other) remain valid in the enum type but will no longer
-- be produced by enrichment code.

-- ── 1. Add new enum values ──────────────────────────────────────

-- company_size: add 'small' and 'medium'
ALTER TYPE company_size ADD VALUE IF NOT EXISTS 'small';
ALTER TYPE company_size ADD VALUE IF NOT EXISTS 'medium';

-- business_type: add 'product_company', 'service_company', 'hybrid'
ALTER TYPE business_type ADD VALUE IF NOT EXISTS 'product_company';
ALTER TYPE business_type ADD VALUE IF NOT EXISTS 'service_company';
ALTER TYPE business_type ADD VALUE IF NOT EXISTS 'hybrid';

-- industry_enum: add creative_services (may already exist from earlier migration)
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'creative_services';
-- Also add missing industries from expanded list
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'pharma_biotech';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'automotive';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'aerospace_defense';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'hospitality';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'real_estate';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'agriculture';

-- ── 2. Data migration: legacy → new values ──────────────────────

-- company_size: startup → small, smb → medium
UPDATE companies SET company_size = 'small' WHERE company_size = 'startup';
UPDATE companies SET company_size = 'medium' WHERE company_size = 'smb';

-- business_type: service_provider → service_company
UPDATE companies SET business_type = 'service_company' WHERE business_type = 'service_provider';

-- ── 3. Backfill industry_category from industry ─────────────────

UPDATE companies SET industry_category = 'technology'
  WHERE industry IN ('software_saas', 'it') AND industry_category IS NULL;

UPDATE companies SET industry_category = 'services'
  WHERE industry IN ('professional_services', 'creative_services') AND industry_category IS NULL;

UPDATE companies SET industry_category = 'finance'
  WHERE industry = 'financial_services' AND industry_category IS NULL;

UPDATE companies SET industry_category = 'healthcare_life_sci'
  WHERE industry IN ('healthcare', 'pharma_biotech') AND industry_category IS NULL;

UPDATE companies SET industry_category = 'industrial'
  WHERE industry IN ('manufacturing', 'automotive', 'aerospace_defense', 'construction') AND industry_category IS NULL;

UPDATE companies SET industry_category = 'consumer'
  WHERE industry IN ('retail', 'hospitality', 'media') AND industry_category IS NULL;

UPDATE companies SET industry_category = 'infrastructure'
  WHERE industry IN ('telecom', 'transport', 'real_estate') AND industry_category IS NULL;

UPDATE companies SET industry_category = 'primary_sector'
  WHERE industry IN ('agriculture', 'energy') AND industry_category IS NULL;

UPDATE companies SET industry_category = 'public_education'
  WHERE industry IN ('education', 'public_sector') AND industry_category IS NULL;
