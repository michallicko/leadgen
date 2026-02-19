# Entity Selection & Bulk Actions — Requirements

**Status**: Draft
**Date**: 2026-02-19
**Theme**: Platform Foundation
**Backlog**: BL-045

## Purpose

Users managing hundreds or thousands of contacts and companies need to perform operations in bulk — assign to campaigns, add tags, triage. Currently every action is one-at-a-time. This feature adds row selection to the DataTable component (reusable across all entity lists) with a floating action bar for bulk operations.

## Functional Requirements

1. **FR-1**: DataTable supports optional row selection via checkboxes (first column)
2. **FR-2**: Individual row selection by clicking the checkbox
3. **FR-3**: Shift-click selects a contiguous range of rows between last-clicked and current
4. **FR-4**: Header checkbox toggles all currently loaded (visible) rows
5. **FR-5**: "Select all X matching" banner appears after header-checkbox select-all, allowing server-side full selection of all records matching current filters
6. **FR-6**: Selection count badge displays in the floating action bar ("12 selected" or "All 1,234 matching filters")
7. **FR-7**: Floating action bar slides up from the bottom when any rows are selected, showing count + action buttons + deselect-all
8. **FR-8**: "Assign to Campaign" action opens a campaign picker and adds selected entities to the chosen campaign
9. **FR-9**: "Add Tags" action opens a tag picker and adds chosen tags to all selected entities (multi-tag, additive — does not remove existing tags)
10. **FR-10**: "Deselect All" button clears selection and hides the action bar
11. **FR-11**: Tag data model upgraded from single FK (`tag_id`) to many-to-many junction tables
12. **FR-12**: Selection is reusable — Contacts page, Companies page, and Campaign contacts tab all use the same DataTable selection capability
13. **FR-13**: Bulk action endpoints accept either explicit IDs or filter criteria (for server-side select-all without transmitting thousands of IDs)

## Non-Functional Requirements

1. **NFR-1**: Selection state must not degrade virtual scroll performance (41px row height, 20-row buffer)
2. **NFR-2**: Server-side select-all must handle 10,000+ records without timeout (<5s response)
3. **NFR-3**: Bulk operations must be tenant-isolated — actions only affect records belonging to the current tenant
4. **NFR-4**: Action bar must be keyboard-accessible (Escape to deselect, Tab through actions)

## Acceptance Criteria

- **AC-1**: Given the Contacts page with 50 loaded contacts, when I click a row checkbox, then that row is visually highlighted and the floating action bar appears showing "1 selected"
- **AC-2**: Given 3 selected contacts, when I shift-click a row 5 rows below the last selection, then all 5 rows between are selected and the count shows "8 selected"
- **AC-3**: Given the header checkbox is unchecked, when I click it, then all loaded rows are selected and a banner says "All loaded selected. Select all X matching filters?"
- **AC-4**: Given I click "Select all X matching filters", when the server responds, then the count updates to "All X matching filters" and actions operate on filter criteria instead of explicit IDs
- **AC-5**: Given 10 contacts selected, when I click "Assign to Campaign" and pick a campaign, then all 10 are added to that campaign and a success toast appears
- **AC-6**: Given 5 companies selected, when I click "Add Tags" and choose 2 tags, then both tags are added to all 5 companies (existing tags preserved) and the tag column updates
- **AC-7**: Given "All 1,234 matching filters" is active, when I click "Add Tags", then the server applies the tag to all 1,234 records using filter criteria (not IDs)
- **AC-8**: Given the floating action bar is visible, when I click "Deselect All" or press Escape, then all selections clear and the bar slides away
- **AC-9**: Given a contact has tags ["outreach", "priority"], when I bulk-add tag "vip", then the contact has tags ["outreach", "priority", "vip"]
- **AC-10**: Given the Campaign contacts tab, when I enable selection mode, then checkboxes appear and I can select campaign contacts for bulk removal or re-tagging

## Out of Scope

- Bulk delete (destructive — separate feature with extra safeguards)
- Bulk field editing (change status, owner, etc. — future extension)
- Drag-and-drop reordering
- Saved selections / named lists
- Export selected to CSV (future BL-039/040)
- Trigger enrichment on selected (future BL-014)

## Dependencies

- **Backlog**: None — this is foundational infrastructure
- **Tech Debt**: None blocking
- **External**: None

## Open Questions

None — all clarified during intake.
