# Personalized Outreach Campaign

**Status**: Draft
**Date**: 2026-02-21
**Theme**: AI-Native GTM — Entry Point 2 (Personalized Outreach)
**Backlog**: BL-060
**Vision Reference**: docs/plans/2026-02-21-ai-native-gtm-vision.md

## Purpose

Transform mass outreach into hyper-personalized conversations at scale. Users create campaigns, select contacts (filtered by owner/ICP), and the system synthesizes enrichment data + playbook strategy into contextual, personalized messages per contact. Users review/edit in batch, then send via Resend (email) or Chrome extension (LinkedIn invites/messages with anti-ban rate limiting).

**Phase 1 acceptance test**: Aitransformers.eu community invites — 50-100 contacts get personalized 2-3 step email sequences ("join our AI community") tailored to their roles, industries, and interests.

**Phase 2 (out of scope)**: Catalog-aware content personalization for Unitedarts.cz.

## Requirements

### Functional Requirements

1. **FR-1: Campaign Creation** — User creates a campaign with name, description, owner, and template selection (email sequence, LinkedIn, or mixed). Campaign starts in `draft` status.

2. **FR-2: Contact Selection** — User adds contacts to a campaign by filtering (owner, ICP criteria, tags, company tier). System validates enrichment readiness per contact and reports gaps.

3. **FR-3: Strategy-Driven Generation** — System generates personalized messages using:
   - Contact enrichment data (person summary, title, seniority, LinkedIn activity)
   - Company enrichment data (industry, size, tech stack, pain points, AI opportunities, recent news)
   - Playbook strategy context (ICP definition, value propositions, messaging framework, competitive positioning)
   - Campaign configuration (tone, language, custom instructions, channel constraints)

4. **FR-4: Batch Message Generation** — Background process generates messages for all contacts × enabled steps. Provides real-time progress (polling every 2s). Handles partial failures gracefully (marks failed contacts, continues with rest).

5. **FR-5: Message Review Queue** — Two review modes:
   - **Queue view** (fullscreen): Sequential review with keyboard shortcuts (A=approve, R=reject, E=edit, G=regenerate). Shows contact card + message side by side.
   - **Grid view** (batch): Sortable/filterable table with inline actions and multi-select for bulk approve/reject.

6. **FR-6: Message Editing with Reason Tracking** — Inline editing preserves original message. Edit requires reason tag (tone, personalization, accuracy, etc.) per existing ADR-007 pattern.

7. **FR-7: Email Send via Resend** — Approved email messages are sent directly from the platform using Resend API. Requires sender domain configuration per tenant.

8. **FR-8: LinkedIn Send via Chrome Extension** — Approved LinkedIn messages are queued for the Chrome extension. Extension pulls messages via API and executes sends with anti-ban patterns:
   - Rate limiting: max 20-30 connection requests/day, max 50-80 messages/day
   - Human-like delays: random 45-120 second intervals between actions
   - Session awareness: only sends during "active hours" (9am-6pm user timezone)
   - Cooldown: backs off on LinkedIn warnings or connection request limits

9. **FR-9: Campaign Analytics** — Dashboard showing: total contacts, generated/approved/rejected counts, send status (sent/delivered/failed), cost breakdown (LLM spend).

10. **FR-10: Cost Controls** — Show cost estimate before generation. Track cost per campaign via `llm_usage_log`. Configurable per-tenant monthly budget limit.

### Non-Functional Requirements

1. **NFR-1: Generation Speed** — Generate 100 messages (1 step each) in < 5 minutes.
2. **NFR-2: Review Speed** — Power user can approve 100 messages in < 15 minutes using keyboard shortcuts.
3. **NFR-3: Tenant Isolation** — Campaigns, contacts, messages, and send queues are tenant-isolated.
4. **NFR-4: Idempotent Sends** — Email and LinkedIn sends are idempotent (no duplicate messages on retry).
5. **NFR-5: Anti-Ban Compliance** — LinkedIn extension respects daily limits and never exceeds safe thresholds.

## Acceptance Criteria

### Aitransformers.eu Acceptance Test

- [ ] **AC-1**: Given a user creates a campaign "AI Community Invites" with "Email 3-Step" template, when they add 50 contacts filtered by owner=Michal, then the campaign shows 50 contacts with enrichment readiness status.
- [ ] **AC-2**: Given 50 contacts are added and playbook has extracted strategy data, when user clicks "Generate", then 150 messages (50 contacts × 3 steps) are generated with progress shown in real-time.
- [ ] **AC-3**: Given messages are generated, when user reviews in queue view pressing A/R keys, then each message references the contact's specific role, company context, and the community's value prop from the playbook.
- [ ] **AC-4**: Given 140 of 150 messages are approved, when user clicks "Send Emails", then emails are dispatched via Resend with proper sender identity and tracking.
- [ ] **AC-5**: Given a campaign with LinkedIn messages, when the Chrome extension syncs, then it pulls approved messages and executes sends with 45-120s random delays between actions.
- [ ] **AC-6**: Given two tenants exist, when tenant B tries to access tenant A's campaign, then they receive 403 Forbidden.

### Core Functionality

- [ ] **AC-7**: Given a campaign in "generating" status, when 3 of 50 contacts fail (missing enrichment), then 47 succeed and the 3 failures are marked with error reasons.
- [ ] **AC-8**: Given a user edits a message body, when they save, then the original is preserved and an edit_reason tag is required.
- [ ] **AC-9**: Given a user selects 30 messages in grid view, when they click "Approve All", then all 30 are approved in one API call.
- [ ] **AC-10**: Given a campaign has $5 estimated cost, when user clicks Generate, then a confirmation dialog shows the cost estimate before proceeding.

## UX/Design

### User Flow

```
1. Campaigns page → "New Campaign" button
2. Campaign creation form: name, description, owner, template
3. Contacts tab → Filter + select contacts (owner, ICP, tags)
4. Generation tab → Configure tone, language, custom instructions
5. Click "Generate" → Progress modal (polling every 2s)
6. Messages tab → Grid view (default) or Queue view (fullscreen)
7. Review: approve/reject/edit messages
8. Outreach tab → Send emails (Resend) + queue LinkedIn (extension)
9. Monitor send status in campaign analytics
```

### Review Interface — Two Modes

**Queue View (Fullscreen)**:
- Left panel: Contact card (name, title, company, enrichment highlights, ICP score)
- Center: Message content with inline editing
- Bottom: Action buttons (Approve, Reject, Edit, Regenerate)
- Top: Progress bar (23 of 127, 15 approved, 3 rejected)
- Keyboard: A/R/E/G/D/Esc, auto-advance on approve

**Grid View (Batch)**:
- Sortable table: Contact | Channel | Step | Status | Body preview | Actions
- Multi-select checkboxes with sticky bulk action bar
- Filters: status, channel, step, owner, contact score
- Inline approve/reject per row
- Cmd+A to select all visible, bulk approve/reject

### Generation Progress

- Large modal with animated progress bar
- Real-time stats: "Processing contact 23 of 50... Emails: 15/50, Step 2: 8/50"
- Cost tracker: "Est. cost: $2.41"
- Minimize button (sends to background toast)
- Cancel button with confirmation

### UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching campaigns/contacts | Skeleton loader |
| Empty campaign | No contacts added | "Add contacts to get started" CTA |
| No enrichment | Contacts lack L1/L2 data | "3 contacts need enrichment" warning + "Enrich" button |
| Generating | Background generation running | Progress modal with real-time stats |
| Partial failure | Some messages failed | "47 of 50 generated, 3 failed" with error details |
| Review pending | Messages awaiting review | Badge count on Messages tab |
| All approved | Ready to send | Green "Ready to Send" banner on Outreach tab |
| Sending | Emails being dispatched | Progress indicator per channel |
| Sent | Campaign complete | Success state with analytics summary |

### Accessibility

- Keyboard-first review: A/R/E/G shortcuts with visible focus indicators
- Screen reader: aria-labels on all action buttons, role="progressbar" on generation, role="table" on grid
- Focus management: modal traps focus, returns on close
- Color: status uses icon + color (not color alone), WCAG AA contrast
- Motion: respects prefers-reduced-motion

## Technical Design

### Affected Components

| Component | File(s) | Change Type |
|-----------|---------|-------------|
| Campaign routes | `api/routes/campaign_routes.py` | Modified — add contact filtering, generation trigger |
| Message routes | `api/routes/message_routes.py` | Modified — add batch approve/reject |
| Campaign service | `api/services/campaign_service.py` | New — campaign workflow orchestration |
| Message generator | `api/services/message_generator.py` | Modified — add enrichment + strategy context to prompts |
| Generation prompts | `api/services/generation_prompts.py` | Modified — add strategy section, enrichment formatting |
| Send service | `api/services/send_service.py` | New — Resend email dispatch + LinkedIn queue |
| Extension API | `api/routes/extension_routes.py` | New — LinkedIn message queue for Chrome extension |
| Campaign wizard | `frontend/src/pages/campaigns/` | Modified — multi-tab workflow |
| Message grid | `frontend/src/components/campaign/CampaignMessagesGrid.tsx` | New — batch review table |
| Generation modal | `frontend/src/components/campaign/GenerationProgressModal.tsx` | New — progress tracking |
| Campaign hooks | `frontend/src/api/queries/useCampaigns.ts` | Modified — add generation, review, send hooks |

### Data Model Changes

**No new tables needed** — existing schema (migration 018) covers campaigns, campaign_contacts, campaign_templates, messages.

**Additions:**

1. **Extension send queue** — New table `linkedin_send_queue`:
   ```sql
   CREATE TABLE linkedin_send_queue (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     tenant_id UUID NOT NULL REFERENCES tenants(id),
     message_id UUID NOT NULL REFERENCES messages(id),
     contact_id UUID NOT NULL REFERENCES contacts(id),
     owner_id UUID NOT NULL REFERENCES owners(id),
     action_type VARCHAR(20) NOT NULL, -- 'connection_request', 'message'
     linkedin_url TEXT,
     body TEXT NOT NULL,
     status VARCHAR(20) DEFAULT 'queued', -- 'queued', 'claimed', 'sent', 'failed', 'skipped'
     claimed_at TIMESTAMPTZ,
     sent_at TIMESTAMPTZ,
     error TEXT,
     retry_count INT DEFAULT 0,
     created_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```

2. **Resend tracking** — New table `email_send_log`:
   ```sql
   CREATE TABLE email_send_log (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     tenant_id UUID NOT NULL REFERENCES tenants(id),
     message_id UUID NOT NULL REFERENCES messages(id),
     resend_message_id TEXT, -- Resend API response ID
     status VARCHAR(20) DEFAULT 'queued', -- 'queued', 'sent', 'delivered', 'bounced', 'failed'
     sent_at TIMESTAMPTZ,
     delivered_at TIMESTAMPTZ,
     error TEXT,
     created_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```

3. **Campaign.sender_config** — Add JSONB column for tenant email sender identity:
   ```sql
   ALTER TABLE campaigns ADD COLUMN sender_config JSONB DEFAULT '{}';
   -- e.g., {"from_email": "michal@aitransformers.eu", "from_name": "Michal", "reply_to": "michal@aitransformers.eu"}
   ```

4. **Indexes:**
   ```sql
   CREATE INDEX idx_linkedin_queue_owner_status ON linkedin_send_queue(owner_id, status);
   CREATE INDEX idx_email_send_log_status ON email_send_log(tenant_id, status);
   ```

### API Contract

#### Campaign Management (existing, enhanced)
- `POST /api/campaigns` — Create campaign (add sender_config)
- `GET /api/campaigns` — List campaigns (add status filter)
- `GET /api/campaigns/{id}` — Campaign detail with stats
- `PATCH /api/campaigns/{id}` — Update config (only in draft/ready)

#### Contact Selection
- `POST /api/campaigns/{id}/contacts/add` — Add contacts by filter/IDs
  - Body: `{owner_id?, icp_filters?, contact_ids?, company_ids?}`
  - Returns: `{added_count, gaps: [{contact_id, missing}]}`
- `GET /api/campaigns/{id}/contacts` — List campaign contacts with enrichment status
- `DELETE /api/campaigns/{id}/contacts/{contact_id}` — Remove contact

#### Generation
- `POST /api/campaigns/{id}/generate` — Start generation (shows cost estimate first)
  - Body: `{tone?, language?, custom_instructions?, confirm_cost: bool}`
  - Returns: `{status: "generating", cost_estimate, message_count}`
- `GET /api/campaigns/{id}/generation-status` — Poll progress
  - Returns: `{total, done, failed, cost_so_far, channels: {email: {done, target}}}`

#### Message Review
- `GET /api/campaigns/{id}/messages` — List with filters (status, channel, step)
- `PATCH /api/messages/{id}` — Approve/reject/edit single message (existing)
- `POST /api/campaigns/{id}/messages/batch-action` — Bulk approve/reject
  - Body: `{message_ids: [], action: "approve"|"reject", reason?}`

#### Send
- `POST /api/campaigns/{id}/send-emails` — Dispatch approved emails via Resend
  - Returns: `{queued_count, sender: {from_email, from_name}}`
- `POST /api/campaigns/{id}/queue-linkedin` — Queue approved LinkedIn messages for extension
  - Returns: `{queued_count, by_owner: {michal: 15, anton: 12}}`

#### Extension API (for Chrome extension)
- `GET /api/extension/linkedin-queue` — Pull next batch of LinkedIn actions for current owner
  - Headers: `Authorization: Bearer {token}`
  - Query: `limit=5` (extension pulls small batches)
  - Returns: `[{id, action_type, linkedin_url, body, contact_name}]`
- `PATCH /api/extension/linkedin-queue/{id}` — Report send result
  - Body: `{status: "sent"|"failed"|"skipped", error?}`

### Architecture Decisions

1. **Strategy context in prompts** — Playbook's `extracted_data` (ICP, value props, messaging framework) is injected into generation prompts alongside enrichment data. Falls back gracefully if no playbook exists. Strategy snapshot is stored in `campaign.generation_config` at generation time for reproducibility.

2. **LinkedIn anti-ban via extension** — The platform queues messages; the Chrome extension executes with rate limiting. This keeps ban risk on the client side (where the user's LinkedIn session lives) and allows per-owner daily limits. The extension is the "safe send agent."

3. **Resend for email** — Direct API integration, no SMTP setup needed. Per-tenant sender domain configuration. Webhook for delivery status tracking.

4. **Dual review modes** — Queue (fullscreen keyboard-driven) for power users reviewing one-by-one; Grid (batch table) for managers doing bulk operations. Both access the same data, just different UX.

## Edge Cases

1. **Contact with no enrichment** — Skip during generation, mark as `failed` with reason "missing enrichment". User can enrich and retry.
2. **Playbook not created** — Generation uses enrichment data only. Messages are personalized but not strategy-aligned. Show gentle prompt: "Create a playbook to improve message quality."
3. **LinkedIn daily limit reached** — Extension reports limit hit. Queue pauses, resumes next day. Dashboard shows "Paused: daily limit" status.
4. **Resend domain not configured** — Block email send with clear error: "Configure sender domain in Settings first."
5. **Duplicate contact in campaign** — Prevent at add time (existing duplicate detection in campaign_contacts).
6. **User edits then regenerates** — Regeneration replaces current body but preserves edit history. Original body remains in `original_body`.
7. **Campaign deleted during generation** — Cancel background thread, mark remaining as "cancelled".
8. **Extension disconnected** — Queue remains in "queued" status. Extension picks up on reconnect.

## Security Considerations

- **Tenant isolation**: All queries filter by `tenant_id`. Campaign access verified per request.
- **Rate limiting**: Cost pre-check before generation. Per-tenant monthly budget configurable.
- **PII**: Messages contain names, titles, company info. Stored in plaintext (consistent with existing messages table). Phase 2: consider encryption at rest.
- **Extension auth**: Extension uses same JWT auth as dashboard. Token refresh handles session expiry.
- **CSV injection**: If CSV export is added later, sanitize body/subject fields (escape leading =, +, -, @).
- **Resend API key**: Stored in tenant settings (encrypted), never exposed to frontend.

## Testing Strategy

### Unit Tests
- Campaign service: contact selection, enrichment validation, cost estimation
- Message generation: prompt building with strategy + enrichment context
- Send service: Resend dispatch, LinkedIn queue management
- Extension API: queue pull, status update, rate limit enforcement
- Batch operations: bulk approve/reject atomicity

### E2E Tests
- Happy path: Create campaign → add contacts → generate → review → send emails
- Partial failure: 3/50 contacts fail generation → 47 succeed, failures shown
- Keyboard review: Navigate 10 messages with A/R keys in queue view
- Bulk operations: Select all → approve → verify all status changed
- Tenant isolation: Tenant B cannot access Tenant A's campaign
- Extension queue: Queue LinkedIn messages → extension pulls → marks sent

### Verification Checklist
- [ ] All new routes have corresponding unit tests
- [ ] Edge cases (no enrichment, no playbook, daily limit) tested
- [ ] Keyboard shortcuts work in both queue and grid view
- [ ] Generation progress polling works with real-time updates
- [ ] Resend integration sends email with correct sender identity
- [ ] Extension API returns messages in correct order with rate limit metadata
- [ ] Cost tracking accurate (LLM cost + per-campaign aggregation)
- [ ] Existing tests still pass

## Dependencies

- **Backlog**: BL-031-036 (campaigns infrastructure — already built)
- **Backlog**: BL-045 (review workflow with edit tracking — already built)
- **Backlog**: BL-046 (contact ICP filters — already built)
- **External**: Resend API account + sender domain verification
- **External**: Chrome extension update for LinkedIn queue consumer

## Out of Scope

- **Catalog-aware personalization** (Phase 2 — Unitedarts.cz use case)
- **A/B variant generation** (BL-043 — future iteration)
- **Reply tracking / conversation threads** (requires email inbox integration)
- **LinkedIn reply monitoring** (requires extension enhancement)
- **Autonomous angle selection** (Phase 3 — ML-based, needs training data)
- **Lemlist integration** (not needed — using own extension + Resend)
- **Mobile-responsive review UI** (desktop-first, Phase 2)

## Open Questions

1. **Resend account**: Do we already have a Resend account, or need to set one up? What sender domain will Aitransformers use?
2. **Extension current state**: What can the Chrome extension currently do? Does it already have LinkedIn message/invite send capability, or does that need to be built?
3. **Daily LinkedIn limits**: What are the safe thresholds we should enforce? (Industry standard: 20-30 connection requests/day, 50-80 messages/day for established accounts)
4. **Email deliverability**: Do we need SPF/DKIM/DMARC setup guidance for tenants, or assume they handle their own domain config?
