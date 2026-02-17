-- 022: Expand contact_enrichment table with scoring + gap fields
-- BL-045: Enrichment Field Audit (Task 4)

BEGIN;

-- Move scoring fields from contacts to contact_enrichment
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS ai_champion BOOLEAN DEFAULT FALSE;
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS ai_champion_score SMALLINT;
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS authority_score SMALLINT;

-- New gap fields
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS career_trajectory TEXT;
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS previous_companies JSONB DEFAULT '[]';
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS speaking_engagements TEXT;
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS publications TEXT;
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS twitter_handle TEXT;
ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS github_username TEXT;

-- Migrate existing scoring data from contacts
UPDATE contact_enrichment ce
SET ai_champion = c.ai_champion,
    ai_champion_score = c.ai_champion_score,
    authority_score = c.authority_score
FROM contacts c
WHERE ce.contact_id = c.id
  AND (c.ai_champion IS NOT NULL OR c.ai_champion_score IS NOT NULL OR c.authority_score IS NOT NULL);

COMMIT;
