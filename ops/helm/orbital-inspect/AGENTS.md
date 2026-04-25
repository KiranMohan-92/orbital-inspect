<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# orbital-inspect (chart)

## Purpose
Helm chart for the orbital-inspect Kubernetes deployment.

## Key Files
| File | Description |
|------|-------------|
| `Chart.yaml` | Chart metadata + version (bump on every template change) |
| `values.yaml` | Default values — image tags, resources, replicas, env |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `templates/` | Kubernetes manifest templates (see `templates/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Bump `Chart.yaml` `version` on every templates or values change.
- Never bake secrets into `values.yaml` — use `external-secrets` / `SealedSecret` / a values override.
- Validate: `helm lint . && helm template . -f values.yaml`.

<!-- MANUAL: -->
