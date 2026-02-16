-- 015: Expand industry_enum with missing B2B verticals
-- These were landing in 'other' but deserve their own category

ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'real_estate';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'automotive';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'pharma_biotech';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'agriculture';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'hospitality';
ALTER TYPE industry_enum ADD VALUE IF NOT EXISTS 'aerospace_defense';
