# Technical Strategy

**Last updated**: 2026-03-06

## Architecture Principles

1. **Scalability**: Design for 50 tenants and 100K+ contacts. Every new feature should work for one tenant and fifty. Prefer horizontal patterns (stateless API, background workers) over vertical scaling.
2. **Security**: Multi-tenant data isolation is non-negotiable. All queries filter by `tenant_id`. Input validation at every system boundary. Audit trail for destructive operations. This is table stakes for paying customers.
3. **Developer Experience**: Fast iteration for a solo/small team. Good test coverage, easy debugging, clear code organization. If a pattern slows you down, change it. Prefer Python-native solutions over visual/no-code tools when the complexity warrants it.
4. **Modularity & Reuse**: Before building anything new, audit existing code for reusable patterns. Extract shared logic into services/utilities. Keep modules loosely coupled with clear interfaces. Every component should be testable in isolation.
5. **Lazy Loading**: Load data and resources on demand, not upfront. Paginate API responses, lazy-load dashboard sections, defer expensive operations. Users should never wait for data they haven't asked for.
6. **User Experience First**: Technical decisions serve the user, not the other way around. Optimize for perceived performance (skeleton screens, optimistic updates), clear error messages, and intuitive flows. Run `/designer review` alongside `/em review` before shipping.
7. **Zero External Lock-in**: All pipeline logic, data storage, and orchestration live in our codebase — versioned, tested, and deployable as code. n8n and Airtable dependencies are eliminated.
8. **Quality Over Cost**: Users pay per token, so quality matters more than cost optimization. Use the best model for the job — Opus when warranted, Sonnet for complex generation, Haiku for routing and simple Q&A. Warn users about token costs before expensive operations; never silently degrade quality to save tokens.

## Technology Choices

| Component | Current | Status | Rationale |
|-----------|---------|--------|-----------|
| Backend | Flask + SQLAlchemy + **Pydantic v2** | Active | Simple, fast iteration. Pydantic for validation + OpenAPI generation. |
| Database | PostgreSQL (RDS) | Active | Relational data, ACID, managed hosting |
| Frontend | **React 19 + TypeScript + Vite + Tailwind v4** | Active | Component reuse, type safety, SPA routing, TanStack Query |
| Rich Text Editor | **Tiptap** (strategy editor) | Active | Block-based editing for strategy documents. **Planned: Tiptap AI Toolkit** for copilot suggestions, agent-driven document editing, accept/reject changes. |
| Auth | JWT + bcrypt | Active | Stateless, standard |
| Infra | Single VPS (2GB) | Active | Cheap, simple |
| Reverse Proxy | Caddy | Active | Auto TLS, simple config |
| AI Integration | Claude API (Haiku/Sonnet/Opus) + Anthropic SDK | Active | Token-efficient, reliable, streaming. Best model for the job. |
| Agent Framework | Custom agent executor → **LangGraph** | **Migrating** | See Agent Architecture below |
| Agent-Frontend Protocol | Custom SSE → **AG-UI** | **Planned** | See Communication Protocols below |
| Agent-Agent Protocol | (none) → **A2A** | **Planned** | See Communication Protocols below |
| Orchestration (Pipeline) | **Python-native DAG executor** | Active | n8n fully removed. L1 enrichment native; L2/Person migration in progress. |
| Memory / Context | Hard 20-message window → **RAG + floating window** | **Planned** | Cross-session memory via retrieval; compacted window for within-session |
| Observability | Basic logging | Active | No paid observability until revenue. Self-hosted LangSmith if feasible, otherwise lightweight tracing. |

## Agent Architecture

### Current State

The agentic system powers the Playbook chat — a conversational AI interface for GTM strategy development. The current `agent_executor.py` is a monolithic loop that handles research, strategy writing, enrichment, and campaign planning in a single agent with all 24 tools available on every call.

### Decided: LangGraph Adoption

**Status: Decided — adopt now, before building custom halt gates.**

LangGraph replaces the custom agent executor as the orchestration framework. The deciding factors:

1. **Halt gates** — LangGraph has `interrupt()` built in, which is our #1 architectural need. Users need confirmation points during strategy generation (company scope, ICP direction, draft review).
2. **Multi-model routing** — Haiku for Q&A, Sonnet for generation, Opus for complex reasoning — trivial in LangGraph via conditional edges.
3. **State machine** — The current simple loop doesn't model conversation flow. LangGraph's `StateGraph` gives typed state schemas with conditional routing.
4. **Observability** — LangSmith tracing (free tier or self-hosted) provides per-node execution visibility.

**Migration approach**: Hybrid — keep Flask routes, SSE streaming adapter, tool implementations, and prompt templates. Adopt `StateGraph` for agent flow, `interrupt()` for halt gates, conditional edges for routing, and typed state schemas. The migration is internal — no API changes, no frontend changes initially.

### Decided: Multi-Agent Orchestration

**Status: Decided — implement after LangGraph migration.**

Moving from monolithic agent to orchestrator + specialist agents:

```
User <-> Orchestrator (Chat Agent)
           |-- Research Agent (web search, company profiling, market analysis)
           |-- Strategy Agent (playbook writing, section generation, framework application)
           |-- Outreach Agent (message generation, personalization, campaign planning)
           |-- Data Agent (contact enrichment, document processing, CRM queries)
```

Each specialist agent has a focused system prompt (~200 tokens vs ~2000 in monolithic), only its relevant tools, and domain-specific reasoning patterns. The orchestrator handles intent detection, agent selection, context routing, result synthesis, and halt gates.

**Orchestration patterns**: Sequential handoff (research completes, results pass to strategy), parallel fan-out (company profiler + contact enricher run simultaneously), hierarchical delegation (research agent orchestrates sub-agents).

### Decided: Adaptive Halt Gates

**Status: Decided — configurable per user preference.**

The agent decomposes work into phases and halts at critical decision points — moments where a wrong assumption would invalidate everything downstream. Gate frequency is adaptive: some users want tight control (more halts), others prefer autonomy (fewer halts). Configurable per user/namespace.

**Gate taxonomy**: Scope decisions (which product to focus on), direction decisions (which ICP segment), draft reviews (strategy looks right?), and cost confirmations (enrich 50 contacts for 500 tokens?).

## Communication Protocols

### Decided: AG-UI (Agent-User Interaction)

**Status: Decided — adopt as agent-to-frontend standard.**

AG-UI is an open protocol that streams JSON events over HTTP/SSE between agent backends and frontends. It replaces our custom SSE event types with standardized events: `TEXT_MESSAGE_*` for streaming text, `TOOL_CALL_*` for tool execution lifecycle, `STATE_DELTA` for incremental state updates, and `STATE_SNAPSHOT` for full state sync.

**What it enables**: Generative UI (agent sends state patches, frontend renders rich components inline in chat), inline approval gates (tool calls pause and show approve/reject UI), shared synchronized state between agent and frontend, and standardized tool approval UX.

**Migration**: Install `ag-ui-langgraph` package, map current SSE events to AG-UI events, update Flask endpoints and frontend ChatProvider. Our current ChatProvider SSE consumption maps directly to AG-UI event handlers.

### Decided: A2A (Agent-to-Agent)

**Status: Decided — for multi-agent orchestration.**

A2A protocol handles communication between specialist agents in the multi-agent setup. The orchestrator communicates with research, strategy, outreach, and data agents via A2A, while the user-facing layer uses AG-UI.

**Protocol stack**:
```
Frontend <-[AG-UI]-> Orchestrator <-[A2A]-> Research Agent
                                   <-[A2A]-> Strategy Agent
                                   <-[A2A]-> Outreach Agent
                                   <-[A2A]-> Data Agent
```

## Prompt Architecture

### Decided: Layered Prompt with Caching

**Status: Decided — implement prompt caching and layering.**

Split the system prompt into cacheable and dynamic layers:

| Layer | Content | Tokens | Cacheable |
|-------|---------|--------|-----------|
| **L0: Identity** | Role definition, critical rules, response style, language | ~800 | Yes (`cache_control: ephemeral`) |
| **L1: Capabilities** | Phase-filtered tool descriptions, tool usage rules, document editing rules | ~1-2K | Yes |
| **L2: Context** | Current phase instructions, section completeness, user objective, enrichment summary, relevant document sections | ~1-5K | No |
| **L3: Conversation** | Summarized older messages + recent messages verbatim + previous turn tool results | ~1-4K | No |

**Expected savings**: 50-70% input token reduction. Current per-call total is 8-20K tokens; proposed is 3-7K tokens with cached static layers. Over a 25-iteration tool loop, this saves ~31K cached input tokens per turn.

### Decided: Intent-Aware Tool Routing

**Status: Decided — phase-filtered tools.**

Only register tools relevant to the current phase. Strategy phase gets strategy tools (not campaign tools). Contacts phase gets enrichment tools (not strategy tools). Reduces schema tokens from ~2.5K (all 24 tools) to ~600-1K (6-10 phase-relevant tools) and eliminates irrelevant tool selection.

### Decided: Smart Document Context

**Status: Decided — relevant section + status (Option B).**

Include only the section the user is working on plus completeness status for all sections. Full document available via tool call when the agent needs cross-referencing. The agent can also request the full document when it determines complete context is needed.

### Decided: RAG for Long-Term Memory

**Status: Decided — RAG for cross-session, floating window for within-session.**

- **Cross-session memory**: Embed key decisions, preferences, and outcomes. Retrieve relevant context via RAG when a new session starts. The agent remembers what ICP the user approved, which messaging angles worked, and past strategy decisions.
- **Within-session memory**: Floating context window with compaction. When history exceeds 15 messages, summarize the oldest 10 into ~200 tokens preserving decisions, preferences, and tool outcomes. Keep last 8 verbatim.

## Multimodal Content Processing

**Status: Decided — phased rollout.**

The agent currently operates on text only. Multimodal processing lets the agent extract strategic intelligence directly from files users upload — pitch decks, annual reports, competitor websites, org charts, product demos.

**Phased rollout**:

| Phase | Formats | Effort | Value |
|-------|---------|--------|-------|
| 1 | PDF + Images | ~1 week | Highest — pitch decks, reports, screenshots |
| 2 | HTML + Word | ~3 days | URL analysis for competitor research, proposals |
| 3 | Excel | ~3 days | Structured data extraction, contact imports |
| 4 | Video | ~1-2 weeks | Product demos, webinars (highest complexity + cost) |

**Architecture**: Upload to S3 (or local `/uploads` in dev), store metadata in PG, dispatch to format-specific extractor, generate cached summaries, inject summaries into agent context on demand. Progressive detail levels: L0 (mention, ~20 tokens), L1 (summary, ~300-700 tokens), L2 (deep dive, up to 4K tokens via tool call).

**File size handling**: Warn users about processing costs (in tokens) before processing. Cap at reasonable limits, show estimated token cost, let user decide whether to proceed.

## Rich Text Editing — Tiptap AI Toolkit

**Status: Decided — staying on Tiptap, adopting AI Toolkit.**

The strategy editor already uses Tiptap for block-based document editing. The planned evolution adopts the Tiptap AI Toolkit for:

- **Copilot suggestions**: Agent proposes edits inline as the user works on the strategy document
- **Agent document editing**: The agent can directly modify strategy sections with tracked changes
- **Accept/reject workflow**: User sees proposed changes with diff highlighting and can accept or reject each change

This aligns with the halt gate architecture — instead of the agent rewriting sections autonomously, it proposes changes that the user reviews and approves.

## Pipeline Orchestration

### n8n Removal — Complete

**Status: Done.**

n8n has been fully removed from the pipeline architecture. All enrichment orchestration runs as Python code — versioned in git, tested in CI, deployed as part of the API container.

### Python-Native Pipeline

**Status: Active — L1 complete, L2/Person migration in progress.**

- **L1 Company Enrichment**: Runs natively via Perplexity API (`l1_enricher.py`). EU government registry adapters (ARES, BRREG, PRH, recherche-entreprises, ISIR) also run natively.
- **DAG Executor** (`dag_executor.py`): Manages stage orchestration with completion-record eligibility tracking.
- **L2 Company + Person**: Migration to full Python-native execution in progress.

**Architecture**:
- Stage definitions as Python classes (L1Enrichment, L2Enrichment, PersonEnrichment, etc.)
- DB-backed queue for execution (graduate to Redis/Celery if needed)
- Built-in cost tracking (credit consumption calculated before/during execution)
- Tenant-isolated execution contexts
- Full test coverage (unit tests per stage, integration tests for pipeline flow)

## Cost Strategy

### Model Selection

**Decision: Best model for the job. Users pay tokens, so quality first.**

| Task Type | Model | Rationale |
|-----------|-------|-----------|
| Intent routing, simple Q&A | Haiku | Fast, cheap, sufficient for classification |
| Strategy generation, research synthesis | Sonnet | Strong reasoning, good value |
| Complex multi-step reasoning | Opus | When the task warrants it — users pay for quality |

### Observability

**Decision: No paid observability until revenue.**

- Use LangSmith free tier if sufficient; evaluate self-hosted LangSmith for cost savings
- Build lightweight tracing as fallback
- Revisit when revenue justifies $100-300/mo for managed observability

### Token Transparency

All operations show estimated token cost before execution. No surprise bills. Users always know what they're paying for. Budget controls per namespace with configurable thresholds and alerts.

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

Each phase exposes only the tools relevant to the current workflow stage. This is now a core architectural pattern — see Intent-Aware Tool Routing above.

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

Campaign status transitions through `draft > ready > generating > review > approved > exported > archived`. All messages must be individually reviewed (approved or rejected) before the campaign can advance to `approved` status. This prevents unreviewed AI-generated content from reaching prospects.

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

| ID | Description | Severity | Blocks | Status |
|----|-------------|----------|--------|--------|
| TD-001 | ~~n8n workflows for enrichment~~ | ~~High~~ | — | **RESOLVED** — n8n fully removed. L1 native Python; L2/Person migration in progress. |
| TD-002 | No API rate limiting | Medium | Multi-tenant launch (abuse risk) | Open |
| TD-003 | SQLite test compat layer masks PG-specific behavior | Medium | Confidence in test results | Open |
| TD-004 | No input validation on several API routes | Medium | Security for paying customers | Open |
| TD-005 | ~~Pipeline logic locked in n8n GUI~~ | ~~High~~ | — | **RESOLVED** — all pipeline orchestration is Python-native. |
| TD-006 | JWT tokens have no revocation mechanism | Low | Account security (logout doesn't invalidate) | Open |
| TD-007 | No background job processing (all work is synchronous) | Medium | Long-running operations (bulk enrichment, PDF generation) | Open |
| TD-008 | ~~Frontend: 13K lines vanilla JS/CSS with massive duplication~~ | ~~High~~ | — | **RESOLVED** — vanilla JS fully eliminated (BL-045, 2026-02-19). React 19 + TypeScript + Tailwind v4. |
| TD-009 | No API input validation library (manual in every route) | Medium | Security, consistency, no OpenAPI docs | Open |
| TD-010 | No auto-generated API types for frontend | Medium | API contract changes silently break UI | Open |
| TD-011 | Monolithic agent executor with no halt gates or state machine | High | Agent quality, user control, multi-agent | **Addressing** — LangGraph migration decided |
| TD-012 | Database schema diagram in ARCHITECTURE.md incomplete | Low | Documentation accuracy, onboarding | Open |
| TD-013 | 30+ new API routes not listed in ARCHITECTURE.md | Low | Documentation accuracy, API discoverability | Open |
| TD-014 | All 24 tools sent on every agent call regardless of context | Medium | Token waste, model confusion | **Addressing** — intent-aware tool routing decided |
| TD-015 | No prompt caching — static tokens re-sent on every iteration | Medium | Token cost (50-70% savings available) | **Addressing** — layered prompt with caching decided |
| TD-016 | No cross-session memory — agent forgets user preferences between sessions | Medium | User experience, strategy coherence | **Addressing** — RAG for long-term memory decided |

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
- Single VPS (2GB RAM): runs Flask API, Caddy, 4 MCP servers
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
- [ ] Upgrade VPS or split services (API on separate instance)
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
| [ADR-002](adr/002-ai-column-mapping.md) | AI Column Mapping | Claude Sonnet for CSV-to-schema mapping with confidence scores and manual override |
| [ADR-003](adr/003-native-l1-enrichment.md) | Native L1 Enrichment | Python-native L1 enrichment via Perplexity API, replacing n8n workflow |
| [ADR-004](adr/004-eu-registry-adapters.md) | EU Registry Adapters | Unified registry orchestrator with country-specific adapters (ARES, BRREG, PRH, recherche, ISIR) |
| [ADR-005](adr/005-enrichment-dag-model.md) | Enrichment DAG Model | DAG-based executor with completion-record eligibility and stage dependencies |
| [ADR-006](adr/006-campaign-data-model.md) | Campaign Data Model | Campaign lifecycle, contact assignment, template presets |
| [ADR-007](adr/007-message-version-tracking.md) | Message Version Tracking | Immutable originals, edit reason tags, regeneration overrides |
| [ADR-008](adr/008-browser-extension-architecture.md) | Browser Extension Architecture | Chrome MV3 extension for Sales Navigator lead capture and activity monitoring |
| [ADR-009](adr/009-external-api-patterns.md) | External API Patterns | Patterns for integrating external APIs (OAuth, webhooks, polling) |

**Pending ADRs** (decisions made, need formal write-up):
- LangGraph adoption and migration plan
- AG-UI + A2A protocol adoption
- Multi-agent orchestration architecture
- Prompt layering and caching strategy

## Product Strategy Alignment

| Product Theme | Technical Enablers | Technical Blockers |
|--------------|-------------------|-------------------|
| Contact Intelligence | PostgreSQL data layer, CSV import pipeline, ICP filter system, Python-native enrichment | No background jobs (TD-007) |
| Outreach Engine | API platform, multi-tenant auth, campaign lifecycle, message generation | No rate limiting (TD-002) |
| Closed-Loop Analytics | PostgreSQL for analytics queries, LLM usage logging, browser extension activity capture | No async event processing, no activity ingestion API |
| Platform Foundation | Multi-tenant schema, JWT auth, namespace routing, token/credit system | Input validation gaps (TD-004/TD-009), no billing infrastructure, no API docs (TD-010) |
| Agent-Driven GTM | Playbook system, agent executor, tool registry, Claude API | Monolithic agent (TD-011), no halt gates, no cross-session memory (TD-016) |
| Playbook-Driven Execution | Phase system, auto-advance, phase-contextual tools | No prompt caching (TD-015), all tools sent every call (TD-014) |

## Decision Log (March 2026)

Architectural decisions from `docs/plans/2026-03-06-agent-prompt-architecture.md`:

| # | Decision | Summary | Status |
|---|----------|---------|--------|
| 1 | LangGraph adoption | Adopt now, before building custom halt gates. Migrate incrementally. | Decided |
| 2 | AG-UI protocol | Replace custom SSE with standardized agent-frontend events. | Decided |
| 3 | A2A protocol | Agent-to-agent communication for multi-agent orchestration. | Decided |
| 4 | Multi-agent architecture | Orchestrator + Research/Strategy/Outreach/Data specialist agents. | Decided |
| 5 | Prompt layering + caching | Static identity cached, dynamic context rebuilt per call. 50-70% token savings. | Decided |
| 6 | Intent-aware tool routing | Phase-filtered tools instead of all 24 every call. | Decided |
| 7 | Smart document context | Relevant section + status in prompt; full document via tool. | Decided |
| 8 | RAG for long-term memory | Cross-session knowledge retrieval; floating window for short-term. | Decided |
| 9 | Adaptive halt gates | Configurable per user preference — more control vs more autonomy. | Decided |
| 10 | Model selection | Best model for the job. Opus when warranted. Quality over cost. | Decided |
| 11 | Observability | No paid tools until revenue. Self-hosted LangSmith or lightweight tracing. | Decided |
| 12 | Multimodal content | Phased rollout: PDF+Images, HTML+Word, Excel, Video. | Decided |
| 13 | Tiptap AI Toolkit | Keep Tiptap, add copilot suggestions and agent document editing. | Decided |
| 14 | n8n removal | Complete. All enrichment is Python-native. | Done |
| 15 | File processing costs | Warn users, show estimated tokens, let them decide. | Decided |
| 16 | Multi-agent cost ceiling | Not yet discussed — open question. | Open |
| 17 | AG-UI adoption timing | Not yet discussed — likely concurrent with LangGraph migration. | Open |
