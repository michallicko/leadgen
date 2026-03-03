-- 039: Propagate new L2 fields from monolithic table to split module tables
-- BL-155/BL-156: Fields added in 028 to company_enrichment_l2 need to exist
-- on the split tables that the API reads from.
--
-- Signals: regulatory_pressure, employee_sentiment, digital_maturity_score,
--          fiscal_year_end, it_spend_indicators, tech_stack_categories
-- Market:  expansion, workflow_ai_evidence, revenue_trend, growth_signals, ma_activity
-- Opportunity: pitch_framing

BEGIN;

-- ── Signals module: 6 new fields ─────────────────────────────────
ALTER TABLE company_enrichment_signals
    ADD COLUMN IF NOT EXISTS regulatory_pressure    TEXT,
    ADD COLUMN IF NOT EXISTS employee_sentiment     TEXT,
    ADD COLUMN IF NOT EXISTS digital_maturity_score TEXT,
    ADD COLUMN IF NOT EXISTS fiscal_year_end        TEXT,
    ADD COLUMN IF NOT EXISTS it_spend_indicators    TEXT,
    ADD COLUMN IF NOT EXISTS tech_stack_categories  TEXT;

-- ── Market module: 5 new fields ──────────────────────────────────
ALTER TABLE company_enrichment_market
    ADD COLUMN IF NOT EXISTS expansion              TEXT,
    ADD COLUMN IF NOT EXISTS workflow_ai_evidence   TEXT,
    ADD COLUMN IF NOT EXISTS revenue_trend          TEXT,
    ADD COLUMN IF NOT EXISTS growth_signals         TEXT,
    ADD COLUMN IF NOT EXISTS ma_activity            TEXT;

-- ── Opportunity module: 1 new field ──────────────────────────────
ALTER TABLE company_enrichment_opportunity
    ADD COLUMN IF NOT EXISTS pitch_framing          TEXT;

-- ── Backfill from monolithic table ───────────────────────────────
-- Copy data from company_enrichment_l2 into split tables for rows that exist

UPDATE company_enrichment_signals s
SET regulatory_pressure    = l2.regulatory_pressure,
    employee_sentiment     = l2.employee_sentiment,
    digital_maturity_score = l2.digital_maturity_score,
    fiscal_year_end        = l2.fiscal_year_end,
    it_spend_indicators    = l2.it_spend_indicators,
    tech_stack_categories  = l2.tech_stack_categories
FROM company_enrichment_l2 l2
WHERE s.company_id = l2.company_id
  AND (l2.regulatory_pressure IS NOT NULL
    OR l2.employee_sentiment IS NOT NULL
    OR l2.digital_maturity_score IS NOT NULL
    OR l2.fiscal_year_end IS NOT NULL
    OR l2.it_spend_indicators IS NOT NULL
    OR l2.tech_stack_categories IS NOT NULL);

UPDATE company_enrichment_market m
SET expansion            = l2.expansion,
    workflow_ai_evidence = l2.workflow_ai_evidence,
    revenue_trend        = l2.revenue_trend,
    growth_signals       = l2.growth_signals,
    ma_activity          = l2.ma_activity
FROM company_enrichment_l2 l2
WHERE m.company_id = l2.company_id
  AND (l2.expansion IS NOT NULL
    OR l2.workflow_ai_evidence IS NOT NULL
    OR l2.revenue_trend IS NOT NULL
    OR l2.growth_signals IS NOT NULL
    OR l2.ma_activity IS NOT NULL);

UPDATE company_enrichment_opportunity o
SET pitch_framing = l2.pitch_framing
FROM company_enrichment_l2 l2
WHERE o.company_id = l2.company_id
  AND l2.pitch_framing IS NOT NULL;

COMMIT;
