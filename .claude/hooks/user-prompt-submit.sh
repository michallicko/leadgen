#!/usr/bin/env bash
# UserPromptSubmit hook: re-inject branch context on EVERY user message
# Lighter than SessionStart (no git fetch), prevents context compression amnesia
set -euo pipefail

BRANCH="$(git branch --show-current 2>/dev/null || echo "detached")"
WORKTREE_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "unknown")"

# Quick staleness check (uses last fetch, no network call)
BEHIND=0
if git rev-parse --verify origin/staging >/dev/null 2>&1; then
  BEHIND="$(git rev-list --count HEAD..origin/staging 2>/dev/null || echo 0)"
fi

CTX="[Branch: \`${BRANCH}\` | Root: \`${WORKTREE_ROOT}\`"
if [ "$BEHIND" -gt 0 ]; then
  CTX+=" | ${BEHIND} behind staging"
fi
CTX+="]"

# Escape for JSON
CTX_ESCAPED="${CTX//\\/\\\\}"
CTX_ESCAPED="${CTX_ESCAPED//\"/\\\"}"

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "${CTX_ESCAPED}"
  }
}
EOF

exit 0
