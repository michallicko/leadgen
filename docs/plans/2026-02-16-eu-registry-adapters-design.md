# EU Registry Adapters — Phase 1 Design

**Date**: 2026-02-16
**Scope**: Norway (BRREG), Finland (PRH/YTJ), France (recherche-entreprises)
**Branch**: feature/ares-enrichment (continuing from ARES work)

## Problem

Czech ARES enrichment works, but companies from other EU countries lack official registry data. Norway, Finland, and France all provide free, zero-auth JSON APIs for company lookups. Adding these as enrichment sources gives verified government data at zero cost.

## Architecture: Registry Adapter Pattern

Refactor the monolithic `api/services/ares.py` into a multi-country adapter system.

```
api/services/registries/
  __init__.py          # get_adapter(country) → adapter instance
  base.py              # BaseRegistryAdapter ABC
  ares.py              # Czech ARES (moved + refactored)
  brreg.py             # Norway Brønnøysund Register Centre
  prh.py               # Finland Patent and Registration Office
  recherche.py         # France recherche-entreprises.api.gouv.fr
```

### BaseRegistryAdapter Contract

```python
class BaseRegistryAdapter(ABC):
    country_code: str           # "CZ", "NO", "FI", "FR"
    country_names: list[str]    # ["Norway", "NO", "Norge"]

    def is_eligible(company) -> bool
    def enrich_company(company_id, tenant_id, name, reg_id, country, domain) -> dict
    def lookup_by_id(reg_id) -> dict | None
    def search_by_name(name) -> list[dict]
    def _store_result(company_id, data, method, confidence)  # shared in base
```

### Database: Reuse Existing Table

`company_registry_data` columns are already generic enough. Add one column:

```sql
ALTER TABLE company_registry_data ADD COLUMN IF NOT EXISTS registry_country TEXT DEFAULT 'CZ';
```

The `ico` column stores any national registration number (org_nr, business_id, SIREN). Other columns (`official_name`, `legal_form`, `date_established`, `registered_address`, `nace_codes` JSONB, `directors` JSONB) work universally.

### Pipeline: Per-Country Stages

Each country is its own pipeline stage: `ares`, `brreg`, `prh`, `recherche`. Each has an independent eligibility query filtering by country. Users choose which countries to enrich from the dashboard wizard.

The `DIRECT_STAGES` set in pipeline_engine.py expands from `{"ares"}` to `{"ares", "brreg", "prh", "recherche"}`.

### Backward Compatibility

`api/services/ares.py` becomes a thin shim:
```python
from .registries.ares import *  # noqa
```

All existing imports (`test_ares_routes.py`, `company_routes.py`) continue working.

## Country APIs

### Norway (BRREG)
- **Base URL**: `https://data.brreg.no/enhetsregisteret/api`
- **ID lookup**: `GET /enheter/{org_nr}` — org name, form (AS/ASA/ENK), address, NACE, bankruptcy, reg date
- **Name search**: `GET /enheter?navn={name}` — paginated
- **Auth**: None
- **Rate limit**: Undocumented, use 0.3s delay
- **Suffix stripping**: AS, ASA, ENK, ANS, DA, NUF

### Finland (PRH/YTJ)
- **Base URL**: `https://avoindata.prh.fi/opendata-ytj-api/v3`
- **ID lookup**: `GET /companies?businessId={id}` — business name, form (OY/OYJ), addresses, reg date
- **Name search**: `GET /companies?name={name}`
- **Auth**: None
- **Rate limit**: Undocumented, use 0.3s delay
- **ID format**: 1234567-8 (7 digits + hyphen + check digit)
- **Suffix stripping**: OY, OYJ, OY AB, OSK

### France (recherche-entreprises)
- **Base URL**: `https://recherche-entreprises.api.gouv.fr`
- **ID lookup**: `GET /search?q={siren}` — name, legal form (SAS/SARL/SA), address, NAF code, creation date, employees
- **Name search**: `GET /search?q={name}`
- **Auth**: None
- **Rate limit**: 7 req/s, use 0.2s delay
- **Suffix stripping**: SAS, SARL, SA, SCI, EURL, SASU

## Name Matching

Reuse bigram similarity from ARES. Each adapter defines country-specific legal suffixes to strip before comparison. Auto-match threshold: >= 0.85. Candidates threshold: >= 0.60.

## Files Summary

### Create
| File | Purpose |
|------|---------|
| `api/services/registries/__init__.py` | Adapter registry + `get_adapter(country)` |
| `api/services/registries/base.py` | `BaseRegistryAdapter` ABC + shared `_store_result` |
| `api/services/registries/ares.py` | Czech ARES adapter (refactored from `api/services/ares.py`) |
| `api/services/registries/brreg.py` | Norway BRREG adapter |
| `api/services/registries/prh.py` | Finland PRH adapter |
| `api/services/registries/recherche.py` | France recherche-entreprises adapter |
| `migrations/013_registry_country.sql` | Add `registry_country` column |
| `tests/unit/test_brreg_service.py` | Norway unit tests |
| `tests/unit/test_prh_service.py` | Finland unit tests |
| `tests/unit/test_recherche_service.py` | France unit tests |

### Modify
| File | Change |
|------|--------|
| `api/services/ares.py` | Thin import shim → `registries.ares` |
| `api/services/pipeline_engine.py` | Add `brreg`, `prh`, `recherche` to stages + dispatch |
| `api/routes/enrich_routes.py` | Add 3 stages to `ENRICHMENT_STAGES` |
| `api/routes/pipeline_routes.py` | Add 3 stages to `ALL_STAGES` |
| `api/routes/company_routes.py` | Generalize on-demand endpoint for any country |
| `dashboard/enrich.html` | 3 new enrichment wizard modules |
| `api/models.py` | Add `registry_country` to `CompanyRegistryData` |
