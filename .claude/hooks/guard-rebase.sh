#!/usr/bin/env bash
# PreToolUse hook for Bash: intercept dangerous git rebase commands
set -euo pipefail

INPUT="$(cat)"

COMMAND="$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")"

# Only care about git rebase commands
if ! echo "$COMMAND" | grep -qE '^\s*git\s+rebase'; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse"}}'
  exit 0
fi

# Extract the rebase target (last argument-like token that isn't a flag)
# git rebase origin/staging → OK
# git rebase main → BAD
# git rebase origin/main → BAD
# git rebase --onto origin/staging ... → OK (--onto target)
BRANCH="$(git branch --show-current 2>/dev/null || echo "unknown")"

# Check for known-bad targets
if echo "$COMMAND" | grep -qE 'rebase\s+(--[a-z-]+\s+)*\b(main|origin/main|master|origin/master)\b'; then
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Rebasing onto main/master is not allowed. Feature branches must rebase onto origin/staging. Use: git rebase origin/staging"
  }
}
EOF
  exit 0
fi

# Check for rebase onto another feature branch (not origin/staging)
if echo "$COMMAND" | grep -qE 'rebase\s+(--[a-z-]+\s+)*(feature/|origin/feature/)'; then
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "WARNING: You are rebasing onto another feature branch. Feature branches should rebase onto origin/staging, not other feature branches. If this is intentional (e.g. stacking), proceed with caution."
  }
}
EOF
  exit 0
fi

# Check that the target includes origin/staging (the correct base)
if echo "$COMMAND" | grep -qE 'rebase\s+(--[a-z-]+\s+)*origin/staging'; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse"}}'
  exit 0
fi

# Anything else — warn
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "CAUTION: You are on branch '${BRANCH}'. The standard rebase target is origin/staging. Your command: ${COMMAND}. Make sure this is the correct base."
  }
}
EOF
exit 0
