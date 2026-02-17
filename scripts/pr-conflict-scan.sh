#!/usr/bin/env bash
# Pre-PR conflict scan: check open PRs targeting staging for overlapping files
# Usage: bash scripts/pr-conflict-scan.sh
#   Exits 0 always (informational). Prints warnings to stdout.
set -euo pipefail

BRANCH="$(git branch --show-current 2>/dev/null || echo "")"
if [ -z "$BRANCH" ]; then
  echo "ERROR: Not on a branch"
  exit 0
fi

echo "==> Scanning for file conflicts with open PRs targeting staging..."
echo ""

# Get files changed in our branch vs origin/staging
OUR_FILES="$(git diff --name-only origin/staging...HEAD 2>/dev/null || true)"
if [ -z "$OUR_FILES" ]; then
  echo "  No changed files vs origin/staging."
  exit 0
fi

OUR_FILE_COUNT="$(echo "$OUR_FILES" | wc -l | tr -d ' ')"
echo "  Your branch ($BRANCH) changes $OUR_FILE_COUNT files."

# List open PRs targeting staging (excluding our own branch)
PR_LIST="$(gh pr list --base staging --state open --json number,headRefName,title 2>/dev/null || echo "[]")"
PR_COUNT="$(echo "$PR_LIST" | python3 -c "import sys,json; prs=[p for p in json.load(sys.stdin) if p['headRefName']!='$BRANCH']; print(len(prs))" 2>/dev/null || echo 0)"

if [ "$PR_COUNT" = "0" ]; then
  echo "  No other open PRs targeting staging. No conflicts possible."
  exit 0
fi

echo "  Found $PR_COUNT other open PRs targeting staging."
echo ""

CONFLICTS_FOUND=0

# Check each PR for overlapping files
echo "$PR_LIST" | python3 -c "
import sys, json
prs = [p for p in json.load(sys.stdin) if p['headRefName'] != '$BRANCH']
for pr in prs:
    print(f\"{pr['number']}|{pr['headRefName']}|{pr['title']}\")
" 2>/dev/null | while IFS='|' read -r PR_NUM PR_BRANCH PR_TITLE; do
  # Get files changed in that PR
  PR_FILES="$(gh pr diff "$PR_NUM" --name-only 2>/dev/null || true)"
  if [ -z "$PR_FILES" ]; then
    continue
  fi

  # Find overlapping files
  OVERLAP="$(comm -12 <(echo "$OUR_FILES" | sort) <(echo "$PR_FILES" | sort) 2>/dev/null || true)"
  if [ -n "$OVERLAP" ]; then
    OVERLAP_COUNT="$(echo "$OVERLAP" | wc -l | tr -d ' ')"
    echo "  CONFLICT with PR #${PR_NUM} (${PR_BRANCH}): \"${PR_TITLE}\""
    echo "  $OVERLAP_COUNT overlapping files:"
    echo "$OVERLAP" | sed 's/^/    - /'
    echo ""
    CONFLICTS_FOUND=1
  fi
done

if [ "$CONFLICTS_FOUND" = "0" ]; then
  echo "  No file overlaps found. Safe to create PR."
fi
