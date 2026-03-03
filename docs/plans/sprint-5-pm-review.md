# Sprint 5 -- PM Challenge Review

**Reviewer**: PM Analyst
**Date**: 2026-03-02
**Sprint**: Sprint 5 -- Seamless Flow
**Items reviewed**: 25
**Context**: 5 engineering agents are already in-flight. This review identifies course corrections.

---

## Verdict: APPROVED WITH CHANGES

The sprint correctly identifies the #1 problem (3.2/10 seamlessness = isolated islands) and the #1 solution (connective tissue between features). The item selection is strategically sound -- every Must Have item directly addresses a gap observed in the baseline test. However, the sprint has **scope risk**: 25 items including an XL orchestrator is aggressive for a 2-week sprint, even with 5 engineers. The critical path through BL-141 -> BL-139 -> BL-146 -> BL-144 has zero slack.

**Key concern**: BL-144 (Workflow Orchestrator, XL) is the capstone that depends on 5 other items completing on schedule. If any upstream item slips by even 1 day, BL-144 gets squeezed. The sprint needs a fallback plan: what does "9/10 seamlessness" look like WITHOUT BL-144?

---

## Strategic Alignment Score: 8.5/10

The sprint is well-aligned with the product vision. The baseline test proved that the system has the building blocks but lacks the "AI as strategist-in-residence" experience. This sprint directly attacks that gap:

- **Closed-loop GTM engine**: BL-144 + BL-135 transform isolated tools into an orchestrated workflow (+5.8 seamlessness)
- **AI as proactive strategist**: BL-135 + BL-146 + BL-147 make the AI suggest next steps instead of waiting passively (+6.4 proactiveness)
- **Zero busywork**: BL-140 (tool call limit), BL-150 (auto-execute), BL-121 (simplified onboarding) reduce unnecessary user interactions
- **Web research**: BL-137 addresses the most embarrassing gap -- the AI writes strategy from training data instead of researching the actual company

**Where alignment weakens**: The sprint is heavier on "connect what exists" than "make what exists better." The AI quality improvements (BL-137, BL-140, BL-150) are correct but underpowered -- the real quality differentiator would be strategy content that is genuinely specific and actionable, not just "uses web_search." More on this under BL-137.

---

## Item-by-Item Review

### BL-134: Fix Import Column Mapping UI Crash [Must Have] [S]
- **Alignment**: Strongly aligned. Blocker. No import = no pipeline.
- **Scope**: Right-sized. Frontend-only fix, backend works perfectly.
- **Priority**: Correct. Must Have is exactly right -- literally nothing works without this.
- **Acceptance Criteria**: Complete. Clear Given/When/Then, includes zero-JS-errors check.
- **Risk**: Low. Backend is confirmed working; this is a null-check bug.
- **Correction for in-flight engineers**: None needed. Ship it.

### BL-136: Fix EntrySignpost for Empty Namespaces [Must Have] [S]
- **Alignment**: Strongly aligned. First-impression failure is fatal for new users.
- **Scope**: Right-sized. Component exists, likely a condition check bug.
- **Priority**: Correct.
- **Acceptance Criteria**: Complete. Covers render conditions and disappearance logic.
- **Risk**: Low.
- **Correction for in-flight engineers**: Ensure the signpost also works when a user deletes all their data (not just first-visit). Test the "has strategy but no contacts" and "has contacts but no strategy" states.

### BL-138: Fix Template Application API [Must Have] [S]
- **Alignment**: Aligned. Template flow is the happy path for onboarding.
- **Scope**: Right-sized.
- **Priority**: Correct, but **drops in importance if BL-121 ships**. BL-121 eliminates the template selector entirely. If BL-121 ships, this fix only matters as a fallback/edge case.
- **Acceptance Criteria**: Complete.
- **Risk**: Low. But there is a **logical conflict with BL-121**: BL-121 removes template selection, so the template API fix becomes dead code. Engineers should clarify which path the onboarding takes and ensure they do not build conflicting flows.
- **Correction for in-flight engineers**: **Check whether BL-121 is also being built. If yes, BL-138 is only needed as a graceful error handler (toast on failure), not as a full template flow fix. Do not invest heavily in template population logic that BL-121 will bypass.**

### BL-142: Fix Cross-Namespace Filter Leakage on Enrich Page [Must Have] [S]
- **Alignment**: Aligned. Data isolation is non-negotiable in multi-tenant SaaS.
- **Scope**: Right-sized. Backend filter needs tenant_id scoping.
- **Priority**: **Should be Should Have, not Must Have.** The baseline rated this as MINOR severity. It is a cosmetic/trust issue, not a blocker. It does not cause data corruption. With 25 items in the sprint, this should not compete for day-1 engineering time.
- **Acceptance Criteria**: Complete.
- **Risk**: Low.
- **Correction for in-flight engineers**: Deprioritize if behind schedule. This is a P2, not P1.

### BL-148: Fix Enrichment Run Button Stuck in Loading State [Must Have] [S]
- **Alignment**: Aligned. Users cannot start enrichment.
- **Scope**: Right-sized.
- **Priority**: Correct. Must Have -- enrichment is step 4-7 of the workflow.
- **Acceptance Criteria**: Complete. Includes 2-second load time expectation.
- **Risk**: Medium. The spec suspects it may be related to BL-142. If the root cause is the same, this is a freebie. If not, it could take longer.
- **Correction for in-flight engineers**: Investigate whether this shares a root cause with BL-142 before building a separate fix.

### BL-137: Add Web Research to Strategy Generation [Must Have] [M]
- **Alignment**: Strongly aligned. This is the difference between "AI tool" and "AI strategist." A strategy consultant who does not research the client is useless.
- **Scope**: **Potentially too narrow.** The spec says "call web_search before generating." But the quality bar should be higher: the AI should synthesize web research findings into every strategy section, not just call web_search once and dump results. The baseline showed placeholder text ("[X] agencies") -- the acceptance criteria should explicitly ban placeholder patterns.
- **Priority**: Correct. Must Have.
- **Acceptance Criteria**: Mostly complete, but **missing**:
  - AC: "No placeholder text patterns ([X], [Y]%, [Z]) appear anywhere in the generated strategy"
  - AC: "At least 3 specific, verifiable facts about the company appear in the strategy (e.g., specific services, team members, venues, clients)"
  - AC: "If web_search returns no results, AI clearly states 'I could not find information about X' rather than fabricating"
- **Risk**: Medium. web_search quality depends on Perplexity API. If the company website is thin or the API returns low-quality results, the strategy quality may not improve much. Engineers should handle the "no good results" case gracefully.
- **Correction for in-flight engineers**: **Add a "research summary" section to the strategy document that cites what was found. The AI should present its web research findings BEFORE generating strategy sections, so the user can validate the source data. Also: implement a check for placeholder patterns and reject any section containing [X], [Y]%, etc.**

### BL-140: Increase Agent Tool Call Limit or Auto-Continue [Must Have] [S]
- **Alignment**: Aligned. Rate limits visible to users = broken experience.
- **Scope**: Right-sized. Either increase limit or implement auto-continue.
- **Priority**: Correct.
- **Acceptance Criteria**: Complete.
- **Risk**: Low for "increase limit" approach. Medium for "auto-continue" approach (more complex). Recommend the simple approach: increase to 15-20.
- **Correction for in-flight engineers**: **Prefer the simple "increase limit" approach. Auto-continue is a bigger project and risks introducing edge cases (duplicate tool calls, lost context). Just raise the number to 15-20 for now.**

### BL-150: AI Agent Should Auto-Execute Tools After Onboarding [Should Have] [M]
- **Alignment**: Aligned. "I'll build your strategy" without executing is the opposite of proactive.
- **Scope**: Right-sized. System prompt adjustment + possibly a code change.
- **Priority**: **Should be Must Have, not Should Have.** This is the single most egregious UX failure: the AI says "I'll do X" and then... does not do X. The user must re-prompt. This directly contradicts the "AI as strategist" vision. Every other user will hit this.
- **Acceptance Criteria**: Complete.
- **Risk**: Medium. System prompt tuning is unpredictable. May require iteration.
- **Correction for in-flight engineers**: **Elevate priority. Test with multiple onboarding scenarios: different business types, different input lengths. The AI must always execute tools on the first turn after onboarding, never respond with only text.**

### BL-141: Add ICP Extraction Feedback and Confirmation [Must Have] [S]
- **Alignment**: Strongly aligned. Silent operations violate "every interaction delivers a result."
- **Scope**: Right-sized.
- **Priority**: Correct.
- **Acceptance Criteria**: Complete. Includes edit capability.
- **Risk**: Low.
- **Correction for in-flight engineers**: None needed.

### BL-143: Implement Playbook Phase 2 -- Contacts Selection [Must Have] [L]
- **Alignment**: Strongly aligned. "Coming soon" is a dead end that breaks the playbook flow.
- **Scope**: Right-sized. Backend APIs already exist.
- **Priority**: Correct.
- **Acceptance Criteria**: Complete. Covers ICP matching, selection, and advancement.
- **Risk**: Medium. The "match score per contact" in the acceptance criteria is vague. What is the scoring algorithm? Is it binary (matches/does not match) or graded? Engineers need clarity.
- **Correction for in-flight engineers**: **Start with binary matching (match/no match based on ICP criteria) rather than a scored ranking. A graded scoring algorithm is a separate effort and should not block this item. Display contacts as "ICP Match" or "Other" with filtering.**

### BL-114: Auto-Advance to Contacts Phase After ICP Extraction [Must Have] [S]
- **Alignment**: Aligned. Removes a manual navigation step.
- **Scope**: Right-sized.
- **Priority**: Correct.
- **Acceptance Criteria**: Complete.
- **Risk**: Low. But depends on BL-141 and BL-143.
- **Correction for in-flight engineers**: None needed.

### BL-121: Simplify Onboarding to 2 Inputs [Should Have] [S]
- **Alignment**: Aligned. Fewer inputs = faster time-to-value.
- **Scope**: Right-sized.
- **Priority**: Correct as Should Have. Nice improvement but the existing 3-step wizard works.
- **Acceptance Criteria**: Complete.
- **Risk**: Low. But **conflicts with BL-138** (template API fix). See BL-138 notes.
- **Correction for in-flight engineers**: **If BL-138 has already been fixed, BL-121 should remove the template selector step entirely (not keep it as a fallback). Clean cut, no dual paths.**

### BL-139: Connect ICP Extraction to Enrichment Triage Rules [Must Have] [M]
- **Alignment**: Strongly aligned. This is the #1 cross-feature integration gap.
- **Scope**: Right-sized. Clear mapping from ICP fields to triage rules.
- **Priority**: Correct. Must Have. Without this, strategy and enrichment remain islands.
- **Acceptance Criteria**: Complete. Includes manual override and backward compatibility.
- **Risk**: Medium. The mapping between ICP text fields and triage evaluator rules could be lossy. "Event management" in the ICP may not exactly match industry categories in the triage system. Engineers need a fuzzy matching or allowlist approach.
- **Correction for in-flight engineers**: **Define the exact field mapping and handle mismatches. ICP industries are freetext; triage rules may use fixed categories. Use a contains/substring match, not exact equality. Document the mapping in the code.**

### BL-116: apply_icp_filters Chat Tool [Must Have] [S]
- **Alignment**: Aligned. AI should be able to filter contacts conversationally.
- **Scope**: Right-sized. File already exists -- verification and integration.
- **Priority**: **Could be Should Have.** The tool already exists in code. If it works, this is just verification. If it does not work, it becomes Must Have.
- **Acceptance Criteria**: Complete.
- **Risk**: Low.
- **Correction for in-flight engineers**: **Test the existing tool first. If it works, mark done and move on. Do not over-engineer.**

### BL-117: Auto-Populate Campaign generation_config from Strategy [Must Have] [S]
- **Alignment**: Aligned. Reduces campaign setup friction.
- **Scope**: Right-sized.
- **Priority**: Correct.
- **Acceptance Criteria**: Complete.
- **Risk**: Low. Clear field mapping.
- **Correction for in-flight engineers**: None needed.

### BL-145: Strategy-Aware Message Generation [Must Have] [M]
- **Alignment**: Strongly aligned. Messages that do not use the strategy context are generic spam.
- **Scope**: Right-sized.
- **Priority**: Correct.
- **Acceptance Criteria**: **Missing testability.** "References strategy messaging angles" is subjective. Need: "Given a strategy with tone='professional, consultative' and angle='corporate entertainment', When messages are generated, Then each message body contains at least 1 strategy-specific keyword from the messaging framework."
- **Risk**: Medium. Prompt engineering quality varies. May require iteration.
- **Correction for in-flight engineers**: **Add strategy context as a structured section in the generation prompt, not as an appended blob. Test with the unitedarts.cz strategy and verify messages mention circus/entertainment, not generic B2B.**

### BL-146: Auto-Enrichment Trigger with Cost Approval Gate [Must Have] [M]
- **Alignment**: Strongly aligned. Import -> Enrich bridge is critical.
- **Scope**: Right-sized. Absorbs BL-131 scope.
- **Priority**: Correct.
- **Acceptance Criteria**: Complete. Includes cost breakdown, balance check, insufficient credits warning.
- **Risk**: Medium. Depends on BL-134 (import) and BL-139 (ICP triage). Both are upstream.
- **Correction for in-flight engineers**: None needed.

### BL-147: Campaign Auto-Setup from Qualified Contacts [Must Have] [M]
- **Alignment**: Strongly aligned. Automates campaign creation from triage results.
- **Scope**: Right-sized.
- **Priority**: Correct.
- **Acceptance Criteria**: Complete. Includes draft status and user approval gate.
- **Risk**: Medium. Depends on BL-139 and BL-145.
- **Correction for in-flight engineers**: **Ensure the campaign is always created in "draft" status. The user MUST approve before any messages are generated. Never auto-generate messages without explicit consent.**

### BL-135: Proactive Next-Step Suggestions in Chat [Must Have] [L]
- **Alignment**: Strongly aligned. This is the highest-impact single item (+5.4 proactiveness). This IS the "strategist-in-residence" experience.
- **Scope**: **Potentially too broad.** 7 trigger points, a new backend endpoint (GET /api/workflow/status), ChatProvider changes, action buttons, polling -- this is pushing toward XL effort disguised as L.
- **Priority**: Correct. Must Have.
- **Acceptance Criteria**: Complete. Each trigger point has a specific suggestion format.
- **Risk**: **High.** This item spans the entire workflow and touches both frontend and backend. If it slips, BL-144 (orchestrator) has no foundation. The 7 trigger points should be prioritized: ship the first 3 (strategy -> extraction -> import) in week 1, the rest in week 2.
- **Correction for in-flight engineers**: **Prioritize trigger points by workflow order. The first 3 (post-strategy, post-extraction, post-import) cover the baseline-tested flow and deliver the most visible improvement. Ship those first. The remaining 4 (post-enrichment, post-triage, post-campaign, post-messages) can follow. Do NOT try to ship all 7 simultaneously.**

### BL-144: End-to-End Workflow Orchestrator [Must Have] [XL]
- **Alignment**: Strongly aligned. This is "the transformation item" per the sprint plan.
- **Scope**: **Too broad for a single sprint item.** A workflow state machine, new model, new API endpoints, a progress bar component, and integration with 5 other items -- this is at least 2 items (backend state machine + frontend progress UI).
- **Priority**: **Should be downgraded to Should Have.** Here is the controversial take: if BL-135 (proactive suggestions) ships with all 7 trigger points, the user GETS the orchestrated experience through the chat. BL-144 adds formal state tracking and a progress bar, but the user-visible improvement is marginal compared to BL-135. The orchestrator is architecturally correct but not necessary for 9/10 seamlessness.
- **Acceptance Criteria**: **Too vague.** "Total user interactions for the full workflow is <= 12" is untestable in this sprint because we cannot run enrichment with real credits. The orchestrator acceptance criteria should focus on: state tracking works, progress bar renders, resumability works.
- **Risk**: **Critical.** XL item at the END of the dependency chain. If any upstream item slips, BL-144 gets compressed into 1-2 days. An XL item cannot be done well in 1-2 days.
- **Correction for in-flight engineers**: **SPLIT this item. Phase A (Sprint 5): Backend state machine + GET /api/workflow/status endpoint. This is the foundation. Phase B (Sprint 6): Frontend progress bar + full integration testing. Ship Phase A this sprint; it enables BL-135 to read state from a real source instead of computing it on the fly. Phase B is polish for the next sprint. Do NOT attempt the full XL scope.**

### BL-126: Contact Import in Playbook [Must Have] [M]
- **Alignment**: Aligned. Keeps users in the playbook flow.
- **Scope**: Right-sized. Reuses existing import components in a modal.
- **Priority**: **Should be Should Have, not Must Have.** Users CAN import contacts via the standalone Import page. The playbook-embedded import is a UX convenience, not a blocker. With 25 items, this can slip without affecting the 9/10 target.
- **Acceptance Criteria**: Complete.
- **Risk**: Medium. Depends on BL-134 and BL-143.
- **Correction for in-flight engineers**: **Deprioritize. If BL-134 and BL-143 are on track, build this. If either is late, skip it. The standalone Import page + BL-135's proactive suggestions ("Import contacts next") covers the same user journey without embedding.**

### BL-131: Credit Cost Estimator Component [Should Have] [S]
- **Alignment**: Aligned. Cost transparency is a product principle.
- **Scope**: Right-sized. Primary scope is in BL-146.
- **Priority**: Correct as Should Have. The reusable component is nice-to-have; the inline version in BL-146 is the must-have.
- **Acceptance Criteria**: Complete.
- **Risk**: Low.
- **Correction for in-flight engineers**: **If BL-146 ships with inline cost display, mark BL-131 as done. Do not build a separate reusable component unless there is time.**

### BL-111: App-Wide Onboarding Signpost + Smart Empty States [Should Have] [L]
- **Alignment**: Aligned. Empty pages are hostile.
- **Scope**: Right-sized.
- **Priority**: Correct as Should Have.
- **Acceptance Criteria**: Complete.
- **Risk**: Low. But L effort for empty states across 5 pages is a lot of polish work.
- **Correction for in-flight engineers**: **Focus on the 2 most-visited empty states: Campaigns page and Enrich page. Contacts page already gets BL-136 (entry signpost). Messages page is rarely visited empty. Ship 2, not 5.**

### BL-149: Namespace Session Persistence [Should Have] [S]
- **Alignment**: Aligned. Small UX improvement.
- **Scope**: Right-sized. localStorage only.
- **Priority**: Correct as Should Have.
- **Acceptance Criteria**: Complete. Includes fallback for inaccessible namespace.
- **Risk**: Low.
- **Correction for in-flight engineers**: None needed.

### BL-151: Strategy Save Progress Indicator Per Section [Could Have] [S]
- **Alignment**: Partially aligned. Polish, not critical.
- **Scope**: Right-sized.
- **Priority**: Correct as Could Have.
- **Acceptance Criteria**: Complete.
- **Risk**: Low.
- **Correction for in-flight engineers**: **Ship only if there is spare time on the last day. This does not move any baseline score meaningfully.**

---

## Critical Issues (STOP items -- engineers must be notified)

### CRITICAL-1: BL-138 and BL-121 Conflict
BL-138 fixes the template application API. BL-121 removes the template selector entirely. If both ship, BL-138 is dead code. Engineers working on BL-138 MUST coordinate with BL-121 to avoid wasted effort. **Resolution**: If BL-121 is in-flight, BL-138 should ONLY fix the error handling (show a toast on failure). Do not invest in template population logic.

### CRITICAL-2: BL-144 Scope Risk
BL-144 is XL and depends on 5 upstream items. It is scheduled for Days 7-9 (last 3 days) of a 9-day sprint. If any upstream item slips by 1 day, BL-144 becomes a 2-day XL, which will result in a half-implemented orchestrator that is worse than no orchestrator (partially tracked state with gaps). **Resolution**: Split BL-144 into backend state machine (Sprint 5) and frontend progress bar (Sprint 6). Engineers should be told NOW that the full orchestrator is optional for this sprint.

### CRITICAL-3: BL-135 is Understaffed
BL-135 (Proactive Suggestions) is the highest-impact item and is L-sized with 7 trigger points spanning the full workflow. It is assigned to a single engineer for 5 consecutive days. This is risky -- if that engineer hits a blocker on trigger point 3, trigger points 4-7 are all delayed. **Resolution**: Assign a second engineer to BL-135 starting Day 3. Split: Engineer A does trigger points 1-3 (strategy/extraction/import flow), Engineer B does trigger points 4-7 (enrichment/campaign/messages flow).

---

## Recommendations

### 1. Items to CUT (if sprint is behind)
- **BL-151** (Could Have, save indicator) -- cosmetic only
- **BL-131** (Should Have, cost estimator component) -- absorbed into BL-146
- **BL-126** (downgrade to Should Have, playbook import) -- standalone import page + proactive suggestions covers this
- **BL-142** (downgrade to Should Have, filter leakage) -- cosmetic, not a blocker

### 2. Items to SPLIT
- **BL-144**: Split into Phase A (backend state machine + API, Sprint 5, M effort) and Phase B (frontend progress bar + full integration, Sprint 6, L effort)
- **BL-135**: Split engineering across 2 engineers -- trigger points 1-3 and trigger points 4-7

### 3. Items to MERGE
- **BL-131 into BL-146**: Already acknowledged in the spec. Do not track BL-131 separately. Close it when BL-146 ships.

### 4. Priority Changes
| Item | Current | Recommended | Reason |
|------|---------|-------------|--------|
| BL-150 | Should Have | **Must Have** | AI saying "I'll do X" without doing it is the worst UX failure in the baseline |
| BL-142 | Must Have | **Should Have** | Minor severity per baseline. Does not affect workflow. |
| BL-126 | Must Have | **Should Have** | Standalone import page works. Playbook embed is convenience. |
| BL-144 | Must Have | **Should Have** (full scope) | BL-135 delivers the user-visible orchestration. BL-144 Phase A is Must Have, Phase B is Should Have. |

### 5. Missing Items
- **Missing: Enrichment progress in chat.** BL-146 triggers enrichment and BL-135 suggests it, but neither item specifies how enrichment PROGRESS is shown to the user during the 10-30 minute enrichment run. The chat should show "L1 enrichment: 3/8 companies done..." in real-time. Without this, there is a 10-30 minute dead zone where the user has no feedback. This is a gap between BL-146 and BL-144.
- **Missing: Error recovery for failed enrichment.** What happens when 2 of 8 companies fail L1 enrichment? Does the workflow stall? Does the chat suggest retrying? Neither BL-135 nor BL-144 cover this edge case.
- **Missing: "Back" navigation in the workflow.** BL-144 tracks forward progress, but what if the user wants to go back and edit their strategy after seeing contacts? The orchestrator needs to handle backward transitions gracefully (not force linear progression).

---

## Minimum Viable Sprint (if we had to ship only 12 items)

If the sprint is behind and we need to cut to a core set, these 12 items deliver 80% of the seamlessness improvement:

| Priority | Item | Rationale |
|----------|------|-----------|
| 1 | **BL-134**: Import crash fix | Blocker. Nothing works without import. |
| 2 | **BL-136**: EntrySignpost fix | First-impression fix. |
| 3 | **BL-148**: Enrich run button fix | Enrichment is step 4-7 of workflow. |
| 4 | **BL-140**: Tool call limit increase | Eliminates re-prompting. Quick fix. |
| 5 | **BL-150**: Auto-execute tools | AI must act, not just talk. |
| 6 | **BL-137**: Web research in strategy | Strategy quality is the foundation. |
| 7 | **BL-141**: Extraction feedback | Silent operations are invisible. |
| 8 | **BL-143**: Phase 2 contacts | Removes "Coming soon" dead end. |
| 9 | **BL-114**: Auto-advance | Connects Phase 1 to Phase 2. |
| 10 | **BL-139**: ICP to triage | Connects strategy to enrichment. |
| 11 | **BL-135**: Proactive suggestions (first 3 triggers) | The seamlessness transformation. |
| 12 | **BL-145**: Strategy-aware messages | Message quality depends on strategy. |

These 12 items fix all blockers, connect the first 5 steps of the workflow, and add proactive guidance. The remaining 13 items are either polish (BL-111, BL-149, BL-151), convenience (BL-126, BL-131), deeper integration (BL-116, BL-117, BL-146, BL-147), or architecturally premature (BL-144 full scope).

**Expected outcome of minimum set**: Seamlessness 3.2 -> 7.0 (not 9.0, but a massive improvement). Proactiveness 2.6 -> 6.5. The remaining gap to 9.0 comes from Sprint 6 (orchestrator + campaign automation + enrichment triggers).

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BL-144 scope creep | High | High | Split into 2 phases |
| BL-135 single-engineer bottleneck | Medium | High | Add second engineer |
| BL-138/BL-121 conflict | High | Medium | Coordinate NOW |
| Web research API quality (BL-137) | Medium | Medium | Graceful fallback for thin websites |
| Enrichment progress dead zone | High | Medium | Add progress display to BL-146 scope |
| Critical path slippage (BL-141->139->146->144) | Medium | High | BL-144 Phase A only; Phase B deferred |

---

## Summary of Corrections for In-Flight Engineers

1. **BL-138 engineer**: Check if BL-121 is also being built. If yes, only fix the error toast, do not rebuild template population.
2. **BL-137 engineer**: Add placeholder pattern rejection, require 3+ verifiable facts, show research summary before strategy.
3. **BL-140 engineer**: Prefer simple limit increase (15-20) over auto-continue.
4. **BL-143 engineer**: Use binary ICP matching (match/no match), not graded scoring.
5. **BL-135 engineer**: Prioritize trigger points 1-3 for Week 1. Do not attempt all 7 simultaneously.
6. **BL-144 engineer**: Build backend state machine + API only. Frontend progress bar is Sprint 6.
7. **BL-142 engineer**: This is P2, not P1. Deprioritize if behind.
8. **BL-126 engineer**: Skip if BL-134 or BL-143 are late.
9. **BL-145 engineer**: Add strategy context as structured prompt section, test with unitedarts.cz data.
10. **BL-150 engineer**: This is more important than its priority suggests. Test multiple onboarding scenarios.
