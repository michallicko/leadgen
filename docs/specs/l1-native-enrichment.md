# L1 Native Enrichment

> Status: Implemented | Branch: `feature/l1-native-enrichment`

## Purpose

Migrate L1 company enrichment from n8n webhook to native Python for better control, testability, and cost visibility. Companies are enriched via Perplexity sonar API with web-grounded research, then QC-validated before advancing to triage.

## Requirements

1. **Perplexity Integration**: Call Perplexity sonar API with B2B-focused system prompt
2. **Field Mapping**: Parse JSON response and map 15+ fields to company columns
3. **QC Validation**: 7 automated checks flag implausible or incomplete research
4. **Domain Resolution**: Resolve company domain from contact email addresses when not set
5. **Cost Tracking**: Log LLM usage with per-call token counts and cost via `llm_usage_log`
6. **Research Storage**: Store raw Perplexity response in `research_assets` table
7. **Review Workflow**: API endpoints to list flagged companies and take corrective action
8. **Dashboard**: Disable non-L1 stages, show progress counters, review list with actions

## Acceptance Criteria

- [ ] Companies with `status='new'` are enriched and advanced to `triage_passed` or `needs_review`
- [ ] Failed enrichments set `status='enrichment_failed'` with error message
- [ ] QC flags stored in `error_message` as JSON array
- [ ] Research data stored in `research_assets` with confidence/quality scores
- [ ] Cost tracked in `llm_usage_log` with `provider='perplexity'`
- [ ] `GET /api/enrich/review` returns flagged companies for a batch
- [ ] `POST /api/enrich/resolve` supports approve/retry/skip actions
- [ ] Dashboard shows only L1 as enabled, other stages grayed with "Coming soon"
- [ ] Dashboard shows success/error counters and estimated time remaining during processing
- [ ] Dashboard shows inline review list with retry/approve actions on completion
- [ ] 94+ unit tests passing for enricher, 32+ for enrich routes

## API Contracts

### GET /api/enrich/review
Query: `batch_name` (required), `stage` (default: "l1")
Response:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Company Name",
      "domain": "example.com",
      "status": "needs_review",
      "flags": ["name_mismatch", "low_confidence"],
      "enrichment_cost_usd": 0.01
    }
  ],
  "total": 1
}
```

### POST /api/enrich/resolve
Body: `{"company_id": "uuid", "action": "approve|retry|skip"}`
Response:
```json
{"success": true, "new_status": "triage_passed"}
```

## Data Model Changes

### New: `research_assets` table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| entity_type | TEXT | "company" |
| entity_id | UUID | FK → companies |
| name | TEXT | "l1_research" |
| tool_name | TEXT | "perplexity_sonar" |
| cost_usd | NUMERIC(10,6) | API call cost |
| research_data | JSONB | Raw Perplexity response |
| confidence_score | NUMERIC(5,2) | Perplexity confidence |
| quality_score | NUMERIC(5,2) | 100 - (flags * 15) |
| created_at | TIMESTAMPTZ | Auto |

### Modified: `companies` table
Uses existing columns: `status`, `error_message`, `summary`, `hq_city`, `hq_country`, `geo_region`, `ownership_type`, `industry`, `business_type`, `revenue_range`, `company_size`, `verified_revenue_eur_m`, `verified_employees`, `enrichment_cost_usd`, `business_model`.

New status values: `needs_review` (QC-flagged), `enrichment_failed` (API error).

## QC Validation Rules

| Check | Flag | Logic |
|-------|------|-------|
| Name mismatch | `name_mismatch` | Bigram similarity < 0.6 |
| Missing fields | `incomplete_research` | <3 of: summary, hq, industry, employees, revenue |
| Revenue sanity | `revenue_implausible` | >€500K/employee or >€50B |
| Employee sanity | `employees_implausible` | >500K or <0 |
| Low confidence | `low_confidence` | Perplexity confidence < 0.4 |
| B2B unclear | `b2b_unclear` | b2b field null/missing |
| Short summary | `summary_too_short` | <30 chars |

## Edge Cases

- Company with no domain and no contacts with email → research by name only (no domain in prompt)
- Free-mail domains (gmail, yahoo, etc.) filtered from contact emails
- Revenue strings like "42M", "1.5 billion", "unverified" → parsed to float or None
- Employee strings like "200-300" → midpoint (250), "1,234" → 1234
- JSON response wrapped in markdown fences → stripped before parsing
