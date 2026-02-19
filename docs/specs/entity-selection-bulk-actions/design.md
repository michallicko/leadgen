# Entity Selection & Bulk Actions — Design

## Affected Components

| Component | File(s) | Change Type |
|-----------|---------|-------------|
| DataTable | `frontend/src/components/ui/DataTable.tsx` | Modified — add selection props, checkbox column, shift-click, select-all banner |
| SelectionActionBar | `frontend/src/components/ui/SelectionActionBar.tsx` | New — floating bottom bar with count + actions |
| TagPicker | `frontend/src/components/ui/TagPicker.tsx` | New — multi-tag selector modal/popover |
| CampaignPicker | `frontend/src/components/ui/CampaignPicker.tsx` | New — campaign selector modal (simpler than existing ContactPicker) |
| ContactsPage | `frontend/src/pages/contacts/ContactsPage.tsx` | Modified — enable selection, wire action bar |
| CompaniesPage | `frontend/src/pages/companies/CompaniesPage.tsx` | Modified — enable selection, wire action bar |
| ContactsTab (Campaign) | `frontend/src/pages/campaigns/tabs/ContactsTab.tsx` | Modified — enable selection for bulk remove/retag |
| Tag model | `api/models.py` | Modified — new junction tables |
| Bulk routes | `api/routes/bulk_routes.py` | New — bulk action endpoints |
| Tag routes | `api/routes/tag_routes.py` | Modified — CRUD for tag assignments |
| Migration | `migrations/005_multi_tag.sql` | New — junction tables + data migration |

## Data Model Changes

### New tables

```sql
-- Junction table for contact ↔ tag (many-to-many)
CREATE TABLE contact_tag_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(contact_id, tag_id)
);
CREATE INDEX idx_cta_contact ON contact_tag_assignments(contact_id);
CREATE INDEX idx_cta_tag ON contact_tag_assignments(tag_id);
CREATE INDEX idx_cta_tenant ON contact_tag_assignments(tenant_id);

-- Junction table for company ↔ tag (many-to-many)
CREATE TABLE company_tag_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(company_id, tag_id)
);
CREATE INDEX idx_cota_company ON company_tag_assignments(company_id);
CREATE INDEX idx_cota_tag ON company_tag_assignments(tag_id);
CREATE INDEX idx_cota_tenant ON company_tag_assignments(tenant_id);
```

### Data migration

```sql
-- Migrate existing single-tag FKs to junction tables
INSERT INTO contact_tag_assignments (tenant_id, contact_id, tag_id)
SELECT tenant_id, id, tag_id FROM contacts WHERE tag_id IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO company_tag_assignments (tenant_id, company_id, tag_id)
SELECT tenant_id, id, tag_id FROM companies WHERE tag_id IS NOT NULL
ON CONFLICT DO NOTHING;
```

The old `tag_id` FK columns on contacts/companies are kept for backwards compatibility during transition but no longer written to. Removal is a future cleanup task.

## API Contract

### Bulk actions

```
POST /api/bulk/assign-campaign
Authorization: Bearer {token}
X-Namespace: {slug}

Request (explicit IDs):
{
  "entity_type": "contact" | "company",
  "ids": ["uuid1", "uuid2", ...],
  "campaign_id": "uuid"
}

Request (filter-based, for select-all):
{
  "entity_type": "contact" | "company",
  "filters": { "tag_name": "outreach", "owner_name": "Michal", ... },
  "campaign_id": "uuid"
}

Response:
{ "affected": 42, "errors": [] }
```

```
POST /api/bulk/add-tags
Authorization: Bearer {token}
X-Namespace: {slug}

Request (explicit IDs):
{
  "entity_type": "contact" | "company",
  "ids": ["uuid1", "uuid2", ...],
  "tag_ids": ["tag-uuid1", "tag-uuid2"]
}

Request (filter-based):
{
  "entity_type": "contact" | "company",
  "filters": { ... },
  "tag_ids": ["tag-uuid1", "tag-uuid2"]
}

Response:
{ "affected": 42, "new_assignments": 38, "already_tagged": 4, "errors": [] }
```

```
POST /api/bulk/remove-tags
Authorization: Bearer {token}
X-Namespace: {slug}

Request: same shape as add-tags
Response: { "affected": 42, "removed": 40, "not_found": 2, "errors": [] }
```

### Matching IDs (for count display)

```
POST /api/contacts/matching-count
POST /api/companies/matching-count

Request: { "filters": { "tag_name": "outreach", ... } }
Response: { "count": 1234 }
```

### Tag CRUD (updated)

```
GET /api/tags
Response: { "tags": [{ "id": "uuid", "name": "outreach" }, ...], "owners": [...] }

POST /api/tags
Request: { "name": "new-tag" }
Response: { "id": "uuid", "name": "new-tag" }

GET /api/contacts/{id}/tags
Response: { "tags": [{ "id": "uuid", "name": "outreach" }, ...] }
```

## UX/Design

### User Flow

1. User is on Contacts page with filters applied (e.g., tag="outreach", owner="Michal")
2. Clicks checkbox on row → row highlights, floating action bar slides up: "1 selected | Assign to Campaign | Add Tags | Deselect All"
3. Shift-clicks another row 10 rows below → range selected, bar updates: "11 selected"
4. Clicks header checkbox → all loaded rows selected, banner: "52 selected. Select all 1,234 matching filters?"
5. Clicks "Select all 1,234" → bar updates: "All 1,234 matching filters"
6. Clicks "Add Tags" → tag picker opens (multi-select dropdown/popover listing existing tags + "Create new" input)
7. Selects 2 tags, confirms → API call with filters (not IDs), toast: "2 tags added to 1,234 contacts"
8. Tags column in table updates on refetch

### Interactions

| Element | Action | Feedback | States |
|---------|--------|----------|--------|
| Row checkbox | Click | Row highlights (blue-50 bg), action bar appears | unchecked, checked |
| Header checkbox | Click | All loaded rows highlight, select-all banner appears | unchecked, checked (partial if some selected), checked (all) |
| Select-all banner | Click "Select all X" | Count updates to total, mode switches to filter-based | hidden, visible |
| Floating action bar | Appears on first selection | Slide-up animation (200ms ease) | hidden, visible |
| "Assign to Campaign" button | Click | Campaign picker modal opens | default, loading |
| "Add Tags" button | Click | Tag picker popover opens below button | default, loading |
| "Deselect All" button | Click or Escape key | All selections clear, bar slides away | default |
| Campaign picker | Select + confirm | API call, success toast, selection cleared | selecting, confirming, success, error |
| Tag picker | Select tags + confirm | API call, success toast, table refetches | selecting, confirming, success, error |

### Layout

The floating action bar is a `fixed` positioned bar at the bottom center of the viewport:

```
┌─────────────────────────────────────────────────┐
│ [Table with checkbox column + rows]              │
│ ☑ John Doe    VP Sales    Acme Corp    outreach  │
│ ☑ Jane Smith  CTO         Beta Inc     priority  │
│ ☐ Bob Wilson  CEO         Gamma Ltd    —         │
│ ☑ ...                                            │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ ✓ 3 selected  │ Campaign │ Tags │ ✕ All │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

Bar specs:
- `position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%)`
- Background: `var(--surface-primary)` with `box-shadow` elevation
- Border-radius: `var(--radius-lg)`
- Padding: `8px 16px`
- Z-index above table, below modals
- Max-width: fits content, min-width: ~300px

### UI States

| State | Condition | Display |
|-------|-----------|---------|
| No selection | 0 rows selected | No action bar, no checkbox highlights |
| Partial selection | 1+ rows selected | Action bar visible, header checkbox shows indeterminate (—) |
| All loaded selected | All visible rows checked | Header checkbox checked, "Select all X matching?" banner |
| All matching selected | Server-side select-all active | Count shows "All X matching filters", actions use filter mode |
| Action in progress | API call running | Action button shows spinner, other buttons disabled |
| Action success | API returns | Toast notification, selection cleared, table data refetched |
| Action error | API error | Toast error with message, selection preserved |

### Responsive Behavior

- Action bar is centered and responsive (flexbox, wraps on narrow screens)
- On mobile widths (<640px): action buttons stack vertically, bar takes full width
- Checkboxes remain usable at all sizes (44px touch target minimum)

### Accessibility

- Checkbox column: proper `<input type="checkbox">` with `aria-label="Select {name}"`
- Header checkbox: `aria-label="Select all"` + `aria-checked="mixed"` for indeterminate state
- Action bar: `role="toolbar"` with `aria-label="Bulk actions for X selected items"`
- Escape key: clears selection (KeyboardEvent listener)
- Tab order: checkboxes → row content → action bar buttons
- Screen reader: action bar announces "X items selected. Actions available: Assign to Campaign, Add Tags, Deselect All"

## Architecture Decisions

- **Filter-based bulk operations**: Instead of sending thousands of IDs, actions accept the same filter criteria the list view uses. The server re-applies filters to find matching records. This scales to any dataset size.
- **Separate junction tables per entity type**: `contact_tag_assignments` and `company_tag_assignments` instead of a polymorphic `entity_tag_assignments`. Avoids polymorphic FK patterns, allows proper FK constraints, simpler queries.
- **Selection state in component**: Selection is managed by DataTable internally via `useState` (or controlled via props). Not persisted to URL/localStorage — navigating away clears selection.
- **Backwards-compatible tag migration**: Old `tag_id` FK columns kept (read-only) during transition. New code reads/writes junction tables only. Future cleanup task removes FK columns.

## Edge Cases

1. **User selects all, then scrolls and loads more rows**: New rows are NOT auto-selected when in "loaded" mode. In "all matching" mode, they're logically included via filters.
2. **User selects all matching, then changes a filter**: Selection clears (filter criteria changed = previous selection invalid).
3. **Bulk assign to campaign with duplicates**: Server deduplicates — contacts already in the campaign are skipped, count reflects only new additions.
4. **Tag added that entity already has**: Junction table UNIQUE constraint prevents duplicates; `ON CONFLICT DO NOTHING` in bulk insert.
5. **Concurrent bulk operations**: Each operation runs in a transaction. No explicit locking — UNIQUE constraints handle races.
6. **Campaign contacts tab selection**: "Remove from campaign" appears instead of "Assign to Campaign". Uses `DELETE /api/campaigns/{id}/contacts` with selected IDs.

## Security Considerations

- All bulk endpoints enforce tenant isolation via `tenant_id` filter (same pattern as existing routes)
- Filter-based operations re-validate filters server-side — client filter params are not trusted
- Bulk operations cap at 10,000 records per request (server enforced) to prevent abuse
- Tag creation (via "Create new" in picker) requires authenticated user, tenant-scoped
- No CSRF concern — JWT auth, no cookies
