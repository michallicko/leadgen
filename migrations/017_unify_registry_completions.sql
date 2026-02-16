-- Migration 017: Unify individual registry stage names into 'registry'
--
-- The 5 separate registry stages (ares, brreg, prh, recherche, isir) are now
-- handled by a single RegistryOrchestrator behind the unified 'registry' stage.
-- This migration renames existing completion and run records.

-- Step 1: Deduplicate entity_stage_completions
-- CZ companies may have both 'ares' + 'isir' records for the same pipeline run.
-- Keep the main adapter (non-isir), drop supplementary.
WITH ranked AS (
  SELECT id,
    ROW_NUMBER() OVER (
      PARTITION BY pipeline_run_id, entity_id
      ORDER BY CASE stage WHEN 'isir' THEN 2 ELSE 1 END, completed_at DESC
    ) AS rn
  FROM entity_stage_completions
  WHERE stage IN ('ares', 'brreg', 'prh', 'recherche', 'isir')
)
DELETE FROM entity_stage_completions WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- Step 2: Rename remaining to 'registry'
UPDATE entity_stage_completions SET stage = 'registry'
WHERE stage IN ('ares', 'brreg', 'prh', 'recherche', 'isir');

-- Step 3: Same for stage_runs
UPDATE stage_runs SET stage = 'registry'
WHERE stage IN ('ares', 'brreg', 'prh', 'recherche', 'isir');
