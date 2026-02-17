-- 024: Drop deprecated columns after migration verification period
-- BL-045: Enrichment Field Audit (Task 9 - Phase D)
--
-- WARNING: Do NOT run this migration until at least 1 week after Phase C
-- is deployed and verified. These columns are kept for rollback safety.
--
-- Pre-flight checks before running:
-- 1. Verify company_enrichment_l1 has data for all enriched companies
-- 2. Verify 4 L2 module tables have data matching old company_enrichment_l2
-- 3. Verify contact_enrichment has ai_champion/authority_score data
-- 4. Verify API endpoints return correct data from new tables

BEGIN;

-- Company: remove duplicated legal fields (now in company_legal_profile)
ALTER TABLE companies DROP COLUMN IF EXISTS ico;
ALTER TABLE companies DROP COLUMN IF EXISTS official_name;
ALTER TABLE companies DROP COLUMN IF EXISTS tax_id;
ALTER TABLE companies DROP COLUMN IF EXISTS legal_form;
ALTER TABLE companies DROP COLUMN IF EXISTS registration_status;
ALTER TABLE companies DROP COLUMN IF EXISTS date_established;
ALTER TABLE companies DROP COLUMN IF EXISTS credibility_score;
ALTER TABLE companies DROP COLUMN IF EXISTS credibility_factors;

-- Company: remove migrated enrichment fields
ALTER TABLE companies DROP COLUMN IF EXISTS batch_number;
ALTER TABLE companies DROP COLUMN IF EXISTS pre_score;
ALTER TABLE companies DROP COLUMN IF EXISTS triage_notes;
ALTER TABLE companies DROP COLUMN IF EXISTS ai_adoption;
ALTER TABLE companies DROP COLUMN IF EXISTS news_confidence;

-- Contact: remove moved/deprecated fields
ALTER TABLE contacts DROP COLUMN IF EXISTS ai_champion;
ALTER TABLE contacts DROP COLUMN IF EXISTS ai_champion_score;
ALTER TABLE contacts DROP COLUMN IF EXISTS authority_score;
ALTER TABLE contacts DROP COLUMN IF EXISTS processed_enrich;
ALTER TABLE contacts DROP COLUMN IF EXISTS email_lookup;
ALTER TABLE contacts DROP COLUMN IF EXISTS duplicity_check;
ALTER TABLE contacts DROP COLUMN IF EXISTS duplicity_conflict;
ALTER TABLE contacts DROP COLUMN IF EXISTS duplicity_detail;

-- Rename old L2 table (keep for rollback rather than dropping)
ALTER TABLE IF EXISTS company_enrichment_l2 RENAME TO company_enrichment_l2_deprecated;

COMMIT;
