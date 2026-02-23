# Spec: Contact Filtering, Selection & Campaign Management via Chat + UI (BL-052)

**Date**: 2026-02-23 | **Status**: Spec'd
**Priority**: Must Have | **Effort**: L
**Dependencies**: AGENT (agent-ready chat architecture), PB-001 (phase infrastructure)

---

## Problem Statement

Today, creating and populating campaigns requires manual navigation through multiple UI screens: browse contacts, apply filters, select, then switch to campaigns to create and assign. The marketing strategist chat has no ability to search contacts, create campaigns, or flag strategy conflicts. Users cannot leverage their AI strategist for the most critical GTM decision: **which contacts to target and how**.

This gap means:
- The AI strategist is blind to the user's contact pool when advising on campaign strategy.
- Contact selection is a mechanical process rather than a strategic one.
- Strategy conflicts (ICP mismatch, channel misalignment, segment overlap) are invisible until messages are generated.
- The user must context-switch between the AI conversation and multiple UI screens.

## User Stories

### Chat Path
1. As a founder, I want to ask my AI strategist "find me all CTOs at Tier 1 SaaS companies in DACH" and get a filtered contact list, so I can make targeting decisions conversationally.
2. As a founder, I want to tell the AI "create a campaign called DACH Enterprise Q1 and add those contacts" and have it done, so campaign creation is one sentence instead of a multi-step form.
3. As a founder, I want the AI to proactively warn me when selected contacts conflict with my strategy (wrong ICP, overlapping campaign, mismatched channel), so I avoid strategic mistakes.

### UI Path
4. As a founder, I want a filter panel on the contact selection screen with faceted counts, so I can visually narrow down my pool.
5. As a founder, I want to select contacts via checkboxes and assign them to a new or existing campaign in a modal, so I have a quick manual path.
6. As a founder, I want to see which contacts are already in other active campaigns, so I avoid duplicate outreach.

### Integration (Chat + UI)
7. As a founder, I want the AI chat to populate the UI filter panel when it finds contacts, so I can see and refine the AI's selections visually.
8. As a founder, I want UI selections to be available to the AI (e.g., "I selected these 15 contacts, what do you think?"), so the two paths work together.

---

## Acceptance Criteria

### AC-1: Chat-Based Contact Filtering

**Given** the AI chat has the `filter_contacts` tool available
**When** a user says "show me all senior contacts at Tier 1 companies in manufacturing"
**Then** the AI:
1. Calls `filter_contacts` with `{seniority_levels: ["C-Level", "VP"], tiers: ["Tier 1 - Platinum"], industries: ["Manufacturing"]}`
2. Returns a summary: "Found 23 contacts across 8 companies. Top contacts: [list of 5 with name, title, company, score]"
3. Offers next actions: "Want me to create a campaign with these contacts, or refine the filters?"

**Given** no contacts match the filters
**When** the AI calls `filter_contacts`
**Then** it responds: "No contacts match those criteria. Your closest options are: [suggest relaxed filters with counts]"

### AC-2: Chat-Based Campaign Creation

**Given** the AI has filtered a set of contacts (from AC-1 or user-provided IDs)
**When** the user says "create a campaign called DACH Manufacturing Q1 with those contacts"
**Then** the AI:
1. Calls `create_campaign` with `{name: "DACH Manufacturing Q1", description: "..."}`
2. Calls `assign_to_campaign` with the contact IDs and new campaign ID
3. Responds: "Created campaign 'DACH Manufacturing Q1' with 23 contacts. 19 are enrichment-ready, 4 need person enrichment. Want me to check for strategy conflicts?"

**Given** a campaign name already exists
**When** the AI calls `create_campaign`
**Then** it gets an error and asks: "A campaign called 'DACH Manufacturing Q1' already exists (draft, 15 contacts). Should I add to it, or create a new one with a different name?"

### AC-3: Chat-Based Contact-to-Campaign Assignment

**Given** an existing campaign (by name or ID)
**When** the user says "add contacts from Acme Corp and Globex to the Q1 campaign"
**Then** the AI:
1. Resolves company names to IDs
2. Finds all non-disqualified contacts at those companies
3. Calls `assign_to_campaign` with the resolved contact IDs
4. Reports: "Added 7 contacts from Acme Corp and 3 from Globex. 2 were already in the campaign (skipped)."

**Given** some contacts are already in another active campaign
**When** the AI assigns them
**Then** it flags: "3 contacts are also in 'EU SaaS Outbound' (approved, not yet sent). Adding them to both campaigns may result in duplicate outreach. Proceed?"

### AC-4: Strategy Conflict Detection and Flagging

**Given** the user asks the AI to add contacts to a campaign (or the AI proactively checks)
**When** `check_strategy_conflicts` is called
**Then** the AI checks and reports ALL of:

1. **ICP Mismatch**: Contacts whose company attributes don't match the strategy's ICP definition.
   - Example: "4 contacts are at companies with <20 employees. Your ICP targets 50-500 employees."

2. **Channel Mismatch**: Contacts missing contact info for the campaign's configured channels.
   - Example: "8 contacts have no email address, but this campaign includes email steps."

3. **Segment Overlap**: Contacts already in other active/approved campaigns.
   - Example: "3 contacts are in 'EU Tech Outbound' which is in review status."

4. **Timing Conflict**: Contacts who were recently contacted (within configurable cooldown period, default 30 days).
   - Example: "2 contacts were emailed 12 days ago via 'Q4 Follow-up'. Recommended cooldown: 30 days."

5. **Messaging Tone Mismatch**: Campaign tone setting conflicts with contact's known preferences or relationship stage.
   - Example: "This campaign uses 'cold_formal' tone, but 5 contacts have existing relationship_status='warm'."

**Given** no conflicts are found
**Then** the AI responds: "No strategy conflicts detected. All 23 contacts align with your ICP and have no scheduling conflicts."

### AC-5: Traditional UI — Filter Panel + Contact Table

**Given** the user is on the Contacts phase page or a campaign's "Add Contacts" screen
**When** the page loads
**Then**:
1. A filter panel appears on the left with faceted multi-value filters:
   - **Company filters**: tier, industry, company_size, geo_region, revenue_range, status
   - **Contact filters**: seniority_level, department, icp_fit, contact_score (range), language
   - **Enrichment**: enrichment_ready (toggle), ai_champion (toggle), min_ai_champion_score
   - **Exclusions**: hide_disqualified (default on), hide_in_active_campaigns (toggle)
2. Each filter shows counts reflecting other active filters (faceted search).
3. The contact table updates in real-time as filters change.
4. A summary bar shows: "Showing 147 of 2,608 contacts | 12 selected"

**Given** the user checks 15 contacts in the table
**When** they click "Add to Campaign"
**Then** a modal appears with:
- Option to select an existing draft/ready campaign from a dropdown
- Option to create a new campaign (name + optional description)
- A preview of enrichment readiness (X ready, Y need enrichment)
- A "Check Conflicts" button that runs AC-4 checks
- Confirm button that assigns contacts and closes modal

### AC-6: Integration Between Chat and UI

**Given** the AI chat has found and filtered contacts
**When** the user says "show these in the table" or the AI proactively offers
**Then**:
1. The UI filter panel updates to match the AI's filters
2. The contact table highlights the AI-selected contacts
3. The user can refine (add/remove selections) in the UI
4. URL updates with filter state (shareable/bookmarkable)

**Given** the user has selected contacts in the UI table
**When** they open the chat and say "what do you think about these contacts?"
**Then** the AI receives the selected contact IDs and analyzes: ICP fit distribution, enrichment readiness, channel coverage, and potential conflicts.

---

## Data Model Changes

### Campaigns Table — Modifications

The existing `campaigns` table needs the following changes to become independent of Lemlist:

```sql
-- Remove Lemlist dependency
-- (lemlist_campaign_id column remains but is deprecated — nullable, unused by new code)

-- Add strategy linking
ALTER TABLE campaigns ADD COLUMN strategy_id UUID REFERENCES strategy_documents(id);

-- Add targeting metadata
ALTER TABLE campaigns ADD COLUMN target_criteria JSONB DEFAULT '{}'::jsonb;
-- Stores the filter criteria used to build the campaign contact list, e.g.:
-- {"tiers": ["Tier 1"], "industries": ["SaaS"], "seniority_levels": ["C-Level", "VP"]}

-- Add conflict tracking
ALTER TABLE campaigns ADD COLUMN conflict_report JSONB DEFAULT '{}'::jsonb;
-- Last conflict check results, e.g.:
-- {"checked_at": "...", "icp_mismatches": 4, "channel_gaps": 8, "overlaps": 3}

-- Add cooldown period
ALTER TABLE campaigns ADD COLUMN contact_cooldown_days INT DEFAULT 30;
```

### New: campaign_overlap_log (Audit Trail)

```sql
CREATE TABLE campaign_overlap_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),       -- the campaign being built
    overlapping_campaign_id UUID NOT NULL REFERENCES campaigns(id),  -- the conflicting campaign
    overlap_type TEXT NOT NULL,  -- 'active_campaign', 'cooldown_violation', 'segment_overlap'
    resolved BOOLEAN DEFAULT false,
    resolved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Contacts Table — No Changes

The existing contacts table already has all the fields needed for filtering (seniority_level, department, icp_fit, contact_score, ai_champion_score, authority_score, language, is_disqualified, etc.).

### Messages Table — No Changes

The existing messages table already supports campaign_contact_id linking.

---

## API Contracts

### New Endpoints

#### POST /api/contacts/search

Advanced contact search endpoint designed for both UI faceted search and AI tool use.

**Request:**
```json
{
  "filters": {
    "tiers": ["Tier 1 - Platinum", "Tier 2 - Gold"],
    "industries": ["Manufacturing", "SaaS"],
    "seniority_levels": ["C-Level", "VP"],
    "departments": ["Engineering", "IT"],
    "company_sizes": ["51-200", "201-500"],
    "geo_regions": ["DACH", "Nordics"],
    "icp_fit": ["Strong", "Moderate"],
    "min_contact_score": 60,
    "min_ai_champion_score": 70,
    "enrichment_ready": true,
    "ai_champion_only": false,
    "exclude_disqualified": true,
    "exclude_campaign_ids": ["uuid-of-existing-campaign"],
    "tag_ids": ["uuid-of-tag"],
    "company_ids": ["uuid1", "uuid2"],
    "search": "acme"
  },
  "sort": {"field": "contact_score", "direction": "desc"},
  "page": 1,
  "page_size": 50,
  "include_facets": true
}
```

**Response:**
```json
{
  "contacts": [
    {
      "id": "uuid",
      "first_name": "Jan",
      "last_name": "Novak",
      "full_name": "Jan Novak",
      "job_title": "CTO",
      "email_address": "jan@acme.cz",
      "linkedin_url": "https://linkedin.com/in/jan-novak",
      "seniority_level": "C-Level",
      "department": "Engineering",
      "contact_score": 85,
      "ai_champion_score": 72,
      "icp_fit": "Strong",
      "language": "cs",
      "company": {
        "id": "uuid",
        "name": "Acme s.r.o.",
        "tier": "Tier 1 - Platinum",
        "industry": "Manufacturing",
        "company_size": "201-500",
        "geo_region": "CEE",
        "status": "Enriched L2"
      },
      "enrichment_ready": true,
      "active_campaigns": ["DACH Enterprise Q4"]
    }
  ],
  "total": 147,
  "page": 1,
  "page_size": 50,
  "facets": {
    "seniority_level": [{"value": "C-Level", "count": 23}, {"value": "VP", "count": 31}],
    "industry": [{"value": "Manufacturing", "count": 45}, {"value": "SaaS", "count": 38}]
  }
}
```

#### POST /api/contacts/search/summary

Lightweight endpoint for AI tool use — returns aggregate stats without full contact records.

**Request:** Same filter object as `/api/contacts/search`

**Response:**
```json
{
  "total": 147,
  "by_tier": {"Tier 1 - Platinum": 23, "Tier 2 - Gold": 45, "Tier 3 - Silver": 79},
  "by_industry": {"Manufacturing": 45, "SaaS": 38, "Fintech": 22},
  "by_seniority": {"C-Level": 23, "VP": 31, "Director": 48, "Manager": 45},
  "avg_contact_score": 67.3,
  "enrichment_ready": 112,
  "enrichment_needed": 35,
  "with_email": 134,
  "with_linkedin": 141,
  "in_active_campaigns": 18,
  "top_contacts": [
    {"id": "uuid", "full_name": "Jan Novak", "job_title": "CTO", "company_name": "Acme", "contact_score": 85}
  ]
}
```

#### POST /api/campaigns/{id}/conflict-check

Run strategy conflict analysis against a campaign's contacts.

**Request:**
```json
{
  "contact_ids": ["uuid1", "uuid2"],
  "strategy_id": "uuid-optional"
}
```

**Response:**
```json
{
  "conflicts": {
    "icp_mismatches": [
      {"contact_id": "uuid", "contact_name": "John Smith", "reason": "Company has 15 employees (ICP: 50-500)", "severity": "warning"}
    ],
    "channel_gaps": [
      {"contact_id": "uuid", "contact_name": "Jane Doe", "missing_channels": ["email"], "severity": "error"}
    ],
    "segment_overlaps": [
      {"contact_id": "uuid", "contact_name": "Bob Lee", "campaigns": [{"id": "uuid", "name": "Q4 Outbound", "status": "approved"}], "severity": "warning"}
    ],
    "cooldown_violations": [
      {"contact_id": "uuid", "contact_name": "Alice Yu", "last_contacted_at": "2026-02-10", "via_campaign": "Q4 Follow-up", "days_since": 13, "cooldown_days": 30, "severity": "info"}
    ],
    "tone_mismatches": [
      {"contact_id": "uuid", "contact_name": "Tom Brown", "campaign_tone": "cold_formal", "contact_relationship": "warm", "severity": "warning"}
    ]
  },
  "summary": {
    "total_contacts": 23,
    "clean": 15,
    "with_warnings": 6,
    "with_errors": 2
  }
}
```

### Modified Endpoints

#### PATCH /api/campaigns/{id}

Add `strategy_id`, `target_criteria`, and `contact_cooldown_days` to allowed fields.

#### POST /api/campaigns/{id}/contacts

Already exists with ICP filter support (`_resolve_contacts_by_filters`). Add:
- `exclude_campaign_ids` filter to avoid overlap
- Return `overlap_warnings` in response alongside `gaps`

### Existing Endpoints (No Changes Needed)

- `GET /api/campaigns` — list campaigns
- `POST /api/campaigns` — create campaign
- `GET /api/campaigns/{id}` — get campaign detail
- `GET /api/campaigns/{id}/contacts` — list campaign contacts
- `DELETE /api/campaigns/{id}/contacts` — remove contacts
- `POST /api/campaigns/{id}/enrichment-check` — check enrichment readiness
- `POST /api/companies/filter-counts` — company faceted search (reuse for contact pool views)
- `POST /api/contacts/filter-counts` — contact faceted search (already exists with 8 dimensions)

---

## Chat Tool Definitions

These tools are registered in the AI chat's tool registry (via the AGENT architecture from BL-011):

### filter_contacts

```json
{
  "name": "filter_contacts",
  "description": "Search and filter the user's contact pool. Returns matching contacts with summary stats. Use this when the user wants to find contacts by criteria like industry, seniority, tier, region, etc.",
  "input_schema": {
    "type": "object",
    "properties": {
      "tiers": {"type": "array", "items": {"type": "string"}, "description": "Company tier filter (e.g., 'Tier 1 - Platinum')"},
      "industries": {"type": "array", "items": {"type": "string"}, "description": "Company industry filter"},
      "seniority_levels": {"type": "array", "items": {"type": "string"}, "description": "Contact seniority (C-Level, VP, Director, Manager, Individual Contributor)"},
      "departments": {"type": "array", "items": {"type": "string"}, "description": "Contact department filter"},
      "geo_regions": {"type": "array", "items": {"type": "string"}, "description": "Company geographic region"},
      "company_sizes": {"type": "array", "items": {"type": "string"}, "description": "Company size range"},
      "min_contact_score": {"type": "integer", "description": "Minimum contact score (0-100)"},
      "enrichment_ready": {"type": "boolean", "description": "Only contacts with full enrichment (L1+L2+Person)"},
      "search": {"type": "string", "description": "Free text search across contact and company names"},
      "exclude_in_campaigns": {"type": "boolean", "description": "Exclude contacts already in active campaigns"},
      "limit": {"type": "integer", "description": "Max contacts to return (default 10 for chat, up to 50)"}
    }
  }
}
```

### create_campaign

```json
{
  "name": "create_campaign",
  "description": "Create a new outreach campaign. Returns the campaign ID. Use this when the user wants to start a new campaign.",
  "input_schema": {
    "type": "object",
    "required": ["name"],
    "properties": {
      "name": {"type": "string", "description": "Campaign name (must be unique within tenant)"},
      "description": {"type": "string", "description": "Campaign description/objective"},
      "strategy_id": {"type": "string", "description": "Link to a strategy document"},
      "target_criteria": {"type": "object", "description": "Filter criteria used to build the contact list (for audit trail)"}
    }
  }
}
```

### assign_to_campaign

```json
{
  "name": "assign_to_campaign",
  "description": "Add contacts to an existing campaign. Handles deduplication. Returns count of added/skipped contacts and enrichment gaps.",
  "input_schema": {
    "type": "object",
    "required": ["campaign_id"],
    "properties": {
      "campaign_id": {"type": "string", "description": "Target campaign UUID"},
      "contact_ids": {"type": "array", "items": {"type": "string"}, "description": "Specific contact UUIDs to add"},
      "company_ids": {"type": "array", "items": {"type": "string"}, "description": "Add all contacts from these companies"},
      "filters": {"type": "object", "description": "Same filter object as filter_contacts — resolves to contact IDs"}
    }
  }
}
```

### check_strategy_conflicts

```json
{
  "name": "check_strategy_conflicts",
  "description": "Check for strategy conflicts when adding contacts to a campaign. Flags ICP mismatches, channel gaps, segment overlaps, timing conflicts, and tone mismatches. Always call this before finalizing a campaign's contact list.",
  "input_schema": {
    "type": "object",
    "required": ["campaign_id"],
    "properties": {
      "campaign_id": {"type": "string", "description": "Campaign to check"},
      "contact_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional: check specific contacts instead of all campaign contacts"},
      "strategy_id": {"type": "string", "description": "Optional: strategy to check against (defaults to campaign's linked strategy)"}
    }
  }
}
```

### remove_from_campaign

```json
{
  "name": "remove_from_campaign",
  "description": "Remove contacts from a campaign. Only works on draft/ready campaigns.",
  "input_schema": {
    "type": "object",
    "required": ["campaign_id", "contact_ids"],
    "properties": {
      "campaign_id": {"type": "string", "description": "Campaign UUID"},
      "contact_ids": {"type": "array", "items": {"type": "string"}, "description": "Contact UUIDs to remove"}
    }
  }
}
```

---

## UI Wireframes (Text Descriptions)

### Contact Selection Screen (Contacts Phase / Campaign Add Contacts)

```
+------------------------------------------------------------------+
| Filter Panel (Left, 280px)     | Contact Table (Right, flex)      |
|                                |                                  |
| [Search: _____________]        | Showing 147 of 2,608 contacts   |
|                                | [x] Select All | Add to Campaign |
| COMPANY FILTERS                |                                  |
| Tier     [v] Tier 1 (23)      | [ ] Jan Novak, CTO               |
|              Tier 2 (45)       |     Acme s.r.o. | Tier 1 | 85pts|
|              Tier 3 (79)       |     jan@acme.cz | LinkedIn       |
|                                |     [In: DACH Q4]                |
| Industry [v] Manufacturing(45) |                                  |
|              SaaS (38)         | [x] Marie Dvorak, VP Engineering |
|              Fintech (22)      |     Globex a.s. | Tier 2 | 78pts|
|                                |     marie@globex.cz | LinkedIn   |
| Size     [v] 51-200 (67)      |                                  |
|              201-500 (42)      | [ ] ... (paginated / virtual)    |
|                                |                                  |
| CONTACT FILTERS                |                                  |
| Seniority [v] C-Level (23)    |                                  |
|               VP (31)          |                                  |
|               Director (48)    |                                  |
|                                |                                  |
| Score     [====|====] 0-100   |                                  |
| Champion  [ ] AI Champions     |                                  |
|                                |                                  |
| EXCLUSIONS                     |                                  |
| [x] Hide disqualified         |                                  |
| [ ] Hide in active campaigns  |                                  |
|                                |                                  |
| [Reset Filters]                |                                  |
+------------------------------------------------------------------+
```

### Add to Campaign Modal

```
+------------------------------------------+
| Add 15 Contacts to Campaign              |
|                                          |
| ( ) Existing campaign:                   |
|     [v] DACH Enterprise Q4 (draft, 23)   |
|         EU SaaS Outbound (ready, 45)     |
|                                          |
| (o) New campaign:                        |
|     Name: [DACH Manufacturing Q1_____]   |
|     Desc: [Manufacturing outreach____]   |
|                                          |
| --- Enrichment Readiness ---             |
| 12 contacts ready                        |
|  3 need person enrichment                |
|                                          |
| --- Conflict Check ---                   |
| [Check for Conflicts]                    |
| (after click:)                           |
| ! 2 contacts overlap with EU SaaS (warn)|
| ! 1 contact has no email (error)         |
| v 12 contacts clean                      |
|                                          |
| [Cancel]            [Add to Campaign]    |
+------------------------------------------+
```

### Campaign Detail — Contact Tab Enhancement

The existing campaign detail view (`GET /api/campaigns/{id}`) adds:
- Conflict badges next to contacts with warnings
- "Run Conflict Check" button in the campaign header
- Filter/sort controls within the campaign's contact list
- Bulk actions: remove selected, check enrichment, check conflicts

---

## Edge Cases

### Empty Results
- **No contacts match filters**: AI suggests relaxing criteria with specific alternatives and counts.
- **No campaigns exist**: AI offers to create one. UI shows "No campaigns yet" state.

### Conflicting Filters
- **Mutually exclusive filters** (e.g., Tier 1 + industry that has no Tier 1 companies): Show 0 results with hint about which filter to relax.
- **Search + filters**: Text search applies on top of faceted filters. If search yields 0, filters reset to show full search results.

### Strategy Conflicts
- **No strategy linked**: AI skips ICP mismatch check, notes "No strategy document linked — I can't check ICP alignment. Consider linking a strategy."
- **Strategy has no ICP defined**: AI skips ICP check with a note.
- **Contact in 3+ campaigns**: Flag with higher severity. Multiple overlaps compound the risk of outreach fatigue.

### Duplicate Campaign Names
- API returns 409 Conflict. AI and UI both handle by suggesting rename or merge.
- Implementation: add unique constraint `UNIQUE(tenant_id, name)` where `is_active = true`.

### Concurrent Access
- Two users adding contacts to the same campaign: `campaign_contacts` unique constraint prevents duplicates. Second request gets `skipped` count.
- Filter counts may be slightly stale (acceptable for UX; counts refresh on filter change).

### Large Contact Pools
- Tenants with 10,000+ contacts: Pagination required. AI tool returns top N with total count. UI uses virtual scroll.
- Faceted counts: Use the existing `_build_base_where` pattern from company_routes.py for cross-filtered facet queries.

### Chat Context Limits
- AI tool results are summarized (top 5-10 contacts, aggregate stats) to avoid flooding the chat context.
- Full result set is available via UI (AI can say "I found 147 contacts — showing top 10 here, or open the Contacts tab to see all").

---

## Implementation Notes

### Phasing

**Phase 1: Chat Tools + API** (requires AGENT)
1. `POST /api/contacts/search` endpoint
2. `POST /api/contacts/search/summary` endpoint
3. `POST /api/campaigns/{id}/conflict-check` endpoint
4. Chat tool handlers: `filter_contacts`, `create_campaign`, `assign_to_campaign`, `check_strategy_conflicts`, `remove_from_campaign`
5. Migration: add `strategy_id`, `target_criteria`, `conflict_report`, `contact_cooldown_days` to campaigns

**Phase 2: UI** (can start in parallel)
1. Contact Selection screen with filter panel
2. "Add to Campaign" modal
3. Campaign detail enhancements (conflict badges, bulk actions)
4. Chat-to-UI filter sync

**Phase 3: Conflict Intelligence**
1. ICP mismatch detection (reads strategy_documents.extracted_data)
2. Cooldown/timing analysis (reads email_send_log + linkedin_send_queue)
3. Tone mismatch logic
4. `campaign_overlap_log` audit table

### Reuse Existing Code

- **`_resolve_contacts_by_filters`** (campaign_routes.py): Already supports tier, industry, icp_fit, seniority, tags, min_score, enrichment_ready filters. Extend rather than rewrite.
- **`POST /api/contacts/filter-counts`** (contact_routes.py): Already has 8 facet dimensions with include/exclude toggles. Reuse the faceted search pattern.
- **`POST /api/companies/filter-counts`** (company_routes.py): Faceted company search with same pattern. Cross-reference for company-level filters.
- **`_check_enrichment_gaps`** (campaign_routes.py): Already checks L1/L2/Person completion per contact. Reuse directly.

### Security

- All endpoints scoped by `tenant_id` (existing pattern).
- Chat tools execute with the authenticated user's permissions (via JWT from the chat session).
- Conflict check reads but never modifies contact/campaign data.
- `campaign_overlap_log` is an append-only audit trail.

---

## Migration

### Migration 030: campaign_targeting.sql

```sql
-- Add strategy linking and targeting metadata to campaigns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS strategy_id UUID REFERENCES strategy_documents(id);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS target_criteria JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS conflict_report JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS contact_cooldown_days INT DEFAULT 30;

-- Overlap audit log
CREATE TABLE IF NOT EXISTS campaign_overlap_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    overlapping_campaign_id UUID NOT NULL REFERENCES campaigns(id),
    overlap_type TEXT NOT NULL,
    resolved BOOLEAN DEFAULT false,
    resolved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaign_overlap_tenant ON campaign_overlap_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_campaign_overlap_contact ON campaign_overlap_log(contact_id);
```

---

## Open Questions

1. **Cooldown scope**: Should cooldown apply per-channel (email cooldown separate from LinkedIn) or globally? **Recommendation**: Per-channel, since LinkedIn connection requests are one-time and email sequences have natural spacing.

2. **ICP extraction format**: The `strategy_documents.extracted_data` JSONB needs a stable schema for ICP fields that the conflict checker can query. **Recommendation**: Define a schema for `extracted_data.icp` with fields like `company_size_range`, `industries`, `geo_regions`, `seniority_targets`.

3. **Campaign name uniqueness**: Strictly unique per tenant, or allow archived campaigns to reuse names? **Recommendation**: Unique among active campaigns only (`WHERE is_active = true`).
