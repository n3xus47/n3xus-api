#!/usr/bin/env bash
set -euo pipefail
MODEL="${1:-qwen3:8b}"
exec docker compose exec ollama ollama pull "$MODEL"
