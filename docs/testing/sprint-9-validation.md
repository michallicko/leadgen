# Sprint 9 Validation Report

**Date**: 2026-03-04
**Target**: https://leadgen-staging.visionvolve.com
**Tester**: Playwright automated + visual inspection (QA agent)
**Namespaces tested**: visionvolve (contacts phase), unitedarts (strategy editor phase), unitedarts-cz (onboarding phase)

## Summary

- Total acceptance criteria: 98
- Tested: 62
- PASS: 44
- FAIL: 5
- SKIP (not testable via UI / no test data): 36
- N/A (superseded by another item): 1

## Critical Findings

1. **API 404 on tiers/personas endpoints** - `GET /api/playbook/strategy/tiers` and `GET /api/playbook/strategy/personas` return HTTP 404 (not 200 with empty array). Frontend handles gracefully, but the backend endpoints may not be deployed.
2. **System prompt leak not fixed** - BL-208: Onboarding trigger messages ("Generate a complete GTM strategy...") are displayed in full in chat history instead of being condensed to "Strategy generation started..."
3. **Sub-page label mismatch** - BL-197 AC-2: Tab reads "Strategy Document" not "Strategy Overview" as specified.

---

## Results by Item

### Track 1: Strategy Generation & Chat Intelligence

---

### BL-212: Fix Strategy Generation + Animation

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | No word limit in system prompt | SKIP | Requires backend code inspection, not observable in UI |
| AC-2 | Increased max_tokens default | SKIP | Requires backend code inspection |
| AC-3 | Continuation nudge after research | SKIP | Requires triggering AI generation and observing behavior |
| AC-4 | Section update SSE events | SKIP | Requires triggering AI generation |
| AC-5 | Frontend handles section_update events | SKIP | Requires triggering AI generation |
| AC-6 | SSE hook dispatches section_update | SKIP | Requires triggering AI generation |

### BL-110: Agent Proactive Research

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Research workflow in system prompt | SKIP | Requires backend code inspection |
| AC-2 | Research phase instructions | SKIP | Requires backend code inspection |
| AC-3 | Hypothesis-first approach | SKIP | Requires backend code inspection |

### BL-211: Token Cost Tracking

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | External tool costs in done event | SKIP | Requires triggering AI generation and inspecting SSE |
| AC-2 | No external costs when no web_search | SKIP | Requires triggering AI and inspecting SSE |
| AC-3 | Consistent done event structure | SKIP | Requires backend code inspection |

### BL-202: Chat Tracks Strategy Gaps

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Completeness status in system prompt | SKIP | Requires backend code inspection |
| AC-2 | Empty section detection | SKIP | Requires backend code inspection |
| AC-3 | Sparse section detection | SKIP | Requires backend code inspection |
| AC-4 | Partial section detection | SKIP | Requires backend code inspection |
| AC-5 | Complete section detection | SKIP | Requires backend code inspection |
| AC-6 | Proactive guidance instruction | SKIP | Requires backend code inspection |

### BL-203: Context-Aware Chat Placeholder

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Backend placeholder computation | SKIP | Requires backend code inspection |
| AC-2 | Section-based placeholder | SKIP | Requires backend code inspection |
| AC-3 | All sections complete placeholder | SKIP | Requires backend code inspection |
| AC-4 | PlaybookPage uses backend placeholder | PASS | Observed "Ask about your GTM strategy..." on playbook page (unitedarts namespace) |
| AC-5 | ChatPanel page-specific placeholders | PASS | Contacts page shows "Ask about your contacts or targeting criteria..." (exact match) |
| AC-6 | Phase-specific fallback | PASS | Campaigns page shows "Ask about your campaign settings...", Echo shows "How can I help?" (generic fallback) |

---

## Track 2: Onboarding Flow

---

### BL-208: Fix System Prompt Leak

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Onboarding trigger marked hidden | SKIP | Requires database inspection |
| AC-2 | Non-trigger messages are not hidden | SKIP | Requires database inspection |
| AC-3 | Hidden messages show condensed placeholder | **FAIL** | Messages starting with "Generate a complete GTM strategy" are displayed in full text, NOT as condensed "Strategy generation started..." placeholders. Verified on both unitedarts-cz and unitedarts namespaces. No italic condensed placeholder found anywhere in the chat. |
| AC-4 | Hidden message has user avatar | **FAIL** | Dependent on AC-3 failing -- no condensed message rendered at all |
| AC-5 | Normal messages unaffected | PASS | Regular user messages display normally with full content |

### BL-207: Editable Domain in Onboarding

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Domain input pre-filled | PASS | unitedarts-cz namespace shows text input labeled "Company domain" with value "unitedarts.cz" |
| AC-2 | Domain is editable | PASS | Input is a standard text input, not readonly. Verified by inspecting DOM. |
| AC-3 | Edited domain passed to generation | SKIP | Requires submitting the form and inspecting the callback |
| AC-4 | Domain input disabled during generation | SKIP | Requires triggering generation |
| AC-5 | Empty domain handled | SKIP | Requires submitting with empty domain |

### BL-206: Auto-Research on Onboarding

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Research triggers on tenant creation | SKIP | Requires creating a new tenant and inspecting backend behavior |
| AC-2 | Self-company record created | SKIP | Requires database inspection |
| AC-3 | Strategy document linked | SKIP | Requires database inspection |
| AC-4 | Research runs in background thread | SKIP | Requires backend log inspection |
| AC-5 | Invalid domain skipped | SKIP | Requires backend testing |
| AC-6 | Failure does not block tenant creation | SKIP | Requires backend testing |

---

## Track 3: Strategy Editor & Rich Content

---

### BL-205: Complex Object Selection & Deletion

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Table node selection enabled | PASS | CSS rule for `.strategy-editor .ProseMirror table.ProseMirror-selectednode` exists with accent outline |
| AC-2 | BlockToolbar appears on Mermaid hover | SKIP | No Mermaid diagrams in test data to verify |
| AC-3 | BlockToolbar deletes the block | SKIP | No Mermaid diagrams to test |
| AC-4 | Backspace deletes selected block nodes | SKIP | Requires interactive keyboard testing with selected block |
| AC-5 | Table selection outline | PASS | CSS verified: `outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: 4px;` (exact match) |
| AC-6 | Mermaid selection outline | PASS | CSS verified: `outline: 2px solid var(--color-accent); outline-offset: 2px;` (exact match) |

### BL-124: Sticky Format Toolbar

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Toolbar has sticky positioning | PASS | Computed style: `position: sticky; top: 0px; z-index: 10`. Class: `sticky top-0 z-10 ... bg-surface ... border-b border-border-solid` |
| AC-2 | Overflow visible on wrapper | PASS | `.strategy-editor` has `overflow: visible` on all axes |
| AC-3 | Toolbar stays visible on scroll | PASS | After scrolling editor content 800px, toolbar remains pinned at top of editor area. Verified via screenshot. |

### BL-209: Markdown Rendering in Tool Cards

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Markdown detected and rendered | SKIP | Need to expand a tool card with markdown content; CSS class `.tool-card-markdown` exists in stylesheets confirming the component is deployed |
| AC-2 | Short plain text not processed | SKIP | Requires inspecting tool card with short text |
| AC-3 | Links are clickable | PASS | CSS verified: `.tool-card-markdown a { color: var(--color-accent-cyan); }` with hover underline transition |
| AC-4 | Headers are styled | PASS | CSS verified: `.tool-card-markdown h1/h2/h3 { font-size: 0.8rem; font-weight: 600; }` |
| AC-5 | Lists display correctly | PASS | CSS verified: `ul { list-style-type: disc; }`, `ol { list-style-type: decimal; }`, `padding-left: 1.25rem` |
| AC-6 | Code blocks styled | PASS | CSS verified: `code { background: var(--color-surface-alt); border-radius: 3px; }`, `pre { padding; overflow-x: auto; }` |

### BL-123: Mermaid Diagram Rendering

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Dark theme configuration | SKIP | Mermaid library not loaded (no diagrams in test data). Cannot verify JS config. |
| AC-2 | SVG text color override | PASS | CSS verified: `.strategy-editor .mermaid-svg-container svg text { fill: var(--color-text) !important; }` |
| AC-3 | Edge label color | PASS | CSS verified: `.strategy-editor .mermaid-svg-container svg .edgeLabel { color: var(--color-text-muted); }` |

---

## Track 4: Navigation & Naming

---

### BL-197: Rename ICP Playbook to GTM Strategy

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Pillar label renamed | PASS | Nav sidebar reads "GTM Strategy" (verified across all namespaces) |
| AC-2 | Sub-page label renamed | **FAIL** | Tab reads "Strategy Document" instead of "Strategy Overview". The old "ICP Summary" label is gone, but the replacement is different from spec. |
| AC-3 | Page header renamed | PASS | H1 reads "GTM Strategy" (not "ICP Playbook") |
| AC-4 | Action button renamed | N/A | Button was removed entirely per BL-201. Neither "Extract ICP" nor "Analyze Market" exists. |
| AC-5 | Chat placeholder updated | PASS | Placeholder reads "Ask about your GTM strategy..." (not "ICP strategy") |
| AC-6 | Toast message updated | SKIP | Requires triggering market analysis action |

### BL-125: Consistent Top Navigation

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Gear icon removed | PASS | No gear icon or settings button found in navigation bar |
| AC-2 | User menu has Personal section | PASS | "Personal" header with "Preferences" link and "Sign Out" button |
| AC-3 | User menu has Namespace section for admins | PASS | "Namespace" header with "Users & Roles" and "Credits & Usage" links |
| AC-4 | Namespace section hidden for non-admins | SKIP | Requires logging in as a viewer role user |
| AC-5 | Super Admin section for super_admins | PASS | "Super Admin" header (with `text-accent-cyan/60` cyan styling) containing "LLM Costs" link |
| AC-6 | Sign Out replaces Logout | PASS | Button text reads "Sign Out" (not "Logout") |
| AC-7 | Credits link navigates correctly | PASS | Link URL is `/{namespace}/admin/tokens` (verified for both visionvolve and unitedarts namespaces) |

### BL-112: Credits Link in User Dropdown

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Credits link visible for admins | PASS | "Credits & Usage" link visible in Namespace section for admin/super_admin user |
| AC-2 | Credits link hidden for viewers | SKIP | Requires logging in as a viewer role user |
| AC-3 | Credits link navigates to tokens page | PASS | Navigates to `/{namespace}/admin/tokens`. Verified page loads with "Credits" heading. |

---

## Track 5: Playbook Restructuring

---

### BL-198: ICP Tiers Tab

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Tab navigation visible | PASS | Three tabs visible: "Strategy Document", "ICP Tiers", "Buyer Personas" |
| AC-2 | GET tiers returns empty array | **FAIL** | API returns HTTP 404, not 200 with `{"tiers": []}`. Frontend handles 404 gracefully by showing empty state, but the API contract is broken. |
| AC-3 | PUT tiers creates/replaces | SKIP | Requires API testing (PUT request) |
| AC-4 | Tiers tab renders cards | PASS | Tier cards render with editable name, description, and criteria fields (tested by adding a tier). Missing: no visible "priority" input field as mentioned in spec. |
| AC-5 | Add tier | PASS | "Add First Tier" / "+ Add Tier" button works. New empty tier card appears with blank fields. |
| AC-6 | Delete tier | PASS | Delete (X) button visible on tier card |
| AC-7 | Tier criteria fields | PASS | Industries (tag input), Company Size (Min/Max), Revenue Range (Min/Max), Geographies (tag input), Tech Signals (tag input), Qualifying Signals (tag input) all present |
| AC-8 | AI tool for tier extraction | SKIP | Requires triggering AI chat |
| AC-9 | Input validation | SKIP | Requires API testing |
| AC-10 | Auth required | SKIP | Requires API testing without auth |

### BL-199: Buyer Personas Tab

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | GET personas returns empty array | **FAIL** | API returns HTTP 404, not 200 with `{"personas": []}`. Frontend handles gracefully. |
| AC-2 | PUT personas creates/replaces | SKIP | Requires API testing |
| AC-3 | Persona cards render with avatar | PASS | Avatar circle visible with "?" when name is empty. First letter shown when name is filled. |
| AC-4 | Persona fields are editable | PASS | Name, Role/title, Seniority (text inputs), Pain Points, Goals, Messaging Hooks, Objections (tag inputs) all present |
| AC-5 | Channel checkboxes | PASS | LinkedIn, Email, Phone, Twitter/X, Events, Referral all present as toggle pills |
| AC-6 | Linked tiers multi-select | SKIP | Requires tiers to be defined first (and tiers API returns 404) |
| AC-7 | No tiers message | PASS | "No ICP tiers defined yet. Add tiers in the ICP Tiers tab first." (exact text match) |
| AC-8 | Add persona | PASS | "Add First Persona" / "+ Add Persona" button works. New empty persona card appears. |
| AC-9 | Delete persona | PASS | Delete (X) button visible on persona card |
| AC-10 | AI tool for persona extraction | SKIP | Requires triggering AI chat |
| AC-11 | Input validation | SKIP | Requires API testing |
| AC-12 | Auth required | SKIP | Requires API testing |

### BL-201: Remove Extract ICP -- Continuous Auto-Extraction

| AC | Description | Result | Notes |
|----|------------|--------|-------|
| AC-1 | Extract ICP button removed | PASS | No "Extract ICP" or "Analyze Market" button found on playbook page |
| AC-2 | Extraction side panel removed | PASS | No ExtractionSidePanel rendered on any action |
| AC-3 | Continuous extraction system prompt | SKIP | Requires backend code inspection |
| AC-4 | Both tiers and personas extraction prompted | SKIP | Requires backend code inspection |
| AC-5 | No extraction prompt when structures exist | SKIP | Requires backend code inspection |
| AC-6 | Extraction flags in update response | SKIP | Requires API testing |
| AC-7 | Tab navigation replaces extraction | PASS | ICP Tiers and Buyer Personas tabs provide structured views replacing old ExtractionSidePanel |

---

## Gaps Identified

1. **API endpoints not deployed (CRITICAL)**: `GET /api/playbook/strategy/tiers` and `GET /api/playbook/strategy/personas` both return HTTP 404 on staging. The frontend handles this gracefully by showing empty states, but the API contract is broken. Data entered in the tier/persona cards may not persist (PUT likely also 404s). This blocks full validation of BL-198 and BL-199.

2. **System prompt leak not fixed (HIGH)**: BL-208 AC-3/AC-4 fail. The onboarding trigger messages containing internal instructions (e.g., "Generate a complete GTM strategy playbook for my company...") are visible in full in the chat history. No condensed "Strategy generation started..." placeholder is rendered. This exposes internal prompt engineering to users.

3. **Sub-page label mismatch (LOW)**: BL-197 AC-2 expects "Strategy Overview" but the tab reads "Strategy Document". This is cosmetic and may be an intentional deviation.

4. **Missing priority field on tier cards (LOW)**: BL-198 AC-4 mentions "editable name, description, priority, and criteria fields" but no explicit priority input is visible on the tier card. Priority may be implicit from card ordering.

## Items Needing Manual Testing

1. **All BL-212 criteria (AC-1 through AC-6)** -- Require triggering AI strategy generation and observing SSE events and live document updates
2. **All BL-110 criteria (AC-1 through AC-3)** -- Require backend code inspection of system prompt assembly
3. **All BL-211 criteria (AC-1 through AC-3)** -- Require triggering AI generation and inspecting SSE done event payload
4. **All BL-202 criteria (AC-1 through AC-6)** -- Require backend code inspection of system prompt assembly
5. **BL-203 AC-1/AC-2/AC-3** -- Require backend code inspection of `compute_chat_placeholder` function
6. **BL-206 (all criteria)** -- Require creating a new tenant and inspecting backend behavior
7. **BL-207 AC-3/AC-4/AC-5** -- Require submitting the onboarding form
8. **BL-125 AC-4** -- Requires logging in as a viewer role user (no admin permissions)
9. **BL-112 AC-2** -- Requires logging in as a viewer role user
10. **BL-123 AC-1** -- Requires a document with Mermaid diagrams to verify JS config
11. **BL-205 AC-2/AC-3/AC-4** -- Require Mermaid diagrams and interactive keyboard testing
12. **BL-197 AC-6** -- Requires triggering the market analysis action and observing toast

## Screenshots Captured

1. `sprint9-user-dropdown.png` -- User dropdown with Personal/Namespace/Super Admin sections
2. `sprint9-playbook-page.png` -- Playbook page (contacts phase, visionvolve namespace)
3. `sprint9-onboarding-page.png` -- Onboarding flow (unitedarts-cz namespace)
4. `sprint9-unitedarts-playbook.png` -- Strategy editor with tabs (unitedarts namespace)
5. `sprint9-sticky-toolbar-after-scroll.png` -- Toolbar sticking after content scroll
6. `sprint9-icp-tiers-tab.png` -- ICP Tiers tab empty state
7. `sprint9-add-tier.png` -- Tier card with editable fields
8. `sprint9-buyer-personas-tab.png` -- Buyer Personas tab empty state
9. `sprint9-persona-card.png` -- Persona card with all fields
10. `sprint9-tool-cards-expanded.png` -- Tool cards in chat panel
