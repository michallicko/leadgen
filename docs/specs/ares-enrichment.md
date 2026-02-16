# ARES Enrichment — Feature Specification

**Date**: 2026-02-16 | **Status**: In Progress

## Purpose

Enrich Czech companies with official government data from the Czech ARES (Administrative Register of Economic Subjects) API. ARES aggregates data from 10+ public registers and provides verified information unavailable from commercial enrichment sources.

## Requirements

### Functional
1. Look up Czech companies by ICO (registration number) or company name
2. Store registry data in a dedicated `company_registry_data` table (1:1 with companies)
3. Extract: ICO, DIC, official name, legal form, address, NACE codes, registration status, insolvency flags
4. Extract directors and registered capital from the VR (commercial register) endpoint
5. Fuzzy name matching when ICO is not available, with confidence scoring
6. On-demand single-company lookup via API endpoint
7. Batch enrichment via the existing pipeline engine (as a new "ares" stage)

### Non-Functional
- Cost: $0.00 per lookup (free government API)
- Rate limiting: 0.5s delay between requests to avoid ARES abuse detection
- Timeout: 10s per request
- No n8n dependency — direct Python HTTP calls

## ARES API Contracts

**Base URL**: `https://ares.gov.cz/ekonomicke-subjekty-v-be/rest`

### Lookup by ICO
```
GET /ekonomicke-subjekty/{ico}
Response: { ico, dic, obchodniJmeno, pravniForma, datumVzniku, datumZaniku, sidlo, czNace, ... }
```

### Search by name
```
POST /ekonomicke-subjekty/vyhledat
Body: { obchodniJmeno: "name", start: 0, pocet: 5 }
Response: { pocetCelkem, ekonomickeSubjekty: [...] }
```

### Commercial register (VR)
```
GET /ekonomicke-subjekty-vr/{ico}
Response: { ico, statutarniOrgany, zakladniKapital, spisovaZnacka, ... }
```

## Data Model

### New table: `company_registry_data`
| Column | Type | Source |
|--------|------|--------|
| company_id | UUID PK, FK | Internal |
| ico | TEXT | ARES ico |
| dic | TEXT | ARES dic |
| official_name | TEXT | ARES obchodniJmeno |
| legal_form | TEXT | ARES pravniForma code |
| legal_form_name | TEXT | Decoded name (e.g. "s.r.o.") |
| date_established | DATE | ARES datumVzniku |
| date_dissolved | DATE | ARES datumZaniku |
| registered_address | TEXT | sidlo.textovaAdresa |
| address_city | TEXT | sidlo.nazevObce |
| address_postal_code | TEXT | sidlo.psc |
| nace_codes | JSONB | ARES czNace array |
| registration_court | TEXT | VR spisovaZnacka court |
| registration_number | TEXT | VR spisovaZnacka file ref |
| registered_capital | TEXT | VR zakladniKapital |
| directors | JSONB | VR statutarniOrgany |
| registration_status | TEXT | active/dissolved/unknown |
| insolvency_flag | BOOLEAN | seznamRegistraci |
| raw_response | JSONB | Full ARES JSON |
| raw_vr_response | JSONB | Full VR JSON |
| match_confidence | NUMERIC(3,2) | 0.00-1.00 |
| match_method | TEXT | ico_direct/name_auto/name_manual |
| ares_updated_at | DATE | datumAktualizace |
| enriched_at | TIMESTAMPTZ | When we ran enrichment |
| enrichment_cost_usd | NUMERIC(10,4) | Always 0.00 |

### companies table addition
- `ico TEXT` column + index for quick filtering

## API Endpoints

### Batch enrichment (existing pattern)
- `POST /api/enrich/estimate` — include `"ares"` in stages
- `POST /api/enrich/start` — include `"ares"` in stages

### On-demand (new)
- `POST /api/companies/<id>/enrich-registry` — single-company lookup
  - Body: `{"ico": "12345678"}` (optional — for direct lookup)
  - Returns: registry data or candidate list if ambiguous
- `POST /api/companies/<id>/confirm-registry` — confirm from candidates
  - Body: `{"ico": "12345678"}`

## Eligibility Criteria

Companies eligible for ARES enrichment:
- No existing `company_registry_data` row
- Czech indicators: `hq_country = 'Czech Republic'` OR domain ends with `.cz` OR `ico` is set

## Matching Strategy

1. **ICO provided** → direct lookup, confidence 1.0
2. **Name only** → search, auto-match if similarity >= 0.85, candidates if >= 0.60, skip below
3. Name similarity strips Czech legal suffixes (s.r.o., a.s., spol. s r.o., etc.)

## Acceptance Criteria

1. ARES stage appears in enrichment wizard with $0.00 cost
2. Pipeline engine processes eligible Czech companies through ARES
3. Registry data appears in company detail modal
4. On-demand lookup works from company detail
5. Unit tests pass for service + routes
6. Full test suite has no regressions
