#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

BASE_URL="${N3XUS_API_BASE_URL:-http://127.0.0.1:8000}"
TIMEOUT_SECS="${N3XUS_API_STARTUP_TIMEOUT_SECS:-180}"
MODEL_OVERRIDE="${N3XUS_API_OLLAMA_MODEL:-}"
SEARCH_VARIANT_OVERRIDE="${N3XUS_API_SEARCH_VARIANT_LIMIT:-}"
MODE="${1:-start}"

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

case "$MODE" in
  start|--update) ;;
  *) die "usage: $0 [--update]" ;;
esac

if [[ ! -f .env ]]; then
  if [[ "$MODE" != "--update" ]]; then
    die "local stack is not initialized; run 'npm run setup' once to download current images and model."
  fi
  cp .env.example .env
  printf 'Created .env from .env.example. Review optional settings before exposing integrations.\n'
fi

# Export .env for Compose and the Ollama CLI. An explicit shell override wins.
set -a
. ./.env
set +a
if [[ "$MODE" == "--update" && -z "$MODEL_OVERRIDE" && "${N3XUS_API_OLLAMA_MODEL:-}" == "qwen3.5:27b" ]]; then
  sed -i 's/^N3XUS_API_OLLAMA_MODEL=.*/N3XUS_API_OLLAMA_MODEL=qwen3.5:4b/' .env
  N3XUS_API_OLLAMA_MODEL=qwen3.5:4b
  printf 'Migrated the previous default model from qwen3.5:27b to qwen3.5:4b.\n'
fi
if [[ -n "$SEARCH_VARIANT_OVERRIDE" ]]; then
  N3XUS_API_SEARCH_VARIANT_LIMIT="$SEARCH_VARIANT_OVERRIDE"
elif [[ "${N3XUS_API_SEARCH_VARIANT_LIMIT:-}" == "5" ]]; then
  sed -i 's/^N3XUS_API_SEARCH_VARIANT_LIMIT=.*/N3XUS_API_SEARCH_VARIANT_LIMIT=3/' .env
  N3XUS_API_SEARCH_VARIANT_LIMIT=3
  printf 'Migrated the previous default search variant limit from 5 to 3.\n'
fi
MODEL="${MODEL_OVERRIDE:-${N3XUS_API_OLLAMA_MODEL:-qwen3.5:4b}}"
export N3XUS_API_OLLAMA_MODEL="$MODEL"

if [[ "$MODE" == "--update" ]]; then
  printf 'Checking Docker Hub for the latest Compose images...\n'
  docker compose pull searxng ollama

  printf 'Starting Ollama and SearxNG...\n'
  docker compose up -d searxng ollama
  docker compose restart searxng
  wait_for_ollama

  printf 'Updating the %s model and building the API in parallel...\n' "$MODEL"
  docker compose exec -T ollama ollama pull "$MODEL" &
  model_pull_pid=$!
  docker compose build --pull api &
  api_build_pid=$!
  model_pull_status=0
  api_build_status=0
  wait "$model_pull_pid" || model_pull_status=$?
  wait "$api_build_pid" || api_build_status=$?
  (( model_pull_status == 0 )) || die "failed to update Ollama model '$MODEL'"
  (( api_build_status == 0 )) || die "failed to build the API image"
else
  printf 'Starting the already configured local stack without downloads or builds...\n'
  if ! docker compose up -d --no-build --pull never searxng ollama; then
    die "local images are missing; run 'npm run setup' to download and build the stack."
  fi
  wait_for_ollama

  if ! docker compose exec -T ollama ollama list | awk 'NR > 1 {print $1}' | grep -Fxq -- "$MODEL"; then
    die "Ollama model '$MODEL' is missing; run 'npm run setup' to install the latest version."
  fi
fi

printf 'Starting n3xusAPI...\n'
docker compose up -d --no-build --pull never api
wait_for_api

printf 'n3xusAPI is ready at %s using Ollama model %s\n' "$BASE_URL" "$MODEL"
