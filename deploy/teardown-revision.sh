#!/usr/bin/env bash
# Tear down a staging revision: stop container, remove compose file, clean Caddyfile route.
# Usage: bash deploy/teardown-revision.sh <commit>
#
# Pass "all" to tear down ALL revisions (keeps only "latest").

set -euo pipefail

STAGING_KEY="/Users/michal/Downloads/LightsailDefaultKey-eu-central-1 (1).pem"
STAGING_HOST="ec2-user@3.124.110.199"
STAGING_DIR="/home/ec2-user"

if [ -z "${1:-}" ]; then
  echo "Usage: bash deploy/teardown-revision.sh <commit|all>"
  echo ""
  echo "Active revisions:"
  ssh -i "$STAGING_KEY" "$STAGING_HOST" "docker ps --format '{{.Names}}' | grep 'leadgen-api-rev-' | grep -v 'latest' | sed 's/leadgen-api-rev-/  /'"
  exit 1
fi

TARGET="$1"

teardown_one() {
  local COMMIT="$1"
  local CONTAINER="leadgen-api-rev-${COMMIT}"

  echo "==> Tearing down revision ${COMMIT}..."

  ssh -i "$STAGING_KEY" "$STAGING_HOST" bash <<REMOTE
cd ${STAGING_DIR}

# Stop and remove container
COMPOSE_FILE="docker-compose.api-rev-${COMMIT}.yml"
if [ -f "\$COMPOSE_FILE" ]; then
  docker compose -f docker-compose.yml -f "\$COMPOSE_FILE" stop ${CONTAINER} 2>/dev/null || true
  docker compose -f docker-compose.yml -f "\$COMPOSE_FILE" rm -f ${CONTAINER} 2>/dev/null || true
  rm -f "\$COMPOSE_FILE"
  echo "    Removed compose file and container"
else
  docker stop ${CONTAINER} 2>/dev/null || true
  docker rm ${CONTAINER} 2>/dev/null || true
  echo "    Removed container (no compose file found)"
fi

# Remove API source directory
rm -rf "leadgen-api-rev-${COMMIT}"
echo "    Removed API source"

# Remove dashboard build
rm -rf "/srv/dashboard-rev-${COMMIT}"
echo "    Removed dashboard build"

# Remove Caddyfile route
CADDYFILE="${STAGING_DIR}/Caddyfile"
if grep -q "api-rev-${COMMIT}" "\$CADDYFILE"; then
  # Remove the handle_path block for this revision
  sed -i "/handle_path \/api-rev-${COMMIT}/,/}/d" "\$CADDYFILE"
  echo "    Removed Caddyfile route"
fi
REMOTE

  echo "    Revision ${COMMIT} torn down"
}

if [ "$TARGET" = "all" ]; then
  echo "==> Finding all revision containers..."
  REVISIONS=$(ssh -i "$STAGING_KEY" "$STAGING_HOST" "docker ps -a --format '{{.Names}}' | grep 'leadgen-api-rev-' | grep -v 'latest' | sed 's/leadgen-api-rev-//'")

  if [ -z "$REVISIONS" ]; then
    echo "    No revisions found"
    exit 0
  fi

  for REV in $REVISIONS; do
    teardown_one "$REV"
  done

  # Reload Caddy after all removals
  echo ""
  echo "==> Reloading Caddy..."
  ssh -i "$STAGING_KEY" "$STAGING_HOST" bash <<REMOTE
cd ${STAGING_DIR}
COMPOSE_FILES="-f docker-compose.yml"
for f in docker-compose.api-rev-*.yml; do
  [ -f "\$f" ] && COMPOSE_FILES="\$COMPOSE_FILES -f \$f"
done
docker compose \$COMPOSE_FILES exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || \
  docker compose \$COMPOSE_FILES restart caddy
REMOTE

  # Prune unused images
  echo "==> Pruning unused Docker images..."
  ssh -i "$STAGING_KEY" "$STAGING_HOST" "docker image prune -f" | tail -1

  echo ""
  echo "==> All revisions torn down"
else
  teardown_one "$TARGET"

  # Reload Caddy
  echo ""
  echo "==> Reloading Caddy..."
  ssh -i "$STAGING_KEY" "$STAGING_HOST" bash <<REMOTE
cd ${STAGING_DIR}
COMPOSE_FILES="-f docker-compose.yml"
for f in docker-compose.api-rev-*.yml; do
  [ -f "\$f" ] && COMPOSE_FILES="\$COMPOSE_FILES -f \$f"
done
docker compose \$COMPOSE_FILES exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || \
  docker compose \$COMPOSE_FILES restart caddy
REMOTE
fi

echo ""
echo "==> Done"
