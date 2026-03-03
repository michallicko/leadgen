# BL-038: Clone Campaign

**Status**: Spec'd
**Sprint**: 3B
**Priority**: Must Have
**Effort**: S
**Theme**: Outreach Engine
**Depends on**: BL-031 (Campaign CRUD)

## Problem

When a user wants to run a similar campaign for a different contact list, they must manually recreate the template steps, tone, language, sender config, and description. There is no way to duplicate an existing campaign's configuration.

## Solution

Add a "Clone" action on campaigns that creates a new draft campaign copying all configuration but no contacts or messages.

## User Stories

### US-1: Clone a campaign
**As a** user with a working campaign setup
**I want to** clone it into a new draft campaign
**So that** I can reuse the configuration for a different set of contacts without manual recreation.

## Technical Approach

### API

**`POST /api/campaigns/<id>/clone`** — Clone campaign configuration.
- No request body required (optional `{ name? }` override)
- Creates new campaign with:
  - `name`: `"{original.name} (Copy)"` (or provided name)
  - `description`: copied from original
  - `owner_id`: copied from original
  - `template_config`: copied from original
  - `generation_config`: copied from original, excluding `strategy_snapshot` and `cancelled`
  - `sender_config`: copied from original
  - `status`: `"draft"`
  - `total_contacts`: 0
  - `generated_count`: 0
  - `generation_cost`: 0.0
- NOT copied: contacts, messages, generation timestamps, `airtable_record_id`, `lemlist_campaign_id`
- Returns: `{ id, name, status: "Draft" }`
- Requires `editor` role

### Frontend

**Campaign list page:**
- Clone icon button on each campaign row (next to existing actions)
- On click: immediate clone, redirect to new campaign detail

**Campaign detail page:**
- Clone button in header actions (alongside existing edit/archive actions)
- Same behavior: clone + redirect

**Loading state**: Clone button shows spinner and is disabled during the POST request to prevent double-clicks.

**Icon**: Duplicate icon (two overlapping rectangles) consistent with the app's inline SVG style.

**Post-clone:**
- Redirect to new campaign's detail page
- Toast: "Campaign cloned as '{name} (Copy)'"

### Edge cases
- Cloning an archived campaign: allowed (creates a fresh draft)
- Cloning a campaign with no steps: allowed (creates empty draft)
- Name collision: append " (2)", " (3)" etc. if "{name} (Copy)" already exists

## Acceptance Criteria

### AC-1: Clone creates correct copy
```
Given I have a campaign with template_config, generation_config, and sender_config
When I click Clone
Then a new draft campaign is created with the same config
And name is "{original} (Copy)"
And it has 0 contacts and 0 messages
```

### AC-2: Clone excludes runtime data
```
Given the original campaign has strategy_snapshot in generation_config
When I clone it
Then the clone's generation_config does not include strategy_snapshot or cancelled
```

### AC-3: Redirect after clone
```
Given I clone a campaign
When the clone is created
Then I am redirected to the new campaign's detail page
And a success toast is shown
```

### AC-4: Clone from any status
```
Given I have campaigns in draft, review, approved, and archived status
When I clone any of them
Then a new draft campaign is created successfully
```

## Task Breakdown

| # | Task | Effort |
|---|------|--------|
| 1 | API: POST /api/campaigns/<id>/clone | S |
| 2 | Frontend: Clone button on campaign list + detail | S |
| 3 | Frontend: Post-clone redirect + toast | S |
