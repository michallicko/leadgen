# Leadgen Pipeline — Baseline E2E Test Report

## Test: GTM Full Workflow (unitedarts.cz)

**Date**: 2026-03-02
**System Version**: staging @ `625753a0705ad889172a0582c56b66b4ea919d64`
**Environment**: https://leadgen-staging.visionvolve.com/
**Namespace**: unitedarts (tenant ID: 4c0960ea-553d-4fba-808f-c7f9419f389e)
**Tester**: Automated (Claude Opus 4.6 via Playwright MCP)
**Login**: test@staging.local / staging123
**Duration**: ~15 minutes

---

## Executive Summary

This baseline test evaluated the full 10-step GTM workflow (Strategy -> Contacts -> Enrichment -> Campaign -> Outreach) using unitedarts.cz, a Czech entertainment/circus performance company, as the test subject with 10 real event-industry contacts.

**4 of 10 steps were completed** (login/strategy, intelligence extraction, contact import, enrichment inspection). Steps 5-10 were untested because enrichment execution requires real API credits and ~30 minutes of processing time.

The system demonstrates **strong individual features** -- the AI generates good strategy content (7.5/10), the import column mapper is excellent (0.99 confidence), and the enrichment DAG visualization is comprehensive. However, the **end-to-end flow is fundamentally disconnected**: each feature operates as an isolated island with no proactive guidance connecting them (proactiveness: 2.5/10, seamlessness: 3.2/10). The AI acts as a capable tool-user but not as the "strategist-in-residence" envisioned in the product vision.

**Verdict**: The system has the building blocks for a complete GTM engine but lacks the connective tissue that would make it feel like a guided, AI-driven workflow. The biggest opportunity is not building new features -- it is making existing features work together proactively.

---

## Scorecard

### Aggregate Scores

| Dimension | Score | Interpretation |
|-----------|-------|---------------|
| **Overall Completeness** | 6.0/10 | Most features exist but several have bugs or gaps |
| **Workflow Seamlessness** | 3.2/10 | Steps are isolated; manual navigation between features |
| **AI Quality** | 7.5/10 | Good content when AI is engaged, but no web research |
| **User Effort** | 7.2/10 | Low effort per step, but inflated by skipped steps scoring 10 |
| **Proactiveness** | 2.5/10 | System waits passively; never suggests next step |

### Per-Step Breakdown

| # | Step | Status | Avail. | Seamless | Proactive | AI Qual. | User Effort |
|---|------|--------|--------|----------|-----------|----------|-------------|
| 1 | Login + Navigation | COMPLETED | 8 | 4 | 2 | -- | 7 |
| 2 | GTM Strategy Creation | COMPLETED | 7 | 6 | 5 | 7 | 5 |
| 3 | Intelligence Extraction | COMPLETED | 5 | 3 | 2 | -- | 8 |
| 4 | Contact Import | COMPLETED | 3 | 2 | 5 | 8 | 1 |
| 5 | Basic Enrichment (L1) | PARTIAL | 7 | 3 | 2 | -- | 8 |
| 6 | Qualification/Triage | SKIPPED | 5 | 3 | 2 | -- | 10 |
| 7 | Deep Enrichment (L2+) | SKIPPED | 5 | 3 | 2 | -- | 10 |
| 8 | Campaign Creation | SKIPPED | 7 | 3 | 2 | -- | 10 |
| 9 | Message Generation | SKIPPED | 7 | 3 | 2 | -- | 10 |
| 10 | Message Review + Launch | SKIPPED | 7 | 3 | 2 | -- | 10 |

*Note: Skipped steps score user_effort=10 (no effort spent) and availability based on system inventory evidence that the feature exists. AI Quality is null for steps where no AI output was produced.*

---

## Step-by-Step: Ideal vs Reality

### Step 1: Login + Navigation

**Ideal**: User logs in and is greeted with a clear starting point. New/empty namespace shows an onboarding flow (EntrySignpost) that guides the user to their first action -- build a strategy, import contacts, or browse templates.

**Reality**: Login worked. Session was cached from previous testing, auto-redirecting to `/visionvolve/admin`. After switching to the `unitedarts` namespace via dropdown, the user landed on the contacts page showing 0 contacts with a full filter sidebar (Company Tier, Industry, Company Size, Region, Revenue, Seniority, Department, LinkedIn Activity). No onboarding signpost appeared despite the `EntrySignpost` component existing in code. No guidance on what to do next.

**Gap**: The onboarding flow (EntrySignpost) exists in code but did not render for the empty namespace. A first-time user would see an empty contacts list with an overwhelming filter sidebar and no indication of what to do first.

**Score**: availability=8, seamlessness=4, proactiveness=2, user_effort=7

---

### Step 2: GTM Strategy Creation

**Ideal**: User opens Playbook, describes their business in one message, and the AI proactively researches unitedarts.cz via web_search, generates a complete 9-section strategy document written directly into the editor, explains its findings, and asks for approval. Total: 2 user interactions (describe + approve).

**Reality**: The PlaybookOnboarding wizard appeared (3-step: Discovery, Template, Generate) -- a well-designed guided flow. The user filled in the Discovery form (domain, objective, ICP) and selected a template. However:
1. The template application API (`/api/playbook/apply-template`) failed silently
2. The system fell back to an AI chat message, but the AI said "I'll build your strategy" without actually executing any tools
3. A second explicit prompt was needed to trigger tool execution
4. The AI hit a rate limit of 5 tool calls per turn, completing only 5/9 sections
5. A third prompt was needed to finish the remaining 4 sections
6. **No web_search was used** -- the AI generated from training data, not from researching unitedarts.cz

Total: 4 user interactions (describe + re-prompt + re-prompt + implicit approval)

**Gap**: The ideal was 2 interactions; reality required 4. The AI generated good content but did not research the actual company. No web_search tool was called despite being available. Placeholder text like "[X] agencies" appeared in the output. The rate limit forced multi-turn interaction. The template API failure was silent.

**Score**: availability=7, seamlessness=6, proactiveness=5, ai_quality=7, user_effort=5

---

### Step 3: Intelligence Extraction

**Ideal**: The system auto-extracts structured ICP data from the approved strategy, presents a summary (industries, geography, company size, job titles, qualification signals), and asks for confirmation before proceeding to the contacts phase. Total: 1 user interaction (confirm).

**Reality**: The user manually clicked "Extract ICP" in the Playbook header. The button showed "Extracting..." for ~5-10 seconds, then returned to its default state. No toast notification. No summary of what was extracted. No explanation. Navigating to Phase 2 (Contacts) showed "Coming soon. Use the chat to discuss this phase with your AI strategist." The Select Contacts button was disabled.

**Gap**: Extraction runs but is completely silent -- the user has no idea what was extracted or whether it succeeded. Phase 2 is non-functional, breaking the playbook flow. The ideal was automatic extraction with a confirmation dialog; reality was a silent button click with zero feedback.

**Score**: availability=5, seamlessness=3, proactiveness=2, ai_quality=null, user_effort=8

---

### Step 4: Contact Import

**Ideal**: User uploads an xlsx file, the system auto-maps columns with high confidence, shows a preview with dedup status, the AI flags data quality issues, and the user confirms the import. Total: 2 user interactions (upload + confirm).

**Reality**: The Import page loaded with a clean 3-step wizard. File upload succeeded. Batch name was auto-generated. But:
1. **BLOCKER**: After clicking "Upload & Analyze", the page went completely blank with `TypeError: Cannot read properties of undefined (reading 'length')`
2. Page reload showed a "Resume" button, but clicking it led to another blank rendering
3. The entire import had to be completed via browser JavaScript console (3 manual API calls)
4. The backend worked perfectly -- column mapping was excellent (0.99 confidence), all 10 contacts imported, 8 companies created

The AI column mapper is the best-performing AI feature in the entire test: it correctly identified Notes as a custom field (0.95 confidence) and generated useful warnings about missing domain data and phone format.

**Gap**: The backend is robust and the AI mapping is excellent, but the frontend crashes consistently on the column mapping step. This is a **blocker** -- no user can complete an import through the UI.

**Score**: availability=3, seamlessness=2, proactiveness=5, ai_quality=8, user_effort=1

---

### Step 5: Basic Enrichment (L1)

**Ideal**: AI proactively suggests running L1 enrichment after import, shows a cost estimate, and the user approves with 1 click. Total: 1 user interaction.

**Reality**: The user manually navigated to the Enrich page. The DAG pipeline visualization loaded with a comprehensive layout (10+ stages across 5 categories: Profiling, Qualification, Company Intelligence, Contact Intelligence, Validation). Stage descriptions were clear. However:
1. Cross-namespace filter leakage: the tag filter showed "batch-2-NL-NORDICS[OPS/FIN]" from the visionvolve namespace
2. The "Run" button showed "Loading..." and did not fully load
3. Enrichment was NOT executed (would require real credits and ~30 minutes)

**Gap**: The DAG UI is impressive, but there is no connection from the import step or the playbook. The AI never suggested running enrichment. The cross-namespace filter leakage is a data isolation issue.

**Score**: availability=7, seamlessness=3, proactiveness=2, ai_quality=null, user_effort=8

---

### Steps 6-10: UNTESTED

Steps 6 through 10 (Qualification/Triage, Deep Enrichment, Campaign Creation, Message Generation, Message Review + Campaign Launch) were **not executed** because they require enrichment data that depends on real API calls with credits and processing time.

**Evidence of existence**: All features are confirmed built per system inventory:
- Campaign CRUD with 6-tab detail page (Contacts, Generation, Review, Outreach, Analytics, Settings)
- Message generation via Claude Haiku with cost estimation
- Review queue with approve/reject/edit/regenerate
- Email sending via Resend API
- LinkedIn message queuing for Chrome extension
- Campaign analytics tracking

**What could not be tested**: The end-to-end flow from enriched contacts through campaign creation, message generation, review, and outreach. This is the majority of the workflow by step count (6/10 steps) but the minority by feature novelty (the untested features are more mature and standard CRUD).

---

## Bug Report

### BUG-001: Import Column Mapping UI Crash (BLOCKER)

- **Severity**: Blocker
- **Component**: Frontend / ImportPage / Column mapping step
- **Description**: After uploading a CSV file and clicking "Upload & Analyze", the page goes completely blank. JavaScript error: `TypeError: Cannot read properties of undefined (reading 'length')`.
- **Reproduction**:
  1. Navigate to `/:namespace/import`
  2. Upload any CSV file
  3. Click "Upload & Analyze"
  4. Observe: page goes blank
  5. Reload page, click "Resume" on the saved import
  6. Observe: Step 2 (Map Columns) renders with empty mapping area
- **Impact**: Users cannot complete any data import through the UI. The entire Import wizard is non-functional past Step 1.
- **Workaround**: Call API endpoints directly via browser console (`/api/imports/{id}/preview` and `/api/imports/{id}/execute`).
- **Backend status**: Backend API works perfectly -- upload, mapping (0.99 confidence), preview, and execute all return correct data.

### BUG-002: Template Application API Failure (MAJOR)

- **Severity**: Major
- **Component**: Backend / `/api/playbook/apply-template`
- **Description**: After selecting a strategy template during PlaybookOnboarding, the template application endpoint returns an error. The system silently falls back to AI chat generation.
- **Reproduction**:
  1. Navigate to `/:namespace/playbook` (fresh namespace with no strategy)
  2. Complete Onboarding Step 1 (Discovery) and Step 2 (Template Selection)
  3. Select any template (e.g., "Professional Services -- Local Market")
  4. Observe: "Personalizing your strategy" loading state, then failure
- **Impact**: The template-based strategy creation flow is broken. Users are forced into the AI chat generation path, which requires more prompts and time. The failure is silent -- no error toast or message.
- **Workaround**: AI chat can generate the strategy content, but requires extra prompts.

### BUG-003: Missing Onboarding for Empty Namespace (MAJOR)

- **Severity**: Major
- **Component**: Frontend / EntrySignpost component
- **Description**: When navigating to a namespace with zero contacts, companies, and no strategy, the `EntrySignpost` component does not render. The user lands on an empty contacts page with a full filter sidebar.
- **Reproduction**:
  1. Login and switch to an empty namespace (e.g., `unitedarts` with no data)
  2. Navigate to `/:namespace/` or `/:namespace/contacts`
  3. Observe: empty contacts list with full filter sidebar, no onboarding guidance
- **Impact**: First-time users have no indication of what to do first. The entry signpost was specifically designed to solve this problem but is not triggering.
- **Workaround**: User must discover the Playbook page through navigation menu.

### BUG-004: Cross-Namespace Filter Leakage (MINOR)

- **Severity**: Minor
- **Component**: Frontend / EnrichPage / Tag filter
- **Description**: The enrichment page shows tag filter options from a different namespace (visionvolve's "batch-2-NL-NORDICS[OPS/FIN]" appears in the unitedarts namespace).
- **Reproduction**:
  1. Work in the visionvolve namespace (which has data)
  2. Switch to the unitedarts namespace
  3. Navigate to the Enrich page
  4. Observe: tag filter dropdown shows visionvolve tags
- **Impact**: Low -- cosmetic/confusing but does not cause data corruption or functional issues.

### BUG-005: AI Rate Limit Visible to User (MINOR)

- **Severity**: Minor
- **Component**: Backend / agent_executor.py
- **Description**: The AI agent has a rate limit of 5 tool calls per turn. When generating a 9-section strategy document, the agent can only complete 5 sections before hitting the limit, forcing the user to send another prompt for the remaining 4.
- **Impact**: Increases user effort and breaks the flow of strategy generation. The rate limit is an implementation detail that should not be visible to the user.
- **Workaround**: User sends additional prompts to complete the remaining sections.

---

## LLM Output Quality Analysis

### Output 1: Strategy Document Generation

- **Model**: claude-sonnet-4-5-20250514 (via agent_executor.py)
- **Input**: Company domain (unitedarts.cz), primary objective (event agency leads in CZ/CEE), ICP description, Professional Services template
- **Output**: Complete 9-section GTM strategy (~3000 words)

**Scores**:
| Dimension | Score | Notes |
|-----------|-------|-------|
| Relevance | 8/10 | Strategy is clearly about entertainment/event industry B2B sales |
| Accuracy | 6/10 | Content is plausible but not verified. No web research was performed. Placeholder stats ("[X] agencies") |
| Specificity | 6/10 | Mentions circus, acrobatics, corporate events -- but no named competitors, no real market data |
| Actionability | 7/10 | 90-day action plan with weekly checklist is usable. Channel percentages are specific. KPI tables are concrete. |
| Tone | 8/10 | Professional, consultative, appropriate for B2B strategy document |

**What was good**:
- Well-structured 9-section format covering all essential strategy areas
- ICP segmentation into Primary (Event Agencies) and Secondary (In-House Corporate Teams)
- 3 detailed buyer personas with pain points, channels, and decision roles
- Competitive positioning matrix (vs brokers, local performers)
- Channel strategy with specific percentages (LinkedIn 40%, Email 25%, Events 20%, Partnerships 15%)
- 90-day action plan with weekly milestones and checkpoints

**What was bad**:
- No web research of unitedarts.cz was performed (the `web_search` tool was available but never called)
- Placeholder text: "[X] agencies", "[Y]% revenue" in several places
- Competitive analysis is generic -- no named Czech competitors
- Revenue estimates and market size figures are fabricated (no data source)
- No mention of specific unitedarts.cz acts (Losers Cirque Company, DaeMen, etc.)
- No reference to their Thalia nomination, Got Talent history, or venue (Divadlo BRAVO!)

**Key excerpt** (Executive Summary):
> "This strategy document outlines a comprehensive go-to-market approach for unitedarts.cz, a Czech-based entertainment company specializing in circus and acrobatic performances for corporate and private events. Our primary objective is to generate 20+ qualified leads among event agencies in CZ/CEE."

*Verdict*: Good structure and framework, but the content is from the AI's training data rather than from researching the actual company. A strategy consultant would always research the client's website first.

### Output 2: AI Column Mapping

- **Model**: claude-haiku-3-5-20241022 (via csv_mapper.py)
- **Input**: CSV headers (First Name, Last Name, Organization, Title, Email, Phone, Notes) + 10 sample rows
- **Output**: 7 column mappings with 0.99 overall confidence + 3 warnings

**Scores**:
| Dimension | Score | Notes |
|-----------|-------|-------|
| Relevance | 10/10 | Every mapping is correct and contextually appropriate |
| Accuracy | 10/10 | All 7 columns mapped correctly, including Notes as custom field |
| Specificity | 9/10 | Correctly identified Notes contains "relationship data" worth preserving |
| Actionability | 10/10 | Mapping can be applied directly, no corrections needed |
| Tone | 8/10 | Warnings are clear and professional |

**What was good**:
- All standard fields mapped with 1.0 confidence
- Notes field correctly mapped as `contact.custom.notes` (0.95 confidence) with suggested custom field definition
- Three useful warnings: (1) "Notes column contains valuable relationship data", (2) "Phone numbers in local format", (3) "Missing domain data for some contacts"
- Zero corrections needed

**What was bad**:
- Nothing significant -- this is the strongest AI output in the entire test

*Verdict*: Excellent. The column mapper is production-quality and the warnings demonstrate contextual awareness.

---

## Workflow Gap Analysis

### 1. Proactive Flow (the system does not guide between steps)

The product vision positions the AI as a "strategist-in-residence" that proactively researches, recommends, and drives the GTM workflow forward. In practice, the AI is reactive -- it responds to prompts but never suggests the next step.

**Specific gaps observed**:
- After strategy creation: no suggestion to extract ICP criteria
- After ICP extraction: no suggestion to import contacts
- After contact import: no suggestion to run enrichment
- After enrichment inspection: no suggestion for triage or campaign creation
- The chat sidebar never proactively offered guidance at any point

**Impact**: The user must already know the full workflow to use it. A new user would be lost after completing any single step.

**Recommendation**: Implement a "next step" suggestion engine that, after each major action completes, proactively suggests the next logical step with a 1-click action. This should work through the chat sidebar as a contextual prompt.

### 2. Cross-Feature Integration (playbook, import, enrichment are islands)

Each feature operates in complete isolation:
- Playbook generates a strategy and extracts ICP criteria, but the extracted criteria are not used by the import or enrichment features
- Import creates contacts, but does not notify the enrichment or playbook features
- Enrichment has no awareness of the strategy or which contacts are ICP-relevant
- Campaign creation has no awareness of which contacts have been enriched

**Specific gaps**:
- ICP criteria from strategy extraction are not pre-loaded into enrichment triage rules
- Import does not auto-assign contacts to a playbook flow
- No pipeline automation: strategy -> extraction -> filter -> enrich -> triage -> campaign

**Impact**: The "closed-loop GTM engine" vision requires these features to communicate. Currently they are standalone tools that happen to share a database.

### 3. Chat Sidebar as Connective Tissue (potential but underutilized)

The chat sidebar persists across page navigation and has 6 tool categories (strategy, analyze, search, campaign, ICP filter, enrichment gap). It has the architectural potential to be the unifying element that connects features.

**Current state**: The chat is used primarily on the Playbook page for strategy generation. On other pages, it is a passive input box with no context-aware behavior.

**Potential**: After importing contacts, the chat could proactively say: "10 contacts imported. Based on your ICP criteria, I recommend running L1 enrichment on these 8 companies. Estimated cost: 200 credits. Shall I start?" This would bridge the gap between import and enrichment with a single conversational interaction.

### 4. User-Input Gates (where they exist vs. where they should)

The ideal workflow defines 10 gates where user input is required (approve strategy, confirm extraction, confirm import, approve enrichment cost, etc.). The current system has some of these gates but they are all implicit -- the user must discover them by navigating to the right page and clicking the right button.

**What exists**: Strategy save, Import confirm, Enrichment run button, Campaign creation, Message generation, Review approve/reject, Send approval
**What is missing**: Proactive gate presentation. No gate says "I've completed X, here's the summary, do you approve?"

### 5. Onboarding for New Namespace

The EntrySignpost component exists in code with three paths (Build a Strategy, Import Contacts, Browse Templates) but did not render during testing. A new namespace user faces:
- Empty contacts page with full filter sidebar
- No indication of what to do first
- Must discover Playbook, Import, and Enrich pages through the navigation menu

This is the most critical first-impression failure. If a user creates a new namespace and sees nothing helpful, they may never return.

---

## User Effort Analysis

### Interactions Observed vs Ideal

| Step | Ideal Min. | Actual | Extra | Cause |
|------|-----------|--------|-------|-------|
| 1. Login + Nav | 1 | 2 | +1 | Namespace switch required |
| 2. Strategy | 2 | 4 | +2 | Rate limit + non-execution |
| 3. Extraction | 1 | 2 | +1 | Manual navigation to Phase 2 |
| 4. Import | 2 | 6+ | +4 | UI crash, 3 API workarounds |
| 5-10 | ~14 | 0 | -- | Untested |
| **Total (tested)** | **6** | **14+** | **+8** | |

### Productive vs Wasted Interactions

- **Productive** (7): Business description, template selection, ICP extract click, file upload, 3 API workaround calls
- **Wasted** (7+): Re-prompt for tool execution, re-prompt for rate limit, namespace switch, page reload after crash, resume attempt, manual navigation to enrich page, filter leak investigation

### Manual Workarounds Performed

1. Switched namespace via dropdown (should default correctly or show onboarding)
2. Re-prompted AI to execute tools after it only responded in text
3. Re-prompted AI to complete remaining 4/9 sections after rate limit
4. Called `/api/imports/{id}/preview` via browser console (UI crashed)
5. Called `/api/imports/{id}/execute` via browser console (UI crashed)
6. Manually navigated to Enrich page (no suggestion from system)

### Corrective Actions Needed

1. Import UI fix (blocker -- prevents all imports)
2. Template API fix (forces fallback to slower chat generation)
3. Rate limit increase or batching (5 tool calls too low for 9-section documents)
4. EntrySignpost rendering fix (new users see nothing)

---

## Recommendations (Prioritized by Impact on Seamlessness Score)

### 1. Fix Import Column Mapping UI Crash (BLOCKER)
**Impact**: Availability +4, Seamlessness +3
The import flow is entirely broken for users. Fixing the `TypeError: Cannot read properties of undefined (reading 'length')` in the column mapping component is the highest-priority bug. The backend already works perfectly.

### 2. Implement Proactive Next-Step Suggestions
**Impact**: Proactiveness +4, Seamlessness +3
After each major action (strategy saved, contacts imported, enrichment completed), the chat sidebar should proactively suggest the next step with a 1-click action. This single change would transform the experience from "isolated tools" to "guided workflow."

### 3. Fix EntrySignpost for Empty Namespaces
**Impact**: Proactiveness +3, Seamlessness +2
The onboarding component exists but does not render. Fixing it gives new users a clear starting point (Build Strategy, Import Contacts, Browse Templates).

### 4. Add Web Research to Strategy Generation
**Impact**: AI Quality +2
The AI should call `web_search` to research the company's website before generating the strategy. This would replace placeholder text with real company details (acts, history, venue, reference clients).

### 5. Fix Template Application API
**Impact**: Availability +1, User Effort +1
The `/api/playbook/apply-template` endpoint fails. Fixing it restores the template-based strategy creation flow, reducing the need for multi-turn AI chat.

### 6. Connect ICP Extraction to Enrichment Triage Rules
**Impact**: Seamlessness +2, Proactiveness +2
Extracted ICP criteria should auto-populate triage rules so that enrichment qualification uses the strategy's definitions without manual configuration.

### 7. Increase Agent Tool Call Rate Limit
**Impact**: User Effort +2
Increase from 5 to 10+ tool calls per turn, or implement automatic continuation. Writing 9 strategy sections should not require multiple user prompts.

### 8. Add Extraction Feedback
**Impact**: Seamlessness +1, User Effort +1
After ICP extraction, show a toast or dialog summarizing what was extracted (industries, geography, company size, job titles). The user should see the extracted data before it is used downstream.

### 9. Fix Cross-Namespace Filter Leakage
**Impact**: Availability +0.5
Ensure enrichment page filters are scoped to the current namespace. Low severity but erodes trust.

### 10. Implement Playbook Phase 2 (Contacts)
**Impact**: Seamlessness +2
The "Coming soon" placeholder breaks the playbook flow. Phase 2 should show ICP-matched contacts and allow the user to confirm a selection for enrichment.

---

## Test Artifacts

### Screenshots (captured during test)
| File | Description |
|------|-------------|
| 01-initial-state-visionvolve-admin.png | Initial redirect to visionvolve admin |
| 02-unitedarts-admin-empty.png | Empty unitedarts admin page |
| 03-unitedarts-contacts-empty.png | Empty contacts page with full filter sidebar |
| 04-playbook-onboarding-step1.png | PlaybookOnboarding wizard Step 1 |
| 05-playbook-discovery-filled.png | Discovery form filled in |
| 06-playbook-template-selection.png | Template selection step |
| 07-playbook-ai-response-initial.png | AI response (text only, no tool execution) |
| 08-playbook-ai-tool-calls.png | AI tool calls (5 succeeded, rate limit hit) |
| 09-playbook-strategy-5-sections.png | Strategy with 5/9 sections complete |
| 10-playbook-strategy-complete.png | Strategy fully complete (9/9 sections) |
| 11-icp-extracted.png | ICP extraction button state |
| 12-playbook-contacts-phase-coming-soon.png | Phase 2 "Coming soon" placeholder |
| 13-import-page-upload.png | Import wizard upload step |
| 14-import-after-upload.png | Import page after upload (blank crash) |
| 15-import-resume-available.png | Import resume button |
| 16-import-resume-crash.png | Import step 2 with empty mapping area |

### Other Artifacts
| Artifact | Path |
|----------|------|
| Raw scores | `tests/baseline-eval/scores.json` |
| Scoring schema | `tests/baseline-eval/scoring-schema.json` |
| Ideal workflow | `tests/baseline-eval/ideal-workflow.md` |
| Test execution log | `tests/baseline-eval/test-execution-log.md` |
| Test subject profile | `tests/baseline-eval/test-subject-profile.md` |
| Namespace setup | `tests/baseline-eval/namespace-setup.md` |
| System inventory | `tests/baseline-eval/system-inventory.md` |
| Test contacts CSV | `tests/baseline-eval/test-contacts.csv` |

---

## Scoring Methodology

### Five Dimensions (per step)

1. **Availability** (0-10): Does the feature exist and work? 0=missing, 5=partial/buggy, 10=fully working.
2. **Seamlessness** (0-10): How smooth is the transition from the previous step? 10=automatic, 5=manual navigation, 0=broken.
3. **Proactiveness** (0-10): Does the system anticipate the next action? 10=auto-proceeds, 5=generic guidance, 0=no indication.
4. **AI Quality** (0-10 or null): Quality of AI-generated content. null if no AI output at this step.
5. **User Effort** (0-10): Computed as `10 - (extra_prompts * 1) - (manual_corrections * 2) - (manual_workarounds * 3) - (unnecessary_clarifications * 1)`. Floor at 0. Higher = less effort.

### LLM Output Quality (per output)

1. **Relevance** (1-10): Does the output fit the context?
2. **Accuracy** (1-10): Factually correct?
3. **Specificity** (1-10): Specific to this business, not generic?
4. **Actionability** (1-10): Can you act on it immediately?
5. **Tone** (1-10): Appropriate for B2B outreach?

### Aggregation Rules

- **Overall Completeness**: Mean of all availability scores
- **Workflow Seamlessness**: Mean of all seamlessness scores
- **AI Quality**: Mean of all non-null ai_quality scores (only 2 outputs scored)
- **User Effort**: Mean of all user_effort scores (skipped steps score 10 -- no effort spent)
- **Proactiveness**: Mean of all proactiveness scores

### Limitations of This Baseline

- Only 4/10 steps were fully tested; 6 were untested due to enrichment dependency
- Skipped steps bias the user_effort aggregate upward (10 for "no effort spent")
- AI quality is based on only 2 outputs (strategy generation + column mapping)
- Automated tester (Claude via Playwright) may interact differently than a human user
- Single test subject (unitedarts.cz) -- results may vary with different industries/geographies

---

## Comparison Notes

This is the **baseline test** (test ID: `baseline-001`). All future test runs should be compared against these scores to measure progress.

### To Reproduce This Exact Test

1. Use the staging environment at `https://leadgen-staging.visionvolve.com/`
2. Login as `test@staging.local` / `staging123`
3. Switch to the `unitedarts` namespace
4. Follow the 10-step workflow as described in `ideal-workflow.md`
5. Upload `test-contacts.csv` (10 Czech event manager contacts)
6. Score each step using the 5-dimension framework in `scoring-schema.json`

### What to Expect in Future Runs

After implementing the recommendations above, the expected score improvements are:
- **Import UI fix**: Availability should jump from 3 to 7+ on Step 4
- **Proactive suggestions**: Proactiveness should rise from 2.5 to 5+ overall
- **EntrySignpost fix**: Step 1 proactiveness should rise from 2 to 6+
- **Web research**: Step 2 AI quality should rise from 7 to 8+
- **Phase 2 implementation**: Step 3 availability should rise from 5 to 7+

The target for "good" seamlessness is 6+/10 on all tested steps. The current 3.2 average indicates significant room for improvement in the connective tissue between features.
