---
name: roadmap
description: Regenerate the dashboard/roadmap.html page from current BACKLOG.md and PRODUCT_STRATEGY.md data. Use when backlog items change, new items are added, or the user wants an updated roadmap page. Invoke with `/roadmap`.
---

# Roadmap Page Generator

You regenerate `dashboard/roadmap.html` — a static HTML page showing the project backlog and quarterly roadmap.

## Step 1: Read Source Data

Read these files from the project root:

1. `BACKLOG.md` — All backlog items with IDs, statuses, MoSCoW categories, dependencies, effort, themes
2. `docs/PRODUCT_STRATEGY.md` — Vision, strategic themes, current quarter focus, success metrics

Parse from BACKLOG.md:
- Every item: ID, title, status, effort, MoSCoW category, dependencies, theme, description (first sentence)
- Counts: total items, per MoSCoW, per status, per theme
- Dependency chains (A depends on B)
- Unblocked items (no dependencies or all dependencies done)

Parse from PRODUCT_STRATEGY.md:
- Current Quarter Focus (top 3 priorities)
- Strategic theme names and descriptions
- Vision statement (for page subtitle)

## Step 2: Read Existing Page

Read `dashboard/roadmap.html` to understand the current structure, styling, and layout patterns. The page uses the project's dark design system (Lexend Deca + Work Sans, purple/cyan accents).

## Step 3: Regenerate the Page

Rewrite `dashboard/roadmap.html` with updated data. Preserve the existing:
- **CSS** — All styles, variables, animations, responsive rules
- **Structure** — 3 tabs (Quarterly Roadmap, Full Backlog, Dependencies)
- **Design** — Dark theme, card styles, theme color coding, hover effects

Update with fresh data:
- **Stats row** — Correct counts for total, done, in progress, per theme
- **Q1 Focus cards** — From PRODUCT_STRATEGY.md Current Quarter Focus
- **Timeline swim lanes** — Arrange items across months based on priority, dependencies, effort
- **Backlog tab** — All items grouped by MoSCoW, with correct badges and dependency info
- **Dependencies tab** — Updated dependency chains and unblocked items list
- **Generated timestamp** — Current date

### Theme Color Mapping

| Theme | CSS Class | Color Variable |
|-------|-----------|---------------|
| Contact Intelligence | `ci` | `--theme-ci` (cyan) |
| Platform Foundation | `pf` | `--theme-pf` (purple) |
| Outreach Engine | `oe` | `--theme-oe` (amber) |
| Closed-Loop Analytics | `cla` | `--theme-cla` (green) |

### Status Badge Mapping

| Status | CSS Class |
|--------|-----------|
| Done | `status-done` |
| In Progress | `status-progress` |
| Refined | `status-refined` |
| Idea | `status-idea` |
| Phase 1 Done | `status-done` |

### Effort Badge Mapping

| Effort | CSS Class |
|--------|-----------|
| S | `effort-s` (green) |
| M | `effort-m` (cyan) |
| L | `effort-l` (amber) |
| XL | `effort-xl` (red) |

### Timeline Layout Rules

- 6-month view starting from the current month
- 4 swim lanes: Platform, Contact Intel, Integrations, Analytics
- Place items in timeline based on: dependencies (blocked items come after their blockers), effort (S=1mo, M=1-2mo, L=2-3mo, XL=3+mo), MoSCoW priority
- Current month column gets the `current-month` class
- Done items get `done` class (strikethrough, reduced opacity)

## Step 4: Report

After regenerating, report:
- Total items rendered
- Any items that couldn't be categorized (missing theme or invalid data)
- Date of generation

Do NOT commit the file — the user will commit when ready.
