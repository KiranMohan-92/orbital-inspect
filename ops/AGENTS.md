<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# ops

## Purpose
Production operations umbrella — Helm chart for Kubernetes deploys, a full observability stack (OpenTelemetry collector, Prometheus, Grafana, Alertmanager, Tempo), runbooks, architecture notes, and smoke-test scripts. Not consumed at runtime by the application; used by operators during deploy and incident response.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `architecture/` | Long-form architecture docs — `MULTI_REGION.md` (see `architecture/AGENTS.md`) |
| `helm/` | Helm chart for `orbital-inspect` (see `helm/AGENTS.md`) |
| `observability/` | OTel collector, Prometheus, Grafana, Alertmanager, Tempo configs (see `observability/AGENTS.md`) |
| `runbook/` | Operator runbooks — `DEPLOYMENT.md` (see `runbook/AGENTS.md`) |
| `scripts/` | Ops scripts — `smoke_test.sh` (see `scripts/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Changes here do not ship with the runtime image; they affect deploy and monitoring.
- Always bump the Helm chart version in `helm/orbital-inspect/Chart.yaml` when templates change.
- Dashboards and alerts should reference metrics emitted by `backend/services/metrics_service.py` / `observability_service.py` — do not invent metric names.

### Testing Requirements
- Helm: `helm lint ops/helm/orbital-inspect && helm template ops/helm/orbital-inspect`.
- Smoke: `bash ops/scripts/smoke_test.sh`.
- Grafana/Prometheus configs: validate with their respective linters before merging.

## Dependencies

### Internal
- Metrics/traces contract is owned by `backend/services/metrics_service.py`, `observability_service.py`, `slo_service.py`, `logging_config.py`.

### External
- Kubernetes, Helm, OpenTelemetry Collector, Prometheus, Grafana, Alertmanager, Tempo.

<!-- MANUAL: -->
