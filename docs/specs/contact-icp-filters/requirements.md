# Contact ICP Filters — Requirements

**Feature**: BL-046 | **Date**: 2026-02-19 | **Status**: Draft

## Purpose

Enable users to select Ideal Customer Profile (ICP) contacts for outreach campaigns using multi-dimensional filters across company and contact attributes. Today the Contacts page has 5 basic single-select filters (search, tag, owner, ICP fit, message status). The Campaign ContactPicker has only text search and is limited to 200 contacts client-side. Users need to filter by company demographics (industry, size, region, revenue) and contact attributes (seniority, department, job title, LinkedIn activity) with multi-select, include/exclude toggles, and live option counts to build precise audience segments.

**Test case**: Select ICP contacts for AiTransformers.eu — an AI consulting company targeting mid-market+ enterprises in specific industries and regions, reaching decision-makers (C-level/VP/Director) active on LinkedIn.

## Functional Requirements

### Multi-Select Filter Component
- **FR-1**: Multi-select dropdown with typeahead search within options. User can select multiple values simultaneously. Selected values appear as removable chips in the filter trigger.
- **FR-2**: Each multi-select filter has an include/exclude toggle. Default is "include" (show contacts matching selected values). "Exclude" mode hides contacts matching selected values. Visual distinction between modes (e.g., blue chips for include, orange for exclude).
- **FR-3**: Each filter option displays a live count of matching contacts. Counts reflect all OTHER active filters (faceted search pattern — standard in e-commerce). Counts update when any filter changes (debounced 300ms).

### Company Filters (cross-entity via company JOIN)
- **FR-4**: Industry filter — multi-select from `companies.industry` enum (~21 values). Include/exclude toggle.
- **FR-5**: Company Size filter — multi-select from `companies.company_size` enum (micro, startup, smb, mid_market, enterprise). Include/exclude toggle.
- **FR-6**: Geo Region filter — multi-select from `companies.geo_region` enum (dach, nordics, benelux, cee, uk_ireland, southern_europe, us, other). Include/exclude toggle.
- **FR-7**: Revenue Range filter — multi-select from `companies.revenue_range` enum (micro, small, medium, mid_market, enterprise). Include/exclude toggle.

### Contact Filters
- **FR-8**: Seniority Level filter — multi-select from `contacts.seniority_level` enum (c_level, vp, director, manager, individual_contributor, founder, other).
- **FR-9**: Department filter — multi-select from `contacts.department` enum (10 values).
- **FR-10**: Job Title filter — typeahead text input that queries distinct job titles from the database. Multi-select (user can pick multiple titles). Partial match (ILIKE).
- **FR-11**: LinkedIn Activity filter — multi-select from new `contacts.linkedin_activity_level` enum (active, moderate, quiet, unknown). Requires new DB column.

### Shared Between Contacts Page and Campaign Picker
- **FR-12**: The advanced filter component is reusable across both the Contacts list page and the Campaign ContactPicker modal. Same filters, same behavior, two contexts.
- **FR-13**: Campaign ContactPicker uses server-side filtering (replacing current client-side 200-contact limit). Existing campaign contacts are excluded from results.

### Existing Filters Retained
- **FR-14**: Existing filters (search, tag, owner, ICP fit, message status) remain available alongside new filters. Search remains a text input. Tag and owner remain single-select (upgrade to multi-select is out of scope).

### UX
- **FR-15**: Filters apply immediately on selection (no "Apply" button). Results update as filters change.
- **FR-16**: "Clear all filters" button resets all filters to default state. Individual filter chips are removable.
- **FR-17**: Active filter state persists in localStorage (same pattern as current filters). Restored when user returns to page.
- **FR-18**: Filter summary shows count of active filters, e.g., "Filters (3)" badge.

## Non-Functional Requirements

- **NFR-1**: Filter counts endpoint responds within 200ms for datasets up to 10,000 contacts.
- **NFR-2**: Filter state changes do not cause full page re-renders — only the results table and count badges update.
- **NFR-3**: SQLite compatibility maintained for test suite (no PostgreSQL-only features in filter queries, or provide dialect fallbacks).
- **NFR-4**: Multi-select dropdowns are keyboard-navigable (arrow keys, Enter to select, Escape to close).

## Acceptance Criteria

### AC-1: Multi-Select Filter Interaction
**Given** I am on the Contacts page
**When** I click the "Industry" filter dropdown
**Then** I see a searchable list of all industries with contact counts per option
**And** I can select multiple industries simultaneously
**And** selected values appear as chips in the filter trigger
**And** the contacts table updates immediately to show only contacts at companies in the selected industries

### AC-2: Include/Exclude Toggle
**Given** I have selected industries "Software / SaaS" and "IT Services" in include mode
**When** I toggle the Industry filter to "Exclude" mode
**Then** the contact list shows all contacts EXCEPT those at SaaS and IT Services companies
**And** the filter chips visually indicate exclusion mode (color change + "NOT" indicator)
**And** other filter counts update to reflect the exclusion

### AC-3: Cross-Filter Live Counts
**Given** I have selected region "DACH"
**When** I open the Industry filter dropdown
**Then** each industry option shows the count of contacts at DACH companies in that industry
**And** industries with zero matching contacts still appear but show count (0)
**And** the total contact count in the header reflects the DACH filter

### AC-4: Job Title Typeahead
**Given** I am filtering contacts
**When** I type "CEO" in the Job Title filter
**Then** I see a dropdown of distinct job titles containing "CEO" from the database (e.g., "CEO", "Co-CEO", "CEO & Founder") with counts
**And** I can select multiple titles
**And** the contact list updates to show only contacts with those titles

### AC-5: Campaign Contact Picker
**Given** I am on a Campaign detail page (draft status), Contacts tab
**When** I click "Add Contacts"
**Then** I see the same advanced filter panel as the Contacts page
**And** I can filter, search, and multi-select contacts
**And** contacts already assigned to this campaign are excluded from results
**And** I can add the selected contacts to the campaign

### AC-6: LinkedIn Activity Filter
**Given** contacts have been enriched with person-level data
**When** I use the LinkedIn Activity filter and select "active"
**Then** only contacts with linkedin_activity_level = "active" are shown
**And** the count next to "active" reflects how many contacts match (with other filters applied)

### AC-7: AiTransformers.eu ICP Selection
**Given** I want to build an outreach list for AiTransformers.eu (AI consulting, targeting enterprises)
**When** I set filters: Industry = Manufacturing, Financial Services; Size = mid_market, enterprise; Region = DACH, Nordics; Seniority = c_level, vp, director; Department = executive, engineering
**Then** the resulting contact list contains decision-makers at large companies in relevant industries and regions
**And** I can add these contacts to a campaign via the campaign picker

## Out of Scope

- Upgrading tag/owner filters to multi-select (keep as single-select)
- Saved filter presets / named ICP profiles (future feature)
- Contact score range slider (keep as sortable column)
- Company-level filter on the Companies page (this feature targets Contacts page + Campaign picker only)
- Backfilling linkedin_activity_level for existing contacts (future enrichment re-run)
- Boolean filters (AI champion, has email) — can be added later using same component
- Filter sharing / URL-based filter state (nice-to-have, not MVP)
