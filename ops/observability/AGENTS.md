<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# observability

## Purpose
Full observability stack — OTel Collector at the front, Prometheus for metrics, Grafana for dashboards, Alertmanager for routing, Tempo for traces (Audit Rec #10).

## Key Files
| File | Description |
|------|-------------|
| `otel-collector-config.yaml` | OpenTelemetry Collector pipeline — receive OTLP, export to Prom + Tempo |
| `tempo.yaml` | Grafana Tempo config — trace ingest + storage |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `prometheus/` | Prometheus scrape + rules (see `prometheus/AGENTS.md`) |
| `grafana/` | Grafana dashboards + provisioning (see `grafana/AGENTS.md`) |
| `alertmanager/` | Alert routing config (see `alertmanager/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Metric names must match `backend/services/metrics_service.py` / `slo_service.py` emissions — do not invent names.
- Trace span names follow `backend/services/observability_service.py` conventions.
- Validate with each tool's linter before merging (`promtool check rules`, `amtool check-config`, etc.).

## Dependencies

### Internal
- Metric/trace contract owned by `backend/services/metrics_service.py`, `observability_service.py`, `slo_service.py`.

### External
- OpenTelemetry Collector, Prometheus, Grafana, Alertmanager, Tempo.

<!-- MANUAL: -->
