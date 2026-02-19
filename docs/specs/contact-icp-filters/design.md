# Contact ICP Filters — Design

**Feature**: BL-046 | **Date**: 2026-02-19 | **Status**: Draft

## Affected Components

| Component | File(s) | Change |
|-----------|---------|--------|
| DB schema | `migrations/023_linkedin_activity_level.sql` | New enum + column |
| Person enricher | `api/services/person_enricher.py` | Store activity level |
| Contacts API | `api/routes/contact_routes.py` | Multi-value + exclude filter params |
| Filter counts API | `api/routes/contact_routes.py` | New endpoint |
| Job title suggest API | `api/routes/contact_routes.py` | New endpoint |
| MultiSelectFilter | `frontend/src/components/ui/MultiSelectFilter.tsx` | New component |
| FilterBar | `frontend/src/components/ui/FilterBar.tsx` | Add multiSelect type |
| ContactsPage | `frontend/src/pages/contacts/ContactsPage.tsx` | Use new filters |
| useContacts hook | `frontend/src/api/contacts.ts` | Extended params |
| ContactPicker | `frontend/src/pages/campaigns/ContactPicker.tsx` | Server-side filtering |
| Display maps | `frontend/src/lib/display.ts` | Add LINKEDIN_ACTIVITY_DISPLAY |
| API types | `frontend/src/types/` | Filter state types |

## Data Model Changes

### New Column: `contacts.linkedin_activity_level`

```sql
-- Migration 023
CREATE TYPE linkedin_activity_level AS ENUM ('active', 'moderate', 'quiet', 'unknown');

ALTER TABLE contacts
  ADD COLUMN linkedin_activity_level linkedin_activity_level DEFAULT 'unknown';
```

No backfill — existing contacts remain `unknown`. Future person enrichment runs will populate this field.

### Person Enricher Update

In `person_enricher.py`, the signals phase already extracts `recent_activity_level` from Perplexity but discards it. Change: write it to `contacts.linkedin_activity_level` during the contact update step.

```python
# In _save_contact_fields() or equivalent:
contact.linkedin_activity_level = signals_data.get('recent_activity_level', 'unknown')
```

Map Perplexity values to enum: `active` → `active`, `moderate` → `moderate`, `quiet`/`inactive` → `quiet`, anything else → `unknown`.

## API Contracts

### Extended: `GET /api/contacts`

New query parameters (all optional, additive AND logic between different filters):

| Param | Type | Example | Behavior |
|-------|------|---------|----------|
| `industry` | Comma-separated | `software_saas,it` | Match contacts at companies with ANY of these industries |
| `industry_exclude` | Boolean | `true` | Invert: exclude matching industries |
| `company_size` | Comma-separated | `mid_market,enterprise` | Match by company size |
| `company_size_exclude` | Boolean | `true` | Invert |
| `geo_region` | Comma-separated | `dach,nordics` | Match by company region |
| `geo_region_exclude` | Boolean | `true` | Invert |
| `revenue_range` | Comma-separated | `medium,mid_market,enterprise` | Match by company revenue range |
| `revenue_range_exclude` | Boolean | `true` | Invert |
| `seniority_level` | Comma-separated | `c_level,vp,director` | Match by contact seniority |
| `seniority_level_exclude` | Boolean | `true` | Invert |
| `department` | Comma-separated | `executive,engineering` | Match by contact department |
| `department_exclude` | Boolean | `true` | Invert |
| `job_titles` | Comma-separated | `CEO,CTO,VP Engineering` | ILIKE match on contact job_title |
| `job_titles_exclude` | Boolean | `true` | Invert |
| `linkedin_activity` | Comma-separated | `active,moderate` | Match by LinkedIn activity level |
| `linkedin_activity_exclude` | Boolean | `true` | Invert |
| `exclude_campaign_id` | UUID | `{uuid}` | Exclude contacts already in this campaign |

**Multi-value handling**: Split on comma, build `WHERE field IN (...)`. With `_exclude=true`, use `WHERE field NOT IN (...)` or `WHERE field IS NULL OR field NOT IN (...)` (include NULLs when excluding).

**NULL handling for excludes**: When excluding values, contacts with NULL in the filtered field are INCLUDED in results (they don't match the excluded values). This prevents "exclude SaaS" from also hiding contacts with unknown industry.

**Existing params unchanged**: `search`, `tag_name`, `owner_name`, `icp_fit`, `message_status`, `company_id`, `sort`, `sort_dir`, `page`, `page_size` all work as before. `icp_fit` and `message_status` could be upgraded to multi-value in the same pattern but that's optional.

### New: `POST /api/contacts/filter-counts`

Returns faceted counts for all filterable fields. Each field's counts are computed with all OTHER active filters applied (standard faceted search).

**Request:**
```json
{
  "filters": {
    "industry": { "values": ["software_saas"], "exclude": false },
    "geo_region": { "values": ["dach"], "exclude": false },
    "seniority_level": { "values": ["c_level", "vp"], "exclude": false }
  },
  "search": "optional text search",
  "tag_name": "optional",
  "owner_name": "optional",
  "exclude_campaign_id": "optional uuid"
}
```

**Response:**
```json
{
  "total": 142,
  "facets": {
    "industry": [
      { "value": "software_saas", "count": 89 },
      { "value": "it", "count": 34 },
      { "value": "manufacturing", "count": 12 }
    ],
    "company_size": [
      { "value": "enterprise", "count": 45 },
      { "value": "mid_market", "count": 67 }
    ],
    "geo_region": [],
    "revenue_range": [],
    "seniority_level": [],
    "department": [],
    "linkedin_activity": []
  }
}
```

**Query strategy**: Run one COUNT GROUP BY query per facet field. Each query applies all filters EXCEPT the field being counted. For ~2600 contacts and 7 facets, this is 7 queries each completing in <10ms — total <100ms.

```sql
-- Example: industry facet counts (apply all filters EXCEPT industry)
SELECT co.industry, COUNT(*) as count
FROM contacts ct
JOIN companies co ON ct.company_id = co.id
WHERE co.geo_region IN ('dach')
  AND ct.seniority_level IN ('c_level', 'vp')
GROUP BY co.industry
ORDER BY count DESC
```

### New: `GET /api/contacts/job-titles`

Typeahead endpoint for job title suggestions.

**Request:** `GET /api/contacts/job-titles?q=CEO&limit=20`

**Response:**
```json
{
  "titles": [
    { "title": "CEO", "count": 15 },
    { "title": "CEO & Co-Founder", "count": 8 },
    { "title": "Co-CEO", "count": 2 }
  ]
}
```

**Query:**
```sql
SELECT job_title, COUNT(*) as count
FROM contacts
WHERE tenant_id = :tenant_id
  AND job_title ILIKE '%' || :q || '%'
  AND job_title IS NOT NULL
GROUP BY job_title
ORDER BY count DESC
LIMIT :limit
```

## UX Flow

### Filter Layout

Two visual groups within a single filter bar, separated by a subtle divider:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔍 Search...  │ Tag ▾ │ Owner ▾ │                              Filters (5) │
├─────────────────────────────────────────────────────────────────────────────┤
│ Company: [Industry ▾] [Size ▾] [Region ▾] [Revenue ▾]                     │
│ Contact: [Seniority ▾] [Department ▾] [Job Title 🔍] [LinkedIn ▾]        │
└─────────────────────────────────────────────────────────────────────────────┘
```

- Row 1: Existing filters (search, tag, owner) + active filter count badge
- Row 2: New company filters (multi-select with include/exclude)
- Row 3: New contact filters (multi-select + typeahead)

### MultiSelectFilter Component

**Trigger (collapsed):**
```
┌──────────────────────────────────────────┐
│ Industry     [×SaaS] [×IT]    [⊕]  ▾    │
└──────────────────────────────────────────┘
```
- Label on left
- Selected value chips (removable with ×)
- Include/exclude toggle icon (⊕ = include, ⊖ = exclude)
- Dropdown arrow

**When nothing selected:** Shows "All" placeholder text.

**Include/exclude toggle:**
- Click toggles between modes
- Include mode: chips are default color (blue/gray)
- Exclude mode: chips turn orange/red, label shows "NOT" prefix
- Keyboard: Tab to toggle, Enter to switch

**Dropdown (expanded):**
```
┌──────────────────────────────────────────┐
│ 🔍 Filter industries...                 │
├──────────────────────────────────────────┤
│ ☑ Software / SaaS              (142)    │
│ ☑ IT Services                  (87)     │
│ ☐ Manufacturing                (38)     │
│ ☐ Healthcare & Pharma          (25)     │
│ ☐ Financial Services           (19)     │
│ ☐ Consulting                   (15)     │
│ ☐ Energy & Utilities           (8)      │
│ ☐ Automotive                   (5)      │
│ ...                                      │
├──────────────────────────────────────────┤
│ Clear selection                          │
└──────────────────────────────────────────┘
```
- Search input filters options locally (the full option list is already loaded)
- Checkbox + label + right-aligned count
- Options sorted by count descending (most contacts first)
- Options with count 0 shown at bottom, dimmed
- "Clear selection" at bottom to deselect all
- Clicks outside close the dropdown
- Max height with scroll for long lists

### Job Title Typeahead

Different from enum multi-select — uses API-driven suggestions:

```
┌──────────────────────────────────────────┐
│ Job Title  [×CEO] [×CTO]           ▾    │
└──────────────────────────────────────────┘
     │ (typing "VP")
     ▼
┌──────────────────────────────────────────┐
│ 🔍 VP                                   │
├──────────────────────────────────────────┤
│ VP of Engineering                  (12)  │
│ VP of Sales                        (8)  │
│ VP Product                         (5)  │
│ VP Marketing                       (3)  │
└──────────────────────────────────────────┘
```
- Type to search (debounced 300ms, hits `/api/contacts/job-titles?q=...`)
- Click to add to selection
- Already-selected titles hidden from suggestions
- Min 2 characters before suggestions appear

### Campaign ContactPicker Refactor

The current ContactPicker becomes a full-screen modal with:

```
┌──────────────────────────────────────────────────────────────────┐
│ Add Contacts to Campaign                              [× Close] │
├──────────────────────────────────────────────────────────────────┤
│ 🔍 Search...                                                    │
│ Company: [Industry ▾] [Size ▾] [Region ▾] [Revenue ▾]          │
│ Contact: [Seniority ▾] [Department ▾] [Job Title 🔍]           │
├──────────────────────────────────────────────────────────────────┤
│ 234 available · 12 selected                    [Select all page]│
├──────────────────────────────────────────────────────────────────┤
│ ☑ John Smith · CEO · Acme Corp · SaaS · Enterprise             │
│ ☐ Jane Doe · VP Engineering · TechCo · IT · Mid-market         │
│ ☑ Bob Johnson · Director AI · BigCorp · Manufacturing · Large  │
│ ...                                     (infinite scroll)       │
├──────────────────────────────────────────────────────────────────┤
│                              [Cancel]  [Add 12 Contacts]        │
└──────────────────────────────────────────────────────────────────┘
```

Key changes from current picker:
- Server-side filtering via `/api/contacts?...&exclude_campaign_id={id}`
- Infinite scroll (paginated API calls) instead of single 200-item fetch
- Same filter components as ContactsPage
- Selection state preserved across filter changes and pagination
- "Select all page" selects all currently-visible contacts (not all filtered results)
- Contact rows show company context (company name, industry, size) for informed selection

### Filter State Management

```typescript
// Shared filter state type
interface AdvancedFilterState {
  search: string
  tag_name: string
  owner_name: string
  // New multi-select filters
  industry: { values: string[]; exclude: boolean }
  company_size: { values: string[]; exclude: boolean }
  geo_region: { values: string[]; exclude: boolean }
  revenue_range: { values: string[]; exclude: boolean }
  seniority_level: { values: string[]; exclude: boolean }
  department: { values: string[]; exclude: boolean }
  job_titles: { values: string[]; exclude: boolean }
  linkedin_activity: { values: string[]; exclude: boolean }
}

// Custom hook
function useAdvancedFilters(storageKey: string): {
  filters: AdvancedFilterState
  setFilter: (key: string, values: string[], exclude?: boolean) => void
  clearFilter: (key: string) => void
  clearAll: () => void
  activeFilterCount: number
  toQueryParams: () => Record<string, string>
}
```

Serialize to API params:
```typescript
// { industry: { values: ['software_saas', 'it'], exclude: false } }
// → { industry: 'software_saas,it' }

// { company_size: { values: ['micro'], exclude: true } }
// → { company_size: 'micro', company_size_exclude: 'true' }
```

### Filter Counts Hook

```typescript
function useFilterCounts(filters: AdvancedFilterState): {
  facets: Record<string, { value: string; count: number }[]>
  total: number
  isLoading: boolean
}
```

- Calls `POST /api/contacts/filter-counts` with current filter state
- Debounced 300ms on filter changes
- Returns `{ facets, total, isLoading }`
- Uses TanStack Query with filter state as query key

## Architecture Decisions

- **Faceted counts via separate endpoint** rather than inline with contact list. Keeps the list query fast and simple. Counts endpoint can be optimized independently (caching, materialized views later).
- **Comma-separated multi-value params** rather than JSON body or repeated params. Simple, URL-readable, compatible with existing `request.args.get()` pattern. Comma is safe because no enum value contains commas.
- **No cascading filter narrowing** — all options always shown for each filter (with counts). Cascading would hide options that might be useful if the user changes another filter. Live counts already communicate "zero results" effectively.
- **Server-side filtering for campaign picker** — the current 200-contact limit is a blocker. With 2600+ contacts, client-side filtering is not viable. Server-side also enables the `exclude_campaign_id` param.
- **No saved filter presets** in MVP — out of scope. Users can rely on localStorage persistence for now. Named ICP profiles can be added later.

## Edge Cases

| Case | Handling |
|------|----------|
| All options selected in a filter | Same as no filter — show all contacts. Clear the filter to simplify state. |
| Exclude with NULL values | NULL fields are NOT excluded. "Exclude SaaS" keeps contacts with `industry IS NULL`. |
| Empty search in job title typeahead | Show nothing (require min 2 chars). |
| No contacts match any filter combination | Show empty state: "No contacts match your filters. Try adjusting your criteria." |
| Filter counts return 0 for all options | Show options dimmed with (0). User can still select them (in case counts are stale). |
| Campaign picker with large selection | Track selected IDs in a Set. Preserved across filter changes and pagination. Show selection count prominently. |
| SQLite test compatibility | Use `LIKE` instead of `ILIKE` (SQLite is case-insensitive by default for ASCII). Use `GROUP_CONCAT` if needed instead of PG `array_agg`. |

## Security Considerations

- **Multi-tenant isolation**: All filter queries include `WHERE tenant_id = :tenant_id`. The filter-counts endpoint must also enforce tenant isolation.
- **SQL injection**: All filter values go through parameterized queries. Comma-split values are each individually parameterized (never string-interpolated into SQL).
- **Input validation**: Enum filter values are validated against known enum lists on the backend. Unknown values are silently ignored (don't error, don't filter).
- **Campaign access**: `exclude_campaign_id` only works if the user has access to that campaign (existing campaign auth check).
- **Rate limiting**: Filter counts endpoint could be called frequently (on every filter change). 300ms debounce on frontend. Backend query is fast enough (<200ms) that no rate limiting is needed for current scale.
