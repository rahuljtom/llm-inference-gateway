# LLM Inference Gateway architecture

## Request path

1. FastAPI authenticates the gateway bearer key against a SHA-256 hash stored in PostgreSQL.
2. Redis enforces per-key request and estimated-token limits. Non-streaming responses may use the exact-match cache; `Cache-Control: no-cache` bypasses both cache reads and writes for that request.
3. The ingress layer resolves an explicit provider or one of the static model aliases.
4. A provider adapter normalizes the upstream response to the OpenAI chat-completion schema. Optional fallback credentials and provider selection may be supplied with the request.
5. Request metadata, token counts, latency, a pricing-table cost estimate, cache status, and fallback status are written to PostgreSQL.

The gateway does not store prompt content in the request log. Provider credentials are passed to the adapter for the request and are excluded from cache keys.

## Components

| Component | Responsibility | Current boundary |
|---|---|---|
| FastAPI | OpenAI-compatible HTTP endpoint and streaming response | Chat completions only |
| Provider adapters | Translate requests/responses for OpenAI, Anthropic, Gemini, and Groq | Provider-specific metadata may be lost during normalization |
| Routing aliases | Map aliases such as `fast-chat` to fixed provider/model pairs | Static mapping, not cost-aware selection |
| Redis | Sliding-window RPM/TPM limits and exact response cache | One Redis deployment; no cross-region coordination |
| PostgreSQL | Team ownership, gateway API key metadata, and request usage records | Monthly spend budgets are not enforced yet |
| Admin API | Usage totals, minute buckets, recent request metadata, adapter list | Requires `X-Admin-API-Key`; provider list is not a health probe |
| React playground | Send sample requests and show browser-session latency | Session telemetry, not a persisted operations dashboard |

## Health endpoints

- `GET /health` reports that the process is answering.
- `GET /ready` checks PostgreSQL and Redis and returns `503` when either dependency is unavailable. Render uses this endpoint before routing traffic.

## Cost accounting

The request logger estimates cost from provider-reported token counts and a static model-price table. This is useful for a prototype report but is not billing-grade accounting: prices may change, token usage may be missing or provider-specific, and the table is not versioned with each request. The current gateway does not enforce spend budgets.

## Reliability behavior

Fallback can retry or switch provider on selected upstream failures. This improves the chance of returning a response but does not guarantee zero downtime or equivalent output. The project has synthetic failure injection for local experiments. Report failure rates and latency only with the workload, provider, timeout/retry policy, and run artifact attached.

## Next architecture steps

1. Add team-scoped keys and a budget ledger with atomic limits.
2. Add configurable policy routing with explicit cost, latency, and quality constraints.
3. Version provider price data and retain the price version used for every estimate.
4. Add provider health probes and circuit breakers with defined recovery behavior.
5. Evaluate semantic caching only after exact cache behavior and savings are measured.
