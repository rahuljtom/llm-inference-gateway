# Reliability lab: experiment plan and reporting standard

This project explores provider failures, retries, fallback, rate limiting, caching, latency, and token-cost estimates. The repository does not currently contain a reproducible run artifact that supports the historical headline numbers previously shown here. Treat those values as unverified until the experiments below are run and their environment and raw output are committed.

## Questions to answer

- What is the added gateway latency for a cache miss, a cache hit, and a fallback request?
- How does the configured RPM/TPM limit behave under concurrent clients?
- What share of eligible requests can be served from the exact-match cache?
- How often does fallback recover a request, and what latency does it add?
- Does routing or caching reduce estimated spend without unacceptable output-quality changes?

## Reproducibility record

For each run, record:

- Git commit, machine/container resources, Python/Node versions, and dependency lock state.
- Provider, model IDs, price-table version/date, timeout, retry policy, fallback policy, and cache TTL.
- Dataset source, license, prompt count, request settings, and any prompt filtering.
- Request concurrency, repetitions, warm-up approach, and whether provider/network time is included.
- Success and failure counts, status codes, p50/p95/p99 latency, cache-hit rate, fallback rate, token counts, and estimated spend.
- Raw command output and machine-readable results, with credentials removed.

## Cost comparison design

Replay one fixed, licensed dataset under at least two policies:

1. **Baseline:** fixed provider/model, cache disabled.
2. **Optimized:** documented alias/routing policy and exact cache enabled.

Report spend estimates, request success, latency percentiles, cache-hit rate, and a quality proxy or human-reviewed sample together. Avoid claiming “savings” from lower spend alone if the policies return different-quality outputs. Keep provider prices and model identifiers fixed for the comparison and state their date.

## Failure experiment design

Use synthetic failure injection in a local environment. Vary failure rate and timeout, and send enough requests to produce a meaningful denominator. Report primary attempts, fallback attempts, recovered requests, unrecovered requests, and added latency separately. Synthetic results are not evidence of production provider availability.

## Existing load command

See [benchmarks.md](benchmarks.md) for the `oha` load script and its current sample output. That output is historical and illustrative; it is not a current measurement of the deployed service. Re-run the benchmark before using it in a portfolio claim.
