# Sprint 5.1 PM Challenge (REVISED)

**Challenger**: PM Analyst
**Date**: 2026-03-03
**Revision**: v2 -- updated after scope change: real enrichment is approved for test (2-3 companies, cost-capped)
**Scope**: Challenge the Sprint 5.1 spec's projections, identify missed quick wins, and assess realistic paths to 9/10 -- now that ALL 10 steps are testable.

---

## Scope Change Impact

The original spec assumed steps 5-10 were permanently untested due to enrichment cost/time. The user has confirmed we CAN and SHOULD run real enrichment during the baseline test:

- **3 companies** through full pipeline (L1 -> Triage -> L2 -> Person)
- **~3-4 contacts** through person enrichment
- **Estimated cost**: ~$0.80-$1.00 total
  - L1: 3 x $0.02 = $0.06
  - Triage: 3 x $0.00 = free (rules-based)
  - L2: ~2 passed companies x $0.08 = $0.16
  - Signals: 3 x $0.05 = $0.15
  - Registry/ARES: 3 x $0.00 = free (CZ companies)
  - News: 3 x $0.04 = $0.12
  - Person: ~4 contacts x $0.04 = $0.16
  - Social/Career/Details: ~4 contacts x $0.07 = $0.28
  - Message generation: ~4 contacts x ~$0.01 = $0.04
- **Processing time**: ~10-15 minutes for the full DAG

**This fundamentally changes the analysis.** The "6 untested steps dragging down the aggregate" constraint is eliminated. Every step can now be scored against real behavior.

---

## Is 7.5 the Real Ceiling?

**The original answer was "no, it's ~8.0 for 4 tested steps." With all 10 steps testable, the question transforms: what's the realistic 10-step aggregate?**

### The Spec's Structural Problem

The spec projects these aggregates assuming 6 steps are untested:

| Dimension | Spec Projects |
|-----------|:------------:|
| Completeness | 7.6 |
| Seamlessness | 5.0 |
| Proactiveness | 4.3 |
| **Grand Average** | **~6.7** |

These numbers are artificially low because untested steps default to seamlessness=3, proactiveness=2. With real testing, steps 5-10 will score MUCH higher than those defaults.

### What Steps 5-10 Should Actually Score

Based on the stage registry, the DAG executor, campaign routes, message generator, and triage evaluator code I've reviewed:

**Step 5 -- Basic Enrichment (L1):**
- DAG visualization is confirmed working (baseline-002: "10 stages across 5 categories")
- CostEstimator component will render after frontend deploy
- Run button confirmed functional in baseline-002 ("Run 10 stages")
- With frontend fix: namespace scoping works, tag filter correct
- Real test: run L1 on 3 companies, observe progress, verify results in UI
- **Projected**: availability=8, seamlessness=6, proactiveness=5, ai_quality=7, user_effort=8

**Step 6 -- Qualification/Triage:**
- Triage is rules-based ($0.00 per entity), runs automatically after L1
- `triage_evaluator.py` evaluates against configurable rules (tier, industry, geo, B2B, revenue)
- Results appear in the enrichment review queue
- Real test: verify 3 companies are classified (Passed/Review/Disqualified)
- **Projected**: availability=7, seamlessness=5, proactiveness=4, ai_quality=null, user_effort=8

**Step 7 -- Deep Enrichment (L2 + Person):**
- L2 depends on triage passing (hard_dep: triage)
- Person depends on L1 (hard_dep: l1), with soft deps on l2 and signals
- Real test: run L2 on ~2 triage-passed companies, person enrichment on ~3-4 contacts
- **Projected**: availability=7, seamlessness=5, proactiveness=4, ai_quality=7, user_effort=7

**Step 8 -- Campaign Creation:**
- Full CRUD confirmed (`POST /api/campaigns`, template system, contact assignment)
- Campaign detail page has 6 tabs: Contacts, Generation, Review, Outreach, Analytics, Settings
- WorkflowSuggestions should suggest "Create a campaign" after enrichment
- Real test: create campaign, add enriched contacts, select template
- **Projected**: availability=8, seamlessness=5, proactiveness=5, ai_quality=null, user_effort=8

**Step 9 -- Message Generation:**
- `start_generation()` runs in background thread via Claude Haiku
- Uses strategy messaging framework + enrichment data per contact
- Cost estimation available (`estimate_generation_cost()`)
- Real test: generate messages for ~3-4 contacts, verify personalization
- **Projected**: availability=8, seamlessness=6, proactiveness=4, ai_quality=7, user_effort=8

**Step 10 -- Message Review + Launch:**
- Review queue with approve/reject/edit/regenerate
- Email sending via Resend API, LinkedIn queuing
- Real test: review generated messages, approve some, edit one
- **Projected**: availability=7, seamlessness=5, proactiveness=3, ai_quality=7, user_effort=7

### Revised Full 10-Step Projection

| Step | Avail | Seamless | Proactive | AI Qual | User Effort |
|------|:-----:|:--------:|:---------:|:-------:|:-----------:|
| 1. Login + Nav | 9 | 8 | 8 | -- | 9 |
| 2. Strategy | 9 | 8 | 8 | 9 | 9 |
| 3. Extraction | 8 | 7 | 6 | 7 | 8 |
| 4. Import | 9 | 7 | 6 | 9 | 9 |
| 5. L1 Enrichment | 8 | 6 | 5 | 7 | 8 |
| 6. Triage | 7 | 5 | 4 | -- | 8 |
| 7. L2 + Person | 7 | 5 | 4 | 7 | 7 |
| 8. Campaign | 8 | 5 | 5 | -- | 8 |
| 9. Msg Generation | 8 | 6 | 4 | 7 | 8 |
| 10. Review + Launch | 7 | 5 | 3 | 7 | 7 |
| **Average** | **8.0** | **6.2** | **5.3** | **7.5** | **8.1** |

**Grand average across all dimensions: ~7.0**

Compare to the spec's 6.7 aggregate. With real testing, the number rises to ~7.0 because:
1. Steps 5-10 score 7-8 on availability (not the conservative 5-7 from inventory assumptions)
2. Steps 5-10 score 5-6 on seamlessness (manual navigation but working), not the default 3
3. Steps 5-10 score 3-5 on proactiveness (WorkflowSuggestions renders on some, others still passive)

### Why Not 9/10?

The 10-step aggregate settles around **7.0**, not 9.0, because:

1. **Seamlessness (6.2)**: Steps 5-10 still require manual page navigation. There are no auto-transitions from enrichment -> triage -> campaign -> messages. The user must discover the flow.
2. **Proactiveness (5.3)**: WorkflowSuggestions helps on steps 1-5, but steps 6-10 get diminishing returns because the suggestions are page-level ("Go to Campaigns") not step-level ("Run message generation for your 4 enriched contacts").
3. **The back half of the workflow is less polished**: Campaign creation, message generation, and review are functional but not guided. These are "power user" features that assume the user knows the flow.

---

## Quick Wins Being Missed

### 1. E2E Test Should Include Enrichment Steps

The spec's Item 4 (E2E framework) only tests steps 1-4. With enrichment now testable, the E2E suite should include:

```
test('L1 enrichment runs on 3 companies with cost under $0.10')
test('triage classifies companies after L1')
test('campaign creation adds enriched contacts')
test('message generation produces personalized messages')
test('review queue shows generated messages for approval')
```

These don't need to be full Playwright browser tests -- API-level tests are sufficient for steps 5-9 (the enrichment and campaign APIs are well-structured). Only step 10 (review UI) benefits from browser testing.

**Impact**: Converts the E2E framework from a deployment sanity check into a full workflow regression suite.

### 2. Cost-Capped Enrichment Run in E2E

The E2E test should include a hard cost cap. The DAG executor tracks `cost_usd` per entity per stage. The test should:
1. Start enrichment for 3 specific companies (select by name, not "all")
2. Assert total cost stays under $1.00
3. Assert all 3 companies have L1 results
4. Assert triage ran (status updated)

This prevents runaway costs if someone accidentally runs it on the full batch.

### 3. WorkflowSuggestions on EVERY Page

The `WorkflowSuggestions` component renders in the chat panel. But the chat panel is only visible on pages that have it (Playbook, Contacts). On the Enrich page, Campaigns page, and Messages page, there may not be a chat panel, meaning WorkflowSuggestions won't render.

**Quick win**: Verify which pages actually show WorkflowSuggestions. If it's only Playbook/Contacts, the proactiveness scores for steps 5-10 should be lower than projected. If it shows on all pages, the scores hold.

### 4. Strategy-to-Triage Pipeline Connection

The ideal workflow says ICP criteria from the strategy should auto-populate triage rules. Currently, `triage_evaluator.py` uses `DEFAULT_TRIAGE_RULES` which are hardcoded defaults. If the triage evaluation doesn't use the extracted ICP data from the strategy, then step 6 (Triage) scores lower on AI Quality because the qualification is generic, not strategy-informed.

**Quick win**: Check if the triage rules are populated from `extracted_data` after ICP extraction. If not, this is a gap that should be flagged for Sprint 5.2 (not a Sprint 5.1 fix, but it affects scoring).

### 5. Message Generation Quality Check

Step 9 (Message Generation) is where the strategy-to-outreach loop closes. The message generator should use:
- Strategy messaging framework (from `StrategyDocument.extracted_data`)
- L2 company intel (from `company_enrichment_l2`)
- Person enrichment (from contact enrichment records)

**Quick win**: Verify that the generated messages actually reference enrichment data. If messages are generic ("Hi, I noticed your company...") instead of specific ("Hi Jan, I saw EventPro's expansion into corporate events..."), the ai_quality score drops from 7 to 5.

---

## Proactiveness Deep Dive

### What BL-135 Actually Does (Unchanged from v1)

The `WorkflowSuggestions` component is a stateful suggestion engine:
- Backend inspects: has_strategy, has_extracted, contact_count, enriched_count, message_count, campaign_count, active_campaigns
- Returns up to 2 contextual suggestion cards with action buttons
- Cards navigate to the relevant page

### How Proactiveness Maps Across All 10 Steps

| Step | Has WorkflowSuggestions? | Has Chat Guidance? | Proactiveness Level |
|------|:------------------------:|:------------------:|:-------------------:|
| 1. Login | Yes (EntrySignpost + Suggestions) | No | 7-8 (concrete cards) |
| 2. Strategy | Yes (chat panel) | Yes (AI suggests next step) | 7-8 |
| 3. Extraction | Yes (chat panel) | Partial (toast) | 5-6 |
| 4. Import | Unlikely (import page may not have chat) | No | 4-5 (just the UI flow) |
| 5. L1 Enrichment | Maybe (enrich page may have suggestions) | No | 4-5 |
| 6. Triage | No (auto-triggered after L1) | No | 3 (runs silently) |
| 7. L2 + Person | Maybe (same as L1) | No | 4 |
| 8. Campaign | Maybe (campaigns page) | No | 4-5 |
| 9. Msg Generation | Maybe (campaign detail page) | No | 3-4 |
| 10. Review | No (review queue is focused UI) | No | 3 |
| **Average** | | | **~5.0** |

**Key insight**: Proactiveness degrades as you move through the workflow because the later steps have less chat integration and fewer suggestion touchpoints. Steps 1-3 benefit most from BL-135; steps 6-10 barely benefit.

### What's Needed for 9/10 Proactiveness (All Steps)

The gap is clear: the "strategist-in-residence" pattern needs to extend beyond the Playbook page. Specifically:

1. **After L1 enrichment completes**: Chat should say "L1 complete. 3 companies profiled: 2 match your ICP (event agencies), 1 needs review. Shall I run triage?"
2. **After triage**: "Triage done. 2 companies passed, 1 in review. Ready for deep enrichment on the 2 qualified companies?"
3. **After L2/Person**: "Deep research complete. I found strategic signals for EventPro (expanding into corporate events) and CreativeAgency (new BD director). Ready to create a campaign?"
4. **After campaign creation**: "Campaign 'Czech Event Agencies Q1' created with 3 contacts. Generate personalized messages? Estimated cost: ~40 credits."
5. **After message generation**: "4 messages generated (2 LinkedIn, 2 email). Ready for your review."

Each of these is a conversational prompt with an inline action. This is Sprint 5.2 work, not Sprint 5.1.

---

## Revised Score Projection (All 10 Steps Testable)

### 10-Step Aggregate

| Dimension | baseline-002 | Spec (6 untested) | PM Revised (all tested) | Delta vs Spec |
|-----------|:-----------:|:-----------------:|:----------------------:|:------------:|
| Completeness | 6.7 | 7.6 | **8.0** | +0.4 |
| Seamlessness | 3.4 | 5.0 | **6.2** | +1.2 |
| AI Quality | 7.0 | 8.3 (3 outputs) | **7.5** (7 outputs) | -0.8 |
| User Effort | 7.4 | 8.2 | **8.1** | -0.1 |
| Proactiveness | 2.8 | 4.3 | **5.3** | +1.0 |
| **Grand Average** | **5.5** | **6.7** | **7.0** | **+0.3** |

**Important notes on the AI Quality drop**: The spec's 8.3 is inflated because only 3 outputs are scored (strategy, import mapper, and extraction -- all strong performers). When you add 4 more outputs (L1 profiles, L2 research, triage results, generated messages), the average will likely drop because:
- L1 profiles are Perplexity sonar output (good but formulaic, ~7/10)
- L2 research quality varies (7-8/10 for well-known companies, 5-6 for obscure ones)
- Generated messages may be generic if strategy-to-message pipeline isn't tightly connected (6-8/10)

The aggregate drops from 8.3 to ~7.5, but this is HONEST -- it reflects actual AI output quality across the full workflow, not just the cherry-picked best outputs.

### Tested-Step Breakdown

| Dimension | Steps 1-4 Avg | Steps 5-7 Avg | Steps 8-10 Avg | All 10 Avg |
|-----------|:------------:|:------------:|:--------------:|:---------:|
| Completeness | 8.75 | 7.3 | 7.7 | **8.0** |
| Seamlessness | 7.5 | 5.3 | 5.3 | **6.2** |
| AI Quality | 8.3 | 7.0 | 7.0 | **7.5** |
| User Effort | 8.75 | 7.7 | 7.7 | **8.1** |
| Proactiveness | 7.0 | 4.3 | 3.7 | **5.3** |

**The pattern is clear**: Steps 1-4 (the "strategy + import" loop) score ~8.0. Steps 5-10 (the "enrich + outreach" loop) score ~6.0. The system's front half is significantly more polished than its back half.

---

## Sprint 5.2 Recommendations (Updated)

With all 10 steps now testable, the recommendations shift from "make steps testable" to "close the quality gap between front half and back half."

### Priority 1: Chat-Initiated Workflow Actions for Steps 5-10

The front half (1-4) has WorkflowSuggestions. The back half (5-10) needs the same treatment but through the chat panel, because enrichment and campaign workflows are more complex than "click here to go to the next page."

**Minimum viable implementation**:
- After each DAG stage completion, push a chat message with results summary + next-step proposal
- After campaign creation, chat suggests "Generate messages?"
- After message generation, chat suggests "Open review queue"

**Impact**: Proactiveness for steps 5-10 goes from ~4 to ~7. Overall proactiveness goes from 5.3 to ~6.8.

### Priority 2: Strategy-to-Triage Pipeline (Seamlessness)

Connect ICP extraction output to triage rules. Currently `DEFAULT_TRIAGE_RULES` are hardcoded. After extraction, the rules should auto-populate from `extracted_data`. This makes step 6 feel like a continuation of step 3, not an isolated feature.

**Impact**: Step 6 seamlessness goes from 5 to 7. AI Quality gets scored because triage is strategy-informed.

### Priority 3: Enrichment Progress UX

The enrich page DAG is visually impressive but lacks real-time feedback during execution. During the 10-15 minute enrichment run, the user should see:
- Per-entity progress (3/3 L1 complete)
- Per-stage cost accumulation
- Error handling for failed entities

**Impact**: Step 5 and 7 user_effort goes from 7-8 to 9. Seamlessness also improves.

### Priority 4: Message Personalization Depth

The message generator needs to pull from enrichment data effectively. Test the actual messages generated and score their specificity. If they're generic, this is the highest-impact AI Quality improvement.

**Impact**: Step 9 ai_quality goes from 7 to 8-9 if messages reference specific company intel.

### Revised Sprint 5.2 Feature Shortlist

| Feature | Impact (10-step avg) | Effort | Primary Dimension |
|---------|:-------------------:|--------|-------------------|
| Chat-initiated actions (steps 5-10) | +1.5 proactiveness | Medium | Proactiveness |
| Strategy-to-triage pipeline | +0.5 seamlessness, +0.5 AI quality | Low | Seamlessness + AI Quality |
| Enrichment progress UX | +0.3 user_effort, +0.3 seamlessness | Medium | User Effort |
| Message personalization audit | +0.5 AI quality | Low | AI Quality |
| Auto-phase transitions (steps 2-4) | +0.5 seamlessness | Low | Seamlessness |
| **Combined 5.2 potential** | **~7.0 -> 8.5** | | |

---

## Test Redesign Suggestions (Updated)

### The Test Now Has Two Modes

**Tier A: "Dry Run" (Steps 1-4 + page verification for 5-10)** -- runs in ~5 minutes, no credits. Validates deployment, UI rendering, navigation, WorkflowSuggestions. This runs after every deploy.

**Tier B: "Wet Run" (Full 10-step workflow with real enrichment)** -- runs in ~20-30 minutes, costs ~$1. Validates the complete end-to-end flow including enrichment quality, triage accuracy, message personalization, and review UX. This runs after each sprint.

### E2E Test Structure for Tier B

```typescript
test.describe('Full Workflow (Wet Run)', () => {
  // Step 5: Run L1 enrichment on 3 companies
  test('L1 enrichment completes for 3 companies under $0.10', async () => {
    // Select 3 specific companies by name
    // Start DAG with only l1 stage
    // Assert completion, cost, and results
  })

  // Step 6: Verify triage ran
  test('triage classifies 3 companies after L1', async () => {
    // Assert company statuses updated (Passed/Review/Disqualified)
    // At least 1 should pass (for downstream testing)
  })

  // Step 7: Run L2 + Person on passed companies
  test('L2 + Person enrichment completes for qualified companies', async () => {
    // Start DAG with l2, person stages
    // Assert completion, cost under $0.50
  })

  // Step 8: Create campaign with enriched contacts
  test('campaign creation with enriched contacts succeeds', async () => {
    // POST /api/campaigns
    // Add contacts from triage-passed companies
    // Assert campaign created with contact count > 0
  })

  // Step 9: Generate messages
  test('message generation produces personalized messages', async () => {
    // POST /api/campaigns/{id}/generate
    // Wait for completion
    // Assert messages created, check for enrichment data references
  })

  // Step 10: Review queue
  test('review queue shows generated messages for approval', async () => {
    // Navigate to campaign review tab
    // Assert messages visible
    // Approve one, edit one
  })
})
```

### Cost Cap Guardrail

The test MUST include a hard cost assertion:

```typescript
test.afterAll(async () => {
  // Query total cost from entity_stage_completions
  const totalCost = await getTotalTestCost('unitedarts')
  expect(totalCost).toBeLessThan(1.50) // Hard cap at $1.50
})
```

### Score Reporting: Dual Aggregate

Report both:
1. **Tested-steps average** across all scored steps (should be all 10 now)
2. **Front-half vs back-half** split (Steps 1-4 vs Steps 5-10) to track where quality lives

---

## Summary Verdict (Revised)

| Question | Original Answer (v1) | Revised Answer (v2) |
|----------|---------------------|---------------------|
| Is 7.5 the ceiling? | No, ~8.0 for 4 tested steps | With all 10 tested, 10-step aggregate is ~7.0 |
| Can we hit 9/10 in 5.1? | No (only 4 steps testable) | No. 10-step aggregate is ~7.0. Steps 5-10 drag it down (seamlessness ~5, proactiveness ~4) |
| What's the realistic 5.1 target? | ~8.0 on tested steps | **~7.0 on all 10 steps, ~8.0 on steps 1-4** |
| What blocks 9/10? | Untested steps | Back-half polish: no chat guidance for steps 5-10, no strategy-to-triage connection, generic messages |
| When can we hit 9/10? | Sprint 5.2 + Sprint 6 | Sprint 5.2 (chat actions + strategy-triage pipeline) could reach **~8.5**. Sprint 6 for 9.0. |
| Test redesign needed? | Split into tiers | Yes, Tier A (dry, every deploy) + Tier B (wet, every sprint). Include cost cap. Report dual aggregates. |

### The Honest Math

- **Sprint 5.1 realistic**: 7.0/10 (all 10 steps)
- **Sprint 5.2 realistic**: 8.0-8.5/10 (chat actions + strategy pipeline close the gap)
- **Sprint 6 target**: 9.0/10 (auto-transitions + deep message personalization + closed-loop learning)

The spec's 4 items are correct and necessary. They fix the deployment gap and the 3 verified bugs. But the spec's framing ("7.5 is the ceiling") was based on only testing 4 steps. Now that we can test all 10, the honest aggregate is 7.0, and the path to 9.0 is clearer: it's about making the back half of the workflow as polished and proactive as the front half.
