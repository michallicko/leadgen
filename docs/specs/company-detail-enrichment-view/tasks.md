# Company Detail Enrichment View — Tasks

**Status**: Draft | **Date**: 2026-02-17
**Branch**: `feature/company-detail-enrichment-view`

## Tasks

Each task = one commit. Implement in order.

### Task 1: Add missing columns to company detail API
- **Files**: `api/routes/company_routes.py`
- **Tests**: `tests/unit/test_company_routes.py::test_company_detail_new_fields`
- **Commit**: `Add website_url, linkedin_url, logo_url, last_enriched_at, data_quality_score to company detail API`
- **Size**: S
- **ACs**: AC-4 (API part), AC-5 (null handling)

Steps:
1. Add `c.website_url, c.linkedin_url, c.logo_url, c.last_enriched_at, c.data_quality_score` to the SELECT query
2. Add corresponding keys to the `company` dict response
3. Write test: company detail returns new fields when populated
4. Write test: company detail returns null for new fields when empty

### Task 2: Update TypeScript types
- **Files**: `frontend/src/api/queries/useCompanies.ts`
- **Tests**: TypeScript compilation (AC-7)
- **Commit**: `Add enrichment_l1 and new company fields to CompanyDetail TypeScript type`
- **Size**: S
- **ACs**: AC-7

Steps:
1. Add `enrichment_l1` interface with all 9 fields
2. Add `website_url`, `linkedin_url`, `logo_url`, `last_enriched_at`, `data_quality_score` to CompanyDetail
3. Add `enrichment_l1` field to CompanyDetail interface
4. Verify `npx tsc --noEmit` passes

### Task 3: Add L1 enrichment section + header links + modular L2 + timeline fix
- **Files**: `frontend/src/pages/companies/CompanyDetail.tsx`
- **Tests**: Visual verification on staging
- **Commit**: `Restructure company detail: L1 section, modular L2, header links, timeline fix`
- **Size**: M
- **ACs**: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

Steps:
1. **Header**: Add logo avatar (first-letter fallback), website + LinkedIn links, data quality badge
2. **L1 Section**: New CollapsibleSection with confidence, quality_score, qc_flags (pill array), cost, enriched_at. Research query as muted text.
3. **L2 Restructure**: Replace flat field list with 4 sub-sections (Company Profile, Strategic Signals, Market Intel, Sales Opportunity). Add 8 new fields. Hide empty modules.
4. **Timeline fix**: Use `enrichment_l1?.enriched_at` instead of `company.updated_at` for L1 entry
5. **Null safety**: All new sections gated on data presence

## Traceability Matrix

| AC | Description | Task(s) | Test(s) |
|----|-------------|---------|---------|
| AC-1 | L1 metadata visible | Task 3 | Visual on staging |
| AC-2 | L2 grouped by module | Task 3 | Visual on staging |
| AC-3 | 8 new L2 fields displayed | Task 3 | Visual on staging |
| AC-4 | Website/LinkedIn clickable links | Task 1, 2, 3 | `test_company_detail_new_fields` + visual |
| AC-5 | Null company shows no errors | Task 1, 3 | `test_company_detail_new_fields` + visual |
| AC-6 | Timeline uses L1 enriched_at | Task 3 | Visual on staging |
| AC-7 | No TypeScript errors | Task 2 | `npx tsc --noEmit` |

## Discovered Scope

| Discovery | Impact | Decision |
|-----------|--------|----------|
| | | |
