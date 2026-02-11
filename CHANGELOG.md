# Changelog

All notable changes to the Leadgen Pipeline project.

## [Unreleased]

### Added
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
