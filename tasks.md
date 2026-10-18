# Gateway implementation tasks

This checklist tracks delivery of the work in [the implementation plan](docs/implementation-plan.md). Update it after each completed implementation chunk.

## P0 — Current behavior safety and accuracy

- [x] Protect admin reads and report persisted request usage.
- [x] Add dependency readiness checks and accurate session-scoped UI labels.
- [x] Align product documentation with implemented behavior.

## P1 — Repeatable release path

- [x] Add CI for Python checks and frontend production builds.
- [x] Build and run the current branch in an isolated local Docker stack with PostgreSQL and Redis; verify liveness, readiness, and fail-closed admin behavior.
- [ ] Verify the deployed service and Render deployment logs when deployment access is available.

## P2 — Routing and caching measurements

- [x] Select a public prompt corpus with a compatible license; record its source, pinned revision, and license.
- [x] Define reproducible baseline and optimized runs with explicit route names, cache modes, price inputs/sources, and pricing effective date.
- [x] Build a replay runner that saves raw responses, request outcomes, token usage, estimated cost, cache hits, and latency data without exposing credentials.
- [x] Report latency percentiles, failure rate, cache-hit ratio, and ROUGE-L F1 as a clearly limited quality proxy.
- [ ] Complete and publish a representative paired evaluation. An initial 50-prompt run completed, but upstream 429s, gateway 500s, and an uneven quality-comparison sample make its estimated savings unsuitable for a result claim. Keep the raw run outside the repository; rerun after controlling request rates and resolving the gateway/database errors.

## P3 — Gateway management capabilities

- [x] Specify and add team-owned API key creation, listing, and revocation; return raw keys only at creation.
- [x] Implement atomic team-month reservations, usage reconciliation, and `429` behavior when a request would exceed its budget.
- [x] Expose team budget configuration and current-month spend/reservation totals through the admin API.
- [x] Add configurable route policies with estimated cost/p95 latency limits, candidate timeouts, bounded retries, and ordered 5xx/timeout fallback.
- [x] Add Redis-backed passive provider circuits with configurable timeout/5xx threshold, cooldown, one half-open recovery request, and documented Redis failure behavior; defer active probes.
- [x] Add an authenticated team usage dashboard for estimated spend, reservations, active keys, and monthly budget controls.
- [x] Update built-in model aliases, examples, and static price estimates for current provider model availability.
- [ ] Measure exact-match cache correctness and savings; evaluate semantic caching only after those results are available.

## Validation and delivery

- [x] Run focused tests and checks for each implementation chunk; run the full relevant suite before completion.
- [x] Review each change for correctness, secrets, attribution, documentation accuracy, and unrelated files before committing.
- [x] Push reviewed commits to the feature branch in small, independent units.
