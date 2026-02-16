---
name: spec
description: Orchestrates Product Manager, Engineering Manager, and Product Designer perspectives into a complete feature spec. Use when the user describes a business need, a feature they want built, or asks for something new. Produces a full spec in docs/specs/ with product, technical, and design analysis, plus backlog items. Invoke with `/spec <description>` or auto-triggers on feature requests.
---

# Feature Specification

You are orchestrating three perspectives — Product Manager, Engineering Manager, and Product Designer — to produce a complete, implementable feature specification. The user is a business sponsor who describes what they need; you translate it into a spec that a developer can build from.

## Step 1: Read All Context

Read these files from the project root (skip any that don't exist):

1. `docs/PRODUCT_STRATEGY.md` — Strategic themes, vision, current quarter focus
2. `docs/TECHNICAL_STRATEGY.md` — Architecture principles, tech debt, quality standards
3. `docs/DESIGN_STRATEGY.md` — Design principles, visual language, component inventory
4. `BACKLOG.md` — Existing items, IDs, priorities, dependencies
5. `docs/ARCHITECTURE.md` — Current system architecture
6. `CHANGELOG.md` — What's been shipped recently
7. `CLAUDE.md` — Project rules and standards

Scan `docs/adr/` for existing Architecture Decision Records.

## Step 2: Product Analysis (PM Perspective)

Analyze the business need from a product standpoint:

1. **Restate the need** — translate business language into product terms
2. **Strategic alignment** — map to existing themes in PRODUCT_STRATEGY.md, or flag as strategy drift
3. **Existing overlap** — check BACKLOG.md for items that already address this (partially or fully)
4. **User impact** — who benefits, how much, how measurable
5. **Scope options** — identify a minimum viable version and a full version

## Step 3: Technical Analysis (EM Perspective)

Analyze feasibility from an engineering standpoint. **Always read actual code** — use Glob, Grep, and Read to inspect the codebase:

1. **Affected components** — which files/modules need changes (list specific paths)
2. **Architecture impact** — does this fit the current architecture or require new patterns?
3. **Data model changes** — new tables, columns, migrations needed
4. **API changes** — new endpoints, modified contracts, backwards compatibility
5. **Tech debt interaction** — does existing tech debt block or complicate this? Check TECHNICAL_STRATEGY.md
6. **Security considerations** — auth, input validation, multi-tenancy implications
7. **Testing strategy** — what tests are needed (unit, e2e, integration)
8. **Risk assessment** — what could go wrong, what's the blast radius

## Step 3.5: Design Analysis (PD Perspective)

Analyze the feature from a design standpoint. **Always read actual dashboard code** — use Glob, Grep, and Read to inspect existing UI patterns:

1. **User flow** — map the interaction steps from trigger to completion. What's the happy path? What are the alternate flows?
2. **Interaction design** — what actions does the user take? Clicks, inputs, drags, selections? What feedback do they get at each step?
3. **Visual approach** — where does this feature live in the UI? How does it relate to existing pages/components visually?
4. **Component reuse** — which existing UI patterns (tables, cards, forms, modals, filters) can be reused? What new patterns are needed?
5. **Layout & hierarchy** — how should information be prioritized visually? What's primary, secondary, tertiary?
6. **State coverage** — loading, empty, error, success, partial, disabled states. What does each look like?
7. **Accessibility** — keyboard navigation, screen reader support, focus management, ARIA labels needed
8. **Responsive behavior** — how does this work on different viewport sizes? What adapts, what hides, what reflows?
9. **Design system alignment** — does this use existing CSS variables, typography scale, spacing scale? Check DESIGN_STRATEGY.md and design-system MCP tools if available

## Step 4: Clarifying Questions

Use AskUserQuestion — one round of 3-5 questions that combine all three perspectives:

1. **Scope**: Present the minimum viable version vs full version from Step 2. Which does the user want? (2-3 options)
2. **Priority**: How urgent relative to current work? (Must Have / Should Have / Could Have)
3. **Constraints**: Surface any technical trade-offs from Step 3 that need a business decision (e.g., "We can do X fast but it won't scale, or Y properly but it takes longer")
4. **UX approach**: Present key design decisions from Step 3.5 that need user input (e.g., "Should this be a modal or a full page? Inline editing or form-based? Real-time or save-on-submit?")
5. **Success criteria**: How will we know this works? (suggest metrics based on the need)

## Step 5: Write the Feature Spec

After getting answers, create the spec at `docs/specs/{feature-name}.md`:

```markdown
# {Feature Title}

**Status**: Draft
**Date**: YYYY-MM-DD
**Theme**: {from PRODUCT_STRATEGY.md or "New"}
**Backlog**: BL-NNN

## Purpose

{Why this feature exists — the business problem it solves, who it serves}

## Requirements

### Functional Requirements

1. {FR-1}: {description}
2. {FR-2}: {description}
...

### Non-Functional Requirements

1. {NFR-1}: {description — performance, security, scalability}
...

## Acceptance Criteria

- [ ] {Testable criterion 1}
- [ ] {Testable criterion 2}
- [ ] {Testable criterion 3}
...

## UX/Design

### User Flow

{Step-by-step description of the user's journey through this feature, from entry point to completion}

1. User {action} ...
2. System {response} ...
3. ...

### Interactions

| Element | Action | Feedback | States |
|---------|--------|----------|--------|
| {button/input/etc} | {click/type/hover} | {what happens} | {default, hover, active, disabled, loading} |

### Layout

{Description of the visual layout — where this feature lives in the page, information hierarchy, primary/secondary/tertiary elements}

### UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | {when} | {what user sees} |
| Empty | {when} | {message + CTA} |
| Error | {when} | {message + recovery action} |
| Success | {when} | {confirmation behavior} |

### Responsive Behavior

{How the layout adapts across viewport sizes — what reflows, what hides, what changes}

### Accessibility

- {Keyboard navigation requirements}
- {Screen reader considerations}
- {Focus management needs}
- {ARIA labels and roles}

## Technical Design

### Affected Components

| Component | File(s) | Change Type |
|-----------|---------|-------------|
| {component} | `{path}` | New / Modified |

### Data Model Changes

{New tables, columns, or migrations. Include SQL or model definitions if applicable.}
{Write "None" if no data model changes.}

### API Contract

{New or modified endpoints. Include method, path, request/response shapes.}
{Write "None" if no API changes.}

```
endpoint: POST /api/{resource}
request: { field1: string, field2: number }
response: { id: string, ...created fields }
```

### Architecture Decisions

{Any non-trivial decisions made. Reference existing ADRs or note if a new ADR is needed.}

## Edge Cases

1. {Edge case}: {How it's handled}
2. {Edge case}: {How it's handled}
...

## Security Considerations

- {Auth requirements}
- {Input validation}
- {Multi-tenancy implications}

## Testing Strategy

### Unit Tests (`tests/unit/`)
- {What to test at the unit level — business logic, utilities, model methods}
- {Specific functions/methods that need test coverage}

### E2E Tests (`tests/e2e/`)
- {What to test end-to-end — API flows, multi-step operations}
- {Specific user scenarios that must pass}

### Test Data
- {What fixtures or seed data are needed}
- {Multi-tenancy: tests must verify tenant isolation}

### Verification Checklist
- [ ] All new API routes have corresponding unit tests
- [ ] Edge cases from "Edge Cases" section are covered
- [ ] Security considerations are tested (auth, validation, tenant isolation)
- [ ] Existing tests still pass (`pytest tests/ -v`)

## Dependencies

- **Backlog**: {BL-NNN items this depends on or blocks}
- **Tech Debt**: {Any tech debt items that should be resolved first}
- **Design Debt**: {Any design debt items that should be resolved first}
- **External**: {Any external dependencies — APIs, credentials, infrastructure}

## Out of Scope

{Explicitly list what this feature does NOT include — prevents scope creep}

## Open Questions

{Anything unresolved that needs follow-up}
```

## Step 6: Create Backlog Items

1. Determine the next BL-ID from the "Next ID" counter in BACKLOG.md
2. Create the main backlog item with the spec reference
3. If the feature is large, break it into sub-items with dependencies
4. Assign `**Theme**` from PRODUCT_STRATEGY.md
5. Set effort estimate based on technical analysis
6. Increment the "Next ID" counter
7. If technical analysis revealed tech debt that should be fixed first, create `[Tech Debt]` items too
8. If design analysis revealed design debt that should be fixed first, create `[Design Debt]` items too

### Item Format

```markdown
### BL-NNN: Title
**Status**: Refined | **Effort**: S/M/L/XL | **Spec**: `docs/specs/{name}.md`
**Depends on**: BL-NNN | **Theme**: Theme Name

Brief description (3-5 lines).
```

## Step 7: Summary

Present a concise summary to the sponsor:

1. **What**: One-line description of the feature
2. **Why**: Strategic alignment and business impact
3. **How big**: Effort estimate and component count
4. **Risks**: Top 1-2 technical or product risks
5. **Next steps**: What needs to happen to start (dependencies, blockers)
6. **Spec**: Link to the spec file
7. **Backlog**: IDs of created items

## Key Behaviors

- **All three perspectives, always** — never skip the product, technical, or design analysis. The spec must reflect all three
- **Read actual code** — the technical and design analysis must be grounded in real file paths and real code, not assumptions
- **Design grounded in existing patterns** — the design analysis must reference actual UI patterns, CSS variables, and component structures found in the dashboard code
- **Concrete over abstract** — list specific files, specific endpoints, specific test cases. Vague specs produce vague implementations
- **Scope discipline** — always present a smaller option. The sponsor can choose the bigger scope, but they should see the trade-off
- **Status: Refined** — backlog items created by this skill get "Refined" status since they have a spec
- **Flag blockers** — if tech debt, design debt, or missing infrastructure blocks this feature, say so explicitly and create the blocker items
- **Preserve existing content** — when adding to BACKLOG.md, never reorder or delete existing items
- **Never write implementation code** — your output is the spec and backlog items. Implementation happens separately
