# Orbital Inspect Production Roadmap

Generated: 2026-04-02

## Objective

Move Orbital Inspect from a hardened demo platform into a trusted operational system that can be validated, audited, and sold into serious insurer/operator workflows.

## Milestones

### Milestone 1: Live Full-Stack E2E
Status: Completed

- Replace mocked browser E2E with deterministic live-backend runs.
- Isolate E2E database and upload storage into ephemeral paths.
- Keep deterministic stub scenarios only as backend-controlled fixtures, not frontend route mocks.
- Exit gate: `npm run test:e2e` exercises the real backend, worker, persistence, SSE stream, and portfolio flow.

### Milestone 2: Operational Observability
Status: Completed

- Add request correlation IDs and response headers.
- Add in-process metrics for request volume, analysis terminal states, stage timing, and SSE stream behavior.
- Expose a metrics snapshot endpoint for staging and E2E verification.
- Exit gate: every analysis can be traced from HTTP submission to worker completion with measurable timings.

### Milestone 3: Failure Injection and Resilience
Status: Completed

- Expand deterministic failure scenarios so full-stack tests cover `completed`, `completed_partial`, `failed`, and `rejected`.
- Add assertions around terminal-state truthfulness, stream completion, and degraded evidence handling.
- Exit gate: failure-path regressions are caught by backend and browser E2E before release.

### Milestone 4: Evidence Lineage Foundation
Status: Completed

- Persist inspection epoch, subsystem focus, request correlation, and richer evidence summary metadata.
- Surface that lineage in the UI so operators can audit what was inspected and when.
- Exit gate: analyses are traceable across epochs and subsystem-specific review workflows.

### Milestone 5: Release Verification
Status: Completed

- Run backend tests, frontend unit tests, production build, and live browser E2E as one release gate.
- Document residual risks and next architecture moves.
- Exit gate: one repeatable verification bundle for every candidate release.

## Verification Completed

- `pytest -q backend/tests/test_e2e.py backend/tests/test_auth_e2e.py` -> `20 passed`
- `npm test` -> `12 passed`
- `npm run build` -> passed
- `npm run test:e2e` -> `4 passed`

## Next Architectural Moves After This Roadmap

1. Move full-stack E2E to ephemeral Postgres and object storage.
2. Add distributed worker queues and retry policies with dead-letter handling.
3. Build multi-epoch comparison and baseline drift scoring.
4. Add incident dashboards, alert thresholds, and replay tooling for operator support.
