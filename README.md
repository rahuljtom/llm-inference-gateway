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
- Exact-match response caching for non-streaming requests
- PostgreSQL request logs with model, provider, latency, token, cost-estimate, cache, and fallback fields
- Authenticated admin API with usage aggregates from the request log table
- Liveness endpoint at `/health` and dependency readiness endpoint at `/ready`

## Product direction

The next step is a cost and reliability control plane. Team-scoped keys, enforceable budgets, cost-aware routing policies, and a replay-based savings report are planned work; they are not implemented yet. Semantic caching is also out of scope until exact-match results are measured.

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

Run [`scripts/bench.sh`](scripts/bench.sh) as described in [docs/benchmarks.md](docs/benchmarks.md). Historical example output is illustrative and is not a current production measurement or proof of cost savings. Re-run with a documented environment before quoting numbers.

## Known limitations

- Routing uses static aliases; there is no cost/quality policy engine or budget enforcement.
- Keys are per API key, not grouped by team or organization.
- Cost estimates use a static pricing table and can drift from provider pricing.
- Cache matching is exact, applies to non-streaming responses, and depends on Redis.
- Provider status is not probed. Fallback behavior does not promise zero downtime or output equivalence.
- Redis rate limits coordinate within one Redis deployment, not across regions.

See [docs/implementation-plan.md](docs/implementation-plan.md) for prioritized follow-up tasks.
