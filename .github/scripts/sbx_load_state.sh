#!/usr/bin/env bash
# Check out a sandbox arm's own state branch at ./sbx_state (orphan on first run).
# Usage: sbx_load_state.sh <branch>. Never touches Gate 2's `state` branch.
set -euo pipefail
b="$1"
case "$b" in sbx-state-*) ;; *) echo "refusing non-sandbox branch '$b'"; exit 1;; esac
if git ls-remote --exit-code --heads origin "$b" >/dev/null 2>&1; then
  git fetch -q --depth=1 origin "$b"
  git worktree add -q -B "$b" sbx_state FETCH_HEAD
else
  git worktree add -q --orphan -b "$b" sbx_state
fi
ls -la sbx_state
