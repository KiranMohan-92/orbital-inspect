<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# auth

## Purpose
JWT-based authentication, org-scoped RBAC, and rate limiting (Audit Rec #6). Exposes FastAPI `Depends(...)` helpers consumed by `../api/` routers.

## Key Files
| File | Description |
|------|-------------|
| `jwt_service.py` | JWT issuance, validation, claim extraction |
| `dependencies.py` | FastAPI dependency helpers — `get_current_user`, role guards |
| `rate_limiter.py` | Per-user / per-IP rate limiting (works with `services/distributed_rate_limiter.py`) |
| `__init__.py` | Package exports |

## For AI Agents

### Working In This Directory
- Auth changes trigger cross-model review (security gate per `CLAUDE.md`).
- Never log JWT contents or raw secrets — `structlog` redaction must be applied.
- Tenant/org isolation is enforced here; do not push that logic into routers or services.

### Testing Requirements
- `../tests/test_auth.py` and `../tests/test_auth_e2e.py` must pass.
- Add a negative test for every new permission (denied path).

## Dependencies

### Internal
- `../services/distributed_rate_limiter.py` (Redis-backed sliding window), `../db/` for user/org lookups.

### External
- `python-jose` / `PyJWT` for JWT, `passlib` for hashing.

<!-- MANUAL: -->
