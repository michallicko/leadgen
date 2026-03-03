-- 039: Add missing columns to split L2 enrichment tables
-- BL-155: Migration 028 added these fields to the old company_enrichment_l2
-- table but NOT to the split tables created in migration 021.
--
-- Field distribution follows the module semantics from migration 021:
--   Profile:      company-level descriptive data
--   Signals:      strategic/hiring/tech signals + scored indicators
--   Market:       news, media, funding, external intel
--   Opportunity:  pain/opportunity synthesis + pitch strategy

BEGIN;

-- ── Profile module: add expansion (new markets/offices/contracts) ───────
ALTER TABLE company_enrichment_profile
    ADD COLUMN IF NOT EXISTS expansion TEXT;

-- ── Signals module: strategic + tech indicators ─────────────────────────
ALTER TABLE company_enrichment_signals
    ADD COLUMN IF NOT EXISTS workflow_ai_evidence   TEXT,
    ADD COLUMN IF NOT EXISTS regulatory_pressure    TEXT,
    ADD COLUMN IF NOT EXISTS employee_sentiment     TEXT,
    ADD COLUMN IF NOT EXISTS tech_stack_categories  TEXT,
    ADD COLUMN IF NOT EXISTS fiscal_year_end        TEXT,
    ADD COLUMN IF NOT EXISTS digital_maturity_score TEXT,
    ADD COLUMN IF NOT EXISTS it_spend_indicators    TEXT;

-- ── Market module: news-derived trends + M&A ────────────────────────────
ALTER TABLE company_enrichment_market
    ADD COLUMN IF NOT EXISTS revenue_trend  TEXT,
    ADD COLUMN IF NOT EXISTS growth_signals TEXT,
    ADD COLUMN IF NOT EXISTS ma_activity    TEXT;

-- ── Opportunity module: pitch strategy ──────────────────────────────────
ALTER TABLE company_enrichment_opportunity
    ADD COLUMN IF NOT EXISTS pitch_framing          TEXT,
    ADD COLUMN IF NOT EXISTS competitor_ai_moves    TEXT;

-- ── Backfill from old company_enrichment_l2 where data exists ───────────

-- Profile backfill
UPDATE company_enrichment_profile p
SET expansion = l2.expansion
FROM company_enrichment_l2 l2
WHERE p.company_id = l2.company_id
  AND l2.expansion IS NOT NULL
  AND p.expansion IS NULL;

-- Signals backfill
UPDATE company_enrichment_signals s
SET workflow_ai_evidence   = l2.workflow_ai_evidence,
    regulatory_pressure    = l2.regulatory_pressure,
    employee_sentiment     = l2.employee_sentiment,
    tech_stack_categories  = l2.tech_stack_categories,
    fiscal_year_end        = l2.fiscal_year_end,
    digital_maturity_score = l2.digital_maturity_score,
    it_spend_indicators    = l2.it_spend_indicators
FROM company_enrichment_l2 l2
WHERE s.company_id = l2.company_id
  AND (l2.workflow_ai_evidence IS NOT NULL OR l2.regulatory_pressure IS NOT NULL
       OR l2.employee_sentiment IS NOT NULL OR l2.tech_stack_categories IS NOT NULL
       OR l2.fiscal_year_end IS NOT NULL OR l2.digital_maturity_score IS NOT NULL
       OR l2.it_spend_indicators IS NOT NULL);

-- Market backfill
UPDATE company_enrichment_market m
SET revenue_trend  = l2.revenue_trend,
    growth_signals = l2.growth_signals,
    ma_activity    = l2.ma_activity
FROM company_enrichment_l2 l2
WHERE m.company_id = l2.company_id
  AND (l2.revenue_trend IS NOT NULL OR l2.growth_signals IS NOT NULL
       OR l2.ma_activity IS NOT NULL);

-- Opportunity backfill
UPDATE company_enrichment_opportunity o
SET pitch_framing       = l2.pitch_framing,
    competitor_ai_moves = l2.competitor_ai_moves
FROM company_enrichment_l2 l2
WHERE o.company_id = l2.company_id
  AND (l2.pitch_framing IS NOT NULL OR l2.competitor_ai_moves IS NOT NULL);

COMMIT;
