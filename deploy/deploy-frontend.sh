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

# Restart Caddy to pick up changes
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

# Get full list of compose files
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.mcp.yml -f docker-compose.airtable-mcp.yml -f docker-compose.dashboard.yml -f docker-compose.api.yml -f docker-compose.ds.yml"
if [ -f docker-compose.frontend.yml ]; then
  COMPOSE_FILES="${COMPOSE_FILES} -f docker-compose.frontend.yml"
fi

docker compose ${COMPOSE_FILES} up -d caddy
echo "    Caddy restarted with frontend volume"
REMOTE

echo "==> Frontend deployed to https://leadgen.visionvolve.com/"
