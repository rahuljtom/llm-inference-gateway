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
- Static model aliases such as `fast-chat` and `smart-chat`; aliases map to configured providers and do not select models dynamically by cost
- Optional fallback provider for eligible upstream failures
- Redis sliding-window RPM and estimated TPM limits per gateway API key
- Exact-match response caching for non-streaming requests; clients can bypass cache reads and writes with `Cache-Control: no-cache`
- PostgreSQL request logs with model, provider, latency, token, cost-estimate, cache, and fallback fields
- Authenticated admin API with usage aggregates from the request log table
- Liveness endpoint at `/health` and dependency readiness endpoint at `/ready`

## Product direction

Planned improvements build on the existing gateway with team-scoped keys, enforceable budgets, cost-aware routing policies, and a replay-based savings report. These capabilities are not implemented yet. Semantic caching is also out of scope until exact-match results are measured.

## Architecture

```mermaid
graph TD
    Client[Client or SDK] -->|OpenAI-compatible request| Gateway[FastAPI gateway]
    Gateway -->|RPM/TPM and exact cache| Redis[(Redis)]
    Gateway -->|API key and request logs| Postgres[(PostgreSQL)]
    Gateway --> Router{Static aliases or explicit provider}
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

## Request example

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "X-Provider: groq" \
  -H "X-Provider-Api-Key: gsk_YOUR_GROQ_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"Hello"}]}'
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

Create a team-owned key with per-key request and token limits:

```bash
curl -X POST http://localhost:8000/admin/api/keys \
  -H "X-Admin-API-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"reporting job","team":"analytics","rpm_limit":30,"tpm_limit":50000}'
```

The response contains the raw gateway key once. Store it securely; later key listings return metadata only.

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

- Routing uses static aliases; there is no cost/quality policy engine or budget enforcement.
- Team names can own API keys, but there is no team-level budget enforcement or usage dashboard yet.
- Cost estimates use a static pricing table and can drift from provider pricing.
- Cache matching is exact, applies to non-streaming responses, and depends on Redis.
- Provider status is not probed. Fallback behavior does not promise zero downtime or output equivalence.
- Redis rate limits coordinate within one Redis deployment, not across regions.

See [docs/implementation-plan.md](docs/implementation-plan.md) for prioritized follow-up tasks.
