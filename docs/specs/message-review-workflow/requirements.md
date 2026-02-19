# Message Review Workflow — Requirements

**Feature**: Enhanced message review with focused review queue, per-message regeneration, version tracking, contact disqualification, and campaign outreach approval.

**Backlog**: New item (extends BL-036) | **Theme**: Outreach Engine

## Purpose

The current review workflow shows messages in a grouped list with basic approve/edit/reject actions. This enhancement transforms review into a focused, sequential process where every message must be explicitly approved or rejected. Reviewers can regenerate messages with different language, tone, or custom instructions — with cost visibility. Manual edits preserve the original LLM output and capture structured feedback (edit reason tags) for future prompt improvement. Contacts can be disqualified directly from the review page. Campaign-level outreach approval gates the handoff to delivery.

## Functional Requirements

### FR-1: Message Review Queue (List View)
Show all campaign messages grouped by contact (current behavior), with enhanced summary:
- Per-contact status: N approved / M rejected / K pending of total
- Per-campaign totals: approved, rejected, pending review, disqualified contacts
- Filter by: status, channel, step
- Click any message card to enter focused review mode starting from that message

### FR-2: Focused Message Review (Drill-in View)
Full-screen single-message view with sequential, gated navigation:
- **Content**: Message body (+ subject for email), channel badge, step label, tone, language
- **Contact context**: Name, title, company, LinkedIn URL, ICP fit, contact score, enrichment highlights
- **Company context**: Name, domain, tier, industry, country, summary
- **Actions**: Approve, Reject (with reason), Edit, Regenerate, Disqualify Contact
- **Navigation**: Must approve, reject, or disqualify to advance to next message. No skipping.
- **Ordering**: Messages ordered by contact (contact_score DESC), then by step within contact. All messages for Contact A before Contact B.
- **Completion**: When all messages reviewed, show completion summary with counts.
- **Keyboard shortcuts**: A (approve), R (reject), E (edit), G (regenerate), D (disqualify), Esc (back to list)

### FR-3: Manual Editing with Version Tracking
- Edit body and subject (email) inline in focused review mode
- On first edit or regeneration, auto-save original LLM output to `original_body` / `original_subject` (immutable once set)
- When saving an edit, require an edit reason tag (select from predefined + custom text)
- Predefined edit reason tags: `too_formal`, `too_casual`, `wrong_tone`, `wrong_language`, `too_long`, `too_short`, `factually_wrong`, `off_topic`, `generic`, `other`
- Edit does NOT auto-approve — reviewer explicitly approves or continues editing
- Save button saves the edit; separate Approve button approves the message

### FR-4: Per-Message Regeneration
- Regenerate a single message with override parameters:
  - **Language**: Dropdown (English, Czech, German, French, Spanish, etc.)
  - **Formality**: Toggle — Formal / Informal (controls address form: Vy/Ty in Czech, Vous/Tu in French, Sie/Du in German)
  - **Tone**: Dropdown (Professional, Casual, Bold, Empathetic)
  - **Custom instruction**: One-line text field (max 200 chars), optional. Passed to LLM as additional context.
- Show expected regeneration cost before confirming (based on Claude Haiku pricing + estimated tokens)
- On confirm: call Claude API with updated parameters, replace message body (save original in `original_body`)
- Track regeneration count and last regeneration config per message

### FR-5: Contact Disqualification from Review
Two options available from the review page:
- **Campaign-only exclusion**: Sets `campaign_contacts.status = 'excluded'`. All messages for this contact in this campaign get status `'rejected'` with `review_notes = 'Contact excluded from campaign'`. Advance past all remaining messages for this contact.
- **Global disqualification**: Sets `contacts.is_disqualified = true` with timestamp. Also performs campaign exclusion (above). Contact hidden from future campaign contact pickers (filtered by `is_disqualified = false`).
- Confirmation dialog for global disqualification (irreversible from review page).

### FR-6: Campaign Outreach Approval
- Campaign detail shows review progress: X approved / Y rejected / Z pending
- "Approve Outreach" button appears when zero messages are in `draft` status (all approved or rejected)
- Clicking shows summary dialog:
  - Approved messages by channel (e.g., "12 LinkedIn invites, 10 Email 1, 8 Email 2")
  - Excluded contacts count
  - Total contacts receiving outreach
- Confirm transitions campaign from `review` → `approved`
- API validates: no draft messages remain before allowing transition

### FR-7: Regeneration Cost Display
- Before confirming regeneration, show:
  - Estimated cost (USD) based on Claude Haiku pricing
  - Token estimate (input + output)
  - Model name
- Cost based on enrichment context size for this specific contact (not a generic estimate)

## Non-Functional Requirements

### NFR-1: Performance
- Focused review mode loads in < 500ms (message + context pre-fetched)
- Regeneration completes in < 10 seconds
- Review queue state (current position, filters) preserved in URL params

### NFR-2: Data Integrity
- `original_body` is immutable once set — never overwritten by subsequent edits or regenerations
- Edit reason tags stored alongside the message for structured analysis
- Regeneration config stored per message for prompt improvement analysis

### NFR-3: Security
- Regeneration endpoint requires `editor` role
- Disqualification requires `editor` role
- Global disqualification is auditable (timestamp + user stored)
- Custom instruction text sanitized (no prompt injection via instructions)

## Acceptance Criteria

### AC-1: Focused Review Navigation
**Given** a campaign in "review" status with 3 contacts (each with 2 messages)
**When** I click a message in the list view
**Then** I see a focused single-message view with full contact and company context
**And** I cannot navigate to the next message without approving, rejecting, or disqualifying

### AC-2: Sequential Approval
**Given** I'm in focused review mode viewing Contact A's first message
**When** I click Approve
**Then** the message status becomes "approved" with `approved_at` timestamp
**And** I automatically advance to Contact A's second message

### AC-3: Rejection with Reason
**Given** I'm in focused review mode
**When** I click Reject
**Then** I must enter a rejection reason before confirming
**And** the message status becomes "rejected" with `review_notes` populated
**And** I advance to the next message

### AC-4: Edit with Version Tracking
**Given** I'm reviewing a message that has never been edited
**When** I edit the body and save
**Then** the original LLM output is preserved in `original_body`
**And** I must select an edit reason tag from the predefined list
**And** the edited body is saved but the message remains in its current status (not auto-approved)

### AC-5: Regeneration with Overrides
**Given** I'm reviewing a message
**When** I click Regenerate and set language=Czech, formality=Informal, tone=Casual, instruction="mention our mutual connection Jan"
**Then** I see the estimated cost before confirming
**And** on confirm, the LLM generates a new message in Czech with informal address (tykani)
**And** the original body is preserved in `original_body` (if not already set)
**And** `regen_count` increments and `regen_config` stores the parameters used

### AC-6: Campaign-Only Exclusion
**Given** I'm reviewing Contact A's message
**When** I choose "Skip in this campaign"
**Then** `campaign_contacts.status` for Contact A becomes "excluded"
**And** all of Contact A's messages in this campaign become "rejected"
**And** I advance past all remaining Contact A messages to Contact B

### AC-7: Global Disqualification
**Given** I'm reviewing Contact A's message
**When** I choose "Disqualify contact" and confirm the dialog
**Then** `contacts.is_disqualified` is set to true with timestamp
**And** Contact A is excluded from this campaign (same as AC-6)
**And** Contact A does not appear in future campaign contact pickers

### AC-8: Outreach Approval Gate
**Given** a campaign with 20 messages where 15 are approved and 5 are rejected
**When** I view the campaign detail
**Then** I see "Approve Outreach" button (since 0 messages are drafts)
**And** clicking it shows a summary: "15 messages approved for 12 contacts (8 LinkedIn, 7 Email)"
**And** confirming transitions the campaign to "approved" status

### AC-9: Outreach Approval Blocked
**Given** a campaign with 20 messages where 15 are approved, 3 are rejected, and 2 are still drafts
**When** I view the campaign detail
**Then** I do NOT see "Approve Outreach" button
**And** I see "2 messages pending review" indicator

### AC-10: Regeneration Cost Display
**Given** I click Regenerate on a message for a contact with full enrichment
**When** the regeneration dialog opens
**Then** I see "Estimated cost: ~$0.001 (800 input + 200 output tokens, Claude Haiku)"
**And** the estimate reflects the actual enrichment context size for this contact

## Out of Scope

- **A/B variant generation** — covered by BL-043
- **Batch regeneration** (regenerate all messages at once) — future enhancement
- **Email delivery / Lemlist export** — covered by BL-039, BL-040
- **Template editing from review page** — use campaign settings tab
- **Multi-user concurrent review** — single reviewer per campaign for now
- **Undo after approve/reject** — use "Reset to Draft" from list view (existing functionality)
