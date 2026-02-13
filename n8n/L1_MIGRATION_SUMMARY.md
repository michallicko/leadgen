# L1 Workflow Migration Summary

## Workflow Details

- **Workflow ID**: `oCCiiwvp7DYqoFb3`
- **Name**: Enrich company L1
- **Version**: v5 (Postgres migration)
- **File**: `/Users/michal/git/leadgen-pipeline/n8n/l1-workflow-v5.json`
- **Status**: ✅ Ready for deployment (after credential setup)

## Node List (9 nodes)

1. **Webhook** (`n8n-nodes-base.webhook`) - NEW
   - Path: `l1-enrich`
   - Method: POST
   - Response mode: lastNode (synchronous)

2. **When Executed by Another Workflow** (`n8n-nodes-base.executeWorkflowTrigger`)
   - Kept for backward compatibility

3. **Read Company** (`n8n-nodes-base.postgres`) - REPLACED Airtable "Get a record"
   - SELECT query fetching company record by ID

4. **If** (`n8n-nodes-base.if`) - UPDATED
   - Checks status = 'new' OR 'enrichment_failed' (PG enum values)

5. **Basic Company Reseach** (`n8n-nodes-base.perplexity`) - UPDATED
   - Field references changed to PG snake_case ($json.name, $json.domain, etc.)

6. **Code in JavaScript** (`n8n-nodes-base.code`) - UPDATED
   - Replaced with v5 code from `l1-triage-code-v5.js`
   - Outputs PG-ready field names (pg_status, pg_tier, etc.)

7. **Update Company Success** (`n8n-nodes-base.postgres`) - REPLACED Airtable "Update record1"
   - UPDATE query with 18 fields
   - Uses expressions from Code node output

8. **Update Company Error** (`n8n-nodes-base.postgres`) - REPLACED Airtable "Update record"
   - UPDATE query for error cases
   - Sets status to 'enrichment_failed'

9. **Save Research Asset** (`n8n-nodes-base.postgres`) - REPLACED Airtable "Save research asset"
   - INSERT query into research_assets table
   - Stores raw Perplexity response + scores

## Connection Flow

```
Webhook ──┐
          ├──> Read Company ──> If (status check)
Trigger ──┘                      ├─ TRUE ──> Basic Company Reseach
                                 │              ├─ SUCCESS ──> Code in JavaScript
                                 │              │                 ├──> Update Company Success
                                 │              │                 └──> Save Research Asset
                                 │              └─ ERROR ──> Update Company Error
                                 └─ FALSE ──> Update Company Error
```

## Changes from Airtable Version

### 1. Added Webhook Trigger ✅
- **Node**: Webhook
- **Path**: `/webhook/l1-enrich`
- **Method**: POST
- **Body**: `{"company_id": "<uuid>"}`
- **Response**: Last node output (Update Company Success or Update Company Error)

### 2. Database Access Layer ✅
All Airtable nodes replaced with Postgres Execute Query nodes:
- Read Company: SELECT from companies table
- Update Company Success: UPDATE companies with enrichment results
- Update Company Error: UPDATE companies with error status
- Save Research Asset: INSERT into research_assets table

### 3. Data Model Alignment ✅
- **If node**: Checks PG enum values (`new`, `enrichment_failed`)
- **Perplexity node**: References PG field names (`$json.name`, `$json.domain`)
- **Code node**: Outputs PG-ready values with `pg_` prefix
- **Update queries**: Use `pg_` prefixed fields from Code node

### 4. Code Logic Update ✅
- v5 code includes full Postgres enum mapping
- Tier values: `tier_1_platinum`, `tier_2_gold`, etc.
- Status values: `triage_passed`, `triage_review`, `triage_disqualified`
- Revenue buckets: `micro`, `small`, `medium`, `mid_market`, `enterprise`
- Employee buckets: `micro`, `startup`, `smb`, `mid_market`, `enterprise`
- Ownership types: `family_owned`, `pe_backed`, `vc_backed`, `public`, etc.

## Credential Setup Required

The workflow uses **placeholder credential ID**: `PLACEHOLDER_POSTGRES_CREDENTIAL_ID`

### Before deployment:

1. **Create Postgres credential in n8n UI**:
   - Name: "Postgres account" (or any name)
   - Host: (same as n8n internal DB host)
   - Port: 5432
   - Database: `leadgen`
   - User: (same as n8n DB user)
   - Password: (same as n8n DB password)
   - SSL Mode: `require`

2. **Get credential ID**:
   - Check browser network requests after saving credential
   - Or query n8n API: `GET /api/v1/credentials`
   - Look for the credential you just created

3. **Replace placeholder in JSON**:
   ```bash
   # Replace all occurrences
   sed -i '' 's/PLACEHOLDER_POSTGRES_CREDENTIAL_ID/<actual-id>/g' \
     /Users/michal/git/leadgen-pipeline/n8n/l1-workflow-v5.json
   ```

## Deployment

```bash
# 1. Set credential ID in workflow JSON (see above)

# 2. Deploy to n8n via API
curl -X PUT https://n8n.visionvolve.com/api/v1/workflows/oCCiiwvp7DYqoFb3 \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @/Users/michal/git/leadgen-pipeline/n8n/l1-workflow-v5.json

# 3. Activate workflow (if needed)
curl -X POST https://n8n.visionvolve.com/api/v1/workflows/oCCiiwvp7DYqoFb3/activate \
  -H "X-N8N-API-KEY: $N8N_API_KEY"
```

## Testing

### Test via Webhook (recommended)
```bash
curl -X POST https://n8n.visionvolve.com/webhook/l1-enrich \
  -H "Content-Type: application/json" \
  -d '{"company_id": "59f4065e-7d31-4d43-9a76-c4d4b7c5f5c4"}'
```

### Test via Execute Workflow (legacy)
```javascript
// From orchestrator or another workflow
$execution("oCCiiwvp7DYqoFb3", {
  company_id: "59f4065e-7d31-4d43-9a76-c4d4b7c5f5c4"
})
```

## Response Format

### Success Path (Update Company Success)
```json
{
  "id": "59f4065e-7d31-4d43-9a76-c4d4b7c5f5c4",
  "status": "triage_passed",
  "tier": "tier_2_gold",
  "enrichment_cost_usd": 0.0234
}
```

### Error Path (Update Company Error)
```json
{
  "id": "59f4065e-7d31-4d43-9a76-c4d4b7c5f5c4",
  "status": "enrichment_failed"
}
```

## Validation Results ✅

- All 9 nodes have required fields (id, name, type, position, parameters)
- All 15 connections reference valid node names
- JSON structure is well-formed
- File size: 31,637 bytes

## Next Steps

1. ☐ Create Postgres credential in n8n UI
2. ☐ Replace placeholder credential ID in workflow JSON
3. ☐ Deploy workflow via n8n API
4. ☐ Test webhook with a sample company ID
5. ☐ Update Python orchestrator to use webhook instead of Execute Workflow
6. ☐ Verify enrichment results in PostgreSQL
7. ☐ Monitor execution logs for errors
8. ☐ Run smoke test with batch-2 companies

## Migration Date

Generated: 2026-02-12
