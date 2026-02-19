# Technical Strategy

**Last updated**: 2026-02-16 (frontend migration strategy added)

## Architecture Principles

1. **Scalability**: Design for 50 tenants and 100K+ contacts. Every new feature should work for one tenant and fifty. Prefer horizontal patterns (stateless API, background workers) over vertical scaling.
2. **Security**: Multi-tenant data isolation is non-negotiable. All queries filter by `tenant_id`. Input validation at every system boundary. Audit trail for destructive operations. This is table stakes for paying customers.
3. **Developer Experience**: Fast iteration for a solo/small team. Good test coverage, easy debugging, clear code organization. If a pattern slows you down, change it. Prefer Python-native solutions over visual/no-code tools when the complexity warrants it.
4. **Modularity & Reuse**: Before building anything new, audit existing code for reusable patterns. Extract shared logic into services/utilities. Keep modules loosely coupled with clear interfaces. Every component should be testable in isolation.
5. **Lazy Loading**: Load data and resources on demand, not upfront. Paginate API responses, lazy-load dashboard sections, defer expensive operations. Users should never wait for data they haven't asked for.
6. **User Experience First**: Technical decisions serve the user, not the other way around. Optimize for perceived performance (skeleton screens, optimistic updates), clear error messages, and intuitive flows. Run `/designer review` alongside `/em review` before shipping.
7. **Zero External Lock-in**: Fully migrate away from n8n and Airtable. All pipeline logic, data storage, and orchestration must live in our codebase — versioned, tested, and deployable as code.

## Technology Choices

| Component | Current | Rationale | Pain Point | Revisit When |
|-----------|---------|-----------|------------|--------------|
| Backend | Flask + SQLAlchemy + **Pydantic v2** | Simple, fast iteration. Adding Pydantic for validation + OpenAPI generation. | Manual validation in routes (TD-004), no API docs, manual serialization | Adopting Pydantic incrementally alongside frontend migration |
| Database | PostgreSQL (RDS) | Relational data, ACID, managed hosting | None | >10GB data or need read replicas |
| Frontend | **React 19 + TypeScript + Vite + Tailwind v4** | Component reuse, type safety, SPA routing, TanStack Query. **Migration complete.** | None (vanilla JS eliminated 2026-02-19) | — |
| Orchestration | n8n (self-hosted) → **removing** | Visual workflows, quick prototyping | **Hard to version, test, extend. Full removal planned.** | Now — see Migration Path below |
| Auth | JWT + bcrypt | Stateless, standard | No rate limiting, no session revocation | Adding billing or external API keys |
| Infra | Single VPS (2GB) | Cheap, simple | Shared resources | >10 tenants or sustained background processing |
| Reverse Proxy | Caddy | Auto TLS, simple config | None | Need load balancing |

## Critical Architecture Decision: Pipeline Orchestration

### Problem

n8n is the current orchestration layer for enrichment pipelines (L1, L2, Person). This creates several issues:

1. **Versioning**: Workflow JSON is not in git. Changes are made in a GUI and deployed via API PUT (full replacement, no diff).
2. **Testing**: No way to unit test pipeline logic. Verification is manual execution.
3. **Extensibility**: Adding new pipeline stages (e.g., email verification, LinkedIn enrichment) requires building complex n8n node chains instead of writing Python functions.
4. **Multi-tenancy**: n8n has no native tenant isolation. Pipeline executions share a single n8n instance.
5. **Debugging**: Execution logs are in n8n's internal DB, not queryable from the platform.
6. **Cost tracking**: Credit consumption must be calculated after the fact from n8n execution data.

### Migration Path

**Phase 1 (Q1 2026)**: Keep n8n for existing workflows but eliminate Airtable dependency (BL-002, BL-003). All n8n workflows write to PostgreSQL. This is prerequisite for everything else.

**Phase 2 (Q2 2026)**: Build Python-native pipeline engine in the Flask API. Port pipeline logic to Python:
- Stage definitions as Python classes (L1Enrichment, L2Enrichment, PersonEnrichment, etc.)
- Queue-based execution (start with simple DB-backed queue, graduate to Redis/Celery if needed)
- Built-in cost tracking (credit consumption calculated before/during execution)
- Tenant-isolated execution contexts
- Full test coverage (unit tests per stage, integration tests for pipeline flow)

**Phase 3 (Q3 2026)**: Remove n8n entirely. All pipeline orchestration runs as Python code — versioned in git, tested in CI, deployed as part of the API container. n8n container is decommissioned. No "keep for ad-hoc" — clean break.

**Phase 4 (alongside Phase 2-3)**: Remove Airtable completely. After BL-002/003 migrate workflow writes to PG, delete the Airtable migration script, remove Airtable MCP dependency, and close the Airtable account. Single source of truth = PostgreSQL.

### Decision Criteria for Phase 2 Start

Begin Phase 2 when ALL of:
- BL-002 (L1 Postgres) is deployed and stable for 2+ weeks
- BL-003 (Full Migration) is at least specced
- A new pipeline stage is needed (e.g., email verification for Contact Intelligence theme)

## Tech Debt Register

| ID | Description | Severity | Blocks | Backlog Ref |
|----|-------------|----------|--------|-------------|
| TD-001 | n8n workflows write to Airtable, not PG | High | All new pipeline features | BL-002, BL-003 |
| TD-002 | No API rate limiting | Medium | Multi-tenant launch (abuse risk) | — |
| TD-003 | SQLite test compat layer masks PG-specific behavior | Medium | Confidence in test results | — |
| TD-004 | No input validation on several API routes | Medium | Security for paying customers | — |
| TD-005 | Pipeline logic locked in n8n GUI | High | Pipeline extensibility, testing, cost tracking | See Migration Path |
| TD-006 | JWT tokens have no revocation mechanism | Low | Account security (logout doesn't invalidate) | — |
| TD-007 | No background job processing (all work is synchronous or via n8n) | Medium | Long-running operations (bulk enrichment, PDF generation) | — |
| TD-008 | ~~Frontend: 13K lines vanilla JS/CSS with massive duplication~~ | ~~High~~ | **Resolved** — vanilla JS eliminated (BL-045, 2026-02-19). All pages React+TS. | `docs/specs/vanilla-js-migration/` |
| TD-009 | No API input validation library (manual in every route) | Medium | Security, consistency, no OpenAPI docs | Phase 6 of frontend migration |
| TD-010 | No auto-generated API types for frontend | Medium | API contract changes silently break UI | Phase 6 of frontend migration |

**Policy**: Fix as we go. Address debt when it's in the path of a feature. No dedicated debt sprints. Run `/em audit` regularly (before each major feature) to surface new debt and refactoring opportunities.

## Quality Standards

- **Testing**: Unit tests required for all API routes and business logic. E2E tests for key user flows. Run `pytest tests/ -v` before every merge. Target: no untested route handlers.
- **Code Review**: Self-review all changes. Check for security issues, edge cases, consistency. Use `/em review` before merge.
- **Security**: OWASP top 10 awareness. Validate at system boundaries. Never trust client input. `tenant_id` filtering on every query. No raw SQL string formatting.
- **Documentation**: ARCHITECTURE.md, CHANGELOG.md, ADR for non-trivial decisions. Required for every feature (per CLAUDE.md quality gates).
- **Modularity Audit**: Before starting any feature, scan the codebase for existing patterns, services, or utilities that can be reused. Use `/em audit` or targeted code exploration. Document shared modules in ARCHITECTURE.md.
- **UX Review**: Use `/designer review` before shipping user-facing changes. Prioritize perceived performance (lazy loading, skeleton screens, progressive rendering).

## Scalability Plan

### Current State (1 tenant, 2.6K contacts)
- Single VPS (2GB RAM): runs n8n, Flask API, Caddy, 4 MCP servers
- Single Gunicorn process, synchronous request handling
- No caching layer
- No background job queue

### Near-term (5-10 tenants, 10-30K contacts) — Q2-Q3 2026
- [ ] Add API rate limiting (per-tenant, per-endpoint)
- [ ] Add Redis for caching (company/contact list queries) and session management
- [ ] Move to background job processing for: CSV imports, bulk enrichment, PDF generation
- [ ] Upgrade VPS or split services (API on separate instance from n8n)
- [ ] Add database connection pooling (PgBouncer or SQLAlchemy pool tuning)

### Medium-term (20-50 tenants, 100K+ contacts) — Q4 2026+
- [ ] Horizontal API scaling (multiple Gunicorn workers behind load balancer)
- [ ] Read replica for heavy query workloads (company/contact browsing)
- [ ] Object storage for file uploads (S3) instead of local/container storage
- [ ] CDN for dashboard static assets
- [x] Frontend migrated to React + TS + Tailwind (BL-045, done 2026-02-19)

## Security Posture

### Current
- **Auth**: JWT with access (15min) + refresh (7d) tokens, bcrypt password hashing
- **Multi-tenancy**: `tenant_id` column on all entity tables, enforced in SQLAlchemy queries
- **TLS**: Automatic via Caddy/Let's Encrypt on all domains
- **Input validation**: Partial — some routes validate, others trust input
- **Secrets**: Environment variables, not in code. `.env` files gitignored

### Gaps (address before multi-tenant launch)
- No API rate limiting — a single tenant could DoS the system
- No CSRF protection (mitigated by JWT Bearer auth, but worth auditing)
- No token revocation — logout is client-side only
- No audit log for admin actions (table exists but not consistently populated)
- Input validation inconsistent across routes (need systematic audit)
- No Content Security Policy headers on dashboard

### Target (before first external tenant)
- Rate limiting on all public endpoints
- Input validation on all route handlers (length limits, type checks, enum validation)
- Audit log for: user creation, role changes, data deletion, pipeline triggers
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options

## Architecture Decisions

| ADR | Title | Summary |
|-----|-------|---------|
| [ADR-001](adr/001-virtual-scroll-for-tables.md) | Virtual Scroll for Tables | DOM windowing for large datasets — render ~60-80 rows regardless of data size |
| [ADR-002](adr/002-ai-column-mapping.md) | AI Column Mapping | Claude Sonnet for CSV→schema mapping with confidence scores and manual override |

## Product Strategy Alignment

| Product Theme | Technical Enablers | Technical Blockers |
|--------------|-------------------|-------------------|
| Contact Intelligence | PostgreSQL data layer, CSV import pipeline | Airtable dependency (TD-001), no background jobs (TD-007) |
| Outreach Engine | API platform, multi-tenant auth | No pipeline engine in Python (TD-005), no rate limiting (TD-002), frontend duplication slows new pages (TD-008) |
| Closed-Loop Analytics | PostgreSQL for analytics queries | No async event processing, no activity ingestion API, no charting library (React migration enables recharts) |
| Platform Foundation | Multi-tenant schema, JWT auth, namespace routing | Input validation gaps (TD-004/TD-009), no billing infrastructure, no API docs (TD-010) |
