# Leadgen Pipeline -- Comprehensive Gap Analysis

**Date:** 2026-02-22
**Purpose:** Compare what EXISTS in the codebase today against what the VISION, GTM STRATEGY, and BUSINESS MODEL require.
**Method:** Direct codebase exploration of `api/`, `frontend/`, `dashboard/`, `migrations/`, and all worktrees.

---

## Executive Summary

The platform has a solid **data foundation** (enrichment pipeline, PostgreSQL backend, multi-tenancy, JWT auth) and an **emerging playbook** (Tiptap editor + AI chat, onboarding research flow). However, the vision describes a **closed-loop GTM engine** with four flywheel phases (Try, Run, Evaluate, Improve), while the product today covers roughly the first half of the "Try" phase and fragments of "Run." The Evaluate and Improve loops do not exist at all.

**Key finding:** Of the 20 capability areas analyzed, 3 are substantially built, 5 are partially built, and 12 have zero implementation. The most critical gaps for MVP (first 10 paying customers) are the multi-phase playbook flow, campaign launch, and a public landing page.

---

## Capability-by-Capability Analysis

### 1. Onboarding / Self-Research

**Vision requirement:** User enters their company domain, AI researches their company (website scraping, L1+L2 enrichment), and seeds a strategy template with findings. The AI asks 3-5 key questions, not 50. (Vision: Step 1 "Research", AI as Analyst)

**Current state:** PARTIALLY BUILT.
- `PlaybookOnboarding` component exists at `/Users/michal/git/leadgen-pipeline/frontend/src/components/playbook/PlaybookOnboarding.tsx` -- accepts domain + objective, triggers research.
- Backend: `POST /api/playbook/research` in `playbook_routes.py` (line ~250+) creates a Company with `is_self=True`, runs L1+L2 enrichment, and seeds the strategy template via `build_seeded_template()` in `playbook_service.py`.
- Status polling: `useResearchStatus` hook polls the company status until enrichment completes.
- Migration 029 adds `is_self` flag to companies table.
- Auto-complete: when research finishes, calls `onComplete()` which transitions to the editor.

**Gap:**
- The onboarding flow is functional but passive -- it waits for enrichment to finish, then dumps the user into a blank-ish template. The vision says the AI should "come back with findings, not more questions" and auto-send a first message.
- No proactive first AI message after research completes -- the chat panel starts empty.
- No progress indication of WHAT the AI is learning (just a spinner with "L1 enrichment" / "L2 enrichment" labels).

**MVP priority:** YES -- this is the first-impression moment. Already mostly built.

**Effort:** S (polish, not rebuild)

---

### 2. Strategy Editor

**Vision requirement:** Rich text editor where the AI helps build an 8-section GTM strategy document (ICP, Buyer Personas, Value Proposition, Competitive Positioning, Channel Strategy, Messaging Framework, Success Metrics). AI assists with editing, challenges weak assumptions, fills gaps proactively.

**Current state:** BUILT.
- `StrategyEditor` component at `/Users/michal/git/leadgen-pipeline/frontend/src/components/playbook/StrategyEditor.tsx` -- full Tiptap setup with StarterKit, Heading, Table, TableRow, TableCell, TableHeader, Placeholder, and Markdown extensions.
- Toolbar with bold, italic, headings, lists, tables, and more.
- Strategy template with 8 sections defined in `/Users/michal/git/leadgen-pipeline/frontend/src/components/playbook/strategy-template.ts`.
- Save (PUT `/api/playbook`) with optimistic version locking (version conflict returns 409).
- Extract (POST `/api/playbook/extract`) uses Claude to parse structured data from the document into `extracted_data` JSONB.
- Editor CSS at `/Users/michal/git/leadgen-pipeline/frontend/src/components/playbook/strategy-editor.css`.

**Gap:**
- Manual save button only -- no auto-save with debounce (vision specifies "2.5-second debounced save, no Save button").
- Manual extract button only -- no auto-extract ("extracted silently after every save").
- AI cannot directly edit the strategy document from chat -- only the user can type into the editor.
- No AI-suggested edits that appear as tracked changes or suggestions in the document.

**MVP priority:** YES -- core of the Try phase. Editor works; auto-save/extract is a polish item.

**Effort:** S (auto-save/extract), M (AI-suggested edits)

---

### 3. Playbook Chat

**Vision requirement:** Persistent AI chat that adapts per phase, asks probing questions, provides findings-based recommendations, detects frustration, matches the user's language, and includes actionable items with checkboxes. "The AI is the strategist; the founder is the CEO."

**Current state:** PARTIALLY BUILT.
- `PlaybookChat` component at `/Users/michal/git/leadgen-pipeline/frontend/src/components/playbook/PlaybookChat.tsx` -- receives messages + streaming state, renders user/assistant bubbles, auto-scrolls.
- Backend: `POST /api/playbook/chat` in `playbook_routes.py` with SSE streaming via `useSSE` hook.
- System prompt built in `playbook_service.py` via `build_system_prompt()` -- includes tenant context, enrichment data (L1/L2 company profile, signals, market data), strategy document content, and 8-section structure.
- Message history: `MAX_HISTORY_MESSAGES = 20` recent messages included in context.
- Chat messages stored in `strategy_chat_messages` table (migration 029).
- Model: Claude Haiku 4.5 via `AnthropicClient`.

**Gap:**
- No phase-aware instructions -- `build_system_prompt()` currently does NOT accept a `phase` parameter. All conversations use the same "strategy" persona regardless of context. (Design doc PB-005 specifies `PHASE_INSTRUCTIONS` dict -- not yet implemented.)
- No proactive AI behavior -- the AI only responds when the user sends a message. Vision says "auto-sends the first message after research" and "asks targeted questions based on findings."
- No action items -- AI responses are plain text. No `- [ ]` parsing, no interactive checkboxes (PB-021/PB-022 not built).
- No frustration detection -- system prompt has no sentiment-aware instructions (PB-027 not built).
- No language matching -- no detection of user's language to switch AI response language (PB-028 not built).
- No topic/intent detection -- no awareness of cross-phase questions (PB-026 not built).
- No markdown rendering in chat -- messages are rendered as plain text in `PlaybookChat.tsx`. The `RichText` component exists at `/Users/michal/git/leadgen-pipeline/frontend/src/components/ui/RichText.tsx` but is not used in chat.
- No phase transition cards -- no `PhaseTransitionCard` component (PB-024 not built).

**MVP priority:** YES -- the chat is the product's soul. Phase-aware prompts and proactive first message are critical for the demo.

**Effort:** M (phase prompts + proactive first message), L (full action items + frustration detection)

---

### 4. Multi-Phase Flow

**Vision requirement:** Four-phase guided workflow: Strategy -> Contacts -> Messages -> Campaign. Phase stepper UI, readiness gates for forward transitions, free backward navigation. Left panel switches per phase; chat persists across all phases.

**Current state:** NOT BUILT.
- Current routing: `App.tsx` line 54: `<Route path="playbook" element={<PlaybookPage />} />` -- single route, no phase parameter.
- No `phase` column on `strategy_documents` table (migration 033 not applied).
- No `playbook_selections` column for storing per-phase structured data.
- No `PhaseIndicator` component.
- No `PlaybookTopBar` component.
- No `StrategyPanel` extraction (editor is inline in `PlaybookPage`).
- No phase guard logic.
- The design doc (`2026-02-22-playbook-multi-phase-design.md`) and implementation backlog (`2026-02-22-playbook-implementation-backlog.md`) are fully specified with 34 items (PB-001 through PB-034) but NONE are implemented.

**Gap:** Everything. The entire multi-phase infrastructure (Bucket 1: PB-001 through PB-010) needs to be built from scratch.

**MVP priority:** YES -- this is the core product differentiator. The stepper UI is what makes the demo compelling. At minimum, Bucket 1 (infrastructure) is needed.

**Effort:** L (Bucket 1 alone = 10 items, mix of S/M)

---

### 5. Contact Selection (Phase 2)

**Vision requirement:** ICP-driven filtering of contacts, pre-populated from extracted strategy data. User selects which contacts to target. AI recommends contacts and explains why they match the ICP.

**Current state:** NOT BUILT (in playbook context).
- Existing contacts infrastructure IS built: `ContactsPage` at `frontend/src/pages/contacts/ContactsPage.tsx`, `ContactDetail` at `frontend/src/pages/contacts/ContactDetail.tsx`, full CRUD API at `api/routes/contact_routes.py`.
- DataTable with filtering exists at `frontend/src/components/ui/DataTable.tsx`.
- FilterBar component exists at `frontend/src/components/ui/FilterBar.tsx`.
- BUT: No `ContactSelectionPanel` component for the playbook (PB-011 not built).
- No API endpoint to store selections in `playbook_selections` (PB-012 not built).
- No ICP-derived filter pre-population logic.

**Gap:** The data layer (contacts, companies, enrichment) exists. The playbook-specific selection UI and persistence layer do not.

**MVP priority:** YES -- but can be a thin wrapper around existing contacts components for MVP.

**Effort:** M (leverages existing DataTable and contacts API)

---

### 6. Message Generation (Phase 3)

**Vision requirement:** AI generates personalized outreach messages per contact using strategy + enrichment data. User reviews, edits, approves. Per-persona calibration. A/B variants.

**Current state:** PARTIALLY BUILT (standalone, not in playbook flow).
- Message generation engine exists: `api/services/message_generator.py` -- background thread, Claude Haiku 3.5, progress tracking.
- Generation prompts: `api/services/generation_prompts.py` with `SYSTEM_PROMPT`, `build_generation_prompt()`, channel-specific constraints.
- Campaign-scoped generation: `POST /api/campaigns/:id/generate` triggers generation for all contacts in a campaign.
- Messages table: `api/models.py` class `Message` (line 902) with fields: contact_id, campaign_id, channel, step, subject, body, status (draft/approved/rejected/sent), persona, edit_reason.
- Message review UI: `frontend/src/pages/messages/MessagesPage.tsx`, `MessageCard.tsx`, `MessageReviewPage.tsx`, `EditPanel.tsx`, `RegenerationDialog.tsx`, `DisqualifyDialog.tsx`.
- Campaign message review: `frontend/src/components/campaign/MessageReviewQueue.tsx`.

**Gap:**
- No `MessageReviewPanel` for the playbook (PB-016 not built).
- No automatic generation trigger on phase entry (PB-017 not built).
- Message generation is campaign-scoped, not playbook-scoped -- generating from the playbook would need to create a campaign first or use a different trigger.
- No persona-based generation using extracted strategy data (personas from `extracted_data` are not fed into `build_generation_prompt`).
- No A/B variant generation in the current system.

**MVP priority:** YES -- this is the "Run" phase. The underlying engine works; needs playbook integration.

**Effort:** M (playbook wrapper + strategy-informed prompts)

---

### 7. Campaign Launch (Phase 4)

**Vision requirement:** Configure and launch outreach campaigns. Sequencing, timing, channel selection. A/B testing. Integration with sending infrastructure.

**Current state:** PARTIALLY BUILT (standalone campaigns).
- Campaign model: `api/models.py` class `Campaign` (line 959) with name, status (draft/ready/generating/review/approved/exported/archived), template_config (JSONB), generation_config, sender_config.
- Campaign contacts: `CampaignContact` model (line 993) linking campaigns to contacts.
- Campaign templates: `CampaignTemplate` model (line 1024).
- Full campaign API: `api/routes/campaign_routes.py` with CRUD, status transitions, generation triggers, send execution.
- Email sending via Resend: `api/services/send_service.py` with `send_campaign_emails()`, idempotent via `EmailSendLog`.
- LinkedIn send queue: `LinkedInSendQueue` model (line 1312) with queued/claimed/sent lifecycle.
- Campaign UI: `frontend/src/pages/campaigns/CampaignsPage.tsx`, `CampaignDetailPage.tsx` with tabs including an Outreach tab and Analytics tab.
- Campaign analytics component: `frontend/src/components/campaign/CampaignAnalytics.tsx` with stat cards and progress bars.
- Contact picker: `frontend/src/pages/campaigns/ContactPicker.tsx`.
- Generation progress modal: `frontend/src/components/campaign/GenerationProgressModal.tsx`.

**Gap:**
- No `CampaignDashboard` panel for the playbook (PB-034 not built).
- Campaign infrastructure is standalone -- not wired into the multi-phase playbook flow.
- No A/B testing framework (mentioned in vision but not implemented anywhere).
- Sequencing is configured via `template_config` but timing/cadence is manual.
- LinkedIn sending is queue-based (manual copy-paste via Chrome extension), not automated.

**MVP priority:** PARTIAL -- the campaign infrastructure works standalone. Playbook integration can come in v2 since the demo can show "and from here, you launch your campaign."

**Effort:** M (playbook panel wrapper), L (A/B testing, automated sequencing)

---

### 8. Enrichment Pipeline

**Vision requirement:** L1 company profiling, L2 deep research, person-level enrichment, website scraping. Fast, cheap, and high quality.

**Current state:** BUILT.
- L1 enricher: `api/services/l1_enricher.py` -- Perplexity sonar, website scraping via BeautifulSoup, company profiling. Cost: $0.0008/company.
- L2 enricher: `api/services/l2_enricher.py` -- Perplexity sonar-pro (news + signals) + Claude Sonnet 4.5 (synthesis). 3 LLM calls. Cost: $0.0144/company.
- Person enricher: `api/services/person_enricher.py` -- Perplexity sonar (profile + signals) + Claude Sonnet 4.5 (synthesis). Cost: $0.0042/contact.
- Pipeline engine: `api/services/pipeline_engine.py` (939 lines) -- DAG-based orchestration, stage registry, batch processing.
- DAG visualization: `frontend/src/pages/enrich/DagVisualization.tsx`, `DagControls.tsx`, `DagEdges.tsx`, `StageCard.tsx`.
- Enrichment config: `api/routes/enrichment_config_routes.py` for model/parameter tuning.
- Schedule panel: `frontend/src/pages/enrich/SchedulePanel.tsx` for scheduled enrichment.
- LLM usage logging: `api/services/llm_logger.py`, `LlmUsageLog` model, `/api/llm-usage` routes.
- Enrichment data split across 6 tables: `CompanyEnrichmentL1`, `CompanyEnrichmentL2`, `CompanyEnrichmentProfile`, `CompanyEnrichmentSignals`, `CompanyEnrichmentMarket`, `CompanyEnrichmentOpportunity`.
- QC checker: `api/services/qc_checker.py` for triage assessment.
- Triage evaluator: `api/services/triage_evaluator.py`.

**Gap:**
- No result caching across tenants (same company enriched per-tenant, not shared).
- No incremental re-enrichment (re-runs full pipeline, not just stale parts).
- No Anthropic Batch API integration for cost savings.
- Contact sourcing/discovery not built -- you can enrich existing contacts but cannot FIND new contacts matching an ICP.

**MVP priority:** Already built. Contact discovery is a Phase 2 product feature, not MVP blocker.

**Effort:** N/A (built); S for incremental optimizations.

---

### 9. Auto-Save / Auto-Extract

**Vision requirement:** "Debounced 2.5-second save. No Save button. No 'unsaved changes' dialogs." Auto-extract runs silently after every save to keep `extracted_data` current.

**Current state:** NOT BUILT.
- Current flow: Manual "Save" button in `PlaybookPage.tsx` (line 48-55 `SaveIcon`, explicit `handleSave` callback).
- Manual "Extract" button (line 58-64 `ExtractIcon`).
- `isDirty` state tracked (line 88) but used only for a visual indicator, not for triggering auto-save.
- No `useDebounce` or `useAutoSave` hooks in the codebase.
- The vision document specifically marks "Auto-save" and "Auto-extract" as "Built Today" in the roadmap section -- this appears to be aspirational rather than factual.

**Gap:** Both auto-save (debounced) and auto-extract (triggered after save) need implementation.

**MVP priority:** YES -- this is table-stakes UX for a modern editor. Users losing work because they forgot to click Save is a churn risk.

**Effort:** S (well-understood pattern: useEffect + setTimeout debounce)

---

### 10. Markdown Rendering

**Vision requirement:** Chat messages and generated outreach messages display formatted text (bold, lists, headers, links).

**Current state:** PARTIALLY BUILT.
- `RichText` component at `/Users/michal/git/leadgen-pipeline/frontend/src/components/ui/RichText.tsx` -- supports **bold**, numbered lists, bullet lists, paragraph breaks. Used in message cards.
- Tiptap editor renders markdown in the strategy editor.
- `tiptap-markdown` extension imported in `StrategyEditor.tsx` (line 10).
- Chat messages in `PlaybookChat.tsx` render `msg.content` as plain text inside a `<p>` tag (no markdown parsing).
- Messages page (`MessageCard.tsx`) uses `ReactMarkdown` for rendering (found in search results).

**Gap:**
- Chat messages do not render markdown -- AI responses with formatting (bold, lists, code blocks) appear as raw text.
- Need to add markdown rendering to `PlaybookChat.tsx` (either `ReactMarkdown` or the existing `RichText` component).

**MVP priority:** YES -- AI responses look unprofessional without formatting.

**Effort:** S (add ReactMarkdown or RichText to chat message rendering)

---

### 11. User Auth & Multi-Tenancy

**Vision requirement:** JWT authentication, namespace-based URL routing, tenant isolation, role-based access.

**Current state:** BUILT.
- JWT auth: `api/auth.py` with bcrypt passwords, access + refresh tokens.
- Multi-tenancy: Shared PG schema with `tenant_id` column, `resolve_tenant()` function.
- Namespace routing: `/:namespace/*` URL pattern in `App.tsx`.
- User model: `api/models.py` class `User` with email, password_hash, is_super_admin.
- Tenant roles: `UserTenantRole` model (line 50) with user_id, tenant_id, role.
- Login page: `frontend/src/components/layout/LoginPage.tsx`.
- Admin page: `frontend/src/pages/admin/AdminPage.tsx` with namespace management.
- Auth provider: `frontend/src/hooks/useAuth.ts`.
- Caddy reverse proxy with namespace routing configured.

**Gap:**
- No self-service signup -- accounts are created manually by admins.
- No password reset flow.
- No OAuth (Google/Microsoft) for login (OAuth exists for Google Contacts import but not for auth).
- No invitation system for adding users to a tenant.

**MVP priority:** Self-service signup is REQUIRED for paying customers (GTM strategy Phase 1 requires "free trial" onboarding). Password reset is day-one table stakes.

**Effort:** M (signup + password reset), L (OAuth login, invitation system)

---

### 12. Billing / Payments

**Vision requirement:** EUR 49/149/399 subscription tiers. Stripe integration. Usage-based limits (companies/month, contacts, messages). Annual plans. Partner discounts.

**Current state:** NOT BUILT.
- No Stripe integration anywhere in the codebase (searched for `stripe`, `billing`, `subscription` -- zero hits except a comment about "stripe.com" domain resolution in `playbook_routes.py` line 386).
- No subscription model in the database.
- No usage limits or metering.
- No pricing/billing UI.
- LLM usage logging exists (`llm_usage_log` table, `llm_usage_routes.py`) but is for cost visibility, not billing.

**Gap:** Everything. No billing infrastructure exists.

**MVP priority:** YES -- cannot charge customers without it. However, the GTM strategy says "founder-led onboarding" for first 10 customers, so manual invoicing could work temporarily.

**Effort:** L (Stripe subscription integration), XL (full metering + usage limits + billing UI)

---

### 13. Analytics / Metrics

**Vision requirement:** Track open rates, reply rates, meeting rates, pipeline generated. Performance dashboards. "Not just metrics -- narratives." (Vision: Step 5 "Measure", AI as Performance Analyst)

**Current state:** MINIMALLY BUILT.
- Campaign analytics component: `frontend/src/components/campaign/CampaignAnalytics.tsx` with stat cards (total contacts, generated messages, approved, costs) and progress bars.
- Email send tracking: `EmailSendLog` model with status (queued/sent/delivered/failed) and timestamps.
- Echo Analytics: Route exists as a placeholder page at `/:namespace/echo` with description "Outreach performance dashboard -- conversion funnels, response rates by channel, pipeline velocity."
- LLM costs page: Route exists as a placeholder at `/:namespace/llm-costs`.
- No reply tracking, no meeting tracking, no open rate tracking.
- No webhook for email delivery/open/reply events from Resend.

**Gap:**
- No reply detection (would need email scanning or manual logging).
- No open rate tracking (Resend supports webhooks for this but not integrated).
- No meeting/conversion tracking.
- No funnel visualization.
- No AI-generated performance narratives.
- Echo Analytics is a placeholder page with zero implementation.

**MVP priority:** PARTIAL -- basic campaign stats exist. Full analytics can wait until after first campaigns are sent. But reply tracking is needed to close the loop.

**Effort:** M (Resend webhooks for opens/replies), L (full analytics dashboard), XL (AI narratives)

---

### 14. Evaluate Loop

**Vision requirement:** Track what worked, surface insights. "ROI framing outperformed innovation framing 3:1 for manufacturing CTOs in DACH." AI as Performance Analyst. (Vision: Step 5 "Measure")

**Current state:** NOT BUILT.
- No evaluation framework.
- No A/B test result tracking.
- No per-segment performance analysis.
- No insight generation from campaign results.

**Gap:** Everything. This is a post-launch feature that depends on having real campaign data.

**MVP priority:** NO -- needs real campaign data first. Important for retention and the "compounding intelligence" pitch.

**Effort:** XL

---

### 15. Improve Loop

**Vision requirement:** AI learns from campaign results, refines ICP scoring, adjusts messaging frameworks, reprioritizes channels. "The next campaign starts where the last one left off." (Vision: Step 6 "Learn", AI as Strategist-in-Residence)

**Current state:** NOT BUILT.
- No feedback tracking on AI suggestions (accept/reject/modify).
- No `strategy_feedback` table (PB-033 not built).
- No mechanism to feed campaign results back into the strategy document.
- No iterative ICP refinement.

**Gap:** Everything. This is the core of the "compounding intelligence" moat described in the vision and the investor pitch.

**MVP priority:** NO -- requires the Evaluate loop first. Critical for retention at 20+ customers.

**Effort:** XL

---

### 16. Voice Dialog

**Vision requirement:** "Voice dialog (hands-free GTM)" listed in the roadmap under "Up Next." Users speak to the AI via browser microphone. (PB-031 in backlog)

**Current state:** NOT BUILT.
- No audio/speech/microphone code anywhere in the codebase.
- PB-031 in the implementation backlog is marked as "Future Vision" with effort XL.

**Gap:** Everything.

**MVP priority:** NO -- nice-to-have for demos but not required for first 10 paying customers.

**Effort:** XL

---

### 17. AI Avatar

**Vision requirement:** "AI avatar with presence" listed under "Future" horizon in the roadmap. Animated virtual team member that speaks and gestures. (PB-032 in backlog)

**Current state:** NOT BUILT.
- No avatar, Lottie, or animation code in the frontend (only standard CSS animations for loading spinners and transitions).
- PB-032 depends on PB-031 (Voice Dialog) and is marked effort XL.

**Gap:** Everything.

**MVP priority:** NO -- far-future differentiator.

**Effort:** XL

---

### 18. Cross-User Learning

**Vision requirement:** "Anonymized, aggregated insights from all customers make everyone's AI smarter." (Vision: Intelligence section, "Network Intelligence"). "LinkedIn outperforms cold email 3:1 for DACH B2B SaaS across all customer campaigns."

**Current state:** NOT BUILT.
- No cross-tenant data aggregation.
- No anonymization framework.
- No shared intelligence layer.
- Tenant isolation is strict (every query filters by `tenant_id`).

**Gap:** Everything. Requires significant data volume (many customers, many campaigns) before this is meaningful.

**MVP priority:** NO -- requires 50+ active customers to be useful.

**Effort:** XL

---

### 19. Frustration Detection

**Vision requirement:** "Detects language switching, tone changes, and signs of fatigue. Immediately adapts -- shorter responses, different angle, or a break suggestion." (Vision: Features section, "Frustration Detection")

**Current state:** NOT BUILT.
- No sentiment analysis in the system prompt.
- No language detection logic.
- PB-027 (frustration detection) and PB-028 (language matching) are in the backlog but not implemented.

**Gap:** Everything, but this is a system prompt change, not an architectural gap.

**MVP priority:** NO for frustration detection specifically. YES for language matching (Czech market requires Czech-language support).

**Effort:** S (both are system prompt additions, not code changes)

---

### 20. Landing Page / Marketing Site

**Vision requirement:** GTM strategy specifies "Set up simple landing page (1 page, value prop + demo booking)" as Week 1 action item. "Landing page live" by Week 3.

**Current state:** NOT BUILT (for the product).
- The vision document itself (`docs/vision/index.html`) is a beautifully designed dark-theme page with flywheel animation, journey steps, pricing tiers, and roadmap. This IS effectively a landing page but is positioned as an internal vision doc, not a public-facing marketing page.
- No public signup form.
- No demo booking integration (Calendly, Cal.com, etc.).
- The roadmap HTML at `dashboard/roadmap.html` exists but is an internal tool.
- No domain registered for a product name (the GTM strategy discusses name candidates: Prospero, Signalio, Reachwise, Ampliro).

**Gap:** No public-facing marketing presence. The vision page could be repurposed as a landing page with minor modifications (add signup/demo CTA, connect to a domain).

**MVP priority:** YES -- the GTM strategy says this is Week 3 deliverable. Cannot do founder-led sales without a URL to share.

**Effort:** S (repurpose vision page + add CTA + domain), M (custom landing page with signup)

---

## Summary Matrix

| # | Capability | Status | MVP Required? | Effort | Priority |
|---|-----------|--------|---------------|--------|----------|
| 1 | Onboarding / Self-Research | 80% built | Yes | S | P0 |
| 2 | Strategy Editor | 90% built | Yes | S | P0 |
| 3 | Playbook Chat | 50% built | Yes | M | P0 |
| 4 | Multi-Phase Flow | 0% built | Yes | L | P0 |
| 5 | Contact Selection (Phase 2) | 0% built (data exists) | Yes | M | P1 |
| 6 | Message Generation (Phase 3) | 60% built (standalone) | Yes | M | P1 |
| 7 | Campaign Launch (Phase 4) | 60% built (standalone) | Partial | M | P2 |
| 8 | Enrichment Pipeline | 95% built | Already done | S | -- |
| 9 | Auto-Save / Auto-Extract | 0% built | Yes | S | P0 |
| 10 | Markdown Rendering (Chat) | 0% in chat | Yes | S | P0 |
| 11 | User Auth & Multi-Tenancy | 85% built | Signup + reset needed | M | P0 |
| 12 | Billing / Payments | 0% built | Yes (or manual invoicing) | L | P1 |
| 13 | Analytics / Metrics | 10% built | Partial | M | P2 |
| 14 | Evaluate Loop | 0% built | No | XL | P3 |
| 15 | Improve Loop | 0% built | No | XL | P3 |
| 16 | Voice Dialog | 0% built | No | XL | P4 |
| 17 | AI Avatar | 0% built | No | XL | P4 |
| 18 | Cross-User Learning | 0% built | No | XL | P4 |
| 19 | Frustration Detection | 0% built | Language matching: Yes | S | P2 |
| 20 | Landing Page | 0% built (vision page exists) | Yes | S | P0 |

---

## Critical Path to MVP (First 10 Paying Customers)

Based on the GTM strategy's 90-day execution calendar, the minimum viable product for founder-led sales requires:

### Must-Have (Weeks 1-4)

1. **Auto-save + auto-extract** (S) -- table-stakes UX, prevents data loss
2. **Markdown rendering in chat** (S) -- AI responses look unprofessional without it
3. **Proactive first AI message after research** (S) -- the "wow" moment in onboarding
4. **Multi-phase infrastructure** (L) -- Bucket 1 of the implementation backlog (PB-001 through PB-010). At minimum: DB migration, model update, phase API, phase-aware system prompts, URL routing, PhaseIndicator component.
5. **Landing page with demo CTA** (S) -- repurpose vision page, register domain, add Calendly embed
6. **Self-service signup + password reset** (M) -- cannot onboard trial users without this

### Should-Have (Weeks 5-8)

7. **Contact selection panel** (M) -- Phase 2 of playbook, leveraging existing contacts UI
8. **Playbook-scoped message generation** (M) -- Phase 3, using existing generation engine
9. **Billing via Stripe** (L) -- or manual invoicing for first 5 customers, Stripe for scale
10. **Language matching in chat** (S) -- Czech market requires Czech-language AI

### Nice-to-Have (Weeks 9-12)

11. **Campaign integration from playbook** (M) -- Phase 4 wrapper
12. **Basic reply tracking** (M) -- Resend webhooks
13. **Action items in chat** (M) -- interactive checkboxes
14. **Frustration detection** (S) -- system prompt addition

---

## What the Vision Claims as "Built Today" vs Reality

The vision document's roadmap section (line 2890-2926) lists these as "Shipped / Built Today":

| Vision Claim | Reality |
|-------------|---------|
| Enrichment pipeline (L1 + L2 + Person) | TRUE -- fully built and tested |
| Website scraping in L1 | TRUE -- BeautifulSoup in `l1_enricher.py` |
| Proactive AI chat | PARTIALLY TRUE -- chat works but is reactive, not proactive |
| Auto-save + auto-extract | FALSE -- both require manual button clicks |
| Markdown rendering | PARTIALLY TRUE -- in editor and messages, but NOT in chat |
| PostgreSQL backend + JWT auth | TRUE -- fully built |
| Multi-tenant namespace routing | TRUE -- fully built |

**Accuracy: 4 of 7 claims are fully true, 2 are partially true, 1 is false.** The vision document overstates what's shipped. The "Building Now" items (multi-phase playbook, phase transitions, readiness gates, action items, Tiptap editor, staging + CI) are more accurately described -- the Tiptap editor is actually built, staging + CI are built, and the rest are designed but not implemented.

---

## Architectural Strengths (What's Already Solid)

1. **Data model is production-ready**: 32+ SQLAlchemy models, 32 migrations, PostgreSQL on RDS with proper multi-tenancy.
2. **Enrichment engine is best-in-class for cost**: $0.015/company for deep research -- 100x cheaper than manual, 30x cheaper than vendors.
3. **API architecture is clean**: Flask blueprints, proper auth middleware, tenant isolation, version-locked document editing.
4. **Frontend is modern**: React + TypeScript + Vite + TanStack Query + Tailwind CSS. Good patterns with hooks and query invalidation.
5. **Campaign infrastructure works end-to-end**: Generation -> review -> approve -> send (email via Resend, LinkedIn via queue).
6. **Deployment is automated**: Docker, Caddy reverse proxy, staging + production environments, deploy scripts.
7. **Testing exists**: Unit tests (pytest), E2E tests (Playwright), CI pipeline (GitHub Actions).

---

## Biggest Risks

1. **Multi-phase playbook is the critical path** and has zero implementation. This is 10+ items of work (Bucket 1 alone) before the demo shows anything beyond "strategy editor + chat."
2. **No self-service signup** means every trial requires founder intervention to create accounts -- the GTM strategy plans for 10-15 concurrent trials by Week 8.
3. **No billing** means revenue collection requires manual invoicing. Acceptable for 3-5 customers, unscalable at 10+.
4. **The Evaluate/Improve loops are the moat** but have zero implementation. The investor pitch relies on "compounding intelligence" but the product currently has no learning mechanism.
5. **Contact discovery is missing** -- the enrichment pipeline enriches contacts you already have, but the ICP-to-contacts sourcing ("find me companies matching this profile") requires external data sources (Apollo, LinkedIn Sales Nav API, or similar) that are not integrated.
