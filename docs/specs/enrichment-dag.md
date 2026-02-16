# Enrichment DAG: Status Redesign + Orchestration Platform

**Status**: In Progress | **Phase**: 4 of 6 (Phases 1-4 complete) | **Backlog**: BL-015, BL-016

## Purpose

Replace the linear `company.status` enum model with a per-entity stage completion tracking system backed by a configurable DAG. This enables parallel enrichment stages, field provenance, and dynamic eligibility without code changes.

## Problem

The current system encodes pipeline position in a single `company.status` enum (11 values). This creates:
- **Linear chain assumption** — status can only represent one path
- **No timestamps per stage** — no data freshness tracking
- **No field provenance** — no record of which stage set which fields
- **Hardcoded eligibility** — bespoke SQL per stage in `ELIGIBILITY_QUERIES`

## Architecture

```
                    ┌──→ [L2 Deep Research]        ──┐
[L1 Company] ──────┼──→ [Strategic Signals]         ──┼──→ [Person] ──→ [Generate] ──→ [QC]
                    ├──→ [ARES] (CZ companies)       │
                    ├──→ [BRREG] (NO companies)      │
                    ├──→ [PRH] (FI companies)        │
                    ├──→ [Recherche] (FR companies)  │
                    └──→ [ISIR] (CZ w/ ICO)          ┘
```

### Dependency Types
- **Hard** (always enforced): L2→L1, Signals→L1, Registries→L1, Person→L1, Generate→Person
- **Soft** (togglable per run): Person→[L2, Signals], Generate→[L2, Signals]
- **QC**: dynamic hard deps = all other enabled stages

## Requirements

### Phase 1: Data Model + Stage Registry
1. New `entity_stage_completions` table tracking per-entity, per-stage completion
2. Backfill from existing `company.status` and registry data
3. Python stage registry dict with dependency graph, country gates, execution modes
4. Utility functions: `get_stage()`, `topo_sort()`, `get_stages_for_entity_type()`
5. `EntityStageCompletion` SQLAlchemy model

### Phase 2: DAG Executor + API
1. Generic eligibility query builder replacing `ELIGIBILITY_QUERIES`
2. Cross-entity-type dependency handling (contact stages checking company completions)
3. Country-gate auto-skip (batch-insert skipped rows for non-matching entities)
4. New API endpoints: `dag-run`, `dag-status`, `dag-stop`
5. Backward compatibility: old endpoints continue working

### Phase 3: Interactive DAG Dashboard
1. Single-page enrich wizard with column-based DAG layout
2. Node components with 6 states (disabled/pending/eligible/running/completed/failed)
3. SVG bezier edge rendering with animation states
4. Soft dependency toggle UI
5. Run controls + 5s polling

### Phase 4: QC Node
1. End-of-pipeline field conflict detection
2. Revenue/employee/name mismatch checks across L1 vs L2 vs registry data

### Phase 5: Strategic Signals (separate enricher)
1. Break out from L2 into independent stage

### Phase 6: Deprecation & Cleanup
1. Remove old eligibility queries and status-based routing

## Acceptance Criteria

### Phase 1 (Complete)
- [x] Migration 016 creates `entity_stage_completions` with correct schema and indexes
- [x] Backfill populates completions from existing status/registry data
- [x] `topo_sort()` returns correct topological ordering for all stage combinations
- [x] `get_stage()` returns correct config for each stage code
- [x] EntityStageCompletion model works with SQLite test DB
- [x] Existing pipeline tests still pass (no behavior change)

### Phase 2 (Complete)
- [x] Generic eligibility query builder replaces `ELIGIBILITY_QUERIES`
- [x] Cross-entity-type dependency handling (contact→company)
- [x] Country-gate auto-skip inserts skipped rows
- [x] DAG API endpoints: dag-run, dag-status, dag-stop
- [x] Old endpoints continue working (backward compatible)

### Phase 3 (Complete)
- [x] 2-step DAG wizard with column-based layout
- [x] 6 node states (disabled/pending/eligible/running/completed/failed)
- [x] SVG bezier edge rendering with animation states
- [x] Soft dependency toggle UI
- [x] Run controls + 5s polling

### Phase 4 (Complete)
- [x] QC checker with 6 cross-source quality checks
- [x] 36 unit tests covering all checks + DB integration

## Data Model

### entity_stage_completions
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| tenant_id | UUID FK→tenants | required |
| batch_id | UUID FK→batches | required |
| pipeline_run_id | UUID FK→pipeline_runs | nullable (backfill has none) |
| entity_type | TEXT | 'company' or 'contact' |
| entity_id | UUID | company.id or contact.id |
| stage | TEXT | stage code from registry |
| status | TEXT | completed, failed, skipped |
| cost_usd | NUMERIC(10,4) | default 0 |
| error | TEXT | error message if failed |
| completed_at | TIMESTAMPTZ | default now() |

### Stage Registry (Python dict)
Each stage has: entity_type, hard_deps, soft_deps, execution_mode, display_name, cost_default_usd, country_gate.

## Edge Cases
- Companies with NULL batch_id are excluded from backfill
- Country gate matching uses both country name variations and TLD patterns
- Backfill is idempotent (UNIQUE constraint on pipeline_run_id + entity_id + stage)
- QC stage has is_terminal flag — deps computed dynamically at run start
