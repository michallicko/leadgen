# Changelog

All notable changes to the Leadgen Pipeline project.

## [Unreleased]

### Added
- **Enrichment DAG Model** (BL-015, BL-016, ADR-005): Replace linear `company.status` routing with DAG-based stage completion tracking
  - `entity_stage_completions` table: per-entity, per-stage completion records with cost and error tracking (migration 016)
  - Stage registry (`stage_registry.py`): 11 configurable stages with hard/soft dependencies, country gates, execution modes
  - DAG executor (`dag_executor.py`): eligibility builder replacing hardcoded `ELIGIBILITY_QUERIES`, cross-entity-type dependency resolution, country-gate auto-skip, reactive polling threads
  - QC checker (`qc_checker.py`): end-of-pipeline quality checks — registry name mismatch, HQ country conflict, active insolvency, dissolved status, data completeness, low registry confidence
  - Interactive DAG dashboard (`enrich.html`): 2-step wizard with column-based DAG visualization, SVG bezier edges, 6 node states, soft dependency toggles, 5s polling
  - API endpoints: `POST /pipeline/dag-run`, `GET /pipeline/dag-status`, `POST /pipeline/dag-stop`
  - Backward compatible: old `/pipeline/start` and `/enrich/start` endpoints still work
  - 88 new unit tests (stage registry, completions model, DAG executor, QC checker)
- **Native L1 Enrichment** (ADR-003): Company enrichment via Perplexity sonar API, replacing n8n webhook
  - `l1_enricher.py`: Domain resolution, Perplexity API call, JSON parsing, field mapping, QC validation
  - 8 QC checks: name mismatch, incomplete research, revenue/employee sanity, low confidence, B2B unclear, short summary, source warning
  - Contact LinkedIn URLs passed to Perplexity for better company identification
  - Companies routed to `triage_passed` (clean) or `needs_review` (flagged) or `enrichment_failed` (error)
  - Research data stored in `research_assets` table with confidence/quality scores
  - Cost tracked in `llm_usage_log` with Perplexity pricing ($1/1M tokens)
  - Pipeline engine hybrid dispatch: L1 runs native Python, L2/Person/Generate still via n8n
  - Review API: `GET /api/enrich/review` (list flagged companies), `POST /api/enrich/resolve` (approve/retry/skip)
  - Dashboard: L2/person/generate disabled with "Coming soon" badges, progress counters, ETA, inline review list
  - 105 unit tests (enricher) + 32 tests (enrich routes), spec, ADR-003
- **EU Registry Adapters** (BL-017 partial): Company registry enrichment from 4 EU government APIs, all free ($0.00/lookup)
  - **Registry adapter pattern** (`api/services/registries/`): `BaseRegistryAdapter` ABC with shared name matching (bigram Dice + legal suffix stripping), result storage, and pipeline dispatch. ADR-004.
  - **Czech ARES** (`ares` stage): ICO/DIC, legal form, directors, capital, NACE codes, insolvency via ares.gov.cz
  - **Norway BRREG** (`brreg` stage): organisasjonsnummer, legal form, NACE codes, capital, bankruptcy via data.brreg.no
  - **Finland PRH** (`prh` stage): Y-tunnus, company form, TOL codes, trade register status via avoindata.prh.fi
  - **France recherche** (`recherche` stage): SIREN, nature juridique, NAF codes, directors via api.gouv.fr
  - `company_registry_data` table with `registry_country` discriminator (migration 013)
  - Generic on-demand endpoint: `POST /api/companies/<id>/enrich-registry/<country>`
  - Dashboard: 4 registry modules in enrichment wizard
  - Backward-compatible import shim for existing `api/services/ares.py` references
  - 62 new tests (adapters + parsers + routes)
- **ISIR Insolvency Check** (BL-017 partial): Czech Insolvency Register via SOAP/XML CUZK web service
  - `api/services/registries/isir.py`: SOAP client for isir.justice.cz:8443, XML parsing, proceeding status mapping
  - `company_insolvency_data` table (migration 014): stores proceedings, active/historical status, case numbers, court info
  - Pipeline integration: `isir` stage in enrichment wizard, runs on Czech companies with ICO
  - 11 proceeding statuses mapped: pending, moratorium, insolvency_declared, bankruptcy, reorganization, debt_relief, etc.
  - Zero cost ($0.00/lookup), no authentication required
  - 27 unit tests covering SOAP parsing, query, enrichment, and storage
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
