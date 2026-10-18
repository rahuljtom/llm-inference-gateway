# Gateway implementation tasks

This checklist tracks delivery of the work in [the implementation plan](docs/implementation-plan.md). Update it after each completed implementation chunk.

## P0 — Current behavior safety and accuracy

- [x] Protect admin reads and report persisted request usage.
- [x] Add dependency readiness checks and accurate session-scoped UI labels.
- [x] Align product documentation with implemented behavior.

## P1 — Repeatable release path

- [x] Add CI for Python checks and frontend production builds.
- [x] Build and run the local Docker stack with PostgreSQL and Redis; verify liveness, readiness, and fail-closed admin behavior.
- [ ] Verify the deployed service and Render deployment logs when deployment access is available.

## P2 — Routing and caching measurements

- [ ] Select a public prompt corpus with a compatible license; record its source, version, and license.
- [ ] Define reproducible baseline and optimized gateway policies, model identifiers, pricing inputs, and the pricing effective date.
- [ ] Build a repeatable runner that saves raw responses, request outcomes, token usage, cost, and latency data without exposing credentials.
- [ ] Compare baseline and optimized runs using latency percentiles, failure rate, and a documented quality measure.
- [ ] Publish commands and results; label measured and estimated savings separately and document limitations.

## P3 — Gateway management capabilities

- [ ] Specify team-scoped key ownership, storage, rotation, and revocation behavior.
- [ ] Implement atomic budget accounting and enforcement with documented behavior at and over each budget limit.
- [ ] Replace fixed aliases with configurable routing policies and explicit cost, latency, and fallback constraints.
- [ ] Define provider probe, timeout, retry, circuit-open, and recovery behavior before enabling circuit breakers.
- [ ] Measure exact-match cache correctness and savings; evaluate semantic caching only after those results are available.

## Validation and delivery

- [ ] Run focused tests and checks for each implementation chunk; run the full relevant suite before completion.
- [ ] Review each change for correctness, secrets, attribution, documentation accuracy, and unrelated files before committing.
- [ ] Push reviewed commits to the feature branch in small, independent units.
