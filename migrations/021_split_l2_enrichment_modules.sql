-- 021: Split company_enrichment_l2 into 4 module tables
-- BL-045: Enrichment Field Audit (Task 3)

BEGIN;

-- Module 1: Company Profile
CREATE TABLE company_enrichment_profile (
    company_id          UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    company_intel       TEXT,
    key_products        TEXT,
    customer_segments   TEXT,
    competitors         TEXT,
    tech_stack          TEXT,
    leadership_team     TEXT,
    certifications      TEXT,
    enriched_at         TIMESTAMP WITH TIME ZONE,
    enrichment_cost_usd NUMERIC(10,4) DEFAULT 0,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Module 2: Strategic Signals
CREATE TABLE company_enrichment_signals (
    company_id              UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    digital_initiatives     TEXT,
    leadership_changes      TEXT,
    hiring_signals          TEXT,
    ai_hiring               TEXT,
    tech_partnerships       TEXT,
    competitor_ai_moves     TEXT,
    ai_adoption_level       TEXT,
    news_confidence         TEXT,
    growth_indicators       TEXT,
    job_posting_count       INTEGER,
    hiring_departments      JSONB DEFAULT '[]',
    enriched_at             TIMESTAMP WITH TIME ZONE,
    enrichment_cost_usd     NUMERIC(10,4) DEFAULT 0,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Module 3: Market Intelligence
CREATE TABLE company_enrichment_market (
    company_id          UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    recent_news         TEXT,
    funding_history     TEXT,
    eu_grants           TEXT,
    media_sentiment     TEXT,
    press_releases      TEXT,
    thought_leadership  TEXT,
    enriched_at         TIMESTAMP WITH TIME ZONE,
    enrichment_cost_usd NUMERIC(10,4) DEFAULT 0,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Module 4: Pain & Opportunity
CREATE TABLE company_enrichment_opportunity (
    company_id              UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    pain_hypothesis         TEXT,
    relevant_case_study     TEXT,
    ai_opportunities        TEXT,
    quick_wins              JSONB DEFAULT '{}',
    industry_pain_points    TEXT,
    cross_functional_pain   TEXT,
    adoption_barriers       TEXT,
    enriched_at             TIMESTAMP WITH TIME ZONE,
    enrichment_cost_usd     NUMERIC(10,4) DEFAULT 0,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- ── Migrate existing L2 data ────────────────────────────────────

-- Profile (cost share: 30%)
INSERT INTO company_enrichment_profile (company_id, company_intel, key_products, customer_segments, competitors, tech_stack, leadership_team, certifications, enriched_at, enrichment_cost_usd, created_at, updated_at)
SELECT company_id, company_intel, key_products, customer_segments, competitors, tech_stack, leadership_team, certifications, enriched_at, enrichment_cost_usd * 0.3, created_at, updated_at
FROM company_enrichment_l2 WHERE company_intel IS NOT NULL;

-- Signals (cost share: 25%)
INSERT INTO company_enrichment_signals (company_id, digital_initiatives, leadership_changes, hiring_signals, ai_hiring, tech_partnerships, competitor_ai_moves, enriched_at, enrichment_cost_usd, created_at, updated_at)
SELECT company_id, digital_initiatives, leadership_changes, hiring_signals, ai_hiring, tech_partnerships, competitor_ai_moves, enriched_at, enrichment_cost_usd * 0.25, created_at, updated_at
FROM company_enrichment_l2 WHERE digital_initiatives IS NOT NULL OR hiring_signals IS NOT NULL;

-- Market (cost share: 20%)
INSERT INTO company_enrichment_market (company_id, recent_news, funding_history, eu_grants, enriched_at, enrichment_cost_usd, created_at, updated_at)
SELECT company_id, recent_news, funding_history, eu_grants, enriched_at, enrichment_cost_usd * 0.2, created_at, updated_at
FROM company_enrichment_l2 WHERE recent_news IS NOT NULL OR funding_history IS NOT NULL;

-- Opportunity (cost share: 25%)
INSERT INTO company_enrichment_opportunity (company_id, pain_hypothesis, relevant_case_study, ai_opportunities, quick_wins, industry_pain_points, cross_functional_pain, adoption_barriers, enriched_at, enrichment_cost_usd, created_at, updated_at)
SELECT company_id, pain_hypothesis, relevant_case_study, ai_opportunities, quick_wins, industry_pain_points, cross_functional_pain, adoption_barriers, enriched_at, enrichment_cost_usd * 0.25, created_at, updated_at
FROM company_enrichment_l2 WHERE pain_hypothesis IS NOT NULL OR ai_opportunities IS NOT NULL;

COMMIT;
