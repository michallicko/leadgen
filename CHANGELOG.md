# Changelog

All notable changes to the Leadgen Pipeline project.

## [Unreleased]

### Added
- **ARES Registry Enrichment** (BL-017 partial): Czech public register data for companies via ares.gov.cz
  - `company_registry_data` table: ICO, DIC, official name, legal form, directors, capital, NACE codes, insolvency flags
  - ARES service (`api/services/ares.py`): ICO lookup, name search with fuzzy matching (Czech suffix stripping), VR (commercial register) for directors/capital
  - Pipeline stage `ares`: direct Python HTTP calls (no n8n), $0.00 cost, integrated into pipeline engine with `DIRECT_STAGES` dispatch pattern
  - On-demand endpoints: `POST /api/companies/<id>/enrich-registry`, `POST /api/companies/<id>/confirm-registry`
  - Dashboard: "Legal & Registers (ARES)" module in enrichment wizard, registry data section in company detail
  - Migration 012, ADR-003, 50 new tests
- **Gmail Contact Extraction** (BL-025 + BL-026): Google OAuth integration, Google Contacts import, and Gmail email scan
  - Google OAuth 2.0 flow with Fernet-encrypted token storage (`oauth_connections` table, migration 011)
  - Google Contacts import via People API — structured field mapping, flows into existing dedup engine
  - Gmail email scan — background thread parses message headers (From/To/CC), extracts signatures via batched Claude Haiku calls
  - OAuth routes: connect/disconnect Google accounts (`/api/oauth/*`)
  - Gmail routes: contacts fetch, scan start/status, dedup preview, execute import (`/api/gmail/*`)
  - Google import integrated as source tab on Import page (CSV / Google Account)
  - 82 new unit tests (google_oauth, google_contacts, gmail_routes, gmail_scanner)
- **LLM Cost Logging**: Per-call cost tracking for all LLM API usage with super admin dashboard
  - `llm_usage_log` table with tenant/user attribution, token counts, cost (NUMERIC 10,6), duration, metadata
  - Logger service with model-specific pricing (Sonnet, Haiku, Opus) and Decimal arithmetic
  - CSV column mapping (Claude API) instrumented with timing and usage extraction
  - Super admin API: `GET /api/llm-usage/summary` (aggregated totals, by_tenant, by_operation, time_series), `GET /api/llm-usage/logs` (paginated, filterable)
  - LLM Costs dashboard page with Chart.js charts (daily cost, cost by operation), breakdown table, recent calls
  - Migration 009, 21 new tests
- **Contact List Import** (BL-006): CSV upload with AI-powered column mapping, dedup preview, and batch import
  - AI column mapping via Claude API (Sonnet) with confidence scores and manual override (ADR-002)
  - Contact dedup: LinkedIn URL → email → name+company hierarchy, 3 strategies (skip/update/create_new)
  - Company dedup: domain → name matching, always links to existing
  - Import wizard page with 3-step flow: Upload → Map Columns → Preview & Import
  - `import_jobs` table tracking full import lifecycle (migration 007)
  - 5 API endpoints: upload, preview, execute, status, list
  - Import nav link added to all dashboard pages (editor+ role)
  - 80 new unit tests (csv_mapper, dedup, import routes)
- Companies & Contacts dashboard pages with infinite scroll and virtual DOM windowing (ADR-001)
- Virtual scroll: only ~60-80 DOM rows rendered at any time, constant performance regardless of dataset size
- Companies API routes: list (paginated, filterable), detail, PATCH update
- Contacts API routes: list (paginated, filterable), detail, PATCH update
- Pipeline API routes: start, stop, status, run-all, stop-all
- Architecture Decision Records (ADR) framework in `docs/adr/`
- Mandatory quality gates in CLAUDE.md: tests, code review, security audit, documentation, backlog, commit+push
- Project structure: CLAUDE.md rules, ARCHITECTURE.md, test infrastructure
- Git repository initialized with GitHub remote (`michallicko/leadgen`)
- Flask API: auth (login/refresh/me), tenants CRUD, users CRUD, messages CRUD, batches/stats
- Dashboard: Pipeline control, Messages review, Admin panel
- JWT authentication with bcrypt password hashing
- Namespace-based multi-tenancy with URL routing via Caddy
- Namespace switcher dropdown in nav (superadmin + multi-namespace users)
- PostgreSQL schema v1.0: 16 entity tables + 3 junction tables, ~30 enums, multi-tenant
- Identity tables: `users`, `user_tenant_roles` with role hierarchy (admin/editor/viewer)
- Seed migration for VisionVolve tenant and initial data
- Airtable record ID indexes for upsert operations during data migration
- Airtable-to-PostgreSQL migration script (`scripts/migrate_airtable_to_pg.py`)
- 37 unit tests covering auth, tenants, and users API routes
- SQLite test compatibility layer (PG types → SQLite for local testing)
- Deploy scripts for API (`deploy-api.sh`) and dashboard (`deploy-dashboard.sh`)

### Fixed
- Ambiguous SQLAlchemy joins on UserTenantRole (two FKs to users table)
- Missing `tenant_routes.py` in API deployments (file not copied by initial deploy)
- Password mismatch for seeded users (reset to known credentials)

### Infrastructure
- PostgreSQL `leadgen` database created on existing RDS instance
- Migrations 001-004 applied (schema, identity, seed, indexes)
- `leadgen-api` Docker container running on VPS (Gunicorn, port 5000)
- Caddy configured: `/api/*` → Flask, `/{namespace}/*` → static dashboard
- Dashboard deployed at `leadgen.visionvolve.com`
