<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# e2e

## Purpose
Playwright E2E tests and the helper script for spinning up the backend in CI. Exercises the analysis flow end-to-end against deterministic stubs (`backend/services/e2e_stub_service.py`) and captures demo assets for the `docs/demo/` runbook.

## Key Files
| File | Description |
|------|-------------|
| `analysis-flow.spec.ts` | Happy-path analysis flow — submit, watch SSE feed, assert report |
| `demo-assets.capture.spec.ts` | Captures screenshots used in `docs/demo/assets/` |
| `global-setup.ts` | Playwright global setup — auth seed, feature-flag priming |
| `run-backend-e2e.sh` | Starts backend (in stub mode) before Playwright runs |

## For AI Agents

### Working In This Directory
- Use deterministic stubs (`e2e_stub_service.py` on the backend) — never hit real Gemini from E2E.
- Demo-asset capture must run in a stable viewport; don't change dimensions without updating `docs/demo/`.
- Prefer data-testid selectors over CSS/text selectors for stability.

### Testing Requirements
- `npx playwright test` — requires backend up per `run-backend-e2e.sh`.

## Dependencies

### Internal
- `backend/services/e2e_stub_service.py` for deterministic pipeline outputs.

### External
- Playwright.

<!-- MANUAL: -->
