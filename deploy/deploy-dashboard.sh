#!/usr/bin/env bash
# Deploy the dashboard to VPS (React SPA only + standalone roadmap.html)
# Usage: bash deploy/deploy-dashboard.sh

set -euo pipefail

VPS_KEY="/Users/michal/git/visionvolve-vps/LightsailDefaultKey-eu-central-1.pem"
VPS_HOST="ec2-user@52.58.119.191"
VPS_DIR="/home/ec2-user/n8n-docker-caddy"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="${PROJECT_DIR}/frontend"

echo "==> Building React frontend..."
cd "$FRONTEND_DIR"
npm run build
echo "    Build complete"

echo "==> Deploying dashboard to VPS..."

# 1. Create dashboard + assets directories on VPS
ssh -i "$VPS_KEY" "$VPS_HOST" "mkdir -p ${VPS_DIR}/dashboard/assets"

# 2. Deploy React SPA build output (index.html + assets/)
scp -i "$VPS_KEY" "${FRONTEND_DIR}/dist/index.html" "${VPS_HOST}:${VPS_DIR}/dashboard/"
scp -i "$VPS_KEY" ${FRONTEND_DIR}/dist/assets/* "${VPS_HOST}:${VPS_DIR}/dashboard/assets/"
scp -i "$VPS_KEY" ${FRONTEND_DIR}/dist/*.svg "${VPS_HOST}:${VPS_DIR}/dashboard/"
echo "    Copied React SPA build"

# 3. Deploy standalone pages (not part of the React SPA)
scp -i "$VPS_KEY" "${PROJECT_DIR}/dashboard/roadmap.html" "${VPS_HOST}:${VPS_DIR}/dashboard/"
echo "    Copied roadmap.html"

# 4. Clean up stale vanilla files from previous deploys
ssh -i "$VPS_KEY" "$VPS_HOST" bash <<'REMOTE'
cd /home/ec2-user/n8n-docker-caddy/dashboard
for stale in contacts.html companies.html messages.html enrich.html \
             import.html admin.html llm-costs.html echo.html playbook.html \
             pipeline-archive.html auth.js nav.js nav.css; do
  if [ -f "$stale" ]; then
    rm "$stale"
    echo "    Removed stale $stale"
  fi
done
REMOTE

# 5. Add dashboard volume to Caddy if not already present
ssh -i "$VPS_KEY" "$VPS_HOST" bash <<'REMOTE'
cd /home/ec2-user/n8n-docker-caddy

if [ ! -f docker-compose.dashboard.yml ]; then
  cat > docker-compose.dashboard.yml <<'EOF'
# Additive compose file — add dashboard volume to Caddy
# Usage: docker compose -f docker-compose.yml -f docker-compose.mcp.yml -f docker-compose.dashboard.yml up -d
services:
  caddy:
    volumes:
      - ./dashboard:/srv/dashboard:ro
EOF
  echo "    Created docker-compose.dashboard.yml"
fi

# Restart with all compose files
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.mcp.yml -f docker-compose.airtable-mcp.yml -f docker-compose.dashboard.yml -f docker-compose.api.yml -f docker-compose.ds.yml"
docker compose $COMPOSE_FILES up -d caddy
echo "    Caddy restarted"
REMOTE

echo "==> Dashboard deployed to https://leadgen.visionvolve.com/"
echo "    React SPA handles all pages"
echo "    Standalone: roadmap.html"
