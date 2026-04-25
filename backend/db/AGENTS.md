<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# db

## Purpose
SQLAlchemy ORM layer — models, engine/session setup, and the repository facade used by services. Postgres in prod, SQLite in dev. All SQL lives here; services must not write raw queries.

## Key Files
| File | Description |
|------|-------------|
| `base.py` | Declarative base, engine, session factory, lifecycle |
| `models.py` | Core ORM models — analyses, events, outputs, evidence, users, orgs (Audit Rec #5) |
| `batch_models.py` | Batch-job ORM models |
| `repository.py` | Repository facade — all read/write helpers consumed by services |
| `__init__.py` | Package exports |

## For AI Agents

### Working In This Directory
- Schema changes trigger cross-model review per `CLAUDE.md`.
- Every schema change needs a matching Alembic migration in `../alembic/versions/`.
- Keep SQL in `repository.py`; services call repository functions, not SQLAlchemy sessions directly.
- Avoid full-table loads in hot paths — prior regression was the asset detail evidence load (see recent commit history).

### Testing Requirements
- `../tests/test_models.py`, `../tests/test_evidence_repository.py`, `../tests/test_migrations.py` must pass.

## Dependencies

### Internal
- `../alembic/` (migrations), `../models/` (Pydantic DTOs that cross the API boundary).

### External
- SQLAlchemy, Alembic, asyncpg (prod), aiosqlite (dev).

<!-- MANUAL: -->
