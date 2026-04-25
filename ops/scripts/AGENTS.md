<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# scripts

## Purpose
Operational scripts run from operator workstations or CI — not shipped in the runtime image.

## Key Files
| File | Description |
|------|-------------|
| `smoke_test.sh` | Post-deploy smoke test — hit key endpoints, verify SSE, confirm health |

## For AI Agents

### Working In This Directory
- Scripts must be idempotent and safe to re-run.
- Exit with a non-zero code on any smoke failure; surface the failing endpoint in stderr.

<!-- MANUAL: -->
