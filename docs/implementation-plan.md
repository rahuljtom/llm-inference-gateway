# LLM Gateway: implementation plan

This plan strengthens the existing gateway and adds measurable reliability and usage controls in stages.

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
- [x] Build and run the current branch with Postgres and Redis in an isolated local Compose stack; `/health` and `/ready` return 200, and the admin API fails closed with 503 when its key is unset.
- [ ] Check the Render deployment logs and health after the updated branch is available there. The public endpoint did not return an app response during review; deployment logs are not available from this checkout.

## Completed follow-up

- [x] Add Docker build-context exclusions for local environments, caches, and frontend dependencies.
- [x] Build the frontend production assets and check in the generated assets served by the app.
- [x] Move the live-provider smoke check out of pytest discovery so CI only runs deterministic tests.

## P2 — Measure routing and caching outcomes

- [ ] Run a fixed, licensed prompt corpus through a documented baseline and optimized policy.
- [ ] Publish the corpus/version, model prices/date, command, raw results, latency percentiles, failure rate, and a quality measure.
- [ ] Separate measured savings from estimated savings.

## P3 — Extend gateway management capabilities

- [x] Add team-scoped key creation, listing, revocation, and atomic estimated-budget enforcement with explicit over-budget behavior.
- [x] Replace static aliases as the only option with configurable route policies using cost, latency, and fallback constraints.
- [x] Add a Redis-backed passive provider circuit with timeout/5xx thresholds, cooldown, single half-open recovery request, and fail-open Redis behavior. Active health probes remain deferred.
- [x] Add a team usage dashboard backed by the authenticated admin API, with spend, reservations, active key count, and monthly budget controls.
- [x] Update built-in model aliases, examples, and static price estimates for current provider model availability.
- [ ] Consider semantic caching after exact-match cache correctness and savings are measured.

## Current limits

There is no license file yet; choose a license before treating this as a reusable open-source project.

The current branch was rebuilt and checked in an isolated local Compose stack on ports 8001 (app), 5436 (PostgreSQL), and 6381 (Redis), since the existing project stack already occupies its default ports. The app returned healthy liveness/readiness responses and the admin API returned 503 without `ADMIN_API_KEY`. The public Render service still needs a deployment-log check and deployment of this branch before its updated readiness behavior can be confirmed.
