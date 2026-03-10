#!/usr/bin/env bash
# Deploy the leadgen API to VPS
# Usage: bash deploy/deploy-api.sh

set -euo pipefail

VPS_KEY="/Users/michal/git/visionvolve-vps/LightsailDefaultKey-eu-central-1.pem"
VPS_HOST="ec2-user@52.58.119.191"
VPS_DIR="/home/ec2-user/n8n-docker-caddy"
API_DIR="/home/ec2-user/leadgen-api"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Deploying leadgen API to VPS..."

# 1. Copy Dockerfile
scp -i "$VPS_KEY" "${PROJECT_DIR}/Dockerfile.api" "${VPS_HOST}:${API_DIR}/"

# 2. Rsync entire api/ directory (includes agents/, tools/, services/memory/, services/multimodal/, services/registries/)
rsync -avz --delete \
  -e "ssh -i $VPS_KEY" \
  --exclude '__pycache__' --exclude '*.pyc' \
  "${PROJECT_DIR}/api/" "${VPS_HOST}:${API_DIR}/api/"
echo "    Synced API source files"

# 3. Copy compose overlay
scp -i "$VPS_KEY" "${PROJECT_DIR}/deploy/docker-compose.api.yml" "${VPS_HOST}:${VPS_DIR}/"
echo "    Copied docker-compose.api.yml"

# 4. Build and start the API container (--no-deps prevents Caddy recreation)
ssh -i "$VPS_KEY" "$VPS_HOST" bash <<'REMOTE'
cd /home/ec2-user/n8n-docker-caddy

COMPOSE_FILES="-f docker-compose.yml \
  -f docker-compose.mcp.yml \
  -f docker-compose.airtable-mcp.yml \
  -f docker-compose.dashboard.yml \
  -f docker-compose.api.yml \
  -f docker-compose.ds.yml \
  -f docker-compose.masterdb-mcp.yml \
  -f docker-compose.workshop.yml \
  -f docker-compose.cases.yml \
  -f docker-compose.backlog.yml \
  -f docker-compose.frontend.yml"

echo "    Compose files: $COMPOSE_FILES"
docker compose $COMPOSE_FILES up -d --no-deps --build leadgen-api
echo "    leadgen-api container started"
REMOTE

echo "==> API deployed to https://leadgen.visionvolve.com/api/health"
