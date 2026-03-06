# Sprint 8: Playbook Bug Fixes

**Date:** 2026-03-04
**Sprint type:** Bug-fix
**Items:** BL-188, BL-189, BL-190, BL-191, BL-192, BL-193, BL-194, BL-195, BL-196
**Tracks:** 5 (one independent, four with dependencies)

---

## Dependency Graph

```
Track 5 (BL-195 breadcrumbs)  ─── independent, do first
Track 2 (BL-188 + BL-196)     ─── independent of research
Track 4 (BL-193 doc fix)      ─── semi-independent, needs investigation
Track 1 (BL-189 + BL-190)     ─── foundation for Track 3
Track 3 (BL-191 + BL-192 + BL-194) ─── depends on Track 1 events
```

**Parallelism:** Tracks 5, 2, and 4 can start simultaneously. Track 1 starts
in parallel. Track 3 starts after Track 1 emits research events.

---

## Track 5: Remove Breadcrumbs (BL-195)

**Effort:** S (1 task)
**Goal:** Remove the `PhaseIndicator` stepper bar from `PlaybookPage`.

### Task 5.1: Delete PhaseIndicator usage from PlaybookPage

**Files:**
- `frontend/src/pages/playbook/PlaybookPage.tsx` (1140 lines)
- `frontend/src/components/playbook/PhaseIndicator.tsx` (81 lines)

**Steps:**

1. In `PlaybookPage.tsx`, remove the import on line 20:
   ```tsx
   // DELETE this line:
   import { PhaseIndicator, PHASE_ORDER, type PhaseKey } from '../../components/playbook/PhaseIndicator'
   ```

2. `PHASE_ORDER` is used on line 49 for `isValidPhase()` and `PhaseKey` is used
   for the `viewPhase` type on line 178. These are used for phase URL routing,
   which survives independently of the breadcrumb UI. Move the definitions
   inline into `PlaybookPage.tsx`:
   ```tsx
   type PhaseKey = 'strategy' | 'contacts' | 'messages' | 'campaign'
   const PHASE_ORDER: PhaseKey[] = ['strategy', 'contacts', 'messages', 'campaign']
   ```

3. Remove the `<PhaseIndicator>` JSX block at lines 853-858:
   ```tsx
   // DELETE this block:
   {/* Phase indicator */}
   <PhaseIndicator
     current={viewPhase}
     unlocked={docPhase}
     onNavigate={handlePhaseNavigate}
   />
   ```

4. Verify no other files import `PhaseIndicator`. Currently only
   `PlaybookPage.tsx` imports it (confirmed via grep). If nothing else uses it,
   delete `frontend/src/components/playbook/PhaseIndicator.tsx` entirely.

5. Verify the `handlePhaseNavigate` callback still works (used by `PhasePanel`
   at line 872 and by extraction confirm flow at line 431). It must remain.

**Validation:**
```bash
cd frontend && npx tsc --noEmit   # TypeScript compiles
make test-changed                  # No regressions
```
Visually confirm: the horizontal "Strategy > Contacts > Messages > Campaign"
stepper no longer appears above the split layout.

**Commit:** `fix(playbook): remove phase indicator breadcrumbs (BL-195)`

---

## Track 2: Onboarding UX Fixes (BL-188 + BL-196)

**Effort:** S + S (2 tasks)
**Goal:** Change onboarding to ask for GTM objective (not business description),
and show as inline box for new spaces instead of full-page takeover.

### Task 2.1: Change onboarding question to GTM objective (BL-188)

**Files:**
- `frontend/src/components/playbook/PlaybookOnboarding.tsx` (128 lines)

**Steps:**

1. Change the heading text (line 61):
   ```tsx
   // FROM:
   Generate Your GTM Strategy
   // TO:
   What's your GTM objective?
   ```

2. Change the description paragraph (lines 63-66):
   ```tsx
   // FROM:
   Describe your business and the AI will research your market and
   draft a complete strategy playbook.
   // TO:
   Tell us what you're trying to achieve and the AI will research
   your company and draft a tailored strategy.
   ```

3. Change the label (line 75):
   ```tsx
   // FROM:
   What does your business do?
   // TO:
   Describe your go-to-market objective
   ```

4. Change the placeholder (line 82):
   ```tsx
   // FROM:
   e.g., We sell marketing automation software to mid-market B2B SaaS companies in Europe...
   // TO:
   e.g., We want to break into the DACH enterprise market for our AI-powered compliance tool...
   ```

5. The `OnboardingPayload` type (line 19-23) sends `description` and
   `challenge_type: 'auto'`. The `description` field is repurposed to carry
   the GTM objective — the backend `trigger_research()` already accepts this
   as `data.get("objective")` (playbook_routes.py:1051). Verify the
   `handleOnboardGenerate` callback in `PlaybookPage.tsx` passes the
   description as `objective` in the research trigger call. If it does not,
   fix the mapping so that `description` from the form becomes `objective`
   in the POST body.

**Validation:**
```bash
cd frontend && npx tsc --noEmit
```
Visually: onboarding form asks about GTM objective, not business description.

**Commit:** `fix(playbook): change onboarding to ask GTM objective (BL-188)`

### Task 2.2: Inline onboarding box for new spaces (BL-196)

**Files:**
- `frontend/src/pages/playbook/PlaybookPage.tsx` (lines 648-672)
- `frontend/src/components/playbook/PlaybookOnboarding.tsx`

**Context:** Currently, when `needsOnboarding` is true (line 648), the
entire page returns `<PlaybookOnboarding>` as a full-page centered card,
blocking access to chat or editor. The fix: render onboarding as an
inline box at the top of the left panel, with the chat panel still visible.

**Steps:**

1. In `PlaybookPage.tsx`, remove the early return for onboarding (lines 650-672).
   Instead, compute `needsOnboarding` and use it to conditionally render
   the onboarding box inside the main layout.

2. Move the `needsOnboarding` check inside the main render, above the
   `<PhasePanel>` in the left column (line 864). When `needsOnboarding && !skipped`,
   render `<PlaybookOnboarding>` in the left panel space instead of `<PhasePanel>`:
   ```tsx
   <div className="flex-[3] min-w-0 flex flex-col min-h-0">
     {needsOnboarding && !skipped ? (
       <PlaybookOnboarding
         onSkip={() => setSkipped(true)}
         onGenerate={handleOnboardGenerate}
         isGenerating={isStreaming}
         onBrowseTemplates={() => setShowTemplateSelector(true)}
       />
     ) : (
       <PhasePanel
         phase={viewPhase}
         content={localContent}
         onEditorUpdate={handleEditorUpdate}
         editable={saveStatus !== 'saving'}
         extractedData={docQuery.data?.extracted_data}
         playbookSelections={docQuery.data?.playbook_selections}
         playbookId={docQuery.data?.id}
         onPhaseAdvance={handlePhaseNavigate}
       />
     )}
   </div>
   ```

3. The chat panel (right column, `<PlaybookChat>` at line 877) stays visible
   during onboarding. Users can already talk to the AI while the form is showing.

4. Update `PlaybookOnboarding.tsx` styling: change the outer wrapper from
   `flex items-center justify-center h-full` (centered fullscreen) to a
   contained card that sits at the top of its column:
   ```tsx
   // FROM (line 58):
   <div className="flex items-center justify-center h-full">
   // TO:
   <div className="flex flex-col items-center pt-12">
   ```

5. Handle the `TemplateSelector` path: the `showTemplateSelector` early return
   (lines 651-662) should also be inlined into the left panel rather than
   being a full-page takeover.

6. When the strategy document gets content (research completes and
   `build_seeded_template` writes content), `needsOnboarding` becomes false
   and the box disappears automatically (the condition checks `!docContent.trim()`).

**Validation:**
```bash
cd frontend && npx tsc --noEmit
```
Visually: opening a new space shows the onboarding form in the left panel
with the chat visible on the right. After generation, the form disappears
and `PhasePanel` appears.

**Commit:** `fix(playbook): inline onboarding box, keep chat visible (BL-196)`

---

## Track 4: Fix Document Editing (BL-193)

**Effort:** M (3 tasks)
**Goal:** Investigate and fix why the strategy document stays empty after
the AI says it's building sections.

### Task 4.1: Investigate the failure path

**Files:**
- `api/routes/playbook_routes.py` (lines 901-1035: `_run_self_research`)
- `api/services/playbook_service.py` (line 1182: `build_seeded_template`)
- `api/services/strategy_tools.py` (line 177: `update_strategy_section`)

**Investigation questions:**

1. **Is `build_seeded_template()` being called?** Add logging before and after
   the call at playbook_routes.py:974. Check if `enrichment_data` is None
   (which causes it to return `_build_empty_template()`).

2. **Is `doc.version == 1` guard stale?** At line 970, the template is only
   seeded when `doc.version == 1`. If the AI chat has already incremented the
   version (e.g., by calling `update_strategy_section`), the seeded template
   will never be written. This is a likely race condition.

3. **Is `update_strategy_section` tool actually called?** Check
   `playbook_service.py` for the system prompt — does it instruct the AI to
   use the tool to write sections? Or does the AI just produce text in chat
   without tool calls?

4. **Does the frontend poll for content changes?** Check if `usePlaybookDocument`
   refetches after research completes. If it only fetches once, the editor
   will show stale (empty) content.

**Steps:**

1. Read `_run_self_research` carefully. Trace the flow:
   - `enrich_l1()` runs, populates L1 tables
   - Company status set to `triage_passed`
   - `enrich_l2()` runs, populates L2 tables
   - `_load_enrichment_data()` gathers all enrichment
   - `build_seeded_template()` generates markdown
   - `doc.content = ...` writes to the StrategyDocument row
   - `db.session.commit()`

2. Add structured logging at each step. Deploy to staging and trigger
   onboarding flow. Read logs to identify where the chain breaks.

3. Check the `doc.version == 1` guard — this is the most likely culprit.
   If the AI chat sends a message that triggers `update_strategy_section`
   before research completes, version increments to 2, and the seeded
   template is silently skipped.

**Commit:** `chore(playbook): add diagnostic logging to research pipeline (BL-193)`

### Task 4.2: Fix the version guard race condition

**Files:**
- `api/routes/playbook_routes.py` (line 970)

**Steps:**

1. Replace the `doc.version == 1` guard with a content-based check:
   ```python
   # FROM (line 970):
   if doc and doc.version == 1:
   # TO:
   if doc and not doc.content.strip():
   ```
   Rationale: the seeded template should be written whenever the document
   is empty, regardless of version. If the AI has already written content,
   the seeded template should not overwrite it.

2. Apply the same fix to the fallback path at line 1025:
   ```python
   # FROM:
   if doc and doc.version == 1:
   # TO:
   if doc and not (doc.content or '').strip():
   ```

3. Add a version increment after seeding so the frontend detects the change:
   ```python
   doc.content = build_seeded_template(...)
   doc.enrichment_id = company_id
   doc.version += 1  # Signal content change to frontend polling
   db.session.commit()
   ```

**Validation:**
```bash
make test-changed
```
Test scenario: trigger research on a fresh space. Verify the document gets
populated with seeded template content. Verify a space where the AI has already
written content is not overwritten.

**Commit:** `fix(playbook): use content check instead of version guard for template seeding (BL-193)`

### Task 4.3: Ensure frontend refetches after research completes

**Files:**
- `frontend/src/pages/playbook/PlaybookPage.tsx`
- `frontend/src/api/queries/usePlaybook.ts`

**Steps:**

1. Check if `usePlaybookDocument` has any refetch logic tied to research
   completion. Currently, `useResearchStatus` polls every 10s (line 116 of
   `usePlaybook.ts`). When research transitions from `in_progress` to
   `completed`, the document query should be invalidated.

2. If there is no invalidation, add an effect in `PlaybookPage.tsx`:
   ```tsx
   useEffect(() => {
     if (researchQuery.data?.status === 'completed') {
       qc.invalidateQueries({ queryKey: ['playbook', 'document'] })
     }
   }, [researchQuery.data?.status, qc])
   ```

3. Also check that `usePlaybookDocument` does not cache aggressively
   (staleTime should be low or 0 for the document query).

**Validation:**
```bash
cd frontend && npx tsc --noEmit
```
Test scenario: trigger research, wait for completion, verify the editor
auto-populates without a manual refresh.

**Commit:** `fix(playbook): refetch document when research completes (BL-193)`

---

## Track 1: Python Research Service (BL-189 + BL-190)

**Effort:** L + M (5 tasks)
**Goal:** Replace the current enrichment pipeline with a Python research
service that emits progress events for chat display. Use a domain-first
strategy: resolve domain, scrape website, run web search, build profile.

### Architecture Overview

The current `_run_self_research()` in `playbook_routes.py:901-1035` already
calls Python enrichment functions (`enrich_l1` and `enrich_l2`). These are
**already Python-native** (not n8n webhooks):

- `api/services/l1_enricher.py` (1428 lines) — Perplexity sonar API for
  company profile, website scraping, domain resolution
- `api/services/l2_enricher.py` (1065 lines) — Perplexity sonar-pro for
  news/signals + Anthropic Claude for synthesis

**The research pipeline is already Python.** The problem is that it runs
silently in a background thread with no progress visibility. The work for
this track is:

1. Add progress event emission to the existing enrichment functions
2. Create a new research event model or use the existing chat/SSE mechanism
3. Wire events so the frontend can show them as tool cards (Track 3)

### Task 1.1: Define research event schema and storage

**Files to create/modify:**
- `api/models.py` — add `ResearchEvent` model (or extend existing `PlaybookLog`)
- `api/routes/playbook_routes.py` — new endpoint `GET /api/playbook/research/events`

**Research event schema:**
```python
class ResearchEvent:
    """A single step in the research pipeline, shown as a tool card in chat."""
    id: str              # UUID
    tenant_id: str       # UUID
    company_id: str      # UUID
    step: str            # e.g., 'domain_resolve', 'website_scrape', 'l1_research', 'l2_news', 'l2_signals', 'l2_synthesis', 'template_build'
    status: str          # 'running' | 'success' | 'error'
    summary: str | None  # Human-readable summary when done
    detail: dict | None  # Structured data (domain found, key findings, etc.)
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
```

**Steps:**

1. Decide whether to use a new DB table or in-memory store. Given that
   research events are transient (only needed during the research session),
   an in-memory dict keyed by `(tenant_id, company_id)` is simpler:
   ```python
   # api/services/research_events.py
   _events: dict[str, list[dict]] = {}  # key: f"{tenant_id}:{company_id}"

   def emit_event(tenant_id, company_id, step, status, summary=None, detail=None): ...
   def get_events(tenant_id, company_id) -> list[dict]: ...
   def clear_events(tenant_id, company_id): ...
   ```

2. Create the API endpoint:
   ```python
   @playbook_bp.route("/api/playbook/research/events", methods=["GET"])
   @require_auth
   def get_research_events():
       tenant_id = resolve_tenant()
       company = Company.query.filter_by(tenant_id=tenant_id, is_self=True).first()
       if not company:
           return jsonify({"events": []})
       events = get_events(str(tenant_id), str(company.id))
       return jsonify({"events": events})
   ```

3. Write a unit test for `emit_event` and `get_events`.

**Validation:**
```bash
make test-changed
```

**Commit:** `feat(playbook): add research event emitter and API endpoint (BL-189)`

### Task 1.2: Add progress events to L1 enrichment

**Files:**
- `api/services/l1_enricher.py` — the `enrich_l1()` function (line 194)
- `api/routes/playbook_routes.py` — `_run_self_research()`

**Context:** `enrich_l1()` does these steps internally:
1. Resolve company domain (website scraping)
2. Build Perplexity prompt with scraped data
3. Call Perplexity sonar API
4. Parse response and store in DB
5. QC checks and status update

The engineer must read `enrich_l1()` (line 194 onwards) to identify the
exact points where events should be emitted. The function signature is:
```python
def enrich_l1(company_id, tenant_id=None, previous_data=None, boost=False):
```

**Steps:**

1. Read `enrich_l1()` fully to understand its internal flow.

2. Add `emit_event()` calls at key milestones. The exact placement depends
   on the function's internal structure, but the pattern is:
   ```python
   emit_event(tenant_id, company_id, 'domain_resolve', 'running', 'Resolving company domain...')
   # ... existing domain resolution code ...
   emit_event(tenant_id, company_id, 'domain_resolve', 'success',
              f'Found domain: {domain}', {'domain': domain})

   emit_event(tenant_id, company_id, 'website_scrape', 'running', 'Reading company website...')
   # ... existing scraping code ...
   emit_event(tenant_id, company_id, 'website_scrape', 'success',
              f'Extracted {len(text)} chars from {domain}',
              {'url': url, 'chars': len(text)})

   emit_event(tenant_id, company_id, 'l1_research', 'running', 'Researching company profile...')
   # ... existing Perplexity call ...
   emit_event(tenant_id, company_id, 'l1_research', 'success',
              f'Profile: {company_name} — {industry}',
              {'company_name': company_name, 'industry': industry, 'size': size})
   ```

3. The `tenant_id` parameter may be None in some call paths. In
   `_run_self_research`, it is always provided. For the event emitter to
   work, ensure `tenant_id` is passed through. If `enrich_l1` does not
   currently accept/use `tenant_id` for this purpose, thread it through.

4. Wrap each `emit_event` in try/except so event emission failures never
   break the enrichment pipeline.

**Validation:**
```bash
make test-changed
```
Trigger research via API, then poll `/api/playbook/research/events` — should
see domain_resolve, website_scrape, l1_research events.

**Commit:** `feat(playbook): emit research progress events from L1 enricher (BL-189)`

### Task 1.3: Add progress events to L2 enrichment

**Files:**
- `api/services/l2_enricher.py` — the `enrich_l2()` function (line 243)
- `api/routes/playbook_routes.py` — `_run_self_research()`

**Context:** `enrich_l2()` does these steps:
1. Two Perplexity calls (News + Strategic Signals) using sonar-pro
2. Anthropic Claude synthesis of research into actionable intelligence
3. Store results in DB

**Steps:**

1. Read `enrich_l2()` fully (line 243 onwards) to map its internal phases.

2. Add events for each phase:
   ```python
   emit_event(tenant_id, company_id, 'l2_news', 'running', 'Researching recent company news...')
   # ... Perplexity news call ...
   emit_event(tenant_id, company_id, 'l2_news', 'success',
              f'Found {n} news items', {'count': n})

   emit_event(tenant_id, company_id, 'l2_signals', 'running', 'Analyzing strategic signals...')
   # ... Perplexity signals call ...
   emit_event(tenant_id, company_id, 'l2_signals', 'success',
              'Identified AI maturity and growth signals',
              {'ai_adoption': level, 'growth': indicators})

   emit_event(tenant_id, company_id, 'l2_synthesis', 'running', 'Synthesizing research with AI...')
   # ... Anthropic synthesis call ...
   emit_event(tenant_id, company_id, 'l2_synthesis', 'success',
              'Research synthesis complete',
              {'sections': ['overview', 'opportunities', 'pain_points', 'quick_wins']})
   ```

3. Same defensive pattern: wrap in try/except, never break enrichment.

**Validation:**
```bash
make test-changed
```

**Commit:** `feat(playbook): emit research progress events from L2 enricher (BL-190)`

### Task 1.4: Add template build event

**Files:**
- `api/routes/playbook_routes.py` — `_run_self_research()` (around line 974)

**Steps:**

1. After L2 completes and before `build_seeded_template()` is called, emit:
   ```python
   emit_event(tenant_id, company_id, 'template_build', 'running',
              'Building your strategy document...')
   ```

2. After the template is written to DB:
   ```python
   emit_event(tenant_id, company_id, 'template_build', 'success',
              f'Strategy document generated ({len(doc.content)} chars, 9 sections)',
              {'sections': STRATEGY_SECTIONS, 'chars': len(doc.content or '')})
   ```

3. In the error fallback path (line 1021-1035), emit an error event:
   ```python
   emit_event(tenant_id, company_id, 'template_build', 'error',
              'Research encountered errors; document built with partial data')
   ```

**Validation:**
```bash
make test-changed
```

**Commit:** `feat(playbook): emit template build events in research pipeline (BL-190)`

### Task 1.5: Unit tests for research event system

**Files:**
- `tests/unit/test_research_events.py` (new file)

**Steps:**

1. Test `emit_event` stores events correctly:
   ```python
   def test_emit_event_stores_in_order():
       clear_events('t1', 'c1')
       emit_event('t1', 'c1', 'domain_resolve', 'running', 'Resolving...')
       emit_event('t1', 'c1', 'domain_resolve', 'success', 'Found example.com')
       events = get_events('t1', 'c1')
       assert len(events) == 2
       assert events[0]['step'] == 'domain_resolve'
       assert events[0]['status'] == 'running'
       assert events[1]['status'] == 'success'
   ```

2. Test `clear_events` removes all events for a key.

3. Test `get_events` returns empty list for unknown key.

4. Test that events include timestamps and duration_ms calculation.

5. Test API endpoint returns events in correct format (use test client
   from conftest.py fixtures).

**Validation:**
```bash
make test-changed
```

**Commit:** `test(playbook): unit tests for research event system (BL-189)`

---

## Track 3: Chat Research UX (BL-191 + BL-192 + BL-194)

**Effort:** M + S + S (4 tasks)
**Goal:** Show research progress as Claude-style tool cards in chat,
with human-formatted details (not JSON), and remove the top-bar spinner.

**Depends on:** Track 1 (research event emitter and API endpoint).

### Task 3.1: Frontend polling for research events (BL-191)

**Files:**
- `frontend/src/api/queries/usePlaybook.ts`
- `frontend/src/pages/playbook/PlaybookPage.tsx`

**Steps:**

1. Add a new query hook in `usePlaybook.ts`:
   ```tsx
   interface ResearchEvent {
     id: string
     step: string
     status: 'running' | 'success' | 'error'
     summary: string | null
     detail: Record<string, unknown> | null
     started_at: string
     completed_at: string | null
     duration_ms: number | null
   }

   export function useResearchEvents(enabled: boolean) {
     return useQuery({
       queryKey: ['playbook', 'research', 'events'],
       queryFn: () => apiFetch<{ events: ResearchEvent[] }>('/playbook/research/events'),
       enabled,
       refetchInterval: (query) => {
         const data = query.state.data
         if (!data) return false
         const hasRunning = data.events.some(e => e.status === 'running')
         return hasRunning ? 2000 : false  // Poll every 2s while research is active
       },
     })
   }
   ```

2. In `PlaybookPage.tsx`, use the hook:
   ```tsx
   const researchEventsQuery = useResearchEvents(researchTriggered)
   ```

3. Convert research events to `ToolCallEvent[]` format that `ToolCallCardList`
   already understands:
   ```tsx
   const researchToolCalls: ToolCallEvent[] = (researchEventsQuery.data?.events || []).map(e => ({
     tool_call_id: e.id,
     tool_name: `research_${e.step}`,  // e.g., 'research_domain_resolve'
     input: {},
     status: e.status,
     summary: e.summary || undefined,
     output: e.detail || undefined,
     duration_ms: e.duration_ms || undefined,
   }))
   ```

4. Pass these tool calls to `PlaybookChat` or inject them into the chat
   message list as a synthetic assistant message with tool_calls metadata.
   The cleanest approach: render a `ToolCallCardList` above the chat messages
   when research is in progress.

**Validation:**
```bash
cd frontend && npx tsc --noEmit
```

**Commit:** `feat(playbook): poll research events and map to tool call cards (BL-191)`

### Task 3.2: Render research events as tool cards in chat (BL-191)

**Files:**
- `frontend/src/components/playbook/PlaybookChat.tsx`
- `frontend/src/components/chat/ChatMessages.tsx`
- `frontend/src/components/playbook/ToolCallCard.tsx`

**Steps:**

1. Add a `getToolMeta` mapping for research step names in `ToolCallCard.tsx`.
   Add entries to the `getToolMeta` function (around line 40):
   ```tsx
   if (toolName.startsWith('research_')) {
     const step = toolName.replace('research_', '')
     const stepMeta: Record<string, ToolMeta> = {
       'domain_resolve': { icon: <SearchIcon />, verb: 'Resolving' },
       'website_scrape': { icon: <EyeIcon />, verb: 'Reading' },
       'l1_research':    { icon: <SearchIcon />, verb: 'Researching' },
       'l2_news':        { icon: <ListIcon />, verb: 'Researching' },
       'l2_signals':     { icon: <SearchIcon />, verb: 'Analyzing' },
       'l2_synthesis':   { icon: <WrenchIcon />, verb: 'Synthesizing' },
       'template_build': { icon: <CreateIcon />, verb: 'Building' },
     }
     return stepMeta[step] || { icon: <SearchIcon />, verb: 'Researching' }
   }
   ```

2. Update `humanizeToolName` (line 66) to handle `research_` prefix:
   ```tsx
   // Add 'research_' to the prefixes array:
   const prefixes = ['research_', 'get_', 'update_', ...]
   ```
   This will transform `research_domain_resolve` to `domain resolve`,
   `research_l2_synthesis` to `l2 synthesis`, etc.

3. In `PlaybookChat.tsx` (or wherever research tool calls are rendered),
   insert the research events `ToolCallCardList` at the top of the chat
   area when research is active. The exact integration point depends on
   how `PlaybookChat` receives props — pass `researchToolCalls` as a prop
   and render them before the first message.

**Validation:**
```bash
cd frontend && npx tsc --noEmit
```
Visually: when research is triggered, tool cards appear in the chat area
showing each step (domain resolution, website scrape, L1 research, etc.)
with running spinners that transition to success checkmarks.

**Commit:** `feat(playbook): render research steps as tool cards in chat (BL-191)`

### Task 3.3: Human-formatted detail in tool card expand (BL-192)

**Files:**
- `frontend/src/components/playbook/ToolCallCard.tsx` (lines 416-430)

**Context:** Currently, expanding a tool card shows raw JSON via `JsonBlock`
(lines 418-423). For research events, the expand should show human-readable
formatted detail instead.

**Steps:**

1. Add a `ResearchDetail` component that renders structured research data:
   ```tsx
   function ResearchDetail({ step, detail }: { step: string; detail: Record<string, unknown> }) {
     // Format based on step type
     if (step === 'domain_resolve' || step === 'research_domain_resolve') {
       return (
         <div className="text-xs text-text-muted space-y-1 mt-2">
           <div><span className="font-medium">Domain:</span> {String(detail.domain || 'Unknown')}</div>
         </div>
       )
     }
     if (step === 'website_scrape' || step === 'research_website_scrape') {
       return (
         <div className="text-xs text-text-muted space-y-1 mt-2">
           <div><span className="font-medium">URL:</span> {String(detail.url || '')}</div>
           <div><span className="font-medium">Content:</span> {String(detail.chars || 0)} characters extracted</div>
         </div>
       )
     }
     if (step.includes('l1_research') || step.includes('research_l1')) {
       return (
         <div className="text-xs text-text-muted space-y-1 mt-2">
           {detail.company_name && <div><span className="font-medium">Company:</span> {String(detail.company_name)}</div>}
           {detail.industry && <div><span className="font-medium">Industry:</span> {String(detail.industry)}</div>}
           {detail.size && <div><span className="font-medium">Size:</span> {String(detail.size)}</div>}
         </div>
       )
     }
     // ... similar for l2_news, l2_signals, l2_synthesis, template_build
     // Fallback: formatted key-value list
     return (
       <div className="text-xs text-text-muted space-y-1 mt-2">
         {Object.entries(detail).map(([k, v]) => (
           <div key={k}><span className="font-medium">{k.replace(/_/g, ' ')}:</span> {String(v)}</div>
         ))}
       </div>
     )
   }
   ```

2. In the `ToolCallCard` expanded detail section (line 416-430), check if the
   tool name starts with `research_` and render `ResearchDetail` instead of
   `JsonBlock`:
   ```tsx
   {isExpanded && (
     <div className="px-3 pb-3 border-t border-border-solid">
       {toolName.startsWith('research_') && output ? (
         <ResearchDetail step={toolName} detail={output} />
       ) : (
         <>
           {input && Object.keys(input).length > 0 && (
             <JsonBlock data={input} label="Input" />
           )}
           {output && Object.keys(output).length > 0 && (
             <JsonBlock data={output} label="Output" />
           )}
         </>
       )}
       {displayStatus === 'error' && summary && (
         <div className="mt-2 text-xs text-error">{summary}</div>
       )}
     </div>
   )}
   ```

**Validation:**
```bash
cd frontend && npx tsc --noEmit
```
Visually: clicking on a completed research step shows formatted info
(domain, company name, industry) instead of raw JSON.

**Commit:** `fix(playbook): show human-formatted detail in research tool cards (BL-192)`

### Task 3.4: Remove research spinner from top bar (BL-194)

**Files:**
- `frontend/src/pages/playbook/PlaybookPage.tsx` (lines 707-722)

**Steps:**

1. Delete the entire research status indicator block at lines 707-722:
   ```tsx
   // DELETE this entire block:
   {/* Research status indicator */}
   {researchTriggered && researchQuery.data?.status === 'in_progress' && (
     <div className="flex items-center gap-1.5 ml-1">
       <span className="w-3 h-3 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
       <span className="text-xs text-accent-cyan font-medium">
         Researching...
       </span>
     </div>
   )}
   {researchTriggered && researchQuery.data?.status === 'failed' && (
     <div className="flex items-center gap-1.5 ml-1">
       <span className="text-xs text-text-muted">
         Research incomplete
       </span>
     </div>
   )}
   ```

2. The research progress is now shown via tool cards in chat (Task 3.2),
   so the top-bar spinner is redundant.

3. Optionally, keep the `useResearchStatus` hook active (it still drives
   the document refetch in Task 4.3). Just remove the visual indicator.

4. If `researchQuery` is no longer used for rendering, clean up but keep
   the `researchTriggered` state since it gates the event polling.

**Validation:**
```bash
cd frontend && npx tsc --noEmit
```
Visually: no more cyan "Researching..." spinner in the top bar.
Research progress shows only in the chat via tool cards.

**Commit:** `fix(playbook): remove redundant research spinner from top bar (BL-194)`

---

## Task Summary

| # | Track | Task | BL | Effort | Files |
|---|-------|------|----|--------|-------|
| 5.1 | 5 | Remove PhaseIndicator | BL-195 | S | PlaybookPage.tsx, PhaseIndicator.tsx |
| 2.1 | 2 | GTM objective question | BL-188 | S | PlaybookOnboarding.tsx |
| 2.2 | 2 | Inline onboarding box | BL-196 | S | PlaybookPage.tsx, PlaybookOnboarding.tsx |
| 4.1 | 4 | Investigate doc fix | BL-193 | M | playbook_routes.py, playbook_service.py, strategy_tools.py |
| 4.2 | 4 | Fix version guard | BL-193 | S | playbook_routes.py |
| 4.3 | 4 | Refetch on research done | BL-193 | S | PlaybookPage.tsx, usePlaybook.ts |
| 1.1 | 1 | Research event schema | BL-189 | M | models.py or research_events.py, playbook_routes.py |
| 1.2 | 1 | L1 progress events | BL-189 | M | l1_enricher.py, playbook_routes.py |
| 1.3 | 1 | L2 progress events | BL-190 | M | l2_enricher.py, playbook_routes.py |
| 1.4 | 1 | Template build event | BL-190 | S | playbook_routes.py |
| 1.5 | 1 | Unit tests | BL-189 | S | test_research_events.py (new) |
| 3.1 | 3 | Frontend event polling | BL-191 | M | usePlaybook.ts, PlaybookPage.tsx |
| 3.2 | 3 | Render as tool cards | BL-191 | M | PlaybookChat.tsx, ChatMessages.tsx, ToolCallCard.tsx |
| 3.3 | 3 | Human-formatted detail | BL-192 | S | ToolCallCard.tsx |
| 3.4 | 3 | Remove spinner | BL-194 | S | PlaybookPage.tsx |

**Total: 15 tasks across 5 tracks.**

---

## Execution Order

```
Phase 1 (parallel):
  Engineer A: Track 5 (task 5.1) → Track 2 (tasks 2.1, 2.2)
  Engineer B: Track 4 (tasks 4.1, 4.2, 4.3)
  Engineer C: Track 1 (tasks 1.1, 1.2, 1.3, 1.4, 1.5)

Phase 2 (after Track 1 completes):
  Engineer A or B: Track 3 (tasks 3.1, 3.2, 3.3, 3.4)
```

**Total engineers:** 3 in Phase 1, then 1 for Phase 2.
**Estimated sessions:** 2 (Phase 1 is ~1 session, Phase 2 is ~0.5 session).

---

## Test Commands

```bash
# After each task:
make test-changed                    # Python unit tests (context-aware)
cd frontend && npx tsc --noEmit      # TypeScript type check

# Before sprint PR:
make lint-changed                    # Python lint (changed files)
cd frontend && npx tsc --noEmit      # Full TS check

# Sprint completion (after all PRs merge to staging):
make test-e2e                        # Full Playwright suite
```
