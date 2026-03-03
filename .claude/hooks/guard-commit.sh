#!/usr/bin/env bash
# PreToolUse hook for Bash: warn if git commit doesn't reference a backlog item
set -euo pipefail

INPUT="$(cat)"

# Extract the command being run
COMMAND="$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")"

# Only care about git commit commands
if ! echo "$COMMAND" | grep -qE '^\s*git\s+commit'; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse"}}'
    exit 0
fi

# Check if commit message references a backlog item (BL-NNN or DASH-NNN pattern)
if echo "$COMMAND" | grep -qiE '(BL-[0-9]+|DASH-[0-9]+)'; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse"}}'
    exit 0
fi

# Warn but don't block
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "WARNING: This commit does not reference a backlog item (e.g., BL-029 or DASH-002). Ensure you have:\\n  1. Claimed the item: backlog_claim_item()\\n  2. Set status to Building: backlog_update_item(status='Building')\\n  3. Include the item ID in the commit message\\nIf this is a docs/chore commit with no backlog item, you may proceed."
  }
}
EOF

exit 0
