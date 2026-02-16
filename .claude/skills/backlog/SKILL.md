---
name: backlog
description: Use when the user wants to add an idea to the backlog, review backlog priorities, or check what to work on next. Also use when starting any new feature work to check for existing items and dependency conflicts. Invoke with `/backlog` (show summary) or `/backlog <idea>` (intake new item).
---

# Backlog Management

You are acting as a Product Owner helping manage the leadgen-pipeline backlog.

## Step 1: Read Context

Read `BACKLOG.md` from the project root. Parse:
- All items with their IDs, statuses, MoSCoW categories, dependencies, effort, and optional `**Theme**` tags
- The "Next ID" counter at the top
- Any dependency chains (A depends on B)

Also read these files if they exist (skip silently if missing):
- `docs/PRODUCT_STRATEGY.md` — for strategic theme alignment
- `docs/TECHNICAL_STRATEGY.md` — for tech debt context and priorities

## Step 2: Route Based on Arguments

### If no arguments (just `/backlog`):

Show a concise summary:

1. **Counts**: Items per MoSCoW category and per status
2. **Dependency chains**: Show which items block others (e.g., "BL-002 blocks BL-003")
3. **Strategy Alignment** (if PRODUCT_STRATEGY.md exists):
   - Flag backlog items not tied to any strategic theme
   - Flag strategic themes with no backlog items
   - Highlight items aligned with Current Quarter Focus (priority boost)
4. **Tech Debt** (if TECHNICAL_STRATEGY.md exists):
   - List `[Tech Debt]` items and their severity
   - Flag any tech debt that blocks Must Have features (should be elevated to Must Have)
5. **Recommendation**: Suggest what to work on next based on:
   - Unblocked items (no pending dependencies)
   - Items already "In Progress" that should be finished first
   - MoSCoW priority (Must > Should > Could)
   - Strategy alignment (Current Quarter Focus items get priority boost)
   - `[Tech Debt]` items that block Must Have features get elevated
   - Effort (prefer smaller items when priorities are equal)

### If arguments provided (`/backlog <idea>`):

Run a PM intake process. Ask clarifying questions using AskUserQuestion (one round of 3-4 questions):

1. **Problem**: What problem does this solve? (free text)
2. **Scope**: What's the minimal viable scope? Suggest options based on the idea.
3. **Category**: MoSCoW classification — Must Have / Should Have / Could Have
4. **Dependencies**: Show existing backlog items and ask which ones this relates to or depends on. Include "None" as an option.

After getting answers:

1. Determine the next BL-ID from the "Next ID" counter in BACKLOG.md
2. Estimate effort (S/M/L/XL) based on scope description
3. If PRODUCT_STRATEGY.md exists, suggest a `**Theme**` from the defined strategic themes. Use AskUserQuestion with the available themes plus "None / New theme" as options. If no strategy file exists, skip this step.
4. Write the new item to BACKLOG.md in the appropriate MoSCoW section
5. Increment the "Next ID" counter
6. Report what was added, and flag any dependency implications (e.g., "This depends on BL-002 which isn't started yet")

## Item Format

```markdown
### BL-NNN: Title
**Status**: Idea | **Effort**: S/M/L/XL | **Spec**: `path` or —
**Depends on**: BL-NNN, BL-NNN | **Theme**: Theme Name

Brief description (3-5 lines).
```

Optional fields (on the same line as `**Depends on**`):
- `**Theme**`: Strategic theme from PRODUCT_STRATEGY.md (set by `/pm` or during intake)
- `**Source**`: Origin of the item, e.g., "Audit 2026-02-13" (set by `/em audit`)

These are backwards-compatible — existing items without these fields remain valid.

### Tech Debt Item Format

```markdown
### BL-NNN: [Tech Debt] Title
**Status**: Idea | **Effort**: S/M/L/XL | **Spec**: —
**Depends on**: — | **Source**: Audit YYYY-MM-DD

Description with specific file paths and what needs to change.
```

## Status Values

- **Idea** — Just captured, needs refinement
- **Refined** — Spec written, ready to start
- **In Progress** — Active development
- **Done** — Completed (move to Completed section with date)

## Rules

- Never delete or reorder existing items without user confirmation
- When adding a dependency, verify the target item exists
- If an idea clearly matches an existing backlog item, point that out instead of creating a duplicate
- Keep descriptions concise (3-5 lines max)
- Always update the "Next ID" counter when adding items
- `[Tech Debt]` items that block Must Have features should be recommended as Must Have priority
- Items aligned with Current Quarter Focus (from PRODUCT_STRATEGY.md) get a priority boost in recommendations
