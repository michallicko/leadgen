# BL-037: Template Library

**Status**: Spec'd
**Sprint**: 3B
**Priority**: Must Have
**Effort**: S
**Theme**: Outreach Engine
**Depends on**: BL-031 (Campaign CRUD)

## Problem

Campaign templates exist in the DB (`campaign_templates` table with `name`, `steps`, `default_config`, `is_system` flag) and the campaign creation form already supports a template dropdown, but there is no UI or API to **create** templates from an existing campaign. Templates can only be seeded via migration (system templates). Users who find a working config must manually recreate it for every new campaign.

## Solution

Add a "Save as Template" action on existing campaigns and a template management section in Settings.

## User Stories

### US-1: Save campaign config as template
**As a** user with a working campaign configuration
**I want to** save it as a reusable template
**So that** I can apply the same step structure and generation settings to future campaigns.

### US-2: Manage my templates
**As a** namespace admin
**I want to** view, rename, and delete my saved templates
**So that** I can keep my template library organized.

## Technical Approach

### API endpoints

**`POST /api/campaign-templates`** — Create template from scratch.
- Body: `{ name, description?, steps, default_config }`
- Sets `tenant_id` = current tenant, `is_system` = false
- Returns: `{ id, name, description, steps, default_config, created_at }`

**`POST /api/campaigns/<id>/save-as-template`** — Convenience: create template from campaign.
- Body: `{ name, description? }`
- Copies `campaign.template_config` → `steps`
- Copies `campaign.generation_config` → `default_config` (excluding `strategy_snapshot`, `cancelled`)
- Returns: `{ id, name }`

**`PATCH /api/campaign-templates/<id>`** — Update name/description.
- Body: `{ name?, description? }`
- Only allowed for tenant-owned templates (`is_system = false`)

**`DELETE /api/campaign-templates/<id>`** — Delete template.
- Only allowed for tenant-owned templates
- Returns 403 for system templates

### Frontend

**Campaign detail page:**
- "Save as Template" button in the campaign header/actions area
- Visible when `template_config` has ≥1 step
- Opens modal: name input (pre-filled with campaign name), description textarea
- On save: calls `POST /api/campaigns/<id>/save-as-template`, shows success toast

**Settings page → Templates section:**
- Table: name, step count, description (truncated), created date
- Actions: rename (inline edit), delete (with confirmation dialog)
- System templates shown with badge, no delete/rename allowed
- Empty state: "No custom templates yet. Save a campaign as a template to get started."

**Campaign creation (existing):**
- Template dropdown already works via `GET /api/campaign-templates`
- No changes needed — new templates appear automatically

### Data flow

```
Campaign (template_config + generation_config)
  → POST /save-as-template
    → campaign_templates row (steps + default_config)
      → GET /campaign-templates (appears in creation dropdown)
        → POST /campaigns with template_id (copies into new campaign)
```

### Excluded from template snapshot
- `generation_config.strategy_snapshot` (runtime data, varies per generation)
- `generation_config.cancelled` (transient flag)

## Acceptance Criteria

### AC-1: Save campaign as template
```
Given I have a campaign with template_config containing ≥1 step
When I click "Save as Template" and enter a name
Then a new campaign_template is created with my tenant_id
And steps = campaign.template_config
And default_config = campaign.generation_config (minus strategy_snapshot, cancelled)
```

### AC-2: Use saved template
```
Given I saved a template from a previous campaign
When I create a new campaign and select that template
Then the new campaign.template_config = template.steps
And generation_config = template.default_config
```

### AC-3: Manage templates
```
Given I have saved templates
When I go to Settings → Templates
Then I see my templates listed with name, step count, created date
And I can rename or delete my templates
And I cannot delete or rename system templates
```

### AC-4: Validation
```
Given I try to save a campaign with 0 steps as a template
Then the Save as Template button is disabled or hidden
```

## Task Breakdown

| # | Task | Effort |
|---|------|--------|
| 1 | API: POST /api/campaign-templates (create) | S |
| 2 | API: POST /api/campaigns/<id>/save-as-template | S |
| 3 | API: PATCH + DELETE /api/campaign-templates/<id> | S |
| 4 | Frontend: Save as Template button + modal on campaign detail | S |
| 5 | Frontend: Template management section in Settings | S |
