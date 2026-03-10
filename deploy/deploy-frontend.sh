#!/usr/bin/env bash
# Deploy the React frontend to VPS
# Usage: bash deploy/deploy-frontend.sh

set -euo pipefail

VPS_KEY="/Users/michal/git/visionvolve-vps/LightsailDefaultKey-eu-central-1.pem"
VPS_HOST="ec2-user@52.58.119.191"
VPS_DIR="/home/ec2-user/n8n-docker-caddy"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Building frontend..."
cd "${PROJECT_DIR}/frontend"
npm run build
echo "    Build complete"

echo "==> Deploying frontend to VPS..."

# Create frontend directory on VPS
ssh -i "$VPS_KEY" "$VPS_HOST" "mkdir -p ${VPS_DIR}/frontend"

# Copy built files
scp -i "$VPS_KEY" -r "${PROJECT_DIR}/frontend/dist/"* "${VPS_HOST}:${VPS_DIR}/frontend/"
echo "    Copied frontend build"

# Ensure frontend compose override exists and reload Caddy
ssh -i "$VPS_KEY" "$VPS_HOST" bash <<'REMOTE'
cd /home/ec2-user/n8n-docker-caddy

# Check if frontend compose override exists
if [ ! -f docker-compose.frontend.yml ]; then
  cat > docker-compose.frontend.yml <<'EOF'
# Additive compose file — add frontend volume to Caddy
services:
  caddy:
    volumes:
      - ./frontend:/srv/frontend:ro
EOF
  echo "    Created docker-compose.frontend.yml"
fi

# Full list of ALL compose overlays — omitting any file when targeting caddy
# drops volume mounts and domain blocks, breaking production sites.
# See: Feb 23 incident, Mar 9 backlog incident.
COMPOSE_FILES="-f docker-compose.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.mcp.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.airtable-mcp.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.dashboard.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.api.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.ds.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.masterdb-mcp.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.workshop.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.cases.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.backlog.yml"
COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.frontend.yml"
# Append any additional overlays that exist (future-proofing)
for f in docker-compose.iam.yml; do
  [ -f "$f" ] && COMPOSE_FILES="${COMPOSE_FILES} -f $f"
done

# Static files are already copied to ./frontend/ which is bind-mounted.
# If Caddy is already running with the volume, a reload is sufficient.
# Only use 'up -d caddy' (with ALL compose files) if the volume mount is new.
if docker compose ${COMPOSE_FILES} ps caddy --format '{{.Status}}' 2>/dev/null | grep -q "Up"; then
  # Caddy is running — just reload config (no recreation, no risk)
  docker compose ${COMPOSE_FILES} exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile 2>/dev/null \
    && echo "    Caddy config reloaded" \
    || echo "    Caddy reload not needed (static files served directly)"
else
  # Caddy not running or needs volume mount — recreate with ALL compose files
  docker compose ${COMPOSE_FILES} up -d caddy
  echo "    Caddy started with frontend volume"
fi
REMOTE

echo "==> Frontend deployed to https://leadgen.visionvolve.com/"
