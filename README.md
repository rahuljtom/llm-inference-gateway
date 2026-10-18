# LLM Inference Gateway

An OpenAI-compatible gateway that centralizes multi-provider requests, Redis-backed request limits, fallback, exact-response caching, and per-key usage logs.

Built with FastAPI, Redis, PostgreSQL, and React.

## Demo

- Live app: <https://llm-inference-gateway.onrender.com/> (Render free-tier instances may take time to wake.)
- Walkthrough: <https://www.loom.com/share/8916ae03dfa345b683c4e235d31c3eea>

## Current capabilities

- OpenAI-compatible `POST /v1/chat/completions`
- Provider adapters for OpenAI, Anthropic, Gemini, and Groq
- Bring-your-own upstream credentials through `X-Provider` and `X-Provider-Api-Key` headers or request fields
- Static model aliases such as `fast-chat` and `smart-chat`, plus optional JSON route policies that filter by estimated cost and expected p95 latency
- Optional fallback provider for eligible upstream failures
- Redis sliding-window RPM and estimated TPM limits per gateway API key
- Exact-match response caching for non-streaming requests; clients can bypass cache reads and writes with `Cache-Control: no-cache`
- PostgreSQL request logs with model, provider, latency, token, cost-estimate, cache, and fallback fields
- Authenticated team usage dashboard for monthly estimated spend, active reservations, API keys, and budget limits
- Authenticated admin API with usage aggregates from PostgreSQL request and budget tables
- Redis-backed provider circuits with a cooldown and half-open recovery request
- Liveness endpoint at `/health` and dependency readiness endpoint at `/ready`

## Product direction

Current work extends the gateway with team-owned keys, estimated monthly budgets, configurable cost/latency route policies, and provider circuit recovery. The replay tool is ready, but paired provider results still need to be collected. Semantic caching stays deferred until exact-match results are measured.

## Architecture

```mermaid
graph TD
    Client[Client or SDK] -->|OpenAI-compatible request| Gateway[FastAPI gateway]
    Gateway -->|RPM/TPM and exact cache| Redis[(Redis)]
    Gateway -->|API key and request logs| Postgres[(PostgreSQL)]
    Gateway --> Router{Route policy, static alias, or explicit provider}
    Router --> OpenAI[OpenAI]
    Router --> Anthropic[Anthropic]
    Router --> Gemini[Gemini]
    Router --> Groq[Groq]
```

See [the architecture notes](docs/architecture.md), [the implementation plan](docs/implementation-plan.md), and [the benchmark instructions](docs/benchmarks.md).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres redis
uvicorn app.main:app --reload
```

The Compose file publishes PostgreSQL at `localhost:5435` and Redis at `localhost:6380`; the app container uses the internal service ports. For running Uvicorn on the host, set `DATABASE_URL=postgresql+asyncpg://gateway:gatewaypass@localhost:5435/gateway` and `REDIS_URL=redis://localhost:6380/0` in `.env`.

The dashboard playground uses the demo gateway key seeded on startup. Each completion still needs a provider and an upstream key, unless a managed provider key is configured by the operator.

## Routing policies

Set `ROUTING_POLICIES_JSON` to define candidate models, the cost or latency selection strategy, eligibility limits, per-candidate timeout, and bounded retries. The `estimated_cost_per_1k_tokens_usd` and `expected_p95_latency_ms` values are operator-supplied estimates and should come from dated price sources and measurements. Candidates without a configured managed provider key are skipped. Eligible candidates after the selected route are used as fallbacks on provider timeouts and 5xx responses. Non-streaming calls apply the configured retry count for timeouts and 429 responses; streaming calls use the candidate timeout and fail over on timeouts/5xx without retries.

Provider circuits are shared in Redis and keyed per provider. `CIRCUIT_BREAKER_FAILURE_THRESHOLD` (default `5`) opens a circuit after consecutive timeouts or 5xx responses; `CIRCUIT_BREAKER_COOLDOWN_SECONDS` (default `30`) controls when one half-open request may probe recovery. A successful or other non-transient outcome closes the circuit, while another timeout/5xx reopens it. Open providers are skipped while route fallbacks are considered. Redis errors fail open and allow provider traffic. The breaker is passive: it does not send separate health probes.

```bash
export ROUTING_POLICIES_JSON='{"budget-chat":{"strategy":"lowest_cost","max_estimated_cost_per_1k_tokens_usd":0.02,"max_p95_latency_ms":1200,"candidates":[{"provider":"groq","model":"MODEL_A","estimated_cost_per_1k_tokens_usd":0.005,"expected_p95_latency_ms":700,"timeout_seconds":10,"max_retries":1},{"provider":"openai","model":"MODEL_B","estimated_cost_per_1k_tokens_usd":0.015,"expected_p95_latency_ms":900,"timeout_seconds":20,"max_retries":0}]}}'
```

When a request uses `budget-chat` without an explicit provider, the gateway picks the eligible candidate with a configured managed key. The second candidate becomes a fallback. The existing static aliases remain available for aliases not defined in this setting.

## Request example

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "X-Provider: groq" \
  -H "X-Provider-Api-Key: gsk_YOUR_GROQ_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-oss-20b","messages":[{"role":"user","content":"Hello"}]}'
```

## Admin API

Set a long random `ADMIN_API_KEY` in the service environment. Admin reads require it in the `X-Admin-API-Key` header; when the secret is not configured, the admin API fails closed with `503`.

- `GET /admin/api/stats` returns last-24-hour usage totals.
- `GET /admin/api/metrics` returns per-minute request counts and mean latency for the last hour.
- `GET /admin/api/requests/live` returns recent request metadata, with no prompt content or credentials.
- `GET /admin/api/providers` lists supported adapters. It does not perform live provider probes.
- `GET /admin/api/keys` lists key metadata without returning credential material.
- `POST /admin/api/keys` creates a key owned by a named team; the raw key is returned once in the creation response.
- `DELETE /admin/api/keys/{id}` revokes the key while keeping its request history.
- `PUT /admin/api/teams/{team}/budget` sets or disables the team's UTC-month estimated-spend limit.
- `GET /admin/api/teams/{team}/usage` returns estimated spend, active reservations, and remaining budget.

Create a team-owned key with per-key request and token limits:

```bash
curl -X POST http://localhost:8000/admin/api/keys \
  -H "X-Admin-API-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"reporting job","team":"analytics","rpm_limit":30,"tpm_limit":50000}'
```

The response contains the raw gateway key once. Store it securely; later key listings return metadata only.

Set a monthly team budget and inspect its current usage:

```bash
curl -X PUT http://localhost:8000/admin/api/teams/analytics/budget \
  -H "X-Admin-API-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"budget_monthly_usd":"25.00"}'

curl http://localhost:8000/admin/api/teams/analytics/usage \
  -H "X-Admin-API-Key: $ADMIN_API_KEY"
```

Budget checks reserve the estimated maximum cost before an upstream request, serialize concurrent requests for the same team, then reconcile the reservation against reported usage. If a successful response omits usage, the held estimate is charged; abandoned holds expire after 15 minutes. If the next request would exceed the limit, the gateway returns `429` with a `Retry-After` until the next UTC month. Requests without an explicit `max_tokens` use a 1024-token completion cap while a team budget is active. Spend is an estimate based on the gateway's static model-price table, not provider billing; keep that table current before using limits for operational controls.

Example:

```bash
curl http://localhost:8000/admin/api/stats \
  -H "X-Admin-API-Key: $ADMIN_API_KEY"
```

## Health and deployment

- `GET /health` is a process liveness check.
- `GET /ready` checks PostgreSQL and Redis and returns `503` if either dependency is unavailable. Render uses this for deployment health checks.
- Render configuration is in [`render.yaml`](render.yaml); deployment notes are in [docs/deploy-render.md](docs/deploy-render.md).

## Benchmarks

Run [`scripts/bench.sh`](scripts/bench.sh) for gateway load checks, or use [`scripts/replay_evaluation.py`](scripts/replay_evaluation.py) for a pinned prompt/reference replay with baseline and optimized cache policies. See [docs/benchmarks.md](docs/benchmarks.md) for inputs and limitations. No current replay result is published; run with documented price sources before quoting savings.

## Known limitations

- Route policies use operator-supplied cost and latency estimates; budget decisions use the static model-price table, not provider invoices.
- The team usage dashboard requires `ADMIN_API_KEY` and displays estimated spend, not provider invoice totals.
- Cost estimates use a static pricing table and can drift from provider pricing.
- Cache matching is exact, applies to non-streaming responses, and depends on Redis.
- Provider status is not probed. Fallback behavior does not promise zero downtime or output equivalence.
- Redis rate limits coordinate within one Redis deployment, not across regions.

See [docs/implementation-plan.md](docs/implementation-plan.md) for prioritized follow-up tasks.
