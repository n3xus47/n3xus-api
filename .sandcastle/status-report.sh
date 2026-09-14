#!/usr/bin/env bash
# Quick Sandcastle snapshot for AFK monitoring (stdout only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Sandcastle $(date -Is) ==="

if pid=$(pgrep -f 'loader.mjs .sandcastle/main.mts' | head -1); then
  echo "orchestrator: RUNNING pid=$pid"
else
  echo "orchestrator: STOPPED"
fi

latest_impl=$(ls -t .sandcastle/logs/*-implementer.log 2>/dev/null | head -1 || true)
latest_rev=$(ls -t .sandcastle/logs/*-reviewer.log 2>/dev/null | head -1 || true)
latest_afk=$(ls -t .sandcastle/logs/cursor-afk-*.log 2>/dev/null | head -1 || true)

if [[ -n "$latest_afk" ]]; then
  echo "afk_log: $latest_afk"
  tail -5 "$latest_afk"
fi

if [[ -n "$latest_impl" ]]; then
  echo "implementer_log: $latest_impl"
  echo "implementer_mtime: $(stat -c %y "$latest_impl")"
  echo "--- implementer (last 40 lines) ---"
  tail -40 "$latest_impl"
fi

if [[ -n "$latest_rev" ]]; then
  echo "reviewer_log: $latest_rev"
  echo "reviewer_mtime: $(stat -c %y "$latest_rev")"
  echo "--- reviewer (last 20 lines) ---"
  tail -20 "$latest_rev"
fi

if [[ -n "${latest_impl:-}" ]]; then
  branch_id=$(basename "$latest_impl" | sed -n 's/sandcastle-sequential-reviewer-\(.*\)-implementer.log/\1/p')
  wt="$ROOT/.sandcastle/worktrees/sandcastle-sequential-reviewer-$branch_id"
  if [[ -d "$wt" ]]; then
    echo "--- worktree sandcastle-sequential-reviewer-$branch_id ---"
    git -C "$wt" status -sb
    echo "commits on branch:"
    git -C "$wt" log --oneline -5
  fi
fi

if pgrep -f 'python -m app.evaluate' >/dev/null 2>&1; then
  echo "WARN: eval still running:"
  pgrep -af 'python -m app.evaluate' || true
else
  echo "eval:m1: none"
fi
