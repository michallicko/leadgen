#!/bin/bash
# SSH tunnel to production PostgreSQL (RDS) via VPS
#
# Opens a local port forwarding tunnel:
#   localhost:5433 → RDS PostgreSQL:5432
#
# Usage:
#   bash scripts/db-tunnel.sh
#
# Then connect with any client to localhost:5433
# Press Ctrl+C to close the tunnel.

set -euo pipefail

LOCAL_PORT=5433
RDS_HOST="ls-934f096d99ba4e98dd82196e6e7470f8a9e993bc.cz6y8ke6ynad.eu-central-1.rds.amazonaws.com"
RDS_PORT=5432
VPS_HOST="52.58.119.191"
VPS_USER="ec2-user"
SSH_KEY="/Users/michal/git/visionvolve-vps/LightsailDefaultKey-eu-central-1.pem"

echo "Opening SSH tunnel: localhost:${LOCAL_PORT} → RDS:${RDS_PORT}"
echo "Press Ctrl+C to close."
echo ""

ssh -i "$SSH_KEY" \
    -N \
    -L "${LOCAL_PORT}:${RDS_HOST}:${RDS_PORT}" \
    "${VPS_USER}@${VPS_HOST}"
