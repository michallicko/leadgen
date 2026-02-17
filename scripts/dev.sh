#!/usr/bin/env bash
# Start local dev environment: PG + Flask + Vite
# Usage: bash scripts/dev.sh
#   DEV_SLOT=0  →  Flask=5001, Vite=5173  (default)
#   DEV_SLOT=1  →  Flask=5002, Vite=5174
#   DEV_SLOT=N  →  Flask=5001+N, Vite=5173+N
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# --- Slot + port computation ---
SLOT="${DEV_SLOT:-0}"
if ! [[ "$SLOT" =~ ^[0-9]$ ]]; then
  echo "ERROR: DEV_SLOT must be 0-9 (got '$SLOT')"
  exit 1
fi
FLASK_PORT=$((5001 + SLOT))
VITE_PORT=$((5173 + SLOT))

echo "==> Dev slot $SLOT  (Flask=:$FLASK_PORT  Vite=:$VITE_PORT)"

# --- .env.dev bootstrap (worktree support) ---
if [ ! -f ".env.dev" ]; then
  # Try to copy from main worktree
  MAIN_WORKTREE="$(git worktree list --porcelain | head -1 | sed 's/^worktree //')"
  if [ -f "$MAIN_WORKTREE/.env.dev" ]; then
    echo "    Copying .env.dev from main worktree..."
    cp "$MAIN_WORKTREE/.env.dev" .env.dev
  else
    echo "ERROR: .env.dev not found. Run first:"
    echo "  bash scripts/init-env.sh"
    exit 1
  fi
fi

# --- Idempotent PG start ---
echo "==> Checking PostgreSQL..."
if docker exec leadgen-dev-pg pg_isready -U leadgen -q 2>/dev/null; then
  echo "    PG already running."
else
  echo "    Starting PostgreSQL..."
  # Use the main worktree's compose file (worktrees share the same PG)
  MAIN_WORKTREE="$(git worktree list --porcelain | head -1 | sed 's/^worktree //')"
  docker compose -f "$MAIN_WORKTREE/docker-compose.dev.yml" up -d

  echo "    Waiting for PG to be healthy..."
  for i in $(seq 1 30); do
    if docker exec leadgen-dev-pg pg_isready -U leadgen -q 2>/dev/null; then
      echo "    PG ready."
      break
    fi
    if [ "$i" = "30" ]; then
      echo "ERROR: PG failed to start. Check: docker compose -f docker-compose.dev.yml logs"
      exit 1
    fi
    sleep 1
  done
fi

# --- Activate venv (.venv fallback to main worktree) ---
if [ -d ".venv" ]; then
  source .venv/bin/activate
else
  MAIN_WORKTREE="$(git worktree list --porcelain | head -1 | sed 's/^worktree //')"
  if [ -d "$MAIN_WORKTREE/.venv" ]; then
    echo "    Using .venv from main worktree..."
    source "$MAIN_WORKTREE/.venv/bin/activate"
  fi
fi

# --- Source env + CORS override ---
set -a
source .env.dev
set +a
export CORS_ORIGINS="http://localhost:${VITE_PORT}"

# --- Auto-install frontend deps ---
if [ ! -d "frontend/node_modules" ]; then
  echo "==> Installing frontend dependencies..."
  (cd frontend && npm install)
fi

# --- Start Flask in background ---
echo "==> Starting Flask API (port $FLASK_PORT)..."
python -m flask run --debug --port "$FLASK_PORT" &
FLASK_PID=$!

# Cleanup on exit — only kill this slot's Flask; leave PG running
cleanup() {
  echo ""
  echo "==> Shutting down slot $SLOT..."
  kill "$FLASK_PID" 2>/dev/null || true
  wait "$FLASK_PID" 2>/dev/null || true
  echo "    Flask stopped. PG container still running (docker compose -f docker-compose.dev.yml down to stop)."
}
trap cleanup EXIT INT TERM

# --- Start Vite (foreground) ---
echo "==> Starting Vite dev server (port $VITE_PORT)..."
echo ""
echo "    Dashboard:  http://localhost:$VITE_PORT"
echo "    API:        http://localhost:$FLASK_PORT/api/health"
echo ""
cd frontend && VITE_API_PORT=$FLASK_PORT npx vite --port "$VITE_PORT" --strictPort
