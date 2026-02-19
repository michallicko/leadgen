# Entity Detail Cleanup — Design

**Date**: 2026-02-19

## Affected Components

### API (Backend)
- `api/routes/company_routes.py` — GET `/companies/<id>` endpoint (add missing fields + stage_completions)
- `api/routes/contact_routes.py` — GET `/contacts/<id>` endpoint (expand enrichment object)
- `api/models.py` — No changes (models already have all fields)

### Frontend (React SPA)
- `frontend/src/pages/companies/CompanyDetail.tsx` — Major restructure: tabs, section reorg, field changes
- `frontend/src/pages/contacts/ContactDetail.tsx` — Tab structure, add enrichment fields, remove deprecated
- `frontend/src/api/queries/useCompanies.ts` — Update `CompanyDetail` type with new fields
- `frontend/src/api/queries/useContacts.ts` — Update `ContactDetail` type with new fields
- `frontend/src/components/ui/DetailField.tsx` — May need minor additions (link field variant)

## Data Model

No database changes. All fields already exist from the enrichment field audit migrations (019-023). This feature is purely about API exposure and UI rendering.

### Company Detail API Response — New Fields

```json
{
  "...existing fields...",
  "website_url": "https://example.com",
  "linkedin_url": "https://linkedin.com/company/example",
  "logo_url": "https://logo.clearbit.com/example.com",
  "last_enriched_at": "2026-02-15T10:30:00Z",
  "data_quality_score": 85,
  "stage_completions": [
    {"stage": "l1", "status": "completed", "completed_at": "2026-02-14T08:00:00Z", "cost_usd": 0.012},
    {"stage": "ares", "status": "completed", "completed_at": "2026-02-14T08:05:00Z", "cost_usd": 0.0},
    {"stage": "l2", "status": "completed", "completed_at": "2026-02-15T10:30:00Z", "cost_usd": 0.045}
  ]
}
```

### Contact Detail API Response — Expanded Enrichment

```json
{
  "...existing fields...",
  "last_enriched_at": "2026-02-15T10:35:00Z",
  "employment_status": "verified",
  "employment_verified_at": "2026-02-15T10:35:00Z",
  "enrichment": {
    "person_summary": "...",
    "linkedin_profile_summary": "...",
    "relationship_synthesis": "...",
    "career_trajectory": "Former CTO at StartupX, moved to VP Engineering...",
    "previous_companies": [{"name": "StartupX", "role": "CTO", "years": "2020-2024"}],
    "speaking_engagements": "WebSummit 2025 speaker...",
    "publications": "Co-author of 'Scaling Microservices'...",
    "twitter_handle": "@johndoe",
    "github_username": "johndoe",
    "ai_champion": true,
    "ai_champion_score": 82,
    "authority_score": 75,
    "enriched_at": "2026-02-15T10:35:00Z",
    "enrichment_cost_usd": 0.023
  }
}
```

## UX Flow — Company Detail

### Tab Layout

```
┌─────────────────────────────────────────────────────┐
│  ← Back                                    Company  │
│                                                     │
│  Acme Corp                              ★ Tier 1    │
│  acme.com · LinkedIn · Website    ◉ Enriched L2     │
│  Owner: Michal · Tag: batch-1  · DQ: 85/100        │
│                                                     │
│  ┌──────────┬─────────────┬────────────┐           │
│  │ Overview │ Enrichment  │ Metadata   │           │
│  └──────────┴─────────────┴────────────┘           │
│                                                     │
│  [Tab content below]                                │
└─────────────────────────────────────────────────────┘
```

### Overview Tab (default)

```
── CLASSIFICATION ──
business_model    company_size     ownership_type    geo_region
industry          industry_cat     revenue_range     business_type

── CRM ──
[tier ▼]          [buying_stage ▼]  [engagement_status ▼]

── LOCATION ──
hq_city           hq_country

── SUMMARY & NOTES ──
summary (read-only)
notes (editable textarea)

── CUSTOM FIELDS ──
(dynamic)

── TAGS ──
[Tag pills grouped by category]

── CONTACTS (5) ──
Name           Title              Email           ICP    Score
John Doe       VP Engineering     john@acme.com   ★★★    85
```

### Enrichment Tab

```
▼ COMPANY PROFILE
  company_intel       key_products       customer_segments
  competitors         tech_stack         leadership_team
  certifications

▼ STRATEGIC SIGNALS
  digital_initiatives   leadership_changes   hiring_signals
  ai_hiring             tech_partnerships    competitor_ai_moves
  ai_adoption_level     news_confidence      growth_indicators
  job_posting_count     hiring_departments

▼ MARKET & NEWS
  recent_news           funding_history      eu_grants
  media_sentiment       press_releases       thought_leadership

▼ PAIN & OPPORTUNITY
  pain_hypothesis       relevant_case_study  ai_opportunities
  quick_wins            industry_pain_points cross_functional_pain
  adoption_barriers

▼ LEGAL & REGISTRY
  [Credibility: 87/100 ●●●●○]
  official_name    ico/reg_id      legal_form      date_established
  address          registration    capital         status
  directors[]      nace_codes[]
  insolvency_flag  active_count    insolvency_details[]

── ENRICHMENT TIMELINE ──
  ● Created: 2026-02-01
  ● L1 Enriched: 2026-02-14 ($0.012)
  ● ARES Registry: 2026-02-14 ($0.00)
  ● L2 Enriched: 2026-02-15 ($0.045)
```

### Metadata Tab

```
── L1 TRIAGE ──
  triage_score: 7.5     pre_score: 8.2      confidence: 0.89
  quality_score: 82     qc_flags: [missing_revenue, weak_linkedin]
  research_query: "Acme Corp technology AI adoption..."
  triage_notes (editable textarea)

── STAGE COMPLETIONS ──
  [l1 ✓] [ares ✓] [l2 ✓] [signals ✗] [person ○]
  (chips: ✓=completed green, ✗=failed red, ○=pending gray)

── COSTS ──
  verified_revenue_eur_m: 15.0    verified_employees: 120
  enrichment_cost_usd: $0.057     data_quality_score: 85

── ERROR ──
  (conditional: only if error_message exists)

── TIMESTAMPS ──
  created_at: 2026-02-01T...
  updated_at: 2026-02-15T...
  last_enriched_at: 2026-02-15T...
```

## UX Flow — Contact Detail

### Tab Layout

```
┌──────────┬─────────────┐
│ Overview │ Enrichment  │
└──────────┴─────────────┘
```

### Overview Tab (default)

```
── COMPANY ──
[Acme Corp card — clickable]

── CONTACT INFO ──
email (link)     phone            city         country
employment_status   employment_verified_at

── CLASSIFICATION ──
[seniority ▼]  [department ▼]  [icp_fit ▼]
[relationship ▼]  [source ▼]  [language ▼]

── NOTES ──
notes (editable textarea)

── CUSTOM FIELDS ──
(dynamic)

── MESSAGES (3) ──
Channel    Step    Variant    Subject    Status    Tone
```

### Enrichment Tab

```
▼ PERSON SUMMARY
  person_summary
  linkedin_profile_summary
  relationship_synthesis

▼ CAREER & SOCIAL
  career_trajectory
  previous_companies[]
  speaking_engagements
  publications
  twitter_handle (link)
  github_username (link)

── SCORES ──
  contact_score: 85    ai_champion: ✓    ai_champion_score: 82
  authority_score: 75   enrichment_cost: $0.023

── ENRICHMENT TIMELINE ──
  ● Created: 2026-02-01
  ● Person Enriched: 2026-02-15 ($0.023)
```

## Architecture Decisions

### Tab Component Reuse
The `Tabs` component already exists at `frontend/src/components/ui/Tabs.tsx` but is unused. We'll adopt it for both detail views. Tab switching is client-side only — all data is loaded in the initial detail fetch (NFR-2).

### L2 Module Rendering
Currently L2 data is rendered as a flat `Record<string, unknown>` blob. We'll replace this with 4 explicit `CollapsibleSection` components, each rendering its module's known fields. The API already merges the 4 module tables into a flat `enrichment_l2` object — we'll read specific keys from it.

### Stage Completions Query
The company detail API will JOIN `entity_stage_completions` for the company's entity_id. This is a simple query addition — no new endpoint needed. The completions are returned as an array of `{stage, status, completed_at, cost_usd}`.

### Deprecated Field Handling
Fields are removed from the UI only — the API still returns them for backward compatibility (NFR-3). The PATCH endpoint continues to accept them. Migration 024 (drop columns) runs separately under BL-045 Phase D.

### Editable triage_notes
`triage_notes` moves from the Pipeline/Notes section to the Metadata tab. It remains editable — the PATCH endpoint already supports it.

## Edge Cases

- **No enrichment data**: If `enrichment_l2` is null, the Enrichment tab shows "No enrichment data yet" placeholder
- **Mixed old/new L2 data**: If data comes from the old monolithic `company_enrichment_l2` table (via API fallback), fields may be under different keys. The UI checks both naming patterns.
- **No stage completions**: If `stage_completions` is empty, the Metadata tab shows all stages as "pending" (gray chips)
- **Null enrichment fields on contact**: Career/social fields may all be null if person enrichment hasn't run — show "Not enriched yet" state

## Security Considerations

- No new auth boundaries — all data is already tenant-scoped and accessible via the existing detail endpoints
- `stage_completions` query must filter by `tenant_id` (already enforced by the entity query pattern)
- No client-side data exposure changes — we're surfacing data the API already returns or trivially could
