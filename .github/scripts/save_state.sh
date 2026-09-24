#!/usr/bin/env bash
# Commit ./state (a worktree of the `state` branch) and push it. No-op if unchanged.
set -euo pipefail
cd state
git add -A
if git diff --cached --quiet; then echo "state unchanged"; exit 0; fi
git -c user.name="kxrain-bot" \
    -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit -q -m "state $(date -u +%Y-%m-%dT%H:%M:%SZ) ($1)"
git push -q origin HEAD:refs/heads/state
echo "state saved"
