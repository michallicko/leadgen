# Entity Detail Cleanup — Requirements

**Feature**: Clean up company and contact entity detail views in the React SPA to reflect the enrichment field audit (BL-045), deprecate pipeline fields, and surface all enrichment data.

**Date**: 2026-02-19

## Purpose

The enrichment field audit (migrations 019-023) restructured the database — splitting L2 into 4 modules, creating company_enrichment_l1, expanding contact_enrichment, and adding new fields (website_url, linkedin_url, etc.). The entity detail UIs were never updated to match. Meanwhile, pipeline fields (`status`, `crm_status`, `cohort`, `lemlist_synced`) are vestigial from the old linear enrichment model — now replaced by DAG completions.

**Who it serves**: Users reviewing enriched company/contact data in the dashboard. Currently they see stale sections, deprecated fields, and miss new enrichment data entirely.

## Functional Requirements

### Company Detail

- **FR-1**: Organize company detail into 3 tabs: **Overview**, **Enrichment**, **Metadata**
- **FR-2**: Overview tab shows: header (name, domain link, website/linkedin/logo links), Classification, CRM fields (tier, buying_stage, engagement_status — no more status/crm_status/cohort), Location, Summary & Notes, Tags, Contacts mini-table
- **FR-3**: Enrichment tab shows L2 data organized by module (Company Profile, Strategic Signals, Market & News, Pain & Opportunity), Legal & Registry section with full insolvency details, and Enrichment Timeline
- **FR-4**: Metadata tab shows: L1 triage details (confidence, quality_score, qc_flags, research query), enrichment stage completions (from entity_stage_completions), enrichment costs breakdown, data quality score, timestamps, error messages
- **FR-5**: Remove deprecated pipeline fields from editable controls: `status`, `crm_status`, `cohort`, `lemlist_synced`
- **FR-6**: Add `website_url`, `linkedin_url`, `logo_url` as clickable links in the header area
- **FR-7**: Add `domain` as a clickable link in the header (currently missing from React detail)
- **FR-8**: Show `data_quality_score` and `last_enriched_at` in the overview header area
- **FR-9**: Display enrichment stage completions (L1, L2, Registry, Person, etc.) as status chips in the Metadata tab, sourced from `entity_stage_completions`

### Contact Detail

- **FR-10**: Organize contact detail into 2 tabs: **Overview**, **Enrichment**
- **FR-11**: Overview tab shows: header (photo, name, title, links), Company card, Contact Info, Classification, Notes, Messages mini-table
- **FR-12**: Enrichment tab shows: Person Summary, LinkedIn Profile, Relationship Synthesis, Career & Social (career_trajectory, previous_companies, speaking_engagements, publications, twitter_handle, github_username), Scores (ai_champion, ai_champion_score, authority_score, contact_score), Enrichment Timeline
- **FR-13**: Remove deprecated status flags: `processed_enrich`, `email_lookup`, `duplicity_check`, `duplicity_conflict`, `duplicity_detail`
- **FR-14**: Surface new contact fields: `employment_status`, `employment_verified_at`, `last_enriched_at`

### API

- **FR-15**: Company detail API (`GET /api/companies/<id>`) must return: `website_url`, `linkedin_url`, `logo_url`, `last_enriched_at`, `data_quality_score`
- **FR-16**: Company detail API must return `enrichment_l1` object (already does — no change needed)
- **FR-17**: Company detail API must return `stage_completions` — a list of `{stage, status, completed_at, cost_usd}` from entity_stage_completions for this company
- **FR-18**: Contact detail API (`GET /api/contacts/<id>`) must return expanded enrichment object including: `career_trajectory`, `previous_companies`, `speaking_engagements`, `publications`, `twitter_handle`, `github_username`, `employment_status`, `employment_verified_at`, `last_enriched_at`

## Non-Functional Requirements

- **NFR-1**: No new API endpoints — extend existing detail endpoints only
- **NFR-2**: Tab switch must be instant (no re-fetch) — all data loaded in the initial detail query
- **NFR-3**: Backward compatible — API changes are additive (new fields, never remove existing ones)
- **NFR-4**: L2 enrichment rendering must handle both old monolithic data (company_enrichment_l2 fallback) and new module data gracefully

## Acceptance Criteria

### AC-1: Company Overview Tab
**Given** a user opens a company detail
**When** the detail loads
**Then** the Overview tab is active by default, showing header with domain/website/linkedin links, Classification, CRM fields (tier, buying_stage, engagement_status only), Location, Summary & Notes, Tags, Contacts

### AC-2: Company Enrichment Tab
**Given** a company has L2 enrichment data
**When** the user clicks the Enrichment tab
**Then** they see 4 organized sections (Company Profile, Strategic Signals, Market & News, Pain & Opportunity) plus Legal & Registry with insolvency details and Enrichment Timeline

### AC-3: Company Metadata Tab
**Given** a company has been through L1 enrichment
**When** the user clicks the Metadata tab
**Then** they see L1 triage details (confidence, quality_score, qc_flags), stage completion chips, enrichment cost breakdown, data_quality_score, and timestamps

### AC-4: Pipeline Fields Removed
**Given** a user opens company detail
**When** they look at the CRM section
**Then** there is no `status`, `crm_status`, `cohort`, or `lemlist_synced` dropdown — only `tier`, `buying_stage`, and `engagement_status`

### AC-5: Contact Enrichment Tab
**Given** a contact has person enrichment data
**When** the user clicks the Enrichment tab
**Then** they see Person Summary, LinkedIn Profile, Relationship Synthesis, Career & Social section (career_trajectory, previous_companies, etc.), and Scores

### AC-6: Contact Deprecated Fields Removed
**Given** a user opens contact detail
**When** they view the contact info
**Then** there are no `processed_enrich`, `email_lookup`, or `duplicity_*` fields shown

### AC-7: API Returns New Fields
**Given** a company has website_url and linkedin_url set
**When** the detail API is called
**Then** the response includes `website_url`, `linkedin_url`, `logo_url`, `last_enriched_at`, `data_quality_score`, and `stage_completions`

## Out of Scope

- Vanilla dashboard updates (being phased out)
- Making `status` derivable from DAG completions (future — for now just remove it from UI)
- PATCH endpoint changes (editable field set stays the same minus removed fields)
- Running migration 024 (drop deprecated columns) — that's a separate BL-045 Phase D concern
- New enrichment stages or pipeline changes
- Contact detail metadata tab (not enough data to warrant it yet)
