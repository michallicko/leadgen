# Sprint 5 Debug Report

**Date**: 2026-03-03
**Debugger**: Claude Opus 4.6 (teammate agent)
**Staging commit**: `95234c2`
**Deployed frontend build**: `8c0f89a` (Sprint 4, Mar 1 20:44)
**Deployed backend**: Sprint 5 code (Mar 2 22:34)

---

## Systemic Finding: Frontend Not Deployed

**The deployed frontend build on staging (`dashboard-rev-latest`) is from Sprint 4 commit `8c0f89a` (Mar 1 20:44). Sprint 5 code was merged to the staging branch but the frontend was never rebuilt and deployed to `dashboard-rev-latest`.**

### Evidence

1. Caddy serves from `/srv/dashboard-rev-latest/` (configured in Caddyfile)
2. The `latest` directory contains `index-Bew8X9s9.js` (1.46 MB, built Mar 1 20:42)
3. This JS bundle contains **zero** Sprint 5 components:
   - `EntrySignpost`: NOT FOUND
   - `WorkflowSuggestions`: NOT FOUND
   - `CostEstimator`: NOT FOUND
   - `useOnboarding` (scoped): NOT FOUND
   - `ContactsPhasePanel` (updated): NOT FOUND
4. The build corresponds to commit `8c0f89a` (`feat(BL-052b): contact filter UI + campaign assignment modal`)
5. Even a newer build at `/srv/dashboard-rev-fa935a7/` (Mar 2 07:47) also lacks Sprint 5 components — it was built from `fa935a7` on the main branch, not staging
6. The **backend** IS running Sprint 5 code — `playbook_service.py` dated Mar 2 22:34 contains the "MANDATORY WEB RESEARCH" prompt

### Root Cause

The `deploy-revision.sh` script deploys to `/srv/dashboard-rev-{COMMIT}` but **does not update** `/srv/dashboard-rev-latest`. The `latest` directory was manually updated to the `8c0f89a` build before the later Sprint 4 PRs and all Sprint 5 PRs were merged. No subsequent deployment updated `latest`.

### Fix

Rebuild the frontend from the staging branch head (`95234c2`) and deploy to `dashboard-rev-latest`:

```bash
cd /Users/michal/git/leadgen-pipeline/frontend
npm run build
# SCP to staging
ssh -i "$KEY" ec2-user@3.124.110.199 "rm -rf /srv/dashboard-rev-latest/assets/*"
scp -r dist/* ec2-user@3.124.110.199:/srv/dashboard-rev-latest/
```

**This single action would fix A1, A3, A4, A5, and B3.**

---

## Per-Feature Diagnosis

### A1: BL-136 EntrySignpost Not Rendering

- **Committed code**: `frontend/src/components/onboarding/EntrySignpost.tsx` exists (created Sprint 4 PR #65, `db19489`). Sprint 5 fix `95ebd1f` updated `shouldShowSignpost()` in `useOnboarding.ts` to show signpost when namespace is truly empty (regardless of `onboarding_path`).
- **Deployed code**: NOT PRESENT. The deployed JS (`index-Bew8X9s9.js` from `8c0f89a`) predates both the component creation and the fix.
- **Match?**: No — deployed build is from before EntrySignpost was added to the codebase.
- **Root cause**: DEPLOYMENT — frontend build not updated after Sprint 4/5 merges.
- **Fix**: Deploy the current staging frontend build. No code changes needed.
- **Verification**: After deploy, navigate to an empty namespace. Should see the "Welcome to your workspace" signpost with 3 path cards.

---

### A2: BL-137 No Web Search in Strategy Generation

- **Committed code**: `api/services/playbook_service.py` lines 235-244 contain "MANDATORY WEB RESEARCH (non-negotiable)" prompt. `api/services/search_tools.py` registers `web_search` tool with Perplexity sonar API.
- **Deployed code**: YES — the backend container has the prompt (confirmed via `docker exec grep`). Perplexity API key IS configured (`pplx-HXAz0...`).
- **Match?**: Yes — backend code is deployed correctly.
- **Root cause**: PROMPT ENGINEERING — the AI receives the web_search tool and the "MANDATORY" instruction, but ignores it when updating an existing strategy. In baseline-002, the strategy already existed from baseline-001. The AI chose to be efficient: 1 `get_strategy_document` + 4 `update_strategy_section` = 5 tool calls. It never called `web_search` because:
  1. The "FIRST MESSAGE BEHAVIOR" clause only triggers on empty chat history (baseline-002 had prior history)
  2. The "SUBSEQUENT MESSAGES" clause says "If the user asks you to generate or draft strategy sections, ALWAYS call `web_search` first" — but the user asked to **update** existing sections, which the model interpreted differently
  3. The AI had specific business details in the user's message (reference clients, acts, service model) so it didn't feel the need for external research
- **Fix**: Two changes needed:
  1. **Prompt change**: Move the `web_search` requirement outside the "FIRST MESSAGE" block. Add explicit text: "Before ANY `update_strategy_section` call, you MUST have called `web_search` at least once in this turn. No exceptions."
  2. **Consider enforcement**: Add a check in `agent_executor.py` that warns/blocks `update_strategy_section` if `web_search` hasn't been called first in the same turn.
- **Verification**: Start a fresh chat in the strategy phase and ask the AI to update the strategy. It should call `web_search` before `update_strategy_section`.

---

### A3: BL-142 Cross-Namespace Tag Filter Leakage

- **Committed code**: `frontend/src/api/queries/useTags.ts` line 34: `queryKey: ['tags', namespace]` — scopes React Query cache by namespace (commit `349323e`).
- **Deployed code**: NOT PRESENT. Deployed JS is Sprint 4 `8c0f89a`, which has the old `queryKey: ['tags']` without namespace scoping.
- **Match?**: No — deployed build predates the fix.
- **Root cause**: DEPLOYMENT — frontend build not updated. The old code caches tags globally, so switching from visionvolve to unitedarts reuses the visionvolve tag cache. The backend API correctly filters by tenant_id via `X-Namespace` header, so a fresh fetch would return correct tags.
- **Fix**: Deploy the current staging frontend build. No code changes needed.
- **Verification**: After deploy, navigate to unitedarts, open enrich page, confirm tag dropdown only shows unitedarts tags.

---

### A4: BL-143/BL-114 Phase 2 Still "Coming Soon"

- **Committed code**: `frontend/src/components/playbook/PhasePanel.tsx` has a `case 'contacts'` branch (line 42) that renders `<ContactsPhasePanel>`. `ContactsPhasePanel.tsx` provides ICP pre-filter contact selection. Created in Sprint 4 PR #70 (`5eda623`), enhanced in Sprint 5 (`d7413ac` BL-126, `fdbdd9e` PD fixes).
- **Deployed code**: NOT PRESENT. The deployed build `8c0f89a` predates PR #70. The old `PhasePanel` renders `PhasePlaceholder` ("Coming soon") for all non-strategy phases.
- **Match?**: No — deployed build predates ContactsPhasePanel.
- **Root cause**: DEPLOYMENT — frontend build not updated.
- **Fix**: Deploy the current staging frontend build. No code changes needed.
- **Verification**: After deploy, click Phase 2 (Contacts) tab in Playbook. Should show contact selection panel with ICP filters, not "Coming soon".

---

### A5: BL-149 Namespace Not Persisting

- **Committed code**: `frontend/src/lib/auth.ts` lines 109-128: `LAST_NAMESPACE_KEY = 'leadgen_last_namespace'` with `getDefaultNamespace()` reading from localStorage and `setLastNamespace()` writing to it. `AppShell.tsx` line 56-60: `useEffect` calls `setLastNamespace(namespace)` on every namespace URL change. Commit `364b802`.
- **Deployed code**: NOT PRESENT. Deployed JS is Sprint 4 `8c0f89a`, which predates the localStorage persistence code.
- **Match?**: No — deployed build predates the fix.
- **Root cause**: DEPLOYMENT — frontend build not updated.
- **Fix**: Deploy the current staging frontend build. No code changes needed.
- **Verification**: After deploy, navigate to unitedarts namespace, close browser, reopen. Should redirect to `/unitedarts/` instead of `/visionvolve/admin`.

---

## Regression Root Causes

### B1: Import Preview 500 Error

- **Error traceback** (from `docker logs leadgen-api-rev-latest`):
  ```
  AttributeError: 'list' object has no attribute 'get'
  ```
  At `api/services/csv_mapper.py:288` in `apply_mapping()`:
  ```python
  mappings = {m["csv_header"]: m for m in mapping_result.get("mappings", [])}
  ```
- **Root cause**: TYPE MISMATCH between frontend format and backend expectation.
  1. Frontend `submitPreview()` sends `{ mapping: ColumnMapping[] }` — a flat array of `{source_column, target_field, ...}` objects (BL-134 format)
  2. Backend `preview_import()` line 406 reads `body.get("mapping")` and gets this flat array
  3. Backend passes it to `apply_mapping(row, mapping)` as the second arg
  4. `apply_mapping()` calls `mapping_result.get("mappings", [])` expecting a dict with `{"mappings": [...]}` (Claude's raw format)
  5. Since `mapping_result` is a list (the flat ColumnMapping array), `.get()` fails
- **Fix**: In `api/routes/import_routes.py`, the `preview_import()` function needs to either:
  - **(Option A)** Convert the flat `ColumnMapping[]` back to Claude format before calling `apply_mapping()`:
    ```python
    # Convert flat columns format to Claude mapping format
    if isinstance(mapping, list):
        mapping = {"mappings": [
            {"csv_header": m.get("source_column"), "target": m.get("target_field"),
             "confidence": m.get("confidence", "low")}
            for m in mapping
        ]}
    ```
  - **(Option B)** Make `apply_mapping()` handle both formats
- **File**: `api/routes/import_routes.py` lines 404-423
- **Verification**: Upload a CSV, map columns, click Preview. Should return preview rows without 500 error.

### B2: AI Column Mapping Not Applied to Dropdowns

- **Root cause**: VALUE FORMAT MISMATCH between API response and `<select>` options.
  1. Claude maps columns to targets like `contact.first_name`, `contact.email`, `company.name`
  2. `_build_upload_response()` passes these through as `target_field` values: `"contact.first_name"`, `"contact.last_name"`, etc.
  3. The frontend `<select>` options use simple names: `"first_name"`, `"last_name"`, `"email"`, `"company_name"` (from `TARGET_OPTIONS` array in `MappingStep.tsx` lines 23-40)
  4. Since `"contact.first_name"` !== `"first_name"`, the `<select>` can't match any option and shows the default empty value ("-- Skip --")
- **Fix**: In `_build_upload_response()`, strip the entity prefix from `target`:
  ```python
  # Line 116 in import_routes.py
  target = m.get("target") or None
  # Strip entity prefix (contact.first_name -> first_name, company.name -> company_name)
  if target and "." in target:
      entity, field = target.split(".", 1)
      if field.startswith("custom."):
          pass  # Keep custom.notes as-is for custom field matching
      elif entity == "company":
          target = f"company_{field}" if field != "name" else "company_name"
      else:
          target = field  # contact.first_name -> first_name
  ```
  Alternatively, update the frontend `TARGET_OPTIONS` to use the `entity.field` format. But stripping the prefix in the API is less disruptive.
- **File**: `api/routes/import_routes.py` lines 114-141 (`_build_upload_response`)
- **Verification**: Upload a CSV, verify dropdowns auto-select the correct target fields (First Name, Last Name, Email, etc.) instead of "-- Skip --".

### B3: Namespace Dropdown Regression on Enrich Page

- **Root cause**: DEPLOYMENT — same as A3/A5. The deployed Sprint 4 frontend has a hardcoded or cached namespace in the enrich page dropdown. The Sprint 5 code reads from the URL path, but it's not deployed.
- **Fix**: Deploy the current staging frontend build.
- **Verification**: After deploy, navigate to `/unitedarts/enrich`, confirm namespace dropdown shows "unitedarts".

---

## Summary

| Issue | Root Cause Category | Fix Complexity | Deployment Needed? | Code Change Needed? |
|-------|-------------------|----------------|-------------------|-------------------|
| A1: EntrySignpost | DEPLOYMENT | S | Yes | No |
| A2: No web_search | PROMPT ENGINEERING | M | Yes (backend redeploy) | Yes (`playbook_service.py`) |
| A3: Tag leakage | DEPLOYMENT | S | Yes | No |
| A4: Phase 2 coming soon | DEPLOYMENT | S | Yes | No |
| A5: Namespace persist | DEPLOYMENT | S | Yes | No |
| B1: Preview 500 | CODE BUG | M | Yes (backend redeploy) | Yes (`import_routes.py`) |
| B2: Dropdowns skip | CODE BUG | M | Yes (backend redeploy) | Yes (`import_routes.py`) |
| B3: Enrich namespace | DEPLOYMENT | S | Yes | No |

### Fix Priority

1. **Deploy frontend build from staging head** — fixes A1, A3, A4, A5, B3 (5 issues, zero code changes)
2. **Fix `_build_upload_response()` target field format** — fixes B2 (dropdown mapping)
3. **Fix `preview_import()` mapping format conversion** — fixes B1 (preview 500)
4. **Strengthen web_search prompt** — fixes A2 (needs testing to verify AI compliance)

### Critical Path

**Step 1**: Fix B1 + B2 in `import_routes.py` (backend code bugs)
**Step 2**: Rebuild frontend from staging head
**Step 3**: Deploy both backend (API container) and frontend (`dashboard-rev-latest`)
**Step 4**: Run baseline-003 to verify all fixes

### Import Fix Detail (B1 + B2 Combined)

Both B1 and B2 are in `api/routes/import_routes.py` and stem from the BL-134 response format change. The fix needs to:

1. In `_build_upload_response()`: Map `target` from Claude format to frontend format:
   - `contact.first_name` -> `first_name`
   - `contact.email` -> `email`
   - `company.name` -> `company_name`
   - `contact.custom.notes` -> keep as custom field path

2. In `preview_import()`: Convert the flat `ColumnMapping[]` from frontend back to Claude format before passing to `apply_mapping()`:
   - Map `source_column` back to `csv_header`
   - Map `target_field` back to `entity.field` format (reverse the above mapping)
   - Wrap in `{"mappings": [...]}` dict

### Deployment Fix Detail

The `deploy-revision.sh` script only deploys to `/srv/dashboard-rev-{commit}`. It does NOT update `/srv/dashboard-rev-latest`. For staging to always serve the latest build, add this to the deploy script (when on `staging` branch):

```bash
# After copying frontend build to /srv/dashboard-rev-${COMMIT}
if [ "$BRANCH" = "staging" ]; then
    ssh -i "$STAGING_KEY" "$STAGING_HOST" "rm -rf /srv/dashboard-rev-latest/assets/* && cp -r /srv/dashboard-rev-${COMMIT}/* /srv/dashboard-rev-latest/"
    echo "    Updated dashboard-rev-latest from ${COMMIT}"
fi
```

---

## Appendix: Deployed vs Expected

| Component | Expected Source | Deployed Source | Gap |
|-----------|---------------|----------------|-----|
| Frontend JS | `95234c2` (staging head) | `8c0f89a` (Sprint 4) | Sprint 5 + late Sprint 4 missing |
| Frontend CSS | `95234c2` | `8c0f89a` | Sprint 5 styles missing |
| API container | `95234c2` | `95234c2` (confirmed) | None - backend is current |
| Perplexity key | Set | Set (`pplx-HXAz0...`) | None |
| Anthropic key | Set | Set (used for chat) | None |

| Frontend Component | In Repo | In Deployed JS | Status |
|-------------------|---------|---------------|--------|
| EntrySignpost | Yes (Sprint 4 #65) | No | Not deployed |
| ContactsPhasePanel | Yes (Sprint 4 #70) | No | Not deployed |
| WorkflowSuggestions | Yes (Sprint 5) | No | Not deployed |
| CostEstimator | Yes (Sprint 5) | No | Not deployed |
| useOnboarding scoped | Yes (Sprint 5) | No | Not deployed |
| useTags scoped | Yes (Sprint 5) | No | Not deployed |
| Namespace localStorage | Yes (Sprint 5) | No | Not deployed |
| MappingStep | Yes (Sprint 4) | Partial (old version) | Old version deployed |
