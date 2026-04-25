<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# workers

## Purpose
Durable background workers (Audit Rec #1) — consume the Redis queue, run the 5-agent pipeline via the orchestrator, persist analyses/events/outputs, and emit SSE.

## Key Files
| File | Description |
|------|-------------|
| `analysis_worker.py` | Consumes queued analysis jobs, drives `../agents/orchestrator.py`, persists via `../db/repository.py`, emits via `../services/sse_service.py` |
| `__init__.py` | Package exports |

## For AI Agents

### Working In This Directory
- Workers must be idempotent — duplicate deliveries are expected.
- Every step that can fail goes through `../services/resilience.resilient_call()`.
- On terminal failure: persist a degraded analysis + event, do not silently drop.
- Metrics + traces from workers land in the observability stack; use `../services/observability_service.py` / `metrics_service.py`.

### Testing Requirements
- `../tests/test_e2e.py` and `../tests/test_production_controls.py` exercise the worker path.

## Dependencies

### Internal
- `../agents/orchestrator.py`, `../services/queue_service.py`, `../services/sse_service.py`, `../db/repository.py`.

### External
- Redis, structlog.

<!-- MANUAL: -->
