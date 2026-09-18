#!/usr/bin/env bash
set -euo pipefail
MODEL="${1:-${N3XUS_API_OLLAMA_MODEL:-qwen3.5:27b}}"
exec docker compose exec -T ollama ollama pull "$MODEL"
