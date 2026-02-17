# Leadgen Pipeline - Project Rules

## Hard Rules (Enforced by Tooling)

- **No direct writes to main** — GitHub branch protection requires PR with 1 approval + CI passing (lint + test).
- **No production deploys from feature branches** — `deploy-api.sh` and `deploy-dashboard.sh` refuse non-main branches.
- **Stay in your worktree** — `git checkout main` and `git switch main` are denied. Always verify: `git branch --show-current`
- **Only rebase onto `origin/staging`** — `git rebase main` and `git rebase origin/main` are blocked. Feature branches always rebase onto `origin/staging`. Use `make sync`.
- **Sync before starting work** — If SessionStart shows "N commits behind origin/staging", run `make sync` before writing any code.
- **Verify before handoff** — Use `/validate` after implementation. Work is not done until the validation report says READY.

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

## Development Philosophy

**Spec-Driven Development** — Every feature starts with a specification, not code. Agents spend 80% on spec and validation, 20% on writing code.

## Planning Behavior (Plan Mode)

When entering plan mode for any feature or change:

1. **Explore** — Read relevant code, understand the current state (this is fine as-is)
2. **Ask questions** — After exploration, ALWAYS ask 3-5 clarifying questions using AskUserQuestion before proposing any design. Questions should cover:
   - **Intent**: What problem are you solving? What does success look like?
   - **Scope**: Minimum viable vs full version — which do you want?
   - **Constraints**: Timeline, compatibility, things to avoid
   - **Acceptance criteria**: How will we verify this works? (Given/When/Then)
   - **Trade-offs**: Surface any technical choices that need a business decision
3. **Design** — Only after getting answers, propose the implementation approach

This applies to plan mode, `/spec`, and brainstorming. The exploration phase informs better questions — but questions must happen before any implementation plan is written.

## Workflow

### Quick Start: `/feature <description>`

The fastest path. Describe what you need; Claude handles the full lifecycle:
backlog check → spec (with questions) → worktree → implement → validate on staging → PR.

Three mandatory pauses: (1) clarifying questions, (2) spec review, (3) human inspection of staging.
For more control, use the individual skills below (`/spec`, `/validate`, etc.).

### 0. Check Backlog
- Before starting any new feature, read `BACKLOG.md`
- Check if the requested feature already exists as a backlog item
- Identify related items that could be bundled together
- Flag dependency conflicts (don't start X if Y isn't done yet)
- Suggest the optimal feature to work on if the user is open to it
- Use `/backlog` to add new ideas or view the current backlog

### 1. Spec First (80% of Your Time)
- Run `/spec <feature>` — produces 3 documents with human review between each:
  1. `docs/specs/{name}/requirements.md` — purpose, ACs (Given/When/Then), out of scope
  2. `docs/specs/{name}/design.md` — components, data model, API contracts, UX flow, edge cases
  3. `docs/specs/{name}/tasks.md` — atomic tasks, traceability matrix (AC → task → test)
- **Do not write code until all three are approved.**
- Specs are living documents — update them as requirements evolve

### 2. Branch Per Feature (Worktree Isolation)
- Create a git branch for each major feature: `feature/{name}`
- Branch from `staging`, merge back to `staging` via PR when complete
- "Fully complete" = spec requirements met + tests passing + docs updated
- **Parallel work uses git worktrees** — multiple Claude instances run simultaneously on different features
- Worktree directory: `.worktrees/` (gitignored, project-local)
- **CRITICAL: Never `git checkout` or `git switch` branches.** You will corrupt other instances' work.
- Instead, verify you're in the correct worktree for your branch:
  ```bash
  # Check your current branch — if wrong, you're in the wrong directory
  git branch --show-current
  ```
- **Creating a new worktree** (when starting a new feature):
  ```bash
  git worktree add .worktrees/{feature-name} -b feature/{feature-name} staging
  cd .worktrees/{feature-name}
  ```
- **Using an existing worktree** (when resuming work):
  ```bash
  cd /Users/michal/git/leadgen-pipeline/.worktrees/{feature-name}
  ```
- **Listing active worktrees**: `git worktree list`
- **Cleanup after merge**: `git worktree remove .worktrees/{feature-name}`

### 2a. Merging (Pull Requests Only)
- **NEVER merge locally.** Multiple Claude instances work in parallel — local merges cause conflicts.
- **Feature branches → staging** via PR:
  ```bash
  git push -u origin feature/{name}
  gh pr create --base staging --title "Short description" --body "$(cat <<'EOF'
  ## Summary
  - bullet points

  ## Test plan
  - [ ] verification steps
  EOF
  )"
  ```
- **Hotfix branches → main** via PR (for urgent production fixes only):
  ```bash
  git push -u origin hotfix/{name}
  gh pr create --base main --title "Hotfix: description" --body "..."
  ```
- **staging → main** via PR (requires CI pass + human approval):
  ```bash
  gh pr create --base main --head staging --title "Release: description"
  ```
- After the PR is merged, clean up:
  ```bash
  git worktree remove .worktrees/{feature-name}
  git branch -d feature/{feature-name}
  ```
- If the PR has merge conflicts, rebase **in the worktree**, not on the target branch:
  ```bash
  cd .worktrees/{feature-name}
  git fetch origin
  git rebase origin/staging
  git push --force-with-lease
  ```

### 3. Test-Driven Verification
- **E2E tests** (`tests/e2e/`): Cover key specs and user flows. Written against the spec before implementation.
- **Unit tests** (`tests/unit/`): Prevent regression on business logic, utilities, API routes.
- Work is **not done** until all tests pass.
- Test runner: `pytest` (Python API), Playwright for browser verification.

### 3a. Local Verification First
- Test locally with `make test-all` (unit + Playwright E2E)
- Fix any failures before deploying

### 3b. Verify on Staging
- After local tests pass, run `/validate <feature>`
- Uses `/deploy` to push to staging, then runs Playwright browser verification
- Work is NOT done until validation report says READY FOR PR
- Only then: `gh pr create` + `bash deploy/teardown-revision.sh`

### 4. Commit Discipline
- Commit every major increment (not just at the end)
- Commit messages: imperative, concise, reference the spec or feature
- Never commit secrets, `.env` files, or credentials
- **Push to remote after every commit** — work must never exist only locally

### 5. Documentation (Mandatory — Every Feature)
- Update `docs/ARCHITECTURE.md` when adding/changing components
- Update relevant spec when requirements change
- Keep `CHANGELOG.md` updated with each feature merge
- **ADR**: Write an Architecture Decision Record in `docs/adr/` for any non-trivial technical decision (see ADR section below)
- Documentation is a **completion gate** — a feature is not done until docs are updated

### 6. Quality Gates (Mandatory — Before Merge/Deploy)
Every feature must pass ALL of these before it is considered complete:

1. **Tests**: Unit tests (`tests/unit/`) + E2E tests (`tests/e2e/`) covering the new functionality. Run `pytest tests/ -v` and verify all pass.
2. **Code review**: Self-review all changed files — check for security issues, edge cases, consistency with existing patterns.
3. **Security audit**: Check for OWASP top 10 (XSS, injection, auth bypass, etc.). Validate at system boundaries. Never trust client input.
4. **Documentation**: ARCHITECTURE.md, CHANGELOG.md, ADR (if applicable), spec updates.
5. **Backlog**: Update `BACKLOG.md` — mark completed items, add new items discovered during work. Use `/backlog` to manage.
6. **Commit + push + PR**: All work committed, pushed to remote, PR targeting `staging`. Never merge locally.

### 7. Architecture Decision Records (ADR)
- Location: `docs/adr/NNN-title.md`
- **When to write**: Any decision about technology choice, pattern adoption, data model change, performance strategy, or trade-off
- **Format**:
  ```
  # ADR-NNN: Title
  **Date**: YYYY-MM-DD | **Status**: Accepted
  ## Context
  ## Decision
  ## Consequences
  ```
- ADRs are append-only — superseded decisions get Status: Superseded with a link to the replacement

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
    ARCHITECTURE.md       # System architecture and data flow
    adr/                  # Architecture Decision Records (append-only)
    specs/                # Feature specifications (created per feature)
  BACKLOG.md              # MoSCoW-prioritized feature backlog
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

### Running Tests Locally

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

When implementing features, use the local dev loop as your primary feedback mechanism:

1. **Start dev server first** — Run `make dev` (or `DEV_SLOT=N make dev` in a worktree) at the beginning of any implementation session.
2. **Use HMR** — Edit React components and Vite picks up changes instantly. Edit Flask routes and the API auto-reloads. Verify in the browser, not by re-reading code.
3. **Run unit tests frequently** — `make test` is fast (SQLite in-memory). Run after every meaningful code change.
4. **Run E2E against dev server** — `make test-e2e` (or `DEV_SLOT=N make test-e2e`) hits the running Vite+Flask for full browser verification.
5. **Local first, staging second** — Only deploy to staging when implementation is complete and `make test-all` passes locally.

### Parallel Worktree Development

Multiple Claude instances can run dev servers simultaneously using `DEV_SLOT`:

| Slot | Flask | Vite | Usage |
|------|-------|------|-------|
| 0 | 5001 | 5173 | Main worktree (default) |
| 1 | 5002 | 5174 | Feature worktree 1 |
| 2 | 5003 | 5175 | Feature worktree 2 |
| N | 5001+N | 5173+N | Nth worktree |

**Commands:**
```bash
bash scripts/worktree.sh my-feature   # Create worktree + set tab title + launch Claude
bash scripts/worktree.sh --list       # List active worktrees
DEV_SLOT=1 make dev                   # Start Flask+Vite on slot 1
DEV_SLOT=1 make test-e2e              # Run E2E tests against slot 1
make dev-status                        # Show all active slots + PG status
make agents                            # List active agents (from registry)
make pr-scan                           # Check open PRs for file conflicts before creating yours
```

**Rules:**
- Each worktree must use a unique slot — check `make dev-status` before starting
- Slot 0 is for the main worktree; feature worktrees use 1+
- All slots share one PostgreSQL container — never `docker compose down` while other slots are active
- `.env.dev` is auto-copied from the main worktree if missing
- `.venv` falls back to the main worktree's virtualenv
- `node_modules` is auto-installed on first run
- **Before creating a PR**, run `make pr-scan` to detect file overlaps with other open PRs

**Safety hooks** (`.claude/settings.json`, active in all instances):
- **SessionStart**: Injects branch, worktree root, **staleness vs origin/staging**, and **list of other active agents**
- **UserPromptSubmit**: Re-injects branch on **every** user message (survives context compression)
- **PreToolUse guard (Write/Edit)**: Warns when targeting a file outside the current worktree **and detects file conflicts with other worktrees** (uncommitted changes to same file)
- **PreToolUse guard (Bash)**: Blocks `git rebase main/master`, warns on non-staging rebase targets

**Agent registry** (`.worktrees/registry.json`):
- Auto-populated by `scripts/worktree.sh` when launching a new agent
- SessionStart reads it to show other active agents
- `make agents` lists all registered agents + cleans up stale entries (dead PIDs)

## Deployment Rules

**Claude must NEVER run deploy scripts directly.** Use `/deploy` skill instead.

Forbidden commands (Claude must not execute):
- `bash deploy/deploy-api.sh`
- `bash deploy/deploy-dashboard.sh`
- `bash deploy/deploy-revision.sh`

The `/deploy` skill enforces:

| Branch | Deploy target | Checks |
|--------|---------------|--------|
| `feature/*` | BLOCKED | Run locally with `make dev` |
| `staging` | Staging VPS | All committed, tests pass |
| `main` | Production | All committed, tests pass, user confirms |

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

- **Root** always serves the latest staging commit (dashboard + API)
- **Feature branches** deploy API-only as `/api-rev-{commit}/` — test via `?rev={commit}` query param
- The `?rev=` param makes the dashboard route API calls to the revision's backend

## Key Commands

```bash
# Local development
make dev              # Start PG + Flask + Vite (hot reload)
DEV_SLOT=1 make dev               # Start on slot 1 (Flask=5002, Vite=5174)
make dev-status                   # Show active dev slots + PG status
make sync                         # Fetch + rebase onto origin/staging
make agents                       # List active agents from registry
make pr-scan                      # Check open PRs for file conflicts
bash scripts/worktree.sh my-feat  # Create worktree + launch Claude in it
make db-pull          # Pull staging DB to local PG
make test             # Unit tests (pytest)
make test-e2e         # Playwright browser tests
make test-all         # Unit + E2E tests
make lint             # Ruff + ESLint

# Deployment (use /deploy skill — never run these directly)
# bash deploy/deploy-revision.sh    → /deploy (on staging branch)
# bash deploy/deploy-api.sh         → /deploy (on main branch)
# bash deploy/deploy-dashboard.sh   → /deploy (on main branch)

# Tear down a feature revision
bash deploy/teardown-revision.sh [commit]

# Deploy Caddy config
cd /Users/michal/git/visionvolve-vps && bash scripts/deploy-caddy.sh
```

## Code Standards

- Python: PEP 8, type hints encouraged on public functions
- JS: ES5 compatible (no build step, vanilla JS)
- SQL: Lowercase keywords, snake_case names
- No over-engineering — minimum complexity for current requirements
- Security: validate at system boundaries, never trust client input
