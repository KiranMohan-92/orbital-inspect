# Orbital Inspect

Orbital Inspect is an orbital infrastructure health intelligence platform for satellite operators, insurers, and future in-space infrastructure builders.

It combines a durable backend analysis pipeline, persisted event streaming, evidence-aware risk synthesis, and a production-grade frontend workflow for inspecting orbital assets from uploaded imagery and supporting context.

## What It Does

- accepts orbital asset imagery plus operator context
- creates durable analysis jobs through `/api/analyses`
- runs a multi-stage inspection pipeline
- persists stage outputs, audit events, and final status
- streams real-time analysis events over SSE
- generates risk-oriented inspection output and portfolio views
- supports browser E2E validation against a live backend
- supports local filesystem or S3-compatible object storage for uploaded inspection evidence

## Current Product Shape

The system is currently optimized as an orbital inspection and underwriting intelligence product, with schema support for broader orbital infrastructure such as:

- `satellite`
- `servicer`
- `station_module`
- `solar_array`
- `radiator`
- `power_node`
- `compute_platform`
- `other`

The latest production hardening tranche added:

- durable analysis submission and persisted event streaming
- correct terminal analysis states: `completed`, `completed_partial`, `failed`, `rejected`
- auth and org-aware backend coverage
- live full-stack browser E2E using deterministic backend fixtures
- request correlation IDs and metrics
- inspection epoch and subsystem lineage fields in the product surface
- Postgres-ready runtime bootstrapping and service-backed E2E configuration
- storage abstraction for local and S3-compatible backends
- CI workflow with backend, observability, frontend, and browser E2E release gates
- queue-backed worker dispatch through ARQ with retry and dead-letter persistence
- Alembic migration scaffolding and migration test coverage
- admin audit and API-key rotation endpoints
- signed report artifact generation and download
- governance-driven underwriting holds and mandatory human review flags
- readiness checks and Prometheus-style metrics output
- distributed rate-limit dependency with Redis-capable backend support
- encrypted webhook secret storage with signed outbound delivery restoration
- auth-enabled live browser E2E against the real backend path
- optional OpenTelemetry wiring for FastAPI, HTTPX, and SQLAlchemy with readiness/health surfacing
- collector-backed observability overlay with OpenTelemetry Collector, Prometheus, Tempo, Alertmanager, and Grafana
- machine-token access path for metrics/readiness scraping without coupling collectors to user JWT flows
- frontend bundle cleanup removing the unused 3D vendor payload from the shipped build

## Architecture

### Backend

- FastAPI API surface
- SQLAlchemy async persistence
- SQLite for demo/local paths and Postgres-ready async support for staging/CI
- multi-stage analysis orchestration
- persisted analysis events and reports
- structlog-based request logging and correlation
- lightweight metrics endpoint at `/api/metrics`
- Prometheus-style metrics endpoint at `/api/metrics/prometheus`
- storage abstraction for uploaded evidence and generated report artifacts
- Alembic-managed schema evolution for production databases
- queue dispatch, retry tracking, and dead-letter visibility for worker execution
- encrypted secret handling for registered webhooks
- optional trace-aware observability hooks with `X-Trace-ID` response propagation when OTel is active
- worker-side trace spans so collector-backed telemetry captures background execution and not only HTTP requests

Key backend paths:

- [`backend/main.py`](/mnt/c/Users/kiran/myprojects/orbital-inspect/backend/main.py)
- [`backend/agents/orchestrator.py`](/mnt/c/Users/kiran/myprojects/orbital-inspect/backend/agents/orchestrator.py)
- [`backend/workers/analysis_worker.py`](/mnt/c/Users/kiran/myprojects/orbital-inspect/backend/workers/analysis_worker.py)
- [`backend/db/models.py`](/mnt/c/Users/kiran/myprojects/orbital-inspect/backend/db/models.py)

### Frontend

- React + Vite
- durable submission flow via `/api/analyses`
- SSE-driven analysis state updates
- portfolio monitoring view
- Playwright browser E2E and Vitest unit coverage

Key frontend paths:

- [`frontend/src/App.tsx`](/mnt/c/Users/kiran/myprojects/orbital-inspect/frontend/src/App.tsx)
- [`frontend/src/hooks/useSSE.ts`](/mnt/c/Users/kiran/myprojects/orbital-inspect/frontend/src/hooks/useSSE.ts)
- [`frontend/src/hooks/useAnalysisState.ts`](/mnt/c/Users/kiran/myprojects/orbital-inspect/frontend/src/hooks/useAnalysisState.ts)
- [`frontend/e2e/analysis-flow.spec.ts`](/mnt/c/Users/kiran/myprojects/orbital-inspect/frontend/e2e/analysis-flow.spec.ts)

## Local Development

### Backend

```bash
cd backend
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
GEMINI_API_KEY=your_key_here python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

For local demo use:

```bash
cd backend
DEMO_MODE=true GEMINI_API_KEY=test-dummy-key python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

For staging-parity local runs with Docker Compose:

```bash
docker compose --profile full up --build
```

For the full local observability stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile full up --build
```

This brings up:

- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3001`
- Tempo: `http://127.0.0.1:3200`
- Alertmanager: `http://127.0.0.1:9093`

Default local observability scrape token:

```bash
export OBSERVABILITY_SHARED_TOKEN=orbital-observability-dev-token
```

The Prometheus/Grafana stack uses that machine token to scrape `/api/metrics/prometheus` and `/api/ready` without relying on user-role JWTs.

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

Frontend URL:

- `http://127.0.0.1:4173`

Backend health:

- `http://127.0.0.1:8000/api/health`

## Tests

### Backend

```bash
pytest -q backend/tests
```

### Frontend Unit

```bash
cd frontend
npm test
```

### Frontend Build

```bash
cd frontend
npm run build
```

### Frontend Browser E2E

```bash
cd frontend
npm run test:e2e
```

The browser E2E suite runs against a live backend using deterministic backend-side fixtures. It exercises the real submission, worker, persistence, SSE, and portfolio paths.
The default browser E2E path now runs with backend auth enabled and frontend API calls authenticated through the same header layer used in production-like environments.

To force a Postgres-backed live run locally:

```bash
cd frontend
npm run test:e2e:live
```

This expects a reachable Postgres instance and can be paired with the `docker compose --profile full up` stack.

## Key Endpoints

- `POST /api/analyses`
- `GET /api/analyses`
- `GET /api/analyses/{id}`
- `GET /api/analyses/{id}/events/stream`
- `GET /api/portfolio`
- `GET /api/portfolio/summary`
- `GET /api/metrics`
- `GET /api/metrics/prometheus`
- `GET /api/ready`
- `GET /api/ops/dead-letters`
- `POST /api/admin/api-key/rotate`
- `GET /api/admin/audit`
- `POST /api/reports/{analysis_id}/generate-pdf`
- `GET /api/reports/artifacts/{token}`

## Verification Snapshot

Latest verified commands on the current shipped tranche:

- backend full suite: `169 passed`
- frontend unit tests: `12 passed`
- frontend browser E2E: `4 passed`
- frontend production build: passed

Current production build footprint:

- main app bundle: `234.93 kB`
- degradation timeline lazy chunk: `61.18 kB`
- risk matrix lazy chunk: `7.56 kB`

## Docs

- production roadmap: [`ROADMAP-PRODUCTION-2026-04-02.md`](/mnt/c/Users/kiran/myprojects/orbital-inspect/ROADMAP-PRODUCTION-2026-04-02.md)
- architectural review: [`REVIEW-2026-04-01.md`](/mnt/c/Users/kiran/myprojects/orbital-inspect/REVIEW-2026-04-01.md)
- prior audit note: [`AUDIT-GPT54.md`](/mnt/c/Users/kiran/myprojects/orbital-inspect/AUDIT-GPT54.md)

## Next Moves

From a production architecture perspective, the next major upgrades should be:

1. deploy the new observability overlay into staging with real collector retention, dashboard ownership, alert routing, and SLO thresholds
2. run auth-enabled browser E2E against fully live Postgres and object storage in CI and staging
3. add replay-protected webhook verification guidance and webhook rotation workflows to the operator surface
4. deepen evidence lineage with multi-epoch comparison, telemetry fusion, and baseline drift analysis
