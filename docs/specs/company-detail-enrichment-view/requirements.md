# Company Detail Enrichment View — Requirements

**Status**: Draft | **Date**: 2026-02-17
**Theme**: Contact Intelligence
**Backlog**: BL-046

## Purpose

The enrichment field audit (BL-045) restructured company data into modular enrichment tables (L1, L2 profile/signals/market/opportunity), but the React company detail view still shows the old flat structure. Users can't see L1 enrichment provenance, miss 8 new L2 fields, and don't see new company link columns. This feature closes the gap between "data exists in DB" and "data is visible in the UI."

## Requirements

### Functional Requirements

1. **FR-1**: API returns 5 new company columns (`website_url`, `linkedin_url`, `logo_url`, `last_enriched_at`, `data_quality_score`) in the company detail response
2. **FR-2**: Company detail header shows website and LinkedIn as clickable external links, logo as avatar
3. **FR-3**: Company detail shows L1 enrichment metadata (confidence, quality_score, qc_flags, enriched_at, cost) when available
4. **FR-4**: L2 enrichment section is organized into 4 module sub-sections: Company Profile, Strategic Signals, Market Intel, Sales Opportunity
5. **FR-5**: L2 section displays all 8 new fields (growth_indicators, job_posting_count, hiring_departments, media_sentiment, press_releases, thought_leadership, ai_adoption_level, news_confidence)
6. **FR-6**: Enrichment Timeline uses L1 enriched_at from `enrichment_l1` instead of `updated_at`
7. **FR-7**: `data_quality_score` shown as a badge near the header when available
8. **FR-8**: TypeScript types updated to include `enrichment_l1` and new company fields

### Non-Functional Requirements

1. **NFR-1**: No additional API calls — all new data comes from the existing company detail endpoint
2. **NFR-2**: Backward compatible — gracefully handles null for all new fields (pre-enrichment companies)

## Acceptance Criteria

- **AC-1**: Given a company with L1 enrichment data, when viewing the detail, then confidence score, quality score, QC flags, and L1 cost are visible
- **AC-2**: Given a company with modular L2 data, when viewing the detail, then L2 fields are grouped under "Company Profile", "Strategic Signals", "Market Intel", "Sales Opportunity" sub-headings
- **AC-3**: Given a company with new L2 signal fields (growth_indicators, job_posting_count, etc.), when viewing the detail, then all 8 new fields are displayed in their respective module sections
- **AC-4**: Given a company with website_url or linkedin_url, when viewing the detail, then clickable links appear in the header area
- **AC-5**: Given a company with no enrichment data (all nulls), when viewing the detail, then enrichment sections are hidden and no errors occur
- **AC-6**: Given a company with L1 enrichment, when viewing the Enrichment Timeline, then the L1 entry shows enrichment_l1.enriched_at (not company.updated_at)
- **AC-7**: Given the TypeScript codebase, when building the frontend, then no type errors related to the new fields

## Out of Scope

- Vanilla dashboard (`dashboard/companies.html`) — React only
- Editing enrichment fields — these are read-only, set by enrichment pipelines
- Contact detail view updates — separate feature
- New enrichment pipeline triggers from the detail view

## Dependencies

- **Backlog**: BL-045 (Enrichment Field Audit) — merged to staging, provides the data model
- **Tech Debt**: None blocking
- **External**: None

## Open Questions

None — all clarified in Phase 2.
