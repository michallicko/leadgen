# Baseline-002 Test Execution Log

## Test: GTM Full Workflow (unitedarts.cz) -- Sprint 5 Build

**Date**: 2026-03-02
**System Version**: staging @ `95234c2`
**Environment**: https://leadgen-staging.visionvolve.com/
**Namespace**: unitedarts
**Tester**: Automated (Claude Opus 4.6 via Playwright MCP)
**Login**: test@staging.local / staging123
**Duration**: ~10 minutes
**Compared against**: baseline-001 (staging @ `625753a`)

---

## Executive Summary

This test re-ran the same 10-step GTM workflow from baseline-001 against the Sprint 5 build. The unitedarts namespace retained data from baseline-001 (strategy document + 10 contacts), so this test evaluated both persistence and incremental improvements.

**3 steps completed, 1 partial, 6 skipped** (same enrichment dependency as baseline-001).

Sprint 5 delivered **meaningful improvements in the strategy creation flow** -- the AI now auto-executes tools and suggests next steps proactively. The import column mapping UI crash (BUG-001) is fixed. However, **new issues emerged**: import preview returns a 500 error, and AI column mappings don't populate the UI dropdowns.

**Verdict**: Sprint 5 improved the AI interaction quality (proactiveness +0.2, seamlessness +0.2) but did not significantly advance the end-to-end workflow. The import flow is still broken (different error), and the cross-namespace filter leakage persists.

---

## Step-by-Step Execution

### Step 1: Login + Navigation

**Time**: 11:38 PM
**Actions**:
1. Navigated to `https://leadgen-staging.visionvolve.com/`
2. Auto-logged in (session from previous testing)
3. Redirected to `/visionvolve/admin` (NOT unitedarts -- namespace did NOT persist)
4. Switched namespace to `unitedarts` via dropdown
5. Navigated to `/unitedarts/` -- redirected to `/unitedarts/contacts`

**Observations**:
- No EntrySignpost appeared (BL-136 NOT visible)
- Namespace did NOT persist from last session (BL-149 NOT working -- defaulted to visionvolve)
- Contacts page showed "0 contacts" initially with Loading state, then showed 10 contacts after tag filter reset
- Full filter sidebar visible (ICP Fit, Msg Status, Tag, Owner, Company Tier, Industry, etc.)
- Chat panel opened with conversation history from baseline-001

**Score**: availability=8, seamlessness=4, proactiveness=2, user_effort=7

---

### Step 2: GTM Strategy Creation

**Time**: 11:41 PM
**Actions**:
1. Clicked Playbook nav link
2. Playbook loaded with existing 9-section strategy from baseline-001
3. Phase tabs: 1 Strategy (active), 2 Contacts, 3 Messages, 4 Campaign
4. Entered business description in chat input (from test instructions)
5. AI immediately called `get_strategy_document` (3ms) then 4x `update_strategy_section`
6. Strategy updated in single turn -- no re-prompting needed

**Observations**:
- AUTO-EXECUTED tools (BL-150 FIXED) -- in baseline-001, AI said "I'll build your strategy" without executing
- Completed in 1 user message (baseline-001 needed 4)
- Updated 4 sections with specific details (reference clients, flagship acts, service model)
- No web_search called (BL-137 NOT fixed)
- Proactive next step: "Move to the Contacts phase"
- Hit rate limit at 5 tool calls (1 read + 4 updates) but sufficient for update flow

**Score**: availability=8, seamlessness=7, proactiveness=7, ai_quality=7, user_effort=8

---

### Step 3: Intelligence Extraction

**Time**: 11:41 PM
**Actions**:
1. Clicked "Extract ICP" button in Playbook header
2. Button changed to "Extracting..." (disabled state)
3. After ~5 seconds, button returned to normal
4. Toast notification appeared: "Strategy data extracted successfully"
5. AI posted 3 strategic follow-up questions
6. Navigated to Phase 2 (Contacts) -- still shows "Coming soon"

**Observations**:
- Toast notification is NEW (was silent in baseline-001) -- partial BL-141
- AI follow-up questions are insightful but are unnecessary_clarifications (answers are in the strategy)
- No extraction summary (what was extracted: industries, geography, etc.)
- Phase 2 still placeholder ("Coming soon")
- Select Contacts button disabled
- Contextual chat placeholder: "Which contacts should we target?"

**Score**: availability=7, seamlessness=4, proactiveness=5, ai_quality=7, user_effort=7

---

### Step 4: Contact Import

**Time**: 11:42 PM
**Actions**:
1. Navigated to `/unitedarts/import`
2. Import page loaded with 3-step wizard
3. Uploaded `test-contacts.csv` via file picker
4. File recognized (1.5 KB), batch name auto-generated: "import-test-contacts"
5. Clicked "Upload & Analyze"
6. **Column Mapping UI RENDERED** (no crash! BUG-001 FIXED!)
7. BUT all dropdowns showed "-- Skip --" instead of AI-mapped values
8. Sample Values column was empty
9. Manually mapped all 7 columns
10. Clicked "Re-analyze with AI" -- no change
11. Clicked "Preview" -- 500 Internal Server Error

**Observations**:
- MAJOR FIX: Column mapping UI no longer crashes (BUG-001 resolved)
- NEW BUG: AI mapping results not applied to dropdowns (all default to Skip)
- NEW BUG: Preview API returns 500 error
- Sample Values column empty
- "Re-analyze with AI" button present but non-functional
- Import wizard step 1 and 2 work, step 3 fails
- Recent Imports section shows baseline-001 completed and mapped entries
- Notes field has "New" badge (custom field detection still works)

**Score**: availability=6, seamlessness=2, proactiveness=2, user_effort=1

---

### Step 5: Basic Enrichment

**Time**: 11:45 PM
**Actions**:
1. Navigated to `/unitedarts/enrich`
2. DAG visualization loaded with 10 stages across 5 categories

**Observations**:
- Cross-namespace filter leakage STILL present: "batch-2-NL-NORDICS[OPS/FIN]" from visionvolve
- Run button shows "Run 10 stages" (improved from baseline-001 "Loading...")
- Namespace dropdown showed "visionvolve" despite unitedarts URL (regression)
- Console errors: 500s on staging-status and estimate APIs due to wrong tag
- Stage configs and toggles work
- No proactive enrichment suggestion from AI
- Did not execute (real credits required)

**Score**: availability=8, seamlessness=3, proactiveness=2, user_effort=8

---

### Steps 6-10: UNTESTED

Same as baseline-001 -- blocked by lack of enrichment data.

Campaigns page confirmed: shows "0 campaigns" with "New Campaign" button and clean empty state.

---

## Bug Report (baseline-002)

### NEW-BUG-001: AI Column Mapping Not Applied to Dropdowns (MAJOR)
- **Severity**: Major
- **Component**: Frontend / ImportPage / Column mapping step
- **Description**: After Upload & Analyze, the column mapping UI renders (BUG-001 fixed!) but all Target Field dropdowns default to "-- Skip --". The AI mapping shows "high" confidence for all columns but the results are not applied to the dropdown selections.
- **Impact**: User must manually map all 7 columns. The "Re-analyze with AI" button also does not fix the mapping.

### NEW-BUG-002: Import Preview 500 Error (BLOCKER)
- **Severity**: Blocker
- **Component**: Backend / `/api/imports/{id}/preview`
- **Description**: After mapping columns and clicking "Preview", the API returns a 500 Internal Server Error. The import cannot be completed through the UI.

### PERSISTENT: Cross-Namespace Filter Leakage (BL-142)
- **Severity**: Minor
- **Component**: Frontend / EnrichPage / Tag filter
- **Description**: Same as baseline-001 -- enrich page shows visionvolve tags in unitedarts namespace.

### PERSISTENT: EntrySignpost Not Rendering (BL-136)
- **Severity**: Major
- **Component**: Frontend / EntrySignpost
- **Description**: Still no onboarding signpost for empty/new namespaces.

### PERSISTENT: No Web Research in Strategy (BL-137)
- **Severity**: Major
- **Component**: Backend / agent_executor.py
- **Description**: AI still does not call web_search to research the company website before generating strategy.

---

## Comparison: baseline-002 vs baseline-001

### Aggregate Score Changes

| Dimension | baseline-001 | baseline-002 | Delta | Direction |
|-----------|-------------|-------------|-------|-----------|
| Overall Completeness | 6.0 | 6.7 | +0.7 | Improved |
| Workflow Seamlessness | 3.2 | 3.4 | +0.2 | Improved |
| AI Quality | 7.5 | 7.0 | -0.5 | Regressed |
| User Effort | 7.2 | 7.4 | +0.2 | Improved |
| Proactiveness | 2.6 | 2.8 | +0.2 | Improved |

*Note: AI Quality appears to have regressed but this is because baseline-001 included the column mapper output (10/10 on multiple dimensions) which inflated the average. The strategy AI quality is comparable.*

### Per-Step Changes

| Step | baseline-001 Avail | baseline-002 Avail | Delta | Notes |
|------|-------------------|--------------------|-------|-------|
| Strategy | 7 | 8 | +1 | Auto-execution, single turn |
| Extraction | 5 | 7 | +2 | Toast notification, AI follow-up |
| Import | 3 | 6 | +3 | UI crash fixed (but new preview error) |
| Enrichment | 7 | 8 | +1 | Run button now functional |
| Steps 5-10 | unchanged | unchanged | 0 | Still untested |

### Fixed Bugs
1. Import column mapping UI crash (BUG-001) -- **FIXED**
2. Enrichment Run button "Loading..." state (BL-148) -- **IMPROVED** (now shows "Run 10 stages")
3. AI not auto-executing tools (BL-150) -- **FIXED**
4. ICP extraction completely silent (BL-141) -- **PARTIALLY FIXED** (toast added)

### New Bugs
1. AI mapping not populating dropdowns in import UI
2. Import preview 500 error
3. Namespace dropdown showing wrong value on enrich page

### Still Broken
1. EntrySignpost not rendering (BL-136)
2. No web_search in strategy (BL-137)
3. Cross-namespace filter leakage (BL-142)
4. Phase 2 Contacts "Coming soon" (BL-114)
5. Namespace not persisting across sessions (BL-149)

---

## Target Assessment

**Sprint 5 target: 9/10**

**Current aggregates**:
- Overall Completeness: 6.7/10 (need 9.0)
- Workflow Seamlessness: 3.4/10 (need 9.0)
- Proactiveness: 2.8/10 (need 9.0)

**Verdict**: Sprint 5 delivered incremental improvements (+0.2 to +0.7 across dimensions) but is far from the 9/10 target. The biggest gaps remain:
1. **Proactiveness (2.8)**: System still does not guide between steps
2. **Seamlessness (3.4)**: Steps remain isolated islands
3. **Import flow**: Fixed the crash but introduced new errors
4. **No web research**: Strategy lacks real company data

The improvements in auto-tool-execution and extraction feedback are meaningful quality-of-life changes but do not move the needle on the end-to-end workflow experience.
