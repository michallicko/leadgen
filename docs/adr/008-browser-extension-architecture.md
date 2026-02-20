# ADR-008: Browser Extension Architecture

**Date**: 2026-02-20 | **Status**: Accepted

## Context

The team had a standalone Chrome extension (`~/git/linkedin-lead-uploader`) for extracting leads from LinkedIn Sales Navigator and logging LinkedIn activities. It was written in vanilla JavaScript with no type system, manual DOM scraping, and direct Airtable writes. As the leadgen pipeline matured around a PostgreSQL backend with JWT auth and multi-tenancy, the extension needed to be brought into the monorepo and integrated with the pipeline's data layer.

Key constraints driving the design:

1. **Dual-environment operation** — Sales and research teams need to work against both production and staging without risk of cross-contamination. A single extension with a settings toggle was deemed too risky after an incident where test data was accidentally written to the production Airtable base.
2. **Existing schema** — The `activities` table was created in migration 001 with an enum-based `source` column (`activity_source` type) and rigid `activity_name NOT NULL` constraints. The extension introduces new activity patterns (e.g., profile views, connection requests) that don't fit the original enum values.
3. **Unknown contacts** — The extension captures activities for LinkedIn profiles that may not yet exist as contacts in the system (e.g., viewing a prospect's profile before importing them).
4. **Auth consistency** — The dashboard already uses JWT auth against `/api/auth/login`. Having the extension use a separate auth mechanism (like API keys or Airtable PATs) would fragment the auth surface.

## Decision

### 1. TypeScript Chrome MV3 rewrite

We chose a full rewrite in TypeScript with Vite as the build system, rather than porting the existing vanilla JS extension. The original extension (~800 lines) had no types, inline DOM manipulation, and Airtable-specific logic woven throughout. A port would have preserved all of these problems.

The rewrite uses Chrome Manifest V3 (service workers instead of background pages), strict TypeScript (`strict: true`), and a Vite build pipeline that produces optimized bundles. The extension source lives at `extension/` in the monorepo (~2,650 lines of TypeScript across 8 source files, plus build config).

**Alternatives considered:**
- Port the vanilla JS as-is: rejected due to maintainability debt and MV2 deprecation timeline.
- Use a framework (React/Preact) for popup UI: rejected as over-engineering — the popup is simple enough for vanilla DOM with TypeScript types.

### 2. Two separate extension builds (prod + staging)

Instead of a runtime environment switcher, we build two distinct extensions from the same source:

- **Production**: `manifests/prod.json` merged with `manifests/base.json` — purple icons, connects to `leadgen.visionvolve.com`.
- **Staging**: `manifests/staging.json` merged with `manifests/base.json` — orange icons, connects to `leadgen-staging.visionvolve.com`.

The `vite.config.ts` accepts a `--mode prod` or `--mode staging` flag that controls which manifest overlay is applied and which API base URL is compiled in. The visual distinction (icon color) makes it immediately obvious which environment the user is interacting with.

**Alternatives considered:**
- Runtime toggle in extension settings: rejected because a single mis-click could send staging test data to production, and users would need to remember to switch back.
- Environment detection from the active tab URL: rejected as unreliable and confusing.

### 3. JWT auth reuse

The extension authenticates via the same `/api/auth/login` endpoint used by the dashboard. Tokens (access + refresh) are stored in `chrome.storage.local`, which is encrypted at rest by Chrome and scoped to the extension's origin. The extension popup shows a login form on first use; subsequent sessions use the stored token with automatic refresh.

This means no new auth mechanism, no API keys to manage, and the extension inherits all existing RBAC (role-based access control) and tenant scoping automatically.

### 4. Direct PostgreSQL API endpoints

New API routes under `/api/extension/*` write directly to PostgreSQL via the Flask API, consistent with the dashboard's data source:

- `POST /api/extension/leads` — bulk import contacts from Sales Navigator extraction
- `POST /api/extension/activities` — sync LinkedIn activities (profile views, messages, connection requests)
- `GET /api/extension/status` — check sync status and contact existence

This replaces the old pattern of the extension writing directly to Airtable via the Airtable REST API with a Personal Access Token. The extension routes reuse the same `require_auth` decorator, `resolve_tenant()` helper, and SQLAlchemy models as all other API routes.

**Alternatives considered:**
- Continue writing to Airtable and sync to PG: rejected because Airtable is now the legacy data store, and dual-write would cause consistency issues.
- Dedicated microservice for extension: rejected as over-engineering for the current scale.

### 5. ALTER TABLE migration on existing activities table

Migration 028 (`028_extension_activities.sql`) modifies the existing `activities` table rather than creating a new one:

- **Adds columns**: `event_type TEXT NOT NULL DEFAULT 'event'`, `timestamp TIMESTAMPTZ`, `payload JSONB DEFAULT '{}'`
- **Converts `source`**: from `activity_source` enum to `TEXT` — allows arbitrary source values like `linkedin_extension` without future ALTER TYPE migrations
- **Relaxes constraints**: `activity_name` becomes nullable (extension activities may not have a meaningful name)
- **Adds indexes**: composite indexes on `(tenant_id, external_id)`, `(tenant_id, contact_id)`, `(tenant_id, event_type, timestamp)`, `(tenant_id, source)` for extension query patterns

Backfill logic copies `activity_type::text` into the new `event_type` column for existing rows before applying the NOT NULL constraint.

**Alternatives considered:**
- New `extension_activities` table: rejected because activities are conceptually the same entity regardless of source, and splitting them would complicate queries that need a unified activity timeline.
- Keep the enum and add new values: rejected because enums in PostgreSQL require `ALTER TYPE ... ADD VALUE` which cannot run inside a transaction, and we anticipate more source types as integrations grow.

### 6. Stub contact creation

When the extension logs an activity for a LinkedIn profile that doesn't exist as a contact, a stub contact record is created automatically with `is_stub = true` and `import_source = 'linkedin_extension'`. This ensures no activity data is dropped.

The `contacts` table gains two new columns (also in migration 028):
- `is_stub BOOLEAN DEFAULT false`
- `import_source TEXT`

A partial index `idx_contacts_is_stub` on `(tenant_id, is_stub) WHERE is_stub = true` supports efficient queries for unresolved stubs.

**Alternatives considered:**
- Drop activities for unknown contacts: rejected because activity data is valuable for prospecting context even before a full contact record exists.
- Queue activities and create contacts lazily: rejected as adding unnecessary complexity — a stub row is simpler and immediately queryable.

## Consequences

**Positive:**
- Single monorepo contains all extension source, build config, API routes, and migration — no external dependency on the old `linkedin-lead-uploader` repo
- TypeScript catches type errors at build time; strict mode prevents common JS pitfalls (null access, implicit any)
- Two-build strategy eliminates an entire class of environment-confusion bugs
- JWT reuse means zero new auth infrastructure; extension users are managed in the same user table
- Unified activities table provides a single timeline view across all data sources (n8n enrichment, extension, future integrations)
- TEXT source column is forward-compatible with any new integration without schema changes

**Negative:**
- Two Chrome Web Store listings will be needed (one production, one staging), doubling the extension publishing overhead
- The `activities.source` column loses enum-level validation — invalid source strings are now possible (mitigated by application-level validation in the API routes)
- Stub contacts create data that needs eventual resolution: merging stubs with real contacts when they are imported through the normal pipeline, or cleaning up orphaned stubs
- The enum-to-TEXT migration is a one-way change — reverting to an enum would require a new migration and data audit
- Extension source (~2,650 lines TypeScript + build config) adds to the monorepo's footprint, though it is self-contained under `extension/`

**Trade-offs accepted:** The loss of enum-level database validation on `activities.source` is acceptable because the API layer validates source values, and the flexibility of TEXT outweighs the safety of a rigid enum for a column that will accumulate more values over time. The stub contact pattern creates cleanup work, but preserving activity data for unknown profiles is more valuable than data loss.
