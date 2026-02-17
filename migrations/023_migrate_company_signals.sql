-- 023: Migrate ai_adoption + news_confidence from companies to company_enrichment_signals
-- BL-045: Enrichment Field Audit (Task 5)

BEGIN;

-- Update existing signal rows with company-level data
UPDATE company_enrichment_signals ces
SET ai_adoption_level = c.ai_adoption,
    news_confidence = c.news_confidence
FROM companies c
WHERE ces.company_id = c.id
  AND (c.ai_adoption IS NOT NULL OR c.news_confidence IS NOT NULL);

-- Insert for companies that have signal data but no enrichment_signals row yet
INSERT INTO company_enrichment_signals (company_id, ai_adoption_level, news_confidence)
SELECT c.id, c.ai_adoption, c.news_confidence
FROM companies c
LEFT JOIN company_enrichment_signals ces ON ces.company_id = c.id
WHERE ces.company_id IS NULL
  AND (c.ai_adoption IS NOT NULL OR c.news_confidence IS NOT NULL);

COMMIT;
