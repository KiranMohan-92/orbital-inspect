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
- CI workflow with backend, frontend, and browser E2E release gates

## Architecture

### Backend

- FastAPI API surface
- SQLAlchemy async persistence
- SQLite for demo/local paths and Postgres-ready async support for staging/CI
- multi-stage analysis orchestration
- persisted analysis events and reports
- structlog-based request logging and correlation
- lightweight metrics endpoint at `/api/metrics`
- storage abstraction for uploaded evidence and future generated artifacts

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
pytest -q backend/tests/test_e2e.py backend/tests/test_auth_e2e.py
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

## Verification Snapshot

Latest verified commands on the current shipped tranche:

- backend full suite: `149 passed`
- frontend unit tests: `12 passed`
- frontend browser E2E: `4 passed`
- frontend production build: passed

## Docs

- production roadmap: [`ROADMAP-PRODUCTION-2026-04-02.md`](/mnt/c/Users/kiran/myprojects/orbital-inspect/ROADMAP-PRODUCTION-2026-04-02.md)
- architectural review: [`REVIEW-2026-04-01.md`](/mnt/c/Users/kiran/myprojects/orbital-inspect/REVIEW-2026-04-01.md)
- prior audit note: [`AUDIT-GPT54.md`](/mnt/c/Users/kiran/myprojects/orbital-inspect/AUDIT-GPT54.md)

## Next Moves

From a production architecture perspective, the next major upgrades should be:

1. add queue durability, retries, and dead-letter handling for worker execution
2. deepen evidence lineage with multi-epoch comparison and baseline drift analysis
3. add storage-backed generated report artifacts and signed retrieval workflows
4. improve operational dashboards and alerting on stream stalls, worker failures, and degraded assessments
