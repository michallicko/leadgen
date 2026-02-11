#!/usr/bin/env bash
# Deploy the enrichment dashboard to VPS
# Usage: bash deploy/deploy-dashboard.sh

set -euo pipefail

VPS_KEY="/Users/michal/git/visionvolve-vps/LightsailDefaultKey-eu-central-1.pem"
VPS_HOST="ec2-user@52.58.119.191"
VPS_DIR="/home/ec2-user/n8n-docker-caddy"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Deploying dashboard to VPS..."

# 1. Create dashboard directory on VPS
ssh -i "$VPS_KEY" "$VPS_HOST" "mkdir -p ${VPS_DIR}/dashboard"

# 2. Copy dashboard files (HTML + JS + SVG assets)
scp -i "$VPS_KEY" ${PROJECT_DIR}/dashboard/*.html ${PROJECT_DIR}/dashboard/*.js ${PROJECT_DIR}/dashboard/*.svg "${VPS_HOST}:${VPS_DIR}/dashboard/"
echo "    Copied dashboard files"

# 3. Add dashboard volume to Caddy if not already present
ssh -i "$VPS_KEY" "$VPS_HOST" bash <<'REMOTE'
cd /home/ec2-user/n8n-docker-caddy

# Check if dashboard compose override already exists
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
docker compose -f docker-compose.yml -f docker-compose.mcp.yml -f docker-compose.airtable-mcp.yml -f docker-compose.dashboard.yml up -d caddy
echo "    Caddy restarted"
REMOTE

echo "==> Dashboard deployed to https://leadgen.visionvolve.com/"
echo "    Note: Caddyfile is managed separately — deploy from visionvolve-vps repo if needed"
