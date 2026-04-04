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

### Milestone 6: Staging-Parity Runtime
Status: Completed

- Add service-backed database bootstrapping for Postgres-capable staging and CI environments.
- Normalize async Postgres connection URLs and keep SQLite support for lightweight local/demo paths.
- Add Docker Compose topology for Postgres, Redis, MinIO, API, worker, and frontend.
- Exit gate: the repo can boot in a production-like topology without hand-editing source code.

### Milestone 7: Storage Abstraction
Status: Completed

- Replace raw filesystem upload writes with a storage service boundary.
- Support both local filesystem storage and S3-compatible object storage through one backend contract.
- Add storage unit coverage so object-key shape, bucket creation, and byte round-tripping are regression tested.
- Exit gate: uploaded evidence no longer depends on hardcoded local-path assumptions.

### Milestone 8: CI Release Gate
Status: Completed

- Replace compile-only CI with service-backed backend, frontend, and browser E2E jobs.
- Run browser E2E against a live backend path with Postgres configuration and production-style runtime settings.
- Wire the release gate so backend, frontend, and browser validation are all required in one workflow.
- Exit gate: every push and PR is evaluated against a credible release bundle.

### Milestone 9: Durable Queue Execution
Status: Completed

- Move production analysis dispatch onto ARQ-backed queue submission instead of in-process-only execution.
- Persist queue job IDs, dispatch mode, retry count, and queue metadata on each analysis.
- Add retry scheduling with exponential backoff and dead-letter persistence after retry exhaustion.
- Exit gate: the worker can retry, dead-letter, and audit failed analysis jobs without silently losing execution state.

### Milestone 10: Migration Discipline
Status: Completed

- Add Alembic configuration and a checked-in initial production schema migration.
- Run migrations as part of backend CI before the test suite.
- Add an explicit migration test so schema upgrades are exercised, not assumed.
- Exit gate: the repo has a real migration path rather than relying only on `create_all()`.

### Milestone 11: Production Auth and Abuse Controls
Status: Completed

- Enforce `AUTH_ENABLED=true` and `DEMO_MODE=false` in staging and production environments.
- Add Redis-capable distributed rate limiting with response headers and backend coverage.
- Extend JWT handling with issuer, audience, prior-secret rotation support, and signed artifact tokens.
- Exit gate: production-like environments cannot boot in demo posture and key API surfaces are rate-limited.

### Milestone 12: Report Artifact Lifecycle
Status: Completed

- Generate report artifacts through the storage abstraction rather than inline-only responses.
- Persist artifact metadata including checksum, size, content type, and retention window.
- Add signed artifact download URLs so reports can be retrieved without exposing raw storage paths.
- Exit gate: report artifacts participate in a real lifecycle with storage metadata and tokenized access.

### Milestone 13: Operations and Audit Surfaces
Status: Completed

- Add readiness checks for database, queue, and storage backends.
- Add admin endpoints for audit-log inspection and API-key rotation.
- Add dead-letter visibility for operator support and incident follow-up.
- Exit gate: operators can see whether the platform is ready, what failed, and who performed privileged actions.

### Milestone 14: Governance Controls
Status: Completed

- Persist governance policy version and model manifest with every analysis.
- Apply evidence-completeness and degraded-state holds to underwriting recommendations.
- Carry human-review requirements and blocked-decision reasons into persisted analysis/report state.
- Exit gate: the system can explicitly downgrade decision authority when evidence quality is insufficient.

### Milestone 15: Verification Refresh
Status: Completed

- Add dedicated production-control tests for readiness, metrics, dead letters, admin endpoints, rate limits, and signed artifacts.
- Re-run the full backend, frontend, build, and browser verification bundle after the queue/governance tranche.
- Exit gate: the release bundle covers control-plane behavior, not only the core analysis flow.

### Milestone 16: Secure Webhook Delivery
Status: Completed

- Encrypt registered webhook secrets at rest instead of storing only irreversible hashes.
- Restore HMAC-signed outbound delivery for persisted webhooks using decrypted runtime secrets.
- Fail closed when encrypted webhook secrets are invalid, and persist delivery failure metadata for operator follow-up.
- Exit gate: registered webhook delivery is signed again without exposing secrets through read APIs.

### Milestone 17: Authenticated Browser E2E
Status: Completed

- Add a shared frontend API auth-header layer that supports bearer tokens and API keys.
- Run the default Playwright live-backend suite with backend auth enabled instead of a bypassed path.
- Inject deterministic E2E credentials at the Playwright/runtime boundary so the browser flow exercises the real auth gate.
- Exit gate: browser E2E proves the operator UX works through authenticated backend requests.

### Milestone 18: Observability Bridge
Status: Completed

- Add optional OpenTelemetry wiring for FastAPI, HTTPX, and SQLAlchemy with graceful fallback when exporters or packages are unavailable.
- Surface observability state through health, metrics, and readiness, including required-vs-optional gating.
- Propagate trace IDs into response headers when telemetry is active so incident investigation can correlate browser, API, and worker paths.
- Exit gate: the codebase can plug into a real observability stack without destabilizing local/dev/test flows.

### Milestone 19: Frontend Bundle Discipline
Status: Completed

- Remove the unused 3D viewer export that was retaining the heavy `three` dependency tree in the shipped build.
- Tighten Vite chunking so future 3D/vendor work stays isolated instead of polluting the main app bundle.
- Verify the production build without the former oversized vendor-chunk warning.
- Exit gate: the shipped frontend no longer carries the unused 3D payload or the associated warning.

### Milestone 20: Collector-Backed Observability Stack
Status: Completed

- Add a dedicated observability compose overlay with OpenTelemetry Collector, Prometheus, Tempo, Alertmanager, and Grafana.
- Introduce a machine-token access path for readiness and Prometheus scraping so internal telemetry does not depend on user JWTs.
- Extend Prometheus exposition with latency, analysis-created, stream, and exporter-info metrics suitable for dashboards and alerts.
- Instrument the ARQ worker with trace spans so collector-backed tracing covers background execution as well as API requests.
- Add CI smoke coverage that boots the backend against a live collector and proves spans are accepted.
- Exit gate: the repo can boot a real local observability stack and CI verifies collector-backed instrumentation instead of only code-level OTel readiness.

## Verification Completed

- `pytest -q backend/tests` -> `169 passed`
- `npm test` -> `12 passed`
- `npm run build` -> passed
- `npm run test:e2e` -> `4 passed`

Build footprint after bundle cleanup:

- main app bundle: `234.93 kB`
- degradation timeline lazy chunk: `61.18 kB`
- risk matrix lazy chunk: `7.56 kB`

## Next Architectural Moves After This Roadmap

1. Carry the new collector stack into staging and production with owned dashboards, routed alerts, retention policy, and service-level objectives.
2. Run browser E2E with auth enabled against fully live Postgres and object storage in CI and staging.
3. Add operator-facing webhook rotation and replay-verification guidance on top of the secure storage/delivery path.
4. Build multi-epoch comparison, telemetry fusion, and baseline drift scoring for subsystem-level inspection authority.
