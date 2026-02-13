# Contacts & Companies Management Screens

## Purpose
Provide Airtable-like table views for browsing, searching, and editing company and contact records directly in the dashboard. Supports server-side pagination (2600+ contacts, 1800+ companies), multi-field filtering, column sorting, and detail modals with linked entity navigation.

## Requirements

### Companies Page (`/companies`)
1. **Table view** with columns: Name, Domain, Status, Tier, Owner, Batch, Industry, HQ Country, Triage Score, Contacts count
2. **Filters**: Status (dropdown), Tier (dropdown), Batch (dropdown), Owner (dropdown), Search (text — matches name/domain)
3. **Sorting**: Click column header to sort asc/desc; re-fetches from API
4. **Pagination**: Offset-based with Previous/Next controls and "Page X of Y (Z total)" indicator
5. **Detail modal**: Click row to open modal via `GET /api/companies/<id>` with sections:
   - Header: name, domain, status badge, tier badge
   - Classification: business_model, size, ownership, geo, industry, revenue
   - Pipeline: buying_stage, engagement, crm_status, AI adoption
   - Scores: triage, pre_score, revenue, employees
   - Summary/Notes: editable textarea
   - L2 Enrichment: collapsible section with ~20 text fields
   - Tags: chips grouped by category
   - Contacts: mini-table of linked contacts, clickable to navigate to contacts page
6. **Editing**: Allowed fields (status, tier, notes, triage_notes, buying_stage, engagement_status, crm_status, cohort) with Save button via `PATCH /api/companies/<id>`
7. **Cross-page linking**: Contact rows in modal navigate to `/contacts?open=<uuid>`

### Contacts Page (`/contacts`)
1. **Table view** with columns: Full Name, Job Title, Company (linked), Email, Score, ICP Fit, Message Status, Owner, Batch
2. **Filters**: Batch (dropdown), Owner (dropdown), ICP Fit (dropdown), Message Status (dropdown), Search (text — matches name/email/title)
3. **Sorting**: Same pattern as companies
4. **Pagination**: Same pattern as companies
5. **Detail modal**: Click row to open modal via `GET /api/contacts/<id>` with sections:
   - Header: name, title, LinkedIn link
   - Company link: clickable to navigate to `/companies?open=<uuid>`
   - Contact info: email, phone, location
   - Classification: seniority, department, ICP fit, relationship, source, language
   - Scores: contact, AI champion, authority
   - Enrichment: person_summary, linkedin_summary, relationship_synthesis
   - Messages: mini-table of linked messages
   - Status flags: processed, email_lookup, duplicity
   - Notes: editable
6. **Editing**: Allowed fields (notes, icp_fit, message_status, relationship_status, seniority_level, department, contact_source, language) with Save button
7. **Cross-page linking**: Company link in modal navigates to `/companies?open=<uuid>`

## API Contracts

### `GET /api/companies`
**Auth**: `@require_auth`
**Params**: `page` (int, default 1), `page_size` (int, default 25, max 100), `search` (text), `status` (enum), `tier` (enum), `batch_name` (text), `owner_name` (text), `sort` (column name), `sort_dir` (asc|desc)
**Response**: `{ companies: [...], total: int, page: int, page_size: int, pages: int }`

### `GET /api/companies/<id>`
**Auth**: `@require_auth`
**Response**: Full company object with enrichment_l2, tags array, contacts summary

### `PATCH /api/companies/<id>`
**Auth**: `@require_role("editor")`
**Body**: `{ field: value, ... }` — only allowed fields
**Response**: `{ ok: true }`

### `GET /api/contacts`
**Auth**: `@require_auth`
**Params**: `page`, `page_size`, `search`, `batch_name`, `owner_name`, `icp_fit`, `message_status`, `company_id`, `sort`, `sort_dir`
**Response**: `{ contacts: [...], total: int, page: int, page_size: int, pages: int }`

### `GET /api/contacts/<id>`
**Auth**: `@require_auth`
**Response**: Full contact object with company link, enrichment, messages array

### `PATCH /api/contacts/<id>`
**Auth**: `@require_role("editor")`
**Body**: `{ field: value, ... }` — only allowed fields
**Response**: `{ ok: true }`

## Data Model
No schema changes. Uses existing tables: `companies`, `company_enrichment_l2`, `company_tags`, `contacts`, `contact_enrichment`, `messages`, `owners`, `batches`.

## Acceptance Criteria
- [ ] Companies page loads with paginated data, all filters work
- [ ] Contacts page loads with paginated data, all filters work
- [ ] Column sorting works (server-side)
- [ ] Detail modals show complete record information
- [ ] Editable fields can be saved via PATCH
- [ ] Cross-page linking works (company modal → contacts, contact modal → companies)
- [ ] `?open=<uuid>` query param auto-opens detail modal
- [ ] Filter state persisted in localStorage
- [ ] All unit tests pass
- [ ] No regressions in existing tests
