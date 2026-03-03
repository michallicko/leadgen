# Technical Strategy

**Last updated**: 2026-03-02

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
| Orchestration | n8n (existing) → **removing** | Visual workflows, quick prototyping | **Hard to version, test, extend. Full removal planned.** | Now — see Migration Path below |
| Auth | JWT + bcrypt | Stateless, standard | No rate limiting, no session revocation | Adding billing or external API keys |
| Infra | Single VPS (2GB) | Cheap, simple | Shared resources | >10 tenants or sustained background processing |
| Reverse Proxy | Caddy | Auto TLS, simple config | None | Need load balancing |
| AI Integration | Claude API (Haiku/Sonnet) + Anthropic SDK | Token-efficient, reliable, streaming | Cost tracking needed, no rate limiting | Scaling to multi-provider |
| Agentic System | Custom agent executor + tool registry | Pluggable, full loop control, streaming SSE | No orchestration framework, no memory persistence | Need cross-conversation memory |
| Orchestration (Pipeline) | n8n (existing) + Python DAG (new) | n8n for existing; Python for extensibility | Dual orchestration complexity | Phase 2 complete (remove n8n) |

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

**Phase 1 Status (March 2026)**: L1 company enrichment runs natively in Python via Perplexity API (`l1_enricher.py`). EU government registry adapters (ARES, BRREG, PRH, recherche-entreprises, ISIR) also run natively in Python. L2 company, Person, and Generate workflows still use n8n orchestrator. The DAG executor (`dag_executor.py`) manages stage orchestration with completion-record eligibility tracking. Migration to full Python-native execution is in progress.

**Phase 2 (Q2 2026)**: Build Python-native pipeline engine in the Flask API. Port remaining pipeline logic to Python:
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

## Agent Executor Architecture

The agentic tool-use system powers the Playbook chat — a conversational AI interface for GTM strategy development.

### Core Loop (`agent_executor.py`)

The agent executor implements the standard agentic loop as a Python generator that yields SSE events:

1. Send messages + system prompt to Claude API
2. If response contains `tool_use` blocks, execute each tool via the registry
3. Feed tool results back to Claude as `tool_result` messages
4. Repeat until Claude produces a final text response (or max 10 iterations reached)

**SSE event types**: `chunk` (streaming text), `tool_start` (tool invocation begin), `tool_result` (tool output), `done` (turn complete with metadata).

**Rate limiting**: Per-turn limits by tool name (`TOOL_RATE_LIMITS` dict). Default 5 calls per tool per turn; `web_search` limited to 3. Prevents runaway loops and excessive API costs.

### Tool Registry (`tool_registry.py`)

Central registry with `ToolDefinition` dataclass:
- `name`: Unique identifier (e.g., `icp_filter`, `search`, `analyze`)
- `description`: Human-readable description passed to Claude's `tools` parameter
- `input_schema`: JSON Schema for parameters
- `handler`: `(args: dict, context: ToolContext) -> dict` — synchronous execution
- `requires_confirmation`: Reserved for future frontend confirmation dialogs

Tools register at app startup via `register_tool()`. Feature modules own their tool definitions (strategy tools in `strategy_tools.py`, search in `search_tools.py`, etc.).

**Registered tools**: `icp_filter`, `search`, `enrichment_gaps`, `campaign`, `analyze`, `strategy_edit`, plus phase-contextual tools.

### System Prompt Builder (`playbook_service.py`)

Constructs the system prompt that positions the AI as a GTM strategy consultant:
- Company context (profile, enrichment data, ICP, personas)
- Current strategy document (9 sections: Executive Summary through 90-Day Action Plan)
- Enrichment data formatted as structured sections (not raw JSON)
- Phase-appropriate instructions and available tools
- Chat history (last 20 messages) converted to Anthropic message format

### Streaming Transport

The Flask route consumes the generator and converts `SSEEvent` objects to wire-format Server-Sent Events. The React frontend reads the SSE stream via `EventSource` and renders chunks incrementally — tool invocations appear as collapsible cards in the chat UI.

## Playbook Phase System

The Playbook implements an 8-phase GTM workflow that guides users from raw contacts to campaign-ready outreach.

### Phases

| # | Phase | Purpose |
|---|-------|---------|
| 1 | **Contacts** | Import and organize target contacts/companies |
| 2 | **Strategy** | Develop GTM strategy with AI assistance |
| 3 | **Playbook** | Refine ICP, personas, messaging framework |
| 4 | **Enrichment** | Run L1/L2/Person enrichment pipeline |
| 5 | **Messages** | Generate personalized outreach messages |
| 6 | **Campaigns** | Configure campaign structure and templates |
| 7 | **Generation** | Bulk message generation with cost estimation |
| 8 | **Ready** | Final review, approval gate, export |

### Auto-Advance Logic (BL-114)

Phases advance automatically when completion criteria are met (e.g., Contacts phase completes when import count > 0, Strategy phase completes when all 9 strategy sections have content). Manual override available for any phase.

### Phase-Contextual Tool Availability

Each phase exposes only the tools relevant to the current workflow stage. For example, `icp_filter` is available in the Contacts phase, `strategy_edit` in the Strategy/Playbook phases, and `campaign` tools in the Campaigns phase.

### PlaybookLog Table

Records phase transitions, tool executions, and key decisions for audit trail and future closed-loop learning. Tracked via `tool_executions` and `chat_persistence` tables (migrations 034-035).

## Message Review & Version Tracking

The message review system implements a quality gate between AI-generated outreach and campaign export.

### Immutable Original Fields

Every generated message preserves `original_body` and `original_subject` as immutable fields. Manual edits update `body`/`subject` while the original is always available for diff comparison and LLM training feedback.

### Edit Reason Tags

When a user edits a message, they select structured reason tags: `tone`, `personalization`, `accuracy`, `brevity`, `relevance`. These tags feed back into prompt improvement — tracking which correction categories are most frequent per campaign or per persona.

### Regeneration with Overrides

Per-message regeneration supports overrides:
- **Language**: Target language for the message
- **Formality**: Ty/Vy (informal/formal address — critical for Czech, German, French markets)
- **Tone**: Adjustable tone slider
- **Custom instruction**: Free-text override (max 200 chars) for specific adjustments
- **Cost estimate**: Displayed before regeneration to avoid surprise token spend

### Contact Disqualification

Two modes: **campaign-only exclusion** (contact skipped for this campaign but remains in pool) and **global disqualification** (contact marked as unfit across all campaigns). Both require a reason.

### Approval Gate

Campaign status transitions through `draft → ready → generating → review → approved → exported → archived`. All messages must be individually reviewed (approved or rejected) before the campaign can advance to `approved` status. This prevents unreviewed AI-generated content from reaching prospects.

## Token/Credit System

Per-operation cost tracking enables transparent AI usage billing for multi-tenant deployment.

### Architecture

- **LLM Usage Logging** (`llm_logger.py`): Every Claude API call logs input tokens, output tokens, model, cost (USD), and operation type to `llm_usage_log` table
- **Token Balance**: Per-tenant credit balance tracked in the token system (migration 037). Credits are debited on each LLM operation.
- **Cost Estimation**: Before expensive operations (bulk generation, regeneration), the system estimates token cost and displays it to the user for confirmation
- **Budget Controls**: Per-namespace budget limits with configurable thresholds and alerts

### Display Rules

- **Namespace admins** see: token balance, usage by operation, budget remaining — all in credits/tokens
- **Super admins** see: raw USD costs, per-provider breakdown, margin analysis
- **Users** see: operation-level cost in tokens (e.g., "This will use ~450 tokens")
- 1 credit = $0.001 USD (configurable per deployment)

### API Routes

`/api/tokens/*` — balance queries, usage history, budget configuration
`/api/llm-usage/*` — detailed per-call logs (super_admin only)

## Tech Debt Register

| ID | Description | Severity | Blocks | Backlog Ref |
|----|-------------|----------|--------|-------------|
| TD-001 | n8n workflows partially migrated — L1 native Python, L2/Person/Generate still n8n | High | Full pipeline extensibility | BL-002, BL-003 |
| TD-002 | No API rate limiting | Medium | Multi-tenant launch (abuse risk) | — |
| TD-003 | SQLite test compat layer masks PG-specific behavior | Medium | Confidence in test results | — |
| TD-004 | No input validation on several API routes | Medium | Security for paying customers | — |
| TD-005 | Pipeline logic locked in n8n GUI | High | Pipeline extensibility, testing, cost tracking | See Migration Path |
| TD-006 | JWT tokens have no revocation mechanism | Low | Account security (logout doesn't invalidate) | — |
| TD-007 | No background job processing (all work is synchronous or via n8n) | Medium | Long-running operations (bulk enrichment, PDF generation) | — |
| TD-008 | ~~Frontend: 13K lines vanilla JS/CSS with massive duplication~~ | ~~High~~ | **RESOLVED** — vanilla JS fully eliminated (BL-045, 2026-02-19). All pages now React 19 + TypeScript + Tailwind v4. | `docs/specs/vanilla-js-migration/` |
| TD-009 | No API input validation library (manual in every route) | Medium | Security, consistency, no OpenAPI docs | Phase 6 of frontend migration |
| TD-010 | No auto-generated API types for frontend | Medium | API contract changes silently break UI | Phase 6 of frontend migration |
| TD-011 | Agentic tool-use loop not documented. No ADR for agent architecture, tool registry, streaming transport, rate limits. | Medium | Onboarding new contributors, architectural consistency | — |
| TD-012 | Database schema diagram in ARCHITECTURE.md incomplete. 14 new migrations (019-038) not reflected in full detail. | Low | Documentation accuracy, onboarding | — |
| TD-013 | 30+ new API routes not listed in ARCHITECTURE.md. Route inventory outdated since Sprint 3. | Low | Documentation accuracy, API discoverability | — |

**Policy**: Fix as we go. Address debt when it's in the path of a feature. No dedicated debt sprints. Run `/em audit` regularly (before each major feature) to surface new debt and refactoring opportunities.

## API Route Inventory

Current route groups registered on the Flask API (24 route modules):

| Route Group | Module | Description |
|------------|--------|-------------|
| `/api/auth/*` | `auth_routes.py` | Login, register, refresh, user info |
| `/api/tenants/*` | `tenant_routes.py` | Tenant CRUD, namespace management |
| `/api/users/*` | `user_routes.py` | User CRUD, role assignment |
| `/api/tags/*` | `tag_routes.py` | Tag management (renamed from batches) |
| `/api/companies/*` | `company_routes.py` | Company CRUD, search, enrichment data |
| `/api/contacts/*` | `contact_routes.py` | Contact CRUD, filter, ICP criteria |
| `/api/contacts/filter-counts` | `contact_routes.py` | Faceted ICP filter counts |
| `/api/contacts/job-titles` | `contact_routes.py` | Job title typeahead search |
| `/api/messages/*` | `message_routes.py` | Message CRUD, batch operations, review |
| `/api/campaigns/*` | `campaign_routes.py` | Campaign lifecycle, contact assignment |
| `/api/campaign-templates` | `campaign_routes.py` | System + tenant template presets |
| `/api/pipeline/*` | `pipeline_routes.py` | DAG executor, stage runs, status |
| `/api/enrich/*` | `enrich_routes.py` | Legacy enrichment triggers |
| `/api/imports/*` | `import_routes.py` | CSV import, Google Contacts import |
| `/api/llm-usage/*` | `llm_usage_routes.py` | LLM cost logs (super_admin) |
| `/api/oauth/*` | `oauth_routes.py` | Google OAuth flow |
| `/api/gmail/*` | `gmail_routes.py` | Gmail scan, contacts fetch |
| `/api/bulk/*` | `bulk_routes.py` | Bulk operations (delete, update) |
| `/api/extension/*` | `extension_routes.py` | Chrome extension leads/activities |
| `/api/playbook/*` | `playbook_routes.py` | Chat, strategy, phase management, agent executor |
| `/api/strategy-templates/*` | `strategy_template_routes.py` | GTM strategy template library |
| `/api/tokens/*` | `token_routes.py` | Token balance, usage, budget |
| `/api/custom-fields/*` | `custom_field_routes.py` | Tenant-defined custom fields |
| `/api/enrichment-configs/*` | `enrichment_config_routes.py` | Enrichment stage configuration |
| `/api/health` | `health.py` | Health check endpoint |

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
- No background job queue (long-running ops use background threads)

### Next Priority (blocker for multi-tenant launch)
- [ ] Add API rate limiting (per-tenant, per-endpoint) — **TD-002**
- [ ] Input validation on all route handlers — **TD-004, TD-009**
- [ ] Security headers: CSP, X-Frame-Options, X-Content-Type-Options

### Near-term (5-10 tenants, 10-30K contacts)
- [ ] Add Redis for caching (company/contact list queries) and session management
- [ ] Move to background job processing for: CSV imports, bulk enrichment, PDF generation
- [ ] Upgrade VPS or split services (API on separate instance from n8n)
- [ ] Add database connection pooling (PgBouncer or SQLAlchemy pool tuning)

### Medium-term (20-50 tenants, 100K+ contacts)
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
| [ADR-003](adr/003-native-l1-enrichment.md) | Native L1 Enrichment | Python-native L1 enrichment via Perplexity API, replacing n8n workflow |
| [ADR-004](adr/004-eu-registry-adapters.md) | EU Registry Adapters | Unified registry orchestrator with country-specific adapters (ARES, BRREG, PRH, recherche, ISIR) |
| [ADR-005](adr/005-enrichment-dag-model.md) | Enrichment DAG Model | DAG-based executor with completion-record eligibility and stage dependencies |
| [ADR-006](adr/006-campaign-data-model.md) | Campaign Data Model | Campaign lifecycle, contact assignment, template presets |
| [ADR-007](adr/007-message-version-tracking.md) | Message Version Tracking | Immutable originals, edit reason tags, regeneration overrides |
| [ADR-008](adr/008-browser-extension-architecture.md) | Browser Extension Architecture | Chrome MV3 extension for Sales Navigator lead capture and activity monitoring |
| [ADR-009](adr/009-external-api-patterns.md) | External API Patterns | Patterns for integrating external APIs (OAuth, webhooks, polling) |

## Product Strategy Alignment

| Product Theme | Technical Enablers | Technical Blockers |
|--------------|-------------------|-------------------|
| Contact Intelligence | PostgreSQL data layer, CSV import pipeline, ICP filter system | Airtable dependency (TD-001), no background jobs (TD-007) |
| Outreach Engine | API platform, multi-tenant auth, campaign lifecycle, message generation | No pipeline engine fully in Python (TD-005), no rate limiting (TD-002) |
| Closed-Loop Analytics | PostgreSQL for analytics queries, LLM usage logging | No async event processing, no activity ingestion API |
| Platform Foundation | Multi-tenant schema, JWT auth, namespace routing, token/credit system | Input validation gaps (TD-004/TD-009), no billing infrastructure, no API docs (TD-010) |
| GTM Strategy & Coaching | Playbook system, agent executor, tool registry, Claude API | None (MVP launched Sprint 4) |
