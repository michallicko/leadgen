# Message Review Workflow — Tasks

## Task Overview

| # | Task | Effort | Depends On |
|---|------|--------|-----------|
| T1 | Database migration 020 | S | — |
| T2 | Message model extensions | S | T1 |
| T3 | Regeneration service | M | T2 |
| T4 | Regeneration API endpoints | S | T3 |
| T5 | Message PATCH edit-reason support | S | T2 |
| T6 | Disqualify contact endpoint | S | T2 |
| T7 | Campaign review summary + approval gate | S | T2 |
| T8 | Review queue API endpoint | M | T2 |
| T9 | Focused review page (frontend) | L | T4, T5, T8 |
| T10 | Regeneration dialog (frontend) | M | T4, T9 |
| T11 | Edit panel with reason tags (frontend) | M | T5, T9 |
| T12 | Disqualify dialog (frontend) | S | T6, T9 |
| T13 | Outreach approval dialog (frontend) | S | T7 |
| T14 | Messages tab drill-in integration | S | T9 |
| T15 | Keyboard shortcuts | S | T9 |
| T16 | Unit tests (API) | M | T3-T8 |
| T17 | E2E tests (Playwright) | M | T9-T15 |

**Total effort**: ~L-XL (estimated 2-3 sessions)

---

## Task Details

### T1: Database Migration 020
**File**: `migrations/020_message_review_workflow.sql`

Add columns:
```sql
-- messages: version tracking + regeneration
ALTER TABLE messages ADD COLUMN original_body TEXT;
ALTER TABLE messages ADD COLUMN original_subject TEXT;
ALTER TABLE messages ADD COLUMN edit_reason TEXT;
ALTER TABLE messages ADD COLUMN edit_reason_text TEXT;
ALTER TABLE messages ADD COLUMN regen_count INTEGER DEFAULT 0;
ALTER TABLE messages ADD COLUMN regen_config JSONB;

-- contacts: disqualification
ALTER TABLE contacts ADD COLUMN is_disqualified BOOLEAN DEFAULT false;
ALTER TABLE contacts ADD COLUMN disqualified_at TIMESTAMPTZ;
ALTER TABLE contacts ADD COLUMN disqualified_reason TEXT;

-- index for filtering non-disqualified contacts
CREATE INDEX idx_contacts_disqualified ON contacts(tenant_id, is_disqualified) WHERE is_disqualified = true;
```

### T2: Message Model Extensions
**File**: `api/models.py`

Add new columns to Message model: `original_body`, `original_subject`, `edit_reason`, `edit_reason_text`, `regen_count`, `regen_config`.

Add new columns to Contact model: `is_disqualified`, `disqualified_at`, `disqualified_reason`.

Add `EDIT_REASONS` constant list for validation.

### T3: Regeneration Service
**File**: `api/services/message_generator.py`

New function `regenerate_message(message_id, tenant_id, language=None, formality=None, tone=None, instruction=None)`:
1. Load message + campaign_contact + contact + company + enrichment
2. Preserve `original_body` / `original_subject` if not already set
3. Build prompt with overrides via updated `build_generation_prompt()`
4. Call Claude Haiku, parse response
5. Update message: body, subject, regen_count++, regen_config, generation_cost_usd
6. Log cost
7. Return updated message

New function `estimate_regeneration_cost(message_id, tenant_id)`:
1. Load message + enrichment context
2. Count tokens in prompt template
3. Return estimated cost, input/output tokens, model name

**File**: `api/services/generation_prompts.py`

Update `build_generation_prompt()` to accept optional `formality` parameter:
- Add formality instruction to prompt: "Use informal address (tykani/tu/du)" or "Use formal address (vykani/vous/Sie)"
- Add per-message `instruction` parameter (separate from campaign-level `custom_instructions`)

### T4: Regeneration API Endpoints
**File**: `api/routes/message_routes.py`

New endpoints:
- `POST /api/messages/<id>/regenerate` — calls `regenerate_message()`, returns updated message
- `GET /api/messages/<id>/regenerate/estimate` — calls `estimate_regeneration_cost()`

Validation:
- Message must belong to tenant
- Message status must not be "generating" (not part of an active generation run)
- Instruction max 200 chars
- Formality must be "formal" or "informal" if provided

### T5: Message PATCH Edit-Reason Support
**File**: `api/routes/message_routes.py`

Extend existing `PATCH /api/messages/<id>`:
- When `body` is in the request and differs from current:
  - If `original_body` is null, set it to the current body
  - Require `edit_reason` field (return 400 if missing)
  - Optionally accept `edit_reason_text`
- Same for `subject` → `original_subject`
- Do NOT auto-approve on edit (remove existing auto-approve behavior)

Update response to include new fields: `original_body`, `original_subject`, `edit_reason`, `regen_count`, `regen_config`.

### T6: Disqualify Contact Endpoint
**File**: `api/routes/campaign_routes.py`

New endpoint `POST /api/campaigns/<id>/disqualify-contact`:
- Request: `{contact_id, scope: "campaign"|"global", reason?}`
- Campaign scope:
  - Set `campaign_contacts.status = 'excluded'` for this contact
  - Update all messages for this campaign_contact to `status = 'rejected'`, `review_notes = 'Contact excluded from campaign'`
- Global scope:
  - Above + set `contacts.is_disqualified = true`, `disqualified_at = now()`, `disqualified_reason = reason`
- Return: contact_id, scope, messages_rejected count

Also: Update `POST /api/campaigns/<id>/contacts` (add contacts) to filter out `is_disqualified = true` contacts.

### T7: Campaign Review Summary + Approval Gate
**File**: `api/routes/campaign_routes.py`

New endpoint `GET /api/campaigns/<id>/review-summary`:
- Query messages via campaign_contacts
- Return: total, approved, rejected, draft counts; excluded_contacts; active_contacts; by_channel breakdown; can_approve_outreach boolean; pending_reason

Extend `PATCH /api/campaigns/<id>` status transition:
- For `review → approved`: query messages. If any have `status = 'draft'`, return 400 with count of pending messages.

### T8: Review Queue API Endpoint
**File**: `api/routes/campaign_routes.py`

New endpoint `GET /api/campaigns/<id>/review-queue`:
- Query params: `status` (default "draft"), `channel`, `step`
- Returns ordered list of messages with full context:
  - Message object (all fields including new ones)
  - Contact object (name, title, email, LinkedIn, score, ICP, enrichment summary)
  - Company object (name, domain, tier, industry, country, summary, L2 highlights)
  - Position in queue (1-indexed) and total count
- Ordering: contact_score DESC, then sequence_step ASC
- Include queue stats (total, approved, rejected, draft, excluded)

### T9: Focused Review Page (Frontend)
**File**: `frontend/src/pages/messages/MessageReviewPage.tsx` (new)

Core single-message review component:
- Route: `/messages/review?campaign=<id>&status=draft`
- Fetches review queue from API
- Displays one message at a time with full context
- Progress bar: "5 of 24" with visual indicator
- Contact card (left): name, title, LinkedIn, ICP badge, score
- Company card (right): name, domain, tier, industry, country, summary snippet
- Message display: channel badge, step label, tone, language, char count
- Action buttons: Approve (A), Reject (R), Edit (E), Regenerate (G), Disqualify (D)
- Auto-advance on action (approve/reject/disqualify → next message)
- Completion state: when queue exhausted, show summary with "Back to Campaign" link

### T10: Regeneration Dialog (Frontend)
**File**: `frontend/src/pages/messages/RegenerationDialog.tsx` (new)

Modal dialog triggered by Regenerate button:
- Language dropdown: English, Czech, German, French, Spanish, Italian, Polish, Dutch, Portuguese, Swedish, Norwegian, Finnish, Danish
- Formality toggle: Formal / Informal (with localized labels: Vy/Ty, Vous/Tu, Sie/Du based on selected language)
- Tone dropdown: Professional, Casual, Bold, Empathetic
- Custom instruction: text input, max 200 chars, with char counter
- Cost estimate section: fetched from `/regenerate/estimate` on dialog open
- Cancel / Regenerate buttons
- Loading state during regeneration (API call in progress)
- On success: update message in queue, stay on same message (reviewer sees the new version)

### T11: Edit Panel with Reason Tags (Frontend)
**File**: `frontend/src/pages/messages/EditPanel.tsx` (new)

Inline edit panel (replaces message display area):
- Subject input (email channel only)
- Body textarea with char count / max chars
- Edit reason tag selector: dropdown with predefined tags + "Other" option
- "Other" shows additional text input for custom reason
- Cancel / Save Edit buttons
- Save calls `PATCH /api/messages/<id>` with body + edit_reason
- After save: returns to view mode with updated body. Message stays in current status (no auto-approve).

### T12: Disqualify Dialog (Frontend)
**File**: `frontend/src/pages/messages/DisqualifyDialog.tsx` (new)

Modal with two radio options:
- "Skip in this campaign" (campaign-only)
- "Disqualify contact globally" (with warning icon)
- Optional reason text input
- Cancel / Confirm buttons
- On confirm: calls `POST /api/campaigns/<id>/disqualify-contact`
- On success: advance past all remaining messages for this contact

### T13: Outreach Approval Dialog (Frontend)
**File**: `frontend/src/pages/campaigns/OutreachApprovalDialog.tsx` (new)

Triggered from campaign detail page:
- Fetches review summary from `/review-summary`
- Shows: contacts receiving outreach, excluded contacts, approved messages by channel, rejected messages
- Warning if 0 approved messages
- Cancel / Approve Outreach buttons
- On confirm: `PATCH /api/campaigns/<id>` with `status: "approved"`

Update `CampaignDetailPage.tsx`:
- Show "Approve Outreach" button when campaign status is "review" AND review summary shows `can_approve_outreach = true`
- Show "N messages pending review" badge when drafts remain

### T14: Messages Tab Drill-in Integration
**File**: `frontend/src/pages/campaigns/tabs/MessagesTab.tsx`

- Add "Start Review" button that navigates to `/messages/review?campaign=<id>&status=draft`
- Each message card in the grouped view is clickable → navigates to focused review at that message's position
- Update stats display to show approved/rejected/draft counts

### T15: Keyboard Shortcuts
**File**: `frontend/src/pages/messages/MessageReviewPage.tsx`

Add keyboard event handler in focused review mode:
- `A` — Approve current message
- `R` — Open reject dialog
- `E` — Enter edit mode
- `G` — Open regeneration dialog
- `D` — Open disqualify dialog
- `Esc` — Back to list (or cancel current dialog)
- Arrow keys / `J` / `K` — disabled (must take action to advance)

Show keyboard shortcut hints on action buttons.

### T16: Unit Tests (API)
**File**: `tests/unit/test_message_review.py` (new)

Tests:
- Regeneration service: correct prompt building with formality, language override, instruction
- Regeneration: original_body preserved on first regen, not overwritten on second
- Regeneration cost estimate accuracy
- Edit with reason: original_body saved, edit_reason required when body changes
- Edit without body change: edit_reason not required
- Disqualify campaign-only: campaign_contacts excluded, messages rejected
- Disqualify global: contacts.is_disqualified set, campaign exclusion also happens
- Contact picker filters out disqualified contacts
- Review summary counts accuracy
- Approval gate: blocked when drafts exist, allowed when all reviewed
- Review queue ordering: contact_score DESC, step ASC

### T17: E2E Tests (Playwright)
**File**: `tests/e2e/test_message_review_workflow.py` (new)

Tests:
- Navigate to campaign → Messages tab → click "Start Review" → focused review loads
- In focused review: approve message → auto-advances to next
- In focused review: reject message with reason → advances
- Edit message: change body, select reason tag, save → body updated, stays on message
- Regenerate: open dialog, set language to Czech + informal, confirm → message body changes
- Disqualify (campaign): confirm → skips to next contact's messages
- Outreach approval: all messages reviewed → button appears → confirm → campaign status = approved
- Keyboard shortcut A → approves current message

---

## Traceability Matrix

| AC | Task(s) | Test(s) |
|----|---------|---------|
| AC-1: Focused review navigation | T8, T9, T14 | T17: focused review loads |
| AC-2: Sequential approval | T5, T9 | T16: approval flow, T17: approve + advance |
| AC-3: Rejection with reason | T5, T9 | T16: reject flow, T17: reject + advance |
| AC-4: Edit with version tracking | T2, T5, T11 | T16: original_body preserved + edit_reason, T17: edit flow |
| AC-5: Regeneration with overrides | T3, T4, T10 | T16: regen service + prompt, T17: regen dialog |
| AC-6: Campaign-only exclusion | T6, T12 | T16: disqualify campaign, T17: disqualify flow |
| AC-7: Global disqualification | T6, T12 | T16: disqualify global + picker filter |
| AC-8: Outreach approval gate | T7, T13 | T16: approval gate, T17: outreach approval |
| AC-9: Outreach approval blocked | T7, T13 | T16: blocked with drafts |
| AC-10: Regeneration cost display | T3, T4, T10 | T16: cost estimate, T17: cost shown in dialog |

---

## Implementation Order

**Phase A: Backend foundation (T1 → T2 → T3 → T4, T5, T6, T7, T8)**
1. T1: Migration (schema)
2. T2: Model extensions
3. T3: Regeneration service (largest backend piece)
4. T4, T5, T6, T7, T8 in parallel (independent API endpoints)

**Phase B: Frontend core (T9 → T10, T11, T12, T13, T14, T15)**
1. T9: Focused review page (core shell)
2. T10, T11, T12 in parallel (dialogs, each independent)
3. T13: Outreach approval (depends on T7 API but independent of T9)
4. T14: Messages tab integration
5. T15: Keyboard shortcuts (last, builds on T9)

**Phase C: Testing (T16, T17)**
1. T16: Unit tests (can start after Phase A)
2. T17: E2E tests (after Phase B)
