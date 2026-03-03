# Baseline E2E Test Execution Log

**Test ID**: baseline-001
**Date**: 2026-03-02
**Subject**: unitedarts.cz
**Environment**: https://leadgen-staging.visionvolve.com/
**Namespace**: unitedarts (tenant ID: 4c0960ea-553d-4fba-808f-c7f9419f389e)
**Tester**: automated (Claude Opus 4.6 via Playwright MCP)
**System Version**: staging (commit 625753a)
**Login**: test@staging.local / staging123

---

## Step 1: Login + Navigation
**Timestamp**: ~21:33 UTC
**Status**: COMPLETED (with issues)

### What happened
- Navigated to `https://leadgen-staging.visionvolve.com/` -- session was already cached from previous testing
- Page auto-redirected to `/visionvolve/admin` (previous namespace)
- Used namespace dropdown to switch to `unitedarts`
- Navigated to `/unitedarts/` which redirected to `/unitedarts/contacts`

### Key findings
1. **No onboarding/entry signpost** for the empty namespace. EntrySignpost component exists in code but did NOT render. User lands on contacts page with 0 contacts and full filter sidebar.
2. **Namespace selector persists session** -- switching namespace via dropdown works and retains across navigation
3. **Namespace defaults to visionvolve** on fresh page loads -- inconsistent default behavior
4. The full filter sidebar (Company Tier, Industry, Company Size, Region, Revenue, Seniority, Department, LinkedIn Activity) shows on an empty namespace -- overwhelming for first-time users

### Scores
- availability: 8 (login works, namespace switching works, but no onboarding)
- seamlessness: 4 (no guidance on what to do next, drops into empty contacts page)
- proactiveness: 2 (no onboarding, no empty state guidance, no "get started" flow)
- ai_quality: null (no AI involved)
- user_effort: 7 (1 extra action to switch namespace)

### Screenshots
- 01-initial-state-visionvolve-admin.png
- 02-unitedarts-admin-empty.png
- 03-unitedarts-contacts-empty.png

---

## Step 2: GTM Strategy Creation
**Timestamp**: ~21:34-21:39 UTC
**Status**: COMPLETED (with workarounds)

### What happened
1. Navigated to Playbook page -- **PlaybookOnboarding** wizard appeared (3-step: Discovery, Template, Generate)
2. Filled in Discovery form: domain=unitedarts.cz, objective, ICP description
3. Selected "Professional Services -- Local Market" template (closest match for entertainment company)
4. System showed "Personalizing your strategy" for ~15 seconds
5. **API error**: `/api/playbook/apply-template` failed -- template application backend error
6. Fallback: System sent automatic chat message asking AI to generate strategy
7. AI responded with "I'll build your complete GTM strategy playbook now" but did NOT actually write to the document
8. **Extra prompt required**: Sent explicit request to write sections using update_strategy_section tool
9. AI executed 5/9 sections successfully, then hit rate limit (5 tool calls per turn)
10. **Second extra prompt**: Asked for remaining 4 sections
11. AI completed all 9 sections successfully in second turn (4/4 tool calls succeeded)

### Strategy quality assessment
The generated strategy is **good quality** -- specific to unitedarts.cz:
- Executive Summary: Mentions Czech-based, circus/acrobatic performances, 20+ leads target
- ICP: Primary (Event Agencies) and Secondary (In-House Corporate Teams) with specific criteria
- Buyer Personas: 3 detailed personas with pain points, channels, decision roles
- Value Proposition: Core proposition plus persona-specific benefits
- Competitive Positioning: Competitive matrix table (vs brokers, local performers)
- Channel Strategy: LinkedIn 40%, Email 25%, Events 20%, Partnerships 15%
- Messaging Framework: 3 persona-specific message variants with tone guidelines
- Metrics & KPIs: 3 KPI tables (primary, secondary, revenue)
- 90-Day Action Plan: Week-by-week checklist with checkpoints

### Issues
1. Template application API failed (404/500)
2. AI's first response was only a chat message, didn't execute tools
3. Rate limit of 5 tool calls per turn forced 2 chat turns to write 9 sections
4. No web_search tool was used -- AI generated from its training data, not from researching unitedarts.cz
5. No auto-save feedback after each section was written

### Scores
- availability: 7 (works but template API failed, rate limit issues)
- seamlessness: 6 (onboarding wizard is nice, but required manual navigation to Playbook)
- proactiveness: 5 (auto-generated chat prompt from onboarding, but didn't execute tools proactively)
- ai_quality: 7 (content is specific to unitedarts.cz but generic -- no website research, no competitor names, placeholder stats like "[X] agencies")
- user_effort: 5 (2 extra prompts due to non-execution + rate limit, 1 manual template selection)

### LLM outputs
- Strategy generation: 9 sections, ~3000 words total
- Model: Claude (via agent_executor.py)
- No web_search was used (should have researched unitedarts.cz)

### Screenshots
- 04-playbook-onboarding-step1.png
- 05-playbook-discovery-filled.png
- 06-playbook-template-selection.png
- 07-playbook-ai-response-initial.png (AI said it would write but didn't)
- 08-playbook-ai-tool-calls.png (5 succeeded, 8 failed)
- 09-playbook-strategy-5-sections.png
- 10-playbook-strategy-complete.png

---

## Step 3: Intelligence Extraction
**Timestamp**: ~21:39 UTC
**Status**: COMPLETED (silent)

### What happened
1. Clicked "Extract ICP" button in Playbook header
2. Button showed "Extracting..." for ~5-10 seconds
3. Button returned to "Extract ICP" -- no visual confirmation
4. No toast, no summary of extracted data
5. Navigated to Phase 2 (Contacts) -- shows "Coming soon. Use the chat to discuss this phase with your AI strategist."

### Key findings
1. **Extraction runs silently** -- no feedback on what was extracted
2. **Phase 2 (Contacts) is not fully functional** -- shows "Coming soon"
3. No ICP-to-filter mapping is presented automatically
4. The "Select Contacts" button is disabled

### Scores
- availability: 5 (extraction runs but no visible output; Phase 2 not functional)
- seamlessness: 3 (no automatic transition, no explanation of what was extracted)
- proactiveness: 2 (extraction is manual button click, no auto-extract after strategy save)
- ai_quality: null (extraction output not visible to user)
- user_effort: 8 (just 1 click, but no feedback)

### Screenshots
- 11-icp-extracted.png
- 12-playbook-contacts-phase-coming-soon.png

---

## Step 4: Contact Import
**Timestamp**: ~21:41-21:45 UTC
**Status**: COMPLETED (via API workaround)

### What happened
1. Navigated to Import page -- clean 3-step wizard (Upload, Map Columns, Preview & Import)
2. Uploaded test-contacts.csv (10 contacts, 7 columns)
3. Batch name auto-generated: "import-test-contacts"
4. Clicked "Upload & Analyze"
5. **CRASH**: Page went completely blank -- JavaScript error `TypeError: Cannot read properties of undefined (reading 'length')`
6. Reloaded page -- previous import showed as "mapped" with "Resume" button
7. Clicked "Resume" -- advanced to Step 2 (Map Columns) but rendering was blank
8. **WORKAROUND**: Used browser JavaScript console to call API directly
9. API response confirmed excellent column mapping (0.99 confidence):
   - First Name -> contact.first_name (1.0)
   - Last Name -> contact.last_name (1.0)
   - Organization -> company.name (1.0)
   - Title -> contact.job_title (1.0)
   - Email -> contact.email_address (1.0)
   - Phone -> contact.phone_number (1.0)
   - Notes -> contact.custom.notes (0.95, custom field)
10. Executed import via API: 10 contacts created, 8 companies created, 1 company linked
11. Verified contacts visible on contacts page (10 contacts with correct data)

### Key findings
1. **BLOCKER BUG**: Frontend column mapping UI crashes consistently (`TypeError: Cannot read properties of undefined (reading 'length')`)
2. Backend API works perfectly -- upload, mapping, preview, and execute all return correct data
3. AI column mapping is excellent (0.99 confidence, Notes correctly mapped as custom field)
4. The bug appears to be in the frontend component rendering the mapping response
5. Two AI-generated warnings were useful: "Notes column contains valuable relationship data", "Phone numbers in local format"

### Errors
- Type: ui_error
- Description: Column mapping step crashes with TypeError on every attempt
- Severity: blocker (cannot complete import through UI)
- Recovery: API workaround via browser console

### Scores
- availability: 3 (feature exists but UI crashes -- only works via API)
- seamlessness: 2 (crash breaks the flow completely)
- proactiveness: 5 (auto-batch naming, AI warnings about data quality)
- ai_quality: 8 (column mapping quality is excellent, good warnings)
- user_effort: 1 (3 manual workarounds via API console)

### Screenshots
- 13-import-page-upload.png
- 14-import-after-upload.png (blank crash)
- 15-import-resume-available.png
- 16-import-resume-crash.png (step 2 with empty mapping area)

---

## Step 5: Basic Enrichment (L1)
**Timestamp**: ~21:47 UTC
**Status**: PARTIAL (inspected only, not executed)

### What happened
1. Navigated to Enrich page -- DAG pipeline visualization loaded
2. Comprehensive stage layout visible:
   - Profiling: Company Profile (CP)
   - Qualification: Triage (TG)
   - Company Intelligence: Deep Research (DR), Strategic Signals (SS), Legal & Registry (LR), News & PR (NP)
   - Contact Intelligence: Role & Employment (RE), Social & Online (SO), Career History (CH), Contact Details (CD)
   - Validation: Quality Check (QC)
3. All stages checked except QC
4. **Namespace filter leakage**: Tag filter shows "batch-2-NL-NORDICS[OPS/FIN]" from visionvolve namespace
5. "Run" button shows "Loading..." -- not fully loaded
6. Did NOT execute enrichment (would cost real credits and take significant time)

### Key findings
1. DAG visualization is comprehensive and well-organized
2. Stage descriptions are clear and informative
3. **Cross-namespace filter leakage** -- filter state from another namespace persists
4. Legal & Registry correctly notes ".cz, .no, .fi, .fr" country limitation

### Scores
- availability: 7 (page loads, stages visible, but run controls not fully loaded)
- seamlessness: 3 (manual navigation required, no suggestion from AI/playbook)
- proactiveness: 2 (no cost estimate shown proactively, no AI suggestion)
- ai_quality: null (not executed)
- user_effort: 8 (would be 1 click to run if controls loaded)

---

## Step 6: Qualification/Triage
**Status**: SKIPPED (requires L1 enrichment first)

### Notes
- Triage stage exists in the DAG (zero-cost, rules-based)
- Cannot be tested without L1 data
- No ICP criteria appear to be pre-loaded from the strategy extraction

### Scores
- availability: 5 (stage exists but untestable without L1 data)
- seamlessness: 3 (no automatic pipeline from strategy -> enrichment)
- proactiveness: 2 (no suggestion to run enrichment after import)
- ai_quality: null
- user_effort: 10 (n/a)

---

## Step 7: Deep Enrichment (L2 + Person + Registry)
**Status**: SKIPPED (requires L1 + triage first)

### Scores
- availability: 5 (stages exist but untestable)
- seamlessness: 3
- proactiveness: 2
- ai_quality: null
- user_effort: 10

---

## Step 8: Campaign Creation
**Status**: NOT TESTED (blocked by no enrichment data)

### What could be tested
- Campaign creation page exists (verified via system inventory)
- Would need contacts with enrichment data for meaningful test

### Scores
- availability: 7 (feature exists per system inventory)
- seamlessness: 3 (no automatic flow from enrichment -> campaign)
- proactiveness: 2
- ai_quality: null
- user_effort: 10

---

## Step 9: Message Generation
**Status**: NOT TESTED (blocked by no campaign with enriched contacts)

### Scores
- availability: 7 (feature exists per system inventory)
- seamlessness: 3
- proactiveness: 2
- ai_quality: null
- user_effort: 10

---

## Step 10: Message Review & Campaign Launch
**Status**: NOT TESTED (blocked by no generated messages)

### Scores
- availability: 7 (feature exists per system inventory)
- seamlessness: 3
- proactiveness: 2
- ai_quality: null
- user_effort: 10

---

## Summary of Findings

### What works well
1. **Playbook onboarding wizard** -- clean 3-step flow (Discovery, Template, Generate)
2. **AI strategy generation** -- specific, actionable, well-structured 9-section strategy
3. **AI column mapping** -- 0.99 confidence, correctly maps all fields including custom Notes
4. **Import API backend** -- robust, handles dedup, Czech characters, custom fields
5. **DAG enrichment UI** -- comprehensive visualization with 10+ stages
6. **Chat persistence** -- conversation history persists across page navigation
7. **Tool call visualization** -- clear display of AI tool usage with timing

### Blockers / Critical bugs
1. **Import column mapping UI crash** -- `TypeError: Cannot read properties of undefined (reading 'length')` -- prevents completing import through frontend
2. **Template application API failure** -- `/api/playbook/apply-template` returns error
3. **No onboarding for empty namespace** -- EntrySignpost not rendering despite code being present

### Major UX gaps
1. **AI doesn't research the company** -- No web_search used during strategy generation. Output is from training data, not live research of unitedarts.cz
2. **ICP extraction is silent** -- No feedback on what was extracted
3. **Phase 2 (Contacts) is "Coming soon"** -- Can't map ICP to contact filters through playbook
4. **AI rate limit visible to user** -- 5 tool calls per turn forces multi-turn interaction for 9 sections
5. **Cross-namespace filter leakage** -- Enrichment page shows filters from another namespace
6. **Namespace defaults to visionvolve** on page reload

### Missing from ideal workflow
1. No AI proactive suggestions after each step ("Now let's import contacts")
2. No automatic pipeline: strategy -> extraction -> contact filtering -> enrichment -> campaign
3. No web research during strategy creation
4. No cost estimate shown before enrichment without clicking
5. No guided flow connecting playbook phases to standalone features
