<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# tests

## Purpose
Pytest test suite for the backend. Covers API routers, domain services, the 5-agent pipeline, durable workers, resilience, auth, storage, observability, and a regression/eval harness (Audit Rec #20).

## Key Files (grouped)

### Framework
| File | Description |
|------|-------------|
| `conftest.py` | Fixtures — DB, client, auth, LLM stubs, event capture |

### API
| File | Description |
|------|-------------|
| `test_assets_api.py`, `test_decisions_api.py`, `test_reports_api.py` | Router integration tests |

### Agents + pipeline
| File | Description |
|------|-------------|
| `test_e2e.py` | End-to-end pipeline happy path |
| `test_insurance_consistency.py` | Risk-matrix + recommendation consistency contracts |
| `test_production_controls.py` | Fail-closed + degraded-state controls |
| `test_offline_eval.py` | Regression/eval harness against golden fixtures |

### Services
| File | Description |
|------|-------------|
| `test_gemini_service.py` | LLM client + JSON parse (cross-model review area) |
| `test_public_data_services.py` | ORDEM / SATNOGS / TLE / UCS / weather |
| `test_ordem_service.py` | ORDEM-specific coverage |
| `test_resilience.py` | Timeout / retry / circuit breaker |
| `test_decision_policy.py`, `test_sensitivity.py` | Decision workflow + sensitivity ±2 range |
| `test_telemetry_services.py`, `test_observability.py` | Metrics + tracing |
| `test_pdf_report_service.py` | PDF rendering |
| `test_storage_service.py` | Object storage abstraction |
| `test_evidence.py`, `test_evidence_repository.py` | Evidence + repository |
| `test_provenance.py` | Provenance field completeness |
| `test_reference_profile_integration.py` | Reference profile integration |
| `test_webhook_security.py` | Webhook signing / replay protection |

### Auth + DB
| File | Description |
|------|-------------|
| `test_auth.py`, `test_auth_e2e.py` | JWT, RBAC, rate limit |
| `test_models.py` | ORM model sanity |
| `test_migrations.py` | Alembic migration apply/rollback |

## For AI Agents

### Working In This Directory
- Every new agent / service / router gets a matching test.
- Always cover the degraded path for agents/services — not just the happy path.
- LLM calls in tests go through stubs (`e2e_stub_service.py` or fixtures in `conftest.py`); no real Gemini calls in unit tests.
- `test_reports_api.py` previously hung — watch for async fixture leaks when editing.

### Testing Requirements
- Full run: `cd backend && pytest`.
- Coverage expectation: add coverage for every new code path.

### Common Patterns
- Async tests via `pytest-asyncio`, fixtures in `conftest.py`, FastAPI `TestClient` for API tests.

## Dependencies

### Internal
- All backend packages. Tests MUST use the fixtures in `conftest.py` rather than constructing their own engines/sessions.

### External
- pytest, pytest-asyncio, httpx, faker.

<!-- MANUAL: -->
