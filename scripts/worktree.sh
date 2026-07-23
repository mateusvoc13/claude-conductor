#!/usr/bin/env bash
# Spin up an isolated git worktree for hands-on work on a branch.
# (conductor.py does this automatically per dispatch; this is for driving a worker — or
#  yourself — interactively in a fresh worktree.)
#
# Usage: scripts/worktree.sh <branch-name>
set -euo pipefail

BRANCH="${1:?usage: worktree.sh <branch-name>}"
WORKTREE="../$(basename "$(pwd)")-$BRANCH"

git worktree add "$WORKTREE" -b "feature/$BRANCH"
echo "Worktree ready at $WORKTREE on branch feature/$BRANCH"
echo "  cd $WORKTREE"
