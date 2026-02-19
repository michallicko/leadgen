# Message Review Workflow — Design

## Affected Components

### Backend (API)
- `api/models.py` — Message model + Contact model extensions
- `api/routes/message_routes.py` — New regenerate endpoint, edit reason support
- `api/routes/campaign_routes.py` — Review summary, outreach approval validation
- `api/services/message_generator.py` — Single-message regeneration function
- `api/services/generation_prompts.py` — Formality parameter in prompt building
- `api/display.py` — New display mappings for edit reasons
- `migrations/020_message_review_workflow.sql` — Schema changes

### Frontend (React SPA)
- `frontend/src/pages/messages/MessageReviewPage.tsx` — **New**: Focused single-message review
- `frontend/src/pages/messages/RegenerationDialog.tsx` — **New**: Regen config + cost estimate
- `frontend/src/pages/messages/DisqualifyDialog.tsx` — **New**: Campaign-only vs global choice
- `frontend/src/pages/messages/EditPanel.tsx` — **New**: Edit body + reason tag selector
- `frontend/src/pages/messages/ReviewProgress.tsx` — **New**: Progress bar + stats
- `frontend/src/pages/campaigns/tabs/MessagesTab.tsx` — Enhanced: drill-in entry point
- `frontend/src/pages/campaigns/OutreachApprovalDialog.tsx` — **New**: Summary + confirm
- `frontend/src/pages/campaigns/CampaignDetailPage.tsx` — Approval button + review stats
- `frontend/src/api/queries/useMessages.ts` — New mutation hooks
- `frontend/src/api/queries/useCampaigns.ts` — Review summary query

## Data Model Changes

### Migration 020: `message_review_workflow`

#### `messages` table — new columns:
```sql
ALTER TABLE messages ADD COLUMN original_body TEXT;
ALTER TABLE messages ADD COLUMN original_subject TEXT;
ALTER TABLE messages ADD COLUMN edit_reason TEXT;        -- tag: too_formal, too_casual, etc.
ALTER TABLE messages ADD COLUMN edit_reason_text TEXT;   -- free text for 'other' reason
ALTER TABLE messages ADD COLUMN regen_count INTEGER DEFAULT 0;
ALTER TABLE messages ADD COLUMN regen_config JSONB;      -- last regen params: {language, formality, tone, instruction}
```

`original_body` / `original_subject`: Set on first edit or regeneration. Never overwritten once set. Represents the first LLM generation output for this message.

`edit_reason`: One of: `too_formal`, `too_casual`, `wrong_tone`, `wrong_language`, `too_long`, `too_short`, `factually_wrong`, `off_topic`, `generic`, `other`. Nullable (only set when human edits).

`regen_config`: JSONB storing the parameters of the most recent regeneration:
```json
{
  "language": "cs",
  "formality": "informal",
  "tone": "casual",
  "instruction": "mention our mutual connection Jan"
}
```

#### `contacts` table — new columns:
```sql
ALTER TABLE contacts ADD COLUMN is_disqualified BOOLEAN DEFAULT false;
ALTER TABLE contacts ADD COLUMN disqualified_at TIMESTAMPTZ;
ALTER TABLE contacts ADD COLUMN disqualified_reason TEXT;
```

`is_disqualified`: Global flag. When true, contact is filtered out of campaign contact pickers.

## API Contracts

### 1. Regenerate Message
```
POST /api/messages/<id>/regenerate
Auth: @require_role("editor")

Request:
{
  "language": "cs",        // optional, default: message's current language
  "formality": "informal", // optional: "formal" | "informal"
  "tone": "casual",        // optional, default: message's current tone
  "instruction": "mention our mutual connection Jan"  // optional, max 200 chars
}

Response (200):
{
  "id": "uuid",
  "body": "Ahoj Jane, ...",
  "subject": null,
  "original_body": "Hello Jane, ...",   // preserved from first generation
  "regen_count": 1,
  "regen_config": {"language": "cs", "formality": "informal", "tone": "casual", "instruction": "..."},
  "generation_cost_usd": 0.0012
}
```

**Logic**:
1. Load message + associated contact + company + enrichment context
2. If `original_body` is null, set it to current `body` (preserve first generation)
3. Build prompt with override parameters (language, formality, tone, instruction)
4. Call Claude Haiku API
5. Parse response, update `body` (and `subject` for email)
6. Increment `regen_count`, set `regen_config`
7. Log cost via `llm_logger`
8. Return updated message

### 2. Regeneration Cost Estimate
```
GET /api/messages/<id>/regenerate/estimate
Auth: @require_auth

Response (200):
{
  "estimated_cost_usd": 0.0012,
  "input_tokens": 850,
  "output_tokens": 200,
  "model": "claude-haiku-3-5-20241022",
  "channel": "linkedin_connect",
  "max_chars": 300
}
```

**Logic**: Compute prompt size from actual enrichment context for this contact. Estimate output tokens from channel max_chars. Apply Haiku pricing.

### 3. Update Message (Extended)
```
PATCH /api/messages/<id>
Auth: @require_role("editor")

Request (existing fields + new):
{
  "body": "edited body text",
  "subject": "edited subject",       // email only
  "status": "approved",
  "edit_reason": "too_formal",        // new: required when body changes
  "edit_reason_text": "needs more personal touch",  // new: optional, for 'other'
  "review_notes": "...",
  "approved_at": "2026-02-19T..."
}

Response (200): updated message object
```

**New logic**: When `body` is changed and differs from current value:
- If `original_body` is null, set it to the previous `body` value
- Require `edit_reason` to be provided (400 if missing)

### 4. Disqualify Contact from Campaign
```
POST /api/campaigns/<campaign_id>/disqualify-contact
Auth: @require_role("editor")

Request:
{
  "contact_id": "uuid",
  "scope": "campaign" | "global",
  "reason": "Not relevant for this outreach"  // optional
}

Response (200):
{
  "contact_id": "uuid",
  "scope": "campaign",
  "messages_rejected": 3,
  "campaign_contacts_status": "excluded"
}
```

**Logic**:
- **campaign**: Set `campaign_contacts.status = 'excluded'`. Update all messages for this contact in this campaign to `status = 'rejected'`, `review_notes = 'Contact excluded from campaign'`.
- **global**: Above + set `contacts.is_disqualified = true`, `disqualified_at = now()`, `disqualified_reason = reason`.

### 5. Campaign Review Summary
```
GET /api/campaigns/<id>/review-summary
Auth: @require_auth

Response (200):
{
  "total_messages": 40,
  "approved": 30,
  "rejected": 8,
  "draft": 2,
  "excluded_contacts": 3,
  "active_contacts": 12,
  "by_channel": {
    "linkedin_connect": {"approved": 10, "rejected": 3},
    "email": {"approved": 20, "rejected": 5}
  },
  "can_approve_outreach": false,
  "pending_reason": "2 messages still in draft status"
}
```

### 6. Campaign Status Transition (Extended)
```
PATCH /api/campaigns/<id>
{
  "status": "approved"
}
```

**New validation for review → approved**: Query messages via campaign_contacts. If any message has `status = 'draft'`, reject with 400: `"Cannot approve outreach: N messages still pending review"`.

### 7. Review Queue Data
```
GET /api/campaigns/<id>/review-queue
Auth: @require_auth
Query params: ?status=draft&channel=&step=

Response (200):
{
  "queue": [
    {
      "message": { ...full message object... },
      "contact": { ...full contact with enrichment... },
      "company": { ...full company with enrichment... },
      "position": 1,
      "total": 24
    },
    ...
  ],
  "stats": {
    "total": 40,
    "approved": 16,
    "rejected": 0,
    "draft": 24,
    "excluded": 0
  }
}
```

Returns messages ordered by contact_score DESC, then step ASC. Includes full enrichment context for each message so the focused view can render without additional API calls. Filters applied server-side.

## UX Flow

### Review Queue Entry
```
Campaign Detail → Messages Tab
  │
  ├── Filter bar (status, channel)
  ├── Stats: "24 pending · 16 approved · 0 rejected"
  ├── Contact groups (existing grouped view)
  │     └── Click any message card
  │           └── Enter Focused Review Mode
  │
  └── "Start Review" button → enters focused mode from first unreviewed message
```

### Focused Review Mode
```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back to list          Review: 5 of 24          [Progress ▓▓░░░░]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─── Contact ────────────────────┐  ┌─── Company ──────────────┐   │
│  │ Jane Smith                      │  │ Acme Corp               │   │
│  │ VP of Sales · ICP: Strong (85)  │  │ SaaS · Tier 1 · Prague  │   │
│  │ LinkedIn ↗                      │  │ acme.com                │   │
│  └─────────────────────────────────┘  └─────────────────────────┘   │
│                                                                       │
│  Step 1: LinkedIn Invite  ·  Channel: linkedin_connect  ·  ≤300ch   │
│  Tone: Professional  ·  Language: English                             │
│                                                                       │
│  ┌─── Message ────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Hi Jane, I noticed Acme Corp recently expanded into the        │  │
│  │  Nordic market. We help SaaS companies like yours streamline    │  │
│  │  their GTM operations...                                        │  │
│  │                                                                  │  │
│  │  278 / 300 chars                                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────────┐  ┌─────────┐ │
│  │Approve │  │ Reject │  │  Edit  │  │ Regenerate ↻ │  │Disqualify│ │
│  │  (A)   │  │  (R)   │  │  (E)   │  │    (G)       │  │   (D)   │ │
│  └────────┘  └────────┘  └────────┘  └──────────────┘  └─────────┘ │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### Edit Mode (inline)
```
┌─── Edit Message ──────────────────────────────────────────────────┐
│                                                                    │
│  [Subject: ... ]  (email only)                                     │
│                                                                    │
│  ┌── textarea ──────────────────────────────────────────────────┐ │
│  │ Hi Jane, I noticed Acme Corp recently expanded into the      │ │
│  │ Nordic market...                                              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│  278 / 300 chars                                                   │
│                                                                    │
│  Edit reason: [too_formal ▾]  Notes: [optional text...........]   │
│                                                                    │
│  [Cancel]  [Save Edit]                                             │
└────────────────────────────────────────────────────────────────────┘
```

### Regeneration Dialog
```
┌─── Regenerate Message ────────────────────────────────────────────┐
│                                                                    │
│  Language:   [Czech ▾]                                             │
│  Formality:  ○ Formal (Vy)   ● Informal (Ty)                     │
│  Tone:       [Casual ▾]                                           │
│                                                                    │
│  Custom instruction (optional):                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ mention our mutual connection Jan Novak                      │ │
│  └──────────────────────────────────────────────────────────────┘ │
│  0 / 200 chars                                                     │
│                                                                    │
│  ┌─ Cost Estimate ──────────────────────────────────────────────┐ │
│  │  ~$0.001  ·  ~850 input + 200 output tokens  ·  Haiku 3.5   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  [Cancel]  [Regenerate]                                            │
└────────────────────────────────────────────────────────────────────┘
```

### Disqualify Dialog
```
┌─── Disqualify Contact ────────────────────────────────────────────┐
│                                                                    │
│  Jane Smith · VP of Sales · Acme Corp                             │
│                                                                    │
│  ○ Skip in this campaign                                          │
│    Excludes from this campaign only. 3 messages will be rejected. │
│    Contact remains available for other campaigns.                  │
│                                                                    │
│  ○ Disqualify contact globally                                    │
│    Marks contact as disqualified across the system.               │
│    Will not appear in future campaign contact pickers.            │
│    ⚠ This cannot be undone from the review page.                 │
│                                                                    │
│  Reason (optional): [________________________________]            │
│                                                                    │
│  [Cancel]  [Confirm]                                               │
└────────────────────────────────────────────────────────────────────┘
```

### Outreach Approval Dialog
```
┌─── Approve Outreach ──────────────────────────────────────────────┐
│                                                                    │
│  Campaign: "Q1 Nordic SaaS Outreach"                              │
│                                                                    │
│  ┌─ Summary ────────────────────────────────────────────────────┐ │
│  │  12 contacts receiving outreach                               │ │
│  │  3 contacts excluded                                          │ │
│  │                                                                │ │
│  │  30 messages approved:                                        │ │
│  │    · 12 LinkedIn invites                                      │ │
│  │    · 10 Email 1                                               │ │
│  │    · 8 Email 2                                                │ │
│  │                                                                │ │
│  │  8 messages rejected                                          │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  [Cancel]  [Approve Outreach]                                      │
└────────────────────────────────────────────────────────────────────┘
```

## Architecture Decisions

### Version tracking: columns on `messages` vs separate table
**Decision**: Columns on `messages` (`original_body`, `edit_reason`).
**Rationale**: We only need the first-generation-vs-final-approved comparison. A full version history table adds complexity without clear benefit for the LLM feedback use case. If needed later, we can add a `message_edits` table. The structured signal comes from `edit_reason` tags, not from intermediate versions.

### Regeneration: replace vs variant
**Decision**: Replace body, preserve original in `original_body`.
**Rationale**: User chose this approach. Keeps review queue clean (one message per step). The `original_body` + `regen_config` provide the LLM feedback signal. The existing variant system (A/B) remains available for BL-043.

### Formality as separate dimension from tone
**Decision**: Formality is a binary toggle (formal/informal) separate from tone.
**Rationale**: Formality controls pronoun choice (Ty/Vy, Tu/Vous, Du/Sie) which is orthogonal to tone (professional can be Ty in Czech startup culture). The prompt explicitly instructs the LLM about address form.

### Edit does not auto-approve
**Decision**: Editing saves the body but does not change message status.
**Rationale**: In the current system, edit always auto-approves. The new focused review flow separates these concerns — the reviewer may want to edit and then regenerate, or edit and then reject (save the edit as feedback but don't approve).

### Review queue: server-fetched vs client-paginated
**Decision**: Server returns full review queue via `/review-queue` endpoint.
**Rationale**: The focused review needs full enrichment context per message (contact + company + enrichment). Fetching this per-message would be slow. Pre-fetching the queue with all context allows instant navigation. For large campaigns (100+ contacts), we can paginate in batches of 20.

## Edge Cases

1. **All messages for a contact rejected**: Contact still counted in active contacts (not excluded). Only explicit disqualification changes campaign_contacts status.
2. **Regeneration during generation**: Blocked — messages in "generating" status cannot be regenerated. Only draft/approved/rejected messages.
3. **Edit after regeneration**: The `original_body` preserves the FIRST generation. A regeneration after edit updates `body` but doesn't change `original_body`. The chain is: original LLM → (optional edit) → (optional regen) → (optional edit) → final approved.
4. **Global disqualification of contact with messages in multiple campaigns**: Only affects the current campaign's messages. Other campaigns' messages remain unchanged but the contact won't be pickable for NEW campaigns.
5. **Campaign approval with excluded contacts**: Excluded contacts' messages (all rejected) don't block approval. Only `draft` status messages block.
6. **Empty campaign after disqualifications**: If all contacts are excluded, campaign can still be approved (0 approved messages). Show warning: "No messages will be sent."

## Security Considerations

- **Custom instruction injection**: The instruction field is max 200 chars and prepended to the prompt as-is. The system prompt already instructs the LLM about output format. Risk is low (same trust level as `custom_instructions` on campaign). Sanitize for control characters.
- **Disqualification audit**: Global disqualification sets `disqualified_at` timestamp. The acting user is identified via JWT. For full audit trail, log to `audit_log` table.
- **Tenant isolation**: All queries filter by `tenant_id`. Regeneration endpoint verifies message belongs to the authenticated tenant.
