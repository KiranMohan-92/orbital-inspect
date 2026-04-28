<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# backend

## Purpose
Python/FastAPI service implementing the 5-agent satellite insurance underwriting pipeline. Owns the LLM orchestration (Gemini), public-data ingestion (TLE / ORDEM / SATNOGS / UCS / SpaceTrack / Space Weather), durable job execution, decision workflow, provenance, and evidence persistence. Exposes REST + SSE to the frontend and PDF/webhook outbound integrations.

## Key Files
| File | Description |
|------|-------------|
| `main.py` | FastAPI entrypoint — router mounting, middleware, lifespan |
| `config.py` | Pydantic settings (env, secrets, feature flags) |
| `requirements.txt` | Pinned Python dependencies |
| `alembic.ini` | Alembic migration config |
| `pytest.ini` | Pytest markers, paths, coverage config |
| `Dockerfile` | Production container image |
| `orbital_inspect.db` | SQLite dev DB (gitignored in prod workflows) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `agents/` | 5-agent pipeline + orchestrator (see `agents/AGENTS.md`) |
| `api/` | REST routers (see `api/AGENTS.md`) |
| `auth/` | JWT, RBAC, rate limiting (see `auth/AGENTS.md`) |
| `db/` | SQLAlchemy models + repository (see `db/AGENTS.md`) |
| `middleware/` | Request logging, correlation IDs (see `middleware/AGENTS.md`) |
| `models/` | Pydantic data contracts (see `models/AGENTS.md`) |
| `services/` | ~40 domain services — LLM, public data, telemetry, decisions, resilience (see `services/AGENTS.md`) |
| `workers/` | Durable background workers (see `workers/AGENTS.md`) |
| `scripts/` | Maintenance/codegen scripts — OpenAPI export, type sync, seeds (see `scripts/AGENTS.md`) |
| `tests/` | Pytest suites (see `tests/AGENTS.md`) |
| `alembic/` | Database migrations (see `alembic/AGENTS.md`) |
| `prompts/` | Per-agent LLM prompt templates (see `prompts/AGENTS.md`) |
| `templates/` | Jinja HTML templates (PDF report) — single file |
| `data/` | Runtime storage, demo cache, uploads, ORDEM tables (not documented) |
| `utils/` | Shared utilities (currently minimal) |

## For AI Agents

### Working In This Directory
- **Never bypass `resilient_call()`** for agent invocations — it provides timeout, retry, and circuit breaker per Audit Rec #3.
- **Never weaken** the fail-closed classification rejection in the orchestrator.
- **Never** add an agent without registering it in `AGENT_ORDER` in `agents/orchestrator.py`.
- Agent error handlers must return `degraded=True`, never silently succeed.
- Evidence gaps must force `FURTHER_INVESTIGATION` recommendation — do not mask them.
- LLM output handling changes (`services/gemini_service.py`, `parse_json_response`, agent error paths) trigger cross-model review.

### Testing Requirements
- `cd backend && pytest` runs the full suite.
- Add a unit/integration test under `tests/` for every new service or agent, including the degraded path.
- Offline eval: `pytest tests/test_offline_eval.py` for regression/eval harness (Audit Rec #20).

### Common Patterns
- `async`/`await` for I/O, `structlog` for logging, Pydantic for all data contracts.
- Repository pattern — business logic in `services/`, SQL isolated in `db/repository.py`.

## Dependencies

### Internal
- Frontend consumes generated types from `scripts/generate_types.py` (Audit Rec #9).

### External
- FastAPI, Uvicorn, SQLAlchemy, Alembic, Pydantic, structlog.
- Redis (queue + rate limit), Postgres (prod) / SQLite (dev).
- Google Gemini via `google-genai` / ADK.

<!-- MANUAL: -->
