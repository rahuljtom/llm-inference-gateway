#!/usr/bin/env bash
# Load-test /v1/chat/completions with oha (gateway auth + BYOK headers).
#
# Usage:
#   export GROQ_API_KEY=gsk_...
#   ./scripts/bench.sh
#
# Env:
#   BASE_URL          Gateway base URL (default http://127.0.0.1:8000)
#   GATEWAY_KEY       Gateway Bearer key (default demo-key)
#   GROQ_API_KEY      Upstream Groq key (required unless SKIP_UPSTREAM=1)
#   BENCH_PROVIDER    X-Provider value (default groq)
#   BENCH_MODEL       Model id (default llama-3.1-8b-instant)
#   OHA_REQUESTS      Total requests per scenario (default 50)
#   OHA_CONCURRENCY   Concurrent workers (default 10)
#   SCENARIO          miss | hit | both (default both)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
GATEWAY_KEY="${GATEWAY_KEY:-demo-key}"
UPSTREAM_KEY="${GROQ_API_KEY:-${UPSTREAM_API_KEY:-}}"
PROVIDER="${BENCH_PROVIDER:-groq}"
MODEL="${BENCH_MODEL:-llama-3.1-8b-instant}"
REQUESTS="${OHA_REQUESTS:-50}"
CONCURRENCY="${OHA_CONCURRENCY:-10}"
SCENARIO="${SCENARIO:-both}"

if ! command -v oha >/dev/null 2>&1; then
  echo "oha is required. Install: brew install oha   # or: cargo install oha"
  exit 1
fi

if [[ "${SKIP_UPSTREAM:-}" != "1" && -z "$UPSTREAM_KEY" ]]; then
  echo "Set GROQ_API_KEY (or UPSTREAM_API_KEY) for live upstream benchmarks."
  echo "Use SKIP_UPSTREAM=1 to only warm /health (CI smoke)."
  exit 1
fi

echo "Warming ${BASE_URL}/health ..."
curl -sf "${BASE_URL}/health" | head -c 200
echo ""

if [[ "${SKIP_UPSTREAM:-}" == "1" ]]; then
  echo "SKIP_UPSTREAM=1 — health check only."
  exit 0
fi

oha_common() {
  oha -n "$REQUESTS" -c "$CONCURRENCY" \
    -H "Authorization: Bearer ${GATEWAY_KEY}" \
    -H "X-Provider: ${PROVIDER}" \
    -H "X-Provider-Api-Key: ${UPSTREAM_KEY}" \
    -H "Content-Type: application/json" \
    -m POST \
    "$@"
}

run_miss() {
  echo ""
  echo "=== Cache MISS (stream=true — cache applies only to non-streaming) ==="
  local payload
  payload=$(printf '{"model":"%s","messages":[{"role":"user","content":"bench miss streaming"}],"max_tokens":16,"stream":true}' "$MODEL")
  oha_common -d "$payload" "${BASE_URL}/v1/chat/completions"
}

run_hit() {
  echo ""
  echo "=== Cache HIT (identical non-streaming body, CACHE_ENABLED=true) ==="
  local payload
  payload=$(printf '{"model":"%s","messages":[{"role":"user","content":"bench cache hit fixed body"}],"max_tokens":16,"stream":false}' "$MODEL")
  # Prime cache once
  curl -sf -X POST "${BASE_URL}/v1/chat/completions" \
    -H "Authorization: Bearer ${GATEWAY_KEY}" \
    -H "X-Provider: ${PROVIDER}" \
    -H "X-Provider-Api-Key: ${UPSTREAM_KEY}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null || true
  oha_common -d "$payload" "${BASE_URL}/v1/chat/completions"
}

case "$SCENARIO" in
  miss) run_miss ;;
  hit) run_hit ;;
  both)
    run_miss
    run_hit
    ;;
  *)
    echo "Unknown SCENARIO=${SCENARIO} (use miss, hit, or both)"
    exit 1
    ;;
esac
