# L1 Workflow: Airtable → Postgres Migration

## Workflow ID: `oCCiiwvp7DYqoFb3`

## Prerequisites

1. Create Postgres credential in n8n UI:
   - Host: same as n8n internal DB (from `DB_POSTGRESDB_HOST` env var)
   - Port: same as n8n internal DB
   - Database: `leadgen`
   - User/Password: same as n8n internal DB credentials
   - SSL: require

2. Note the credential ID after creation (needed for workflow JSON).

## Node-by-Node Changes

### 1. ADD: Webhook Trigger Node

New node: `n8n-nodes-base.webhook`
- Path: `l1-enrich`
- HTTP Method: `POST`
- Response Mode: `lastNode` (synchronous — waits for workflow to finish)
- Connect output → Read Company (same as trigger)

This allows the Python orchestrator to call the workflow via HTTP POST.

### 2. REPLACE: "Get a record" → "Read Company" (Postgres Execute Query)

**SQL:**
```sql
SELECT id, name, domain, status, industry, company_size, revenue_range,
       tier, enrichment_cost_usd, owner_id, tenant_id
FROM companies WHERE id = '{{ $json.company_id }}'
```

Input: `company_id` from webhook or trigger.
Output: Single row with snake_case PG column names.

### 3. UPDATE: "If" Node — PG Enum Values

Change conditions from Airtable display values to PG enums:
- Condition 1: `{{ $json.status }}` equals `new` (was `New`)
- Condition 2: `{{ $json.status }}` equals `enrichment_failed` (was `Enrichment Failed`)

### 4. UPDATE: "Basic Company Reseach" (Perplexity) — Field References

Change expressions in user message:
- `{{ $json.Company }}` → `{{ $json.name }}`
- `{{ $json.Domain }}` → `{{ $json.domain }}`
- `{{ $json['Industry (Enum)'] }}` → `{{ $json.industry }}`
- `{{ $json['Company Size'] }}` → `{{ $json.company_size }}`
- `{{ $json.Revenue }}` → `{{ $json.revenue_range }}`

### 5. UPDATE: "Code in JavaScript" — Full Rewrite

See `n8n/l1-triage-code-v5.js` for the complete updated code.

Key changes:
- Input field mapping: Airtable camelCase → PG snake_case
- Output enum values: Airtable display → PG enum values
- `formatTier()` returns PG values (`tier_1_platinum`, etc.)
- `statusMap` uses PG values (`triage_passed`, etc.)
- Revenue/employee bucket functions return PG enum values
- `mapOwnership()` returns PG enum values

### 6. REPLACE: "Update record1" → "Update Company" (Postgres Execute Query)

**SQL:**
```sql
UPDATE companies SET
  status = '{{ $json.pg_status }}',
  tier = '{{ $json.pg_tier }}',
  summary = '{{ $json.pg_summary }}',
  hq_city = '{{ $json.pg_hq_city }}',
  hq_country = '{{ $json.pg_hq_country }}',
  geo_region = '{{ $json.pg_geo_cluster }}',
  ownership_type = '{{ $json.pg_ownership_type }}',
  triage_notes = {{ $json.pg_triage_notes ? "'" + $json.pg_triage_notes.replace(/'/g, "''") + "'" : "NULL" }},
  triage_score = {{ $json.pg_triage_score }},
  verified_employees = {{ $json.pg_verified_employees || 'NULL' }},
  verified_revenue_eur_m = {{ $json.pg_verified_revenue_m || 'NULL' }},
  business_model = {{ $json.pg_business_model ? "'" + $json.pg_business_model + "'" : "NULL" }},
  industry = {{ $json.pg_industry ? "'" + $json.pg_industry + "'" : "NULL" }},
  business_type = {{ $json.pg_business_type ? "'" + $json.pg_business_type + "'" : "NULL" }},
  revenue_range = {{ $json.pg_revenue_bucket ? "'" + $json.pg_revenue_bucket + "'" : "NULL" }},
  company_size = {{ $json.pg_company_size_bucket ? "'" + $json.pg_company_size_bucket + "'" : "NULL" }},
  enrichment_cost_usd = {{ $json.pg_enrichment_cost }},
  updated_at = now()
WHERE id = '{{ $json.record_id }}'
RETURNING id, status, tier, enrichment_cost_usd
```

### 7. REPLACE: "Update record" → "Update Company Error" (Postgres Execute Query)

**SQL:**
```sql
UPDATE companies SET
  status = 'enrichment_failed',
  error_message = {{ $json.error ? "'" + String($json.error).replace(/'/g, "''").substring(0, 500) + "'" : "NULL" }},
  updated_at = now()
WHERE id = '{{ $('Read Company').item.json.id }}'
RETURNING id, status
```

### 8. REPLACE: "Save research asset" → "Save Research Asset" (Postgres Execute Query)

**SQL:**
```sql
INSERT INTO research_assets (
  tenant_id, entity_type, entity_id, name, tool_name,
  cost_usd, research_data, confidence_score, quality_score
) VALUES (
  '{{ $('Read Company').item.json.tenant_id }}',
  'company',
  '{{ $('Read Company').item.json.id }}',
  'company_basic_research',
  'perplexity_{{ $('Basic Company Reseach').item.json.model }}',
  {{ $('Basic Company Reseach').item.json.usage.cost.total_cost || 0 }},
  '{{ $('Basic Company Reseach').item.json.choices[0].message.content.replace(/'/g, "''") }}',
  {{ $json.research_confidence_score || 0 }},
  {{ $json.research_quality_score || 0 }}
)
RETURNING id
```

## Connection Flow (Updated)

```
Webhook ─┐
         ├─→ Read Company → If (status check) → Perplexity → Code → Update Company → Save Research Asset
Trigger ─┘                                        ↓ (error)
                                             Update Company Error
```

Both trigger nodes connect to Read Company. The rest of the flow is identical.

## Webhook Response

With `responseMode: "lastNode"`, the webhook returns whatever the last executed node outputs.
For the success path: Save Research Asset returns `{id}`.
For the error path: Update Company Error returns `{id, status}`.

The Python orchestrator reads the response to extract `enrichment_cost_usd`.
