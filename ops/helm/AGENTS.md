<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# helm

## Purpose
Helm chart packaging for Kubernetes deploys of the orbital-inspect stack.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `orbital-inspect/` | The chart itself — `Chart.yaml`, `values.yaml`, `templates/` (see `orbital-inspect/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Bump the chart version in `orbital-inspect/Chart.yaml` whenever templates or default values change.
- Validate locally: `helm lint orbital-inspect && helm template orbital-inspect`.

<!-- MANUAL: -->
