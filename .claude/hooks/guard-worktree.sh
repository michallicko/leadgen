#!/usr/bin/env bash
# PreToolUse hook: ensure Write/Edit targets stay within the current worktree
# AND detect file conflicts with other active worktrees
set -euo pipefail

# Read tool input from stdin
INPUT="$(cat)"

FILE_PATH="$(echo "$INPUT" | python3 -c "import sys,json; inp=json.load(sys.stdin).get('tool_input',{}); print(inp.get('file_path','') or inp.get('path',''))" 2>/dev/null || echo "")"

# If no file path, allow
if [ -z "$FILE_PATH" ]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse"}}'
  exit 0
fi

# Get worktree root
WORKTREE_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
if [ -z "$WORKTREE_ROOT" ]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse"}}'
  exit 0
fi

# Resolve to absolute path
if [[ "$FILE_PATH" = /* ]]; then
  ABS_PATH="$FILE_PATH"
else
  ABS_PATH="$(pwd)/$FILE_PATH"
fi

WARNINGS=""
BRANCH="$(git branch --show-current 2>/dev/null || echo "unknown")"

# --- Check 1: Outside worktree boundary ---
case "$ABS_PATH" in
  "${WORKTREE_ROOT}"/*)
    # Inside worktree — OK
    ;;
  *)
    WARNINGS+="WARNING: You are on branch '${BRANCH}' (worktree: ${WORKTREE_ROOT}) but writing to '${FILE_PATH}' which is OUTSIDE your worktree. This likely modifies another branch's files.\\n"
    ;;
esac

# --- Check 2: File conflict with other worktrees ---
# Get relative path within the repo
REL_PATH="${ABS_PATH#${WORKTREE_ROOT}/}"

# Scan other worktrees for uncommitted changes to the same file
while IFS= read -r line; do
  if [[ "$line" =~ ^worktree\ (.+)$ ]]; then
    WT="${BASH_REMATCH[1]}"
    # Skip our own worktree
    if [ "$WT" = "$WORKTREE_ROOT" ]; then
      continue
    fi
    # Check if other worktree has uncommitted changes to the same relative path
    if git -C "$WT" diff --name-only HEAD 2>/dev/null | grep -qx "$REL_PATH"; then
      OTHER_BRANCH="$(git -C "$WT" branch --show-current 2>/dev/null || echo "unknown")"
      WARNINGS+="CONFLICT: '${REL_PATH}' has uncommitted changes in worktree '${WT}' (branch: ${OTHER_BRANCH}). Editing the same file in parallel will cause merge conflicts.\\n"
    fi
    # Also check staged changes
    if git -C "$WT" diff --cached --name-only 2>/dev/null | grep -qx "$REL_PATH"; then
      OTHER_BRANCH="$(git -C "$WT" branch --show-current 2>/dev/null || echo "unknown")"
      WARNINGS+="CONFLICT: '${REL_PATH}' has staged changes in worktree '${WT}' (branch: ${OTHER_BRANCH}). Editing the same file in parallel will cause merge conflicts.\\n"
    fi
  fi
done < <(git worktree list --porcelain 2>/dev/null)

# --- Output ---
if [ -n "$WARNINGS" ]; then
  # Escape for JSON
  WARNINGS_ESCAPED="${WARNINGS//\\/\\\\}"
  WARNINGS_ESCAPED="${WARNINGS_ESCAPED//\"/\\\"}"
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "${WARNINGS_ESCAPED}"
  }
}
EOF
else
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse"}}'
fi

exit 0
