# Leadgen Pipeline - Project Rules

## Development Philosophy

**Spec-Driven Development** — Every feature starts with a specification, not code.

## Workflow

### 1. Spec First
- Before writing any code, create a spec in `docs/specs/` as `{feature-name}.md`
- Spec must include: purpose, requirements, acceptance criteria, API contracts, data model changes, edge cases
- Review existing docs (`docs/`) to understand the bigger picture before designing
- Specs are living documents — update them as requirements evolve

### 2. Branch Per Feature
- Create a git branch for each major feature: `feature/{name}`
- Branch from `main`, merge back to `main` only when the feature is **fully complete**
- "Fully complete" = spec requirements met + tests passing + docs updated

### 3. Test-Driven Verification
- **E2E tests** (`tests/e2e/`): Cover key specs and user flows. Written against the spec before implementation.
- **Unit tests** (`tests/unit/`): Prevent regression on business logic, utilities, API routes.
- Work is **not done** until all tests pass.
- Test runner: `pytest` (Python API), browser-based for dashboard if needed.

### 4. Commit Discipline
- Commit every major increment (not just at the end)
- Commit messages: imperative, concise, reference the spec or feature
- Never commit secrets, `.env` files, or credentials

### 5. Documentation
- Update `docs/ARCHITECTURE.md` when adding/changing components
- Update relevant spec when requirements change
- Keep `CHANGELOG.md` updated with each feature merge

## Project Structure

```
leadgen-pipeline/
  api/                    # Flask API (Python)
  dashboard/              # Static frontend (HTML/JS/CSS)
  deploy/                 # Deployment scripts and Docker compose overlays
  migrations/             # SQL migration files
  scripts/                # Utility scripts
  tests/
    unit/                 # Unit tests (pytest)
    e2e/                  # End-to-end tests
    conftest.py           # Shared fixtures
  docs/
    ARCHITECTURE.md       # High-level architecture diagram and description
    specs/                # Feature specifications
    *.md                  # Other documentation
  workflows/              # n8n workflow JSON exports (gitignored)
  CLAUDE.md               # This file — project rules
  CHANGELOG.md            # Release log
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

- Python: PEP 8, type hints on public API functions
- JS: ES5 compatible (no build step, vanilla JS)
- SQL: Lowercase keywords, snake_case names
- No over-engineering — minimum complexity for current requirements
- Security: validate at system boundaries, never trust client input
