# Leadgen Pipeline - Project Rules

## Development Philosophy

**Spec-Driven Development** — Every feature starts with a specification, not code.

## Workflow

### 0. Check Backlog
- Before starting any new feature, read `BACKLOG.md`
- Check if the requested feature already exists as a backlog item
- Identify related items that could be bundled together
- Flag dependency conflicts (don't start X if Y isn't done yet)
- Suggest the optimal feature to work on if the user is open to it
- Use `/backlog` to add new ideas or view the current backlog

### 1. Spec First
- Before writing any code, create a spec in `docs/specs/` as `{feature-name}.md`
- Spec must include: purpose, requirements, acceptance criteria, API contracts, data model changes, edge cases
- Review existing docs (`docs/`) to understand the bigger picture before designing
- Specs are living documents — update them as requirements evolve

### 2. Branch Per Feature (Worktree Isolation)
- Create a git branch for each major feature: `feature/{name}`
- Branch from `main`, merge back to `main` only when the feature is **fully complete**
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
  git worktree add .worktrees/{feature-name} -b feature/{feature-name}
  cd .worktrees/{feature-name}
  ```
- **Using an existing worktree** (when resuming work):
  ```bash
  # Main repo dir has one branch; others are in .worktrees/
  cd /Users/michal/git/leadgen-pipeline/.worktrees/{feature-name}
  ```
- **Listing active worktrees**: `git worktree list`
- **Cleanup after merge**: `git worktree remove .worktrees/{feature-name}`

### 3. Test-Driven Verification
- **E2E tests** (`tests/e2e/`): Cover key specs and user flows. Written against the spec before implementation.
- **Unit tests** (`tests/unit/`): Prevent regression on business logic, utilities, API routes.
- Work is **not done** until all tests pass.
- Test runner: `pytest` (Python API), browser-based for dashboard if needed.

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
6. **Commit + push**: All work committed and pushed to remote.

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
  deploy/                 # Deployment scripts and Docker compose overlays
  migrations/             # SQL migration files (001-004)
  scripts/                # Utility scripts (Airtable migration)
  tests/
    unit/                 # Unit tests (pytest)
    e2e/                  # End-to-end tests
    conftest.py           # Shared fixtures + SQLite compat layer
  docs/
    ARCHITECTURE.md       # System architecture and data flow
    adr/                  # Architecture Decision Records (append-only)
    specs/                # Feature specifications (created per feature)
    postgres-migration.md # Airtable → PostgreSQL migration design
  BACKLOG.md              # MoSCoW-prioritized feature backlog
  CLAUDE.md               # This file — project rules
  CHANGELOG.md            # Release log
  README.md               # Project overview and quick start
```

## Tech Stack

- **Backend**: Flask + SQLAlchemy + PostgreSQL (RDS)
- **Frontend**: Vanilla HTML/JS/CSS (no framework) — served by Caddy
- **Orchestration**: n8n (self-hosted) for enrichment pipeline workflows
- **Deployment**: Docker on VPS (52.58.119.191), Caddy reverse proxy
- **Auth**: JWT (bcrypt passwords, access + refresh tokens)
- **Multi-tenant**: Shared PG schema with `tenant_id` column + namespace URL routing

## Infrastructure

| Service | URL | Container |
|---------|-----|-----------|
| Dashboard | `leadgen.visionvolve.com/{namespace}/` | Caddy (static files) |
| API | `leadgen.visionvolve.com/api/*` | `leadgen-api` (Flask/Gunicorn) |
| n8n | `n8n.visionvolve.com` | `n8n` |
| DB | RDS PostgreSQL | External (AWS Lightsail) |

## Key Commands

```bash
# Deploy API
bash deploy/deploy-api.sh

# Deploy dashboard
bash deploy/deploy-dashboard.sh

# Deploy Caddy config
cd /Users/michal/git/visionvolve-vps && bash scripts/deploy-caddy.sh

# Run tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run e2e tests only
pytest tests/e2e/ -v
```

## Code Standards

- Python: PEP 8, type hints encouraged on public functions
- JS: ES5 compatible (no build step, vanilla JS)
- SQL: Lowercase keywords, snake_case names
- No over-engineering — minimum complexity for current requirements
- Security: validate at system boundaries, never trust client input
