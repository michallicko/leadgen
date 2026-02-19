#!/usr/bin/env bash
# Deploy a feature branch as an API + frontend revision to STAGING.
# Usage: bash deploy/deploy-revision.sh [commit]
#
# If commit is omitted, uses the short SHA of HEAD.
# Creates:
#   - leadgen-api-rev-{commit} container on staging
#   - /srv/dashboard-rev-{commit} static files
#   - Caddyfile route for /api-rev-{commit}/*

set -euo pipefail

STAGING_KEY="/Users/michal/Downloads/LightsailDefaultKey-eu-central-1 (1).pem"
STAGING_HOST="ec2-user@3.124.110.199"
STAGING_DIR="/home/ec2-user"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve commit hash
COMMIT="${1:-$(git -C "$PROJECT_DIR" rev-parse --short=7 HEAD)}"
BRANCH="$(git -C "$PROJECT_DIR" branch --show-current)"
CONTAINER="leadgen-api-rev-${COMMIT}"

echo "==> Deploying revision ${COMMIT} (branch: ${BRANCH}) to staging..."
echo "    Container: ${CONTAINER}"

# ---- 1. Build frontend ----
echo ""
echo "==> Building frontend..."
cd "${PROJECT_DIR}/frontend"
npm run build 2>&1 | tail -3
echo "    Frontend build complete"

# ---- 2. Copy API source to staging ----
echo ""
echo "==> Copying API source to staging..."
API_REMOTE="${STAGING_DIR}/leadgen-api-rev-${COMMIT}"

ssh -i "$STAGING_KEY" "$STAGING_HOST" "mkdir -p ${API_REMOTE}/api/routes ${API_REMOTE}/api/services ${API_REMOTE}/api/services/registries"

scp -i "$STAGING_KEY" "${PROJECT_DIR}/Dockerfile.api" "${STAGING_HOST}:${API_REMOTE}/"
scp -i "$STAGING_KEY" "${PROJECT_DIR}/api/requirements.txt" "${STAGING_HOST}:${API_REMOTE}/api/"
scp -i "$STAGING_KEY" ${PROJECT_DIR}/api/*.py "${STAGING_HOST}:${API_REMOTE}/api/"
scp -i "$STAGING_KEY" ${PROJECT_DIR}/api/routes/*.py "${STAGING_HOST}:${API_REMOTE}/api/routes/"
scp -i "$STAGING_KEY" ${PROJECT_DIR}/api/services/*.py "${STAGING_HOST}:${API_REMOTE}/api/services/"
# Copy registry adapters if they exist
if ls ${PROJECT_DIR}/api/services/registries/*.py 1>/dev/null 2>&1; then
  scp -i "$STAGING_KEY" ${PROJECT_DIR}/api/services/registries/*.py "${STAGING_HOST}:${API_REMOTE}/api/services/registries/"
fi
echo "    API source copied"

# ---- 3. Copy frontend build ----
echo ""
echo "==> Copying frontend build to staging..."
ssh -i "$STAGING_KEY" "$STAGING_HOST" "sudo mkdir -p /srv/dashboard-rev-${COMMIT} && sudo chown ec2-user:ec2-user /srv/dashboard-rev-${COMMIT}"
scp -i "$STAGING_KEY" -r "${PROJECT_DIR}/frontend/dist/"* "${STAGING_HOST}:/srv/dashboard-rev-${COMMIT}/"
echo "    Frontend build copied to /srv/dashboard-rev-${COMMIT}"

# ---- 4. Generate docker-compose overlay ----
echo ""
echo "==> Generating docker-compose overlay..."

ssh -i "$STAGING_KEY" "$STAGING_HOST" bash <<REMOTE
cat > ${STAGING_DIR}/docker-compose.api-rev-${COMMIT}.yml <<'COMPOSE'
services:
  leadgen-api-rev-${COMMIT}:
    build:
      context: ./leadgen-api-rev-${COMMIT}
      dockerfile: Dockerfile.api
    container_name: leadgen-api-rev-${COMMIT}
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://\${DB_POSTGRESDB_USER}:\${DB_POSTGRESDB_PASSWORD}@\${DB_POSTGRESDB_HOST}:\${DB_POSTGRESDB_PORT}/leadgen_staging?sslmode=require
      - JWT_SECRET_KEY=\${LEADGEN_JWT_SECRET}
      - CORS_ORIGINS=https://leadgen-staging.visionvolve.com
      - ANTHROPIC_API_KEY=\${ANTHROPIC_API_KEY:-}
      - PERPLEXITY_API_KEY=\${PERPLEXITY_API_KEY:-}
    networks:
      - default
COMPOSE
echo "    Created docker-compose.api-rev-${COMMIT}.yml"
REMOTE

# ---- 5. Update Caddyfile with revision route ----
echo ""
echo "==> Updating Caddyfile..."

ssh -i "$STAGING_KEY" "$STAGING_HOST" python3 - "${STAGING_DIR}/Caddyfile" "${COMMIT}" "${CONTAINER}" <<'PYEOF'
import sys
caddyfile, commit, container = sys.argv[1], sys.argv[2], sys.argv[3]

with open(caddyfile, 'r') as f:
    content = f.read()

if f'api-rev-{commit}' in content:
    print(f'    Route /api-rev-{commit}/* already exists in Caddyfile')
else:
    block = (
        f'    # --- rev:{commit} ---\n'
        f'    handle_path /api-rev-{commit}/* {{\n'
        f'        reverse_proxy {container}:5000\n'
        f'    }}\n'
        f'    # --- /rev:{commit} ---\n'
    )
    content = content.replace('    handle /api/* {', block + '    handle /api/* {')
    with open(caddyfile, 'w') as f:
        f.write(content)
    print(f'    Added /api-rev-{commit}/* route to Caddyfile')
PYEOF

# ---- 6. Build and start containers ----
echo ""
echo "==> Building and starting containers..."

ssh -i "$STAGING_KEY" "$STAGING_HOST" bash <<REMOTE
cd ${STAGING_DIR}

# Gather all compose files
COMPOSE_FILES="-f docker-compose.yml"
for f in docker-compose.api-rev-*.yml; do
  [ -f "\$f" ] && COMPOSE_FILES="\$COMPOSE_FILES -f \$f"
done

echo "    Compose files: \$COMPOSE_FILES"

# Build and start the new revision container
docker compose \$COMPOSE_FILES up -d --build ${CONTAINER}
echo "    ${CONTAINER} started"

# Reload Caddy to pick up new routes
docker compose \$COMPOSE_FILES exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || \
  docker compose \$COMPOSE_FILES restart caddy
echo "    Caddy reloaded"
REMOTE

# ---- 7. Report ----
echo ""
echo "==========================================="
echo "  Revision ${COMMIT} deployed to staging"
echo "==========================================="
echo ""
echo "  API:       https://leadgen-staging.visionvolve.com/api-rev-${COMMIT}/api/health"
echo "  Dashboard: https://leadgen-staging.visionvolve.com/visionvolve/?rev=${COMMIT}"
echo ""
echo "  To tear down: bash deploy/teardown-revision.sh ${COMMIT}"
echo ""
