<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# src

## Purpose
Frontend application source. Contains the entry components, generated backend types, hand-written domain types, feature-folder components, SSE + state hooks, API wrapper utils, and telemetry.

## Key Files
| File | Description |
|------|-------------|
| `App.tsx` | Root component — routing + global layout |
| `main.tsx` | React root mount + providers |
| `index.css` | Global Tailwind entry + base styles |
| `generated-types.ts` | Auto-generated from backend OpenAPI (via `backend/scripts/generate_types.py`) — DO NOT hand-edit |
| `types.ts` | Hand-written domain types (frontend-only) |
| `smoke.test.ts` | Vitest smoke — must always stay green |
| `test-setup.ts` | Vitest setup (globals, matchers) |
| `vite-env.d.ts` | Vite type declarations |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `components/` | Feature-folder React components (see `components/AGENTS.md`) |
| `hooks/` | Custom hooks — `useSSE`, `useAnalysisState` (see `hooks/AGENTS.md`) |
| `utils/` | API wrapper + helpers (see `utils/AGENTS.md`) |
| `services/` | Telemetry client (single file `telemetry.ts`) — not documented separately |
| `store/` | Reserved for global state; currently empty |

## For AI Agents

### Working In This Directory
- **Never hand-edit `generated-types.ts`** — regenerate via `backend/scripts/generate_types.py`.
- Strict TS — no `any`; use `unknown` + narrowing.
- Feature components go in `components/<feature>/`; shared primitives stay at `components/` root (e.g. `ErrorBoundary.tsx`).
- SSE consumption goes through `hooks/useSSE.ts`; state derived from events goes through `hooks/useAnalysisState.ts`.

### Testing Requirements
- Vitest unit tests colocated (e.g. `api.test.ts`, `useSSE.test.ts`) or under `__tests__/` subdir.
- `smoke.test.ts` is a must-pass regression gate.

## Dependencies

### Internal
- Consumes `backend/api/` via `utils/api.ts` + SSE.

### External
- React 18, Vite client, Vitest.

<!-- MANUAL: -->
