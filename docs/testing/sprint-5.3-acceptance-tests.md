# Sprint 5.3 Acceptance Test Plan

**Date**: 2026-03-03
**Scope**: All sprint 5.3 items — new PRs + pre-built items
**Test environment**: leadgen-staging.visionvolve.com
**Login**: test@staging.local / staging123

---

## Pre-Test Setup

1. Ensure all sprint 5.3 PRs are merged to staging
2. Verify staging deployment: `GET /api/health` returns 200
3. Clear browser localStorage to test fresh-state scenarios
4. Have a namespace with: strategy document, imported contacts, at least one enriched company

---

# Part 1: New PR Tests (Detailed)

These items have new code from sprint 5.3 PRs and require full testing.

---

## T1: BL-141 — ICP Extraction Feedback and Confirmation

**Precondition**: Strategy document with ICP-relevant content.

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| T1.1 | Navigate to playbook Strategy phase. Write content with clear ICP signals (e.g., "We target mid-size SaaS companies in EU, focusing on CTOs and VPs of Engineering"). Ask AI to extract ICP. | AI calls `set_extracted_field` tool for ICP data | |
| T1.2 | After extraction completes, observe UI feedback | Side panel or inline summary shows extracted ICP criteria (industries, geographies, company size, personas) as readable tags/pills | |
| T1.3 | Check display format | Human-readable: "Industries: SaaS, IT" — not raw JSON | |
| T1.4 | Click "Confirm & Continue" (or equivalent CTA) | Navigates to Contacts phase with ICP filters pre-applied | |
| T1.5 | **Error case**: Ask AI to extract ICP from empty strategy | Graceful error message: "No ICP data found" or similar. No crash | |

---

## T2: BL-143 — Playbook Phase 2: Contacts Selection (PR #76)

**Precondition**: Strategy with extracted ICP, contacts imported.

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| T2.1 | Navigate to playbook Contacts phase | ContactsPhasePanel renders (not "Coming soon" placeholder) | |
| T2.2 | Verify ICP filters are pre-applied | Filter chips show ICP-derived filters (industries, seniority, etc.) from strategy | |
| T2.3 | Verify contact count | "N contacts (ICP filtered)" label visible | |
| T2.4 | Select 3+ contacts using checkboxes | Selection count: "3 contacts selected" | |
| T2.5 | Click "Confirm Selection" | Toast: "N contacts confirmed. Moving to Messages..." Advances to Messages phase | |
| T2.6 | Remove an ICP filter chip | Contact list updates, count changes | |
| T2.7 | Click "Clear filters" | All filter chips removed, shows all contacts | |
| T2.8 | Test ICP Fit column | Binary display: "Strong Fit" or "--" (per PM correction: binary match, not graded) | |
| T2.9 | **Error case**: Contacts phase with no contacts imported | Empty state with "Import Contacts" button, not a blank page | |
| T2.10 | **Error case**: Contacts phase with no ICP | Warning banner: "Extract your ICP..." Shows all contacts unfiltered | |
| T2.11 | Pagination | With >25 contacts, Prev/Next buttons work, page indicator shows correctly | |
| T2.12 | Search | Type in search box, contacts filter by name/company | |

---

## T3: BL-135 — Proactive Next-Step Suggestions (Trigger Points 1-3)

**Precondition**: Fresh namespace or namespace at various workflow stages.

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| T3.1 | **Trigger 1 (post-strategy)**: Complete strategy writing (fill all 9 sections) | Chat proactively suggests next step: "Extract ICP" or "Review strategy" | |
| T3.2 | **Trigger 2 (post-extraction)**: After ICP extraction completes | Chat suggests: "View matching contacts" or "Import contacts" | |
| T3.3 | **Trigger 3 (post-import)**: Import contacts, return to playbook | Chat suggests: "Run enrichment" or "View contacts in playbook" | |
| T3.4 | Verify suggestion format | Suggestions appear as cyan-tinted card with CTA button, or pill chips with lightbulb prefix | |
| T3.5 | Click a suggestion CTA | Action executes (navigates to relevant page or triggers the suggested action) | |
| T3.6 | Verify suggestions don't repeat | After acting on a suggestion, it doesn't reappear on next page load | |
| T3.7 | **Error case**: Suggestions with partial workflow state | No crash if some data is missing. Suggestion adapts to current state. | |

---

## T4: BL-139 — ICP to Enrichment Triage Rules

**Precondition**: Strategy with extracted ICP containing industries.

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| T4.1 | Extract ICP with specific industries (e.g., "SaaS", "FinTech") | ICP extracted_data contains industries array | |
| T4.2 | Run L1 enrichment on a batch with mixed-industry companies | Companies are enriched with industry data | |
| T4.3 | Check triage results for ICP-matching companies | Companies matching ICP industries get "Triage: Passed" | |
| T4.4 | Check triage results for non-matching companies | Non-matching get "Triage: Review" or "Disqualified" | |
| T4.5 | Verify substring/contains matching | ICP industry "SaaS" matches company "Software/SaaS" (not exact equality) | |
| T4.6 | **Error case**: Triage with no ICP data | Falls back to default rules. No crash, no empty triage | |
| T4.7 | **Error case**: ICP with empty industries array | Triage runs with remaining criteria (geographies, size) or falls back | |

---

## T5: BL-131 — Credit Cost Estimator in Enrichment UI (PR #79)

**Precondition**: Navigate to Enrich page, select a tag with contacts.

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| T5.1 | Select a tag and enable enrichment stages | DagControls shows "Est. cost: X,XXX credits" (NOT "$X.XX") | |
| T5.2 | Check per-stage costs in StageCards | Each enabled stage shows "N cr" per item (NOT "$X.XX") | |
| T5.3 | Verify remaining budget context | DagControls shows "/ Y,YYY remaining" after the estimated cost | |
| T5.4 | If possible, set budget low to test exceeded warning | Red "(exceeds budget)" warning appears when est > remaining | |
| T5.5 | Run enrichment and check running/completed cost | Running and completed states show credits format | |
| T5.6 | Disable all stages | Cost display disappears (0 cost, nothing shown) | |

---

# Part 2: Pre-Built Smoke Tests

These items were already found implemented in the codebase. Verify they work on staging.

---

## S1: BL-145 — Strategy-Aware Message Generation

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S1.1 | Navigate to Messages phase with strategy + contacts confirmed | "Generate Messages" button visible with contact count | |
| S1.2 | Click "Generate Messages" | Generation starts, progress indicator shows | |
| S1.3 | Review generated messages | Messages reference strategy context: industries, value propositions | |
| S1.4 | Check personalization | Messages include contact name, company name, job title | |

---

## S2: BL-117 — Campaign Config Auto-Populate from Strategy

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S2.1 | Create a campaign (or use auto-setup) with a strategy document | Campaign `generation_config` is pre-filled from strategy extracted_data | |
| S2.2 | Check generation config fields | Tone, language, channel preferences derived from strategy (not empty defaults) | |

---

## S3: BL-114 — Auto-Advance to Contacts After ICP Extraction

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S3.1 | Extract ICP from strategy phase, confirm extraction | Phase indicator advances to "Contacts" phase automatically | |
| S3.2 | Verify no manual navigation needed | User does NOT need to click "Contacts" in phase selector | |

---

## S4: BL-149 — Namespace Session Persistence

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S4.1 | Navigate to namespace `/acme/contacts` | Page loads correctly | |
| S4.2 | Close browser tab, reopen app at root `/` | Redirects to `/acme/` (last-used namespace), not default | |
| S4.3 | Login from fresh session (clear tokens, keep localStorage) | After login, redirects to last-used namespace | |

---

## S5: BL-151 — Save Progress Indicator (Strategy Toasts)

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S5.1 | On playbook page, ask AI to update strategy sections | Toast appears per section saved: "Section saved: value_proposition" (or similar) | |
| S5.2 | Multiple sections saved rapidly | Toasts stack vertically, auto-dismiss after ~4 seconds | |

---

## S6: BL-116 — apply_icp_filters Chat Tool

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S6.1 | In chat, ask "Find contacts matching my ICP" or "Apply ICP filters" | AI calls `apply_icp_filters` tool | |
| S6.2 | Check tool result | Returns match count, applied filters, top segments | |

---

## S7: BL-147 — Campaign Auto-Setup from Qualified Contacts

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S7.1 | Complete enrichment with triage-passed contacts | CompletionPanel shows "Create Campaign from Qualified Contacts" button | |
| S7.2 | Click the button | Campaign created with auto-generated name, contact count, strategy-prefilled config | |
| S7.3 | Navigate to the new campaign | Campaign detail page loads with contacts and generation config populated | |

---

## S8: BL-121 — Simplified Onboarding (2 Inputs)

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S8.1 | New namespace or fresh user sees onboarding | EntrySignpost or simplified onboarding asks for company URL + description (2 inputs) | |
| S8.2 | Submit onboarding inputs | AI begins strategy research and extraction | |

---

## S9: BL-126 — Import from Playbook (Return URL)

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S9.1 | From playbook Contacts phase, click "Import Contacts" | Navigates to import page with `?return=playbook` query param | |
| S9.2 | Complete import on the import page | After successful import, redirects back to playbook (not import page) | |

---

## S10: BL-146 — Auto-Enrichment with Cost Gate

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S10.1 | After importing contacts, check if enrichment suggestion appears | Chat or UI suggests running enrichment with cost preview | |
| S10.2 | Verify cost gate | Before enrichment starts, cost estimate is shown. User must approve. No silent auto-start. | |

---

## S11: BL-111 — Smart Empty States

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| S11.1 | Navigate to Campaigns page with no campaigns | Smart empty state with actionable CTA (not blank page) | |
| S11.2 | Navigate to Enrich page with no contacts | Smart empty state with "Import Contacts" CTA | |
| S11.3 | Navigate to Messages page with no messages | Smart empty state, not a blank table | |

---

# Part 3: Integration Tests

## I1: End-to-End Playbook Flow

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| I1.1 | Start from Strategy phase. Write strategy content. | Strategy editor saves, toasts confirm sections saved | |
| I1.2 | Ask AI to extract ICP | ICP extracted, feedback panel shown with criteria | |
| I1.3 | Confirm ICP, advance to Contacts | Auto-advances to Contacts phase, ICP filters applied | |
| I1.4 | Select contacts, confirm selection | Advances to Messages phase | |
| I1.5 | Generate messages | Messages are strategy-aware and personalized | |
| I1.6 | Approve messages, advance to Campaign | Campaign phase loads (or placeholder) | |
| I1.7 | Throughout: check proactive suggestions | At each transition, chat suggests the next logical step | |

---

## I2: Credit Display Consistency

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| I2.1 | Check Enrich page DagControls | Credits format, not USD | |
| I2.2 | Check Enrich page StageCards | Credits format per item | |
| I2.3 | Check message generation cost dialog | Credits format (if applicable) | |

---

# Part 4: Regression Tests

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| R1 | Login with test@staging.local / staging123 | Login succeeds, redirects to namespace | |
| R2 | All sidebar nav items | Contacts, Companies, Enrich, Messages, Campaigns, Playbook all load | |
| R3 | Chat: send a message | AI responds, tool calls work | |
| R4 | Contact detail page | Click a contact, detail page loads with enrichment data | |
| R5 | Company detail page | Click a company, detail page loads with modules | |
| R6 | CSV import | Upload a CSV, contacts appear in list | |
| R7 | Enrichment configure mode | Stage cards render, toggles work, estimates load | |
| R8 | Logout and re-login | Logout redirects to `/`, login works, namespace persisted | |

---

# BL-166 Verification Notes

BL-166 (Real-Time Enrichment Progress Feedback) depends on BL-148 + BL-142 from sprint 5.2.

**Already exists:**
- `useEnrichPipeline.ts`: Polls `GET /api/pipeline/dag-status` every 5 seconds
- `StageCard.tsx`: Per-stage progress bars (done/total), current item name, cost
- `DagMode` states: configure -> running -> completed with visual transitions
- Backend: `pipeline_routes.py` has `/api/pipeline/dag-status` endpoint

**BL-166 gap (enhancement, M effort):**
- Per-entity progress within a stage (currently aggregate counts only)
- Per-stage cost accumulation during run (populated only on completion)
- Error details per failed entity (currently only failed count)
- SSE/WebSocket for lower-latency updates (currently 5s polling)

**Verdict: PARTIALLY DONE** — Basic real-time progress works. BL-166 is an enhancement for granularity and error details. Deferrable to Sprint 6.
