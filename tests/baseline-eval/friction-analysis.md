# Baseline Friction Analysis — Sprint 5 Planning

**Source**: baseline-001 (2026-03-02, unitedarts.cz, staging @ 625753a)
**Analyst**: Claude Opus 4.6 (automated)
**Date**: 2026-03-02

---

## 1. Complete Friction Inventory

Every issue observed during the baseline test, extracted from BASELINE-REPORT.md, test-execution-log.md, ideal-workflow.md, and scores.json.

### Category A: Bugs (Crashes, Errors, Failures)

| # | Friction | Severity | Source | Existing Item |
|---|----------|----------|--------|---------------|
| A1 | Import column mapping UI crashes with `TypeError: Cannot read properties of undefined (reading 'length')` — page goes blank after "Upload & Analyze" | BLOCKER | BUG-001, Step 4 | **BL-134** (Sprint 5) |
| A2 | Template application API (`/api/playbook/apply-template`) fails — silent fallback to AI chat | MAJOR | BUG-002, Step 2 | **BL-138** (Sprint 5) |
| A3 | EntrySignpost component exists in code but does not render for empty namespaces | MAJOR | BUG-003, Step 1 | **BL-136** (Sprint 5) |
| A4 | Cross-namespace filter leakage — enrichment page shows tags from visionvolve in unitedarts namespace | MINOR | BUG-004, Step 5 | **BL-142** (Sprint 5) |
| A5 | AI rate limit of 5 tool calls per turn visible to user — forces multi-turn for 9-section strategy | MINOR | BUG-005, Step 2 | **BL-140** (Sprint 5) |
| A6 | Import "Resume" button leads to blank column mapping area (same underlying crash as A1) | MAJOR | Step 4, test log line 144-147 | **BL-134** (same bug) |
| A7 | Enrichment "Run" button shows "Loading..." and does not fully load | MINOR | Step 5, test log line 199 | **NEW: BL-148** |
| A8 | Namespace defaults to visionvolve on fresh page loads — inconsistent with last-used namespace | MINOR | Step 1, test log line 27 | **NEW: BL-149** |

### Category B: UX Friction (Extra Clicks, Confusing UI, Missing Feedback)

| # | Friction | Severity | Source | Existing Item |
|---|----------|----------|--------|---------------|
| B1 | ICP extraction is completely silent — no toast, no summary, no confirmation of what was extracted | HIGH | Step 3, report lines 96-98 | **BL-141** (Sprint 5) |
| B2 | Empty namespace shows full filter sidebar (Company Tier, Industry, Size, Region, Revenue, Seniority, Department, LinkedIn Activity) — overwhelming for first-time users | MEDIUM | Step 1, test log line 28 | **BL-111** (Sprint 4, Spec'd) / **BL-136** (Sprint 5) |
| B3 | Phase 2 (Contacts) shows "Coming soon. Use the chat to discuss this phase with your AI strategist." — dead end in playbook | HIGH | Step 3, report line 97 | **BL-143** (Sprint 5) |
| B4 | Template selection fails silently — no error toast or message shown to user | MEDIUM | Step 2, report line 181 | **BL-138** (Sprint 5, same item) |
| B5 | AI first response was text-only ("I'll build your strategy") without executing tools — user had to re-prompt | MEDIUM | Step 2, test log line 57 | **NEW: BL-150** |
| B6 | No auto-save feedback after each strategy section was written | LOW | Step 2, test log line 79 | **BL-049** (Done, but feedback missing) — **NEW: BL-151** |
| B7 | After strategy completion, no suggestion to extract ICP or proceed to next phase | HIGH | Report line 291-292 | **BL-135** (Sprint 5) |
| B8 | After ICP extraction, no suggestion to import contacts | HIGH | Report line 293 | **BL-135** (Sprint 5, same) |
| B9 | After contact import, no suggestion to run enrichment | HIGH | Report line 294 | **BL-135** (Sprint 5, same) |
| B10 | After enrichment inspection, no suggestion for triage or campaign creation | HIGH | Report line 295 | **BL-135** (Sprint 5, same) |
| B11 | Chat sidebar never proactively offered guidance at any point during entire test | HIGH | Report line 296 | **BL-135** (Sprint 5, same) |
| B12 | User must manually navigate to Playbook page from empty contacts page — no shortcut or guidance | MEDIUM | Step 1, report line 194 | **BL-136** (Sprint 5) |
| B13 | Namespace switch required after login (session cached from previous test) — extra click | LOW | Step 1, test log line 20-22 | **BL-149** (same as A8) |
| B14 | No cost estimate shown proactively on enrichment page without user action | MEDIUM | Step 5, test log line 211 | **BL-146** (Sprint 5) / **BL-131** (unassigned) |
| B15 | "Select Contacts" button disabled on Phase 2 with no explanation | LOW | Step 3, test log line 118 | **BL-143** (Sprint 5, same) |

### Category C: Missing Features (Should Exist But Don't)

| # | Friction | Severity | Source | Existing Item |
|---|----------|----------|--------|---------------|
| C1 | No web_search called during strategy generation — AI uses training data instead of researching unitedarts.cz | HIGH | Step 2, report line 82 | **BL-137** (Sprint 5) |
| C2 | Playbook Phase 2 (Contacts) not functional — "Coming soon" placeholder | HIGH | Step 3, report line 418 | **BL-143** (Sprint 5) |
| C3 | No end-to-end workflow orchestrator connecting strategy -> extraction -> contacts -> enrichment -> campaign | HIGH | Report section "Workflow Gap Analysis" | **BL-144** (Sprint 5) |
| C4 | No proactive "next step" suggestion engine after major actions | HIGH | Report recommendation #2 | **BL-135** (Sprint 5) |
| C5 | ICP criteria from extraction not pre-loaded into enrichment triage rules | MEDIUM | Report line 309-310, step 6 notes | **BL-139** (Sprint 5) |
| C6 | No pipeline automation: strategy -> extraction -> filter -> enrich -> triage -> campaign | HIGH | Report line 312 | **BL-144** (Sprint 5, same) |
| C7 | Chat has no context-aware behavior outside Playbook page | MEDIUM | Report line 320 | **BL-135** (Sprint 5) / **BL-133** (unassigned) |
| C8 | No proactive gate presentation — no "I've completed X, here's the summary, do you approve?" | MEDIUM | Report section 4 (User-Input Gates) | **BL-135** (Sprint 5) |
| C9 | No strategy-aware campaign configuration — campaigns have no awareness of strategy content | MEDIUM | Report line 307-308 | **BL-145** (Sprint 5) / **BL-117** (Sprint 4, Spec'd) |
| C10 | Strategy document has placeholder text: "[X] agencies", "[Y]% revenue" | MEDIUM | Step 2, report line 86, 245-246 | **BL-137** (Sprint 5, web research would fix) |
| C11 | No named Czech competitors in competitive analysis — generic positioning | MEDIUM | Step 2, report line 247 | **BL-137** (Sprint 5, web research would fix) |
| C12 | No mention of specific unitedarts.cz acts (Losers Cirque, DaeMen) or venues (Divadlo BRAVO!) | MEDIUM | Step 2, report line 248-249 | **BL-137** (Sprint 5, web research would fix) |
| C13 | Enrichment has no awareness of strategy or which contacts are ICP-relevant | MEDIUM | Report line 306 | **BL-139** (Sprint 5) |
| C14 | Import does not auto-assign contacts to a playbook flow | LOW | Report line 311 | **BL-126** (unassigned) |
| C15 | Campaign creation has no awareness of which contacts have been enriched | MEDIUM | Report line 307 | **BL-147** (Sprint 5) |

### Category D: Integration Gaps (Features Don't Talk to Each Other)

| # | Friction | Severity | Source | Existing Item |
|---|----------|----------|--------|---------------|
| D1 | Playbook and Import are completely disconnected — ICP criteria not used by import | HIGH | Report section 2 (Cross-Feature Integration) | **BL-126** (unassigned) / **BL-143** (Sprint 5) |
| D2 | Import and Enrichment are disconnected — import does not notify enrichment | HIGH | Report line 311 | **BL-146** (Sprint 5) |
| D3 | Enrichment and Strategy are disconnected — no ICP awareness | HIGH | Report line 306 | **BL-139** (Sprint 5) |
| D4 | Enrichment and Campaign are disconnected — no auto-campaign from enriched contacts | MEDIUM | Report line 307 | **BL-147** (Sprint 5) |
| D5 | Each feature operates as "isolated island" — share a database but no process integration | HIGH | Report line 314 | **BL-144** (Sprint 5) |

### Category E: AI Quality Issues

| # | Friction | Severity | Source | Existing Item |
|---|----------|----------|--------|---------------|
| E1 | No web research performed — web_search tool available but never called | HIGH | Step 2, report line 82, 303-304 | **BL-137** (Sprint 5) |
| E2 | Placeholder statistics: "[X] agencies", "[Y]% revenue" in strategy | MEDIUM | Step 2, report line 245-246 | **BL-137** (Sprint 5) |
| E3 | Generic competitive analysis — no named competitors, fabricated market data | MEDIUM | Step 2, report line 247 | **BL-137** (Sprint 5) |
| E4 | Revenue estimates and market size figures are fabricated (no data source) | MEDIUM | Step 2, report line 247 | **BL-137** (Sprint 5) |
| E5 | AI said "I'll build your strategy" but did not execute tools — required re-prompt | MEDIUM | Step 2, test log line 57 | **BL-150** (new) |
| E6 | AI hit rate limit after 5/9 sections — implementation detail leaked to user | MINOR | Step 2, test log line 58-59 | **BL-140** (Sprint 5) |

### Category F: Data Issues

| # | Friction | Severity | Source | Existing Item |
|---|----------|----------|--------|---------------|
| F1 | Cross-namespace filter leakage — visionvolve tags visible in unitedarts | MINOR | Step 5, BUG-004 | **BL-142** (Sprint 5) |
| F2 | Namespace session persistence inconsistent — defaults to visionvolve on reload | LOW | Step 1, test log line 27 | **BL-149** (new) |

### Category G: Workflow Dead-Ends

| # | Friction | Severity | Source | Existing Item |
|---|----------|----------|--------|---------------|
| G1 | After ICP extraction, Phase 2 shows "Coming soon" — complete dead-end | HIGH | Step 3, report line 97 | **BL-143** (Sprint 5) |
| G2 | After import crash, "Resume" button also crashes — no recovery path through UI | BLOCKER | Step 4, test log line 144-147 | **BL-134** (Sprint 5) |
| G3 | After strategy completion, user has no guidance on next action — must discover Import/Enrich through nav | HIGH | Report section 1 (Proactive Flow) | **BL-135** (Sprint 5) |
| G4 | After import, user must manually navigate to Enrich page — no suggestion | HIGH | Report line 294 | **BL-135** (Sprint 5) |
| G5 | Enrichment Run button stuck in "Loading..." — cannot actually start enrichment | MEDIUM | Step 5, test log line 199 | **BL-148** (new) |

### Category H: Performance Issues

| # | Friction | Severity | Source | Existing Item |
|---|----------|----------|--------|---------------|
| H1 | ICP extraction took 5-10 seconds with no progress indicator | LOW | Step 3, test log line 109 | **BL-141** (Sprint 5, includes progress feedback) |

---

## 2. Mapping to Backlog

### Existing Sprint 5 Items — All Confirmed Needed

| Sprint 5 Item | Friction(s) Covered | Notes |
|---------------|---------------------|-------|
| **BL-134**: Fix Import Column Mapping UI Crash | A1, A6, G2 | BLOCKER. Must fix first. |
| **BL-135**: Proactive Next-Step Suggestions in Chat | B7, B8, B9, B10, B11, C4, C7, C8, G3, G4 | Covers 10 friction points. Highest-impact single item. |
| **BL-136**: Fix EntrySignpost for Empty Namespaces | A3, B2, B12 | First-impression failure. |
| **BL-137**: Add Web Research to Strategy Generation | C1, C10, C11, C12, E1, E2, E3, E4 | 8 friction points. Major AI quality upgrade. |
| **BL-138**: Fix Template Application API | A2, B4 | Restores template-based flow. |
| **BL-139**: Connect ICP Extraction to Enrichment Triage | C5, C13, D3 | Cross-feature integration. |
| **BL-140**: Increase Agent Tool Call Limit | A5, E6 | UX polish — rate limit should be invisible. |
| **BL-141**: Add ICP Extraction Feedback | B1, H1 | Silent operation → clear feedback. |
| **BL-142**: Fix Cross-Namespace Filter Leakage | A4, F1 | Data isolation fix. |
| **BL-143**: Implement Playbook Phase 2 (Contacts) | B3, B15, C2, D1, G1 | Removes "Coming soon" dead-end. |
| **BL-144**: End-to-End Workflow Orchestrator | C3, C6, D5 | Connective tissue for entire workflow. |
| **BL-145**: Strategy-Aware Message Generation | C9 | Messages use strategy context. |
| **BL-146**: Auto-Enrichment Trigger with Cost Gate | B14, D2 | Bridge import → enrichment with cost approval. |
| **BL-147**: Campaign Auto-Setup from Qualified Contacts | C15, D4 | Bridge enrichment → campaign. |

### New Items Created

| New Item | Friction(s) | Priority | Effort | Sprint |
|----------|-------------|----------|--------|--------|
| **BL-148**: Enrichment Run Button Stuck in Loading State | A7, G5 | Must Have | S | Sprint 5 |
| **BL-149**: Namespace Session Persistence — Remember Last Used | A8, B13, F2 | Should Have | S | Sprint 5 |
| **BL-150**: AI Agent Should Auto-Execute Tools After Onboarding | B5, E5 | Should Have | M | Sprint 5 |
| **BL-151**: Strategy Save Progress Indicator Per Section | B6 | Could Have | S | Sprint 5 |

### Existing Items From Other Sprints That Map to Friction Points

| Item | Current Sprint | Friction(s) | Recommendation |
|------|---------------|-------------|----------------|
| **BL-111**: App-Wide Onboarding Signpost | Sprint 4 (Spec'd) | B2 | **MOVE to Sprint 5** — overlaps BL-136, do together |
| **BL-113**: Wire company research into onboarding | Sprint 4 (Spec'd) | C1 partial | **MERGE into BL-137** — BL-137 is broader (web research everywhere, not just onboarding) |
| **BL-114**: Auto-advance to Contacts after extraction | Sprint 4 (Spec'd) | G1 | **MOVE to Sprint 5** — overlaps BL-141 and BL-143 |
| **BL-116**: apply_icp_filters chat tool | Sprint 4 (Spec'd) | C5, D1 | **MOVE to Sprint 5** — overlaps BL-139 |
| **BL-117**: Auto-populate campaign generation_config | Sprint 4 (Spec'd) | C9 | **MOVE to Sprint 5** — overlaps BL-145 |
| **BL-121**: Simplify onboarding to 2 inputs | Sprint 4 (Spec'd) | B12 | **MOVE to Sprint 5** — overlaps BL-136 (entry signpost) |
| **BL-126**: Contact Import in Playbook | Unassigned | D1, C14 | **MOVE to Sprint 5** — overlaps BL-134 and BL-143 |
| **BL-131**: Credit Cost Estimator | Unassigned | B14 | **MOVE to Sprint 5** — overlaps BL-146 (cost gate) |
| **BL-133**: Phase Transition Prompts | Unassigned | C7, C8 | **MERGE into BL-135** — proactive suggestions is the superset |

---

## 3. New Backlog Items Created

### BL-148: Enrichment Run Button Stuck in Loading State

**Priority**: Must Have | **Effort**: S | **Sprint**: 5

#### Problem
The enrichment page "Run" button shows "Loading..." and never fully loads. Users cannot start enrichment through the UI even when contacts and stages are properly configured.

#### Acceptance Criteria
- Given a namespace with imported contacts and selected enrichment stages
- When the user clicks the "Run" button on the Enrich page
- Then the button should load within 2 seconds and show the run configuration (tag filter, stages, cost estimate)
- And clicking Run should trigger the enrichment pipeline

#### Technical Notes
Likely a frontend state issue — the button depends on tag/batch data loading. May be related to the cross-namespace filter leakage (BL-142) if the loading state depends on resolving namespace-scoped data.

#### Baseline Reference
From baseline test Step 5: "Run button shows 'Loading...' — not fully loaded" (test-execution-log.md line 199)

---

### BL-149: Namespace Session Persistence — Remember Last Used

**Priority**: Should Have | **Effort**: S | **Sprint**: 5

#### Problem
On fresh page loads, the namespace defaults to visionvolve instead of remembering the last-used namespace. This forces an extra click to switch namespaces on every session.

#### Acceptance Criteria
- Given a user who last worked in the "unitedarts" namespace
- When they open the app in a new tab or refresh the page
- Then the app should load into the "unitedarts" namespace (stored in localStorage or cookie)
- And if the stored namespace is no longer accessible, fall back to the first available namespace

#### Technical Notes
Store `lastNamespace` in localStorage. Read on app init before the first API call. This is a pure frontend change.

#### Baseline Reference
From baseline test Step 1: "Namespace defaults to visionvolve on fresh page loads — inconsistent default behavior" (test-execution-log.md line 27)

---

### BL-150: AI Agent Should Auto-Execute Tools After Onboarding

**Priority**: Should Have | **Effort**: M | **Sprint**: 5

#### Problem
After the PlaybookOnboarding wizard completes and falls back to AI chat (either because the template API failed or by design), the AI responds with "I'll build your strategy" but does NOT execute any tools. The user must send a second explicit prompt to trigger tool execution.

#### Acceptance Criteria
- Given a user who completes the PlaybookOnboarding wizard (Discovery + Template steps)
- When the AI receives the auto-generated chat message with the user's inputs
- Then the AI should immediately begin executing strategy tools (update_strategy_section) without waiting for another user prompt
- And the AI should NOT send a text-only "I'll do this" response without acting

#### Technical Notes
This may be a system prompt issue — the AI might need stronger instruction to "act immediately" rather than "describe what it will do." Could also be an agent_executor.py issue where the auto-generated message is treated differently from user messages.

#### Baseline Reference
From baseline test Step 2: "AI responded with 'I'll build your complete GTM strategy playbook now' but did NOT actually write to the document" (test-execution-log.md lines 55-57)

---

### BL-151: Strategy Save Progress Indicator Per Section

**Priority**: Could Have | **Effort**: S | **Sprint**: 5

#### Problem
When the AI writes strategy sections via tools, there is no visual feedback that each section was saved. The user sees tool call indicators but no save confirmation per section.

#### Acceptance Criteria
- Given the AI is writing strategy sections via update_strategy_section tool
- When each section is successfully saved
- Then a brief toast or inline indicator should confirm "Section X saved"
- And the editor should scroll to show the newly written section

#### Technical Notes
The auto-save debounce indicator exists (BL-049) but this is about per-section feedback during AI generation, not user-edit auto-save.

#### Baseline Reference
From baseline test Step 2: "No auto-save feedback after each section was written" (test-execution-log.md line 79)

---

## 4. Overlap Analysis

### Sprint 4 Items That Should Move to Sprint 5

These Sprint 4 items are Spec'd but not Done, and directly overlap with Sprint 5 baseline friction items:

| Sprint 4 Item | Overlaps With | Recommendation |
|---------------|--------------|----------------|
| **BL-111**: App-Wide Onboarding Signpost | BL-136 (entry signpost fix) | **MOVE** — BL-136 is the bug fix, BL-111 is the enhanced version. Do BL-136 first, then BL-111 as enhancement in same sprint. |
| **BL-113**: Wire company research into onboarding | BL-137 (web research) | **MERGE into BL-137** — BL-137 adds web research to all strategy generation. BL-113's scope (onboarding-only) is a subset. |
| **BL-114**: Auto-advance to Contacts after extraction | BL-141 (extraction feedback) + BL-143 (Phase 2) | **MOVE** — BL-114 connects extraction to contacts. Do after BL-141 and BL-143. |
| **BL-116**: apply_icp_filters chat tool | BL-139 (ICP to triage) | **MOVE** — BL-116 is the chat tool, BL-139 is the backend bridge. Complementary, same sprint. |
| **BL-117**: Auto-populate campaign generation_config | BL-145 (strategy-aware messages) | **MOVE** — BL-117 is one piece of BL-145. |
| **BL-121**: Simplify onboarding to 2 inputs | BL-136 (entry signpost) | **MOVE** — Both are about first-time user experience. |

### Sprint 4 Items to LEAVE in Sprint 4

| Item | Reason to Leave |
|------|----------------|
| **BL-123**: Mermaid diagram rendering | Not related to baseline friction. Nice-to-have editor feature. |
| **BL-124**: Sticky format toolbar | Not related to baseline friction. Editor UX polish. |

### Unassigned Items That Should Move to Sprint 5

| Unassigned Item | Overlaps With | Recommendation |
|----------------|---------------|----------------|
| **BL-126**: Contact Import in Playbook | BL-134 (import fix) + BL-143 (Phase 2) | **MOVE** — After import fix and Phase 2, embed import in playbook. |
| **BL-131**: Credit Cost Estimator | BL-146 (cost approval gate) | **MOVE** — Cost estimator is a component needed by the cost approval gate. |
| **BL-133**: Phase Transition Prompts | BL-135 (proactive suggestions) | **MERGE into BL-135** — Phase transition prompts are a subset of proactive suggestions. |

### Unassigned Items to LEAVE as-is

| Item | Reason |
|------|--------|
| **BL-125**: Consistent top navigation | Not baseline friction — nav worked fine in test. |
| **BL-127**: Enrichment Strategy Presets | Overlaps BL-139 but adds preset UI — defer to later sprint. |
| **BL-128**: Enrichment Agent Tools | Overlaps BL-146 but adds chat tools for enrichment — defer after Sprint 5 bridge items. |
| **BL-129**: Enrichment Trigger from Playbook | Overlaps BL-146 — defer, BL-146 covers the critical path. |
| **BL-130**: ICP-to-Eligibility Bridge | Overlaps BL-139 — defer, BL-139 covers the immediate need. |
| **BL-132**: Enrichment Progress Panel | Not baseline friction — enrichment was not executed. Defer. |
| **BL-057**: Campaign Generation Customization | Not baseline friction — campaigns were not tested. |
| **BL-058**: Strategy Feedback Loop | Not baseline friction — needs campaign data first. |
| **BL-112**: Link Credits to context dropdown | Not baseline friction — cosmetic UX. |

---

## 5. Recommended Sprint 5 Item List

### Final Deduplicated Sprint 5 Items (22 items)

#### Track 1: Bug Fixes (5 items, parallel)

| Item | Title | Priority | Effort | Depends On |
|------|-------|----------|--------|------------|
| **BL-134** | Fix Import Column Mapping UI Crash | Must Have | M | None |
| **BL-136** | Fix EntrySignpost for Empty Namespaces | Must Have | S | None |
| **BL-138** | Fix Template Application API | Must Have | S | None |
| **BL-142** | Fix Cross-Namespace Filter Leakage on Enrich Page | Must Have | S | None |
| **BL-148** | Fix Enrichment Run Button Loading State | Must Have | S | BL-142 (may share root cause) |

#### Track 2: AI Quality (3 items, sequential)

| Item | Title | Priority | Effort | Depends On |
|------|-------|----------|--------|------------|
| **BL-137** | Add Web Research to Strategy Generation | Must Have | L | None |
| **BL-140** | Increase Agent Tool Call Limit or Auto-Continue | Must Have | S | None |
| **BL-150** | AI Agent Should Auto-Execute Tools After Onboarding | Should Have | M | None |

**Note**: BL-113 (Sprint 4, wire research into onboarding) is **merged into BL-137**.

#### Track 3: Extraction + Phase Transitions (4 items, sequential)

| Item | Title | Priority | Effort | Depends On |
|------|-------|----------|--------|------------|
| **BL-141** | Add ICP Extraction Feedback and Confirmation | Must Have | M | None |
| **BL-143** | Implement Playbook Phase 2 — Contacts Selection | Must Have | L | None |
| **BL-114** | Auto-advance to Contacts after ICP Extraction (from Sprint 4) | Must Have | S | BL-141, BL-143 |
| **BL-121** | Simplify Onboarding to 2 Inputs (from Sprint 4) | Should Have | M | BL-136 |

#### Track 4: Cross-Feature Integration (5 items, sequential)

| Item | Title | Priority | Effort | Depends On |
|------|-------|----------|--------|------------|
| **BL-139** | Connect ICP Extraction to Enrichment Triage Rules | Must Have | M | BL-141 |
| **BL-116** | apply_icp_filters chat tool (from Sprint 4) | Must Have | M | BL-139 |
| **BL-145** | Strategy-Aware Message Generation | Must Have | M | None |
| **BL-117** | Auto-populate campaign generation_config (from Sprint 4) | Must Have | S | BL-145 |
| **BL-147** | Campaign Auto-Setup from Qualified Contacts | Must Have | L | BL-139, BL-145 |

#### Track 5: Proactive AI + Orchestration (3 items, sequential)

| Item | Title | Priority | Effort | Depends On |
|------|-------|----------|--------|------------|
| **BL-135** | Proactive Next-Step Suggestions in Chat | Must Have | L | None |
| **BL-146** | Auto-Enrichment Trigger with Cost Approval Gate | Must Have | L | BL-134 (import works), BL-139 |
| **BL-144** | End-to-End Workflow Orchestrator | Must Have | XL | BL-135, BL-139, BL-145, BL-146, BL-147 |

**Note**: BL-133 (phase transition prompts) is **merged into BL-135**.

#### Track 6: Polish (3 items, independent)

| Item | Title | Priority | Effort | Depends On |
|------|-------|----------|--------|------------|
| **BL-111** | App-Wide Onboarding Signpost + Smart Empty States (from Sprint 4) | Should Have | M | BL-136 |
| **BL-149** | Namespace Session Persistence — Remember Last Used | Should Have | S | None |
| **BL-151** | Strategy Save Progress Indicator Per Section | Could Have | S | None |

#### Deferred (mentioned in baseline but out of Sprint 5 scope)

| Item | Reason for Deferral |
|------|-------------------|
| **BL-126**: Contact Import in Playbook | Depends on BL-134 + BL-143. Sprint 6 candidate after both are solid. |
| **BL-131**: Credit Cost Estimator Component | Part of BL-146 scope — cost estimator is embedded, not standalone. |

---

## 6. Dependency Graph

```
Legend:
  --> means "blocks" (must complete before)
  |   means parallel (no dependency)

TRACK 1 (Bug Fixes) — all parallel, no dependencies
  BL-134 (import crash)
  BL-136 (entry signpost)
  BL-138 (template API)
  BL-142 (filter leakage) --> BL-148 (run button loading)

TRACK 2 (AI Quality) — mostly parallel
  BL-137 (web research)    [absorbs BL-113]
  BL-140 (tool call limit)
  BL-150 (auto-execute tools)

TRACK 3 (Extraction + Phases) — sequential chain
  BL-141 (extraction feedback)
    --> BL-114 (auto-advance to contacts)
  BL-143 (Phase 2 contacts)
    --> BL-114 (auto-advance to contacts)
  BL-136 (entry signpost)
    --> BL-121 (simplify onboarding)
    --> BL-111 (smart empty states)

TRACK 4 (Integration) — sequential chain
  BL-141 (extraction feedback)
    --> BL-139 (ICP to triage)
      --> BL-116 (apply_icp_filters tool)
  BL-145 (strategy-aware messages)
    --> BL-117 (campaign generation_config)
  BL-139 + BL-145
    --> BL-147 (campaign auto-setup)

TRACK 5 (Proactive AI) — sequential chain
  BL-135 (proactive suggestions)    [absorbs BL-133]
  BL-134 + BL-139
    --> BL-146 (auto-enrichment trigger)
  BL-135 + BL-139 + BL-145 + BL-146 + BL-147
    --> BL-144 (workflow orchestrator)

TRACK 6 (Polish) — parallel
  BL-149 (namespace persistence)
  BL-151 (save indicator)

Full dependency chain (critical path):
  BL-141 --> BL-139 --> BL-146 --> BL-144
  BL-134 ---------> BL-146
  BL-135 -----------------------> BL-144
  BL-145 --> BL-147 ------------> BL-144
```

### Critical Path

The longest dependency chain is:
1. **BL-141** (extraction feedback) + **BL-134** (import fix) — parallel, do first
2. **BL-139** (ICP to triage) — needs BL-141
3. **BL-145** (strategy-aware messages) — independent, parallel with above
4. **BL-146** (auto-enrichment trigger) — needs BL-134, BL-139
5. **BL-147** (campaign auto-setup) — needs BL-139, BL-145
6. **BL-144** (workflow orchestrator) — needs BL-135, BL-139, BL-145, BL-146, BL-147

**BL-144 (orchestrator) is the final capstone** — it ties everything together. All other items feed into it. It should be the last item built.

---

## 7. Sprint 5 Summary Statistics

| Metric | Value |
|--------|-------|
| Total items | 22 |
| New items created | 4 (BL-148, BL-149, BL-150, BL-151) |
| Moved from Sprint 4 | 6 (BL-111, BL-113→merged, BL-114, BL-116, BL-117, BL-121) |
| Merged items | 2 (BL-113→BL-137, BL-133→BL-135) |
| Must Have | 17 |
| Should Have | 4 (BL-111, BL-149, BL-150, BL-121) |
| Could Have | 1 (BL-151) |
| Effort S | 8 |
| Effort M | 8 |
| Effort L | 5 |
| Effort XL | 1 (BL-144) |
| Bug fixes | 5 (Track 1) |
| AI quality | 3 (Track 2) |
| Phase/extraction | 4 (Track 3) |
| Integration | 5 (Track 4) |
| Proactive AI | 3 (Track 5) |
| Polish | 3 (Track 6) |
| Baseline friction points covered | 45/45 (100%) |

### Expected Score Impact After Sprint 5

| Dimension | Current | Target | Delta |
|-----------|---------|--------|-------|
| Overall Completeness | 6.0 | 8.0+ | +2.0 |
| Workflow Seamlessness | 3.2 | 7.0+ | +3.8 |
| AI Quality | 7.5 | 9.0+ | +1.5 |
| User Effort | 7.2 | 8.5+ | +1.3 |
| Proactiveness | 2.5 | 7.0+ | +4.5 |

The biggest improvement is expected in **Proactiveness** (+4.5) and **Seamlessness** (+3.8) because Sprint 5 focuses on the connective tissue between features (BL-135, BL-144) rather than building new standalone features.
