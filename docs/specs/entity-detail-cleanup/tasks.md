# Entity Detail Cleanup — Tasks

**Date**: 2026-02-19

## Task Dependency Graph

```
T1 (API: company) ─────┬──→ T3 (Company Detail tabs)
                        │
T2 (API: contact) ──────┼──→ T4 (Contact Detail tabs)
                        │
                        └──→ T5 (Types update)

T3 + T4 + T5 ──→ T6 (Tests)
T6 ──→ T7 (Docs)
```

## Tasks

### T1: Extend company detail API with missing fields + stage_completions
**Traces**: FR-15, FR-17, AC-7

Update `GET /api/companies/<id>` in `api/routes/company_routes.py`:

1. Add `website_url`, `linkedin_url`, `logo_url`, `last_enriched_at`, `data_quality_score` to the company detail response serialization
2. Query `entity_stage_completions` for this company and return as `stage_completions` array:
   ```sql
   SELECT stage, status, completed_at, cost_usd
   FROM entity_stage_completions
   WHERE entity_type = 'company' AND entity_id = :company_id
   ORDER BY completed_at
   ```
3. Include `stage_completions` in the response JSON

**Files**: `api/routes/company_routes.py`

### T2: Extend contact detail API with expanded enrichment + new fields
**Traces**: FR-18

Update `GET /api/contacts/<id>` in `api/routes/contact_routes.py`:

1. Add `career_trajectory`, `previous_companies`, `speaking_engagements`, `publications`, `twitter_handle`, `github_username`, `ai_champion`, `ai_champion_score`, `authority_score` to the enrichment sub-object
2. Add `last_enriched_at`, `employment_status`, `employment_verified_at` to the contact response
3. Remove deprecated flags from default rendering (they can still be returned but aren't highlighted)

**Files**: `api/routes/contact_routes.py`

### T3: Restructure CompanyDetail with tabs
**Traces**: FR-1 through FR-9, AC-1 through AC-4

Rewrite `CompanyDetail.tsx` to use `Tabs` component with 3 tabs:

**Overview tab** (FR-2):
- Header: name, domain link, website_url link, linkedin_url link, logo
- Classification section (unchanged — 8 fields)
- CRM section: keep only `tier`, `buying_stage`, `engagement_status` as editable selects (FR-5, AC-4)
- Location section (unchanged)
- Summary & Notes: `summary` (read-only), `notes` (editable)
- Custom Fields (unchanged)
- Tags (unchanged)
- Contacts mini-table (unchanged)

**Enrichment tab** (FR-3):
- 4 CollapsibleSections for L2 modules (Company Profile, Strategic Signals, Market & News, Pain & Opportunity) — each reads specific keys from `enrichment_l2` blob
- Legal & Registry section — add `insolvency_details`, `active_insolvency_count` rendering
- Enrichment Timeline (moved from bottom)

**Metadata tab** (FR-4, FR-9):
- L1 Triage section: `confidence`, `quality_score`, `qc_flags` (as badges), `research_query`, `triage_notes` (editable), `triage_score`, `pre_score`
- Stage Completions: render `stage_completions` as colored chips
- Costs: `verified_revenue_eur_m`, `verified_employees`, `enrichment_cost_usd`, `data_quality_score`
- Error section (conditional)
- Timestamps: `created_at`, `updated_at`, `last_enriched_at`

**Files**: `frontend/src/pages/companies/CompanyDetail.tsx`

### T4: Restructure ContactDetail with tabs
**Traces**: FR-10 through FR-14, AC-5, AC-6

Rewrite `ContactDetail.tsx` to use `Tabs` component with 2 tabs:

**Overview tab** (FR-11):
- Header: photo, name, title, icp badge, message_status badge, linkedin link
- Company card (unchanged)
- Contact Info: email, phone, city, country + `employment_status`, `employment_verified_at`, `last_enriched_at` (FR-14)
- Classification (unchanged — 6 editable selects)
- Notes (editable)
- Custom Fields
- Messages mini-table

**Enrichment tab** (FR-12):
- Person Summary section: `person_summary`, `linkedin_profile_summary`, `relationship_synthesis`
- Career & Social section: `career_trajectory`, `previous_companies` (render as list), `speaking_engagements`, `publications`, `twitter_handle` (as link), `github_username` (as link)
- Scores: `contact_score`, `ai_champion`, `ai_champion_score`, `authority_score`, `enrichment_cost_usd`
- Enrichment Timeline

Remove deprecated fields (FR-13, AC-6): `processed_enrich`, `email_lookup`, `duplicity_check`, `duplicity_conflict`, `duplicity_detail`

**Files**: `frontend/src/pages/contacts/ContactDetail.tsx`

### T5: Update TypeScript types
**Traces**: FR-15, FR-18

Update interfaces in query hook files:

1. `CompanyDetail` type: add `website_url`, `linkedin_url`, `logo_url`, `last_enriched_at`, `data_quality_score`, `stage_completions`, `enrichment_l1`
2. `ContactDetail` type: add `last_enriched_at`, `employment_status`, `employment_verified_at`; expand `enrichment` sub-type with career/social fields + scores
3. Remove deprecated fields from types (or mark as optional — backward compat)

**Files**: `frontend/src/api/queries/useCompanies.ts`, `frontend/src/api/queries/useContacts.ts`

### T6: Tests
**Traces**: AC-1 through AC-7

**Unit tests** (API):
- Test company detail endpoint returns new fields (website_url, linkedin_url, stage_completions)
- Test company detail with no stage completions returns empty array
- Test contact detail returns expanded enrichment fields
- Test contact detail with null enrichment returns null

**E2E tests** (Playwright):
- Test company detail opens to Overview tab by default
- Test tab switching works (Overview → Enrichment → Metadata)
- Test company Enrichment tab shows L2 module sections
- Test company Metadata tab shows stage completion chips
- Test company CRM section has exactly 3 selects (tier, buying_stage, engagement_status)
- Test contact detail opens to Overview tab
- Test contact Enrichment tab shows career fields when enrichment exists
- Test contact detail does not show deprecated status flags

**Files**: `tests/unit/test_company_routes.py`, `tests/unit/test_contact_routes.py`, `tests/e2e/test_entity_detail.py`

### T7: Documentation
**Traces**: Quality gate

1. Update `docs/ARCHITECTURE.md` — React frontend section (mention tabs, field organization)
2. Update `CHANGELOG.md` with feature summary
3. Update `BACKLOG.md` — mark this feature, note any follow-ups discovered

**Files**: `docs/ARCHITECTURE.md`, `CHANGELOG.md`, `BACKLOG.md`

## Traceability Matrix

| AC | Tasks | Tests |
|----|-------|-------|
| AC-1: Company Overview Tab | T3, T5 | E2E: default tab, fields present |
| AC-2: Company Enrichment Tab | T3 | E2E: L2 module sections, Legal section |
| AC-3: Company Metadata Tab | T1, T3, T5 | E2E: L1 details, stage chips; Unit: API stage_completions |
| AC-4: Pipeline Fields Removed | T3 | E2E: exactly 3 CRM selects |
| AC-5: Contact Enrichment Tab | T2, T4, T5 | E2E: career fields shown; Unit: API enrichment fields |
| AC-6: Contact Deprecated Removed | T4 | E2E: no deprecated flags |
| AC-7: API New Fields | T1, T2 | Unit: company + contact API responses |

## Effort Estimate

| Task | Effort | Notes |
|------|--------|-------|
| T1 | S | ~30 lines added to existing endpoint |
| T2 | S | ~20 lines added to existing endpoint |
| T3 | L | Major component restructure, ~300 lines rewritten |
| T4 | M | Simpler restructure, ~200 lines |
| T5 | S | Type definitions only |
| T6 | M | ~8 unit tests + ~8 E2E tests |
| T7 | S | Doc updates |

**Total**: M-L (bulk of work is T3 + T4 frontend restructure)
