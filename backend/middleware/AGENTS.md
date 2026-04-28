<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# middleware

## Purpose
FastAPI HTTP middleware — currently request logging with correlation IDs tied into the structured logging stack (Audit Rec #10).

## Key Files
| File | Description |
|------|-------------|
| `request_logging.py` | Attaches correlation ID, logs request/response metadata via structlog |
| `__init__.py` | Package exports |

## For AI Agents

### Working In This Directory
- Middleware runs on every request — keep it fast and allocation-light.
- Never log request/response bodies containing secrets or PII.
- Correlation ID must propagate into every structlog bind context.

### Testing Requirements
- Covered by integration smoke in `../tests/test_observability.py`.

## Dependencies

### Internal
- `../services/logging_config.py`, `../services/observability_service.py`.

### External
- FastAPI middleware API, structlog.

<!-- MANUAL: -->
