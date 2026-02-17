# Company Detail Enrichment View — Design

**Status**: Draft | **Date**: 2026-02-17

## Affected Components

| Component | File(s) | Change Type | Description |
|-----------|---------|-------------|-------------|
| Company API | `api/routes/company_routes.py` | Modified | Add 5 new columns to SELECT |
| TS Types | `frontend/src/api/queries/useCompanies.ts` | Modified | Add enrichment_l1 + new fields to CompanyDetail |
| Company Detail | `frontend/src/pages/companies/CompanyDetail.tsx` | Modified | L1 section, modular L2, header links, timeline fix |

## Data Model Changes

None — all tables and columns already exist from BL-045 (migrations 019-023). This feature only exposes existing data.

## API Contract

### Modified: `GET /api/companies/<id>`

**New top-level fields added to response:**

```json
{
  "website_url": "https://example.com",
  "linkedin_url": "https://linkedin.com/company/example",
  "logo_url": "https://example.com/logo.png",
  "last_enriched_at": "2026-02-17T10:00:00Z",
  "data_quality_score": 85
}
```

**Existing `enrichment_l1` field** (already returned, no API change needed):

```json
{
  "enrichment_l1": {
    "triage_notes": "VERDICT: PASS...",
    "pre_score": 7.5,
    "research_query": "company name + domain",
    "raw_response": { ... },
    "confidence": 0.85,
    "quality_score": 7,
    "qc_flags": ["flag1"],
    "enriched_at": "2026-02-17T10:00:00Z",
    "enrichment_cost_usd": 0.0012
  }
}
```

**Existing `enrichment_l2` field** (already returned with new fields, no API change needed):

New fields in L2 response: `ai_adoption_level`, `news_confidence`, `growth_indicators`, `job_posting_count`, `hiring_departments`, `media_sentiment`, `press_releases`, `thought_leadership`

## UX Flow

### Company Detail Layout (updated sections)

```
┌─────────────────────────────────────────────────────┐
│ [logo] Company Name                                  │
│ domain.com · 🔗 Website · 🔗 LinkedIn               │
│ [Status badge] [Tier badge] [Quality: 85] Owner Tag  │
├─────────────────────────────────────────────────────┤
│ ▸ Classification (8 fields — unchanged)              │
│ ▸ Pipeline (6 editable fields — unchanged)           │
│ ▸ Scores (7 fields — unchanged)                      │
│ ▸ Location (2 fields — unchanged)                    │
│ ▸ Summary & Notes (3 fields — unchanged)             │
│ ▸ Custom Fields (dynamic — unchanged)                │
│ [Save] (when dirty — unchanged)                      │
│                                                      │
│ ▾ L1 Enrichment ──────────────────────── NEW         │
│   Confidence: 0.85  Quality: 7  Cost: $0.0012        │
│   QC Flags: [flag1, flag2]                           │
│   Enriched: 2026-02-17 10:00                         │
│                                                      │
│ ▾ L2 Enrichment (grouped by module) ── RESTRUCTURED  │
│   ┌─ Company Profile ───────────────────────┐        │
│   │  Company Intel, Key Products, Customer   │        │
│   │  Segments, Competitors, Tech Stack,      │        │
│   │  Leadership Team, Certifications         │        │
│   └──────────────────────────────────────────┘        │
│   ┌─ Strategic Signals ─────────────────────┐        │
│   │  Digital Initiatives, Leadership Changes,│        │
│   │  Hiring Signals, AI Hiring, Tech Partners│        │
│   │  Competitor AI Moves, AI Adoption Level, │        │
│   │  News Confidence, Growth Indicators,     │ ← NEW  │
│   │  Job Posting Count, Hiring Departments   │ ← NEW  │
│   └──────────────────────────────────────────┘        │
│   ┌─ Market Intel ──────────────────────────┐        │
│   │  Recent News, Funding History, EU Grants,│        │
│   │  Media Sentiment, Press Releases,        │ ← NEW  │
│   │  Thought Leadership                      │ ← NEW  │
│   └──────────────────────────────────────────┘        │
│   ┌─ Sales Opportunity ─────────────────────┐        │
│   │  Pain Hypothesis, Case Study, AI Opps,   │        │
│   │  Quick Wins, Industry Pains, Cross-Func, │        │
│   │  Adoption Barriers                       │        │
│   └──────────────────────────────────────────┘        │
│                                                      │
│ ▾ Legal & Registry (unchanged)                       │
│ ▸ Tags (unchanged)                                   │
│ ▸ Contacts (unchanged)                               │
│ ▸ Errors (unchanged)                                 │
│ ▸ Enrichment Timeline (L1 timestamp fixed)           │
│ ▸ Timestamps (unchanged)                             │
└─────────────────────────────────────────────────────┘
```

### L1 Enrichment Section

Collapsible section showing key metadata fields in a compact grid:

| Field | Display | Notes |
|-------|---------|-------|
| Confidence | Number (0-1) | Show as percentage badge if available |
| Quality Score | Integer | Raw score from L1 enricher |
| QC Flags | Pill array | Each flag as a small warning badge |
| Enriched At | Datetime | Formatted timestamp |
| Cost | USD | 4 decimal places |

Research query shown as a small muted text line (helpful for debugging, not prominent).
Raw response NOT shown (too large, not user-facing).

### L2 Module Sub-Sections

Each module is a subtle sub-heading within the L2 collapsible:
- Light separator line + module name
- Fields for that module in a FieldGrid
- Empty modules hidden (if no data for that module)

### Header Enhancements

- Logo: Small avatar (24x24) to the left of company name, falls back to first letter if no logo_url
- Website: Clickable link icon + text, opens in new tab
- LinkedIn: Clickable LinkedIn icon + text, opens in new tab
- Data Quality Score: Small badge (like credibility score on Legal section), color-coded (green ≥80, yellow ≥50, red <50)

### UI States

| State | Condition | Display |
|-------|-----------|---------|
| No L1 data | `enrichment_l1 === null` | L1 section hidden entirely |
| No L2 data | `enrichment_l2 === null` | L2 section hidden entirely |
| Partial L2 | Only some modules have data | Empty modules hidden, populated ones shown |
| No links | `website_url` and `linkedin_url` both null | Link area not rendered |
| No logo | `logo_url` null | Show first letter avatar fallback |
| No quality score | `data_quality_score` null | Badge not shown |

## Edge Cases

1. **All enrichment null**: Company with no enrichment data shows only core fields (Classification, Pipeline, etc.). No enrichment sections rendered.
2. **L2 data from old table**: Backward-compat fallback returns flat L2 data without module grouping. Display all fields under a single L2 section (current behavior).
3. **QC flags as empty array vs null**: Both render as "no flags" — section shows "No issues" or flags hidden.
4. **Very long research query**: Truncate with ellipsis, expandable on click.

## Security Considerations

- No new auth requirements — uses existing JWT + tenant isolation
- No new inputs — all data is read-only from enrichment pipelines
- External URLs (website, LinkedIn) opened in new tab with `rel="noopener noreferrer"`

## Architecture Decisions

No new ADR needed. This is a display-only change that consumes the existing data model from BL-045.
