<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# templates

## Purpose
Kubernetes manifest templates rendered by Helm. Consumes values from `../values.yaml` and produces Deployments, Services, ConfigMaps, Secrets, Ingresses, and ServiceMonitors as appropriate.

## For AI Agents

### Working In This Directory
- Keep label selectors stable across releases — changing them is a breaking change for rolling updates.
- Probes (liveness/readiness) must hit endpoints owned by `backend/services/readiness_service.py`.
- ServiceMonitor scrape paths must match Prometheus config in `../../../observability/prometheus/`.
- Every template change → bump `../Chart.yaml` version.

### Testing Requirements
- `helm template ..` must render cleanly for every environment in `../../../runbook/DEPLOYMENT.md`.

<!-- MANUAL: -->
