<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# docs

## Purpose
Human-facing documentation outside the `README.md` — currently the demo runbook and captured demo assets used in presentations and QA.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `demo/` | Demo runbook + captured screenshots/assets (see `demo/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Narrative docs only. Do not stash code, configs, or schemas here — use `backend/`, `frontend/`, or `ops/`.
- Demo assets should be regenerated via `frontend/e2e/demo-assets.capture.spec.ts` rather than hand-edited.

## Dependencies

### Internal
- `frontend/e2e/demo-assets.capture.spec.ts` produces artifacts consumed here.

<!-- MANUAL: -->
