#!/usr/bin/env bash
# Create or switch to a git worktree and launch Claude Code in it.
# Sets terminal tab title to the branch name for easy identification.
#
# Usage:
#   bash scripts/worktree.sh <feature-name>         # create + launch
#   bash scripts/worktree.sh <feature-name> --no-claude  # create only
#   bash scripts/worktree.sh --list                  # list active worktrees
set -euo pipefail

MAIN_ROOT="$(git worktree list --porcelain | head -1 | sed 's/^worktree //')"
WORKTREE_DIR="${MAIN_ROOT}/.worktrees"

# --- List mode ---
if [ "${1:-}" = "--list" ]; then
  echo "Active worktrees:"
  git worktree list
  exit 0
fi

# --- Validate args ---
if [ -z "${1:-}" ]; then
  echo "Usage: bash scripts/worktree.sh <feature-name> [--no-claude]"
  echo "       bash scripts/worktree.sh --list"
  exit 1
fi

FEATURE="$1"
BRANCH="feature/${FEATURE}"
WT_PATH="${WORKTREE_DIR}/${FEATURE}"
NO_CLAUDE="${2:-}"

# --- Create worktree if needed, sync if exists ---
if [ -d "$WT_PATH" ]; then
  echo "Worktree already exists: $WT_PATH"
  CURRENT_BRANCH="$(git -C "$WT_PATH" branch --show-current)"
  echo "Branch: $CURRENT_BRANCH"

  # Fetch and show divergence from staging
  echo "Fetching latest refs..."
  git -C "$WT_PATH" fetch origin --quiet 2>/dev/null || true
  BEHIND="$(git -C "$WT_PATH" rev-list --count HEAD..origin/staging 2>/dev/null || echo 0)"
  AHEAD="$(git -C "$WT_PATH" rev-list --count origin/staging..HEAD 2>/dev/null || echo 0)"
  echo "vs origin/staging: ${AHEAD} ahead, ${BEHIND} behind"

  if [ "$BEHIND" -gt 0 ]; then
    echo ""
    echo "  WARNING: $BEHIND commits behind origin/staging."
    echo "  Run 'make sync' inside the worktree to rebase."
    echo ""
  fi
else
  echo "Creating worktree for $BRANCH..."
  mkdir -p "$WORKTREE_DIR"

  # Check if branch exists remotely or locally
  if git show-ref --verify --quiet "refs/heads/${BRANCH}" 2>/dev/null; then
    git worktree add "$WT_PATH" "$BRANCH"
  elif git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}" 2>/dev/null; then
    git worktree add "$WT_PATH" "$BRANCH"
  else
    # New branch from staging
    echo "Creating new branch $BRANCH from staging..."
    git fetch origin staging 2>/dev/null || true
    git worktree add "$WT_PATH" -b "$BRANCH" origin/staging
  fi
fi

# --- Set terminal tab title (works in iTerm2, Terminal.app, kitty) ---
set_tab_title() {
  printf '\033]1;%s\007' "$1"    # Tab title
  printf '\033]2;%s\007' "$1"    # Window title
}
set_tab_title "[$FEATURE]"

# --- Assign next available DEV_SLOT ---
pick_slot() {
  for s in 1 2 3 4 5 6 7 8 9; do
    fp=$((5001 + s))
    if ! lsof -ti :"$fp" >/dev/null 2>&1; then
      echo "$s"
      return
    fi
  done
  echo "1"  # fallback
}
SLOT=$(pick_slot)

echo ""
echo "  Worktree:  $WT_PATH"
echo "  Branch:    $BRANCH"
echo "  DEV_SLOT:  $SLOT  (Flask=:$((5001+SLOT))  Vite=:$((5173+SLOT)))"
echo ""

if [ "$NO_CLAUDE" = "--no-claude" ]; then
  echo "cd $WT_PATH && DEV_SLOT=$SLOT make dev"
  exit 0
fi

# --- Register in agent registry ---
bash "$MAIN_ROOT/scripts/registry.sh" register "$BRANCH" "$SLOT" "$WT_PATH"

# --- Launch Claude Code in the worktree ---
cd "$WT_PATH"
export DEV_SLOT="$SLOT"
exec claude
