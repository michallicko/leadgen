# Chrome Extension Integration Design

**Date**: 2026-02-20
**Status**: Approved

## Overview

Port the LinkedIn Lead Uploader Chrome extension into leadgen-pipeline. Add a Preferences page where users see extension connection status. Two separate extensions (prod + staging) built from the same TypeScript source.

## Decisions

| Decision | Choice |
|----------|--------|
| **Scope** | Both features (lead extraction + activity monitoring) |
| **Auth** | Login in extension popup (email/password -> JWT, auto-refresh) |
| **Environments** | Two separate extensions (purple=prod, orange=staging) |
| **Data target** | Direct to PostgreSQL via new API endpoints |
| **Lead flow** | Direct to contacts + companies, tagged with source |
| **Missing contacts** | Auto-create stub contacts from activity data |
| **Code location** | `extension/` directory inside leadgen-pipeline |
| **Tech stack** | TypeScript + Vite build for Chrome MV3 |
| **Settings UI** | User dropdown -> Preferences page (minimal, extension status only) |
| **API routes** | `POST /api/extension/leads`, `POST /api/extension/activities`, `GET /api/extension/status` |
| **DB changes** | New `activities` table + `is_stub`/`import_source` on contacts |

## Extension Architecture

```
extension/
  src/
    common/
      api-client.ts        # Auth-aware fetch wrapper (mirrors frontend/src/api/client.ts)
      auth.ts              # Login, token storage/refresh via chrome.storage.local
      config.ts            # Environment config (API URL, extension name)
      types.ts             # Shared types (Lead, Activity, AuthState)
    content/
      sales-navigator.ts   # Lead extraction from SN pages
      activity-monitor.ts  # LinkedIn messaging/network activity scraping
    background/
      service-worker.ts    # Multi-page orchestration, activity sync scheduler, API relay
    popup/
      popup.html           # Login form + status display
      popup.ts             # Login logic, connection status, manual sync trigger
    icons/
      prod/                # Purple icons (16, 48, 128)
      staging/             # Orange icons (16, 48, 128)
  manifests/
    base.json              # Shared manifest fields (permissions, content scripts)
    prod.json              # name: "VisionVolve Leads", API: leadgen.visionvolve.com
    staging.json           # name: "VisionVolve Leads [STAGING]", API: leadgen-staging...
  vite.config.ts           # Vite build with CRXJS or manual MV3 bundling
  tsconfig.json
  package.json
```

Build: `npm run build:prod` and `npm run build:staging` produce two `dist/` folders, each a loadable unpacked extension.

Key differences between prod/staging:

- Extension name and description
- Icon color (purple vs orange)
- API base URL
- Extension ID (different for each so both can be installed simultaneously)

## Auth Flow

Extension login flow:

1. User clicks extension icon
2. Popup shows login form (email + password)
3. POST /api/auth/login (same endpoint as dashboard)
4. Receives `{ access_token, refresh_token, user }`
5. Stores in `chrome.storage.local` (NOT localStorage -- extensions use chrome.storage)
6. Popup switches to "Connected" view showing user email + last sync time

Token lifecycle:

- Access token: 15-min expiry (same as dashboard)
- Refresh token: 7-day expiry
- api-client.ts auto-refreshes before API calls (checks expiry, calls /api/auth/refresh)
- On refresh failure (7-day token expired): popup shows "Session expired, please log in again"

Namespace/tenant resolution:

- At login, API returns user's roles including namespace slugs
- If user has exactly one namespace, use it automatically
- If multiple, popup shows a namespace picker after login
- Selected namespace stored in `chrome.storage.local` alongside tokens
- All API calls include `X-Namespace` header (same pattern as dashboard)

## API Endpoints

New routes under `api/routes/extension_routes.py`:

### POST /api/extension/leads

Request:

```json
{
  "leads": [{
    "name": "John Doe",
    "job_title": "CTO",
    "company_name": "Acme Inc",
    "linkedin_url": "https://linkedin.com/in/johndoe",
    "company_website": "https://acme.com",
    "revenue": "$10M-50M",
    "headcount": "51-200",
    "industry": "Technology"
  }],
  "source": "sales_navigator",
  "tag": "SN Import 2026-02-20"
}
```

Response: `{ "created_contacts": N, "created_companies": N, "skipped_duplicates": N }`

Behavior:

- Deduplicates contacts by LinkedIn URL
- Creates companies if not found (exact match on name)
- Tags contacts with source + import tag
- Links contacts to companies
- Sets Owner based on authenticated user's owner_id

### POST /api/extension/activities

Request:

```json
{
  "events": [{
    "event_type": "message",
    "timestamp": "2026-02-20T10:30:00Z",
    "contact_linkedin_url": "https://linkedin.com/in/johndoe",
    "external_id": "ext_a1b2c3d4",
    "payload": {
      "contact_name": "John Doe",
      "message": "Hey, interested in...",
      "conversation_id": "conv_123",
      "direction": "sent"
    }
  }]
}
```

Response: `{ "created": N, "skipped_duplicates": N }`

Behavior:

- Deduplicates by external_id
- Matches contacts by LinkedIn URL
- Creates stub contacts if no match (is_stub=true, minimal data from payload)
- Stores in activities table

### GET /api/extension/status

Response:

```json
{
  "connected": true,
  "last_lead_sync": "2026-02-20T10:30:00Z",
  "last_activity_sync": "2026-02-20T10:25:00Z",
  "total_leads_imported": 142,
  "total_activities_synced": 580
}
```

## Database Schema

### New `activities` table (migration 005)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK -> tenants |
| contact_id | UUID | FK -> contacts (nullable until resolved) |
| owner_id | UUID | FK -> owners |
| event_type | text | "message" or "event" |
| activity_name | text | Display name |
| activity_detail | text | Message body or event description |
| source | text | "linkedin_extension", "email", etc. |
| external_id | text | Dedup key (unique per tenant) |
| timestamp | timestamptz | When the activity occurred |
| payload | jsonb | Full event data (direction, conversation_id, etc.) |
| processed | boolean | Default false |
| created_at | timestamptz | |

Indexes:

- Unique on `(tenant_id, external_id)` for deduplication
- Index on `(tenant_id, contact_id)` for lookups by contact
- Index on `(tenant_id, event_type, timestamp)` for filtered queries

### Contacts table changes

- Add `is_stub` boolean (default false) -- marks auto-created stub contacts
- Add `import_source` text (nullable) -- "sales_navigator", "csv_import", "activity_stub", etc.

## Settings UI

### User Dropdown Menu

Top-right corner of AppShell, click on user name/avatar:

- Preferences
- Logout

### Preferences Page (`/:namespace/preferences`)

```
Preferences
---------------------------------------------
Browser Extension

  Status: * Connected (last sync 5 min ago)
    - or -
  Status: o Not connected

  Stats:
    Leads imported: 142
    Activities synced: 580
    Last lead sync: Feb 20, 2026 10:30 AM
    Last activity sync: Feb 20, 2026 10:25 AM

  [Disconnect Extension]
---------------------------------------------
```

Read-only from dashboard side. Connection managed from extension popup.

## Data Flow

### Lead Extraction

1. User browses Sales Navigator
2. Content script detects SN list page
3. Extracts leads from DOM + enriches via LinkedIn Sales API (CSRF token from cookies)
4. User clicks "Upload" in extension popup
5. Extension POSTs to /api/extension/leads with JWT auth + X-Namespace
6. API deduplicates by LinkedIn URL
7. Creates companies (if new) + contacts (tagged with source)
8. Returns `{ created: N, skipped: N }`
9. Extension popup shows success summary

### Activity Sync

1. Activity monitor runs on LinkedIn messaging/network pages
2. Scrapes conversations, extracts events with timestamps
3. Generates deterministic external_id per event
4. Every 30 min (or manual trigger): POSTs batch to /api/extension/activities
5. API deduplicates by external_id
6. Matches contacts by LinkedIn URL (creates stubs if missing)
7. Stores in activities table

### Settings Page

1. User clicks name -> Preferences
2. Dashboard fetches GET /api/extension/status
3. Shows connected/not, last sync times, totals

## Source Material

- LinkedIn Lead Uploader: `~/git/linkedin-lead-uploader/` (Chrome MV3 extension, vanilla JS)
- Airtable LinkedIn Importer: `~/git/airtable-linkedin-importer/` (Node.js CLI, company matching logic)
- Existing extension sends to Supabase (leads CSV) and n8n cloud webhooks (activities)
- All data targets are being replaced with leadgen-pipeline PostgreSQL via API
