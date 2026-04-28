<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# api

## Purpose
FastAPI routers for the REST surface. Each file owns one resource family and delegates to `../services/` for business logic. SSE is handled via `../services/sse_service.py`; errors use the shared envelope in `error_envelope.py`. The `v1/` namespace is the versioned contract stub (Audit Rec #7).

## Key Files
| File | Description |
|------|-------------|
| `admin.py` | Admin endpoints — readiness, feature flags, retention |
| `assets.py` | Asset/satellite detail — report summaries, evidence |
| `batch.py` | Batch job submit/status |
| `datasets.py` | Benchmark + public dataset registry |
| `decisions.py` | Decision workflow — review, approval, policy |
| `portfolio.py` | Fleet/portfolio-level endpoints (Audit Rec #14) |
| `precedents.py` | Precedents + claims knowledge base (Audit Rec #15) |
| `reports.py` | Per-analysis report fetch + SSE subscription |
| `trends.py` | Time-series trends for risk/degradation |
| `webhooks.py` | Inbound webhook receivers (Audit Rec #16) |
| `error_envelope.py` | Shared error schema + exception handlers |
| `v1/` | Versioned namespace stub |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `v1/` | Future versioned router namespace (empty beyond `__init__.py` today) |

## For AI Agents

### Working In This Directory
- Routers are thin — put business logic in `../services/` and data access in `../db/repository.py`.
- Use `error_envelope.py` for all raised API errors; do not bypass it.
- Any route that streams events must go through `../services/sse_service.py` (versioned SSE contract, Audit Rec #7+8).
- Auth: protect routes via `Depends(get_current_user)` from `../auth/dependencies.py`.
- Register new routers in `../main.py` — forgetting this was an audited gap.

### Testing Requirements
- Add an API test in `../tests/` (e.g. `test_reports_api.py`, `test_decisions_api.py`, `test_assets_api.py`).

## Dependencies

### Internal
- `../services/*`, `../auth/`, `../db/repository.py`, `../models/`.

<!-- MANUAL: -->
