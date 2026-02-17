#!/usr/bin/env bash
# Agent registry: tracks which agents are active on which branches
# Usage:
#   bash scripts/registry.sh register <branch> <slot> <worktree_path>
#   bash scripts/registry.sh deregister <branch>
#   bash scripts/registry.sh list
#   bash scripts/registry.sh cleanup   (remove stale entries)
set -euo pipefail

MAIN_ROOT="$(git worktree list --porcelain | head -1 | sed 's/^worktree //')"
REGISTRY="${MAIN_ROOT}/.worktrees/registry.json"

# Ensure directory + file exist
mkdir -p "$(dirname "$REGISTRY")"
if [ ! -f "$REGISTRY" ]; then
  echo '[]' > "$REGISTRY"
fi

ACTION="${1:-list}"

case "$ACTION" in
  register)
    BRANCH="${2:?branch required}"
    SLOT="${3:?slot required}"
    WT_PATH="${4:?worktree_path required}"
    PID="$$"
    TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    python3 -c "
import json, sys
reg = json.load(open('$REGISTRY'))
# Remove existing entry for this branch
reg = [e for e in reg if e['branch'] != '$BRANCH']
reg.append({
    'branch': '$BRANCH',
    'slot': int('$SLOT'),
    'worktree': '$WT_PATH',
    'pid': int('$PID'),
    'started_at': '$TIMESTAMP'
})
json.dump(reg, open('$REGISTRY', 'w'), indent=2)
"
    echo "Registered: $BRANCH (slot $SLOT)"
    ;;

  deregister)
    BRANCH="${2:?branch required}"
    python3 -c "
import json
reg = json.load(open('$REGISTRY'))
reg = [e for e in reg if e['branch'] != '$BRANCH']
json.dump(reg, open('$REGISTRY', 'w'), indent=2)
"
    echo "Deregistered: $BRANCH"
    ;;

  list)
    if [ ! -s "$REGISTRY" ] || [ "$(cat "$REGISTRY")" = "[]" ]; then
      echo "No active agents registered."
      exit 0
    fi
    echo "Active agents:"
    python3 -c "
import json
reg = json.load(open('$REGISTRY'))
for e in reg:
    print(f\"  {e['branch']:40s} slot={e['slot']}  pid={e['pid']}  since={e['started_at']}\")
"
    ;;

  cleanup)
    # Remove entries whose PID is no longer running
    python3 -c "
import json, os
reg = json.load(open('$REGISTRY'))
alive = []
removed = []
for e in reg:
    try:
        os.kill(e['pid'], 0)  # Check if PID exists
        alive.append(e)
    except OSError:
        removed.append(e['branch'])
json.dump(alive, open('$REGISTRY', 'w'), indent=2)
for b in removed:
    print(f'  Removed stale: {b}')
if not removed:
    print('  No stale entries.')
"
    ;;

  *)
    echo "Usage: bash scripts/registry.sh {register|deregister|list|cleanup}"
    exit 1
    ;;
esac
