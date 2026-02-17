# Spec: Campaign CRUD + Data Model (BL-031)

**Date**: 2026-02-17 | **Status**: In Progress

## Purpose

Create the foundational data model and CRUD operations for outreach campaigns. Campaigns organize contacts for AI-personalized message generation across multiple channels (LinkedIn, email, call scripts).

## Requirements

1. **Campaign data model** — Extend existing `campaigns` table with status, template config, generation config, and tracking fields.
2. **Campaign contacts junction** — Track which contacts are assigned to a campaign with per-contact status.
3. **Campaign templates** — System-provided and tenant-custom templates defining message sequences.
4. **Campaign CRUD API** — Full lifecycle management of campaigns (create, read, update, delete).
5. **Campaign list page** — React page in the "Reach" pillar showing campaigns with key stats.
6. **Multi-tenant safety** — All queries scoped by `tenant_id`.

## Data Model Changes

### Migration 018: campaign_tables.sql

**ALTER `campaigns` ADD columns:**
- `status TEXT DEFAULT 'draft'` — draft | ready | generating | review | approved | exported | archived
- `description TEXT`
- `template_config JSONB DEFAULT '[]'` — ordered message steps
- `generation_config JSONB DEFAULT '{}'` — tone, language, persona, instructions
- `total_contacts INT DEFAULT 0`
- `generated_count INT DEFAULT 0`
- `generation_cost NUMERIC(10,4) DEFAULT 0`
- `generation_started_at TIMESTAMPTZ`
- `generation_completed_at TIMESTAMPTZ`

**NEW TABLE `campaign_contacts`:**
- `id UUID PK`
- `campaign_id UUID FK→campaigns`
- `contact_id UUID FK→contacts`
- `tenant_id UUID FK→tenants`
- `status TEXT DEFAULT 'pending'` — pending | enrichment_ok | enrichment_needed | generating | generated | failed | excluded
- `enrichment_gaps JSONB DEFAULT '[]'`
- `generation_cost NUMERIC(10,4) DEFAULT 0`
- `error TEXT`
- `added_at TIMESTAMPTZ`
- `generated_at TIMESTAMPTZ`
- `UNIQUE(campaign_id, contact_id)`

**NEW TABLE `campaign_templates`:**
- `id UUID PK`
- `tenant_id UUID` (NULL = system template)
- `name TEXT NOT NULL`
- `description TEXT`
- `steps JSONB` — ordered message step definitions
- `default_config JSONB` — default generation config
- `is_system BOOLEAN DEFAULT false`
- `created_at, updated_at TIMESTAMPTZ`

**ALTER `messages` ADD:**
- `campaign_contact_id UUID FK→campaign_contacts`

### template_config JSONB shape
```json
[
  {"step": 1, "channel": "linkedin_connect", "label": "LinkedIn Invite", "enabled": true, "needs_pdf": false, "variant_count": 1},
  {"step": 2, "channel": "email", "label": "Email 1", "enabled": true, "needs_pdf": false, "variant_count": 1},
  {"step": 3, "channel": "email", "label": "Email 2", "enabled": true, "needs_pdf": false, "variant_count": 1},
  {"step": 4, "channel": "linkedin_message", "label": "LI Followup + PDF", "enabled": true, "needs_pdf": true, "variant_count": 1},
  {"step": 5, "channel": "email", "label": "Email 3", "enabled": false, "needs_pdf": false, "variant_count": 1}
]
```

## API Contracts

### GET /api/campaigns
Returns all campaigns for the tenant.

**Response:**
```json
{
  "campaigns": [
    {
      "id": "uuid",
      "name": "Q1 Outreach",
      "status": "draft",
      "description": "...",
      "owner_name": "Alice",
      "total_contacts": 42,
      "generated_count": 0,
      "generation_cost": 0,
      "created_at": "2026-02-17T...",
      "updated_at": "2026-02-17T..."
    }
  ]
}
```

### POST /api/campaigns
Create a new campaign.

**Request:**
```json
{
  "name": "Q1 Outreach",
  "description": "First outreach wave",
  "owner_id": "uuid",
  "template_id": "uuid"
}
```

### GET /api/campaigns/:id
Campaign detail with config and contact stats.

### PATCH /api/campaigns/:id
Update campaign fields (name, description, status, template_config, generation_config).

### DELETE /api/campaigns/:id
Soft delete — only allowed for `draft` campaigns. Sets status to `archived`.

## Acceptance Criteria

- [ ] Migration 018 applies cleanly on PostgreSQL
- [ ] Campaign CRUD endpoints work with tenant scoping
- [ ] Campaign list page renders under Reach pillar
- [ ] PATCH validates status transitions
- [ ] DELETE only works on draft campaigns
- [ ] Unit tests cover all routes
- [ ] Existing tests still pass

## Edge Cases

- Creating a campaign without template_id: starts with empty template_config
- Creating from template_id: copies template steps into template_config
- Status transitions: draft → ready (bidirectional), ready → generating (one-way), etc.
- Campaign with 0 contacts is allowed (draft state)
