# Sprint 10: Enrichment Excellence — Specifications

## Phase 1: Bug Fixes

---

### BL-227: Company Profile field quality enum migration

**Problem:** Migration `migrations/026_field_quality_enums.sql` exists but hasn't been applied to the staging database. It adds new enum values (`small`, `medium` for `company_size`; `product_company`, `service_company`, `hybrid` for `business_type`; several new `industry_enum` values), migrates legacy values (`startup`->`small`, `smb`->`medium`, `service_provider`->`service_company`), and backfills `industry_category` from `industry`.

**Fix:** Run the migration on the staging database:
```bash
# SSH to staging VPS and run against staging DB
psql $DATABASE_URL < migrations/026_field_quality_enums.sql
```
No code changes needed — the migration SQL is already written and correct.

**Acceptance Criteria:**
- Given the staging DB, When migration 026 is applied, Then `company_size` enum accepts `small` and `medium` values
- Given companies with `company_size='startup'`, When the migration runs, Then their value is updated to `small`
- Given companies with `industry='software_saas'` and null `industry_category`, When the migration runs, Then `industry_category` is set to `technology`

**Test Plan:**
- Run migration on staging DB
- Verify with: `SELECT DISTINCT company_size FROM companies WHERE company_size IN ('small','medium')` returns rows
- Verify no companies have `company_size='startup'` or `company_size='smb'`
- Verify `industry_category` is populated for companies with known industries

---

### BL-228: Triage estimate rejected

**Problem:** The `/api/enrich/estimate` endpoint validates stages against `ENRICHMENT_STAGES` list in `api/routes/enrich_routes.py` (line 21-33). The list already includes `"triage"` at position 2. However, the frontend may be sending a legacy alias that doesn't map to `"triage"`. Check that `_LEGACY_STAGE_ALIASES` in `pipeline_engine.py` (line 46-52) covers any old name the frontend might use. The current aliases only map registry-related names (`ares`, `brreg`, `prh`, `recherche`, `isir` -> `registry`). If the frontend sends `"auto_triage"` or similar, it would fail validation.

**Fix:** Investigate the actual frontend request that's failing. The `ENRICHMENT_STAGES` list already contains `"triage"`. The issue is likely that:
1. The estimate endpoint resolves aliases (line 132) before validating, which is correct
2. The frontend stage selector might not include `"triage"` in its options, OR
3. The error occurs in a different endpoint or with a different payload format

Files to check:
- `frontend/src/pages/enrich/EnrichPage.tsx` — what stage names does the frontend send?
- `api/routes/enrich_routes.py:132-138` — alias resolution + validation

**Acceptance Criteria:**
- Given a POST to `/api/enrich/estimate` with `stages: ["triage"]`, When the request is processed, Then it returns 200 with cost estimate (not 400 "Invalid stages")
- Given a POST with `stages: ["l1", "triage", "l2"]`, When processed, Then all three stages return valid estimates

**Test Plan:**
- `curl -X POST /api/enrich/estimate -d '{"tag_name":"batch-2","stages":["triage"]}' -H 'Authorization: Bearer ...'`
- Verify 200 response with `triage` stage showing `eligible_count` and `cost_per_item: 0.00`
- Unit test: call estimate endpoint with `stages=["triage"]` and verify no validation error

---

### BL-229: QC dispatch broken

**Problem:** In `api/services/pipeline_engine.py`, the `DIRECT_STAGES` set (line 30-42) already includes `"qc"`, and the `_process_entity` dispatch function (line 514-550) already has a handler for `stage == "qc"` at line 538-541 that calls `from .qc_checker import run_qc`. So the dispatch is NOT broken for QC.

However, the `STAGE_PREDECESSORS` dict (line 55-60) does NOT include `"qc"`, which means the reactive pipeline (`run_stage_reactive`) can't properly chain QC after other stages. QC has no predecessor mapping, so when running in reactive mode, the pipeline won't know when QC's predecessors are done.

**Fix:** Add QC to `STAGE_PREDECESSORS` in `api/services/pipeline_engine.py`:
```python
STAGE_PREDECESSORS = {
    "l1": [],
    "l2": ["l1"],
    "person": ["l2"],
    "registry": [],
    "qc": ["l2", "person"],  # ADD THIS — QC runs after L2 and person complete
}
```
Also add `ELIGIBILITY_QUERIES["qc"]` if missing (it exists at line 148-155, so this is already covered).

**Acceptance Criteria:**
- Given a pipeline run with stages `["l1", "l2", "person", "qc"]`, When QC stage starts in reactive mode, Then it waits for L2 and person to complete before processing
- Given the `_process_entity` function called with `stage="qc"`, When executed, Then it calls `run_qc()` without error

**Test Plan:**
- Unit test: verify `STAGE_PREDECESSORS["qc"]` contains expected dependencies
- Integration: start a pipeline with QC stage and verify it runs after predecessors complete
- Unit test: `_process_entity("qc", company_id, tenant_id)` calls `run_qc`

---

### BL-230: Registry dag-run 0 items

**Problem:** In `api/services/stage_registry.py` (line 39-62), the registry stage definition has `"hard_deps": []` (no dependencies), which is correct — registry is independent and should not depend on L1. The `STAGE_PREDECESSORS` in `pipeline_engine.py` also shows `"registry": []` (line 59), which is correct.

The "0 items" issue is likely in the eligibility query. The `ELIGIBILITY_QUERIES["registry"]` (line 97-115) requires:
1. No existing `company_legal_profile` row (`LEFT JOIN ... WHERE clp.company_id IS NULL`)
2. Country match (`hq_country IN (...)` or domain TLD match or `ico IS NOT NULL`)

If all companies already have legal profiles, or none match the country/TLD gate, the query returns 0 items.

**Fix:** Investigate why 0 items are returned. Likely causes:
1. All companies already have `company_legal_profile` rows (no re-enrichment path)
2. No companies match the country/domain filter

Add a `re_enrich` path: if re-enrich is enabled for registry, skip the `clp.company_id IS NULL` check. This requires updating `dag_executor.py`'s `count_eligible_for_estimate()` to handle registry's re-enrich case.

**Acceptance Criteria:**
- Given companies with `hq_country='CZ'` and no existing `company_legal_profile`, When registry stage is estimated, Then `eligible_count > 0`
- Given companies with existing `company_legal_profile` and re-enrich enabled, When registry stage is estimated, Then eligible companies include those with stale profiles

**Test Plan:**
- Query staging DB: `SELECT COUNT(*) FROM companies c LEFT JOIN company_legal_profile clp ON clp.company_id = c.id WHERE clp.company_id IS NULL AND c.hq_country IN ('CZ','NO','FI','FR')`
- If 0, the fix is to add re-enrich support
- If >0, the bug is elsewhere (tag_id filter, owner_id filter)

---

### BL-215: Person seniority enum mismatch

**Problem:** The person enricher (`api/services/person_enricher.py`) detects seniority as display values like `"C-Level"`, `"VP"`, `"Director"`, `"Manager"`, `"Individual Contributor"` (line 608-613, 630-635). The `_SENIORITY_TO_DB` mapping (line 1084-1092) converts these to DB enum values: `c_level`, `vp`, `director`, `manager`, `individual_contributor`, `founder`, `other`.

The PostgreSQL enum `seniority_level` (defined in `migrations/001_initial_schema.sql:81-83`) has values: `c_level`, `vp`, `director`, `manager`, `individual_contributor`, `founder`, `other`.

The `_detect_seniority()` function returns `"C-Level"` for CEO/CFO/CTO/etc patterns (line 609). The `_SENIORITY_TO_DB` map converts `"C-Level"` -> `"c_level"`. This mapping is correct.

The actual bug: when Perplexity's response contains a seniority value in its JSON output (e.g., `"C-Level"` as raw text), and the enricher uses that value INSTEAD of the `_detect_seniority()` function result, the raw `"C-Level"` string gets written to the DB, which fails the PostgreSQL enum constraint.

**Fix:** The `_update_contact()` function (line 1115-1167) already maps through `_SENIORITY_TO_DB`. But the fallback at line 1130 does `scores["seniority"].lower().replace(" ", "_")` which converts `"C-Level"` to `"c-level"` (with hyphen, not underscore). This produces an invalid enum value.

Change line 1129-1131 in `api/services/person_enricher.py`:
```python
seniority_db = _SENIORITY_TO_DB.get(
    scores["seniority"], "other"  # fallback to "other" instead of string manipulation
)
```

**Acceptance Criteria:**
- Given a contact with title "CEO" that Perplexity classifies as "C-Level", When person enrichment runs, Then `seniority_level` is saved as `c_level` (valid enum)
- Given an unrecognized seniority value from Perplexity, When the fallback is used, Then `seniority_level` is saved as `other` (valid enum) instead of crashing

**Test Plan:**
- Unit test: call `_update_contact()` with `scores["seniority"] = "C-Level"` and verify DB gets `c_level`
- Unit test: call with `scores["seniority"] = "Senior Executive"` (unmapped) and verify DB gets `other`
- Verify no `DataError` / `InvalidTextRepresentation` on staging after enriching contacts with C-level titles

---

### BL-216: Anomaly detection 500

**Problem:** The `/api/enrich/anomalies` endpoint (`api/routes/enrich_routes.py:498-517`) calls `detect_anomalies()` from `api/services/anomaly_detector.py`. The detector runs 5 checks, each with basic null handling. However, several potential null crashes exist:

1. `_check_cost_outliers` (line 126-128): `row[2]` null check exists but `row[1]` (company name) could be None — handled with `or "Unknown"` at line 137
2. `_check_stale_enrichment` (line 286-300): `row[0]` and `row[2]` null checks exist
3. `_check_missing_critical_fields` (line 230): CAST to TEXT on enum columns could fail if the column has an unexpected type

The most likely crash: `_check_high_failure_rates` (line 168-194) accesses `row[2]` and `row[4]` which are `total` and `failed` columns. If these are `NULL` in the DB (as opposed to 0), the `int()` call at lines 174-175 handles this with `if row[N] is not None else 0`. But `row[0]` (stage name) being NULL would cause `stage in seen_stages` to work but `seen_stages.add(stage)` adds None, and the resulting alert has `"entity_name": None` which may cause downstream JSON serialization issues.

**Fix:** Add defensive null checks in `api/services/anomaly_detector.py`:
1. In `_check_high_failure_rates` (line 170): the `if not stage` check already handles null stage names — this is fine
2. The real crash is likely in `_check_missing_critical_fields` when `CAST({field} AS TEXT)` fails on non-text enum columns. Add `try/except` around each field check (already done at line 226-240)
3. Add a top-level `try/except` in `detect_anomalies()` to catch any unhandled errors and return partial results

Actually, the existing code already has comprehensive `try/except` blocks. The 500 error may be from a different issue: the route itself doesn't wrap the call in try/except. Add error handling in the route:

```python
@enrich_bp.route("/api/enrich/anomalies", methods=["GET"])
@require_auth
def enrich_anomalies():
    # ... existing tag resolution ...
    try:
        result = detect_anomalies(str(tenant_id), str(tag_id))
    except Exception as e:
        logger.exception("Anomaly detection failed")
        return jsonify({"error": "Anomaly detection failed", "detail": str(e)[:200]}), 500
    return jsonify(result)
```

**Acceptance Criteria:**
- Given a batch with some null enrichment fields, When `/api/enrich/anomalies?tag_name=batch-2` is called, Then it returns 200 with alerts (not 500)
- Given a batch with no enrichment data at all, When anomalies endpoint is called, Then it returns `{"total_alerts": 0, "alerts": []}`

**Test Plan:**
- Unit test: call `detect_anomalies()` with a tag that has companies with null fields
- Integration: `curl /api/enrich/anomalies?tag_name=batch-2` on staging, verify 200
- Unit test: mock DB to return None values in all positions and verify no crash

---

### BL-217: deriveStage.ts only handles 6/11 stages

**Problem:** `frontend/src/lib/deriveStage.ts` already handles ALL stages. The `STAGE_ORDER` array (line 19-33) includes all 13 stages: `l1`, `triage`, `signals`, `registry`, `news`, `l2`, `person`, `social`, `career`, `contact_details`, `generate`, `review`, `qc`. The `STAGE_CONFIG` record (line 35-49) has entries for all 13 stages with labels and colors.

This item appears to already be resolved. The code at lines 19-49 covers all stages including `signals`, `registry`, `news`, `social`, `career`, `contact_details`, and `qc`.

**Fix:** No code changes needed — verify that the deployed frontend on staging has the latest version of this file. If the staging build is stale, redeploy the frontend.

**Acceptance Criteria:**
- Given a company with `entity_stage_completions` containing `{stage: "signals", status: "completed"}`, When `deriveStage()` is called, Then it returns `{label: "Strategic Signals", color: "#a855f7"}`
- Given completions for all 11 enrichment stages, When deriveStage is called, Then the latest completed stage is correctly identified

**Test Plan:**
- Unit test: call `deriveStage()` with completions for each of the 11 stages individually and verify correct label/color
- Verify staging frontend shows correct stage labels for companies at various pipeline stages

---

### NEW-1: useWorkflowStatus missing enrich completion detection

**Problem:** `frontend/src/hooks/useWorkflowStatus.ts` derives workflow phase from `OnboardingStatus`. It uses `BACKEND_PHASE_MAP` (line 33-45) to map backend `workflow_phase` strings to GTM phases. The map includes `enrichment_done: 'messages'` and `enrichment_running: 'enrich'`. However, the hook only checks `has_strategy` and `contact_count` explicitly (lines 50-55). Enrichment completion is detected via the `workflow_phase` field from the backend, but the hook doesn't directly check if enrichment stage_runs are completed — it relies on the backend's `workflow_phase` being accurate.

The issue is that `workflow_phase` may not update promptly when enrichment completes (it's computed on the backend from various signals). If the backend doesn't set `workflow_phase` to `enrichment_done`, the hook won't detect enrichment completion.

**Fix:** Add explicit enrichment completion check in `deriveWorkflowStatus()`:
```typescript
// Check enrichment completion from pipeline data
if (status.has_completed_enrichment || backendPhase === 'enrichment_done') {
  if (!completed.includes('enrich')) {
    completed.push('enrich')
  }
}
```
This requires the backend's `/tenants/onboarding-status` endpoint to include an `has_completed_enrichment` flag, OR the frontend to query pipeline_runs status separately.

**Acceptance Criteria:**
- Given a tenant whose pipeline has completed all stages, When `useWorkflowStatus()` is called, Then `completedPhases` includes `'enrich'`
- Given a tenant with running enrichment, When the hook fires, Then `currentPhase` is `'enrich'`

**Test Plan:**
- Unit test: mock `OnboardingStatus` with `workflow_phase: 'enrichment_done'` and verify `enrich` is in `completedPhases`
- Unit test: mock with `workflow_phase: 'enrichment_running'` and verify `currentPhase` is `'enrich'`
- Integration: complete an enrichment run on staging, verify the workflow status bar updates

---

### NEW-2: USD shown instead of credits

**Problem:** Multiple frontend components display costs as USD (`$X.XXXX`) instead of credits. The project rule is: "all cost displays show tokens/credits, never raw USD" (except super_admin LLM dashboard). Affected files:

1. `frontend/src/pages/enrich/CompletionPanel.tsx:19-23` — `fmtCost()` returns `$X.XX`
2. `frontend/src/components/ui/EnrichmentTimeline.tsx:58` — `${entry.cost.toFixed(4)}`
3. `frontend/src/pages/companies/ModuleSummaryCard.tsx:235` — `${cost.toFixed(4)}`
4. `frontend/src/pages/companies/CompanyDetail.tsx:519,547` — `Cost (USD)` labels and `.toFixed(4)` formatting
5. `frontend/src/pages/contacts/ContactDetail.tsx:425,493` — `enrichment_cost_usd?.toFixed(4)` raw display
6. `frontend/src/pages/campaigns/CampaignDetailPage.tsx:273` — `$${campaign.generation_cost.toFixed(2)}`
7. `frontend/src/components/campaign/GenerationProgressModal.tsx:172` — `${cost.toFixed(2)}`
8. `frontend/src/pages/messages/RegenerationDialog.tsx:132` — `~$${estimate.estimated_cost.toFixed(4)}`
9. `frontend/src/components/campaign/MessageReviewQueue.tsx:666` — `$${msg.generation_cost.toFixed(3)}`
10. `frontend/src/pages/campaigns/CampaignsPage.tsx:150` — `$${c.generation_cost.toFixed(2)}`
11. `frontend/src/components/ui/SourceTooltip.tsx:46` — `Cost: $${source.cost.toFixed(4)}`

Note: `StageCard.tsx:44-49` already has the correct format: `fmtCost()` converts USD to credits (`Math.ceil(v / 0.001)` credits).

**Fix:** Create a shared `formatCredits(usd: number): string` utility in `frontend/src/lib/format.ts`:
```typescript
export function formatCredits(usd: number): string {
  if (usd === 0) return 'free'
  const credits = Math.ceil(usd / 0.001)
  return `${credits.toLocaleString()} cr`
}
```
Replace all `$X.toFixed(N)` cost displays with `formatCredits(X)` across all affected components. Update labels from "Cost (USD)" to "Cost".

**Acceptance Criteria:**
- Given a company with `enrichment_cost_usd = 0.0234`, When displayed on CompanyDetail, Then it shows "24 cr" (not "$0.0234")
- Given a completed pipeline with `totalCost = 1.50`, When CompletionPanel renders, Then it shows "1,500 cr" (not "$1.50")
- Given an enrichment timeline entry with `cost = 0.004`, When rendered, Then it shows "4 cr"

**Test Plan:**
- Visual check: navigate to CompanyDetail, ContactDetail, CompletionPanel, EnrichmentTimeline on staging
- Verify no `$` symbol appears in any cost display (except super_admin dashboard if it exists)
- Unit test: `formatCredits(0)` returns `'free'`, `formatCredits(0.001)` returns `'1 cr'`, `formatCredits(1.5)` returns `'1,500 cr'`

---

### NEW-3: Stub dispatchers for 5 missing stages

**Problem:** In `api/services/pipeline_engine.py`, the `_process_entity()` dispatch function (line 542-544) already has stub dispatchers for the 5 unimplemented stages (`signals`, `news`, `social`, `career`, `contact_details`). They raise `NotImplementedError(f"Stage '{stage}' not yet implemented")`. This is already the correct behavior — it gives a clear error message instead of falling through to the n8n webhook path which would fail with "No webhook path".

**Fix:** This item is already implemented. The stubs at line 543-544 in `pipeline_engine.py` correctly raise `NotImplementedError` for all 5 stages. No code change needed.

**Acceptance Criteria:**
- Given `_process_entity("signals", company_id, tenant_id)`, When called, Then it raises `NotImplementedError("Stage 'signals' not yet implemented")`
- Given a pipeline run that includes `signals` stage, When an entity is processed, Then the error is caught by the stage runner and logged as a failure (not a crash)

**Test Plan:**
- Unit test: verify `_process_entity("signals", ...)` raises `NotImplementedError`
- Unit test: verify `_process_entity("news", ...)` raises `NotImplementedError`
- Verify that `run_stage()` catches the exception and increments `failed` count

---

## Phase 2: New Enricher Implementations

---

### BL-234: Strategic Signals Enricher

**Problem:** The `signals` stage is defined in `stage_registry.py` and has a DB model (`CompanyEnrichmentSignals` in `api/models.py:295-323`) with 17+ fields, but no enricher implementation exists. The `_process_entity()` dispatch currently raises `NotImplementedError`.

**Fix:** Create `api/services/signals_enricher.py` following the pattern of `l1_enricher.py`:

1. **Input**: company_id, tenant_id
2. **Research**: 1 Perplexity call (sonar model) asking about:
   - Digital transformation initiatives
   - AI/ML adoption signals and evidence
   - Hiring patterns (AI/data roles, tech departments)
   - Leadership changes
   - Tech partnerships and stack
   - Competitor AI moves
   - Growth indicators
   - Regulatory pressure
3. **Output**: Parse JSON response, write to `company_enrichment_signals` table (UPSERT on `company_id`)
4. **Fields to populate** (from `CompanyEnrichmentSignals` model):
   - `digital_initiatives`, `leadership_changes`, `hiring_signals`, `ai_hiring`
   - `tech_partnerships`, `competitor_ai_moves`, `ai_adoption_level`
   - `news_confidence`, `growth_indicators`, `job_posting_count`
   - `hiring_departments` (JSON), `workflow_ai_evidence`, `regulatory_pressure`
   - `employee_sentiment`, `tech_stack_categories`, `digital_maturity_score`, `it_spend_indicators`
5. **Update dispatch**: Replace `NotImplementedError` stub with import and call in `_process_entity()`
6. **Cost tracking**: Set `enrichment_cost_usd` from Perplexity token usage

**Acceptance Criteria:**
- Given a company with `status='triage_passed'`, When signals enrichment runs, Then `company_enrichment_signals` row is created with populated fields
- Given the enricher runs, When it completes, Then `enrichment_cost_usd` reflects actual Perplexity API cost
- Given invalid/empty Perplexity response, When parsing fails, Then enricher returns error dict without crashing

**Test Plan:**
- Unit test with mocked Perplexity client: verify correct prompt construction, response parsing, DB write
- Integration: run `_process_entity("signals", company_id, tenant_id)` on staging with a real company
- Verify `company_enrichment_signals` row exists after enrichment
- `make test-changed` passes

---

### BL-231: News & PR Enricher

**Problem:** The `news` stage is defined in `stage_registry.py` with fields pointing to `company_news` table (per STAGE_FIELDS). However, no `CompanyNews` model exists in `api/models.py` and no `company_news` table exists in migrations. The stage registry references `company_news` for fields like `media_mentions`, `press_releases`, `sentiment_score`, `thought_leadership`, `news_summary`.

**Fix:**
1. **Create migration** `migrations/0XX_company_news.sql`:
   ```sql
   CREATE TABLE IF NOT EXISTS company_news (
     company_id UUID PRIMARY KEY REFERENCES companies(id),
     media_mentions JSONB DEFAULT '[]'::jsonb,
     press_releases JSONB DEFAULT '[]'::jsonb,
     sentiment_score NUMERIC(5,2),
     thought_leadership TEXT,
     news_summary TEXT,
     enriched_at TIMESTAMPTZ,
     enrichment_cost_usd NUMERIC(10,4) DEFAULT 0,
     created_at TIMESTAMPTZ DEFAULT now(),
     updated_at TIMESTAMPTZ DEFAULT now()
   );
   ```
2. **Create model** `CompanyNews` in `api/models.py`
3. **Create enricher** `api/services/news_enricher.py`:
   - 1 Perplexity call (sonar model) for recent news, press releases, media sentiment
   - Optional Anthropic synthesis for news summary
   - Write to `company_news` table
4. **Update dispatch** in `_process_entity()`

**Acceptance Criteria:**
- Given a company with `status IN ('triage_passed', 'enriched_l2')`, When news enrichment runs, Then `company_news` row is created
- Given the enricher finds recent news, When it completes, Then `media_mentions` contains structured JSON with titles, dates, sources
- Given no news found, When enricher completes, Then row is created with empty arrays and null summary

**Test Plan:**
- Unit test with mocked Perplexity: verify prompt, response parsing, DB write
- Verify migration creates table successfully on clean DB
- `make test-changed` passes

---

### BL-232: Social & Online Enricher (contacts)

**Problem:** The `social` stage is defined for contacts with fields in `contact_enrichment` table: `twitter_handle`, `speaking_engagements`, `publications`, `github_username`, `linkedin_url`. These columns already exist on the `ContactEnrichment` model. No enricher implementation exists.

**Fix:** Create `api/services/social_enricher.py`:

1. **Input**: contact_id, tenant_id
2. **Research**: 1 Perplexity call (sonar model) asking about:
   - LinkedIn activity and profile URL
   - Twitter/X handle
   - GitHub username
   - Speaking engagements (conferences, webinars)
   - Publications (articles, blog posts, papers)
3. **Output**: Write to `contact_enrichment` table (UPSERT on `contact_id`)
4. **Fields to populate** (already on `ContactEnrichment` model):
   - `twitter_handle`, `speaking_engagements`, `publications`, `github_username`
   - Also update `linkedin_url` on `contacts` table if found
5. **Update dispatch** in `_process_entity()`

**Acceptance Criteria:**
- Given a contact whose company has `status='enriched_l2'`, When social enrichment runs, Then `contact_enrichment` row is updated with social fields
- Given a contact with a known LinkedIn profile, When enriched, Then `linkedin_url` on `contacts` table is populated
- Given Perplexity finds no social presence, When enricher completes, Then fields are set to null (not error)

**Test Plan:**
- Unit test with mocked Perplexity: verify correct prompt with contact name + company context
- Integration: run on staging with a real contact
- `make test-changed` passes

---

### BL-235: Career History Enricher (contacts)

**Problem:** The `career` stage is defined for contacts with fields in `contact_enrichment` table: `career_trajectory`, `previous_companies` (JSON). However, the model also references `industry_experience` (JSON) and `total_experience_years` (number) in STAGE_FIELDS but these columns do NOT exist on `ContactEnrichment` model.

**Fix:**
1. **Create migration** to add missing columns:
   ```sql
   ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS industry_experience JSONB DEFAULT '[]'::jsonb;
   ALTER TABLE contact_enrichment ADD COLUMN IF NOT EXISTS total_experience_years INTEGER;
   ```
2. **Update model** in `api/models.py` — add `industry_experience` and `total_experience_years` to `ContactEnrichment`
3. **Create enricher** `api/services/career_enricher.py`:
   - 1 Perplexity call (sonar model) for career history, previous companies, industry experience
   - Write to `contact_enrichment` table
4. **Fields to populate**:
   - `career_trajectory` (text summary)
   - `previous_companies` (JSON array: `[{name, role, duration, industry}]`)
   - `industry_experience` (JSON array: `[{industry, years}]`)
   - `total_experience_years` (integer)
5. **Update dispatch** in `_process_entity()`

**Acceptance Criteria:**
- Given a contact whose company has `status='enriched_l2'`, When career enrichment runs, Then `career_trajectory` and `previous_companies` are populated
- Given Perplexity finds career history, When parsed, Then `previous_companies` is a valid JSON array
- Given `total_experience_years` is computed, When saved, Then it's a positive integer

**Test Plan:**
- Unit test with mocked Perplexity: verify prompt, JSON parsing, DB write
- Verify migration adds columns without breaking existing data
- `make test-changed` passes

---

### BL-233: Contact Details Enricher

**Problem:** The `contact_details` stage is defined for contacts with fields: `email_address`, `phone_number`, `linkedin_url`, `profile_photo_url`. These columns already exist on the `contacts` table. No enricher implementation exists.

**Fix:** Create `api/services/contact_details_enricher.py`:

1. **Input**: contact_id, tenant_id
2. **Research**: 1 Perplexity call (sonar model) for:
   - Business email address
   - Phone number (direct/mobile)
   - LinkedIn profile URL (verification)
   - Profile photo URL
3. **Output**: Update `contacts` table directly (these are contact-level fields, not enrichment table fields)
4. **Important**: This is Perplexity-only. Email verification (bounce checking) is Sprint 11.
5. **Fields to update** on `contacts` table:
   - `email_address` (only if currently null — don't overwrite existing)
   - `phone_number` (only if currently null)
   - `linkedin_url` (update if found and higher confidence)
   - `profile_photo_url` (update if found)
6. **Update dispatch** in `_process_entity()`

**Acceptance Criteria:**
- Given a contact with null `email_address`, When contact_details enrichment runs, Then email is populated if Perplexity finds one
- Given a contact with existing `email_address`, When enrichment runs, Then existing email is NOT overwritten
- Given Perplexity can't find contact details, When enricher completes, Then no fields are nulled out (preserve existing data)

**Test Plan:**
- Unit test: verify null-guard logic (don't overwrite existing values)
- Unit test with mocked Perplexity: verify correct prompt construction
- Integration: run on staging with contacts that have missing emails
- `make test-changed` passes

---

### BL-236: Enrichment Test Suite with Scoring

**Problem:** No automated way to verify all enrichers work end-to-end and score their implementation completeness.

**Fix:** Create `tests/unit/test_enrichment_scoring.py` with a scoring rubric:

**Scoring rubric per stage** (10 points max):
| Check | Points | How |
|-------|--------|-----|
| Enricher file exists | 2 | `importlib.import_module(f"api.services.{stage}_enricher")` |
| Stage in `DIRECT_STAGES` | 1 | Check `pipeline_engine.DIRECT_STAGES` |
| Estimate API works | 2 | POST `/api/enrich/estimate` with the stage, verify no 400/500 |
| `_process_entity()` doesn't raise NotImplementedError | 3 | Call with mock entity, catch NotImplementedError |
| No unhandled exceptions | 2 | Run with mocked Perplexity/Anthropic, verify clean result dict |

**Stages to test**: `l1`, `l2`, `person`, `triage`, `registry`, `qc`, `signals`, `news`, `social`, `career`, `contact_details`

**Makefile target**: Add `test-enrichment` to Makefile:
```makefile
test-enrichment:
	python -m pytest tests/unit/test_enrichment_scoring.py -v --tb=short
```

**Acceptance Criteria:**
- Given all Phase 2 enrichers are implemented, When `make test-enrichment` runs, Then all stages score >= 8/10
- Given a stage with only stubs, When scored, Then it gets 1-3 points (file exists + in DIRECT_STAGES)
- Given the test suite, When run in CI, Then it produces a human-readable score table

**Test Plan:**
- Run `make test-enrichment` locally
- Verify score output shows per-stage breakdown
- Verify existing enrichers (l1, l2, person, registry, triage, qc) score 10/10
