# Changelog

All notable changes to the Leadgen Pipeline project.

## [Unreleased]

### Added
- Project structure: CLAUDE.md rules, ARCHITECTURE.md, test infrastructure
- Git repository initialized with GitHub remote
- Flask API: auth (login/refresh/me), tenants CRUD, users CRUD
- Dashboard: Pipeline control, Messages review, Admin panel
- JWT authentication with namespace-based multi-tenancy
- Namespace URL routing via Caddy
- Namespace switcher dropdown in nav (superadmin + multi-namespace users)
- PostgreSQL schema v1.0 (16 entity tables, 30 enums, multi-tenant)

### Fixed
- Ambiguous SQLAlchemy joins on UserTenantRole (two FKs to users table)
- Missing tenant_routes.py in API deployments
