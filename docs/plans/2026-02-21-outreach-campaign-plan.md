# Personalized Outreach Campaign — Track A Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable end-to-end personalized email campaigns with enrichment-powered AI message generation, playbook strategy integration, dual-mode review UI, and Resend email delivery.

**Architecture:** Extends existing campaign infrastructure (migration 018) with enrichment context in generation prompts, playbook strategy integration, dual-mode review UI, and Resend email dispatch. The LinkedIn queue API is built now (Track A) but consumed by the Chrome extension later (Track B).

**Tech Stack:** Flask + SQLAlchemy (backend), React + TypeScript + TanStack Query (frontend), Resend API (email), Claude API via existing `message_generator.py`

**Spec:** `docs/specs/personalized-outreach-campaign.md`

**Existing code to build on:**
- Campaign CRUD: `api/routes/campaign_routes.py` (list, create, get, update, delete, contacts, enrichment-check, cost-estimate, generate, generation-status, review-queue, review-summary, disqualify)
- Message routes: `api/routes/message_routes.py` (list, update, batch, regenerate)
- Message generator: `api/services/message_generator.py` (background thread, enrichment loading, Claude API calls)
- Generation prompts: `api/services/generation_prompts.py` (system prompt, prompt builder, channel constraints, formality)
- Extension routes: `api/routes/extension_routes.py` (lead import, activity sync)
- Frontend campaign pages: `frontend/src/pages/campaigns/` (CampaignsPage, CampaignDetailPage with 5 tabs)
- Frontend message review: `frontend/src/pages/messages/MessageReviewPage.tsx` (fullscreen queue with keyboard shortcuts)
- React Query hooks: `frontend/src/api/queries/useCampaigns.ts`, `useMessages.ts`
- Last migration: `031_add_business_type_enum_values.sql`

---

## Task 1: Database Migration — New Tables and Columns

**Files:**
- Create: `migrations/032_outreach_campaign_tables.sql`
- Modify: `api/models.py` — add `LinkedInSendQueue`, `EmailSendLog` models, add `sender_config` to `Campaign`

**Migration SQL:**
```sql
-- Resend email tracking
CREATE TABLE IF NOT EXISTS email_send_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    message_id UUID NOT NULL REFERENCES messages(id),
    resend_message_id TEXT,
    status VARCHAR(20) DEFAULT 'queued',
    from_email TEXT,
    to_email TEXT,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- LinkedIn send queue for Chrome extension
CREATE TABLE IF NOT EXISTS linkedin_send_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    message_id UUID NOT NULL REFERENCES messages(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    owner_id UUID NOT NULL REFERENCES owners(id),
    action_type VARCHAR(20) NOT NULL,
    linkedin_url TEXT,
    body TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'queued',
    claimed_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    error TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Campaign sender configuration
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS sender_config JSONB DEFAULT '{}';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_email_send_log_tenant_status ON email_send_log(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_email_send_log_message ON email_send_log(message_id);
CREATE INDEX IF NOT EXISTS idx_linkedin_queue_owner_status ON linkedin_send_queue(owner_id, status);
CREATE INDEX IF NOT EXISTS idx_linkedin_queue_tenant ON linkedin_send_queue(tenant_id, status);
```

**ORM models to add in `api/models.py`:**
- `EmailSendLog` with fields matching the table
- `LinkedInSendQueue` with fields matching the table
- Add `sender_config = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))` to `Campaign`

**Test requirements:**
- Unit test: migration applies cleanly (already covered by CI migration runner)
- Unit test: ORM models can be instantiated

**Estimated time:** 2 hours

---

## Task 2: Backend — Contact Selection with ICP Filters

**Files:**
- Modify: `api/routes/campaign_routes.py` — enhance `POST /api/campaigns/{id}/contacts` to accept `owner_id` and `icp_filters`

**Current state:** `add_campaign_contacts` already accepts `contact_ids` and `company_ids`. We need to add `owner_id` filter and `icp_filters` (tier, industry, icp_fit, seniority, tag_ids) to automatically resolve matching contacts.

**API contract:**
```
POST /api/campaigns/{id}/contacts
Body: {
  contact_ids?: string[],
  company_ids?: string[],
  owner_id?: string,          // NEW: filter contacts by owner
  icp_filters?: {             // NEW: auto-resolve contacts matching filters
    tiers?: string[],
    industries?: string[],
    icp_fit?: string[],
    seniority_levels?: string[],
    tag_ids?: string[],
    min_contact_score?: number,
    enrichment_ready?: boolean  // only contacts with completed enrichment
  }
}
Response: { added: N, skipped: N, total: N, gaps: [{contact_id, missing}] }
```

**Implementation:**
1. If `icp_filters` provided, build a dynamic SQL query joining `contacts`, `companies`, `entity_stage_completions`
2. Apply each filter as a WHERE clause
3. If `enrichment_ready`, join `entity_stage_completions` and require `l1_company`, `l2_deep_research`, `person` stages completed
4. Merge results with explicitly provided `contact_ids`/`company_ids`
5. Return enrichment gaps alongside added count

**Test requirements:**
- Unit test: filter by owner resolves correct contacts
- Unit test: filter by tier + industry applies correctly
- Unit test: enrichment_ready filter excludes contacts without completed stages
- Unit test: duplicate prevention still works

**Estimated time:** 3 hours

---

## Task 3: Backend — Strategy Context in Generation Prompts

**Files:**
- Modify: `api/services/generation_prompts.py` — add `_build_strategy_section()`, update `build_generation_prompt()` signature
- Modify: `api/services/message_generator.py` — load playbook `extracted_data` and pass to prompt builder, snapshot strategy in `campaign.generation_config`

**Current state:** `build_generation_prompt()` already builds `--- CONTACT ---` and `--- COMPANY ---` sections from enrichment data. We need to add `--- STRATEGY ---` section from the tenant's playbook `extracted_data` (ICP, value props, messaging framework).

**Implementation in `generation_prompts.py`:**
```python
def _build_strategy_section(strategy_data: dict) -> str:
    """Format playbook extracted_data for the generation prompt."""
    lines = []
    if strategy_data.get("icp"):
        lines.append(f"ICP: {strategy_data['icp']}")
    if strategy_data.get("value_proposition"):
        lines.append(f"Value Proposition: {strategy_data['value_proposition']}")
    if strategy_data.get("messaging_framework"):
        lines.append(f"Messaging Framework: {strategy_data['messaging_framework']}")
    if strategy_data.get("competitive_positioning"):
        lines.append(f"Competitive Position: {strategy_data['competitive_positioning']}")
    if strategy_data.get("buyer_personas"):
        lines.append(f"Buyer Personas: {strategy_data['buyer_personas']}")
    return "\n".join(lines) if lines else "No strategy data available."
```

**Implementation in `message_generator.py`:**
1. In `_generate_all()`, load `StrategyDocument.extracted_data` for the tenant
2. Snapshot it in `campaign.generation_config["strategy_snapshot"]` at generation start
3. Pass `strategy_data` to `build_generation_prompt()`
4. In `build_generation_prompt()`, add a `--- STRATEGY ---` section between `--- COMPANY ---` and `--- SEQUENCE CONTEXT ---`

**Updated `build_generation_prompt()` signature:**
```python
def build_generation_prompt(
    *,
    channel: str,
    step_label: str,
    contact_data: dict,
    company_data: dict,
    enrichment_data: dict,
    generation_config: dict,
    step_number: int,
    total_steps: int,
    strategy_data: dict | None = None,  # NEW
    formality: str | None = None,
    per_message_instruction: str | None = None,
) -> str:
```

**Test requirements:**
- Unit test: prompt includes strategy section when data available
- Unit test: prompt gracefully omits strategy section when no playbook exists
- Unit test: strategy snapshot stored in generation_config
- Unit test: regeneration also includes strategy context

**Estimated time:** 3 hours

---

## Task 4: Backend — Enhanced Generation Progress Endpoint

**Files:**
- Modify: `api/routes/campaign_routes.py` — enhance `GET /api/campaigns/{id}/generation-status`

**Current state:** Already returns `status`, `total_contacts`, `generated_count`, `generation_cost`, `progress_pct`, `contact_statuses`. We need to add channel-level breakdown and per-step counts.

**Enhanced response:**
```json
{
  "status": "Generating",
  "total_contacts": 50,
  "generated_count": 23,
  "generation_cost": 2.41,
  "progress_pct": 46,
  "contact_statuses": {"generating": 1, "generated": 22, "pending": 27},
  "channels": {
    "email": {"generated": 69, "target": 150},
    "linkedin_connect": {"generated": 23, "target": 50}
  },
  "failed_contacts": [
    {"contact_id": "...", "name": "...", "error": "missing enrichment"}
  ]
}
```

**Implementation:**
1. Add a query joining `messages` with `campaign_contacts` grouped by `channel`
2. Calculate target per channel from `template_config` step counts times `total_contacts`
3. Add a query for failed contacts (status = 'failed') with their error messages

**Test requirements:**
- Unit test: channel breakdown correctly groups by message channel
- Unit test: failed contacts list included with error reasons

**Estimated time:** 2 hours

---

## Task 5: Backend — Batch Message Operations (Bulk Approve/Reject)

**Files:**
- Modify: `api/routes/campaign_routes.py` — add `POST /api/campaigns/{id}/messages/batch-action`

**Current state:** `message_routes.py` has `PATCH /api/messages/batch` that updates status for a list of IDs. We need a campaign-scoped batch action endpoint that's more semantic (approve/reject) and handles timestamps.

**API contract:**
```
POST /api/campaigns/{id}/messages/batch-action
Body: { message_ids: string[], action: "approve"|"reject", reason?: string }
Response: { updated: N, action: "approve"|"reject" }
```

**Implementation:**
1. Verify all message_ids belong to the campaign and tenant
2. For `approve`: set `status='approved'`, `approved_at=now()`
3. For `reject`: set `status='rejected'`, `review_notes=reason`
4. Update in a single SQL statement for atomicity
5. Return count of updated messages

**Test requirements:**
- Unit test: batch approve sets status and approved_at for all messages
- Unit test: batch reject sets status and review_notes
- Unit test: messages from wrong campaign are rejected (403)
- Unit test: empty list returns error

**Estimated time:** 2 hours

---

## Task 6: Backend — Resend Email Send Service

**Files:**
- Create: `api/services/send_service.py` — Resend integration + email dispatch
- Modify: `api/routes/campaign_routes.py` — add `POST /api/campaigns/{id}/send-emails`
- Modify: `requirements.txt` — add `resend` package

**API contract:**
```
POST /api/campaigns/{id}/send-emails
Body: { confirm?: boolean }
Response: { queued_count: N, sender: { from_email, from_name } }
```

**`send_service.py` implementation:**
```python
import resend
from ..models import db, EmailSendLog

def send_campaign_emails(campaign_id: str, tenant_id: str) -> dict:
    """Send all approved email messages for a campaign via Resend."""
    # 1. Load campaign sender_config
    # 2. Load approved email messages not yet sent
    # 3. For each message:
    #    a. Create EmailSendLog entry (status='queued')
    #    b. Call resend.Emails.send({from, to, subject, html})
    #    c. Update EmailSendLog with resend_message_id and status='sent'
    #    d. Update message.sent_at
    # 4. Return summary

def configure_resend(api_key: str):
    """Configure Resend API key (from tenant settings)."""
    resend.api_key = api_key
```

**Key decisions:**
- Resend API key stored in `tenant.settings["resend_api_key"]` (encrypted in DB)
- Sender identity from `campaign.sender_config` (from_email, from_name, reply_to)
- Idempotent: skip messages that already have an EmailSendLog with status != 'failed'
- Send synchronously in a loop with 100ms delay (Resend rate limit: 10 req/s)
- Body rendered as HTML (wrap plain text in `<pre>` tags for now; Phase 2 adds templates)

**Test requirements:**
- Unit test: emails dispatched with correct sender identity
- Unit test: idempotent — skips already-sent messages
- Unit test: failed sends logged with error
- Unit test: missing sender_config returns 400
- Unit test: non-email messages excluded

**Estimated time:** 4 hours

---

## Task 7: Backend — LinkedIn Queue API (for Chrome Extension)

**Files:**
- Modify: `api/routes/extension_routes.py` — add LinkedIn queue endpoints
- Modify: `api/routes/campaign_routes.py` — add `POST /api/campaigns/{id}/queue-linkedin`

**Campaign endpoint — queue messages:**
```
POST /api/campaigns/{id}/queue-linkedin
Response: { queued_count: N, by_owner: { "michal": 15 } }
```

**Extension endpoints — consume queue:**
```
GET /api/extension/linkedin-queue?limit=5
Response: [{ id, action_type, linkedin_url, body, contact_name }]

PATCH /api/extension/linkedin-queue/{id}
Body: { status: "sent"|"failed"|"skipped", error? }
Response: { ok: true }
```

**Implementation:**

1. `POST /campaigns/{id}/queue-linkedin`:
   - Find approved LinkedIn messages (channel in `linkedin_connect`, `linkedin_message`)
   - For each, create a `LinkedInSendQueue` entry with owner_id from message, linkedin_url from contact
   - Skip messages already queued (idempotent by message_id)
   - Return count grouped by owner

2. `GET /extension/linkedin-queue`:
   - Filter by current user's owner_id and status='queued'
   - Return oldest N entries
   - Mark as 'claimed' with `claimed_at`

3. `PATCH /extension/linkedin-queue/{id}`:
   - Verify ownership
   - Update status, sent_at, error
   - Update source message's sent_at if status='sent'

**Test requirements:**
- Unit test: queuing creates correct LinkedInSendQueue entries
- Unit test: idempotent — re-queuing skips existing entries
- Unit test: extension pulls only own owner's messages
- Unit test: status update propagates to source message

**Estimated time:** 4 hours

---

## Task 8: Backend — Campaign Analytics Endpoint

**Files:**
- Modify: `api/routes/campaign_routes.py` — add `GET /api/campaigns/{id}/analytics`

**API contract:**
```
GET /api/campaigns/{id}/analytics
Response: {
  contacts: { total, enriched, failed },
  messages: { total, approved, rejected, draft },
  emails: { queued, sent, delivered, bounced, failed },
  linkedin: { queued, claimed, sent, failed, skipped },
  cost: { generation, total_llm },
  by_step: [{ step, label, channel, total, approved, sent }],
  by_channel: { email: { approved, sent }, linkedin_connect: { approved, queued } }
}
```

**Implementation:**
- Aggregate from `campaign_contacts`, `messages`, `email_send_log`, `linkedin_send_queue`
- Group by step (from message `sequence_step`) and by channel
- Cost from `campaign.generation_cost` + sum of `llm_usage_log` for this campaign

**Test requirements:**
- Unit test: analytics aggregates all tables correctly
- Unit test: empty campaign returns zero counts (not errors)
- Unit test: tenant isolation enforced

**Estimated time:** 3 hours

---

## Task 9: Frontend — Campaign Creation Wizard Enhancements

**Files:**
- Modify: `frontend/src/pages/campaigns/CampaignsPage.tsx` — enhance create dialog
- Modify: `frontend/src/api/queries/useCampaigns.ts` — add sender_config to create mutation

**Current state:** CampaignsPage has a "New Campaign" dialog with name, description, owner, template selection. We need to add `sender_config` fields.

**Enhancements:**
1. Add "Sender Identity" section to create dialog (collapsible, optional):
   - From Email input
   - From Name input
   - Reply-To input
2. Pass `sender_config` in the create mutation body
3. Update `Campaign` interface to include `sender_config`

**Test requirements:**
- E2E test: create campaign with sender config
- E2E test: create campaign without sender config (defaults to empty)

**Estimated time:** 2 hours

---

## Task 10: Frontend — Contact Selector with Enrichment Readiness

**Files:**
- Modify: `frontend/src/pages/campaigns/ContactPicker.tsx` — add ICP filter controls
- Modify: `frontend/src/pages/campaigns/tabs/ContactsTab.tsx` — add enrichment check button
- Modify: `frontend/src/api/queries/useCampaigns.ts` — add `useEnrichmentCheck` hook

**Current state:** ContactPicker fetches all contacts and allows selection. ContactsTab shows the list with a remove button. Neither has ICP filters or enrichment readiness indicators.

**Enhancements to ContactPicker:**
1. Add filter bar: Owner dropdown, Tier multi-select, ICP Fit multi-select, Min Score slider
2. Filter locally first (all contacts loaded), or add server-side filter if needed
3. Show enrichment status icon per contact (green check = ready, orange warning = gaps)
4. "Select All Filtered" button

**Enhancements to ContactsTab:**
1. "Check Enrichment" button that calls `POST /api/campaigns/{id}/enrichment-check`
2. Show enrichment status column: ready (green), needs L1 (orange), needs L2 (orange), needs person (orange)
3. Summary banner: "42 of 50 contacts enrichment-ready. 8 need enrichment."
4. Badge on Contacts tab showing gap count

**New React Query hook:**
```typescript
export function useEnrichmentCheck() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<EnrichmentCheckResponse>(`/campaigns/${campaignId}/enrichment-check`, { method: 'POST' }),
    onSuccess: (_, campaignId) => {
      qc.invalidateQueries({ queryKey: ['campaign-contacts', campaignId] })
    },
  })
}
```

**Test requirements:**
- E2E test: filter contacts by owner and verify filtered list
- E2E test: enrichment check shows correct gap summary
- E2E test: contacts with gaps show warning icons

**Estimated time:** 4 hours

---

## Task 11: Frontend — Generation Progress Modal

**Files:**
- Create: `frontend/src/components/campaign/GenerationProgressModal.tsx`
- Modify: `frontend/src/pages/campaigns/tabs/MessageGenTab.tsx` — add Generate button + cost confirmation + progress modal
- Modify: `frontend/src/api/queries/useCampaigns.ts` — add `useCostEstimate`, `useStartGeneration`, `useGenerationStatus` hooks

**Current state:** MessageGenTab shows template steps and generation config. There's no "Generate" button or progress tracking in the frontend yet (the backend endpoints exist).

**GenerationProgressModal component:**
```tsx
interface Props {
  campaignId: string
  isOpen: boolean
  onClose: () => void
}
```
- Large modal with animated progress bar
- Polls `GET /api/campaigns/{id}/generation-status` every 2 seconds
- Shows: "Processing contact 23 of 50..."
- Channel breakdown: "Emails: 69/150, LinkedIn: 23/50"
- Cost tracker: "Cost so far: $2.41"
- Failed contact count with expandable list
- "Minimize" button (closes modal, shows toast with progress)
- Auto-closes when status transitions from "Generating" to "Review"

**MessageGenTab enhancements:**
1. "Estimate Cost" button → shows cost breakdown dialog
2. "Generate Messages" button (disabled unless status is Ready and contacts > 0)
3. Cost confirmation dialog: "Generate 150 messages for 50 contacts? Estimated cost: $3.50"
4. On confirm → POST `/generate` → open GenerationProgressModal

**New React Query hooks:**
```typescript
export function useCostEstimate() {
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<CostEstimateResponse>(`/campaigns/${campaignId}/cost-estimate`, { method: 'POST' }),
  })
}

export function useStartGeneration() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<{ ok: boolean; status: string }>(`/campaigns/${campaignId}/generate`, { method: 'POST' }),
    onSuccess: (_, campaignId) => {
      qc.invalidateQueries({ queryKey: ['campaign', campaignId] })
    },
  })
}

export function useGenerationStatus(campaignId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['generation-status', campaignId],
    queryFn: () => apiFetch<GenerationStatusResponse>(`/campaigns/${campaignId}/generation-status`),
    enabled: enabled && !!campaignId,
    refetchInterval: 2000,
  })
}
```

**Test requirements:**
- E2E test: cost estimate dialog shows correct breakdown
- E2E test: generate button transitions campaign to "Generating"
- E2E test: progress modal shows updating progress (mock backend)

**Estimated time:** 5 hours

---

## Task 12: Frontend — Message Review Grid View (MessagesTab Enhancement)

**Files:**
- Modify: `frontend/src/pages/campaigns/tabs/MessagesTab.tsx` — add table view alongside existing grouped view
- Create: `frontend/src/components/campaign/MessageGridView.tsx` — sortable/filterable table

**Current state:** MessagesTab groups messages by contact using `ContactGroup` component. This is effectively a card-based view. We need to add a flat table view with multi-select and bulk actions.

**MessageGridView component:**
- Flat table with columns: Checkbox, Contact, Channel, Step, Status, Body preview (50 chars), Actions
- Sortable by contact score, channel, step, status
- Filterable by status, channel, step
- Multi-select checkboxes with "Select All Visible" (Cmd+A)
- Sticky bulk action bar at bottom: "15 selected — Approve All | Reject All"
- Inline per-row actions: Approve (checkmark), Reject (X), Edit (pencil → navigate to review page)

**MessagesTab changes:**
- Add view toggle: "Grid | Grouped" (icon buttons)
- Grid view shows `MessageGridView`
- Grouped view shows existing `ContactGroup` layout
- Persist preference in localStorage

**Test requirements:**
- E2E test: toggle between grid and grouped views
- E2E test: select multiple messages and bulk approve
- E2E test: filter by channel shows correct subset
- E2E test: Cmd+A selects all visible

**Estimated time:** 5 hours

---

## Task 13: Frontend — Message Review Queue View Enhancement

**Files:**
- Modify: `frontend/src/pages/messages/MessageReviewPage.tsx` — enhance with campaign context

**Current state:** MessageReviewPage already has fullscreen queue with keyboard shortcuts (A=approve, R=reject, E=edit, G=regenerate, D=disqualify). It works well. Minor enhancements needed for the campaign flow.

**Enhancements:**
1. Add a "Back to Campaign" breadcrumb link when navigated from CampaignDetailPage
2. Show enrichment highlights in the contact card (person summary, ICP score, relationship synthesis)
3. Show strategy alignment note if playbook is available ("Aligned with: AI Community Growth strategy")
4. Add progress stats bar at top: "23 of 127 reviewed | 15 approved | 3 rejected | 5 remaining"
5. Auto-advance filter: option to show only draft messages (skip already-reviewed)

**Implementation:**
- Add `enrichment_highlights` to the review queue API response (already available in the query, just needs to be formatted)
- Progress bar is a simple calculation from `stats` already returned by the API

**Test requirements:**
- E2E test: keyboard navigation through messages still works
- E2E test: progress bar updates after approve/reject

**Estimated time:** 3 hours

---

## Task 14: Frontend — Outreach Tab (Send Emails, Queue LinkedIn)

**Files:**
- Modify: `frontend/src/pages/campaigns/tabs/OutreachTab.tsx` — replace placeholder with actual send UI
- Modify: `frontend/src/api/queries/useCampaigns.ts` — add `useSendEmails`, `useQueueLinkedIn`, `useCampaignAnalytics` hooks

**Current state:** OutreachTab is a placeholder ("Coming soon"). We need to build the actual send interface.

**OutreachTab layout:**
```
┌─────────────────────────────────────────────┐
│  Outreach Summary                           │
│  42 approved emails | 15 LinkedIn messages  │
│                                             │
│  ┌─── Email ─────────────────────────────┐  │
│  │ Sender: michal@aitransformers.eu      │  │
│  │ 42 emails ready to send               │  │
│  │ [Send All Emails]                     │  │
│  │                                       │  │
│  │ Status: 30 sent, 10 delivered, 2 fail │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌─── LinkedIn ──────────────────────────┐  │
│  │ 15 messages ready to queue            │  │
│  │ [Queue for Extension]                 │  │
│  │                                       │  │
│  │ Status: 10 queued, 5 sent             │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**Implementation:**
1. Show sender config (from campaign.sender_config) with edit button
2. "Send All Emails" button with confirmation dialog ("Send 42 emails from michal@aitransformers.eu?")
3. POST `/campaigns/{id}/send-emails` on confirm
4. Poll analytics for send status updates
5. "Queue for Extension" button for LinkedIn messages
6. POST `/campaigns/{id}/queue-linkedin` on confirm
7. Show live status from analytics endpoint

**New React Query hooks:**
```typescript
export function useSendEmails() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<{ queued_count: number; sender: Record<string, string> }>(
        `/campaigns/${campaignId}/send-emails`,
        { method: 'POST', body: { confirm: true } },
      ),
    onSuccess: (_, campaignId) => {
      qc.invalidateQueries({ queryKey: ['campaign-analytics', campaignId] })
    },
  })
}

export function useQueueLinkedIn() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<{ queued_count: number; by_owner: Record<string, number> }>(
        `/campaigns/${campaignId}/queue-linkedin`,
        { method: 'POST' },
      ),
    onSuccess: (_, campaignId) => {
      qc.invalidateQueries({ queryKey: ['campaign-analytics', campaignId] })
    },
  })
}
```

**Test requirements:**
- E2E test: send emails button triggers API call
- E2E test: queue LinkedIn button triggers API call
- E2E test: status cards update after send
- E2E test: missing sender config shows configuration prompt

**Estimated time:** 4 hours

---

## Task 15: Frontend — Campaign Analytics Dashboard

**Files:**
- Create: `frontend/src/components/campaign/CampaignAnalytics.tsx`
- Modify: `frontend/src/pages/campaigns/CampaignDetailPage.tsx` — add analytics to header or as summary card
- Modify: `frontend/src/api/queries/useCampaigns.ts` — add `useCampaignAnalytics` hook

**CampaignAnalytics component:**
```
┌─────────────────────────────────────────────┐
│  Campaign Overview                          │
│                                             │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌────────┐  │
│  │  50  │  │ 150  │  │ 140  │  │ $3.50  │  │
│  │Contct│  │Msgs  │  │Appvd │  │ Cost   │  │
│  └──────┘  └──────┘  └──────┘  └────────┘  │
│                                             │
│  Delivery Status                            │
│  Email:    ████████████░░░  80% (32/40)     │
│  LinkedIn: ██████░░░░░░░░  40% (6/15)      │
│                                             │
│  By Step                                    │
│  Step 1 (Intro Email):  50 gen | 48 appv    │
│  Step 2 (Follow-up):   50 gen | 46 appv    │
│  Step 3 (Value add):   50 gen | 46 appv    │
└─────────────────────────────────────────────┘
```

**Implementation:**
1. Fetch from `GET /api/campaigns/{id}/analytics`
2. Stat cards: contacts, messages, approved, cost
3. Progress bars per channel (email, linkedin)
4. Step breakdown table
5. Show on campaign detail page header (collapsed by default, expandable)

**Test requirements:**
- E2E test: analytics loads and shows correct counts
- E2E test: progress bars reflect delivery status

**Estimated time:** 3 hours

---

## Task 16: Integration Tests

**Files:**
- Create: `tests/unit/test_send_service.py`
- Create: `tests/unit/test_linkedin_queue.py`
- Modify: `tests/unit/test_campaign_routes.py` (if exists, or create)
- Modify: `tests/unit/test_message_routes.py` (if exists, or create)

**Test coverage:**

**`test_send_service.py`:**
1. `test_send_emails_dispatches_via_resend` — mock Resend API, verify emails sent
2. `test_send_emails_idempotent` — re-send skips already-sent
3. `test_send_emails_handles_failure` — failed send logged correctly
4. `test_send_emails_requires_sender_config` — 400 if no sender_config
5. `test_send_emails_only_approved` — only approved email messages sent

**`test_linkedin_queue.py`:**
6. `test_queue_linkedin_creates_entries` — approved LinkedIn messages queued
7. `test_queue_linkedin_idempotent` — re-queue skips existing
8. `test_extension_pull_returns_own_messages` — owner isolation
9. `test_extension_status_update_propagates` — sent status updates message
10. `test_extension_claimed_then_sent` — full lifecycle

**Campaign route tests:**
11. `test_batch_approve_all_messages` — bulk approve sets status
12. `test_batch_reject_with_reason` — bulk reject includes review_notes
13. `test_contact_filter_by_owner` — ICP filter resolves correct contacts
14. `test_generation_status_channels` — channel breakdown in progress
15. `test_analytics_aggregation` — analytics combines all tables

**Test requirements:**
- All tests use SQLite in-memory (existing pattern from `tests/conftest.py`)
- Mock external APIs (Resend, Anthropic)
- Each test file has proper fixtures

**Estimated time:** 5 hours

---

## Task 17: E2E Tests

**Files:**
- Create: `tests/e2e/test_campaign_e2e.py`

**Test scenarios:**

1. **Happy path**: Login → Create campaign → Add contacts → Configure generation → Generate (mock) → Review in grid → Approve all → Send emails (mock) → Verify analytics
2. **Keyboard review**: Navigate to review page → Use A/R/E keys → Verify progression
3. **Bulk operations**: Select multiple messages in grid → Bulk approve → Verify all updated
4. **Contact filtering**: Open picker → Filter by owner → Select filtered → Verify count
5. **Enrichment check**: Add contacts → Check enrichment → Verify gaps displayed
6. **Partial failure**: Generate with some contacts failing → Verify failure count shown

**Test requirements:**
- Uses Playwright (existing pattern)
- Requires `make dev` running
- Mock Anthropic API responses for generation
- Mock Resend API for email send

**Estimated time:** 5 hours

---

## Build Order

Tasks should be implemented in this order (dependencies noted):

```
Phase 1: Database + Core Backend (Tasks 1-5)
  Task 1: Migration                      [no deps]
  Task 2: Contact selection filters      [depends on Task 1]
  Task 3: Strategy in prompts            [no deps]
  Task 4: Generation progress            [no deps]
  Task 5: Batch message operations       [no deps]

Phase 2: Send Infrastructure (Tasks 6-8)
  Task 6: Resend email service           [depends on Task 1]
  Task 7: LinkedIn queue API             [depends on Task 1]
  Task 8: Campaign analytics             [depends on Tasks 6, 7]

Phase 3: Frontend (Tasks 9-15)
  Task 9: Campaign wizard enhancements   [depends on Task 1]
  Task 10: Contact selector + enrichment [depends on Task 2]
  Task 11: Generation progress modal     [depends on Task 4]
  Task 12: Message grid view             [depends on Task 5]
  Task 13: Queue view enhancement        [depends on Task 3]
  Task 14: Outreach tab                  [depends on Tasks 6, 7]
  Task 15: Campaign analytics            [depends on Task 8]

Phase 4: Testing (Tasks 16-17)
  Task 16: Integration tests             [depends on all backend tasks]
  Task 17: E2E tests                     [depends on all tasks]
```

**Parallelizable pairs:**
- Tasks 3 + 4 + 5 (independent backend work)
- Tasks 9 + 10 + 11 (independent frontend work, different tabs)
- Tasks 12 + 13 (different views of same data)

**Total estimated time:** ~59 hours (12-15 working days for a single developer)

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Resend API key not configured | Blocks email send testing | Use mock in dev/staging, real key in production only |
| Claude API rate limits during generation | Slow generation for large campaigns | Existing 0.5s delay between contacts; add backoff on 429 |
| LinkedIn extension not ready for Track B | Queue accumulates unsent messages | Queue API is complete; extension consumes later |
| Playbook extracted_data format varies | Strategy section in prompt may be sparse | Graceful fallback — prompt works without strategy |
| Large campaigns (500+ contacts) | Generation takes 15+ minutes | Progress modal with minimize; background thread already handles this |

---

## Files Created/Modified Summary

**New files (5):**
- `migrations/032_outreach_campaign_tables.sql`
- `api/services/send_service.py`
- `frontend/src/components/campaign/GenerationProgressModal.tsx`
- `frontend/src/components/campaign/MessageGridView.tsx`
- `frontend/src/components/campaign/CampaignAnalytics.tsx`

**Modified files (12):**
- `api/models.py` — add EmailSendLog, LinkedInSendQueue models + Campaign.sender_config
- `api/routes/campaign_routes.py` — batch-action, send-emails, queue-linkedin, analytics, enhanced contact add + generation-status
- `api/routes/extension_routes.py` — linkedin-queue pull + status update
- `api/services/message_generator.py` — load strategy data, pass to prompt builder
- `api/services/generation_prompts.py` — add `_build_strategy_section`, updated `build_generation_prompt`
- `frontend/src/api/queries/useCampaigns.ts` — 6 new hooks (cost estimate, generation, send, queue, analytics, enrichment check)
- `frontend/src/pages/campaigns/CampaignsPage.tsx` — sender config in create dialog
- `frontend/src/pages/campaigns/ContactPicker.tsx` — ICP filter controls
- `frontend/src/pages/campaigns/tabs/ContactsTab.tsx` — enrichment check
- `frontend/src/pages/campaigns/tabs/MessageGenTab.tsx` — generate button + cost confirm
- `frontend/src/pages/campaigns/tabs/MessagesTab.tsx` — grid/grouped view toggle
- `frontend/src/pages/campaigns/tabs/OutreachTab.tsx` — full send interface
- `frontend/src/pages/campaigns/CampaignDetailPage.tsx` — analytics card
- `frontend/src/pages/messages/MessageReviewPage.tsx` — enrichment highlights + strategy note

**Test files (3):**
- `tests/unit/test_send_service.py`
- `tests/unit/test_linkedin_queue.py`
- `tests/e2e/test_campaign_e2e.py`
