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

## Dataset replay evaluation

`scripts/replay_evaluation.py` replays a deterministic sample of English prompt/reference pairs from OpenAssistant/oasst1 against baseline and optimized gateway model names. It pins the source to dataset revision `fdf72ae0827c1cda404aff25b6603abec9e3399b` and downloads the ready-for-export tree file on first run. The dataset is marked Apache-2.0 on its [dataset card](https://huggingface.co/datasets/OpenAssistant/oasst1); the upstream dataset description explains that each tree contains a prompter question and assistant replies. The corpus file stays local and is not committed.

The comparison uses the same gateway API key for both routes. It sends each baseline prompt twice with `Cache-Control: no-cache`, then sends each optimized prompt twice through exact-match caching. It records raw request and response bodies, and reports latency percentiles, request failures, observed token usage, cache-hit ratio, and ROUGE-L F1 against one human reference. ROUGE-L is only a lexical similarity proxy. It does not establish answer correctness or broad model quality. Costs and savings are estimates computed from observed token counts and the per-million-token prices supplied to the command; they are not provider invoice totals. Record the date and source of those price inputs when publishing a run. The script makes provider calls and may incur charges.

Example (replace model names, provider keys, and price values with the route and rates being evaluated):

```bash
export GATEWAY_API_KEY=your_gateway_key
export BASELINE_PROVIDER_API_KEY=your_baseline_provider_key
export OPTIMIZED_PROVIDER_API_KEY=your_optimized_provider_key
python scripts/replay_evaluation.py \
  --baseline-url http://localhost:8000 \
  --optimized-url http://localhost:8000 \
  --baseline-provider groq \
  --baseline-model llama-3.3-70b-versatile \
  --optimized-provider groq \
  --optimized-model llama-3.1-8b-instant \
  --baseline-input-price 0.00 \
  --baseline-output-price 0.00 \
  --optimized-input-price 0.00 \
  --optimized-output-price 0.00 \
  --pricing-date 2026-10-18 \
  --baseline-price-source https://console.groq.com/docs/models \
  --optimized-price-source https://console.groq.com/docs/models \
  --limit 50 \
  --output benchmark-results.json
```

The zero prices above are placeholders, not current provider prices or benchmark results. Replace all four prices with the rates applicable to the selected provider/model and date. The price-source values must point to the actual sources used for those rates. Omit `--baseline-provider` or `--optimized-provider` when evaluating an auto-routed alias that resolves its provider from gateway configuration. Raw output contains prompts and generated responses; store it with the same care as other evaluation data.
