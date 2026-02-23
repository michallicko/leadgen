# Spec: Campaign Message Generation Customization (BL-057)

**Date**: 2026-02-23 | **Status**: Spec'd
**Priority**: Should Have | **Effort**: M
**Dependencies**: BL-055 (LLM cost logging), BL-056 (token credit system for cost display)

---

## Problem Statement

Message generation is a black box. Users click "Generate Messages", wait, and get results with no control over the output's tone, language, or quality. When messages miss the mark, users must regenerate one by one, lose the previous version, and have no reference for what "good" looks like.

**Current pain points:**

1. **No campaign-level language control** -- The `generation_config` stores `tone` and `custom_instructions`, but there is no language selector on the MessageGenTab. Language defaults to `"en"` silently. The RegenerationDialog supports language per-message, but this must be repeated for each individual message.

2. **Limited tone vocabulary** -- Only 4 tones (professional, casual, bold, empathetic). Real outreach needs more nuance: consultative, direct, friendly, provocative, academic, etc.

3. **No example messages** -- Users have no reference for what the AI will produce for each step. They must generate the entire campaign to see output, burning credits on potentially unwanted results.

4. **Regeneration is per-message only** -- `regenerate_message()` works on a single message ID. There is no way to regenerate all messages for a campaign step, or all messages for a contact, or re-run the entire campaign with different settings.

5. **No version history** -- The `original_body`/`original_subject` fields capture the first version only. On second regeneration, the intermediate version is lost. `regen_count` tracks how many times, but there is no way to revert to version N.

6. **Cost shown in USD** -- The MessageGenTab cost dialog and RegenerationDialog both display `$X.XX` in USD. Per BL-056 design rules, only super_admins see USD; regular users see token credits.

## Current State

### Backend (what exists)

| Component | File | What It Does |
|-----------|------|-------------|
| `message_generator.py` | `api/services/` | Core generation engine. `start_generation()` spawns background thread. `_generate_all()` loops contacts x steps. `regenerate_message()` handles single-message regen with tone/language/formality/instruction overrides. |
| `generation_prompts.py` | `api/services/` | Prompt templates. `SYSTEM_PROMPT` is hardcoded. `build_generation_prompt()` assembles context sections. `CHANNEL_CONSTRAINTS` defines per-channel limits. `FORMALITY_INSTRUCTIONS` for language-specific address forms. |
| `llm_logger.py` | `api/services/` | `log_llm_usage()` creates `LlmUsageLog` entries with tenant_id, operation, tokens, cost_usd. |
| `campaign_routes.py` | `api/routes/` | `POST /generate` starts generation. `POST /cost-estimate` returns estimated cost. `GET /generation-status` polls progress. `DELETE /generate` cancels. |
| `message_routes.py` | `api/routes/` | `POST /messages/<id>/regenerate` regenerates one message. `GET /messages/<id>/regenerate/estimate` estimates single-message cost. |

### Frontend (what exists)

| Component | File | What It Does |
|-----------|------|-------------|
| `MessageGenTab.tsx` | `pages/campaigns/tabs/` | Template loader, step toggle, tone dropdown (4 options), custom instructions textarea, cost estimate + confirm dialog, generate button, progress modal. |
| `RegenerationDialog.tsx` | `pages/messages/` | Single-message regen with language, formality, tone, instruction overrides. Shows estimated cost in USD. |
| `GenerationProgressModal.tsx` | `components/campaign/` | Polls `/generation-status` every 2s, shows progress bar and contact statuses. |

### Data Model (what exists)

**Campaign.generation_config** (JSONB):
```json
{
  "tone": "professional",
  "language": "en",
  "custom_instructions": "...",
  "strategy_snapshot": { ... },
  "cancelled": false
}
```

**Message columns** (relevant):
- `tone`, `language` -- per-message values
- `original_body`, `original_subject` -- first version only (immutable once set)
- `regen_count` -- integer counter
- `regen_config` -- JSONB with last regen settings
- `generation_cost_usd` -- cumulative cost

### Gaps

1. `generation_config` has no `language` field in the UI (only in the JSON schema)
2. `generation_config` has no `formality` field (only available during single-message regen)
3. No `message_versions` table -- version history limited to original + current
4. No example message generation endpoint
5. No bulk regeneration endpoint (campaign-wide or per-step)
6. Cost displayed in USD, not credits

---

## User Stories

**US-1: Tone & Language Control**
As a founder, I want to set the tone and language for my entire campaign before generating, so that all messages match my outreach style from the start.

**US-2: Example Messages**
As a founder, I want to see 5 example messages for each campaign step before generating, so that I know what to expect and can adjust settings if the style is wrong.

**US-3: Bulk Regeneration**
As a founder, I want to regenerate all messages for a campaign (or just one step) with different settings, so that I can iterate on the entire campaign without reviewing each message individually.

**US-4: Version History**
As a founder, I want to see previous versions of a message and revert to any version, so that I don't lose good messages when experimenting with regeneration.

**US-5: Token Cost Visibility**
As a founder, I want to see the estimated token credit cost before generating and the actual cost after, so that I can manage my AI budget.

---

## Acceptance Criteria

### AC-1: Tone Selection

**Given** a campaign in Draft or Ready status
**When** the user opens the Message Generation tab
**Then** they see a tone selector with options: professional, casual, bold, empathetic, consultative, direct, friendly, provocative
**And** changing the tone updates `campaigns.generation_config.tone`
**And** the selected tone is used for all subsequent message generation

### AC-2: Language Selection

**Given** a campaign in Draft or Ready status
**When** the user opens the Message Generation tab
**Then** they see a language dropdown (English, Czech, German, French, Spanish, Italian, Polish, Dutch, Portuguese, Swedish, Norwegian, Finnish, Danish)
**And** for languages with formal/informal address (cs, de, fr, es, it, pt, pl, nl), a formality toggle appears
**And** changing language/formality updates `campaigns.generation_config.language` and `campaigns.generation_config.formality`
**And** these values are used for all subsequent generation

### AC-3: Example Messages Per Step

**Given** a campaign with at least one contact and at least one enabled step
**When** the user clicks "Preview Examples" on a step
**Then** the system generates 3 example messages using the first 3 contacts (or fewer if the campaign has fewer)
**And** examples are displayed in a slide-over panel showing contact name, company, and message body
**And** examples are NOT saved as real messages -- they are ephemeral, for preview only
**And** the estimated credit cost for the preview is shown before generation

**Given** no contacts in the campaign
**When** the user clicks "Preview Examples"
**Then** they see a message: "Add contacts to preview example messages"

### AC-4: Bulk Regeneration

**Given** a campaign with generated messages
**When** the user clicks "Regenerate All" or "Regenerate Step N"
**Then** a confirmation dialog shows: number of messages to regenerate, estimated credit cost, and option to adjust tone/language/instruction
**And** on confirmation, all affected messages are regenerated in the background (same thread pattern as initial generation)
**And** previous versions are preserved in the `message_versions` table
**And** the campaign status transitions to `generating` during regeneration and back to `review` when complete

**Given** a user regenerates an individual message (existing flow)
**When** the regeneration completes
**Then** the previous body/subject are saved to `message_versions` (not just `original_body`)

### AC-5: Token Cost Display

**Given** a regular user (not super_admin) views the cost estimate dialog
**When** estimated cost is displayed
**Then** cost is shown in credits (e.g., "~340 credits") not USD

**Given** a super_admin views the cost estimate dialog
**When** estimated cost is displayed
**Then** cost is shown in both credits and USD (e.g., "~340 credits ($0.34)")

**Given** generation has completed
**When** the user views the generation status or campaign detail
**Then** actual credit cost is shown for the generation run

---

## Data Model Changes

### 1. New table: `message_versions`

```sql
CREATE TABLE message_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    subject TEXT,
    body TEXT NOT NULL,
    tone TEXT,
    language TEXT,
    generation_cost_usd NUMERIC(10, 4),
    generation_config JSONB,       -- snapshot of config used for this version
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(message_id, version_number)
);
CREATE INDEX idx_message_versions_message ON message_versions(message_id);
```

### 2. Campaign.generation_config additions

No schema change needed -- `generation_config` is already JSONB. New keys:

```json
{
  "tone": "consultative",
  "language": "cs",
  "formality": "formal",
  "custom_instructions": "...",
  "strategy_snapshot": { ... }
}
```

### 3. New tone values

Extend the tone vocabulary (no migration needed -- it's a free-text field):

| Value | Label | Description |
|-------|-------|-------------|
| `professional` | Professional | Business formal, clear and concise |
| `casual` | Casual | Relaxed, conversational |
| `bold` | Bold | Confident, direct, attention-grabbing |
| `empathetic` | Empathetic | Understanding, pain-focused |
| `consultative` | Consultative | Advisory, question-driven |
| `direct` | Direct | Short, to-the-point, no filler |
| `friendly` | Friendly | Warm, personable, relationship-first |
| `provocative` | Provocative | Challenging assumptions, thought-provoking |

---

## API Contracts

### POST /api/campaigns/:id/preview-examples

Generate ephemeral example messages for a campaign step. Does NOT save to the database.

**Request:**
```json
{
  "step": 1,
  "count": 3
}
```

**Response:**
```json
{
  "examples": [
    {
      "contact_name": "Jan Novak",
      "company_name": "Acme Corp",
      "subject": "Quick question about...",
      "body": "Hi Jan, ...",
      "channel": "email"
    }
  ],
  "cost": {
    "credits": 45,
    "input_tokens": 2400,
    "output_tokens": 600,
    "model": "claude-haiku-3-5-20241022"
  }
}
```

**Notes:**
- Uses the first N contacts in the campaign (ordered by contact_score DESC)
- Uses the campaign's current `generation_config` (tone, language, formality, custom_instructions)
- Logs to `llm_usage_log` with `operation="message_preview"`
- Returns actual cost (not estimated) since the messages are actually generated

### POST /api/campaigns/:id/regenerate-bulk

Regenerate all messages or messages for a specific step.

**Request:**
```json
{
  "scope": "all" | "step",
  "step": 2,
  "overrides": {
    "tone": "consultative",
    "language": "cs",
    "formality": "formal",
    "instruction": "Focus on AI automation benefits"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "status": "generating",
  "messages_to_regenerate": 45,
  "estimated_credits": 1350
}
```

**Notes:**
- Sets campaign status to `generating` during bulk regen
- Versions all existing messages before overwriting
- Background thread (same pattern as `start_generation`)
- Only regenerates messages with status `draft` or `approved` (not `rejected` or `sent`)

### POST /api/campaigns/:id/regenerate-bulk/estimate

Estimate cost of bulk regeneration without executing.

**Request:**
```json
{
  "scope": "all" | "step",
  "step": 2
}
```

**Response:**
```json
{
  "messages_to_regenerate": 45,
  "estimated_credits": 1350,
  "estimated_cost_usd": 1.35,
  "model": "claude-haiku-3-5-20241022"
}
```

### GET /api/messages/:id/versions

List all versions of a message.

**Response:**
```json
{
  "versions": [
    {
      "version_number": 1,
      "subject": "Original subject",
      "body": "Original body...",
      "tone": "professional",
      "language": "en",
      "cost_credits": 15,
      "created_at": "2026-02-23T10:00:00Z"
    },
    {
      "version_number": 2,
      "subject": "Updated subject",
      "body": "Updated body...",
      "tone": "consultative",
      "language": "cs",
      "cost_credits": 18,
      "created_at": "2026-02-23T11:30:00Z"
    }
  ],
  "current_version": 3
}
```

### POST /api/messages/:id/revert

Revert a message to a previous version.

**Request:**
```json
{
  "version_number": 1
}
```

**Response:**
```json
{
  "ok": true,
  "reverted_to": 1,
  "body": "Original body...",
  "subject": "Original subject"
}
```

**Notes:**
- Saves current body/subject as a new version before reverting
- Revert is a copy operation (doesn't delete newer versions)
- Sets message status back to `draft`

---

## UI Design

### MessageGenTab Additions

The existing tab gets three additions below the template step list:

**1. Campaign Generation Config Panel** (replaces current inline tone/instructions)

```
+----------------------------------------------------+
| Generation Settings                                |
+----------------------------------------------------+
| Tone:      [  Consultative  v ]                    |
| Language:  [  Czech         v ]  [Formal | Informal] |
| Custom instructions:                               |
| [                                                 ]|
| [  Focus on AI automation and time savings.       ]|
| [                                                 ]|
+----------------------------------------------------+
```

**2. Example Preview Button** (per step)

Each step row in the template list gets a "Preview" button:

```
[x] Em  Step 1: Initial Email         email     [Preview]
[x] LI  Step 2: LinkedIn Connection   linkedin  [Preview]
[x] Em  Step 3: Follow-up Email       email     [Preview]
```

Clicking "Preview" opens a slide-over panel:

```
+--------------------------------------------------+
| Preview: Step 1 - Initial Email                  |
| Generating 3 examples...  ~45 credits            |
+--------------------------------------------------+
| Jan Novak (Acme Corp)                            |
| Subject: Quick question about your AI roadmap    |
| Hi Jan, I noticed Acme recently expanded its     |
| automation team. We've helped similar companies...|
+--------------------------------------------------+
| Eva Horakova (TechCo)                            |
| Subject: Thought on your digital transformation  |
| Hi Eva, Your recent talk at WebExpo about...     |
+--------------------------------------------------+
| Petr Svoboda (DataWorks)                         |
| Subject: Data engineering + AI question          |
| Hi Petr, DataWorks' migration to Snowflake...    |
+--------------------------------------------------+
| [Close]                                          |
+--------------------------------------------------+
```

**3. Cost Display** (updated)

```
Before generation:
  "~1,200 credits  (60 messages x ~20 credits each)"

After generation:
  "Actual cost: 1,147 credits"

Super_admin sees additionally:
  "~1,200 credits ($1.20)"
```

### Bulk Regeneration (Campaign Detail)

After initial generation (campaign in `review` status), the MessageGenTab shows:

```
+----------------------------------------------------+
| Regeneration                                        |
+----------------------------------------------------+
| [Regenerate All]  [Regenerate Step: [Step 1 v] ]   |
|                                                     |
| Adjust settings before regenerating:               |
| Tone:      [  Direct  v ]                          |
| Language:  [  English  v ]                          |
| Instruction: [Be more specific about ROI          ]|
|                                                     |
| Estimated cost: ~1,200 credits                     |
| Previous versions will be preserved.               |
+----------------------------------------------------+
```

### Message Version History (Message Review Page)

The existing MessageReviewPage / MessageCard gets a "Version History" section:

```
+--------------------------------------------------+
| Version History                     [v3 current]  |
+--------------------------------------------------+
| v1  Professional / English  2026-02-23 10:00     |
|     "Hi Jan, I noticed Acme recently..."          |
|     [Revert to v1]                                |
+--------------------------------------------------+
| v2  Consultative / Czech   2026-02-23 11:30      |
|     "Dobry den Jene, zaujalo me, ze Acme..."     |
|     [Revert to v2]                                |
+--------------------------------------------------+
| v3  Direct / Czech         2026-02-23 14:00      |
|     "Jene, automatizace v Acme by mohla..."       |
|     (current)                                     |
+--------------------------------------------------+
```

---

## How Example Messages Work

**Approach: On-demand AI generation** (not pre-curated templates)

Rationale: Pre-curated templates would need maintenance per industry/channel and would not use the campaign's actual enrichment data. AI-generated previews use the real contacts and enrichment context, so the preview accurately represents what the full generation will produce.

**Flow:**
1. User clicks "Preview" on a step
2. Frontend calls `POST /api/campaigns/:id/preview-examples` with `{ step: N, count: 3 }`
3. Backend picks the top 3 contacts by `contact_score`
4. For each, calls `build_generation_prompt()` with the campaign's `generation_config`
5. Calls Claude API (same model as generation)
6. Returns the generated messages WITHOUT saving to the `messages` table
7. Logs cost to `llm_usage_log` with `operation="message_preview"`

**Cost:** ~15-20 credits per preview message (same as generation). 3 previews = ~45-60 credits.

---

## Token Cost Integration

### Estimation (before generation)

The existing `estimate_generation_cost()` function already computes cost in USD. Add a conversion:

```python
credits = int(cost_usd * 1000)  # 1 credit = $0.001
```

Return both `estimated_credits` and `estimated_cost_usd` from the API. Frontend displays credits by default, USD only for super_admin.

### Tracking (during generation)

The existing `log_llm_usage()` already tracks every API call. `compute_cost()` returns exact USD. Credit conversion happens at display time:

```python
credits = int(log_entry.cost_usd * 1000)
```

### Display (after generation)

The campaign's `generation_cost` column stores total USD. API response adds:

```json
{
  "generation_cost": 1.147,
  "generation_credits": 1147
}
```

Frontend shows `1,147 credits`. Super_admin sees `1,147 credits ($1.15)`.

---

## Edge Cases

### Regeneration while campaign is active (sending)

- Block bulk regeneration if campaign status is `approved` or `exported`
- Individual message regen remains possible for `draft` messages only
- Error message: "Cannot regenerate messages that are already approved or sent"

### Language mismatch with contact

- Campaign language applies to all messages. A Czech-language campaign targeting English-speaking contacts will generate Czech messages regardless.
- The AI system prompt gets the contact's country (`hq_country`) which helps it adapt formality naturally.
- Future improvement: per-contact language override (out of scope for this spec).

### Cost exceeds budget (requires BL-056)

- Before generation: if estimated credits exceed remaining budget, show warning
- During generation: if budget runs out mid-generation, the background thread stops gracefully (same pattern as cancellation)
- After generation: budget enforcement happens in `check_budget()` called before each Claude API call

### Preview cost

- Previews cost real credits. Show estimated cost before generating previews.
- Limit to 3 examples per preview request (not 5, to keep costs reasonable)
- Previews are ephemeral -- no database persistence, no cleanup needed

### Version table growth

- `message_versions` grows with each regen. For 100 contacts x 3 steps x 5 regens = 1,500 version rows per campaign.
- This is manageable. No pruning needed in v1.
- Future: add campaign-level version snapshot for bulk operations

### Revert semantics

- Revert copies the old version's body/subject to the message's current body/subject
- Creates a new version entry (the "revert" itself becomes a version)
- Sets status back to `draft` so the message goes through review again
- Does not restore the old tone/language on the `messages` row (those reflect generation params, not display params)

---

## Migration Plan

### Migration 0XX: Add message_versions table

```sql
CREATE TABLE message_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    subject TEXT,
    body TEXT NOT NULL,
    tone TEXT,
    language TEXT,
    generation_cost_usd NUMERIC(10, 4),
    generation_config JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(message_id, version_number)
);
CREATE INDEX idx_message_versions_message ON message_versions(message_id);
```

### Backfill

After migration, backfill v1 for all existing messages that have `original_body`:

```sql
INSERT INTO message_versions (message_id, version_number, subject, body, tone, language, generation_cost_usd, created_at)
SELECT id, 1, original_subject, original_body, tone, language, generation_cost_usd, created_at
FROM messages
WHERE original_body IS NOT NULL;
```

---

## Implementation Order

1. **Migration**: Add `message_versions` table + backfill
2. **Backend: Version tracking**: Modify `regenerate_message()` to write to `message_versions` before overwriting. Add `GET /messages/:id/versions` and `POST /messages/:id/revert` endpoints.
3. **Backend: Extended generation config**: Add `formality` to generation_config, extend tone vocabulary in prompts
4. **Frontend: Config panel**: Add language dropdown + formality toggle + extended tone selector to MessageGenTab
5. **Backend: Preview examples**: Add `POST /campaigns/:id/preview-examples` endpoint
6. **Frontend: Preview panel**: Add "Preview" button per step, slide-over panel
7. **Backend: Bulk regeneration**: Add `POST /campaigns/:id/regenerate-bulk` and estimate endpoints
8. **Frontend: Bulk regen UI**: Add regeneration controls to MessageGenTab (post-generation state)
9. **Frontend: Version history**: Add version list to message review, revert button
10. **Frontend: Credit cost display**: Replace USD with credits in all cost dialogs. Show USD for super_admin only. (Depends on BL-056 being available)
