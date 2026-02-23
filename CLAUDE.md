# Leadgen Pipeline - Project Rules

<!-- sdlc-tier: product -->

> This project uses the **global SDLC plugin** for feature specs (`/spec`), backlog management (`/backlog`), product strategy (`/pm`), technical health (`/em`), and design review (`/pd`). Project-specific rules below override or extend the global workflow. The `/roadmap` skill is project-local.

## Hard Rules (Enforced by Tooling)

- **No direct writes to main** — GitHub branch protection requires PR with 1 approval + CI passing (lint + test).
- **No production deploys from feature branches** — `deploy-api.sh` and `deploy-dashboard.sh` refuse non-main branches.
- **Stay in your worktree** — `git checkout main` and `git switch main` are denied. Always verify: `git branch --show-current`
- **Only rebase onto `origin/staging`** — `git rebase main` and `git rebase origin/main` are blocked. Feature branches always rebase onto `origin/staging`. Use `make sync`.
- **Sync before starting work** — If SessionStart shows "N commits behind origin/staging", run `make sync` before writing any code.
- **Verify before handoff** — Use `/validate` after implementation. Work is not done until the validation report says READY.
- **Lead agent NEVER does work** — In delegation mode, the lead coordinator NEVER reads source files, writes code, calls MCP tools for data gathering, runs bash commands, or does any extensive work (more than 1 tool call). ALL work is delegated to spawned agents. "Let me just read this first" is building. Delegate it.
- **Start every session from the backlog dashboard** — `docs/backlog/index.html` is the source of truth for the development plan. Open it first, check sprint status, see where we left off, then pick up from there. Never start work without consulting the dashboard.
- **Everything goes through the backlog** — When the user requests a new feature, improvement, or reports a bug: (1) Create a JSON file in `docs/backlog/items/BL-XXX.json` and add the ID to `docs/backlog/config.json`, (2) Assign priority (Must Have/Should Have/Could Have), (3) Write a spec (problem, acceptance criteria, technical approach), (4) Assign to a sprint. **No implementation starts without a backlog entry and spec.** Even single-line bug fixes get a backlog entry (lightweight: problem + fix + test plan). This ensures nothing is lost, work is prioritized, and the dashboard stays the single source of truth.

## Branch Model

```
main ──────────────────────────────── production (deploy-api.sh, deploy-dashboard.sh)
  ↑ PR (requires CI pass + 1 approval)
staging ───────────────────────────── latest beta (deploy-revision.sh → staging VPS)
  ↑ PR (feature branches merge here)
feature/* ─────────────────────────── agent work (deploy-revision.sh → staging VPS under /rev-{slug}/)
hotfix/*  ─────────────────────────── urgent fixes (can PR directly to main)
```

| Branch | Merges to | Deploy target | CI required |
|--------|-----------|---------------|-------------|
| `feature/*` | `staging` via PR | Staging as `/rev-{slug}/` | Yes (on push) |
| `hotfix/*` | `main` via PR | Staging first, then production | Yes (required for merge) |
| `staging` | `main` via PR | Staging as "latest beta" | Yes (required for merge) |
| `main` | — | Production | — |

## Multi-Worktree Setup

- **Parallel work uses git worktrees** — multiple Claude instances run simultaneously on different features
- Worktree directory: `.worktrees/` (gitignored, project-local)
- **CRITICAL: Never `git checkout` or `git switch` branches.** You will corrupt other instances' work.
- Verify you're in the correct worktree: `git branch --show-current`

**Creating a new worktree:**
```bash
git worktree add .worktrees/{feature-name} -b feature/{feature-name} staging
cd .worktrees/{feature-name}
```

**Using an existing worktree:**
```bash
cd /Users/michal/git/leadgen-pipeline/.worktrees/{feature-name}
```

**Merging (Pull Requests Only):**
- NEVER merge locally. Multiple Claude instances work in parallel.
- Feature → staging via PR, hotfix → main via PR, staging → main via PR.
- After merge: `git worktree remove .worktrees/{feature-name}`
- Merge conflicts: rebase in the worktree, `git rebase origin/staging && git push --force-with-lease`

**Port slots for parallel dev servers:**

| Slot | Flask | Vite | Usage |
|------|-------|------|-------|
| 0 | 5001 | 5173 | Main worktree (default) |
| 1 | 5002 | 5174 | Feature worktree 1 |
| 2 | 5003 | 5175 | Feature worktree 2 |
| N | 5001+N | 5173+N | Nth worktree |

**Safety hooks** (`.claude/settings.json`):
- **SessionStart**: Injects branch, staleness vs origin/staging, active agents
- **UserPromptSubmit**: Re-injects branch on every user message
- **PreToolUse guard (Write/Edit)**: Warns on files outside worktree, detects cross-worktree conflicts
- **PreToolUse guard (Bash)**: Blocks `git rebase main/master`

**Agent registry** (`.worktrees/registry.json`): Auto-populated, `make agents` to list.

## Project Structure

```
leadgen-pipeline/
  .worktrees/             # Git worktrees for parallel feature work (gitignored)
  api/                    # Flask API (auth, tenants, users, messages, batches)
  dashboard/              # Static frontend (HTML/JS/CSS)
  frontend/               # React SPA (Vite + TypeScript)
  deploy/                 # Deployment scripts and Docker compose overlays
    staging/              # Staging VPS config (Caddyfile, docker-compose)
  migrations/             # SQL migration files (001-004)
  scripts/                # Utility scripts (Airtable migration, staging DB)
  tests/
    unit/                 # Unit tests (pytest)
    e2e/                  # End-to-end tests
    conftest.py           # Shared fixtures + SQLite compat layer
  docs/
    vision/               # Product vision microsite (the north star)
    ARCHITECTURE.md       # System architecture and data flow
    adr/                  # Architecture Decision Records (append-only)
    specs/                # Feature specifications (created per feature)
  docs/backlog/           # Backlog dashboard + JSON items (source of truth)
  BACKLOG.md              # DEPRECATED — see docs/backlog/
  CLAUDE.md               # This file — project rules
  CHANGELOG.md            # Release log
  README.md               # Project overview and quick start
```

## Tech Stack

- **Backend**: Flask + SQLAlchemy + PostgreSQL (RDS)
- **Frontend**: React SPA (Vite) + vanilla HTML pages — served by Caddy
- **Orchestration**: n8n (self-hosted) for enrichment pipeline workflows
- **Deployment**: Docker on VPS, Caddy reverse proxy
- **Auth**: JWT (bcrypt passwords, access + refresh tokens)
- **Multi-tenant**: Shared PG schema with `tenant_id` column + namespace URL routing
- **CI**: GitHub Actions (ruff lint + pytest on push/PR)

## Product Vision

The product vision is documented at `docs/vision/index.html` — a self-contained microsite describing the closed-loop GTM engine (Try → Run → Evaluate → Improve).

**Consult this vision when making design decisions.** Every feature should move us closer to:
- AI as proactive strategist, not passive tool
- Closed-loop learning from campaign results
- Zero busywork for the founder (auto-save, auto-extract, guided flow)
- Multi-phase workflow: Strategy → Contacts → Messages → Campaign

Key design principles from the vision:
- The founder is the CEO, the AI is the strategist
- Every interaction should gather a decision or deliver a result
- The AI gets smarter with every cycle
- Never show harsh/judgmental language about prospects or companies

## Local Development

### Prerequisites

- Docker Desktop (for PostgreSQL)
- Python 3.13+ with pip
- Node.js 20+ with npm

### One-Time Setup

```bash
bash scripts/init-env.sh    # Pull secrets from VPS → .env.dev
make db-pull                 # Pull staging DB to local PG (port 5433)
cd frontend && npm install   # Install frontend deps + Playwright
npx playwright install       # Install browser binaries
```

### Quick Start

```bash
make dev         # Start PG + Flask (auto-reload) + Vite (HMR)
```

Opens:
- Dashboard: http://localhost:5173
- API: http://localhost:5001/api/health
- Login: `test@staging.local` / `staging123`

### Running Tests

```bash
make test        # Unit tests (pytest)
make test-e2e    # Playwright browser tests (requires make dev running)
make test-all    # Both
make lint        # Ruff + ESLint
```

### Database

```bash
make db-pull     # Refresh local DB from staging
make db-reset    # Empty local DB (then db-pull to restore)
```

### Dev-First Workflow

1. Start dev server first — `make dev` (or `DEV_SLOT=N make dev` in a worktree)
2. Use HMR — Vite picks up React changes instantly, Flask auto-reloads
3. Run unit tests frequently — `make test` is fast (SQLite in-memory)
4. Run E2E against dev server — `make test-e2e`
5. Local first, staging second — only deploy when `make test-all` passes

### Worktree Commands

```bash
bash scripts/worktree.sh my-feature   # Create worktree + set tab title + launch Claude
bash scripts/worktree.sh --list       # List active worktrees
DEV_SLOT=1 make dev                   # Start Flask+Vite on slot 1
DEV_SLOT=1 make test-e2e              # Run E2E tests against slot 1
make dev-status                        # Show all active slots + PG status
make agents                            # List active agents (from registry)
make pr-scan                           # Check open PRs for file conflicts
```

## Deployment Rules

**Claude must NEVER run deploy scripts directly.** Use `/deploy` skill instead.

Forbidden commands:
- `bash deploy/deploy-api.sh`
- `bash deploy/deploy-dashboard.sh`
- `bash deploy/deploy-revision.sh`

| Branch | Deploy target | Checks |
|--------|---------------|--------|
| `feature/*` | BLOCKED | Run locally with `make dev` |
| `staging` | Staging VPS | All committed, tests pass |
| `main` | Production | All committed, tests pass, user confirms |

### Staging Rev Deployments

- **Root** always serves the latest staging commit (dashboard + API)
- **Feature branches** deploy API-only as `/api-rev-{commit}/` — test via `?rev={commit}` query param
- The `?rev=` param makes the dashboard route API calls to the revision's backend

## Infrastructure

### Production (52.58.119.191)

| Service | URL | Container |
|---------|-----|-----------|
| Dashboard | `leadgen.visionvolve.com/{namespace}/` | Caddy (static files) |
| API | `leadgen.visionvolve.com/api/*` | `leadgen-api` (Flask/Gunicorn) |
| n8n | `n8n.visionvolve.com` | `n8n` |
| DB | RDS PostgreSQL (`leadgen`) | External (AWS Lightsail) |

### Staging (3.124.110.199)

| Service | URL | Container |
|---------|-----|-----------|
| Dashboard | `leadgen-staging.visionvolve.com/` | Caddy (static files) |
| API (latest) | `leadgen-staging.visionvolve.com/api/*` | `leadgen-api-rev-latest` |
| API (revision) | `leadgen-staging.visionvolve.com/api-rev-{commit}/*` | `leadgen-api-rev-{commit}` |
| DB | RDS PostgreSQL (`leadgen_staging`) | Same RDS instance |

## Key Commands

```bash
# Local development
make dev              # Start PG + Flask + Vite (hot reload)
DEV_SLOT=1 make dev   # Start on slot 1 (Flask=5002, Vite=5174)
make dev-status       # Show active dev slots + PG status
make sync             # Fetch + rebase onto origin/staging
make agents           # List active agents from registry
make pr-scan          # Check open PRs for file conflicts
make db-pull          # Pull staging DB to local PG
make test             # Unit tests (pytest)
make test-e2e         # Playwright browser tests
make test-all         # Unit + E2E tests
make lint             # Ruff + ESLint

# Deployment (use /deploy skill — never run these directly)
bash deploy/teardown-revision.sh [commit]
cd /Users/michal/git/visionvolve-vps && bash scripts/deploy-caddy.sh
```

## Sprint Methodology

Work is organized in **sprints** — batches of backlog items grouped to maximize parallelization and minimize deployment/testing overhead.

### Sprint Planning (Lead Agent Decides)

The lead agent plans each sprint by:
1. **Selecting items from backlog** — group items that share dependencies, touch the same systems, or can be deployed together
2. **Sizing the team** — decide how many engineers based on sprint scope (2-6 typical)
3. **Mapping parallelism** — identify which items can run simultaneously vs which must be sequential
4. **Batching deploys** — group items so they deploy and test together (1 staging deploy per sprint, not per item)

### Sprint Team Composition (Mandatory)

Every sprint has these roles (spawned as agents):

| Role | Agent Type | Responsibility |
|------|-----------|----------------|
| **PM** | `sdlc:pm-analyst` | Scope validation, acceptance criteria, user story clarity |
| **EM** | `sdlc:em-analyst` | Architecture review, code review, technical strategy alignment |
| **PD** | `sdlc:pd-analyst` | UX review, design consistency, accessibility |
| **QA** | `general-purpose` | E2E tests, staging verification, regression testing |
| **Engineers (N)** | `general-purpose` | Implementation, unit tests, lint — one per parallel track |

Lead decides N (engineers) based on how many items can run in parallel. PM, EM, PD, QA are always present.

### Sprint Lifecycle

```
1. PLAN        Lead selects items, maps dependencies, sizes team
2. SPEC CHECK  PM + EM + PD verify specs meet Development-Ready gates
3. IMPLEMENT   Engineers build in parallel (separate worktrees)
4. REVIEW      EM runs code review + security scan on all PRs
5. DESIGN QA   PD reviews UI/UX on all frontend changes
6. DEPLOY      QA deploys all PRs to staging (batched)
7. E2E TEST    QA runs Playwright + acceptance criteria on staging
8. MERGE       All PRs merged to staging together
9. RETRO       Lead updates backlog, captures learnings
```

### Optimization Rules

- **Batch dependencies**: If B depends on A, put them in the same sprint — A builds first, B starts when A's PR is ready (not merged)
- **Minimize deploy cycles**: One staging deploy per sprint (merge all PRs, deploy once, test once)
- **Parallel worktrees**: Each engineer gets their own worktree — no blocking on shared branches
- **Shared base**: If items share a dependency PR, later items branch from that PR's branch (not staging)
- **Gate batching**: Run code review + security scan on ALL sprint PRs at once (one EM pass, not N passes)

### Agent Context Rules (CRITICAL)

**Every spawned agent starts with FRESH context.** Agents cannot see the conversation history, backlog discussions, or decisions made in the lead's session. The lead MUST pass all relevant context explicitly.

**What to include in every agent prompt:**
1. **Task scope** — exactly what to build/research, no ambiguity
2. **Relevant specs** — paste or reference the spec sections that apply (don't say "see the design doc" — quote the relevant parts or tell them which file + section to read)
3. **Architecture decisions** — any decisions from this session that affect the work (e.g., "chat is app-level not page-level", "no n8n, Python only")
4. **File locations** — exact paths to read, create, or modify
5. **Acceptance criteria** — what "done" looks like for this specific task
6. **Constraints** — what NOT to do (e.g., "don't touch PlaybookPage.tsx, it's being refactored by another agent")
7. **Workflow** — exact steps: implement → test → lint → commit → push → PR → report

**What NOT to assume agents know:**
- Previous agent results (pass them explicitly)
- Backlog item details (quote the relevant task)
- Design decisions from chat (state them as facts)
- Other agents' work (list what's in flight and what to avoid)

**Anti-pattern**: "Build the auto-save feature" (agent has no context)
**Correct**: Full prompt with setup steps, files to read, what to change, acceptance criteria, test commands, and workflow.

### Sprint Sizing Guide

| Sprint Size | Engineers | Items | Duration |
|-------------|-----------|-------|----------|
| Small | 2 | 2-3 items | ~1 session |
| Medium | 3-4 | 4-6 items | ~2 sessions |
| Large | 5-6 | 7-10 items | ~3 sessions |

### Live Backlog Dashboard

The backlog dashboard at `docs/backlog/index.html` shows:
- All items with priority, effort, status, dependencies, assignee
- Sprint groupings with progress tracking
- Kanban and table views with filters
- Auto-refreshes from embedded JSON (future: `/api/backlog` endpoint)

## Definition of Development-Ready

A feature is **development-ready** when ALL of the following are complete. No code is written until this gate passes.

1. **Full specification** — Written spec with: problem statement, user stories, acceptance criteria (Given/When/Then), data model changes, API contracts, UI wireframes or descriptions
2. **Product strategy alignment** — Reviewed against `docs/vision/index.html` and `PRODUCT_STRATEGY.md`. The feature moves us closer to the north star, not sideways.
3. **Technical strategy alignment** — Reviewed against `docs/TECHNICAL_STRATEGY.md`. No architectural contradictions, tech debt is acknowledged and planned for.
4. **Usability perspective** — UX flow reviewed: is this zero-busywork? Does every interaction gather a decision or deliver a result? Accessibility considered.
5. **Challenge round 1** — Spec presented to a critical reviewer (agent or human). Questions answered, gaps filled, scope trimmed if needed.
6. **Challenge round 2** — Revised spec re-reviewed. Reviewer confirms: "This is ready to build." No open questions remain.

**Skip conditions**: Hotfixes and single-line bug fixes can skip to a lightweight version (problem + fix + test plan).

## Definition of Done

A feature is **done** when ALL of the following gates pass in order. Work is not complete until every gate is green.

### Gate 1: Code Quality
- [ ] All unit tests pass (`make test`)
- [ ] All lint checks pass (`make lint` — Ruff + ESLint)
- [ ] No new security vulnerabilities (OWASP top 10 scan)
- [ ] Code review passed (confidence >= 80%, no Critical/Important findings)

### Gate 2: Security Audit
- [ ] Security scanner run — no Critical or Important findings
- [ ] Input validation at all system boundaries
- [ ] No secrets in code, no hardcoded credentials
- [ ] Auth/authz checks on all new endpoints

### Gate 3: Staging Revision + Automated E2E
- [ ] Deployed to staging revision (`deploy-revision.sh`)
- [ ] Playwright E2E tests pass against staging revision (run by agent, NOT the user)
- [ ] Acceptance criteria verified via Playwright against the revision
- [ ] No regressions in existing E2E tests
- [ ] Tear down revision container after tests pass (free staging resources)

### Gate 4: Review & Audit
- [ ] Code review by `feature-dev:code-reviewer` or human (confidence >= 80%)
- [ ] Security audit by `sdlc:security-scanner` (no Critical/Important)
- [ ] Spec compliance verified (all acceptance criteria met)

### Gate 5: Documentation
- [ ] CHANGELOG.md updated
- [ ] ARCHITECTURE.md updated (if architectural changes)
- [ ] ADR written (if significant decision made)
- [ ] API docs updated (if endpoints changed)
- [ ] Backlog items marked Done

### Gate 6: Merge to Staging
- [ ] PR created to staging with passing CI
- [ ] PR approved (1 approval required)
- [ ] Merged to staging
- [ ] Staging root deployment verified (auto-deploys on merge)
- [ ] User notified: "Feature X is ready for testing on staging"

**Gate order is strict**: Code Quality → Security → Staging Rev + E2E → Review → Docs → Merge. Do not skip ahead.

### Testing Responsibilities
- **Agents do**: Deploy to staging revision, run Playwright E2E, verify acceptance criteria, tear down revision, code review, security audit, merge to staging
- **User does**: Manual testing on staging root AFTER features are merged. User tests the integrated experience, not individual revisions.
- **Flow**: Agent builds → Agent deploys rev → Agent runs E2E → Agent reviews → Agent merges to staging → User tests on staging root
- **Manual test scripts**: `docs/testing/sprint-{N}-manual-tests.md` — used by the user for staging root testing

## Code Standards

- Python: PEP 8, type hints encouraged on public functions
- JS: ES5 compatible (no build step, vanilla JS)
- SQL: Lowercase keywords, snake_case names
- No over-engineering — minimum complexity for current requirements
- Security: validate at system boundaries, never trust client input
