#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

BASE_URL="${N3XUS_API_BASE_URL:-http://127.0.0.1:8000}"
MODEL="${N3XUS_API_OLLAMA_MODEL:-qwen3.5:27b}"
TIMEOUT_SECS="${N3XUS_API_STARTUP_TIMEOUT_SECS:-180}"

die() {
  printf 'n3xusAPI startup failed: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is missing: $1"
}

wait_for_ollama() {
  local deadline=$((SECONDS + TIMEOUT_SECS))
  until docker compose exec -T ollama ollama list >/dev/null 2>&1; do
    (( SECONDS >= deadline )) && die "Ollama did not become ready within ${TIMEOUT_SECS}s"
    sleep 2
  done
}

wait_for_api() {
  local deadline=$((SECONDS + TIMEOUT_SECS))
  until curl --silent --show-error --fail "$BASE_URL/v1/health" >/dev/null 2>&1; do
    (( SECONDS >= deadline )) && die "n3xusAPI did not become healthy within ${TIMEOUT_SECS}s"
    sleep 2
  done
}

require_command docker
require_command curl

printf 'Starting Ollama and SearxNG...\n'
docker compose up -d searxng ollama
wait_for_ollama

if docker compose exec -T ollama ollama list | awk 'NR > 1 {print $1}' | grep -Fxq -- "$MODEL"; then
  printf 'Ollama model is installed: %s\n' "$MODEL"
else
  printf 'Ollama model is missing; downloading: %s\n' "$MODEL"
fi

# Pull is idempotent: it verifies the manifest and updates an installed model
# when Ollama has a newer version.
docker compose exec -T ollama ollama pull "$MODEL"

printf 'Starting n3xusAPI...\n'
docker compose up --build -d api
wait_for_api

printf 'n3xusAPI is ready at %s using Ollama model %s\n' "$BASE_URL" "$MODEL"
