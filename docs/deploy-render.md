# Deploy on Render

Deploy the gateway as a Render Blueprint: one Python web service, managed Postgres, and a Render Key Value (Redis) instance. No upstream LLM API keys are configured on the server (BYOK only).

## Prerequisites

- [Render](https://render.com) account
- This repository pushed to GitHub/GitLab
- A Groq/OpenAI/Anthropic key on the **client** for BYOK requests (not stored on Render)

## One-click Blueprint

1. In Render: **New → Blueprint**.
2. Connect this repo; Render reads [`render.yaml`](../render.yaml) from the repo root.
3. Review services: `llm-inference-gateway` (web), `gateway-db` (Postgres), `gateway-redis` (Key Value).
4. Apply the Blueprint and wait for the first deploy.

## Build and start commands

| Step | Command |
|------|---------|
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

Render sets `$PORT` automatically. Health checks use `GET /health`.

## Environment variables

Set in Blueprint ([`render.yaml`](../render.yaml)) or the Render dashboard:

| Variable | Source | Purpose |
|----------|--------|---------|
| `DATABASE_URL` | Linked Postgres (`gateway-db`) | API keys + request logs |
| `REDIS_URL` | Linked Key Value (`gateway-redis`) | RPM/TPM limits + response cache |
| `PROVIDER_TIMEOUT_SECONDS` | `30` | Upstream httpx timeout |
| `CACHE_ENABLED` | `true` | Exact-match cache (non-streaming) |
| `CACHE_TTL_SECONDS` | `3600` | Cache TTL in seconds |

Do **not** set `OPENAI_API_KEY`, `GROQ_API_KEY`, or similar on Render. Upstream credentials are per-request (headers or JSON body).

### `DATABASE_URL` and asyncpg

Render Postgres connection strings use the `postgresql://` scheme. This app expects SQLAlchemy async URLs:

```text
postgresql+asyncpg://user:pass@host:port/dbname
```

If the dashboard shows `postgresql://…`, change the prefix to `postgresql+asyncpg://` (same host, user, password, database). The app also normalizes `postgresql://` → `postgresql+asyncpg://` on startup when read from the environment.

## Migrations

MVP uses `init_db()` in the FastAPI lifespan ([`app/db/session.py`](../app/db/session.py)): `create_all` plus seeding the `demo-key` gateway key. No separate migration runner is required for the initial deploy.

For production schema changes later, add Alembic or a one-off migration job.

## Verify deploy

```bash
export BASE_URL="https://YOUR-SERVICE.onrender.com"

curl -s "${BASE_URL}/health"
# {"status":"ok","gateway":"online"}

curl -s -X POST "${BASE_URL}/v1/chat/completions" \
  -H "Authorization: Bearer demo-key" \
  -H "X-Provider: groq" \
  -H "X-Provider-Api-Key: gsk_YOUR_GROQ_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"hi"}],"max_tokens":16}'
```

Admin UI (unauthenticated in MVP): `GET /admin`, stats at `GET /admin/api/stats`.

## External Redis (Upstash)

To use Upstash instead of Render Key Value:

1. Remove or ignore the `gateway-redis` service in the Blueprint.
2. Set `REDIS_URL` manually on the web service to your Upstash URL (`rediss://…` if TLS).

## Load benchmarks

See [benchmarks.md](./benchmarks.md) and [`scripts/bench.sh`](../scripts/bench.sh).
