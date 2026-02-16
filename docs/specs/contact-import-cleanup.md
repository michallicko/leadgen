# Contact List Import & Cleanup

> **Status**: Phase 1 (MVP) implemented | **Backlog**: BL-006

## Purpose

Enable users to import existing contact lists from CSV files. The system uses AI to auto-detect CSV column structure and map to database fields, previews imports with deduplication detection, and inserts contacts/companies into the existing data model for enrichment via the pipeline.

## Requirements

### Phase 1: Import & Map (Implemented)
1. Upload CSV file (max 10 MB, UTF-8 or Latin-1)
2. AI-powered column mapping via Claude API
3. User can adjust AI-suggested mappings
4. Preview with deduplication detection (25 rows)
5. Execute import with configurable dedup strategy
6. Track import history per tenant

### Phase 2: Enrich & Export (Future)
- Enrichment depth selection (L1/L2/Person)
- Cost estimation before running
- CSV export of enriched results
- Enrichment trigger from import page

### Phase 3: Person L1 Workflow (Future)
- New n8n workflow for lightweight person verification

## API Contracts

### `POST /api/imports/upload`
Multipart form with `file` field (CSV).
Returns: `{ job_id, filename, total_rows, headers, sample_rows, mapping, mapping_confidence }`

### `POST /api/imports/<job_id>/preview`
Body: `{ mapping: <adjusted mapping> }`
Returns: `{ job_id, preview_rows[], total_rows, preview_count, summary }`

### `POST /api/imports/<job_id>/execute`
Body: `{ batch_name, owner_id?, dedup_strategy: "skip"|"update"|"create_new" }`
Returns: `{ job_id, status, batch_name, counts }`

### `GET /api/imports/<job_id>/status`
Returns: ImportJob object

### `GET /api/imports`
Returns: `{ imports: ImportJob[] }`

## Data Model

### import_jobs table
Tracks the full lifecycle: uploaded → mapped → previewed → importing → completed/error.
Stores raw CSV, headers, sample rows, AI mapping, dedup results, and execution counts.

### FK additions
- `contacts.import_job_id` → tracks which import created each contact
- `companies.import_job_id` → tracks which import created each company

## Deduplication

### Contact matching (priority order)
1. LinkedIn URL (exact, case-insensitive)
2. Email address (exact, case-insensitive)
3. Full name + company name (case-insensitive)

### Company matching (priority order)
1. Domain (normalized: strip protocol, www, path)
2. Name (case-insensitive)

### Strategies
- **skip**: Don't import duplicate contacts (default)
- **update**: Fill empty fields on the existing record
- **create_new**: Always create new record regardless of match

Companies always link to existing when matched (never duplicated).

## AI Column Mapping

Claude Sonnet analyzes CSV headers + 5 sample rows and returns:
- Per-column mapping with target field and confidence score
- Transform suggestions: `combine_first_last`, `extract_domain`, `normalize_enum`
- Warnings for missing required fields or ambiguous matches
- Combine instructions for split columns (e.g., First + Last → full_name)

## Edge Cases

- Empty name rows are skipped (contact requires `full_name`)
- AI mapping failure degrades gracefully (empty mapping + warning)
- Large files processed entirely in memory (10 MB limit)
- Intra-file duplicates detected in preview (e.g., same email twice in CSV)
- Domain normalization strips www/protocol for consistent matching

## Acceptance Criteria

- [x] Upload CSV via drag-and-drop or file picker
- [x] AI auto-maps columns with confidence indicators
- [x] User can adjust mappings via dropdowns
- [x] Preview shows 25 rows with dedup badges (New/Duplicate/Existing)
- [x] Summary bar shows counts before import
- [x] Execute creates batch, companies, contacts in DB
- [x] Dedup strategies work correctly (skip/update/create_new)
- [x] Import history visible on page
- [x] 80 unit tests covering mapper, dedup, and routes
- [x] All 194 project tests pass
