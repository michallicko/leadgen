-- Migration 043: Add missing career enrichment columns to contact_enrichment
-- Required for BL-235 (Career History Enricher)

ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS industry_experience JSONB DEFAULT '[]'::jsonb;
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS total_experience_years INTEGER;
