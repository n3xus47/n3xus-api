#!/usr/bin/env bash
# AFK run: Sandcastle sequential reviewer, then push main to origin.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG=".sandcastle/logs/cursor-afk-$(date +%s).log"
mkdir -p .sandcastle/logs
echo "Sandcastle AFK started $(date -Is) | log=$LOG" | tee -a "$LOG"
npm run sandcastle 2>&1 | tee -a "$LOG"
echo "Sandcastle finished $(date -Is)" | tee -a "$LOG"
git checkout main
git status -sb | tee -a "$LOG"
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "$(cat <<'EOF'
chore: post-Sandcastle sync (uncommitted fixes from overnight run)

Auto-commit any remaining workspace changes before push.
EOF
)" || true
fi
git push origin main 2>&1 | tee -a "$LOG"
echo "Push complete $(date -Is)" | tee -a "$LOG"
