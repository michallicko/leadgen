#!/usr/bin/env bash
# Deploy the dashboard to VPS (React SPA + vanilla HTML fallbacks)
# Usage: bash deploy/deploy-dashboard.sh
#
# The React SPA (frontend/) handles: contacts, companies, messages, login
# Vanilla HTML pages (dashboard/) handle: enrich, import, admin, llm-costs, etc.
# Caddy try_files serves {path}.html first, then falls back to React's index.html

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

# 3. Deploy vanilla HTML pages that React doesn't handle yet
#    SKIP: contacts.html, companies.html, messages.html, index.html (React handles these)
VANILLA_PAGES="enrich.html import.html admin.html llm-costs.html pipeline-archive.html playbook.html roadmap.html echo.html"
for page in $VANILLA_PAGES; do
  if [ -f "${PROJECT_DIR}/dashboard/${page}" ]; then
    scp -i "$VPS_KEY" "${PROJECT_DIR}/dashboard/${page}" "${VPS_HOST}:${VPS_DIR}/dashboard/"
  fi
done
echo "    Copied vanilla HTML pages"

# 4. Deploy shared assets (nav, auth) used by vanilla pages
scp -i "$VPS_KEY" ${PROJECT_DIR}/dashboard/*.js ${PROJECT_DIR}/dashboard/*.css "${VPS_HOST}:${VPS_DIR}/dashboard/"
echo "    Copied shared JS/CSS assets"

# 5. Clean up stale vanilla files that React now handles
ssh -i "$VPS_KEY" "$VPS_HOST" bash <<'REMOTE'
cd /home/ec2-user/n8n-docker-caddy/dashboard
for stale in contacts.html companies.html messages.html; do
  if [ -f "$stale" ]; then
    rm "$stale"
    echo "    Removed stale $stale (React handles this route)"
  fi
done
REMOTE

# 6. Add dashboard volume to Caddy if not already present
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
echo "    React SPA: contacts, companies, messages, login"
echo "    Vanilla: enrich, import, admin, llm-costs, pipeline-archive, playbook, roadmap"
