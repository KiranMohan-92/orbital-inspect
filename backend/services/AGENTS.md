<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# services

## Purpose
Domain service layer — ~40 focused modules that encapsulate LLM calls, public-data ingestion, telemetry, decision workflow, outbound integrations, and cross-cutting resilience. Routers in `../api/` are thin; workers in `../workers/` are drivers; services are where business logic lives.

## Key Files (grouped by theme)

### LLM
| File | Description |
|------|-------------|
| `gemini_service.py` | Gemini client — prompt dispatch, `parse_json_response`, retries (LLM output handling, cross-model review gate) |

### Public / reference data
| File | Description |
|------|-------------|
| `celestrak_service.py` | TLE fetch from Celestrak |
| `space_track_service.py` | Space-Track.org TLE/catalogue |
| `satnogs_service.py` | SATNOGS telemetry data |
| `ucs_service.py` | UCS Satellite Database |
| `ordem_service.py` | NASA ORDEM debris model (tables in `../data/ordem_tables/`) |
| `tle_history_service.py` | TLE history lookup |
| `space_weather_service.py` | Space weather indices |
| `enhanced_weather_service.py` | Enriched weather signals |
| `conjunction_service.py` | Conjunction / close-approach analysis |
| `dataset_registry_service.py` | Registry of benchmark + public datasets |

### Resilience + orchestration
| File | Description |
|------|-------------|
| `resilience.py` | `resilient_call()` — timeout, retry, circuit breaker (Audit Rec #3 — DO NOT BYPASS) |
| `queue_service.py` | Redis-backed job queue for durable jobs |
| `cache_service.py` | Shared cache helpers |
| `distributed_rate_limiter.py` | Distributed rate limiter (works with `../auth/rate_limiter.py`) |
| `feature_flag_service.py` | Feature flag evaluation |
| `secret_service.py` | Secret retrieval / rotation |

### Telemetry + observability
| File | Description |
|------|-------------|
| `observability_service.py` | OpenTelemetry tracing bootstrap |
| `metrics_service.py` | Prometheus metrics registration and emission |
| `slo_service.py` | SLO measurements + error-budget accounting |
| `logging_config.py` | structlog configuration |
| `cost_tracker.py` | LLM cost + token accounting |
| `readiness_service.py` | Readiness/liveness probes |

### Decision workflow
| File | Description |
|------|-------------|
| `decision_policy_service.py` | Policy engine for underwriting decisions |
| `sensitivity_service.py` | Sensitivity analysis for risk scoring (range ±2 post-fix) |
| `governance_service.py` | Approval + audit trail for decisions |
| `post_analysis_service.py` | Post-pipeline enrichment |

### Evidence + fleet
| File | Description |
|------|-------------|
| `evidence_service.py` | Evidence aggregation + retrieval |
| `evidence_ingest_service.py` | Evidence ingestion pipeline |
| `fleet_ingestion_service.py` | Fleet/portfolio ingestion (Audit Rec #14) |
| `fleet_summary_service.py` | Fleet aggregate summaries |
| `batch_service.py` | Batch-job lifecycle |
| `trend_analysis_service.py` | Trend computation for degradation over time |
| `classification_marking_service.py` | Classification markings on reports |
| `retention_service.py` | Data retention / TTL enforcement |

### Output + integrations
| File | Description |
|------|-------------|
| `sse_service.py` | SSE emission (versioned contract, Audit Rec #7+8) |
| `pdf_report_service.py` | Server-side PDF generation (Audit Rec #12) |
| `chart_renderer.py` | Server-side chart rendering for PDF |
| `image_annotator.py` | Evidence image annotation (bounding boxes) |
| `storage_service.py` | Object storage abstraction |
| `webhook_service.py` | Outbound webhook dispatch (Audit Rec #16) |
| `alert_service.py` | Alerting pipeline for ops |
| `e2e_stub_service.py` | Deterministic stubs for E2E testing |

## For AI Agents

### Working In This Directory
- **Never bypass `resilience.resilient_call()`** for agent/external calls.
- **LLM output handling changes** (`gemini_service.py`) trigger cross-model review.
- Every new service gets: type hints, structlog logger, unit test in `../tests/`, and entry here.
- Services call `../db/repository.py` — not SQLAlchemy sessions directly.
- Metric/trace names must match what `ops/observability/` configs expect.

### Testing Requirements
- Each theme has its test file: `test_gemini_service.py`, `test_public_data_services.py`, `test_resilience.py`, `test_telemetry_services.py`, `test_ordem_service.py`, `test_decision_policy.py`, `test_sensitivity.py`, `test_evidence.py`, `test_storage_service.py`, `test_pdf_report_service.py`, `test_webhook_security.py`, `test_observability.py`, `test_reference_profile_integration.py`.
- Offline eval: `test_offline_eval.py` (Audit Rec #20).

### Common Patterns
- Async functions, explicit return types, structlog logger at module top.
- Secrets via `secret_service.py`, feature flags via `feature_flag_service.py` — no hardcoded toggles.

## Dependencies

### Internal
- `../agents/`, `../api/`, `../db/repository.py`, `../models/`, `../workers/`.

### External
- google-genai / ADK (Gemini), redis, prometheus_client, opentelemetry, reportlab or weasyprint (PDF), httpx.

<!-- MANUAL: -->
