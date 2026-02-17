#!/usr/bin/env bash
# SessionStart hook: inject branch + worktree + staleness context into Claude's awareness
set -euo pipefail

WORKTREE_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "unknown")"
BRANCH="$(git branch --show-current 2>/dev/null || echo "detached")"
IS_WORKTREE="no"
MAIN_WORKTREE=""

# Detect if we're in a linked worktree (not the main one)
if [ "$WORKTREE_ROOT" != "unknown" ]; then
  MAIN_WORKTREE="$(git worktree list --porcelain | head -1 | sed 's/^worktree //')"
  if [ "$WORKTREE_ROOT" != "$MAIN_WORKTREE" ]; then
    IS_WORKTREE="yes"
  fi
fi

# Fetch latest refs (quiet, best-effort)
git fetch origin --quiet 2>/dev/null || true

# Check staleness: how many commits behind origin/staging?
BEHIND=0
AHEAD=0
if git rev-parse --verify origin/staging >/dev/null 2>&1; then
  BEHIND="$(git rev-list --count HEAD..origin/staging 2>/dev/null || echo 0)"
  AHEAD="$(git rev-list --count origin/staging..HEAD 2>/dev/null || echo 0)"
fi

# Build context message
CTX="## Git Context (auto-injected)\\n"
CTX+="- **Branch**: \`${BRANCH}\`\\n"
CTX+="- **Worktree root**: \`${WORKTREE_ROOT}\`\\n"
if [ "$IS_WORKTREE" = "yes" ]; then
  CTX+="- **Linked worktree** (main: \`${MAIN_WORKTREE}\`)\\n"
  CTX+="- You are in an isolated worktree. ALL file operations must target paths under \`${WORKTREE_ROOT}\`.\\n"
fi
CTX+="- **DEV_SLOT**: \`${DEV_SLOT:-not set}\`\\n"
CTX+="- **vs origin/staging**: ${AHEAD} ahead, ${BEHIND} behind\\n"

if [ "$BEHIND" -gt 0 ]; then
  CTX+="\\n**WARNING: Your branch is ${BEHIND} commits behind origin/staging.**\\n"
  CTX+="Run \`make sync\` before starting work to rebase onto the latest staging.\\n"
  CTX+="Do NOT rebase onto main or any other branch — always use origin/staging as your base.\\n"
fi

CTX+="\\n**Rebase rule**: ONLY rebase onto \`origin/staging\`. Never onto \`main\`, \`origin/main\`, or another feature branch.\\n"
CTX+="To sync: \`make sync\` (fetches + rebases onto origin/staging).\\n"

# Show other active agents from registry
REGISTRY="${MAIN_WORKTREE:-$WORKTREE_ROOT}/.worktrees/registry.json"
if [ -f "$REGISTRY" ] && [ -s "$REGISTRY" ]; then
  # Cleanup stale entries first
  bash "$(dirname "$0")/../../scripts/registry.sh" cleanup >/dev/null 2>&1 || true

  OTHER_AGENTS="$(python3 -c "
import json
reg = json.load(open('$REGISTRY'))
others = [e for e in reg if e['branch'] != '$BRANCH']
if others:
    for e in others:
        print(f\"  - \`{e['branch']}\` (slot {e['slot']})\")
" 2>/dev/null || true)"

  if [ -n "$OTHER_AGENTS" ]; then
    CTX+="\\n**Other active agents:**\\n"
    while IFS= read -r line; do
      CTX+="${line}\\n"
    done <<< "$OTHER_AGENTS"
    CTX+="Avoid editing files that these branches are likely changing. Run \`make pr-scan\` before creating a PR to check for file overlaps."
  fi
fi

# Escape for JSON
CTX_ESCAPED="${CTX//\\/\\\\}"
CTX_ESCAPED="${CTX_ESCAPED//\"/\\\"}"

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${CTX_ESCAPED}"
  }
}
EOF

exit 0
