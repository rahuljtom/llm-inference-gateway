# Gateway load checks (`oha`)

Reproducible load numbers for the gateway using [oha](https://github.com/hatoo/oha). The script exercises gateway auth plus BYOK headers; upstream calls go to the real provider (Groq by default).

## Prerequisites

- Gateway running locally (`docker compose up -d` + `uvicorn app.main:app`) or deployed URL in `BASE_URL`
- `oha` installed (`brew install oha` or `cargo install oha`)
- `GROQ_API_KEY` set (or another provider via `BENCH_PROVIDER` + key env)

## Run

```bash
export GROQ_API_KEY=gsk_YOUR_KEY
chmod +x scripts/bench.sh
./scripts/bench.sh
```

Optional:

```bash
export BASE_URL=https://your-service.onrender.com
export OHA_REQUESTS=100
export OHA_CONCURRENCY=20
export SCENARIO=hit   # miss | hit | both
```

Health check (no upstream, requires the gateway and its dependencies to be ready):

```bash
SKIP_UPSTREAM=1 ./scripts/bench.sh
```

## Scenarios

| Scenario | Payload | What it measures |
|----------|---------|------------------|
| **miss** | `stream: true` | End-to-end latency through gateway + upstream (cache skipped) |
| **hit** | Same non-streaming JSON repeated | Gateway cache + Postgres logging; much lower p50 after prime |

This command measures gateway and upstream latency. It does not replay a public dataset, compare routing policies, assess output quality, or calculate savings. No current benchmark result is published here; commit raw output and full run settings before quoting measurements.

## What to record

- RPS (`Request/sec`)
- p50 / p99 latency
- Success rate and failure categories
- Error rate (429 from gateway limits vs 401 upstream key)

See also [deploy-render.md](./deploy-render.md) for production `BASE_URL`.
