# MVP Backlog -- First 10 Paying Customers

**Date:** 2026-02-22
**Purpose:** Comprehensive, sequenced task list for shipping the MVP that converts the first 10 paying customers.
**Inputs:** Gap Analysis, GTM Strategy, Vision Microsite, Business Model Analysis, Playbook Implementation Backlog (PB-001..PB-034), Main BACKLOG.md

---

## Executive Summary

### Counts by Priority

| Priority | Tasks | Effort Points | Estimated Weeks (solo) |
|----------|-------|---------------|----------------------|
| **Must Have** (MVP-required) | 30 | 114 pts | ~13 weeks |
| **Should Have** (by customer 5) | 7 | 34 pts | ~4 weeks |
| **Could Have** (by customer 10) | 8 | 28 pts | ~3 weeks |
| **Won't Have** (post-MVP) | 8 | — | deferred |
| **Total** | 53 | 176 pts | ~20 weeks |

### Effort Scale

| Size | Solo Dev Time | Points |
|------|--------------|--------|
| S | 1-2 days | 2 |
| M | 3-5 days | 5 |
| L | 1-2 weeks | 10 |
| XL | 2-4 weeks | 20 |

### Estimated Total Effort (Must + Should)

- **Must Have:** 114 points (~13 weeks at ~9 pts/week)
- **Should Have:** 34 points (~4 weeks)
- **Could Have:** 28 points (~3 weeks)
- **Must + Should (paying customer ready):** 148 points (~17 weeks solo, ~9 weeks with 2 developers)

### Critical Path (Longest Dependency Chain)

```
PB-001 (DB migration, S)
  → PB-002 (Model update, S)
    → PB-005 (Phase instructions, M)
      → PB-004 (Chat phase param, S)
    → PB-003 (Phase API, M)
      → PB-006 (Frontend route, S)
        → PB-007 (PhaseIndicator, M)
          → PB-008 (PlaybookTopBar, M)
            → PB-009 (StrategyPanel, M)
              → PB-011 (ContactSelectionPanel, L)
                → PB-013 (Phase 1→2 gate, S)
                  → PB-015 (Generate Messages button, M)
                    → PB-016 (MessageReviewPanel, L)
                      → PB-020 (Launch Campaign button, M)
```

**Critical path length:** ~14 items, ~10 weeks. This is the multi-phase playbook flow and it gates the entire product demo.

### Risk Factors

1. **Multi-phase playbook is zero-built** -- 10 items of sequential infrastructure before any phase beyond Strategy works. This is a 4-6 week chain with no shortcuts.
2. **Stripe integration has never been attempted** -- no billing code exists. If this blocks, manual invoicing is the fallback for customers 1-5.
3. **Self-service signup is missing** -- every trial currently requires manual account creation. GTM strategy needs 10-15 concurrent trials by Week 8.
4. **No landing page** -- cannot run founder-led sales without a URL to share. Low effort but often deprioritized.
5. **Chat markdown rendering** -- AI responses currently look like raw text. Small fix but high impact on perceived quality.
6. **Phase prompts need real-world tuning** -- PHASE_INSTRUCTIONS text is specified but untested with real users. Expect 2-3 iterations.

---

## MVP Boundary Definitions

### Demo-Ready (first prospect demo)

The product must show the complete journey in a guided demo, even if some steps are manual:

- [x] Onboarding: enter domain, AI researches company, seeds strategy template
- [ ] Strategy editor with AI chat (proactive first message, markdown rendering)
- [ ] Multi-phase stepper UI showing Strategy -> Contacts -> Messages -> Campaign
- [ ] Phase transitions work (forward gated, backward free)
- [ ] Contact selection panel with ICP-derived filters
- [ ] Message generation triggered from playbook
- [ ] Landing page with demo booking CTA

### First Paying Customer Ready

Everything above, plus:

- [ ] Self-service signup (email + password)
- [ ] Password reset flow
- [ ] Auto-save + auto-extract (no data loss risk)
- [ ] Language matching in chat (Czech market)
- [ ] Message review panel in playbook flow
- [ ] Billing (Stripe checkout or manual invoicing)

### By Customer 5

- [ ] Stripe subscription integration (replaces manual invoicing)
- [ ] Usage metering (companies/contacts/messages per month)
- [ ] Basic reply tracking (Resend webhooks)
- [ ] Action items in chat
- [ ] Phase transition cards in chat

### By Customer 10

- [ ] Campaign phase full integration
- [ ] Frustration detection in chat
- [ ] Referral tracking
- [ ] Basic analytics dashboard (campaign stats)
- [ ] German language UI (i18n framework)

---

## Workstream 1: Playbook Multi-Phase Flow

> **Vision pillar:** Try phase (Strategy + Contacts) and Run phase (Messages + Campaign)
> **GTM milestone:** Demo-ready by Week 2, full flow by Week 4

This is the critical path. The multi-phase playbook is the product's core differentiator and has zero implementation today.

### MVP-001: DB migration -- add `phase` and `playbook_selections` to strategy_documents
**Incorporates:** PB-001
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** Add `phase` column (VARCHAR, default `'strategy'`) and `playbook_selections` column (JSONB, default `'{}'`) to `strategy_documents` table.

**Acceptance Criteria:**
- Given the migration is applied, when I query strategy_documents, then every row has `phase='strategy'` and `playbook_selections='{}'`
- Given a new row is inserted without specifying phase, when I read it back, then phase is 'strategy'
- Given playbook_selections is set to nested JSON, when I query individual keys via JSONB operators, then the nested structure is accessible

**Files to modify:**
- Create: `migrations/033_playbook_phases.sql`

---

### MVP-002: Model update -- StrategyDocument gains `phase` and `playbook_selections`
**Incorporates:** PB-002
**Priority:** Must Have | **Effort:** S | **Dependencies:** MVP-001

**Description:** Add `phase` and `playbook_selections` columns to the `StrategyDocument` SQLAlchemy model. Update `to_dict()`. Define `PLAYBOOK_PHASES` constant.

**Acceptance Criteria:**
- Given a StrategyDocument created without phase, when serialized, then `phase='strategy'` and `playbook_selections={}`
- Given `phase='contacts'`, when serialized, then `to_dict()["phase"]` equals `'contacts'`

**Files to modify:**
- `api/models.py` (StrategyDocument class)
- Create: `tests/unit/test_playbook_phases.py`

---

### MVP-003: Phase API -- `PUT /api/playbook/phase` with validation gates
**Incorporates:** PB-003
**Priority:** Must Have | **Effort:** M | **Dependencies:** MVP-002

**Description:** New endpoint to advance or rewind the playbook phase. Forward transitions are gated (strategy->contacts requires extracted ICP; contacts->messages requires selected contacts; messages->campaign requires generated messages). Backward navigation always allowed.

**Acceptance Criteria:**
- Given a document in strategy phase with empty extracted_data, when I PUT `{"phase":"contacts"}`, then I get 422
- Given a document with valid extracted_data.icp, when I PUT `{"phase":"contacts"}`, then the phase updates to contacts (200)
- Given backward navigation, when I PUT any earlier phase, then it succeeds (200)
- Given an invalid phase value, when I PUT it, then I get 400

**Files to modify:**
- `api/routes/playbook_routes.py`
- `tests/unit/test_playbook_phases.py`

---

### MVP-004: Phase-aware system prompt -- `PHASE_INSTRUCTIONS` dict
**Incorporates:** PB-005
**Priority:** Must Have | **Effort:** M | **Dependencies:** MVP-002

**Description:** Add PHASE_INSTRUCTIONS dictionary to `playbook_service.py` mapping each phase to additional system prompt text. Modify `build_system_prompt()` to accept optional `phase` parameter and append phase-specific instructions with interpolated context (ICP summary, contact count).

**Acceptance Criteria:**
- Given build_system_prompt called with phase="strategy", when I inspect output, then it contains "STRATEGY phase"
- Given phase="contacts" with ICP extracted data, when prompt is built, then it contains formatted ICP summary
- Given phase="messages" with 5 selected contacts, when prompt is built, then it says "Selected contacts: 5"

**Files to modify:**
- `api/services/playbook_service.py`
- Create: `tests/unit/test_playbook_phase_prompts.py`

---

### MVP-005: Chat endpoint gains `phase` parameter
**Incorporates:** PB-004
**Priority:** Must Have | **Effort:** S | **Dependencies:** MVP-004

**Description:** Extend `POST /api/playbook/chat` to accept optional `phase` in request body. Pass it to `build_system_prompt()`. Does not change document's stored phase.

**Acceptance Criteria:**
- Given chat request with `{"message":"...","phase":"contacts"}`, when system prompt is built, then it includes contacts-phase instructions
- Given chat request without phase, when processed, then it defaults to document's stored phase
- Given document in strategy phase but request sends phase:"contacts", when processed, then document's phase field is unchanged

**Files to modify:**
- `api/routes/playbook_routes.py`

---

### MVP-006: Frontend route -- `playbook/:phase` with redirect
**Incorporates:** PB-006
**Priority:** Must Have | **Effort:** S | **Dependencies:** MVP-003

**Description:** Update React router to use `playbook/:phase?`. Redirect `/playbook` to `/playbook/strategy`. PlaybookPage reads phase from URL.

**Acceptance Criteria:**
- Given user navigates to `/:namespace/playbook`, then they are redirected to `/:namespace/playbook/strategy`
- Given user navigates to `/:namespace/playbook/contacts`, then PlaybookPage receives phase="contacts"

**Files to modify:**
- `frontend/src/App.tsx`
- `frontend/src/pages/playbook/PlaybookPage.tsx`

---

### MVP-007: PhaseIndicator component
**Incorporates:** PB-007
**Priority:** Must Have | **Effort:** M | **Dependencies:** MVP-006

**Description:** Horizontal stepper showing four phases (Strategy, Contacts, Messages, Campaign) with active/completed/locked/unlocked states. Clicking completed or unlocked phases navigates.

**Acceptance Criteria:**
- Given currentPhase="strategy", when rendered, then Strategy step is active, others dimmed
- Given currentPhase="contacts", when rendered, then Strategy has checkmark, Contacts is active
- Given canAdvanceTo.messages=false, when user clicks Messages, then nothing happens
- Given canAdvanceTo.contacts=true, when user clicks Contacts, then onPhaseChange("contacts") fires

**Files to modify:**
- Create: `frontend/src/components/playbook/PhaseIndicator.tsx`

---

### MVP-008: PlaybookTopBar component
**Incorporates:** PB-008
**Priority:** Must Have | **Effort:** M | **Dependencies:** MVP-007

**Description:** Extract top bar from PlaybookPage. Houses PhaseIndicator (centered), page title, and phase-specific action buttons (Save/Extract for Strategy, Generate for Contacts, Launch for Messages).

**Acceptance Criteria:**
- Given currentPhase="strategy", when rendered, then Save and Extract buttons visible
- Given currentPhase="contacts", when rendered, then "Generate Messages" button appears
- Given isDirty=true, when rendered, then unsaved indicator visible

**Files to modify:**
- Create: `frontend/src/components/playbook/PlaybookTopBar.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

---

### MVP-009: StrategyPanel extraction -- refactor PlaybookPage
**Incorporates:** PB-009
**Priority:** Must Have | **Effort:** M | **Dependencies:** MVP-008

**Description:** Extract editor + state management from PlaybookPage into standalone StrategyPanel. PlaybookPage becomes a phase router showing StrategyPanel for strategy phase, placeholders for others. Pure refactor, no behavior changes.

**Acceptance Criteria:**
- Given the refactor is complete, when I visit /playbook/strategy, then editor and chat work exactly as before
- Given I navigate to /playbook/contacts, then editor is replaced by a placeholder panel
- Given chat is visible in all phases, then it remains on the right side regardless of phase

**Files to modify:**
- Create: `frontend/src/components/playbook/StrategyPanel.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

---

### MVP-010: Phase guard -- forward navigation blocked until unlocked
**Incorporates:** PB-010
**Priority:** Must Have | **Effort:** S | **Dependencies:** MVP-003, MVP-007

**Description:** Client-side validation computing `canAdvanceTo` based on document state. Server-side validation via PUT /api/playbook/phase. Backward always allowed.

**Acceptance Criteria:**
- Given extracted_data is empty, when PhaseIndicator renders, then Contacts step is locked
- Given extracted_data.icp exists, when PhaseIndicator renders, then Contacts step is unlocked
- Given user clicks locked step, then phase does not change
- Given PUT with invalid transition, then 422 error shown in toast

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx`
- `frontend/src/api/queries/usePlaybook.ts`

---

### MVP-011: ContactSelectionPanel with ICP-derived filter pre-population
**Incorporates:** PB-011
**Priority:** Must Have | **Effort:** L | **Dependencies:** MVP-009, MVP-010

**Description:** New panel shown when phase="contacts". Filterable, selectable contact list. Pre-populates filters from extracted_data.icp. Uses existing contacts API. Includes search, filter dropdowns, select-all/none toggle, count badge.

**Acceptance Criteria:**
- Given phase="contacts", when panel renders, then contacts are displayed in a filterable list
- Given extracted_data.icp has industries=["SaaS"], when panel loads, then industry filter pre-selects SaaS
- Given user selects 5 contacts, when they click next, then selections are persisted

**Files to modify:**
- Create: `frontend/src/components/playbook/ContactSelectionPanel.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

---

### MVP-012: API -- store selected contact IDs in playbook_selections
**Incorporates:** PB-012
**Priority:** Must Have | **Effort:** S | **Dependencies:** MVP-002

**Description:** `PATCH /api/playbook/selections` endpoint merging partial updates into playbook_selections JSONB. Stores `{"contacts":{"selected_ids":[...],"filters":{...}}}`.

**Acceptance Criteria:**
- Given a PATCH with `{"contacts":{"selected_ids":["id1","id2"]}}`, when I read the document, then playbook_selections.contacts.selected_ids has 2 entries
- Given a subsequent PATCH with messages config, when I read the document, then both contacts and messages keys exist (merge, not replace)

**Files to modify:**
- `api/routes/playbook_routes.py`
- `tests/unit/test_playbook_phases.py`

---

### MVP-013: Phase 1->2 readiness gate
**Incorporates:** PB-013
**Priority:** Must Have | **Effort:** S | **Dependencies:** MVP-010, MVP-011

**Description:** When user clicks "Next: Select Contacts" or Contacts step, validate extracted_data.icp has at least industries and one other field. Auto-trigger extraction if not run. Toast on failure.

**Acceptance Criteria:**
- Given no extraction has been run, when user clicks Contacts step, then extraction is triggered automatically
- Given extraction fails, when toast appears, then it shows an actionable error message
- Given ICP data exists, when user clicks Contacts step, then transition succeeds

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx`
- `frontend/src/components/playbook/PlaybookTopBar.tsx`

---

### MVP-014: Generate Messages button -- Phase 2->3 transition
**Incorporates:** PB-015
**Priority:** Must Have | **Effort:** M | **Dependencies:** MVP-012, MVP-013

**Description:** Action button in PlaybookTopBar during contacts phase. Validates contacts are selected, stores them, transitions to messages phase, triggers message generation for selected contacts.

**Acceptance Criteria:**
- Given 5 contacts selected, when user clicks "Generate Messages", then selections are persisted and phase transitions to messages
- Given 0 contacts selected, when user clicks "Generate Messages", then a validation error is shown
- Given generation starts, when phase transitions, then a progress indicator appears

**Files to modify:**
- `frontend/src/components/playbook/PlaybookTopBar.tsx`
- `frontend/src/pages/playbook/PlaybookPage.tsx`

---

### MVP-015: MessageReviewPanel component
**Incorporates:** PB-016
**Priority:** Must Have | **Effort:** L | **Dependencies:** MVP-014

**Description:** Panel for phase="messages". Adapted from existing MessagesPage/MessageCard scoped to playbook-selected contacts. Shows messages grouped by contact with approve/edit/regenerate. Reuses `PATCH /api/messages/:id`.

**Acceptance Criteria:**
- Given messages have been generated for 5 contacts, when messages phase loads, then messages are displayed grouped by contact
- Given user approves a message, when action completes, then message status changes to approved
- Given user clicks regenerate, when generation completes, then new version replaces old

**Files to modify:**
- Create: `frontend/src/components/playbook/MessageReviewPanel.tsx`
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

---

### MVP-016: Message generation trigger -- on Phase 3 entry
**Incorporates:** PB-017
**Priority:** Must Have | **Effort:** L | **Dependencies:** MVP-012, MVP-015

**Description:** When user enters messages phase for the first time (no messages for selected contacts), auto-trigger message generation using strategy's messaging framework + personas + selected contacts. Uses existing campaign generation service. Shows progress.

**Acceptance Criteria:**
- Given first entry to messages phase with no existing messages, when phase loads, then generation auto-starts
- Given generation in progress, when panel renders, then progress bar shows completion percentage
- Given messages already exist for selected contacts, when re-entering messages phase, then no new generation triggers

**Files to modify:**
- `api/routes/playbook_routes.py` (or new endpoint)
- Create: `api/services/playbook_message_service.py`

---

### MVP-017: Phase 2->3 transition gate
**Incorporates:** PB-018
**Priority:** Must Have | **Effort:** S | **Dependencies:** MVP-012, MVP-014

**Description:** Before transitioning contacts->messages, validate at least 1 contact selected (client + server). Persist selections via PATCH before triggering transition.

**Acceptance Criteria:**
- Given 0 contacts selected, when transition is attempted, then it is blocked with an error
- Given contacts are selected, when transition fires, then selections are saved before phase changes

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx`

---

### MVP-018: Launch Campaign button -- Phase 3->4 transition
**Incorporates:** PB-020
**Priority:** Should Have | **Effort:** M | **Dependencies:** MVP-015, MVP-017

**Description:** Action button in PlaybookTopBar during messages phase. Validates messages approved, transitions to campaign phase, creates or links to campaign.

**Acceptance Criteria:**
- Given all messages approved, when user clicks "Launch Campaign", then a campaign is created with the selected contacts and approved messages
- Given some messages not reviewed, when button is clicked, then validation warning is shown

**Files to modify:**
- `frontend/src/components/playbook/PlaybookTopBar.tsx`
- `frontend/src/pages/playbook/PlaybookPage.tsx`

---

## Workstream 2: Chat & Editor Polish

> **Vision pillar:** Try phase -- the "AI as strategist" experience
> **GTM milestone:** Demo-ready quality by Week 2

### MVP-019: Auto-save with debounce (2.5s)
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** Replace manual Save button with automatic debounced save. Editor changes trigger a 2.5-second debounce timer; save fires after inactivity. Remove Save button, add "Saving..." / "Saved" status indicator.

**Acceptance Criteria:**
- Given user edits the strategy document, when they stop typing for 2.5 seconds, then the document auto-saves
- Given auto-save succeeds, when the status indicator updates, then it shows "Saved" with a checkmark
- Given auto-save encounters a 409 conflict, when the error is caught, then the user sees a conflict notification

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx`
- `frontend/src/components/playbook/StrategyEditor.tsx`

---

### MVP-020: Auto-extract after save
**Priority:** Must Have | **Effort:** S | **Dependencies:** MVP-019

**Description:** After each successful auto-save, silently trigger extraction (`POST /api/playbook/extract`) in the background. No manual Extract button. Extraction failures are silently retried once; persistent failures show a subtle warning.

**Acceptance Criteria:**
- Given auto-save completes, when the background extraction runs, then extracted_data is updated silently
- Given extraction fails, when retry fails, then a subtle warning appears (not a blocking error)
- Given the Extract button existed before, when this is deployed, then the button is removed

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx`
- `frontend/src/api/queries/usePlaybook.ts`

---

### MVP-021: Markdown rendering in chat messages
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** Use ReactMarkdown (already available in the project via MessageCard) or the existing RichText component to render AI responses in PlaybookChat. Currently chat messages render as plain text inside `<p>` tags.

**Acceptance Criteria:**
- Given AI responds with `**bold**` text, when the message renders, then bold formatting is applied
- Given AI responds with bullet lists, when the message renders, then proper list formatting is displayed
- Given AI responds with numbered lists and headers, when rendered, then they display correctly

**Files to modify:**
- `frontend/src/components/playbook/PlaybookChat.tsx`

---

### MVP-022: Proactive first AI message after onboarding research
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** When onboarding research completes (L1+L2 enrichment finishes), auto-send a first AI message summarizing findings and asking 2-3 targeted questions about the user's GTM goals. Currently the chat starts empty after research.

**Acceptance Criteria:**
- Given onboarding research finishes, when the user lands in the strategy editor, then the chat already has one AI message
- Given the first AI message, when the user reads it, then it references specific findings from the enrichment (industry, competitors, signals)
- Given the first message, when displayed, then it asks 2-3 concrete questions (not generic "how can I help?")

**Files to modify:**
- `api/routes/playbook_routes.py` (self-research completion handler)
- `api/services/playbook_service.py`

---

### MVP-023: Language matching in chat
**Incorporates:** PB-028
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** Detect user's language from chat messages (simple heuristic: if last 3 messages are non-English, switch). Add system prompt instruction: "Respond in the same language the user writes in." Critical for Czech market.

**Acceptance Criteria:**
- Given user writes 3 messages in Czech, when AI responds, then response is in Czech
- Given user switches to English, when AI responds after 3 English messages, then it switches to English
- Given mixed-language messages, when AI responds, then it uses the most recent predominant language

**Files to modify:**
- `api/services/playbook_service.py`
- `api/routes/playbook_routes.py`

---

## Workstream 3: Auth & Billing

> **Vision pillar:** Self-service onboarding (Try phase entry point)
> **GTM milestone:** Trial-ready by Week 3, billing by Week 6

### MVP-024: Self-service signup (email + password)
**Priority:** Must Have | **Effort:** M | **Dependencies:** None

**Description:** Public registration form. Creates user account + tenant + namespace. Email confirmation (via Resend transactional email). Redirects to onboarding flow after confirmation.

**Acceptance Criteria:**
- Given a new user visits /signup, when they submit email + password + company name, then account is created
- Given signup is successful, when the user confirms their email, then they can log in
- Given a duplicate email, when signup is attempted, then a clear error message is shown
- Given signup completes, when user logs in, then they land in the onboarding flow

**Files to modify:**
- Create: `api/routes/signup_routes.py`
- Create: `frontend/src/components/layout/SignupPage.tsx`
- Modify: `frontend/src/App.tsx` (add /signup route)
- Modify: `api/auth.py` (add signup logic)

---

### MVP-025: Password reset flow
**Priority:** Must Have | **Effort:** M | **Dependencies:** MVP-024

**Description:** "Forgot password" link on login page. Sends reset email with time-limited token (via Resend). Reset page accepts new password. Token expires after 1 hour.

**Acceptance Criteria:**
- Given user clicks "Forgot password", when they submit their email, then a reset email is sent
- Given user clicks the reset link within 1 hour, when they set a new password, then it succeeds
- Given a reset link older than 1 hour, when user clicks it, then they see "link expired" message
- Given a user with no account, when they request a reset, then no email is sent (silent failure for security)

**Files to modify:**
- Create: `api/routes/password_reset_routes.py`
- Create: `frontend/src/components/layout/PasswordResetPage.tsx`
- Create: `frontend/src/components/layout/ForgotPasswordPage.tsx`
- Modify: `frontend/src/App.tsx`

---

### MVP-026: Stripe Checkout integration (subscription)
**Priority:** Should Have | **Effort:** L | **Dependencies:** MVP-024

**Description:** Stripe Checkout session for subscription signup. Three tiers (EUR 49/149/399). Webhook handler for subscription lifecycle events (created, updated, cancelled, payment_failed). Subscription status stored on tenant. Usage limits enforced based on tier. **Fallback:** manual invoicing for first 5 customers.

**Acceptance Criteria:**
- Given user selects Growth tier, when they click Subscribe, then they are redirected to Stripe Checkout
- Given payment succeeds, when webhook fires, then tenant's subscription_status is set to active
- Given payment fails, when webhook fires, then tenant is notified and access is restricted after grace period
- Given user cancels subscription, when billing period ends, then access is restricted

**Files to modify:**
- Create: `api/routes/billing_routes.py`
- Create: `api/services/billing_service.py`
- Create: `frontend/src/pages/billing/BillingPage.tsx`
- Create: `migrations/034_billing.sql`
- Modify: `api/models.py` (add Subscription model)

---

### MVP-027: Usage metering -- tier limits enforcement
**Priority:** Should Have | **Effort:** M | **Dependencies:** MVP-026

**Description:** Track companies enriched, contacts used, and messages generated per tenant per month. Enforce tier limits (Starter: 50/100/200, Growth: 200/500/1000, Scale: 500/1500/3000). Show usage progress bars in settings. Block actions when limits reached.

**Acceptance Criteria:**
- Given tenant on Growth tier has enriched 200 companies, when they attempt to enrich another, then they see an upgrade prompt
- Given tenant's usage resets monthly, when a new month starts, then counters reset to zero
- Given usage is at 80% of limit, when user is on any page, then a subtle warning appears

**Files to modify:**
- Create: `api/services/usage_service.py`
- Create: `api/routes/usage_routes.py`
- Create: `migrations/035_usage_metering.sql`
- Modify: `api/models.py` (add UsageRecord model)
- Create: `frontend/src/components/settings/UsageDisplay.tsx`

---

### MVP-028: Pricing page with tier comparison
**Priority:** Should Have | **Effort:** S | **Dependencies:** MVP-026

**Description:** In-app pricing page showing three tiers with feature comparison. Links to Stripe Checkout for each tier. Shows current plan if subscribed.

**Acceptance Criteria:**
- Given an unauthenticated user visits /pricing, then three tiers are displayed with features and prices
- Given a logged-in user on Starter, when they view pricing, then Starter shows "Current Plan" and others show "Upgrade"
- Given user clicks Upgrade, when redirected, then they land on Stripe Checkout with the correct tier

**Files to modify:**
- Create: `frontend/src/pages/billing/PricingPage.tsx`
- Modify: `frontend/src/App.tsx`

---

## Workstream 4: Landing Page & Marketing

> **Vision pillar:** Product awareness and lead generation
> **GTM milestone:** Landing page live by Week 3

### MVP-029: Landing page with demo CTA
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** Repurpose the existing vision page (`docs/vision/index.html`) as a public landing page. Add a prominent "Book a Demo" CTA linking to Calendly. Add email capture form for waitlist. Register domain (prospero.ai or signalio.ai). Deploy to a separate static hosting (Vercel/Cloudflare Pages or Caddy subdomain).

**Acceptance Criteria:**
- Given a visitor arrives at the product domain, when the page loads, then they see a clear value proposition and "Book a Demo" CTA
- Given visitor clicks "Book a Demo", when Calendly opens, then they can schedule a 25-minute call
- Given visitor enters their email, when they submit, then they are added to a waitlist
- Given the page is live, when shared on LinkedIn, then link preview shows correct title + description

**Files to modify:**
- Modify: `docs/vision/index.html` (add CTA, demo booking embed, email capture)
- Create: DNS configuration for product domain

---

### MVP-030: Domain registration + DNS setup
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** Register the chosen product domain (prospero.ai, signalio.ai, or ampliro.com). Set up DNS to point to landing page hosting. Configure SSL.

**Acceptance Criteria:**
- Given the domain is registered, when I visit it, then the landing page loads with HTTPS
- Given social sharing, when the URL is pasted, then it resolves correctly

**Files to modify:**
- DNS configuration (external)

---

## Workstream 5: Enrichment & Data

> **Vision pillar:** Data intelligence layer
> **GTM milestone:** Already operational; polish for customer-facing use

### MVP-031: Onboarding research progress -- show what AI is learning
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** During onboarding research (L1+L2 enrichment), show progress messages describing what the AI is doing: "Analyzing your website...", "Researching your market position...", "Identifying competitors...", "Building strategic signals...". Currently shows just a spinner with "L1 enrichment" / "L2 enrichment" labels.

**Acceptance Criteria:**
- Given research is in L1 phase, when the progress UI renders, then it shows descriptive messages like "Analyzing your website"
- Given research transitions from L1 to L2, when the status updates, then messages change to L2-specific descriptions
- Given research completes, when all stages finish, then user is transitioned to the editor with the proactive first message

**Files to modify:**
- `frontend/src/components/playbook/PlaybookOnboarding.tsx`
- `frontend/src/hooks/useResearchStatus.ts` (or equivalent)

---

### MVP-032: Strategy-informed message generation prompts
**Priority:** Must Have | **Effort:** M | **Dependencies:** MVP-016

**Description:** Feed extracted strategy data (personas, messaging framework, value props, tone) into the message generation prompt when generating from the playbook context. Currently `build_generation_prompt()` does not use playbook data.

**Acceptance Criteria:**
- Given a strategy with personas defined, when messages are generated from the playbook, then the prompt includes persona details
- Given a messaging framework with specific angles, when messages are generated, then the prompt references those angles
- Given tone preferences in the strategy, when messages are generated, then the prompt enforces the specified tone

**Files to modify:**
- `api/services/generation_prompts.py`
- `api/services/playbook_message_service.py` (from MVP-016)

---

## Workstream 6: Infrastructure & DevOps

> **Vision pillar:** Operational reliability
> **GTM milestone:** Staging pipeline operational, production stable

### MVP-033: Email transactional setup (Resend)
**Priority:** Must Have | **Effort:** M | **Dependencies:** None

**Description:** Configure Resend for transactional emails: signup confirmation, password reset, trial notifications. Set up sending domain and templates. This is a prerequisite for MVP-024 (signup) and MVP-025 (password reset).

**Acceptance Criteria:**
- Given a user signs up, when confirmation email is sent, then it arrives within 30 seconds
- Given a password reset is requested, when email is sent, then it arrives with a valid reset link
- Given emails are sent, when checked in Resend dashboard, then delivery status is tracked

**Files to modify:**
- Create: `api/services/email_service.py`
- Create: `api/templates/email/` (confirmation, reset, trial)

---

### MVP-034: Production environment health checks
**Priority:** Must Have | **Effort:** S | **Dependencies:** None

**Description:** Add `/api/health/deep` endpoint that checks DB connectivity, Redis (if used), and external service reachability (Anthropic API, Perplexity API). Used for monitoring and container health checks.

**Acceptance Criteria:**
- Given all services are healthy, when `/api/health/deep` is called, then it returns 200 with all checks passing
- Given DB is unreachable, when endpoint is called, then it returns 503 with the specific failing check
- Given Docker container uses this as healthcheck, when the API is unhealthy, then Docker restarts the container

**Files to modify:**
- Modify: `api/routes/health_routes.py`

---

### MVP-035: Error tracking integration (Sentry)
**Priority:** Should Have | **Effort:** S | **Dependencies:** None

**Description:** Add Sentry SDK to Flask API and React frontend. Captures unhandled exceptions with context (user, tenant, phase). Essential for debugging customer-reported issues during founder-led sales.

**Acceptance Criteria:**
- Given an unhandled exception in the API, when it occurs, then it appears in Sentry with user + tenant context
- Given a React crash, when it occurs, then the error boundary reports it to Sentry
- Given a Sentry alert, when reviewed, then it includes enough context to reproduce

**Files to modify:**
- Modify: `api/__init__.py` (Flask app factory)
- Modify: `frontend/src/main.tsx`
- Add: `sentry-sdk` to requirements.txt, `@sentry/react` to package.json

---

## Workstream 7: Chat Enhancements (Post-Core)

> **Vision pillar:** AI intelligence and interaction quality
> **GTM milestone:** Retention features for customer 5+

### MVP-036: Action items -- parse `- [ ]` from AI responses
**Incorporates:** PB-021
**Priority:** Could Have | **Effort:** M | **Dependencies:** None

**Description:** Parse markdown task items from AI responses, store as structured action items in chat message metadata JSONB.

**Acceptance Criteria:**
- Given AI responds with `- [ ] Define your ICP`, when parsed, then action_items array in metadata contains the item
- Given multiple task items in one response, when parsed, then all items are captured

**Files to modify:**
- `api/routes/playbook_routes.py`
- `api/services/playbook_service.py`

---

### MVP-037: ActionItemList component with interactive checkboxes
**Incorporates:** PB-022
**Priority:** Could Have | **Effort:** M | **Dependencies:** MVP-036

**Description:** React component rendering action items as an interactive checklist. Toggle state via API.

**Acceptance Criteria:**
- Given action items exist in a message, when rendered, then checkboxes appear with item text
- Given user checks an item, when API call succeeds, then checkbox state persists across page refresh

**Files to modify:**
- Create: `frontend/src/components/playbook/ActionItemList.tsx`
- Modify: `frontend/src/components/playbook/PlaybookChat.tsx`

---

### MVP-038: API for toggling action items
**Incorporates:** PB-023
**Priority:** Could Have | **Effort:** S | **Dependencies:** MVP-036

**Description:** `PATCH /api/playbook/chat/:id/actions` endpoint updating metadata.action_items[N].checked.

**Acceptance Criteria:**
- Given action item at index 0 is unchecked, when PATCH is called with index 0 and checked=true, then it persists
- Given message belongs to a different tenant, when PATCH is called, then 403 is returned

**Files to modify:**
- `api/routes/playbook_routes.py`
- `tests/unit/test_playbook_api.py`

---

### MVP-039: PhaseTransitionCard in chat
**Incorporates:** PB-024
**Priority:** Could Have | **Effort:** M | **Dependencies:** MVP-004, MVP-010

**Description:** Special card rendered in chat when AI suggests advancing to next phase. Shows CTA button like "Ready for Contacts Phase ->" triggering phase transition.

**Acceptance Criteria:**
- Given AI response contains a readiness suggestion, when rendered, then a transition card with CTA button appears
- Given user clicks the CTA, when transition is valid, then phase advances

**Files to modify:**
- Create: `frontend/src/components/playbook/PhaseTransitionCard.tsx`
- Modify: `frontend/src/components/playbook/PlaybookChat.tsx`

---

### MVP-040: PhaseDivider in chat history
**Incorporates:** PB-025
**Priority:** Could Have | **Effort:** S | **Dependencies:** MVP-003

**Description:** Visual separator between phases in chat. System message inserted on phase change.

**Acceptance Criteria:**
- Given phase changes from strategy to contacts, when chat renders, then a divider shows "Strategy Phase Complete"

**Files to modify:**
- Create: `frontend/src/components/playbook/PhaseDivider.tsx`
- Modify: `frontend/src/components/playbook/PlaybookChat.tsx`
- Modify: `api/routes/playbook_routes.py`

---

### MVP-041: Topic/intent detection in system prompt
**Incorporates:** PB-026
**Priority:** Could Have | **Effort:** S | **Dependencies:** MVP-004

**Description:** System prompt detects when user asks about a different phase than current. AI acknowledges but redirects.

**Acceptance Criteria:**
- Given user in strategy phase asks about messaging, when AI responds, then it acknowledges but redirects to strategy

**Files to modify:**
- `api/services/playbook_service.py`

---

### MVP-042: Frustration/sentiment detection
**Incorporates:** PB-027
**Priority:** Could Have | **Effort:** S | **Dependencies:** None

**Description:** System prompt instructions for detecting frustration and responding with empathy and concrete help.

**Acceptance Criteria:**
- Given user sends short frustrated replies, when AI detects the pattern, then it adapts with shorter, more direct responses

**Files to modify:**
- `api/services/playbook_service.py`

---

### MVP-043: Strategy readiness assessment
**Incorporates:** PB-029
**Priority:** Could Have | **Effort:** M | **Dependencies:** MVP-004

**Description:** AI evaluates strategy document readiness. Periodically suggests moving to next phase when criteria are met. Readiness score computed server-side.

**Acceptance Criteria:**
- Given ICP has disqualifiers and personas have title patterns, when AI assesses, then it suggests moving to Contacts phase
- Given strategy is sparse, when AI assesses, then it asks targeted questions to fill gaps

**Files to modify:**
- `api/services/playbook_service.py`
- `api/routes/playbook_routes.py`

---

## Workstream 8: Analytics & Tracking (Customer 5+)

> **Vision pillar:** Evaluate phase
> **GTM milestone:** Retention features by Month 3

### MVP-044: Resend webhook integration (opens + replies)
**Priority:** Should Have | **Effort:** M | **Dependencies:** None

**Description:** Register Resend webhooks for email delivery, open, click, and bounce events. Store events in an `email_events` table. Update message status based on events. Foundation for reply tracking.

**Acceptance Criteria:**
- Given an email is opened, when Resend webhook fires, then the open event is recorded
- Given an email bounces, when webhook fires, then the contact's email is flagged
- Given events are recorded, when campaign analytics are viewed, then open rates are displayed

**Files to modify:**
- Create: `api/routes/webhook_routes.py` (Resend webhooks)
- Create: `migrations/036_email_events.sql`
- Modify: `api/models.py`

---

### MVP-045: Basic campaign analytics dashboard
**Priority:** Should Have | **Effort:** M | **Dependencies:** MVP-044

**Description:** Replace the placeholder Echo Analytics page with a real dashboard showing: messages sent, opens, replies, bounces by campaign. Per-campaign funnel visualization.

**Acceptance Criteria:**
- Given a campaign has sent 50 emails, when analytics page loads, then it shows sent/open/reply/bounce counts
- Given email events are tracked, when funnel is displayed, then conversion rates are shown at each stage

**Files to modify:**
- Modify: `frontend/src/pages/echo/EchoPage.tsx`
- Create: `api/routes/analytics_routes.py`

---

## Post-MVP Items (Won't Have for MVP)

These are tracked for planning purposes but are explicitly excluded from the MVP scope.

| ID | Title | Effort | Rationale for Deferral |
|----|-------|--------|----------------------|
| POST-001 | Campaign phase full implementation (PB-034) | XL | Standalone campaigns work; playbook integration is polish |
| POST-002 | Voice Dialog Mode (PB-031, BL-047) | XL | Far-future differentiator; requires real-time voice infrastructure |
| POST-003 | AI Avatar (PB-032, BL-047) | XL | Depends on voice dialog; no customer has asked for it |
| POST-004 | Continuous Learning Loop (PB-033, BL-048) | XL | Requires real campaign data from many customers |
| POST-005 | Cross-User Learning (BL-048) | XL | Requires 50+ active customers to be meaningful |
| POST-006 | A/B Variant Generation (BL-043) | M | Nice-to-have; manual testing works for first 10 customers |
| POST-007 | German language UI (i18n) | L | Required for DACH expansion (Month 7); not needed for Czech launch |
| POST-008 | CRM integrations (BL-007/008/009/010) | L each | First 10 customers use CSV import; integrations are retention features |

---

## Recommended Implementation Sequence

### Phase A: Demo-Ready (Weeks 1-4)

**Goal:** Show the complete multi-phase playbook journey in a live demo. Landing page live with demo booking.

```
Week 1:
  - MVP-029: Landing page with demo CTA [S] — Marketing
  - MVP-030: Domain registration [S] — Marketing
  - MVP-019: Auto-save with debounce [S] — Editor
  - MVP-020: Auto-extract after save [S] — Editor
  - MVP-021: Markdown rendering in chat [S] — Chat
  - MVP-022: Proactive first AI message [S] — Chat
  - MVP-001: DB migration (phase + selections) [S] — Playbook

Week 2:
  - MVP-002: Model update [S] — Playbook
  - MVP-003: Phase API [M] — Playbook (can parallel with MVP-004/005)
  - MVP-004: Phase-aware system prompt [M] — Playbook
  - MVP-005: Chat phase parameter [S] — Playbook
  - MVP-012: Store selections API [S] — Playbook
  - MVP-031: Onboarding progress messages [S] — Enrichment

Week 3:
  - MVP-006: Frontend route [S] — Playbook
  - MVP-007: PhaseIndicator [M] — Playbook
  - MVP-008: PlaybookTopBar [M] — Playbook
  - MVP-009: StrategyPanel extraction [M] — Playbook
  - MVP-010: Phase guard [S] — Playbook

Week 4:
  - MVP-011: ContactSelectionPanel [L] — Playbook
  - MVP-013: Phase 1->2 gate [S] — Playbook
  - MVP-023: Language matching [S] — Chat
```

**Milestone:** Demo-ready. Can show: onboarding -> strategy editor with AI chat -> phase stepper -> contact selection -> forward transition. Message phase is a placeholder but the story is clear.

### Phase B: Trial-Ready (Weeks 5-8)

**Goal:** Self-service signup, full message flow, first paying customer.

```
Week 5:
  - MVP-033: Email transactional setup [M] — Infra (prerequisite for signup)
  - MVP-014: Generate Messages button [M] — Playbook
  - MVP-017: Phase 2->3 gate [S] — Playbook

Week 6:
  - MVP-024: Self-service signup [M] — Auth
  - MVP-015: MessageReviewPanel [L] — Playbook
  - MVP-016: Message generation trigger [L] — Playbook (parallel with MVP-015)
  - MVP-034: Health checks [S] — Infra

Week 7:
  - MVP-025: Password reset [M] — Auth
  - MVP-032: Strategy-informed prompts [M] — Enrichment
  - MVP-035: Sentry integration [S] — Infra

Week 8:
  - MVP-018: Launch Campaign button [M] — Playbook
  - MVP-026: Stripe Checkout integration [L] — Billing (start; continues into Week 9)
```

**Milestone:** First paying customer. Full playbook flow works end-to-end. Self-service signup operational. Manual invoicing as billing fallback.

### Phase C: Scale to 10 (Weeks 9-12)

**Goal:** Billing, analytics, polish for retention.

```
Week 9:
  - MVP-026: Stripe Checkout (completion) [L] — Billing
  - MVP-027: Usage metering [M] — Billing
  - MVP-028: Pricing page [S] — Billing

Week 10:
  - MVP-044: Resend webhooks [M] — Analytics
  - MVP-036: Action item parsing [M] — Chat
  - MVP-037: ActionItemList [M] — Chat

Week 11:
  - MVP-045: Campaign analytics [M] — Analytics
  - MVP-038: Toggle action items API [S] — Chat
  - MVP-039: PhaseTransitionCard [M] — Chat

Week 12:
  - MVP-040: PhaseDivider [S] — Chat
  - MVP-041: Topic detection [S] — Chat
  - MVP-042: Frustration detection [S] — Chat
  - MVP-043: Strategy readiness [M] — Chat
```

**Milestone:** 10 paying customers. Stripe billing active. Basic analytics. Chat intelligence features deployed.

---

## Mapping to Vision Pillars and GTM Milestones

| Task ID | Vision Pillar | GTM Milestone | Phase |
|---------|--------------|---------------|-------|
| MVP-001..MVP-018 | Try + Run (Flywheel phases 1-2) | Demo-ready (W2), Trial-ready (W6) | A-B |
| MVP-019..MVP-020 | Try (editor quality) | Demo-ready (W1) | A |
| MVP-021..MVP-023 | Try (AI intelligence) | Demo-ready (W1) | A |
| MVP-024..MVP-025 | Self-service onboarding | Trial-ready (W6) | B |
| MVP-026..MVP-028 | Revenue capture | First paying customer (W8) | C |
| MVP-029..MVP-030 | Brand awareness | Landing page live (W1) | A |
| MVP-031..MVP-032 | Try + Run (data quality) | Demo-ready (W2), Trial-ready (W6) | A-B |
| MVP-033..MVP-035 | Operational reliability | Trial-ready (W6) | B |
| MVP-036..MVP-043 | Try (AI intelligence depth) | Retention (W10+) | C |
| MVP-044..MVP-045 | Evaluate (analytics loop) | Scale to 10 (W12) | C |

---

## Existing Backlog Cross-Reference

| MVP Task | Existing BL/PB Item | Status | Notes |
|----------|-------------------|--------|-------|
| MVP-001 | PB-001 | Not started | Identical |
| MVP-002 | PB-002 | Not started | Identical |
| MVP-003 | PB-003 | Not started | Identical |
| MVP-004 | PB-005 | Not started | Identical |
| MVP-005 | PB-004 | Not started | Identical |
| MVP-006 | PB-006 | Not started | Identical |
| MVP-007 | PB-007 | Not started | Identical |
| MVP-008 | PB-008 | Not started | Identical |
| MVP-009 | PB-009 | Not started | Identical |
| MVP-010 | PB-010 | Not started | Identical |
| MVP-011 | PB-011 | Not started | Identical |
| MVP-012 | PB-012 | Not started | Identical |
| MVP-013 | PB-013 | Not started | Identical |
| MVP-014 | PB-015 | Not started | Identical |
| MVP-015 | PB-016 | Not started | Identical |
| MVP-016 | PB-017 | Not started | Identical |
| MVP-017 | PB-018 | Not started | Identical |
| MVP-018 | PB-020 | Not started | Identical |
| MVP-023 | PB-028 | Not started | Identical |
| MVP-032 | — | New | Not in existing backlogs |
| MVP-036 | PB-021 | Not started | Identical |
| MVP-037 | PB-022 | Not started | Identical |
| MVP-038 | PB-023 | Not started | Identical |
| MVP-039 | PB-024 | Not started | Identical |
| MVP-040 | PB-025 | Not started | Identical |
| MVP-041 | PB-026 | Not started | Identical |
| MVP-042 | PB-027 | Not started | Identical |
| MVP-043 | PB-029 | Not started | Identical |
| MVP-024 | — | New | Self-service signup not in backlogs |
| MVP-025 | — | New | Password reset not in backlogs |
| MVP-026 | — | New | Stripe billing not in backlogs |
| MVP-027 | — | New | Usage metering not in backlogs |
| MVP-029 | — | New | Landing page not in backlogs |
| MVP-033 | BL-030 (partial) | Partial | Resend integration exists but only for outreach, not transactional |

---

## What's NOT in This Backlog (and Why)

| Capability | Why Excluded | When to Revisit |
|-----------|-------------|-----------------|
| Contact discovery (find new contacts matching ICP) | Requires external data source integration (Apollo, LinkedIn API). Enrichment of existing contacts is built. | After 10 customers validate the core loop |
| CRM integrations (HubSpot, Pipedrive, Notion) | First 10 customers use CSV import. Integrations are retention. | After Month 3 (Phase 2 GTM) |
| German language UI | Czech market first. DACH expansion planned for Month 7. | After 25 CZ customers |
| Evaluate loop (A/B results, segment analysis) | Requires real campaign data from multiple customers. | After 20+ campaigns sent |
| Improve loop (AI learns from results) | Requires Evaluate loop first. The moat, but premature to build. | After Month 6 |
| White-label / agency partner portal | Channel partnerships in Phase 3 (Month 7). | After first partner conversation |
| OAuth login (Google/Microsoft) | Email+password works for first 10. OAuth is convenience. | After 25 customers |
| Smart contact refresh (BL-029) | Staleness is not a problem in first 3 months. | After data ages |
| PDF generation (BL-042) | Edge case for enterprise tier. | On customer request |
