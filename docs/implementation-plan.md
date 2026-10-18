# LLM Gateway: implementation plan

This plan puts the current repository in a trustworthy state before expanding it into a cost-control product.

## P0 — Make current behavior safe and accurate

- [x] Review GitHub `main`, the local checkout, the Render endpoint, and current app behavior.
- [x] Use an isolated branch based on the latest default-branch commit.
- [x] Require `ADMIN_API_KEY` for admin API reads and fail closed when it is missing.
- [x] Replace fabricated admin API metrics with aggregates from PostgreSQL request logs.
- [x] Add a readiness endpoint that checks PostgreSQL and Redis; keep `/health` as process liveness.
- [x] Change the UI to label its numbers as current-browser-session observations and stop claiming DB/Redis/provider health it does not measure.
- [x] Correct README and architecture/report claims to match the code.

## P1 — Restore a repeatable release path

- [x] Add GitHub Actions for the existing Python tests and frontend production build.
- [x] Build and run the app locally with Postgres and Redis; `/health` and `/ready` return 200, and the admin API fails closed with 503 when its key is unset.
- [ ] Check the Render deployment logs and health after the updated branch is available there. The public endpoint did not return an app response during review; deployment logs are not available from this checkout.

## Completed follow-up

- [x] Add Docker build-context exclusions for local environments, caches, and frontend dependencies.
- [x] Build the frontend production assets and check in the generated assets served by the app.

## P2 — Demonstrate the cost claim

- [ ] Run a fixed, licensed prompt corpus through a documented baseline and optimized policy.
- [ ] Publish the corpus/version, model prices/date, command, raw results, latency percentiles, failure rate, and a quality measure.
- [ ] Separate measured savings from estimated savings.

## P3 — Add control-plane capabilities

- [ ] Add team-scoped keys and atomic budget enforcement with explicit over-budget behavior.
- [ ] Replace static aliases with configurable routing policies using cost, latency, and fallback constraints.
- [ ] Add provider health probes and circuit-breaker behavior only with clear timeout, retry, and recovery rules.
- [ ] Consider semantic caching after exact-match cache correctness and savings are measured.

## Current limits

There is no license file yet; choose a license before treating this as a reusable open-source project.

The local Docker app has been rebuilt from this branch. Its admin API remains disabled until `ADMIN_API_KEY` is configured. The public Render service still needs a deployment-log check and a deployment of this branch before its updated readiness behavior can be confirmed.
