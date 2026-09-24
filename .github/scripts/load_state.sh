#!/usr/bin/env bash
# Check out the `state` branch at ./state, creating it (empty, orphan) on the first run.
set -euo pipefail
if git ls-remote --exit-code --heads origin state >/dev/null 2>&1; then
  git fetch -q --depth=1 origin state
  git worktree add -q -B state state FETCH_HEAD
else
  git worktree add -q --orphan -b state state
fi
ls -la state
