# Load benchmarks (`oha`)

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

CI smoke (health only, no upstream):

```bash
SKIP_UPSTREAM=1 ./scripts/bench.sh
```

## Scenarios

| Scenario | Payload | What it measures |
|----------|---------|------------------|
| **miss** | `stream: true` | End-to-end latency through gateway + upstream (cache skipped) |
| **hit** | Same non-streaming JSON repeated | Gateway cache + Postgres logging; much lower p50 after prime |

## Sample output (local, illustrative)

Environment: MacBook, `BASE_URL=http://127.0.0.1:8000`, `OHA_REQUESTS=50`, `OHA_CONCURRENCY=10`, Groq `llama-3.1-8b-instant`, May 2026.

### Cache MISS (`stream: true`)

```text
Summary:
  Success rate: 100.00%
  Total:        50 requests in 12.34s
  Request/sec:  4.05
  Latency:
    Average:    2.41s
    p50:        2.28s
    p99:        3.91s
```

### Cache HIT (non-streaming, identical body)

```text
Summary:
  Success rate: 100.00%
  Total:        50 requests in 1.02s
  Request/sec:  49.02
  Latency:
    Average:    18.2ms
    p50:        16.1ms
    p99:        42.5ms
```

Numbers vary with hardware, network, provider load, and cache TTL. Re-run on your machine and paste updated tables when publishing results.

## What to record

- RPS (`Request/sec`)
- p50 / p99 latency
- Success rate (target 100% with valid BYOK key)
- Error rate (429 from gateway limits vs 401 upstream key)

See also [deploy-render.md](./deploy-render.md) for production `BASE_URL`.
