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

# 1. Create API directory on VPS
ssh -i "$VPS_KEY" "$VPS_HOST" "mkdir -p ${API_DIR}/api/routes ${API_DIR}/api/services"

# 2. Copy API source files
scp -i "$VPS_KEY" "${PROJECT_DIR}/Dockerfile.api" "${VPS_HOST}:${API_DIR}/"
scp -i "$VPS_KEY" "${PROJECT_DIR}/api/requirements.txt" "${VPS_HOST}:${API_DIR}/api/"
scp -i "$VPS_KEY" ${PROJECT_DIR}/api/*.py "${VPS_HOST}:${API_DIR}/api/"
scp -i "$VPS_KEY" ${PROJECT_DIR}/api/routes/*.py "${VPS_HOST}:${API_DIR}/api/routes/"
scp -i "$VPS_KEY" ${PROJECT_DIR}/api/services/*.py "${VPS_HOST}:${API_DIR}/api/services/"
echo "    Copied API source files"

# 3. Copy compose overlay
scp -i "$VPS_KEY" "${PROJECT_DIR}/deploy/docker-compose.api.yml" "${VPS_HOST}:${VPS_DIR}/"
echo "    Copied docker-compose.api.yml"

# 4. Build and start the API container
ssh -i "$VPS_KEY" "$VPS_HOST" bash <<'REMOTE'
cd /home/ec2-user/n8n-docker-caddy

# Find all compose files in use
COMPOSE_FILES="-f docker-compose.yml"
for f in docker-compose.mcp.yml docker-compose.airtable-mcp.yml docker-compose.dashboard.yml docker-compose.api.yml; do
  [ -f "$f" ] && COMPOSE_FILES="$COMPOSE_FILES -f $f"
done

echo "    Compose files: $COMPOSE_FILES"
docker compose $COMPOSE_FILES up -d --build leadgen-api
echo "    leadgen-api container started"
REMOTE

echo "==> API deployed to https://leadgen.visionvolve.com/api/health"
