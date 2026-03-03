# Sprint 5 — EM Technical Challenge

## Verdict: APPROVED WITH CHANGES

## Technical Risk Score: 6/10 (moderate — several spec inaccuracies, one architectural gap, manageable merge risk)

The sprint plan is technically sound in direction. The codebase is more mature than the spec assumes — several components (ContactsPhasePanel, generation_prompts strategy section builder) already exist and the spec doesn't know it. The main risks are: (1) merge conflicts from 5 parallel agents touching shared files, (2) the orchestrator (BL-144) being over-scoped for a single sprint, and (3) AI behavioral changes (BL-137/140/150) being hard to test deterministically.

---

## Merge Conflict Analysis

| File | Agents Touching It | Risk | Resolution Order |
|------|-------------------|------|-----------------|
| `frontend/src/pages/playbook/PlaybookPage.tsx` | BL-141 (extraction feedback), BL-114 (auto-advance), BL-121 (onboarding simplification) | **HIGH** | BL-141 first → BL-114 second → BL-121 last. All three modify the extract handler and onboarding flow. |
| `frontend/src/providers/ChatProvider.tsx` | BL-135 (proactive suggestions), BL-146 (auto-enrichment trigger) | **HIGH** | BL-135 first (adds workflow status polling + suggestion engine). BL-146 builds on top. |
| `api/services/agent_executor.py` | BL-140 (rate limits), BL-150 (auto-execute) | **MEDIUM** | BL-140 first (trivial constant changes). BL-150 does NOT actually need to touch this file (see item review below). |
| `api/services/playbook_service.py` | BL-137 (web research system prompt), BL-150 (auto-execute system prompt) | **HIGH** | BL-137 first (adds research-first instructions). BL-150 second (adds action-first instructions). Both modify `build_system_prompt()`. |
| `frontend/src/pages/enrich/EnrichPage.tsx` | BL-142 (tag filter fix), BL-148 (run button fix) | **LOW** | BL-142 first. BL-148 may be automatically fixed by BL-142. |
| `frontend/src/components/playbook/PhasePanel.tsx` | BL-143 already done (ContactsPhasePanel exists) | **NONE** | No changes needed — see BL-143 review below. |
| `api/services/triage_evaluator.py` | BL-139 only | **NONE** | No conflicts. |
| `api/services/generation_prompts.py` | BL-145 only | **NONE** | No conflicts. |
| `api/services/campaign_tools.py` | BL-117 (campaign config), BL-147 (campaign auto-setup) | **MEDIUM** | BL-117 first (auto-populate config). BL-147 adds new tool function. |
| `frontend/src/components/playbook/PlaybookOnboarding.tsx` | BL-121 (simplified onboarding) | **NONE** | Single agent. |
| `frontend/src/components/layout/AppShell.tsx` | BL-136 (signpost), BL-144 (workflow progress bar) | **MEDIUM** | BL-136 first. BL-144 later. |

### Recommended Merge Order

1. **Wave 1 (parallel, no conflicts)**: BL-134, BL-136, BL-138, BL-142, BL-137
2. **Wave 2 (after Wave 1)**: BL-148 (after BL-142), BL-140, BL-141, BL-149, BL-151
3. **Wave 3 (after Wave 2)**: BL-150 (after BL-137), BL-143, BL-121 (after BL-136), BL-145
4. **Wave 4 (after Wave 3)**: BL-114 (after BL-141), BL-139 (after BL-141), BL-116 (after BL-139), BL-117 (after BL-145)
5. **Wave 5 (after Wave 4)**: BL-135 (can start early but merge late), BL-147 (after BL-139+BL-145), BL-146 (after BL-134+BL-139), BL-111 (after BL-136), BL-126 (after BL-134+BL-143)
6. **Wave 6 (capstone)**: BL-144 (after everything), BL-131

---

## Item-by-Item Review

### BL-134: Fix Import Column Mapping UI Crash [Must Have] [S]
- **Technical soundness**: Sound, but the spec's diagnosis is WRONG. The spec says `MappingStep.tsx` has a null-safety issue on `mappingResult.columns.length`. I read the actual `MappingStep.tsx` — it receives `mapping` as a prop from `ImportPage.tsx` and iterates `mapping.map(...)` directly. The crash is likely in `ImportPage.tsx` at line 196: `state.step === 2 && state.uploadResponse && (` — the guard checks `uploadResponse` but the `MappingStep` also accesses `state.mapping!` with a non-null assertion. If `state.mapping` is null (upload response arrives but columns array is null/undefined), the crash occurs.
- **Architecture fit**: Good — pure frontend state fix, no architectural concerns.
- **Actual files to change**: `frontend/src/pages/import/ImportPage.tsx` (add null guard on `state.mapping` at line 196-204), possibly `frontend/src/pages/import/MappingStep.tsx` (add defensive `mapping ?? []` fallback). Also check `frontend/src/api/queries/useImports.ts` for the `UploadResponse` type — `columns` might be optional.
- **Migration needed**: No
- **Security**: OK
- **Testing**: Need E2E test with `tests/baseline-eval/test-contacts.csv` upload. Unit test the edge case where upload API returns null/empty columns array.
- **Correction for engineers**: Do NOT look for `mappingResult.columns.length` — that pattern doesn't exist in the code. Look at `ImportPage.tsx` line 196 where `state.uploadResponse` is truthy but `state.mapping` could still be null. The `handleUploadComplete` callback at line 88 sets both `mapping: response.columns` and `uploadResponse: response` — but if `response.columns` is undefined, `state.mapping` will be undefined while `state.uploadResponse` is truthy. Add a null guard: `state.step === 2 && state.uploadResponse && state.mapping &&`. Also add optional chaining in `MappingStep` on `mapping.map(...)`.

---

### BL-136: Fix EntrySignpost for Empty Namespaces [Must Have] [S]
- **Technical soundness**: Sound. The spec's file path guesses are close. I confirmed `EntrySignpost` is in `frontend/src/components/onboarding/EntrySignpost.tsx` and it's imported in `frontend/src/components/layout/AppShell.tsx`. The onboarding status API exists at `GET /api/tenants/onboarding-status` (confirmed in `tenant_routes.py` line 269).
- **Architecture fit**: Good — uses existing onboarding infrastructure.
- **Actual files to change**: `frontend/src/components/layout/AppShell.tsx` (rendering condition for EntrySignpost), `frontend/src/components/onboarding/EntrySignpost.tsx` (verify props/rendering logic). Check whether the `useOnboardingStatus()` hook exists and is wired up.
- **Migration needed**: No
- **Security**: OK
- **Testing**: E2E test: create/switch to empty namespace, verify signpost renders, verify 3 action paths navigate correctly.
- **Correction for engineers**: The spec says to check `ContactsPage.tsx` — that's wrong. The signpost renders in `AppShell.tsx`, not in a specific page. Check the AppShell component for the conditional rendering logic.

---

### BL-138: Fix Template Application API [Must Have] [S]
- **Technical soundness**: Sound. The `apply-template` route exists in `playbook_routes.py`. Need to find the exact handler and debug it.
- **Architecture fit**: Good
- **Actual files to change**: `api/routes/playbook_routes.py` (the `apply-template` endpoint handler), `frontend/src/components/playbook/PlaybookOnboarding.tsx` (add error toast on failure)
- **Migration needed**: No
- **Security**: OK — endpoint already has `@require_auth`
- **Testing**: Test with each existing strategy template. Verify template content populates the StrategyDocument.
- **Correction for engineers**: The likely failure is a JSONB serialization issue when writing template content to `StrategyDocument.content`. Check if the template stores content as a string (markdown) vs structured object — the endpoint may expect one but receive the other. Also check if `StrategyTemplate` model has a `sections` field and how it maps to `StrategyDocument.content`.

---

### BL-142: Fix Cross-Namespace Filter Leakage on Enrich Page [Must Have] [S]
- **Technical soundness**: Sound. The spec correctly identifies a `tenant_id` filtering issue.
- **Architecture fit**: This is a **security-relevant** bug (data isolation breach), even if cosmetic. Fix must be thorough.
- **Actual files to change**: Check `frontend/src/pages/enrich/useEnrichState.ts` — find the tag fetch. The `X-Namespace` header must be sent with the tag API call. Also check `api/routes/tag_routes.py` — verify `GET /api/tags` filters by `tenant_id`.
- **Migration needed**: No
- **Security**: **This is a security issue, not just cosmetic.** Tags leaking across namespaces could expose business information (batch names contain strategy details like "NL-NORDICS[OPS/FIN]"). Ensure ALL queries in the tag endpoint filter by `tenant_id`.
- **Testing**: Multi-namespace test: create data in namespace A, switch to namespace B, verify no namespace A tags appear.
- **Correction for engineers**: Check if the EnrichPage's tag filter uses a different API call or caches tags from a previous namespace. The issue might be in the React Query cache not being invalidated on namespace switch (stale cache from visionvolve showing in unitedarts). Check if the query key includes the namespace.

---

### BL-148: Fix Enrichment Run Button Stuck in Loading State [Must Have] [S]
- **Technical soundness**: Likely correct that this shares a root cause with BL-142.
- **Architecture fit**: Good
- **Actual files to change**: `frontend/src/pages/enrich/DagControls.tsx` (Run button state), `frontend/src/pages/enrich/useEnrichState.ts` (loading dependencies)
- **Migration needed**: No
- **Security**: OK
- **Testing**: Test on a namespace WITH data (not just empty). The "Loading..." state may be caused by the estimate API call hanging when tag data is corrupted.
- **Correction for engineers**: Test BL-142 fix first. If the Run button still shows "Loading...", inspect `useEnrichEstimate.ts` — the cost estimate API call may have a dependency on tag selection that never resolves. Check if `DagControls` disables the Run button when `estimate.isLoading` is true and the estimate query never completes due to missing/invalid filter params.

---

### BL-137: Add Web Research to Strategy Generation [Must Have] [M]
- **Technical soundness**: Sound approach, but the spec underestimates the complexity. The `web_search` tool already works and is registered (`search_tools.py` line 155-181). The issue is that the system prompt in `playbook_service.py` doesn't instruct the AI to research first.
- **Architecture fit**: Good — system prompt modification only, no architectural change.
- **Actual files to change**: `api/services/playbook_service.py` (system prompt), NOT `agent_executor.py` (rate limits are a separate item BL-140).
- **Migration needed**: No
- **Security**: OK — Perplexity API key is already in env vars, no new secrets.
- **Testing**: This is **hard to test deterministically**. The AI may or may not call `web_search` depending on prompt phrasing. Write a behavioral test: send the onboarding prompt for unitedarts.cz and check that at least one `tool_start` SSE event has `tool_name: "web_search"`. If Perplexity is unavailable in test env, mock it.
- **Correction for engineers**: The `web_search` rate limit is 3 per turn (line 31 of `agent_executor.py`). With BL-140 bumping the iteration limit, 3 searches should suffice (1 for company, 1 for competitors, 1 for market). Do NOT increase `web_search` rate limit beyond 3 — Perplexity costs money per query. Focus the system prompt change on making research MANDATORY, not optional: "BEFORE writing any strategy section, you MUST research the company using web_search. I will NOT accept strategy sections that don't reference real findings."

---

### BL-140: Increase Agent Tool Call Limit or Auto-Continue [Must Have] [S]
- **Technical soundness**: Sound and trivially simple. Change 2 constants.
- **Architecture fit**: Good — but the spec suggests adding a "cost circuit breaker" (500 credits threshold). This is **scope creep**. A cost circuit breaker is a new feature, not a constant change. Remove it from scope.
- **Actual files to change**: `api/services/agent_executor.py` lines 27 and 33.
- **Migration needed**: No
- **Security**: The increased limits (MAX_TOOL_ITERATIONS=20, DEFAULT_TOOL_RATE_LIMIT=15) are safe. 20 iterations with Claude Sonnet at ~$0.02/turn = $0.40 max per conversation turn. Acceptable.
- **Testing**: Send a "write full strategy" prompt. Verify all 9 sections complete in one turn (count `tool_result` SSE events with `tool_name: "update_strategy_section"`).
- **Correction for engineers**: Do NOT implement the cost circuit breaker. That's out of scope — just change the two constants. Keep `web_search` at 3 per turn as specified.

---

### BL-150: AI Agent Should Auto-Execute Tools After Onboarding [Should Have] [M]
- **Technical soundness**: Sound, but the spec's file locations are partially wrong. The auto-generated message is constructed in `PlaybookPage.tsx` lines 443-458 (the `handleOnboardGenerate` callback), NOT in `PlaybookOnboarding.tsx`. The onboarding component calls `onGenerate(payload)` and `PlaybookPage` constructs the prompt and calls `sendMessage()`.
- **Architecture fit**: Good — this is a prompt engineering fix, not an architecture change.
- **Actual files to change**: (1) `frontend/src/pages/playbook/PlaybookPage.tsx` lines 443-458 — make the auto-generated prompt more explicit: instead of "Draft all sections of the strategy document using the update_strategy_section tool", say "Research [domain] via web_search FIRST, then write ALL 9 sections. Execute tools immediately — do NOT describe what you will do." (2) `api/services/playbook_service.py` — add an instruction to the system prompt: "When you receive a strategy generation request, execute tools immediately. Do NOT send a text-only planning response."
- **Migration needed**: No
- **Security**: OK
- **Testing**: E2E behavioral test: complete onboarding wizard, verify the AI's first response includes at least one `tool_start` event (not just text).
- **Correction for engineers**: The spec says to check `agent_executor.py` for "auto-generated messages processed differently." This is WRONG — the agent executor processes all messages identically. There is no special flag or marker. The fix is purely in prompt engineering: make the auto-generated message AND the system prompt both demand immediate action.

---

### BL-141: Add ICP Extraction Feedback and Confirmation [Must Have] [S]
- **Technical soundness**: Sound. The extract handler is in `PlaybookPage.tsx` lines 355-377 (`handleExtract`). It already calls `extractMutation.mutateAsync()` and gets back `extracted_data`. Currently shows a toast "Strategy data extracted successfully" but no summary dialog.
- **Architecture fit**: Good
- **Actual files to change**: `frontend/src/pages/playbook/PlaybookPage.tsx` (add extraction summary dialog/panel), new component or inline JSX for the summary display.
- **Migration needed**: No
- **Security**: OK
- **Testing**: Extract ICP from a populated strategy, verify the dialog shows industries, geography, company size. Verify error toast on empty extraction.
- **Correction for engineers**: The extract handler ALREADY shows a toast and auto-advances to contacts phase (lines 361-377). The issue is it doesn't show a SUMMARY of what was extracted. Add a modal that displays `extractedData.icp` fields before navigating to contacts.

---

### BL-143: Implement Playbook Phase 2 — Contacts Selection [Must Have] [L]
- **Technical soundness**: **THE SPEC IS WRONG — THIS IS ALREADY BUILT.** I read `PhasePanel.tsx` (lines 42-50) and it renders `ContactsPhasePanel` for the contacts phase. The `ContactsPhasePanel.tsx` is a fully implemented 395-line component with: ICP filter chips, DataTable with checkbox selection, search, pagination, confirm selection button, ICP-derived auto-filters, and proper API integration via `usePlaybookContacts` and `useConfirmContactSelection` hooks.
- **Architecture fit**: N/A — already exists.
- **Actual files to change**: **NONE** (or very minor adjustments). The baseline report says Phase 2 shows "Coming soon" — but the code I'm reading shows a full implementation. This means either: (a) the code was deployed AFTER the baseline test, or (b) the component exists but doesn't render due to a phase gate issue. Engineers should verify by navigating to `/:namespace/playbook/contacts` on staging.
- **Migration needed**: No
- **Security**: OK — already scoped to tenant
- **Testing**: Navigate to Phase 2 with extracted ICP data. Verify contacts render, filters work, selection + confirm works.
- **Correction for engineers**: **CRITICAL — Check if this is already working on staging.** The `PhasePanel.tsx` code renders `ContactsPhasePanel` for the contacts phase — NOT a "Coming soon" placeholder. If it's already working, mark this as done and move on. If it's not rendering, the issue is in the phase navigation or data loading, not in the component's existence. The "Coming soon" text only appears for the `campaign` phase (PhasePanel.tsx line 62).

---

### BL-114: Auto-Advance to Contacts Phase After ICP Extraction [Must Have] [S]
- **Technical soundness**: **ALREADY PARTIALLY IMPLEMENTED.** I read `PlaybookPage.tsx` lines 361-377 — the `handleExtract` callback ALREADY auto-advances to contacts phase after successful extraction (`advancePhaseMutation.mutateAsync({ phase: 'contacts' })` and `handlePhaseNavigate('contacts')`). It even shows a toast: "ICP extracted. Moving to Contacts phase..."
- **Architecture fit**: N/A — already exists.
- **Actual files to change**: **Minimal or NONE.** Verify the existing auto-advance works on staging. If it does, this item is already done.
- **Migration needed**: No
- **Security**: OK
- **Testing**: Extract ICP, verify URL changes to `/:namespace/playbook/contacts` and phase indicator updates.
- **Correction for engineers**: **CRITICAL — This auto-advance code already exists at PlaybookPage.tsx lines 361-377.** Before building anything, test it on staging. If it works, mark BL-114 as already complete. If the advance fails (e.g., phase validation blocks it), debug the `_validate_phase_transition` function in `playbook_routes.py` line 267.

---

### BL-121: Simplify Onboarding to 2 Inputs [Should Have] [S]
- **Technical soundness**: Sound. The current `PlaybookOnboarding` component has a multi-step wizard. Simplifying to 2 fields is straightforward.
- **Architecture fit**: Good
- **Actual files to change**: `frontend/src/components/playbook/PlaybookOnboarding.tsx` (simplify wizard), `frontend/src/pages/playbook/PlaybookPage.tsx` (update `handleOnboardGenerate` prompt construction)
- **Migration needed**: No
- **Security**: OK
- **Testing**: Test with and without a namespace domain configured. Verify the simplified form generates a complete strategy.
- **Correction for engineers**: The spec says "Auto-inject domain from namespace settings via tenant API." Check if `GET /api/tenants/:id` returns a domain field. If not, skip the auto-inject and let the user type the domain manually — don't create new backend work for a UX simplification.

---

### BL-139: Connect ICP Extraction to Enrichment Triage Rules [Must Have] [M]
- **Technical soundness**: Sound. The `triage_evaluator.py` already has the rule structure (`DEFAULT_RULES` with `industry_allowlist`, `geo_allowlist`, `min_employees`, etc.) that maps cleanly to ICP data.
- **Architecture fit**: Good — extends existing pattern. No new models needed.
- **Actual files to change**: `api/services/triage_evaluator.py` (add ICP-aware rule loader), `api/services/dag_executor.py` (pass tenant_id to triage stage)
- **Migration needed**: No
- **Security**: Ensure the `StrategyDocument` query in triage_evaluator is scoped to the correct `tenant_id`. Don't load another tenant's ICP.
- **Testing**: Unit test: create a StrategyDocument with ICP data, run triage on a company, verify ICP rules are applied. Test fallback: no ICP data → DEFAULT_RULES used.
- **Correction for engineers**: The spec is accurate. The key mapping is: `icp.industries` → `industry_allowlist`, `icp.geographies` → `geo_allowlist`, `icp.company_size.min` → `min_employees`. The triage evaluator needs to load the StrategyDocument for the tenant and merge ICP fields into the rules dict. Keep backward compatibility: if no ICP exists, use DEFAULT_RULES unchanged.

---

### BL-116: apply_icp_filters Chat Tool — Bridge Strategy to Contacts [Must Have] [S]
- **Technical soundness**: Sound. The file `api/services/icp_filter_tools.py` already exists. Need to verify the tool is registered and functional.
- **Architecture fit**: Good — follows existing tool pattern.
- **Actual files to change**: `api/services/icp_filter_tools.py` (verify/fix), check tool registration in app startup.
- **Migration needed**: No
- **Security**: OK — scoped to tenant via ToolContext
- **Testing**: Send "Show me contacts matching my ICP" in chat. Verify tool is called and returns match counts.
- **Correction for engineers**: Read the existing `icp_filter_tools.py` first. It may already be functional. If the tool is registered but not being called, the issue is in the system prompt not mentioning it — add it to the available tools list in `playbook_service.py`.

---

### BL-145: Strategy-Aware Message Generation [Must Have] [M]
- **Technical soundness**: **THE SPEC UNDERESTIMATES WHAT'S ALREADY BUILT.** I read `generation_prompts.py` lines 75-154 — the `_build_strategy_section()` function ALREADY exists and formats ICP, value proposition, messaging framework, competitive positioning, and buyer personas from `extracted_data`. The question is whether `build_generation_prompt()` actually CALLS this function and whether the Campaign's `strategy_id` is used to load the strategy.
- **Architecture fit**: Good — the Campaign model already has `strategy_id` (confirmed at `models.py` line 1053).
- **Actual files to change**: `api/services/message_generator.py` (load StrategyDocument via Campaign.strategy_id, pass extracted_data to prompt builder), `api/services/generation_prompts.py` (verify `build_generation_prompt` uses `_build_strategy_section`).
- **Migration needed**: No — `strategy_id` column already exists on Campaign.
- **Security**: OK
- **Testing**: Create a campaign with `strategy_id` set. Generate messages. Verify the prompt includes strategy context (check LLM usage logs for prompt content, or add a debug log).
- **Correction for engineers**: **Read `generation_prompts.py` carefully** — `_build_strategy_section()` already exists at line 75. Your job is to wire it up: in `message_generator.py`, load the Campaign's linked StrategyDocument, get its `extracted_data`, and pass it to the prompt builder. The formatting logic is already done.

---

### BL-117: Auto-Populate Campaign generation_config from Linked Strategy [Must Have] [S]
- **Technical soundness**: Sound. Straightforward data mapping.
- **Architecture fit**: Good
- **Actual files to change**: `api/routes/campaign_routes.py` (POST /api/campaigns handler), `api/services/campaign_tools.py` (create_campaign tool handler)
- **Migration needed**: No
- **Security**: OK
- **Testing**: Create a campaign with `strategy_id`. Verify `generation_config.tone`, `channel`, and `target_criteria` are auto-populated.
- **Correction for engineers**: The `extracted_data` schema for mapping is defined in `strategy_tools.py` lines 39-57. Map: `messaging.tone` → `generation_config.tone`, `channels.primary` → `channel`, `icp` → `target_criteria`. Allow user override of any auto-populated field.

---

### BL-147: Campaign Auto-Setup from Qualified Contacts [Must Have] [M]
- **Technical soundness**: Sound approach, but note that this is a NEW TOOL for the chat agent, not just backend logic. It needs to be registered in the tool registry.
- **Architecture fit**: Good — follows the existing `campaign_tools.py` pattern.
- **Actual files to change**: `api/services/campaign_tools.py` (new `auto_create_campaign_from_triage` function + ToolDefinition), tool registration in app startup.
- **Migration needed**: No
- **Security**: Ensure the campaign is created in "draft" status. Never auto-execute message generation without user approval.
- **Testing**: Run triage on test data, then invoke the tool. Verify a draft campaign is created with the correct contacts and strategy-derived settings.
- **Correction for engineers**: The tool should query `Company.query.filter_by(tenant_id=ctx.tenant_id, status='Triage: Passed')` and then get associated contacts. Create the Campaign with `strategy_id` set (so BL-117's auto-population kicks in). Return a summary dict that the AI can present to the user.

---

### BL-135: Proactive Next-Step Suggestions in Chat [Must Have] [L]
- **Technical soundness**: Sound, but this is the most complex item in the sprint. The spec proposes a new `GET /api/workflow/status` endpoint — this is correct and necessary.
- **Architecture fit**: **CONCERN — the spec proposes adding a workflow status polling mechanism to ChatProvider.** ChatProvider is already 300+ lines and manages SSE streaming, tool calls, document changes, and analysis. Adding workflow polling risks making it a god object. Consider a separate `useWorkflowStatus()` hook that ChatProvider consumes, rather than building the polling logic inline.
- **Actual files to change**: New file `api/routes/workflow_routes.py` (status endpoint), `frontend/src/providers/ChatProvider.tsx` (suggestion state), `frontend/src/components/chat/ChatMessages.tsx` (render suggestion chips), new hook `frontend/src/hooks/useWorkflowStatus.ts`.
- **Migration needed**: No — workflow status is computed from existing models, not stored.
- **Security**: The workflow status endpoint must be scoped to the current tenant. Don't leak cross-namespace workflow state.
- **Testing**: Verify suggestions change as the user progresses through the workflow. Test: strategy saved → suggestion to extract ICP. Import completed → suggestion to enrich. Etc.
- **Correction for engineers**: Do NOT build the full 10-step suggestion engine on day 1. Start with 3-4 key transitions: (1) strategy saved → extract ICP, (2) contacts imported → enrich, (3) enrichment complete → create campaign, (4) messages reviewed → launch outreach. Additional transitions can be added incrementally. The workflow status endpoint should query existing models — NOT maintain a separate state table. Compute state on read.

---

### BL-146: Auto-Enrichment Trigger with Cost Approval Gate [Must Have] [M]
- **Technical soundness**: Sound, but the spec's approach of adding an `onImportComplete` handler to ChatProvider creates tight coupling between import and chat. A better pattern: dispatch a custom event from the import success handler, and have the ChatProvider (or a separate workflow hook) listen for it.
- **Architecture fit**: **CONCERN** — embedding enrichment trigger logic in ChatProvider makes it harder to test and maintain. Use the workflow status endpoint (from BL-135) instead: after import, the workflow status changes, and the suggestion engine naturally suggests enrichment.
- **Actual files to change**: `frontend/src/pages/import/PreviewStep.tsx` or `ImportSuccess.tsx` (dispatch event or update workflow state), ChatProvider or workflow hook (react to state change), backend estimation already exists at `POST /api/enrich/estimate`.
- **Migration needed**: No
- **Security**: **CRITICAL** — the "Approve & Start" button must enforce budget checks. Use `api/services/budget.py` to verify sufficient credits before triggering `POST /api/pipeline/dag-run`. Never allow enrichment to start without credit verification.
- **Testing**: Import contacts, verify cost estimate appears in chat. Approve, verify enrichment starts. Test with insufficient credits — verify warning instead of approve button.
- **Correction for engineers**: Prefer using the workflow status mechanism (from BL-135) rather than a direct import-to-chat coupling. The flow should be: import completes → workflow status changes to `contacts_imported` → suggestion engine generates enrichment suggestion → user clicks approve → enrichment starts. This is cleaner and more testable than hardwiring import success to chat messages.

---

### BL-144: End-to-End Workflow Orchestrator [Must Have] [XL]
- **Technical soundness**: **OVER-SCOPED.** The spec proposes a full state machine with 11 states, a new model (`WorkflowState`), new API endpoints, a `WorkflowProgressBar` component, AND integration with all other Track 4/5 items. This is easily 2-3 sprints of work, not a single item in a 22-item sprint.
- **Architecture fit**: **The spec proposes storing workflow state in a new model.** This is unnecessary for Sprint 5. The workflow state can be COMPUTED from existing data: has_strategy (StrategyDocument exists with content), has_icp (extracted_data.icp populated), has_contacts (Contact count > 0), has_enrichment (EntityStageCompletion records exist), has_campaign (Campaign exists), etc. The onboarding-status endpoint (`GET /api/tenants/onboarding-status`) already does part of this.
- **Actual files to change**: If descoped to computed status: extend `GET /api/tenants/onboarding-status` to include enrichment and campaign milestones. If full scope: new files as spec describes.
- **Migration needed**: No (if computed state). Yes (if new WorkflowState model).
- **Security**: OK — scoped to tenant.
- **Testing**: Full E2E workflow test.
- **Correction for engineers**: **DESCOPE THIS ITEM.** For Sprint 5, implement: (1) Extend the onboarding-status endpoint to return full workflow state (computed, not stored). (2) Build a simple `WorkflowProgressBar` that reads this status. (3) DO NOT build a state machine with event-driven transitions — that's Phase 2. The proactive suggestions (BL-135) already provide the guided experience. BL-144 in Sprint 5 should be "visible workflow progress indicator" + "computed status API", NOT a full orchestration engine.

---

### BL-111: App-Wide Onboarding Signpost + Smart Empty States [Should Have] [M]
- **Technical soundness**: Sound. Components already exist per system inventory (`SmartEmptyState`, `ProgressChecklist`).
- **Architecture fit**: Good
- **Actual files to change**: Various page components (CampaignsPage, EnrichPage, MessagesPage, ContactsPage) — add conditional rendering of empty states.
- **Migration needed**: No
- **Security**: OK
- **Testing**: Navigate to each page with an empty namespace. Verify appropriate empty state renders with correct CTAs.
- **Correction for engineers**: The spec is accurate. Focus on wiring existing components to data state, not building new components.

---

### BL-149: Namespace Session Persistence [Should Have] [S]
- **Technical soundness**: Sound. Simple localStorage implementation.
- **Architecture fit**: Good
- **Actual files to change**: Find the namespace resolution in the router (likely in `AppShell.tsx` or a namespace context provider). Add localStorage read/write.
- **Migration needed**: No
- **Security**: Validate stored namespace against user's accessible namespaces. Don't allow access to a namespace the user was later removed from.
- **Testing**: Switch namespace, refresh page, verify same namespace loads.
- **Correction for engineers**: The spec is accurate. Straightforward implementation.

---

### BL-151: Strategy Save Progress Indicator Per Section [Could Have] [S]
- **Technical soundness**: Sound, but may cause toast spam (9 toasts for 9 sections). Consider a single summary toast instead.
- **Architecture fit**: Good
- **Actual files to change**: `frontend/src/providers/ChatProvider.tsx` (detect `update_strategy_section` tool results and fire toast), or `PlaybookPage.tsx`.
- **Migration needed**: No
- **Security**: OK
- **Testing**: Generate a strategy, verify section-level feedback appears.
- **Correction for engineers**: Do NOT show 9 individual toasts — that's spammy. Instead, show a single notification after all tool calls complete: "Strategy updated (9 sections written)." The existing `documentChanged` mechanism in ChatProvider already does something similar — extend it rather than building a new notification path.

---

### BL-126: Contact Import in Playbook — Embedded Import Flow [Must Have] [M]
- **Technical soundness**: Sound. Reuse existing import wizard components in a modal.
- **Architecture fit**: Good — component reuse pattern.
- **Actual files to change**: `frontend/src/components/playbook/ContactsPhasePanel.tsx` (add "Import Contacts" button + modal), reuse `UploadStep`, `MappingStep`, `PreviewStep`.
- **Migration needed**: No
- **Security**: OK
- **Testing**: Open Phase 2, click Import, complete wizard, verify contacts appear in the phase panel.
- **Correction for engineers**: The `ContactsPhasePanel` already has an empty state message: "No contacts found. Import contacts first." Add a button to this empty state that opens the import modal. The modal should wrap the existing wizard steps with minimal changes.

---

### BL-131: Credit Cost Estimator Component [Should Have] [S]
- **Technical soundness**: Sound.
- **Architecture fit**: Good — reusable UI component.
- **Actual files to change**: New file `frontend/src/components/ui/CreditCostEstimator.tsx`
- **Migration needed**: No
- **Security**: OK
- **Testing**: Render with various props. Verify insufficient balance warning.
- **Correction for engineers**: The spec is accurate. Keep it simple — a presentational component that receives data as props.

---

## Critical Technical Issues (STOP — Notify Engineers)

### ISSUE 1: BL-143 (Phase 2) and BL-114 (Auto-Advance) May Already Be Built

**Severity**: HIGH — Engineers may waste 2-3 days building something that already exists.

`PhasePanel.tsx` already renders `ContactsPhasePanel` for the contacts phase (line 42-50). `ContactsPhasePanel.tsx` is a fully implemented 395-line component with ICP filters, DataTable, selection, confirm button, pagination, and API hooks. `PlaybookPage.tsx` already auto-advances to contacts after extraction (lines 361-377).

**Action Required**: Before ANY engineer starts on BL-143 or BL-114, test on staging:
1. Navigate to `/:namespace/playbook/contacts`
2. Extract ICP from a populated strategy
3. Verify: Does ContactsPhasePanel render? Does auto-advance work?

If both work → mark BL-143 and BL-114 as DONE, saving ~3 engineer-days.

### ISSUE 2: BL-145 Strategy Section Builder Already Exists

`generation_prompts.py` already has `_build_strategy_section()` at line 75 that formats ICP, value proposition, messaging, competitive positioning, and personas. The engineer for BL-145 should check if this function is already called by `build_generation_prompt()` before writing duplicate code.

### ISSUE 3: BL-144 Over-Scoped

The workflow orchestrator as specified (full state machine, new model, new API endpoints, progress bar, integration with 5 other items) is XL scope — too much for Sprint 5. Descope to: computed workflow status (extend onboarding-status endpoint) + simple progress bar. The state machine can come in Sprint 6.

### ISSUE 4: `playbook_service.py` Conflict Risk

BL-137 and BL-150 both modify the system prompt in `playbook_service.py`. If both engineers work on it simultaneously, the merge will be painful. **Stagger**: BL-137 merges first (adds research instructions), then BL-150 merges (adds action-first instructions).

---

## Missing Technical Work

1. **React Query Cache Invalidation on Namespace Switch**: BL-142 (tag filter leakage) may be caused by stale React Query cache, not a backend bug. Check if namespace switch invalidates all query caches. If not, add `queryClient.clear()` on namespace change.

2. **E2E Tests for AI Behavioral Changes**: BL-137, BL-140, BL-150 change AI behavior. These need behavioral tests (e.g., "AI called web_search at least once during strategy generation"). No framework for this exists. Engineers need to write Playwright tests that check SSE event streams for expected tool calls.

3. **Cost Guardrails for Increased Limits**: BL-140 increases MAX_TOOL_ITERATIONS to 20. A single agent turn could now make 20+ API calls. Add a warning to `llm_logger.py` if a single turn exceeds a cost threshold (e.g., log a WARNING if turn cost > $0.50).

4. **Workflow Status API Design**: BL-135 and BL-144 both need a workflow status API but the spec has them building it independently. Define the API contract ONCE before either starts. My recommendation: extend `GET /api/tenants/onboarding-status` with additional fields rather than creating a new endpoint.

5. **Missing Unit Tests**: The sprint plan mentions E2E tests but not unit tests for:
   - `triage_evaluator.py` with ICP rules (BL-139)
   - `campaign_tools.py` auto-create function (BL-147)
   - `workflow_routes.py` status computation (BL-135/144)

   Each of these needs unit tests — they're backend logic that can be tested without a browser.

---

## Summary of Corrections for In-Flight Engineers

| Agent | Item | Key Correction |
|-------|------|---------------|
| **Engineer 1 (BL-134)** | Import crash | Look at `ImportPage.tsx` line 196 null guard on `state.mapping`, NOT `MappingStep.tsx` |
| **Engineer 2 (BL-136)** | EntrySignpost | Check `AppShell.tsx`, NOT `ContactsPage.tsx` |
| **Engineer 3 (BL-138)** | Template API | Check JSONB serialization between StrategyTemplate and StrategyDocument |
| **Engineer 4 (BL-142)** | Tag leakage | Check React Query cache invalidation on namespace switch |
| **Engineer 5 (BL-137)** | Web research | Only modify `playbook_service.py`, keep `web_search` rate limit at 3 |
| **ALL** | BL-143/BL-114 | CHECK IF ALREADY BUILT before implementing |
| **ALL** | BL-145 | `_build_strategy_section()` already exists — wire it up, don't rebuild |
| **ALL** | BL-144 | DESCOPE to computed status + progress bar, no state machine |
