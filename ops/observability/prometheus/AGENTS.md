<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# prometheus

## Purpose
Prometheus configuration — scrape targets and alerting/recording rules. Scrape paths target the `/metrics` endpoint served by the backend and the OTel Collector's Prometheus exporter.

## For AI Agents

### Working In This Directory
- Validate rules with `promtool check rules <file>` before committing.
- Recording rules should pre-aggregate panels used by `../grafana/dashboards/` to keep Grafana responsive.
- Alert expressions must reference metrics that exist in `backend/services/metrics_service.py`.

## Dependencies

### Internal
- Scrapes `backend/services/metrics_service.py` endpoints; alerts route to `../alertmanager/`.

### External
- Prometheus.

<!-- MANUAL: -->
