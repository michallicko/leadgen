-- 040: Expand contact_enrichment with granular person research fields
-- BL-153: Person enrichment generates ~20 LLM fields but only stores 9.
-- Add dedicated columns for profile, signals, and synthesis data.

BEGIN;

-- ── Profile research fields ─────────────────────────────────────────────
ALTER TABLE contact_enrichment
    ADD COLUMN IF NOT EXISTS role_verified          BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS role_mismatch_flag     TEXT,
    ADD COLUMN IF NOT EXISTS career_highlights      TEXT,
    ADD COLUMN IF NOT EXISTS thought_leadership     TEXT,
    ADD COLUMN IF NOT EXISTS thought_leadership_topics JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS education              TEXT,
    ADD COLUMN IF NOT EXISTS certifications         TEXT,
    ADD COLUMN IF NOT EXISTS expertise_areas        JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS public_presence_level  TEXT,
    ADD COLUMN IF NOT EXISTS profile_data_confidence TEXT;

-- ── Signals research fields ─────────────────────────────────────────────
ALTER TABLE contact_enrichment
    ADD COLUMN IF NOT EXISTS ai_champion_evidence   TEXT,
    ADD COLUMN IF NOT EXISTS authority_signals       TEXT,
    ADD COLUMN IF NOT EXISTS authority_level         TEXT,
    ADD COLUMN IF NOT EXISTS team_size_indication    TEXT,
    ADD COLUMN IF NOT EXISTS budget_signals          TEXT,
    ADD COLUMN IF NOT EXISTS technology_interests    JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS pain_indicators         TEXT,
    ADD COLUMN IF NOT EXISTS buying_signals          TEXT,
    ADD COLUMN IF NOT EXISTS signals_data_confidence TEXT;

-- ── Synthesis fields ────────────────────────────────────────────────────
ALTER TABLE contact_enrichment
    ADD COLUMN IF NOT EXISTS personalization_angle   TEXT,
    ADD COLUMN IF NOT EXISTS connection_points       JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS pain_connection         TEXT,
    ADD COLUMN IF NOT EXISTS conversation_starters   TEXT,
    ADD COLUMN IF NOT EXISTS objection_prediction    TEXT;

-- ── Scoring fields (new: department alignment + ICP fit + flags) ────────
ALTER TABLE contact_enrichment
    ADD COLUMN IF NOT EXISTS seniority              TEXT,
    ADD COLUMN IF NOT EXISTS department              TEXT,
    ADD COLUMN IF NOT EXISTS dept_alignment          TEXT,
    ADD COLUMN IF NOT EXISTS contact_score           SMALLINT,
    ADD COLUMN IF NOT EXISTS icp_fit                 TEXT,
    ADD COLUMN IF NOT EXISTS scoring_flags           JSONB DEFAULT '[]';

COMMIT;
