# ADR-005: Unified Registry Module
**Date**: 2026-02-16 | **Status**: Accepted

## Context

We had 5 separate pipeline stages for registry enrichment (`ares`, `brreg`, `prh`, `recherche`, `isir`), each running independently. Users had to manually select which registers to run per batch. Data was split across two tables (`company_registry_data` for core registry data and `company_insolvency_data` for ISIR proceedings). There was no cross-register intelligence — ARES insolvency flags and ISIR proceedings weren't correlated.

Key problems:
1. Dashboard showed 5 separate package cards with no unified view
2. Users had to know which register applied to which country
3. No credibility scoring — registry data was stored but not evaluated
4. ISIR required a separate manual step after ARES enrichment

## Decision

Replace all 5 registry stages with a single `registry` pipeline stage backed by a `RegistryOrchestrator` that:

1. **Auto-detects** applicable registers from `hq_country` (priority) or domain TLD
2. **Runs adapters in dependency order** — ARES before ISIR, since ISIR requires ICO
3. **Aggregates results** into a unified `company_legal_profile` table
4. **Computes credibility score** (0-100) with 6 weighted components

**Deterministic orchestrator for V1**, not an LLM agent. Country → adapter(s) is a simple lookup. But the adapter interface (`provides_fields`, `requires_inputs`, `depends_on`, `is_supplementary`) is designed to be tool-compatible for future LLM agent routing.

**Credibility score** (0-100) with transparent factor breakdown:
- Registration verified (0-25): Based on match confidence tier
- Active status (0-20): Active/unknown/dissolved
- No insolvency (0-20): Clean/historical-only/active proceedings
- Business history (0-15): Company age tiers
- Data completeness (0-10): Ratio of filled fields
- Directors known (0-10): Has director list

**Backward compatibility** via `_LEGACY_STAGE_ALIASES` dict — old API calls with `"ares"`, `"brreg"` etc. are transparently resolved to `"registry"`.

## Consequences

**Positive:**
- One-click enrichment — users don't need to know which register applies
- Cross-register intelligence (ARES ICO → ISIR proceedings, credibility scoring)
- Unified data model (one table instead of two, one API response shape)
- Dashboard shows single "Legal & Registry" card with credibility badge
- Foundation for adding more country adapters without pipeline changes

**Negative:**
- Old `company_registry_data` and `company_insolvency_data` tables become legacy (not dropped yet)
- Data migration script required for existing data
- `confirm-registry` endpoint still uses old ARES import (not migrated to orchestrator)

**Migration path:**
1. Migration 016 creates `company_legal_profile` alongside old tables
2. Data migration script backfills from old tables
3. Future migration 017 can rename/drop old tables after verification
