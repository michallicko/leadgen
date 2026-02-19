# Entity Selection & Bulk Actions — Tasks

## Implementation Tasks

### Phase 1: Data Model (migration + models)

- [ ] **T-1**: Write migration `005_multi_tag.sql` — create `contact_tag_assignments` and `company_tag_assignments` junction tables with indexes — `migrations/005_multi_tag.sql`
- [ ] **T-2**: Add SQLAlchemy models for junction tables — `api/models.py`
- [ ] **T-3**: Write data migration script to copy `contacts.tag_id` and `companies.tag_id` to junction tables — `migrations/005_multi_tag.sql` (part of same migration)
- [ ] **T-4**: Update `GET /api/contacts` and `GET /api/companies` to join on junction tables for tag display (return array of tag names instead of single) — `api/routes/contact_routes.py`, `api/routes/company_routes.py`
- [ ] **T-5**: Update `GET /api/tags` to return tag objects with IDs (not just names) — `api/routes/tag_routes.py`
- [ ] **T-6**: Add `POST /api/tags` endpoint for creating new tags — `api/routes/tag_routes.py`

### Phase 2: Bulk API Endpoints

- [ ] **T-7**: Create `api/routes/bulk_routes.py` with `POST /api/bulk/add-tags` — accepts `{entity_type, ids|filters, tag_ids}`, inserts junction rows — `api/routes/bulk_routes.py`
- [ ] **T-8**: Add `POST /api/bulk/remove-tags` — deletes junction rows for given entities + tags — `api/routes/bulk_routes.py`
- [ ] **T-9**: Add `POST /api/bulk/assign-campaign` — adds entities to campaign (reuses existing campaign_contacts insert logic) — `api/routes/bulk_routes.py`
- [ ] **T-10**: Add `POST /api/contacts/matching-count` and `POST /api/companies/matching-count` — returns count of records matching given filters — `api/routes/contact_routes.py`, `api/routes/company_routes.py`
- [ ] **T-11**: Register bulk blueprint in Flask app — `api/__init__.py`

### Phase 3: DataTable Selection

- [ ] **T-12**: Add selection props to DataTable — `selectable?: boolean`, `selectedIds?: Set<string>`, `onSelectionChange?: (ids: Set<string>, mode: 'explicit' | 'all-matching') => void` — `frontend/src/components/ui/DataTable.tsx`
- [ ] **T-13**: Render checkbox column (first column) when `selectable=true` — header checkbox + row checkboxes — `DataTable.tsx`
- [ ] **T-14**: Implement shift-click range selection — track `lastClickedIndex`, select range on shift+click — `DataTable.tsx`
- [ ] **T-15**: Implement "Select all X matching" banner — appears after header select-all, calls matching-count endpoint, switches to filter mode — `DataTable.tsx`
- [ ] **T-16**: Visual row highlighting for selected rows (blue-50 background) — `DataTable.tsx`

### Phase 4: SelectionActionBar + Pickers

- [ ] **T-17**: Build `SelectionActionBar` component — fixed bottom bar with count, action buttons, deselect-all, slide animation — `frontend/src/components/ui/SelectionActionBar.tsx`
- [ ] **T-18**: Build `CampaignPicker` component — modal listing campaigns, select one, confirm — `frontend/src/components/ui/CampaignPicker.tsx`
- [ ] **T-19**: Build `TagPicker` component — popover with multi-select tag list + "Create new" input — `frontend/src/components/ui/TagPicker.tsx`
- [ ] **T-20**: Add React Query mutations for bulk endpoints — `frontend/src/api/mutations/useBulkActions.ts`

### Phase 5: Page Integration

- [ ] **T-21**: Wire selection + action bar into ContactsPage — enable `selectable`, pass filters for server-side select-all, render action bar with campaign + tag actions — `frontend/src/pages/contacts/ContactsPage.tsx`
- [ ] **T-22**: Wire selection + action bar into CompaniesPage — same pattern as contacts — `frontend/src/pages/companies/CompaniesPage.tsx`
- [ ] **T-23**: Wire selection into Campaign ContactsTab — enable selection, action bar with "Remove from Campaign" + "Add Tags" — `frontend/src/pages/campaigns/tabs/ContactsTab.tsx`
- [ ] **T-24**: Update tag display in both tables to show multiple tags (comma-separated badges or pill list) — `ContactsPage.tsx`, `CompaniesPage.tsx`
- [ ] **T-25**: Update tag filter dropdowns to work with multi-tag model (filter contacts that have ANY of selected tags) — `ContactsPage.tsx`, `CompaniesPage.tsx`

### Phase 6: Polish + Docs

- [ ] **T-26**: Keyboard support — Escape to deselect, proper focus management — `DataTable.tsx`, `SelectionActionBar.tsx`
- [ ] **T-27**: Update ARCHITECTURE.md with bulk actions section and multi-tag model
- [ ] **T-28**: Update CHANGELOG.md

## Traceability Matrix

| AC | Task(s) | Test(s) |
|----|---------|---------|
| AC-1 (click checkbox → bar appears) | T-12, T-13, T-16, T-17 | `test_unit_datatable_selection`, `test_e2e_contact_select_one` |
| AC-2 (shift-click range) | T-14 | `test_unit_shift_click_range`, `test_e2e_contact_shift_select` |
| AC-3 (header checkbox → all loaded) | T-13, T-15 | `test_unit_select_all_loaded`, `test_e2e_header_checkbox` |
| AC-4 (select all matching filters) | T-10, T-15 | `test_unit_matching_count_endpoint`, `test_e2e_select_all_matching` |
| AC-5 (assign to campaign) | T-9, T-18, T-20, T-21 | `test_unit_bulk_assign_campaign`, `test_e2e_bulk_assign_campaign` |
| AC-6 (add tags to companies) | T-1, T-2, T-7, T-19, T-20, T-22 | `test_unit_bulk_add_tags`, `test_e2e_bulk_add_tags_companies` |
| AC-7 (filter-based tag all matching) | T-7, T-10, T-15 | `test_unit_bulk_add_tags_filters`, `test_e2e_select_all_add_tags` |
| AC-8 (deselect all / Escape) | T-17, T-26 | `test_unit_deselect_all`, `test_e2e_deselect_escape` |
| AC-9 (additive tags) | T-1, T-7 | `test_unit_tags_additive` |
| AC-10 (campaign contacts tab) | T-23 | `test_e2e_campaign_contacts_selection` |

## Testing Strategy

### Unit Tests (`tests/unit/`)

- **Migration**: Test junction table creation, data migration from FK to junction, unique constraints
- **Bulk endpoints**: Test `add-tags` (explicit IDs + filter mode), `remove-tags`, `assign-campaign` — verify tenant isolation, dedup, error cases
- **Matching count**: Test count endpoint with various filter combinations
- **Tag model**: Test multi-tag queries (contacts with tag X AND Y, contacts with ANY of tags)

### E2E Tests (`tests/e2e/`)

- **Selection flow**: Navigate to contacts, click checkbox, verify bar appears with count
- **Shift-click**: Select row 1, shift-click row 5, verify rows 1-5 selected
- **Select all matching**: Apply filter, select all loaded, click "select all X matching", verify count
- **Bulk assign campaign**: Select contacts, click assign, pick campaign, verify contacts appear in campaign
- **Bulk add tags**: Select companies, click add tags, pick tags, verify tags appear in table
- **Deselect**: Select rows, press Escape, verify cleared
- **Campaign contacts tab**: Select contacts in campaign, remove, verify removed

### Test Data

- Seed: at least 20 contacts with varied tags/owners, 2 campaigns, 5 tags
- Multi-tenancy: verify bulk actions don't leak across tenants (seed a second tenant, attempt cross-tenant bulk op)

## Verification Checklist

- [ ] All ACs from requirements.md have corresponding tests
- [ ] Multi-tag migration runs clean on staging DB (test against `leadgen_staging`)
- [ ] Bulk operations handle 1,000+ records without timeout
- [ ] Edge cases: duplicate tag assignment, already-in-campaign contacts, empty selection
- [ ] Security: tenant isolation tested for all bulk endpoints
- [ ] Existing tests still pass (`make test-all`)
- [ ] No breaking changes to existing tag filter behavior
