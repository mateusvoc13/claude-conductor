#!/usr/bin/env bash
# List open worker PRs waiting for the conductor's review.
# Requires the GitHub CLI (`gh`).
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "needs the GitHub CLI: https://cli.github.com/" >&2
  exit 1
fi

gh pr list --state open --json number,title,author,createdAt \
  --jq '.[] | "#\(.number)  \(.title)  —  \(.author.login)  (\(.createdAt))"'
