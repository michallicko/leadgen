# Sprint 5 Review and Test Strategy

**Date**: 2026-03-03
**Status**: Planning review complete
**Source**: Synthesized from backlog analysis, test infrastructure survey, and sprint plan review
**Parent Plan**: `docs/plans/sprint-5-plan.md`, `docs/plans/sprint-5-breakdown.md`

---

## 1. Backlog Health Check

### Sprint 5.1 Is Empty

Sprint 5.1 has **0 items assigned** in the backlog service. The sprint definition in `docs/plans/sprint-5-breakdown.md` describes 4 items (deploy fix, import format fix, web search prompt fix, E2E framework), but none were created as discrete backlog entries or moved into Sprint 5.1.

**Recommendation**: Either create 4 new items in Sprint 5.1, or merge Sprint 5.1's scope into Sprint 5.2 as a "Phase 0" since Sprint 5.2 already contains the relevant bug fixes (BL-134, BL-137, BL-138). The deploy fix and E2E framework are infrastructure tasks that have no corresponding backlog items at all.

### Stale "Building" Items

**8 items** in Backlog are stuck in "Building" status with no active agent claims. These should be reset to Idea:

| Item | Title | Notes |
|------|-------|-------|
| BL-004 | — | Stale since Sprint 1 era |
| BL-005 | — | Stale since Sprint 1 era |
| BL-015 | — | No agent claim |
| BL-017 | — | No agent claim |
| BL-020 | — | No agent claim |
| BL-025 | — | No agent claim |
| BL-026 | — | No agent claim |
| BL-045 | Enrichment field audit | Superseded by migration work |

### Orphaned Sprint 4 Items

**2 items** from Sprint 4 are Spec'd but were never built:

| Item | Title | Recommendation |
|------|-------|---------------|
| BL-123 | Mermaid rendering | Move to Backlog or defer to Sprint 6+ |
| BL-124 | Sticky toolbar | Move to Backlog or defer to Sprint 6+ |

### Missing E2E Test Backlog Items

There are **no backlog items** for E2E test infrastructure improvements in any Sprint 5.x sub-sprint. The sprint-5.1-specs.md describes an "E2E Framework" task but it has no corresponding backlog entry. Items to create:

- E2E auth fixture extraction (reusable login helper)
- Visual regression baseline infrastructure
- Sprint 5.x acceptance test specs
- Scoring schema integration helpers

### Dependency Graph Health

The dependency graph is **clean** -- no circular dependencies detected. Cross-sprint dependencies are correctly declared. All dependency chains flow forward (5.1 -> 5.2 -> 5.3).

---

## 2. Full Dependency Map

### Cross-Sprint Dependencies (5.2 -> 5.3)

```
BL-134 (5.2: Import Crash Fix)    --> BL-126 (5.3: Playbook Import)
BL-134 (5.2: Import Crash Fix)    --> BL-146 (5.3: Auto-Enrich Trigger)
BL-136 (5.2: EntrySignpost Fix)   --> BL-111 (5.3: Smart Empty States)
BL-136 (5.2: EntrySignpost Fix)   --> BL-121 (5.3: Simplified Onboarding)
BL-142 (5.2: Namespace Filter)    --> BL-165 (5.3: gap: Auto-Chain Triage)
BL-142 (5.2: Namespace Filter)    --> BL-166 (5.3: gap: Real-Time Progress)
BL-148 (5.2: Enrich Run Button)   --> BL-165 (5.3: gap: Auto-Chain Triage)
BL-148 (5.2: Enrich Run Button)   --> BL-166 (5.3: gap: Real-Time Progress)
```

### Sprint 5.3 Internal Layers

```
Layer 0 (no internal deps):
  BL-135 (Proactive Suggestions)
  BL-141 (ICP Extraction Feedback)
  BL-143 (Phase 2 Contacts)
  BL-145 (Strategy-Aware Messages)
  BL-149 (Namespace Persistence)
  BL-151 (Save Progress Indicator)

Layer 1 (depends on Layer 0):
  BL-114 (Auto-Advance)          <-- BL-141, BL-143
  BL-139 (ICP to Triage)         <-- BL-141
  BL-117 (Campaign Config)       <-- BL-145
  BL-147 (Campaign Auto-Setup)   <-- BL-139, BL-145
  BL-167 (Msg Personalization)   <-- BL-145
  BL-126 (Playbook Import)       <-- BL-143 (+ BL-134 from 5.2)

Layer 2 (depends on Layers 0-1):
  BL-116 (apply_icp_filters)     <-- BL-139
  BL-146 (Auto-Enrich Trigger)   <-- BL-134 (5.2), BL-139
  BL-164 (Chat-Initiated Actions)<-- BL-135, BL-139, BL-145, BL-146

Layer 3 (capstone):
  BL-144 (Workflow Orchestrator)  <-- BL-135, BL-139, BL-145, BL-146, BL-147
```

### Critical Path

```
BL-141 --> BL-139 --> BL-146 --> BL-144
```

With BL-134 (from 5.2), BL-135, BL-145, and BL-147 as parallel feeders into BL-144.

**Critical path duration**: S + M + M + XL = ~8 working days (reduced to ~5 with BL-144 descoped to Phase A).

---

## 3. Sprint Review Verdicts

### Sprint 5.1: READY (with mandatory spec revision)

| Aspect | Verdict | Detail |
|--------|---------|--------|
| Deploy fix | APPROVED | Highest-impact single change. `deploy-revision.sh` fix is correct and complete. |
| Import format fix | NEEDS REVISION | The spec's simple prefix-stripping rule (`company.X -> company_X`) is wrong. An explicit bidirectional mapping table (`CLAUDE_TO_FRONTEND` / `FRONTEND_TO_CLAUDE`) is required per EM challenge. `company.domain` -> `domain`, `company.industry` -> `industry`, `company.hq_city` -> `location`, etc. |
| Web search fix | APPROVED (with caveat) | Prompt compliance is probabilistic (~85%), not deterministic. Accept 8/10 AI quality, not 9/10. |
| E2E framework | APPROVED | Minor improvements: replace `networkidle` waits with element waits, add positive assertions. |

**Mandatory action before implementation**: Update `docs/plans/sprint-5.1-specs.md` with the EM's bidirectional mapping table for the import format fix.

**Score target**: ~7.0/10 grand average (confidence: 85%)

### Sprint 5.2: READY (minor adjustments)

| Aspect | Verdict | Detail |
|--------|---------|--------|
| Track 1: Bug fixes | APPROVED | 5 items, high parallelism, well-scoped. All S-effort. |
| Track 2: AI quality | APPROVED | 3 items, mostly parallel. BL-150 upgraded to Must Have. |
| BL-138 scope | NEEDS DOWNSCOPE | Error toast only -- BL-121 in 5.3 replaces the template selector. |
| Merge ordering | ATTENTION | BL-137 and BL-150 both touch `playbook_service.py`. Merge BL-137 first. |
| Riskiest item | BL-150 | AI behavior change is non-deterministic. Write behavioral tests, not output-exact tests. |

**Score target**: ~7.4/10 grand average (confidence: 80%)

### Sprint 5.3: NEEDS WORK (scope reduction required)

**21 items is too many for a single sub-sprint.** The EM and PM reviews both flagged this. Recommended split:

#### Sprint 5.3a (8 items, critical path)

| Item | Title | Effort | Rationale |
|------|-------|--------|-----------|
| BL-141 | ICP Extraction Feedback | S | Gate for BL-139, BL-114 |
| BL-143 | Phase 2 Contacts | L | May already be built -- test first |
| BL-114 | Auto-Advance to Contacts | S | May already be built -- test first |
| BL-139 | ICP to Triage Rules | M | Critical integration piece |
| BL-145 | Strategy-Aware Messages | M | Foundation for message quality |
| BL-147 | Campaign Auto-Setup | M | Connects enrichment to outreach |
| BL-135 | Proactive Suggestions (trigger points 1-3) | L | Highest-impact seamlessness item |
| BL-144 | Workflow Orchestrator Phase A | S | Descoped to computed-on-read endpoint only |

**Score target for 5.3a**: ~7.9/10 grand average (confidence: 75%)

#### Sprint 5.3b (13 items, polish + remaining triggers)

| Item | Title | Effort | Notes |
|------|-------|--------|-------|
| BL-121 | Simplified Onboarding | S | 2-field form |
| BL-116 | apply_icp_filters Chat Tool | S | Depends on BL-139 |
| BL-117 | Auto-Populate Campaign Config | S | Depends on BL-145 |
| BL-146 | Auto-Enrichment with Cost Gate | M | Depends on BL-134, BL-139 |
| BL-135 | Proactive Suggestions (trigger points 4-7) | M | Second pass |
| BL-111 | Smart Empty States | M | Focus on Campaigns + Enrich pages |
| BL-149 | Namespace Persistence | S | localStorage write |
| BL-151 | Save Progress Indicator | S | First to cut |
| BL-126 | Playbook Import | M | Depends on BL-134, BL-143 |
| BL-131 | Credit Cost Estimator | S | Absorbed into BL-146 |
| BL-164 | Chat-Initiated Actions (gap) | L | Merge into BL-135 scope |
| BL-165 | Auto-Chain Triage (gap) | S | Merge into BL-139 scope |
| BL-166 | Real-Time Progress (gap) | M | New gap item |
| BL-167 | Msg Personalization Audit (gap) | M | New gap item |

**Score target for 5.3a+5.3b**: ~8.2/10 grand average (confidence: 65%)

#### Key 5.3 Decisions Required

1. **BL-144 Phase A** must be descoped to a computed-on-read endpoint (S effort, not XL). Full state machine is Sprint 6.
2. **BL-139** matching semantics must be defined before implementation. Recommendation: `contains-any-word` for v1 (freetext ICP industries matched against company industry via substring).
3. **BL-143/BL-114** may already be built -- `PhasePanel.tsx` has a fully implemented `ContactsPhasePanel` (395 lines) and `PlaybookPage.tsx` has auto-advance logic (lines 361-377). Test on staging after 5.1 deployment before assigning engineers.
4. **BL-135** needs 2 engineers: one for infrastructure (`useWorkflowStatus()` hook, suggestion component system) and one for trigger point implementations.
5. **Merge BL-164 into BL-135** (duplicate scope: chat-initiated actions are a subset of proactive suggestions).
6. **Merge BL-165 into BL-139** (auto-chain triage is a natural extension of ICP-to-triage rules).

---

## 4. Playwright Visual Test Strategy

### Current State Assessment

| Aspect | Status | Detail |
|--------|--------|--------|
| Spec files | 4 files | `playbook.spec.ts`, `campaign-outreach.spec.ts`, `company-detail.spec.ts`, `sprint-3b-acceptance.spec.ts` |
| Test count | 30+ tests | Across all spec files |
| Auth pattern | API login + localStorage | `page.request.post()` -> inject tokens via `page.evaluate()` |
| Staging config | `playwright-staging.config.ts` | Single worker, no parallel, 60s timeout, 15s expect timeout |
| Scoring schema | Comprehensive | `scoring-schema.json` with 5 dimensions, 10 steps, LLM quality sub-scores |
| Visual regression | NOT SET UP | No `toHaveScreenshot()` calls, no baseline images |
| Reusable fixtures | NONE | `login()` duplicated across spec files, no page objects |
| Test data isolation | NONE | Tests share `visionvolve` namespace, no cleanup |

### Proposed Directory Structure

```
frontend/e2e/
  baselines/
    sprint-5.1/          # Baseline screenshots after 5.1 deployment
    sprint-5.2/          # Updated baselines after 5.2
    sprint-5.3a/         # Updated baselines after 5.3a
  fixtures/
    auth.ts              # Reusable login fixture
    namespace.ts         # Namespace switching fixture
    test-data.ts         # Test CSV, test contacts, mock data
  helpers/
    scoring.ts           # Scoring schema integration helpers
    screenshot.ts        # Screenshot capture + baseline comparison
  sprint-5.1-verification.spec.ts
  sprint-5.2-bugfixes.spec.ts
  sprint-5.2-ai-quality.spec.ts
  sprint-5.3a-integration.spec.ts
  sprint-5.3b-polish.spec.ts
  playbook.spec.ts       # Existing (keep)
  campaign-outreach.spec.ts  # Existing (keep)
  company-detail.spec.ts     # Existing (keep)
  sprint-3b-acceptance.spec.ts  # Existing (keep)
```

### Reusable Auth Fixture

Extract from the duplicated pattern in `playbook.spec.ts` and other spec files:

```typescript
// fixtures/auth.ts
import { type Page } from '@playwright/test'

const BASE = process.env.BASE_URL ?? 'https://leadgen-staging.visionvolve.com'
const API = process.env.API_URL ?? BASE

export async function login(page: Page, namespace = 'unitedarts') {
  const resp = await page.request.post(`${API}/api/auth/login`, {
    data: { email: 'test@staging.local', password: 'staging123' },
  })
  const body = await resp.json()
  await page.goto(BASE)
  await page.evaluate(
    ({ access, refresh, user }) => {
      localStorage.setItem('lg_access_token', access)
      localStorage.setItem('lg_refresh_token', refresh)
      localStorage.setItem('lg_user', JSON.stringify(user))
    },
    {
      access: body.access_token,
      refresh: body.refresh_token,
      user: body.user,
    },
  )
  await page.goto(`${BASE}/${namespace}/`)
}

export { BASE, API }
```

### Visual Regression Configuration

Add to `playwright-staging.config.ts`:

```typescript
expect: {
  timeout: 15_000,
  toHaveScreenshot: {
    maxDiffPixelRatio: 0.01,  // Strict: 1% pixel tolerance
    threshold: 0.2,            // Per-pixel color threshold
  },
},
```

**Baseline management approach**:
- Store baselines per sprint milestone in `frontend/e2e/baselines/sprint-{N}/`
- Update baselines only when features intentionally change UI
- Use `expect(page).toHaveScreenshot('name.png')` for visual regression
- CI runs compare against committed baselines

---

## 5. Test Strategy Per Sprint

### Sprint 5.1 Test Strategy

**Goal**: Validate deployment pipeline fix + create baseline-003 across all 10 workflow steps.

```
sprint-5.1-verification.spec.ts:

  1. Deployment Verification
     - Assert Sprint 5 JS bundle is served (not stale Sprint 4 build)
       > Check for a Sprint 5 component in DOM (e.g., EntrySignpost, WorkflowSuggestions)
     - Assert EntrySignpost component exists in DOM on empty namespace
     - Assert PlaybookOnboarding renders (not "Coming soon" on Phase 2)
     - Screenshot: deployment-verified.png

  2. Import Format Fix Verification
     - Upload test CSV (tests/baseline-eval/test-contacts.csv)
     - Verify column mapping step renders (no crash, no blank page)
     - Verify AI-suggested mappings match frontend TARGET_OPTIONS values
       > company.domain -> domain, company.industry -> industry,
       > company.hq_city -> location, company.company_size -> employee_count
     - Verify all 7 columns mapped with >= 0.95 confidence
     - Screenshot: import-mapping-step.png

  3. Web Search Verification (non-deterministic -- run 3x)
     - Navigate to Playbook, trigger strategy generation for unitedarts.cz
     - Assert web_search tool was called (check tool call indicators in chat UI)
     - Assert no placeholder text ([X], [Y]) in generated strategy
     - Assert strategy mentions real company details (verifiable facts)
     - Screenshot: strategy-with-research.png
     - NOTE: Accept ~85% compliance rate. If 2/3 runs show web_search, PASS.

  4. Baseline-003 Scoring Run
     - Execute the 10-step workflow per ideal-workflow.md
     - Capture screenshots at each step (10 screenshots minimum)
     - Record scores per scoring-schema.json (5 dimensions x 10 steps)
     - Compare against baseline-002 scores
     - Output: tests/baseline-eval/baseline-003/scores.json
```

### Sprint 5.2 Test Strategy

**Goal**: Verify all 8 bug fixes + AI quality improvements. Two spec files separate deterministic bug fixes from non-deterministic AI tests.

```
sprint-5.2-bugfixes.spec.ts (Track 1: Bug Fixes, deterministic):

  1. BL-134: Import Column Mapping
     - Upload CSV -> mapping step renders -> all 7 columns have correct targets
     - Company fields map correctly:
       company.domain -> domain
       company.industry -> industry
       company.hq_city -> location
       company.company_size -> employee_count
       email_address -> email
       phone_number -> phone
     - Preview shows correct data -> Execute import succeeds
     - Screenshots: import-upload.png, import-mapping.png, import-preview.png

  2. BL-136: EntrySignpost
     - Navigate to empty namespace -> EntrySignpost renders
     - 3 paths visible: Build Strategy, Import Contacts, Browse Templates
     - Each path navigates to the correct destination
     - Screenshot: entry-signpost-empty-namespace.png

  3. BL-138: Template Application
     - Start PlaybookOnboarding -> select template -> apply
     - Either: template applies successfully OR error toast shown (not silent failure)
     - NOTE: Downscoped to error toast only. Full template flow is BL-121 (Sprint 5.3).
     - Screenshot: template-application.png

  4. BL-142: Namespace Filter
     - Switch to unitedarts namespace -> navigate to Enrich page
     - Tag filter dropdown shows ONLY unitedarts tags (no visionvolve tags)
     - API verification: GET /api/tags?namespace=unitedarts returns only unitedarts tags
     - Screenshot: enrich-namespace-tags.png

  5. BL-148: Enrichment Run Button
     - Navigate to Enrich page -> Run button loads within 2 seconds
     - Run button shows configuration (stages, cost estimate)
     - No perpetual "Loading..." spinner
     - Screenshot: enrich-run-ready.png


sprint-5.2-ai-quality.spec.ts (Track 2: AI Quality, non-deterministic):

  6. BL-137: Web Research in Strategy
     - Generate strategy for unitedarts.cz
     - Assert: strategy mentions real company details
       > Losers Cirque Company, DaeMen, Divadlo BRAVO! (known unitedarts.cz acts)
     - Assert: no [X] or [Y] placeholders in any section
     - Assert: competitive analysis names real Czech competitors
     - Timeout: 120s (strategy generation is slow with web research)
     - Screenshot: strategy-sections-with-research.png (full page)

  7. BL-140: Tool Call Limit
     - Request full 9-section strategy in single message
     - Assert: all 9 sections written in ONE user turn (no rate limit message)
     - Assert: no "I've reached my limit" or similar rate-limit text
     - Timeout: 180s (9 sections with tool calls)
     - Screenshot: strategy-9-sections-complete.png

  8. BL-150: Auto-Execute Tools
     - Complete PlaybookOnboarding wizard -> AI receives auto-message
     - Assert: AI starts tool execution immediately (no "I'll build your strategy" text-only)
     - Assert: first tool call indicator appears within 10 seconds
     - Assert: tool execution spinner visible before any text-only response
     - Timeout: 30s for tool call to appear
     - Screenshot: auto-execute-first-tool.png
```

### Sprint 5.3a Test Strategy

**Goal**: Verify integration between strategy, extraction, enrichment, and campaign. Verify proactive AI suggestions.

```
sprint-5.3a-integration.spec.ts:

  Track 3: Extraction + Phase Transitions

  1. BL-141: ICP Extraction Feedback
     - Click "Extract ICP" action in playbook
     - Confirmation side panel appears (not centered modal)
     - Panel shows extracted data: industries, geography, company size, job titles
     - Panel has pill tags for each ICP criterion
     - "Confirm & Continue" button + "Edit in Strategy" link visible
     - Toast notification confirms successful extraction
     - Screenshot: icp-extraction-feedback.png

  2. BL-143: Phase 2 Contacts
     - Navigate to Playbook Phase 2 (Contacts tab)
     - Contacts list renders (NOT "Coming soon" text)
     - Contacts shown with ICP matching indicators
     - NOTE: Test on staging first -- may already be built (ContactsPhasePanel, 395 lines)
     - Screenshot: playbook-phase2-contacts.png

  3. BL-114: Auto-Advance to Contacts
     - Extract ICP -> dismiss confirmation panel -> observe navigation
     - URL auto-updates to /:namespace/playbook/contacts
     - PhaseIndicator highlights Contacts phase (active state)
     - NOTE: Test on staging first -- PlaybookPage.tsx lines 361-377 may already handle this
     - Screenshot: auto-advance-to-contacts.png

  Track 4: Cross-Feature Integration

  4. BL-139: ICP to Triage Rules
     - Run triage after L1 enrichment completes
     - Assert: triage uses ICP criteria from strategy (not hardcoded defaults)
     - Assert: companies matching ICP industries marked "Triage: Passed"
     - Assert: companies NOT matching ICP criteria marked "Triage: Review" or "Disqualified"
     - API test: GET /api/companies -> verify triage_status reflects ICP rules
     - NOTE: Matching semantics = contains-any-word (substring match for v1)

  5. BL-145: Strategy-Aware Messages
     - Generate messages for a campaign that has a linked strategy
     - Assert: messages reference strategy talking points (value proposition, messaging framework)
     - Assert: tone matches strategy messaging framework (professional/warm, not salesy)
     - Assert: at least 1 verifiable detail from strategy appears in message body
     - Screenshot: strategy-aware-message.png

  6. BL-147: Campaign Auto-Setup
     - After triage completes, trigger campaign creation flow
     - Assert: campaign created with qualified (Triage: Passed) contacts pre-assigned
     - Assert: campaign name derived from strategy title or namespace
     - Assert: campaign generation_config pre-populated from strategy
     - Screenshot: campaign-auto-setup.png

  Track 5: Proactive AI (trigger points 1-3)

  7. BL-135: Proactive Suggestions
     - Trigger Point 1: After strategy save
       > Chat shows suggestion: "Extract ICP?" with action button (cyan accent)
       > Screenshot: suggestion-after-strategy.png
     - Trigger Point 2: After ICP extraction
       > Chat shows suggestion: "View Contacts" with navigation button
       > Screenshot: suggestion-after-extraction.png
     - Trigger Point 3: After contact import
       > Chat shows suggestion: "Run Enrichment" with cost estimate
       > Screenshot: suggestion-after-import.png
     - All suggestions use cyan (#00B8CF) accent to distinguish from user/brand actions

  8. BL-144 Phase A: Workflow Status Endpoint
     - GET /api/workflow/status returns correct state for current namespace
     - State reflects: which steps are complete, which is current, which are pending
     - API test: verify state transitions through the workflow
       > Before strategy: all steps pending
       > After strategy: step 1 complete, step 2 current
       > After extraction: steps 1-2 complete, step 3 current
     - NOTE: Computed on read, no state table. Queries existing models.
```

### Sprint 5.3b Test Strategy

**Goal**: Verify polish items + remaining proactive trigger points.

```
sprint-5.3b-polish.spec.ts:

  1. BL-135 Trigger Points 4-7
     - TP4: After enrichment completes -> chat suggests "Create Campaign" with CTA button
     - TP5: After campaign creation -> chat suggests "Generate Messages" with contact count
     - TP6: After message generation -> chat suggests "Review Messages" with approve/reject buttons
     - TP7: After message review -> chat suggests "Launch Campaign" with send estimate
     - Screenshot per trigger point: suggestion-after-enrichment.png, etc.

  2. BL-121: Simplified Onboarding
     - First visit to empty namespace -> 2-field form renders
       > Field 1: Business description (textarea)
       > Field 2: Primary challenge (textarea)
     - No template selector step (removed -- was BL-138 scope)
     - Submit form -> AI starts strategy generation immediately
     - Screenshot: simplified-onboarding.png

  3. BL-149: Namespace Persistence
     - Work in unitedarts namespace -> close tab -> reopen browser/tab
     - Assert: lands in unitedarts namespace (reads from localStorage)
     - Assert: no manual namespace dropdown switch required
     - Screenshot: namespace-persisted.png

  4. BL-111: Smart Empty States
     - Empty Campaigns page -> SmartEmptyState component renders
       > CTA button to "Create First Campaign" or "Go to Playbook"
     - Empty Enrich page -> SmartEmptyState with guidance
       > CTA to "Import Contacts First" if no contacts, or "Run Enrichment" if contacts exist
     - Screenshot: smart-empty-campaigns.png, smart-empty-enrich.png

  5. BL-116: apply_icp_filters Chat Tool
     - In playbook chat, type "filter contacts by ICP"
     - Assert: AI calls apply_icp_filters tool (not a generic text response)
     - Assert: contacts list updates to show only ICP-matched contacts
     - Screenshot: icp-filter-applied.png

  6. BL-146: Auto-Enrichment with Cost Gate
     - After import, navigate to enrichment
     - Cost estimate shown before any execution
     - "Approve & Start" button (never auto-execute without cost gate)
     - After approval, enrichment stages run in sequence
     - Screenshot: cost-gate-approval.png

  7. BL-126: Playbook Import
     - From Playbook Phase 2 (Contacts), click "Import Contacts"
     - Import wizard opens in-context (not separate page navigation)
     - After import, contacts appear in Phase 2 list
     - Screenshot: playbook-inline-import.png
```

---

## 6. Visual Regression Strategy

### Approach

Screenshot baselines captured per sprint milestone. Each sprint's tests produce named screenshots that serve as both documentation and regression baselines.

### Baseline Lifecycle

| Event | Action |
|-------|--------|
| Sprint 5.1 deploys | Capture baseline-003 screenshots (10 workflow steps). Store in `baselines/sprint-5.1/`. |
| Sprint 5.2 deploys | Run 5.1 tests first (regression check). Capture 5.2 screenshots. Store in `baselines/sprint-5.2/`. |
| Sprint 5.3a deploys | Run 5.1 + 5.2 tests (regression). Capture 5.3a screenshots. Store in `baselines/sprint-5.3a/`. |
| Feature intentionally changes UI | Update affected baselines. Commit updated screenshots with the feature PR. |

### Screenshot Comparison Configuration

```typescript
// In playwright-staging.config.ts
expect: {
  timeout: 15_000,
  toHaveScreenshot: {
    maxDiffPixelRatio: 0.01,   // 1% tolerance (strict)
    threshold: 0.2,             // Per-pixel color threshold
    animations: 'disabled',     // Freeze CSS animations for determinism
  },
},
```

### Non-Deterministic Test Handling

AI-generated content varies between runs. For AI quality tests:

- **Do NOT use visual regression** on AI output text (it will always differ)
- **DO use structural assertions**: element exists, section count, no placeholder patterns
- **DO use behavioral assertions**: tool was called, response appeared within timeout
- **Run non-deterministic tests 3x**: pass if 2/3 succeed (85% compliance threshold)
- **Separate AI tests into dedicated spec files** (`sprint-5.2-ai-quality.spec.ts`) so deterministic bug-fix tests can run independently

---

## 7. Recommended Actions (Priority Order)

| # | Priority | Action | Owner | Detail |
|---|----------|--------|-------|--------|
| 1 | MANDATORY | Update sprint-5.1-specs.md with EM mapping table | Lead | BL-134 import fix spec is wrong. Needs `CLAUDE_TO_FRONTEND` / `FRONTEND_TO_CLAUDE` bidirectional mapping. |
| 2 | MANDATORY | Split Sprint 5.3 into 5.3a and 5.3b | Lead | Create 2 sprints in backlog. 5.3a = 8 critical path items. 5.3b = 13 polish items. |
| 3 | HIGH | Decide Sprint 5.1 fate | Lead | Either: (a) create 4 backlog items and populate Sprint 5.1, or (b) merge scope into Sprint 5.2 Phase 0. |
| 4 | HIGH | Write BL-144 Phase A spec | PM/EM | Descoped to computed-on-read `GET /api/workflow/status` endpoint. S effort. |
| 5 | HIGH | Define BL-139 matching semantics | PM | Recommendation: `contains-any-word` substring match for v1. Document in spec. |
| 6 | HIGH | Downscope BL-138 | PM | Error toast only. Full template flow removed (BL-121 replaces it in 5.3). |
| 7 | HIGH | Create E2E test infrastructure backlog items | Lead | At minimum: auth fixture, visual regression setup, scoring helpers. |
| 8 | MEDIUM | Reset 8 stale Building items to Idea | Lead | BL-004, BL-005, BL-015, BL-017, BL-020, BL-025, BL-026, BL-045 |
| 9 | MEDIUM | Move BL-123/BL-124 to Backlog | Lead | Sprint 4 orphans. Spec'd but never built. |
| 10 | MEDIUM | Test BL-143/BL-114 on staging after 5.1 deploy | QA | May already be implemented. If working, mark Done and save ~3 engineer-days. |
| 11 | MEDIUM | Merge BL-164 into BL-135 | PM | Chat-initiated actions are a subset of proactive suggestions. |
| 12 | MEDIUM | Merge BL-165 into BL-139 | PM | Auto-chain triage is a natural extension of ICP-to-triage rules. |
| 13 | LOW | Assign 2 engineers to BL-135 | EM | One for infrastructure (hook + component system), one for trigger points. |

---

## 8. Score Trajectory (Revised After Review)

### Grand Average Projection

| Milestone | Grand Avg | Confidence | Key Risk |
|-----------|:---------:|:----------:|----------|
| Baseline-002 (current) | 5.5 | -- | -- |
| After Sprint 5.1 | ~7.0 | 85% | Web search compliance (~85% not 100%) |
| After Sprint 5.2 | ~7.4 | 80% | AI behavior non-deterministic (BL-150) |
| After Sprint 5.3a | ~7.9 | 75% | BL-135 scope (L item), BL-144 deps |
| After Sprint 5.3a+b | ~8.2 | 65% | Cumulative risk across 21+ items |
| Sprint 6 target | ~8.5 | 55% | Closed-loop learning + auto-transitions |
| Sprint 7 target | ~9.0 | 45% | Full polish, back-half equalized |

### Per-Dimension Projection

| Dimension | Baseline-002 | After 5.1 | After 5.2 | After 5.3a | After 5.3a+b | Sprint 6 |
|-----------|:-----------:|:---------:|:---------:|:----------:|:------------:|:--------:|
| Completeness | 6.7 | 8.0 | 8.5 | 8.5 | 8.5 | 9.0 |
| Seamlessness | 3.4 | 6.2 | 6.5 | 7.5 | 8.0 | 9.0 |
| AI Quality | 7.0 | 7.5 | 8.0 | 8.0 | 8.5 | 9.0 |
| User Effort | 7.4 | 8.1 | 8.5 | 8.5 | 9.0 | 9.5 |
| Proactiveness | 2.8 | 5.3 | 5.5 | 7.0 | 8.0 | 9.0 |

### Front-Half vs Back-Half Gap

| Milestone | Steps 1-4 Avg | Steps 5-10 Avg | Gap |
|-----------|:------------:|:--------------:|:---:|
| Baseline-002 | 6.5 | 4.5 | 2.0 |
| After 5.1 | 8.0 | 6.0 | 2.0 |
| After 5.2 | 8.5 | 6.5 | 2.0 |
| After 5.3a | 8.5 | 7.0 | 1.5 |
| After 5.3a+b | 8.5 | 7.5 | 1.0 |
| Sprint 6 | 9.0 | 9.0 | 0.0 |

### Honest Assessment

The path from 5.5 to ~8.0 is well-planned and achievable. The critical path is identified, dependencies are clean, and the PM/EM reviews have produced realistic expectations.

The path from 8.0 to 9.0 requires at least 2 more sprints beyond Sprint 5 (Sprint 6 for auto-transitions and closed-loop learning, Sprint 7 for full polish). The front half of the workflow (steps 1-4: strategy, extraction, import, basic enrichment) will reach 8.5-9.0 after Sprint 5.3. The back half (steps 5-10: triage, deep enrichment, campaign, messages, review, launch) will reach 7.0-7.5. Closing that gap is Sprint 6's primary mission.

The confidence drops at each milestone because:
- Sprint 5.1 is small and well-scoped (85% confidence)
- Sprint 5.2 introduces non-deterministic AI changes (80%)
- Sprint 5.3a has a complex dependency chain and an L-sized item (75%)
- Sprint 5.3b has 13 items with cumulative integration risk (65%)

**The single biggest risk** is BL-135 (Proactive Suggestions, L effort). It touches every step of the workflow and is the primary driver of the proactiveness score increase from 2.8 to 8.0. If BL-135 underdelivers, proactiveness stays at ~6.0 and the grand average drops to ~7.5 instead of ~8.2.

---

## 9. Appendix: Scoring Schema Reference

The scoring schema at `tests/baseline-eval/scoring-schema.json` defines 5 dimensions:

| Dimension | Scale | Description |
|-----------|-------|-------------|
| **Availability** | 0-10 | Does this feature exist and work? 0=missing, 5=partial/buggy, 10=fully working |
| **Seamlessness** | 0-10 | How smooth is the transition? 0=broken, 5=manual nav, 7=AI suggests, 10=automatic |
| **Proactiveness** | 0-10 | Does the system anticipate next action? 0=nothing, 7=suggests concrete action, 10=auto-proceeds |
| **AI Quality** | 0-10 (nullable) | Quality of AI output. null if no AI at this step. 10=excellent, 7=good, 5=generic |
| **User Effort** | 0-10 | Computed: `10 - (extra_prompts x 1) - (manual_corrections x 2) - (manual_workarounds x 3) - (unnecessary_clarifications x 1)`. Floor 0. |

**10 workflow steps evaluated**: Strategy Creation, Intelligence Extraction, Contact Import, Basic Enrichment, Qualification/Triage, Deep Enrichment, Campaign Creation, Message Generation, Message Review, Campaign Launch.

**LLM output sub-scores** (5 dimensions): Relevance, Accuracy, Specificity, Actionability, Tone.
