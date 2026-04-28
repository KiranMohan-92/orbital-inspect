<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# grafana

## Purpose
Grafana dashboards and provisioning configuration. Dashboards visualize the metrics emitted by `backend/services/metrics_service.py` / `slo_service.py` and traces stored in Tempo.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `dashboards/` | Dashboard JSON exports |
| `provisioning/` | Provisioning configs for dashboards + datasources |

## For AI Agents

### Working In This Directory
- Dashboard panels must reference metrics that actually exist in `backend/services/metrics_service.py` — do not invent names.
- Export dashboards via Grafana UI → "Share → Export for sharing externally", then commit the JSON.
- Datasources are provisioned, not hand-created — edit `provisioning/datasources/`.

## Dependencies

### Internal
- Metric contract owned by `backend/services/metrics_service.py`, `observability_service.py`, `slo_service.py`.

### External
- Grafana, Tempo, Prometheus.

<!-- MANUAL: -->
