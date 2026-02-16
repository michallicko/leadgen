# ADR-005: Enrichment DAG Model
**Date**: 2026-02-16 | **Status**: Accepted

## Context

The enrichment pipeline encoded pipeline position in a single `company.status` enum (11 values like `new`, `triage_passed`, `enriched_l2`). This caused several problems:

1. **Linear chain assumption**: Status could only represent one path, but enrichment stages form a DAG (L2 and registry lookups run in parallel after L1).
2. **No timestamps per stage**: No way to determine data freshness or when each enrichment happened.
3. **No field provenance**: No record of which stage set which fields.
4. **Hardcoded eligibility**: Each stage had a bespoke SQL query checking `company.status`, making it impossible to add or rewire stages without code changes.

## Decision

Replace the status-based linear model with a **per-entity stage completion tracking system** backed by a configurable DAG:

1. **`entity_stage_completions` table**: Records each entity's completion (or failure/skip) for each stage, with cost, error, and timestamp. Unique constraint on `(pipeline_run_id, entity_id, stage)`.

2. **Stage registry** (Python dict, not DB table): Defines 11 stages with hard dependencies, soft (togglable) dependencies, country gates, execution modes, and cost defaults. New stages require handler code anyway, so a DB-based registry adds complexity without benefit.

3. **Eligibility by completion records**: An entity is eligible for stage X when all hard deps (and activated soft deps) have `completed` rows. Cross-entity-type deps (contact→company) resolve via `company_id` joins. Country-gate auto-skip inserts `skipped` rows for non-matching entities.

4. **Dual-write for backward compatibility**: Handlers continue updating `company.status` alongside inserting completion records. Old endpoints work unchanged.

### Alternatives considered

- **Status array** (multiple statuses per entity): Simpler schema change but no timestamps, costs, or error tracking per stage. Doesn't support cross-entity deps.
- **DB-stored DAG config**: More flexible but over-engineered — adding a stage always requires Python handler code, making the DB config redundant.

## Consequences

### Positive
- Stages can run in parallel (L2 + registries + signals after L1)
- Adding new stages only requires a registry entry + handler — no eligibility query rewrites
- Per-entity, per-stage timestamps enable freshness tracking
- Cost tracking per stage per entity enables accurate billing
- Soft deps give users control over quality vs speed tradeoff

### Negative
- Dual-write period adds complexity until old status-based routing is deprecated
- Completion table grows linearly with entities x stages (mitigated by batch_id partitioning potential)
- `company.status` becomes denormalized — must be kept in sync or deprecated

### Migration path
- Phase 6 (future): Remove old `ELIGIBILITY_QUERIES`, migrate dashboard fully to DAG endpoints, make `company.status` a computed field
