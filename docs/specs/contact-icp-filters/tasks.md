# Contact ICP Filters — Tasks

**Feature**: BL-046 | **Date**: 2026-02-19 | **Status**: Draft

## Task List

### Phase 1: Database & Backend Foundation

#### T1: Migration — Add linkedin_activity_level column
**Traces**: FR-11, AC-6 | **Effort**: S | **Depends on**: —

- Create `migrations/023_linkedin_activity_level.sql`
- Create `linkedin_activity_level` enum type: `active`, `moderate`, `quiet`, `unknown`
- Add column to `contacts` table with default `'unknown'`
- Update `api/models.py` Contact model
- Add `LINKEDIN_ACTIVITY_DISPLAY` map to `api/display.py`
- **Test**: Migration applies cleanly; model reflects new column

#### T2: Person enricher — Store linkedin_activity_level
**Traces**: FR-11, AC-6 | **Effort**: S | **Depends on**: T1

- In `api/services/person_enricher.py`, find where `recent_activity_level` is extracted from signals_data
- Map Perplexity value to enum: active→active, moderate→moderate, quiet/inactive→quiet, else→unknown
- Write to `contact.linkedin_activity_level` during contact update
- **Test**: Unit test enricher saves activity level correctly for each mapping

#### T3: API — Multi-value + exclude filter params on GET /api/contacts
**Traces**: FR-4 to FR-11, AC-1, AC-2, AC-6 | **Effort**: M | **Depends on**: T1

- Extend `contact_routes.py` `list_contacts()` to accept new params:
  - `industry`, `company_size`, `geo_region`, `revenue_range` (company filters via existing JOIN)
  - `seniority_level`, `department`, `linkedin_activity` (contact filters)
  - `job_titles` (ILIKE match on job_title)
  - Each with corresponding `{field}_exclude` boolean param
- Multi-value: split on comma → `WHERE field IN (:vals)` or `WHERE field NOT IN (:vals) OR field IS NULL`
- `exclude_campaign_id` param: LEFT JOIN campaign_contacts, WHERE cc.id IS NULL
- Validate enum values against known sets; silently ignore invalid values
- Preserve SQLite compat for tests (LIKE instead of ILIKE where needed)
- **Test**: Unit tests for each filter param (include + exclude mode), multi-value, NULL handling, invalid values ignored, campaign exclusion

#### T4: API — Filter counts endpoint
**Traces**: FR-3, AC-3 | **Effort**: M | **Depends on**: T3

- New endpoint: `POST /api/contacts/filter-counts`
- Accept JSON body with `filters` dict, `search`, `tag_name`, `owner_name`, `exclude_campaign_id`
- For each facet field, run COUNT GROUP BY with all OTHER filters applied (not own)
- Return `{ total, facets: { field: [{value, count}, ...] } }`
- Facet fields: industry, company_size, geo_region, revenue_range, seniority_level, department, linkedin_activity
- Tenant-isolated (WHERE tenant_id = :tid)
- **Test**: Unit tests — counts correct with no filters, with single filter, with cross-filters, with exclude mode, tenant isolation

#### T5: API — Job title suggestions endpoint
**Traces**: FR-10, AC-4 | **Effort**: S | **Depends on**: —

- New endpoint: `GET /api/contacts/job-titles?q=CEO&limit=20`
- ILIKE search on contacts.job_title, GROUP BY job_title, COUNT, ORDER BY count DESC
- Min 2 chars required (return empty if q < 2)
- Tenant-isolated
- **Test**: Unit test — returns distinct titles with counts, respects limit, min chars

### Phase 2: Frontend Components

#### T6: MultiSelectFilter component
**Traces**: FR-1, FR-2, FR-3, AC-1, AC-2, AC-3 | **Effort**: L | **Depends on**: —

- New component: `frontend/src/components/ui/MultiSelectFilter.tsx`
- Props: `label`, `options: {value, label, count}[]`, `selected: string[]`, `exclude: boolean`, `onSelectionChange`, `onExcludeToggle`, `searchable?: boolean`
- Trigger: shows selected chips (removable), include/exclude toggle icon, dropdown arrow
- Dropdown: search input (local filter), checkboxes with labels and counts, "Clear" action
- Options sorted by count descending; zero-count options dimmed at bottom
- Keyboard: arrow navigation, Enter to toggle, Escape to close, Tab to toggle button
- Click outside to close (useRef + useEffect)
- Responsive: full-width on mobile
- **Test**: Component renders, selection works, exclude toggles, search filters options, keyboard nav

#### T7: Job title typeahead component
**Traces**: FR-10, AC-4 | **Effort**: M | **Depends on**: T5

- Extend MultiSelectFilter or create variant for API-driven suggestions
- On typing (debounced 300ms, min 2 chars): fetch `/api/contacts/job-titles?q=...`
- Show suggestions as dropdown with counts
- Click to add to selection (chip appears in trigger)
- Already-selected titles filtered from suggestions
- **Test**: Debounced fetch, suggestions rendered, selection adds chip

#### T8: useAdvancedFilters hook
**Traces**: FR-12, FR-15, FR-17 | **Effort**: M | **Depends on**: T6

- New hook: `frontend/src/hooks/useAdvancedFilters.ts`
- State: `AdvancedFilterState` with typed filter entries (values array + exclude boolean)
- Methods: `setFilter(key, values, exclude)`, `clearFilter(key)`, `clearAll()`, `activeFilterCount`
- `toQueryParams()`: serialize to flat `Record<string, string>` for API calls
- Persistence: localStorage via `useLocalStorage` with `storageKey` param
- **Test**: State management, serialization, persistence

#### T9: useFilterCounts hook
**Traces**: FR-3, AC-3 | **Effort**: S | **Depends on**: T4, T8

- New hook: `frontend/src/hooks/useFilterCounts.ts`
- Calls `POST /api/contacts/filter-counts` with current filter state
- Debounced 300ms on filter changes
- Returns `{ facets, total, isLoading }`
- Uses TanStack Query with filter state as query key
- **Test**: Fires on filter change, debounced, returns structured facets

#### T10: Display maps for new filter options
**Traces**: FR-4 to FR-11 | **Effort**: S | **Depends on**: —

- Add `LINKEDIN_ACTIVITY_DISPLAY` to `frontend/src/lib/display.ts`
- Verify existing maps: `INDUSTRY_DISPLAY`, `COMPANY_SIZE_DISPLAY`, `GEO_REGION_DISPLAY`, `REVENUE_RANGE_DISPLAY`, `SENIORITY_DISPLAY`, `DEPARTMENT_DISPLAY` — ensure all enum values have display labels
- Export `filterOptions()` calls for each (may already exist)
- **Test**: All display maps return correct label/value pairs

### Phase 3: Page Integration

#### T11: ContactsPage — Advanced filters
**Traces**: FR-12, FR-14, FR-15, FR-16, FR-17, FR-18, AC-1 to AC-4, AC-7 | **Effort**: M | **Depends on**: T3, T6, T7, T8, T9, T10

- Replace/extend FilterBar on ContactsPage with AdvancedFilterBar
- Row 1: existing search + tag + owner (unchanged)
- Row 2: Company filters — Industry, Size, Region, Revenue (MultiSelectFilter with counts)
- Row 3: Contact filters — Seniority, Department, Job Title (typeahead), LinkedIn Activity
- Wire `useAdvancedFilters` for state, `useFilterCounts` for live counts
- Wire `toQueryParams()` into existing `useContacts` query hook
- Active filter count badge
- "Clear all" button
- Preserve existing sort, pagination behavior
- **Test**: E2E — filter interaction, results update, counts display, clear all, persistence across navigation

#### T12: Campaign ContactPicker — Server-side filtering refactor
**Traces**: FR-12, FR-13, AC-5 | **Effort**: M | **Depends on**: T3, T6, T8, T11

- Refactor ContactPicker from client-side 200-limit to server-side filtered
- Use `useContacts` hook with `exclude_campaign_id` param
- Add AdvancedFilterBar (same as ContactsPage, minus tag/owner which are less relevant here)
- Infinite scroll for results (paginated API)
- Selection state (`Set<string>`) preserved across filter changes and pages
- "Select all page" selects visible contacts only
- Row layout: checkbox + name + title + company + industry badge + size badge
- Footer: Cancel + "Add N Contacts" button
- **Test**: E2E — open picker, filter, select contacts, add to campaign, verify exclusion of existing contacts

### Phase 4: Polish & Tests

#### T13: E2E test — ICP selection workflow
**Traces**: AC-7 | **Effort**: S | **Depends on**: T11, T12

- Playwright test: AiTransformers.eu ICP selection scenario
  1. Navigate to Contacts page
  2. Set company filters: industry, size, region
  3. Set contact filters: seniority, department
  4. Verify result count updates
  5. Verify filter counts are shown
  6. Navigate to campaign, open picker, apply same filters
  7. Select and add contacts
- **Test**: Full E2E scenario passes

#### T14: Unit tests — API filters comprehensive
**Traces**: All ACs | **Effort**: M | **Depends on**: T3, T4, T5

- Comprehensive unit tests for all filter combinations
- Multi-value include and exclude for each field
- Cross-filter count accuracy
- Job title suggestions accuracy
- Edge cases: empty filters, all-exclude, NULL handling
- SQLite compatibility verification
- **Test**: pytest suite covering all filter API behavior

## Traceability Matrix

| AC | Tasks | Tests |
|----|-------|-------|
| AC-1: Multi-select interaction | T3, T6, T8, T11 | T6 unit, T11 E2E, T14 |
| AC-2: Include/exclude toggle | T3, T6, T8, T11 | T6 unit, T11 E2E, T14 |
| AC-3: Cross-filter live counts | T4, T6, T9, T11 | T9 unit, T11 E2E, T14 |
| AC-4: Job title typeahead | T5, T7, T11 | T7 unit, T11 E2E, T14 |
| AC-5: Campaign contact picker | T3, T6, T8, T12 | T12 E2E |
| AC-6: LinkedIn activity filter | T1, T2, T3, T6, T11 | T2 unit, T14 |
| AC-7: AiTransformers.eu ICP | T11, T12 | T13 E2E |

## Task Dependencies (DAG)

```
T1 ──→ T2
T1 ──→ T3 ──→ T4 ──→ T9
              T3 ──→ T14
T5 ──→ T7
T6 ──→ T8 ──→ T9
T10 (parallel with everything)

T3 + T6 + T7 + T8 + T9 + T10 ──→ T11
T3 + T6 + T8 + T11 ──→ T12
T11 + T12 ──→ T13
T3 + T4 + T5 ──→ T14
```

**Parallelizable groups:**
- T1 + T5 + T6 + T10 (all independent)
- T2 + T3 (after T1) + T7 (after T5) + T8 (after T6)
- T4 + T9 (after their deps)
- T11, T12, T13, T14 (sequential due to integration deps)

## Testing Strategy

**Unit tests** (`tests/unit/`):
- Filter param parsing and SQL generation
- Multi-value splitting and validation
- Exclude mode with NULL handling
- Faceted count queries
- Job title suggestion queries
- Person enricher activity level mapping
- SQLite compatibility for all queries

**E2E tests** (`tests/e2e/`):
- Filter interaction on ContactsPage (select, exclude, clear)
- Live counts update on filter change
- Job title typeahead search and selection
- Campaign picker with filters and selection
- AiTransformers.eu ICP selection workflow
- Filter persistence across navigation
