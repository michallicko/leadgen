#!/usr/bin/env bash
# Pull the staging PostgreSQL database from RDS (via staging VPS) into local Docker PG.
#
# Usage:
#   bash scripts/pull-staging-db.sh
#   make db-pull
#
# Environment:
#   LEADGEN_SSH_KEY  — path to SSH key for staging VPS (auto-detected if unset)
#
# Prerequisites:
#   - Local PG running: docker exec leadgen-dev-pg pg_isready -U leadgen
#   - Or start it: make dev  (then Ctrl+C after PG is up, or run this in another tab)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
STAGING_HOST="3.124.110.199"
STAGING_USER="ec2-user"
LOCAL_PG_CONTAINER="leadgen-dev-pg"
LOCAL_PG_PORT=5433
LOCAL_PG_USER="leadgen"
LOCAL_PG_PASS="leadgen"
LOCAL_PG_DB="leadgen"
STAGING_DB="leadgen_staging"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ---------------------------------------------------------------------------
# Resolve SSH key (same logic as init-env.sh)
# ---------------------------------------------------------------------------
resolve_ssh_key() {
  if [ -n "${LEADGEN_SSH_KEY:-}" ] && [ -f "$LEADGEN_SSH_KEY" ]; then
    echo "$LEADGEN_SSH_KEY"
    return
  fi

  local candidates=(
    "/Users/michal/Downloads/LightsailDefaultKey-eu-central-1 (1).pem"
    "$HOME/.ssh/lightsail-staging.pem"
    "$HOME/.ssh/LightsailDefaultKey-eu-central-1.pem"
  )

  for key in "${candidates[@]}"; do
    if [ -f "$key" ]; then
      echo "$key"
      return
    fi
  done

  echo ""
}

SSH_KEY="$(resolve_ssh_key)"
if [ -z "$SSH_KEY" ]; then
  echo "ERROR: Cannot find SSH key for staging VPS."
  echo "  Set LEADGEN_SSH_KEY=/path/to/key.pem and re-run."
  echo "  Searched: common locations under ~/.ssh and ~/Downloads"
  exit 1
fi

# Helper: run a command on the staging VPS
run_ssh() {
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new \
    "${STAGING_USER}@${STAGING_HOST}" "$@"
}

# ---------------------------------------------------------------------------
# Verify local PG is running
# ---------------------------------------------------------------------------
echo "==> Checking local PostgreSQL..."
if docker exec "$LOCAL_PG_CONTAINER" pg_isready -U "$LOCAL_PG_USER" -q 2>/dev/null; then
  echo "    Local PG is running (port $LOCAL_PG_PORT)."
else
  echo "ERROR: Local PostgreSQL is not running."
  echo "  Start it with: make dev  (or start just PG with docker compose)"
  exit 1
fi

# ---------------------------------------------------------------------------
# Upload dump helper script to VPS
# ---------------------------------------------------------------------------
# The RDS password contains special chars ($, #, ', [, ]) that break shell
# escaping. We upload a self-contained script that reads .env on the VPS
# directly, avoiding any password transit through the local shell.
echo "==> Preparing remote dump script..."

run_ssh "cat > /tmp/_dump_staging.sh" <<'DUMP_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
# Read DB credentials from .env — handle values containing '=' and surrounding quotes
while IFS= read -r line; do
  key="${line%%=*}"
  val="${line#*=}"
  # Strip surrounding single quotes if present
  val="${val#\'}"
  val="${val%\'}"
  case "$key" in
    DB_POSTGRESDB_HOST)     PGHOST="$val" ;;
    DB_POSTGRESDB_PORT)     PGPORT="$val" ;;
    DB_POSTGRESDB_USER)     PGUSER="$val" ;;
    DB_POSTGRESDB_PASSWORD) PGPASSWORD="$val" ;;
  esac
done < <(grep '^DB_POSTGRESDB_' /home/ec2-user/.env)
PGPORT="${PGPORT:-5432}"

# Use a postgres:17 container to match the RDS server version (17.x).
# The VPS system pg_dump may be too old and refuse to dump.
exec docker run --rm -e PGPASSWORD="$PGPASSWORD" postgres:17-alpine \
  pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d leadgen_staging \
  --no-owner --no-privileges --no-comments --clean --if-exists
DUMP_SCRIPT

run_ssh "chmod +x /tmp/_dump_staging.sh"

# Verify credentials are readable
echo "==> Verifying RDS credentials on VPS..."
RDS_HOST_CHECK=$(run_ssh 'grep "^DB_POSTGRESDB_HOST=" /home/ec2-user/.env | cut -d= -f2 | tr -d "\r"')
RDS_USER_CHECK=$(run_ssh 'grep "^DB_POSTGRESDB_USER=" /home/ec2-user/.env | cut -d= -f2 | tr -d "\r"')
echo "    RDS host: $RDS_HOST_CHECK"
echo "    RDS user: $RDS_USER_CHECK"
echo "    Staging DB: $STAGING_DB"

# ---------------------------------------------------------------------------
# Drop and recreate local database for a clean restore
# ---------------------------------------------------------------------------
echo ""
echo "==> Resetting local database '$LOCAL_PG_DB'..."
# Terminate active connections before dropping
docker exec "$LOCAL_PG_CONTAINER" psql -U "$LOCAL_PG_USER" -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${LOCAL_PG_DB}' AND pid <> pg_backend_pid();" \
  >/dev/null 2>&1 || true
docker exec "$LOCAL_PG_CONTAINER" psql -U "$LOCAL_PG_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS ${LOCAL_PG_DB};"
docker exec "$LOCAL_PG_CONTAINER" psql -U "$LOCAL_PG_USER" -d postgres \
  -c "CREATE DATABASE ${LOCAL_PG_DB};"
echo "    Database recreated."

# ---------------------------------------------------------------------------
# Dump staging DB via VPS and restore locally
# ---------------------------------------------------------------------------
echo ""
echo "==> Dumping staging DB via VPS and restoring locally..."
echo "    This may take a minute depending on database size..."

run_ssh "bash /tmp/_dump_staging.sh" \
  | docker exec -i "$LOCAL_PG_CONTAINER" psql -U "$LOCAL_PG_USER" -d "$LOCAL_PG_DB" -q 2>/dev/null

# Clean up remote script
run_ssh "rm -f /tmp/_dump_staging.sh"

# ---------------------------------------------------------------------------
# Verify restore
# ---------------------------------------------------------------------------
echo ""
echo "==> Verifying restore..."

TABLES=$(docker exec "$LOCAL_PG_CONTAINER" psql -U "$LOCAL_PG_USER" -d "$LOCAL_PG_DB" -t -A \
  -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;")

echo ""
echo "    Tables restored:"
for t in $TABLES; do
  COUNT=$(docker exec "$LOCAL_PG_CONTAINER" psql -U "$LOCAL_PG_USER" -d "$LOCAL_PG_DB" -t -A \
    -c "SELECT count(*) FROM \"${t}\";" 2>/dev/null || echo "?")
  printf "      %-30s %s rows\n" "$t" "$COUNT"
done

echo ""
echo "==> Done. Local DB refreshed from staging."
echo "    Connection: postgresql://${LOCAL_PG_USER}:${LOCAL_PG_PASS}@localhost:${LOCAL_PG_PORT}/${LOCAL_PG_DB}"
