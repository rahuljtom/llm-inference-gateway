# LLM Inference Gateway architecture

## Request path

1. FastAPI authenticates the gateway bearer key against a SHA-256 hash stored in PostgreSQL.
2. Redis enforces per-key request and estimated-token limits. Non-streaming responses may use the exact-match cache; `Cache-Control: no-cache` bypasses both cache reads and writes for that request.
3. The ingress layer resolves an explicit provider, static alias, or configured route policy.
4. A provider adapter normalizes the upstream response to the OpenAI chat-completion schema. Optional fallback credentials and provider selection may be supplied with the request.
5. Request metadata, token counts, latency, a pricing-table cost estimate, cache status, and fallback status are written to PostgreSQL.

The gateway does not store prompt content in the request log. Provider credentials are passed to the adapter for the request and are excluded from cache keys.

## Components

| Component | Responsibility | Current boundary |
|---|---|---|
| FastAPI | OpenAI-compatible HTTP endpoint and streaming response | Chat completions only |
| Provider adapters | Translate requests/responses for OpenAI, Anthropic, Gemini, and Groq | Provider-specific metadata may be lost during normalization |
| Route policies and circuit breaker | Select candidates by configured cost or expected p95 latency limits; use later eligible candidates as fallback and skip open provider circuits | Estimates are operator-supplied; breaker state uses Redis and fails open if Redis is unavailable |
| Redis | Sliding-window RPM/TPM limits and exact response cache | One Redis deployment; no cross-region coordination |
| PostgreSQL | Team ownership, gateway API key metadata, request usage, and monthly budget reservations | Spend is estimated from the configured model-price table |
| Admin API | Usage totals, minute buckets, recent request metadata, adapter list | Requires `X-Admin-API-Key`; provider list is not a health probe |
| React frontend | Send sample requests and inspect team spend, reservations, active keys, and budget limits | Playground telemetry remains session-scoped; team dashboard requires the admin key and reports estimates |

## Health endpoints

- `GET /health` reports that the process is answering.
- `GET /ready` checks PostgreSQL and Redis and returns `503` when either dependency is unavailable. Render uses this endpoint before routing traffic.

## Cost accounting

The request logger estimates cost from provider-reported token counts and a static model-price table. Team budgets reserve a worst-case estimate before upstream calls, then reconcile the hold against reported usage; concurrent requests for the same team serialize on its database row. Requests that would exceed the UTC calendar-month limit receive `429`. If a successful provider response omits usage, the gateway charges the held estimate. This is not billing-grade accounting: prices may change, provider tokenization and usage vary, and the table is not versioned with each request.

## Reliability behavior

Configured route policies filter candidates by operator-supplied estimated cost and expected p95 latency. Non-streaming requests retry timeouts and 429 responses within the configured retry limit; eligible later candidates are tried after timeouts and 5xx responses. Streaming requests use the configured timeout and can fail over on timeout/5xx without retries. A Redis-backed passive circuit opens after consecutive timeouts/5xx, skips the provider during its cooldown, then permits one half-open request; a successful or other non-transient outcome closes it. Redis errors fail open. These controls improve the chance of returning a response but do not guarantee zero downtime or equivalent output. Report failure rates and latency only with the workload, provider, timeout/retry policy, and run artifact attached.

## Next architecture steps

1. Version provider price data and retain the price version used for every estimate.
2. Evaluate semantic caching only after exact cache behavior and savings are measured.
