---
name: deploy
description: Safe deployment to staging or production. Use when the user says "deploy", "push to staging", "push to production", or "ship it".
user_invocable: true
---

# Deploy Skill

Guided deployment with safety checks. Determines target from the current branch.

## Branch → Target Mapping

| Branch | Target | Scripts |
|--------|--------|---------|
| `feature/*` | BLOCKED | Cannot deploy feature branches. Use `make dev` locally. |
| `staging` | Staging VPS | `deploy-revision.sh` (API only, as `/api-rev-{commit}/`) |
| `main` | Production | `deploy-api.sh` + `deploy-dashboard.sh` |
| `hotfix/*` | Staging first | Same as staging, then promote to main via PR |

## Procedure

### Step 1: Verify branch and state

```bash
BRANCH=$(git branch --show-current)
echo "Branch: $BRANCH"
git status --porcelain
```

- If uncommitted changes exist: STOP. Ask user to commit first.
- If branch is `feature/*`: STOP. Tell user feature branches cannot be deployed.

### Step 2: Run tests

```bash
make lint && make test
```

- If tests fail: STOP. Fix before deploying.
- For `main` deploys, also run `make test-e2e` if dev server is available.

### Step 3: Confirm with user

Before running any deploy script, show:
- **Branch**: current branch name
- **Target**: staging or production
- **Last commit**: subject + hash
- **Test status**: pass/fail

Ask: "Deploy to [target]? (y/n)"

### Step 4: Deploy

**For `main` (production):**
```bash
bash deploy/deploy-api.sh
bash deploy/deploy-dashboard.sh
```

**For `staging`:**
```bash
bash deploy/deploy-revision.sh
```

### Step 5: Verify

```bash
# Production
curl -s https://leadgen.visionvolve.com/api/health | python3 -m json.tool

# Staging
curl -s https://leadgen-staging.visionvolve.com/api/health | python3 -m json.tool
```

Report the health check result to the user.

## CRITICAL RULES

- NEVER deploy from a feature branch
- NEVER skip the test step
- ALWAYS confirm with the user before running deploy scripts
- ALWAYS run the health check after deploy
- If deploying to production, migration must have been run first
