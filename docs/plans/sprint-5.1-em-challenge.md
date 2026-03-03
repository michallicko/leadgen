# Sprint 5.1 EM Challenge

**Challenger**: Claude Opus 4.6 (EM agent)
**Date**: 2026-03-03 (updated with Steps 5-10 scope expansion)
**Verdict**: **NEEDS REVISION** (Items 1 and 2 have issues; Items 3 and 4 are solid; Steps 5-10 projections are mostly realistic but over-optimistic on triage chaining)

---

## Per-Item Verdict

### Item 1: Import Response Format (B1 + B2)

**Root cause verified: YES -- with caveats**

I read the actual code. The diagnosis is correct:

1. `_build_upload_response()` at `import_routes.py:115` iterates over `mapping_result.get("mappings", [])` and copies `m.get("target")` directly to `target_field` (line 116, 135). Claude's prompt in `csv_mapper.py:130` explicitly says `"target": the target field name (prefixed with "contact." or "company.")`. So the API returns `"contact.first_name"` as `target_field`.

2. The frontend `TARGET_OPTIONS` in `MappingStep.tsx:23-40` uses flat values: `"first_name"`, `"last_name"`, `"email"`, `"company_name"`, `"domain"`, `"industry"`, etc. The `<select>` at line 168 uses `value={col.target_field ?? ''}`, so `"contact.first_name"` will not match `"first_name"` and the dropdown defaults to `""` ("-- Skip --").

3. `apply_mapping()` at `csv_mapper.py:288` does `mapping_result.get("mappings", [])` -- it expects a dict with `"mappings"` key. The frontend sends `{ mapping: ColumnMapping[] }` which is a flat array. A list has no `.get()` method -> `AttributeError`.

**Root cause is correct.**

**Fix will work: PARTIALLY -- there is a mapping gap in the reverse conversion**

The forward conversion (Change 1) is mostly correct but has a **critical gap**:

- Claude's company target fields include: `name`, `domain`, `industry`, `hq_city`, `hq_country`, `company_size`, `business_model` (from `TARGET_FIELDS["company"]` at `csv_mapper.py:26-34`)
- The spec's conversion: `company.name -> company_name`, `company.domain -> company_domain`, `company.industry -> company_industry`
- But the frontend's `TARGET_OPTIONS` has: `company_name`, `domain` (NOT `company_domain`), `industry` (NOT `company_industry`), `employee_count` (NOT `company_company_size`), `location` (NOT `company_hq_city`), `description` (NOT `company_description`)

**The spec's simple rule `elif entity == "company": target = f"company_{field}"` would produce:**

| Claude output | Spec's conversion | Frontend expects | MATCH? |
|---|---|---|---|
| `company.name` | `company_name` | `company_name` | YES |
| `company.domain` | `company_domain` | `domain` | **NO** |
| `company.industry` | `company_industry` | `industry` | **NO** |
| `company.hq_city` | `company_hq_city` | `location` | **NO** |
| `company.company_size` | `company_company_size` | `employee_count` | **NO** |
| `company.business_model` | `company_business_model` | (not in TARGET_OPTIONS) | **NO** |

Only `company.name -> company_name` works. The other company fields are **completely wrong** under the spec's conversion rule.

The reverse conversion (`_frontend_to_claude_mapping`) has the same problem in the opposite direction. It hardcodes a list of company fields (`domain`, `industry`, `employee_count`, `location`, `description`) but misses `hq_city`, `hq_country`, `company_size`, `business_model`. And it maps `domain -> company.domain` which is correct, but the forward conversion already broke the chain.

**The fix needs a proper bidirectional mapping table, not a simple prefix rule.**

Correct approach:
```python
CLAUDE_TO_FRONTEND = {
    "contact.first_name": "first_name",
    "contact.last_name": "last_name",
    "contact.email_address": "email",     # NOTE: Claude field is "email_address" not "email"!
    "contact.phone_number": "phone",      # NOTE: Claude field is "phone_number" not "phone"!
    "contact.job_title": "job_title",
    "contact.linkedin_url": "linkedin_url",
    # etc.
    "company.name": "company_name",
    "company.domain": "domain",
    "company.industry": "industry",
    "company.hq_city": "location",        # Approximate match
    "company.company_size": "employee_count",  # Approximate match
}
```

**ADDITIONAL BUG**: The spec and debug report show Claude maps to `contact.email`, but the actual `TARGET_FIELDS["contact"]` list has `email_address` (not `email`). Similarly `phone_number` not `phone`. Claude may use its own judgment and produce `contact.email` instead of `contact.email_address`, but this is non-deterministic. The mapping must handle both variants.

**Edge cases missed:**

1. **CSV with no matching headers**: If Claude returns all `"target": null` mappings, the frontend shows all "-- Skip --". This is correct behavior, not a bug. OK.
2. **Claude returns unknown field names**: If Claude invents a target like `contact.full_name` (not in TARGET_FIELDS), the forward conversion would strip to `full_name` which is not in TARGET_OPTIONS. The dropdown would show "-- Skip --". Degraded but safe.
3. **Column mapping stored then retrieved**: The `preview_import()` stores `mapping` via `job.column_mapping = json.dumps(mapping)`. But `mapping` here is either the frontend's ColumnMapping[] or the Claude format dict. The spec's fix stores the converted Claude format, which is correct. But `import_status()` at line 645 reads `job.column_mapping` and passes it to `_build_upload_response()` which expects Claude format. This path works because the stored value IS in Claude format after the conversion. OK.
4. **`execute_import_job()`** at line 502 reads `job.column_mapping` (Claude format) and passes to `apply_mapping()`. If the `preview_import()` fix stores converted Claude format correctly, this path works. But if the preview stores the raw frontend array (which the current buggy code does via `json.dumps(mapping)` where `mapping` is a list), then `execute_import_job` inherits the bug. The spec addresses this correctly -- after the fix, `job.column_mapping` is always Claude format.

**Breaking changes:**

None -- `_build_upload_response()` is only called in 3 places: `upload_csv()`, `remap_import()`, and `import_status()`. All receive Claude-format mapping. The forward conversion only affects the response shape, not stored data.

**E2E test adequate: PARTIALLY**

The E2E test at the spec's line 284-326 tests the upload + mapping UI path. However:
- It relies on a test CSV file (`tests/fixtures/test-contacts.csv`) that doesn't exist yet. The spec doesn't specify its contents.
- The API-level tests (lines 758-847) are much better -- they test the actual response format and preview path directly.
- The API-level test for preview (line 801-847) correctly sends frontend-format mapping and checks for 200 status. This is the critical test.

**Score projection realistic: PARTIALLY**

- availability 6->9: Realistic IF the mapping table is correct. With the broken company field mapping, some fields would still show "-- Skip --", so more like 7-8.
- seamlessness 2->7: Optimistic. Even with perfect mapping, the user still needs to review and click Preview and Import manually. 5-6 is more honest.
- user_effort 1->9: Removing 3 workarounds is correct math. But the "slight friction for manual review" is more like 2 interactions, so 8 is more honest.

**Verdict: NEEDS REVISION**

The forward conversion rule `company.X -> company_X` is wrong for most company fields. Need an explicit mapping table that accounts for the mismatch between Claude's TARGET_FIELDS names and the frontend's TARGET_OPTIONS values. Also need to handle the `email_address` vs `email` and `phone_number` vs `phone` discrepancy.

---

### Item 2: Web Search Prompt (A2)

**Root cause verified: YES**

I read the actual prompt at `playbook_service.py:231-315`. The structure is exactly as described:

1. Lines 235-244: "MANDATORY WEB RESEARCH (non-negotiable)" -- top-level, correctly positioned
2. Lines 246-286: "FIRST MESSAGE BEHAVIOR (critical -- when chat history is empty...)" -- gated on empty history
3. Lines 304-312: "SUBSEQUENT MESSAGES" -- says "If the user asks you to **generate or draft** strategy sections, ALWAYS call web_search first"

The verb coverage gap ("generate or draft" but not "update/refine/revise") is a real issue. The AI in baseline-002 was asked to "update" and interpreted that as not matching "generate or draft".

**Fix will work: PROBABLY -- but it's prompt engineering, not deterministic**

The proposed fix is to:
1. Add "HARD RULE: Before ANY call to `update_strategy_section`..." to SUBSEQUENT MESSAGES
2. Add a CRITICAL REMINDER block at the end

This is the right approach for prompt engineering. However:

- **Prompt compliance is probabilistic, not guaranteed.** Even with "HARD RULE" and "CRITICAL REMINDER", Claude models may still skip web_search if the context is long enough or the user provides very specific details. The spec should acknowledge this and set a realistic expectation (e.g., "web_search called in 90%+ of turns" not "100%").
- **No programmatic enforcement.** The spec mentions "Consider enforcement: Add a check in agent_executor.py" but doesn't include it in the actual fix. A server-side check that logs a warning when `update_strategy_section` is called without a preceding `web_search` in the same turn would be a much stronger guarantee.
- **The acceptance criteria say "MUST call web_search"** but the E2E test is weak -- it checks for placeholder absence and optionally for tool call indicators, but doesn't reliably detect whether web_search was actually called. The tool call UI may not be visible or may have different selectors.

**Edge cases missed:**

1. **Perplexity API failure**: If `web_search` fails (rate limit, API error), the AI will proceed without it. The prompt should say "If web_search fails, acknowledge to the user that research was unavailable."
2. **Very long conversation context**: In turn 10 of a long strategy refinement, the AI may deprioritize the web_search instruction as it gets pushed far from the most recent instructions.
3. **Multiple sections in one turn**: If the user asks to "update all 9 sections", the AI should call web_search once at the beginning (not 9 times). The spec's wording "at least once in this conversation turn" is correct.

**Breaking changes:**

None -- this is a prompt text change only. Other phases (contacts, messages, campaign) are not affected.

**E2E test adequate: NO**

The E2E test (spec lines 428-465) is fundamentally weak:
- It checks for placeholder text (`[X]`, `[Y]`) but the AI may produce generic text without placeholders that still isn't grounded in research.
- The tool call detection (`page.locator('[data-testid="tool-call"]')`) depends on UI elements that may not exist or may have different test IDs.
- **More importantly**: This test takes 60+ seconds (waiting for AI response) and is non-deterministic. It should be a backend integration test, not a Playwright test. A backend test could inspect the `tool_calls` list in the agent executor's response to deterministically verify `web_search` was called.

**Score projection realistic: PARTIALLY**

- ai_quality 7->9: Possible but depends on AI compliance. With current prompt-only approach, 8 is more honest (sometimes it will still skip web_search).

**Verdict: NEEDS REVISION**

1. Add programmatic logging/warning when `update_strategy_section` is called without prior `web_search` in the same turn.
2. Acknowledge that prompt compliance is probabilistic and adjust score projection to 8 instead of 9.
3. Replace or supplement the Playwright E2E test with a backend integration test that verifies tool call sequence.

---

### Item 3: Fix Deployment Pipeline

**Root cause verified: YES**

I read `deploy-revision.sh` end to end. The script:
1. Builds frontend (line 30-32)
2. Copies API source to `/home/ec2-user/leadgen-api-rev-{COMMIT}` (lines 37-50)
3. Copies frontend build to `/srv/dashboard-rev-{COMMIT}` (lines 55-57)
4. Generates docker-compose overlay (lines 63-82)
5. Updates Caddyfile with `/api-rev-{commit}/*` route (lines 88-109)
6. Builds and starts containers (lines 115-134)
7. Prints report (lines 137-146)

**There is NO step that updates `/srv/dashboard-rev-latest`.** This confirms the root cause.

**Fix will work: YES**

The proposed fix adds a `3b` step that runs `cp -r /srv/dashboard-rev-${COMMIT}/* /srv/dashboard-rev-latest/` when `BRANCH == "staging"`. This is correct and sufficient.

**Are there other deploy scripts that need updating?**

- `deploy-frontend.sh`: Deploys to `/home/ec2-user/n8n-docker-caddy/frontend` on the production VPS. Not related to staging.
- `deploy-dashboard.sh`: Deploys to `/home/ec2-user/n8n-docker-caddy/dashboard` on the production VPS. Not related to staging.
- `deploy-api.sh`: Deploys the API container only on production VPS. Not related to staging.

Only `deploy-revision.sh` is used for staging. No other scripts need the fix.

**Edge cases:**

1. **First-ever staging deploy**: If `/srv/dashboard-rev-latest` doesn't exist yet, the `sudo mkdir -p` and `sudo chown` handle this. OK.
2. **Concurrent deploys**: If two agents deploy simultaneously, the `cp -r` is not atomic. One deploy could overwrite the other's `latest`. This is unlikely in practice and the fix would survive it (last writer wins, both are valid builds). Acceptable risk.
3. **Disk space**: Each deploy creates a new `/srv/dashboard-rev-{commit}` directory (~3-5 MB). Over time, old revisions accumulate. The `teardown-revision.sh` script handles cleanup, but the spec doesn't mention running it as part of the deploy lifecycle. Minor concern.
4. **Branch detection**: `git branch --show-current` returns the branch name. If the deploy is run from a detached HEAD (e.g., CI), `BRANCH` would be empty and the `if [ "$BRANCH" = "staging" ]` check would skip the latest update. This is correct behavior (CI should explicitly handle this).

**Verification step analysis:**

The proposed step 8 (verification) is a good addition but the JS bundle content check (`curl | grep -q "EntrySignpost"`) is brittle:
- Vite may minify/mangle component names in production builds. `EntrySignpost` might become `$e` or similar.
- Better to check for a specific string that survives minification, like a unique CSS class name or a data-testid attribute.

However, the primary check (JS bundle filename match) is robust and sufficient for catching the deployment gap.

**Breaking changes:** None.

**E2E test adequate: YES**

The E2E test in Item 4 (baseline-workflow.spec.ts) effectively tests the deployment outcome. The Phase 2 "Coming soon" check and localStorage persistence check directly verify that Sprint 5 code is deployed.

**Score projection realistic: YES**

This is the single highest-impact fix. Deploying the frontend fixes 5 of 8 issues with zero code changes. The score projections for the deployment-gated items (A1, A3, A4, A5, B3) are all realistic because they're not predicting behavior change -- they're predicting that already-working code will finally be served.

**Verdict: PASS**

The fix is correct, complete, and the score projection is honest.

---

### Item 4: E2E Verification Framework

**Root cause verified: YES (systemic, not a code bug)**

Sprint 5 failed because the deployment pipeline had no verification step. The CI tested code correctness but not deployment correctness. This is a process gap, not a code gap.

**Fix will work: YES**

The Playwright test suite covers:
1. Deployment verification (Sprint 5 components present)
2. Namespace persistence (localStorage)
3. Playbook page loads
4. Import page loads
5. Import API format (forward: Claude -> frontend)
6. Import preview API (reverse: frontend -> Claude)
7. Enrich page namespace tags
8. Enrich page namespace dropdown

This covers the 5 deployment-gated issues and 2 code bugs, which is comprehensive.

**Concerns:**

1. **Auth setup**: The `login()` function calls the API directly and injects tokens into localStorage. This works but bypasses the actual login UI flow. For deployment verification, this is acceptable (the login page is not what we're testing).

2. **Test fixture dependency**: The import tests upload CSV content inline (via `Buffer.from(csvContent)`), which is self-contained. No external fixture files needed. Good.

3. **Timing**: The web_search test (from Item 2) has a 60-second timeout. For a verification suite that should run in under 30 seconds, this is too slow. However, the Item 2 E2E test is listed separately, not in baseline-workflow.spec.ts. The baseline-workflow tests themselves should be fast.

4. **Flakiness risk**: `page.waitForLoadState('networkidle')` is known to be flaky in Playwright. If the page makes periodic API calls (e.g., polling), `networkidle` may never resolve. Better to wait for specific elements.

5. **The test checks `text=Coming soon` to be NOT visible**: This is a negative assertion on a deployment-gated component. If the page hasn't loaded yet, the assertion passes vacuously (nothing is visible). The test should ALSO assert that the expected component IS visible (e.g., check for ContactsPhasePanel content).

**Are the E2E tests runnable against staging?**

Yes -- the `BASE_URL` defaults to `https://leadgen-staging.visionvolve.com`, the auth credentials are the staging test user. No additional setup needed.

**Breaking changes:** None -- this is a new test file.

**Score projection: N/A** (this item doesn't affect baseline scores directly)

**Verdict: PASS**

The framework is sound. Minor improvements suggested (replace `networkidle` with element waits, add positive assertions alongside negative ones) but not blocking.

---

## What's Missing for 9/10

The spec claims a tested-steps average of 8.75 on completeness and 7.0 on seamlessness. Here's what would actually be needed for a true 9/10:

### Immediate gaps (not addressed by Sprint 5.1):

1. **Import field mapping table is wrong** (detailed above in Item 1). Without fixing the company field mapping, Step 3 (Import) will still have partial failures. This drags availability down to 7-8 instead of 9.

2. **No programmatic enforcement of web_search** (Item 2). The AI may still skip web_search in some turns. ai_quality stays at 7-8 not 9.

3. **Enrichment is untestable** (Steps 5-10). These 6 steps carry scores of 2-5 across seamlessness and proactiveness. They represent 60% of the workflow but are blocked by enrichment credits. **The aggregate score is mathematically capped at ~5-6 until enrichment works.**

4. **No error recovery in import flow**. If the CSV has encoding issues, the user gets a generic error. No retry or partial import.

5. **Chat input discovery**. The E2E tests use multiple fallback selectors (`[data-testid="chat-input"], textarea[placeholder*="message"]`). If none match, the test fails silently. The chat input should have a stable `data-testid`.

### To actually reach 9/10 on tested steps (1-4):

| Gap | Impact | Fix |
|-----|--------|-----|
| Correct company field mapping table | Step 3 avail +1 | Explicit CLAUDE_TO_FRONTEND dict |
| Programmatic web_search enforcement | Step 2 ai_quality +1 | Agent executor check |
| Positive assertions in E2E (assert component IS visible, not just negative) | Test reliability | Replace negative-only checks |
| Error boundary for import failures | Step 3 seamlessness +1 | Try/catch with user-friendly message |

---

## Revised Score Projection

I disagree with the spec's tested-steps projection on two items:

### Item 1 (Import): Spec says availability=9, seamlessness=7

With the broken company field mapping:
- **availability: 7** (import works for contact fields but company fields silently default to "-- Skip --")
- **seamlessness: 5** (user has to manually fix 4-5 company field dropdowns)

After fixing the mapping table:
- **availability: 9** (agree with spec)
- **seamlessness: 7** (agree with spec)

### Item 2 (Web Search): Spec says ai_quality=9

Without programmatic enforcement:
- **ai_quality: 8** (web_search called ~85% of the time, not 100%)

With programmatic enforcement:
- **ai_quality: 9** (agree with spec)

### Revised tested-steps average (Steps 1-4)

**If Item 1 mapping table is fixed:**

| Dimension | Spec projection | My projection | Delta |
|-----------|----------------|---------------|-------|
| Completeness | 8.75 | 8.5 | -0.25 |
| Seamlessness | 7.00 | 6.75 | -0.25 |
| AI Quality | 8.33 | 8.0 | -0.33 |
| User Effort | 8.75 | 8.5 | -0.25 |
| Proactiveness | 6.25 | 6.0 | -0.25 |

**If Item 1 mapping table is NOT fixed:**

| Dimension | Spec projection | My projection | Delta |
|-----------|----------------|---------------|-------|
| Completeness | 8.75 | 7.75 | -1.0 |
| Seamlessness | 7.00 | 5.75 | -1.25 |
| AI Quality | 8.33 | 8.0 | -0.33 |
| User Effort | 8.75 | 7.5 | -1.25 |
| Proactiveness | 6.25 | 5.5 | -0.75 |

The mapping table bug is a significant risk to the score projection.

---

## Summary of Required Revisions

### Item 1 (CRITICAL): Replace the simple prefix-stripping rule with an explicit mapping table

The spec's `company.X -> company_X` rule fails for `domain`, `industry`, `hq_city`, `company_size`, and `business_model`. Also needs to handle `email_address -> email` and `phone_number -> phone`.

Required: An explicit `CLAUDE_TO_FRONTEND` mapping dict in `import_routes.py` and its reverse `FRONTEND_TO_CLAUDE` for `_frontend_to_claude_mapping()`.

### Item 2 (RECOMMENDED): Add programmatic enforcement or adjust score

Either:
- Add a logging/warning mechanism in `agent_executor.py` when `update_strategy_section` is called without prior `web_search`, OR
- Lower the ai_quality projection from 9 to 8

### Items 3 and 4: No revisions needed.

---

## Steps 5-10 Scope Expansion Analysis

The scope has been updated: we CAN and SHOULD run real enrichment on a small batch (2-3 companies, 3-5 contacts). This makes Steps 5-10 testable. I reviewed the enrichment pipeline code, campaign routes, and message generation to assess the projections.

### Code Verification

**Enrichment pipeline** (`api/services/pipeline_engine.py`):
- L1, L2, person, triage are all `DIRECT_STAGES` (Python, not n8n). Confirmed at line 30.
- `_process_entity()` dispatches correctly: l1 -> `enrich_l1()`, l2 -> `enrich_l2()`, person -> `enrich_person()`, triage -> `_process_triage()`. Confirmed at lines 480-495.
- L1 uses Perplexity sonar API (`api/services/l1_enricher.py`). Perplexity API key confirmed available on staging.
- Triage uses rules-based evaluation (`api/services/triage_evaluator.py`). Zero-cost, no external API. DEFAULT_RULES are conservative (lets most through).

**Campaign auto-setup** (`api/routes/campaign_routes.py:2858`):
- Endpoint exists: `POST /api/campaigns/auto-setup`
- Pre-populates from triage-passed contacts, names campaign from strategy, assigns channels based on contact info.
- Requires `@require_role("editor")` -- test user `test@staging.local` is super_admin, so this works.

**Message generation** (`api/services/message_generator.py`):
- Uses Claude Haiku (`claude-haiku-3-5-20241022`), which is correct for cost-efficient generation.
- `start_generation()` runs in background thread. Progress tracking exists.
- Cost estimate: EST_INPUT_TOKENS=800, EST_OUTPUT_TOKENS=200 per message.

**Send/queue** (`api/routes/campaign_routes.py:2109, 2227`):
- `send-emails` endpoint exists (Resend integration).
- `queue-linkedin` endpoint exists (Chrome extension integration).
- Both correctly gated by status transitions (campaign must be "approved").

### Per-Step Score Assessment

**Step 5: Qualification & Triage (projected: avail=8, seam=6, proact=5, effort=9)**

Concerns:
- The spec says "Triage stage auto-chains after L1". I checked `dag_executor.py` and `pipeline_engine.py` -- triage is NOT auto-chained after L1. The `start_pipeline_threads()` function runs stages independently based on what the user selects. The user must explicitly select triage as a stage OR the pipeline must be configured to run L1+triage in sequence.
- **If the user runs L1 only**, they must then manually trigger triage. This is a seamlessness issue the spec glosses over.
- The spec says "WorkflowSuggestions deployed; AI suggests running triage after L1" -- but WorkflowSuggestions is a frontend component (`frontend/src/components/chat/WorkflowSuggestions.tsx`) that shows proactive suggestions in the chat panel. It's deployed by Item 3 (frontend deploy). However, the suggestions are based on workflow state, and I need to verify the `useWorkflowSuggestions.ts` hook actually detects "L1 done, triage needed" state.

**Step 6: Deep Enrichment L2 + Person (projected: avail=8, seam=6, proact=5, ai_quality=7, effort=9)**

Mostly realistic. L2 and person enrichment are well-tested Python modules. The ai_quality=7 for L2 is conservative and honest (Perplexity sonar output quality varies by company).

One concern: The spec says to run L2 + person on "2-3 triage-passed companies". But person enrichment runs on CONTACTS, not companies. The contact count depends on how many contacts were imported per company. If we imported 10 contacts across 8 companies, and 2-3 companies pass triage, we might have 3-5 eligible contacts. This matches the spec's cost estimate.

**Step 7: Campaign Creation (projected: avail=8, seam=6, proact=5, effort=9)**

Realistic. The auto-setup endpoint exists and is tested. One edge case: `_build_strategy_generation_config()` at line 55 extracts tone, messaging angles, etc. from the strategy document. If the strategy was generated without web_search (Item 2 issue), the generation_config may be generic. This cascades to Step 9 (message quality).

**Step 8: Message Generation (projected: avail=8, seam=6, proact=5, ai_quality=8, effort=9)**

Mostly realistic. Claude Haiku generates messages using L2 enrichment data. The ai_quality=8 is reasonable IF L2 enrichment produced good data for the test companies. For unitedarts.cz, which has a real website with content, this should work well.

**Cost concern**: The spec estimates ~10 credits for 3 contacts x 2 steps. At Haiku pricing (~$0.001/message), this is about $0.006 or 6 credits. The 10 credit estimate has margin. OK.

**Step 9: Message Review (projected: avail=8, seam=6, proact=4, ai_quality=8, effort=8)**

Realistic. The review UI exists in campaign detail page. Messages show contact context. user_effort=8 is honest (1 action per message, multiple messages).

**Step 10: Campaign Launch (projected: avail=8, seam=6, proact=4, effort=9)**

Realistic -- we don't actually send, just verify UI. The send summary, conflict check, and send button are all implemented.

### Aggregate Score Verification

The spec computes:
- Completeness: (9+8+9+9+8+8+8+8+8+8) = 83/10 = **8.3** -- AGREE
- Seamlessness: (8+7+7+6+6+6+6+6+6+6) = 64/10 = **6.4** -- SLIGHTLY OPTIMISTIC
- AI Quality: (9+7+9+7+8+8) = 48/6 = **8.0** -- AGREE (if web_search works)
- User Effort: (9+8+9+9+9+9+9+9+8+9) = 88/10 = **8.8** -- AGREE
- Proactiveness: (8+7+5+5+5+5+5+5+4+4) = 53/10 = **5.3** -- SLIGHTLY OPTIMISTIC

**My revised aggregate (accounting for triage not auto-chaining):**

Step 5 seamlessness should be 5 not 6 (user must manually trigger triage after L1). Step 6 seamlessness stays at 6 (L2+person can be selected together). This changes the seamlessness mean from 6.4 to 6.3 -- a trivial difference.

The bigger concern is proactiveness. The spec gives Steps 5-7 proactiveness=5, based on "WorkflowSuggestions deployed; AI suggests next steps." But WorkflowSuggestions shows in the CHAT panel, not on the ENRICH page. The user on the enrich page doesn't see chat suggestions unless they open the chat panel. If they're focused on the DAG UI, proactiveness at the enrich step is closer to 3 (system waits passively). This would drop proactiveness from 5.3 to ~4.5.

### Cost Budget Assessment

The spec's cost estimate:
- L1: 2-3 companies x ~$0.02 = ~$0.06 (60 credits) -- VERIFIED against `STATIC_COST_DEFAULTS["l1"] = 0.02`
- Triage: zero cost -- VERIFIED (rules-based, no API calls)
- L2: 2-3 companies x ~$0.08 = ~$0.24 (240 credits) -- VERIFIED against `STATIC_COST_DEFAULTS["l2"] = 0.08`
- Person: 3-5 contacts x ~$0.04 = ~$0.20 (200 credits) -- CORRECTED: spec says $0.05 but `STATIC_COST_DEFAULTS["person"] = 0.04`
- Message generation: 3-5 contacts x 2 steps x ~$0.001 = ~$0.01 (10 credits) -- VERIFIED
- **Total**: ~$0.51 (510 credits) -- under $1 cap. SAFE.

The spec says $0.56 / 560 credits. My calculation shows $0.51 / 510 credits because person enrichment is $0.04 not $0.05. Minor discrepancy, still well under budget.

### E2E Tests for Steps 5-10

The updated spec includes:
1. L1 enrichment API test (run on small batch) -- exists in baseline-workflow.spec.ts
2. Campaign creation API test -- exists
3. Campaigns page UI test -- exists
4. Messages page UI test -- exists

**Missing E2E coverage:**
1. **No triage test** -- after L1, verify companies got `triage_passed` status
2. **No L2 test** -- verify L2 enrichment actually ran and produced data
3. **No message generation test** -- verify messages were generated with real content
4. **No message review test** -- verify approve/reject actions work

These are significant gaps. The E2E suite tests that pages LOAD but not that the enrichment workflow EXECUTES correctly end-to-end. The spec should add API-level tests that:
1. Run L1 on 2 companies -> verify status changed
2. Run triage -> verify passed/failed classification
3. Create campaign -> verify contacts assigned
4. Generate messages -> verify messages created with non-empty body
5. Approve messages -> verify status transition

### Steps 5-10 Verdict

**Score projections: MOSTLY REALISTIC with minor adjustments needed:**

| What | Spec says | I say | Why |
|------|-----------|-------|-----|
| Step 5 seamlessness | 6 | 5 | Triage doesn't auto-chain after L1 |
| Steps 5-7 proactiveness | 5 | 3-4 | WorkflowSuggestions only visible in chat panel, not enrich page |
| Step 8 ai_quality | 8 | 7-8 | Depends on L2 enrichment quality for specific test companies |
| Aggregate seamlessness | 6.4 | 6.1 | -0.3 from triage chaining |
| Aggregate proactiveness | 5.3 | 4.5 | -0.8 from WorkflowSuggestions visibility |

**Required revisions for Steps 5-10:**

1. **E2E gaps**: Add API-level tests for the enrichment workflow (L1 -> triage -> L2 -> campaign -> messages). Page load tests are insufficient.
2. **Triage chaining**: Either acknowledge that triage requires manual trigger (and adjust seamlessness score), OR add triage to the default stage selection when L1 is selected (small code change in enrich_routes.py).
3. **Cost estimate correction**: Person enrichment is $0.04/entity, not $0.05. Total is ~510 credits, not 560. Minor.

---

## Updated Summary of Required Revisions

### Item 1 (CRITICAL): Replace the simple prefix-stripping rule with an explicit mapping table

The spec's `company.X -> company_X` rule fails for `domain`, `industry`, `hq_city`, `company_size`, and `business_model`. Also needs to handle `email_address -> email` and `phone_number -> phone`.

Required: An explicit `CLAUDE_TO_FRONTEND` mapping dict in `import_routes.py` and its reverse `FRONTEND_TO_CLAUDE` for `_frontend_to_claude_mapping()`.

### Item 2 (RECOMMENDED): Add programmatic enforcement or adjust score

Either:
- Add a logging/warning mechanism in `agent_executor.py` when `update_strategy_section` is called without prior `web_search`, OR
- Lower the ai_quality projection from 9 to 8

### Items 3 and 4: No revisions needed.

### Steps 5-10 (RECOMMENDED): Strengthen E2E coverage and adjust proactiveness scores

1. Add API-level E2E tests that verify the enrichment workflow executes correctly (not just that pages load)
2. Adjust proactiveness scores for Steps 5-7 from 5 to 3-4 (WorkflowSuggestions only visible in chat panel)
3. Acknowledge triage doesn't auto-chain; adjust Step 5 seamlessness from 6 to 5
4. Total impact on aggregates: seamlessness 6.4 -> 6.1, proactiveness 5.3 -> 4.5
