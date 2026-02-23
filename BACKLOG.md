# Backlog — DEPRECATED

> **This file is deprecated.** The backlog is now managed via individual JSON files.

## New Location
- **Dashboard**: `docs/backlog/index.html`
- **Items**: `docs/backlog/items/BL-XXX.json` (one file per item)
- **Config**: `docs/backlog/config.json` (manifest of all item IDs)

## Adding a New Item
1. Create `docs/backlog/items/BL-XXX.json` with the item data
2. Append the ID to `docs/backlog/config.json` → `items` array
3. That's it — the dashboard loads dynamically

## Item JSON Format
```json
{
  "id": "BL-XXX",
  "title": "Feature name",
  "priority": "Must Have|Should Have|Could Have",
  "effort": "S|M|L|XL",
  "status": "Idea|Spec'd|Building|PR Open|In Review|Merged|Done",
  "theme": "Playbook Core|Outreach Engine|...",
  "sprint": "Sprint 1|Sprint 2|Sprint 3|Backlog",
  "depends_on": [],
  "assignee": null,
  "spec_file": "docs/specs/xxx.md",
  "description": "Short description",
  "created": "2026-02-23",
  "updated": "2026-02-23"
}
```
