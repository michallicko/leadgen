# BL-044: Custom Prompt Instructions

**Status**: Spec'd
**Sprint**: 3B
**Priority**: Must Have
**Effort**: S
**Theme**: Outreach Engine
**Depends on**: BL-035 (Message Generation Engine)

## Problem

The `generation_config.custom_instructions` key is already consumed by the prompt builder — `build_generation_prompt()` reads it at `generation_prompts.py:249` and appends it after tone/language/formality instructions. However, the MessageGenTab UI only exposes **tone**. Users cannot add campaign-specific instructions like "mention our recent funding round" or "reference the prospect's recent LinkedIn post" without directly editing the JSON via API.

## Solution

Add a Custom Instructions textarea to the MessageGenTab, below the tone selector. This is a **frontend-only change** — the backend already supports it.

## User Stories

### US-1: Add custom instructions
**As a** user preparing a campaign
**I want to** add free-text instructions that guide message generation
**So that** every generated message reflects campaign-specific context (e.g., event references, product launches, seasonal angles).

## Technical Approach

### No API changes needed

The existing infrastructure already works:
- `PATCH /api/campaigns/<id>` accepts `generation_config` JSONB updates
- `build_generation_prompt()` reads `custom_instructions` and appends to prompt
- `message_generator.py` passes full `generation_config` to prompt builder

### Frontend: MessageGenTab changes

**New field** below the tone selector (existing `EditableSelect`):

```tsx
<EditableTextarea
  label="Custom Instructions"
  value={generationConfig.custom_instructions || ''}
  onChange={(val) => updateGenerationConfig({ custom_instructions: val })}
  maxLength={2000}
  placeholder="e.g., Mention our Series A funding. Reference prospect's recent company news. Keep under 100 words."
  helpText="These instructions are appended to every message generation prompt for this campaign."
/>
```

**Character counter:** Show `{remaining}/2000` below the textarea, gray text, red when <100 remaining.

**Save behavior:** Same as tone — save on blur via existing `PATCH /api/campaigns/<id>` with updated `generation_config`.

**Save feedback**: After successful save-on-blur, show an inline "Saved" checkmark that fades after 2 seconds (matching PlaybookPage's SaveStatus pattern).

**Accessibility**: textarea has `aria-describedby` linking to both the help text and character counter. Character limit warning at <100 remaining announced via `aria-live="polite"`.

**Layout:** Below tone selector, above the step configuration section. Full-width textarea, 3 rows default, auto-expand up to 6 rows.

### Integration with BL-037 (Template Library) and BL-038 (Clone Campaign)

- **Save as template:** `custom_instructions` is included in `default_config` (it's part of `generation_config`)
- **Load template:** `custom_instructions` applied from `template.default_config`
- **Clone:** `custom_instructions` copied (it's part of `generation_config`)

No extra work needed — these features copy `generation_config` wholesale.

### Validation

- Max 2000 characters (enforced client-side via `maxLength`)
- Backend already truncates at prompt level if somehow exceeded
- No server-side validation change needed — JSONB accepts any string

## Acceptance Criteria

### AC-1: Custom instructions field visible
```
Given I am on a campaign's Message Generation tab
When I look below the tone selector
Then I see a Custom Instructions textarea with placeholder text and character counter
```

### AC-2: Instructions saved to generation_config
```
Given I type instructions in the textarea and leave the field (blur)
When the campaign is saved
Then generation_config.custom_instructions contains my text
And reloading the page shows the saved instructions
```

### AC-3: Instructions used in generation
```
Given I set custom_instructions to "Mention our Berlin office opening"
When messages are generated for this campaign
Then the LLM prompt includes "Mention our Berlin office opening" in the instructions section
And generated messages reference the Berlin office
```

### AC-4: Character limit
```
Given I type in the custom instructions field
When the text approaches 2000 characters
Then the counter shows remaining characters
And input is prevented beyond 2000 characters
```

### AC-5: Empty state
```
Given I have not set custom instructions
When messages are generated
Then generation works normally without any instruction injection
And the textarea shows the placeholder text
```

## Task Breakdown

| # | Task | Effort |
|---|------|--------|
| 1 | Frontend: Add EditableTextarea to MessageGenTab | S |
| 2 | Frontend: Character counter component | S |
| 3 | Manual test: verify instructions appear in generated messages | S |
