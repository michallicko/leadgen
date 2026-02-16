# ADR-004: EU Registry Adapter Pattern
**Date**: 2026-02-16 | **Status**: Accepted

## Context
ARES enrichment (ADR-003) proved the value of free government registry data for Czech companies. Norway (BRREG), Finland (PRH), and France (recherche-entreprises) have similar zero-auth JSON APIs. Adding each as a monolithic service like the original `ares.py` would duplicate shared logic (name matching, result storage, pipeline dispatch).

## Decision
Refactor into a registry adapter pattern:
- `BaseRegistryAdapter` ABC in `api/services/registries/base.py` — shared name matching (bigram Dice coefficient with legal suffix stripping), result storage (upsert to `company_registry_data`), and `enrich_company()` orchestration (ID lookup → name search → auto-match/ambiguous/no-match)
- Per-country subclasses: `AresAdapter` (CZ), `BrregAdapter` (NO), `PrhAdapter` (FI), `RechercheAdapter` (FR)
- Adapter registry in `api/services/registries/__init__.py` with lazy loading
- One pipeline stage per country for independent control
- Existing `company_registry_data` table reused with `registry_country` discriminator column
- Backward-compatible import shim in `api/services/ares.py`

## Consequences
- New countries can be added by creating a single adapter file (~150 lines)
- All adapters share name matching, result storage, and pipeline dispatch logic
- Existing ARES imports continue working via shim (zero migration for existing code)
- Each country is an independent pipeline stage — users choose which to run
- All registry data stored in one table, queryable by `registry_country`
- All 4 registries are free ($0.00/lookup), no API keys required
