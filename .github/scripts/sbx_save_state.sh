#!/usr/bin/env bash
# Commit a sandbox arm's state dir and push it to its own branch. No-op if unchanged.
# Usage: sbx_save_state.sh <dir> <branch> <message>
set -euo pipefail
dir="$1"; b="$2"; msg="$3"
case "$b" in sbx-state-*) ;; *) echo "refusing non-sandbox branch '$b'"; exit 1;; esac
cd "$dir"
touch .nojekyll
git add -A
if git diff --cached --quiet; then echo "state unchanged"; exit 0; fi
git -c user.name="kxrain-sandbox-bot" \
    -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit -q -m "$b $(date -u +%Y-%m-%dT%H:%M:%SZ) ($msg)"
for i in 1 2 3; do
  git push -q origin "HEAD:refs/heads/$b" && { echo "state saved"; exit 0; }
  sleep $((i * 10))
done
echo "push failed"; exit 1
