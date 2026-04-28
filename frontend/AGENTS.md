<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# frontend

## Purpose
React + Vite + TypeScript + Tailwind UI for Orbital Inspect. Surfaces the 5-agent analysis pipeline as a live feed (SSE), a multi-evidence viewer, insurance risk cards, a portfolio/fleet view, and visualization primitives (3D viewer, degradation timeline, trend chart, risk matrix drilldown). Strict TS — no `any`.

## Key Files
| File | Description |
|------|-------------|
| `package.json` | Dependencies + scripts (`dev`, `build`, `test`, `test:e2e`) |
| `vite.config.ts` | Vite dev server + build config |
| `vitest.config.ts` | Unit test runner config |
| `playwright.config.ts` | E2E test runner config |
| `tsconfig.json` | TypeScript strict-mode config |
| `tailwind.config.js` | Tailwind theme + content globs |
| `postcss.config.js` | PostCSS pipeline |
| `index.html` | Vite HTML entry |
| `Dockerfile` | Production container (nginx-served static build) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `src/` | Application source (see `src/AGENTS.md`) |
| `e2e/` | Playwright specs + backend helper scripts (see `e2e/AGENTS.md`) |
| `public/` | Static assets + demo image copies |
| `dist/` | Build output (gitignored) |
| `playwright-report/`, `test-results/` | Test artifacts (gitignored) |

## For AI Agents

### Working In This Directory
- **No `any` types** — use `unknown` + narrowing or generate types via `backend/scripts/generate_types.py`.
- Use Tailwind utility classes for styling; do not introduce a second styling system.
- Regenerate `src/generated-types.ts` from the backend OpenAPI schema after backend contract changes.

### Testing Requirements
- Unit: `npm run test` (Vitest).
- E2E: `npx playwright test` — requires backend running (see `e2e/run-backend-e2e.sh`).
- Smoke: `src/smoke.test.ts` must stay green.

### Common Patterns
- Feature-folder components (`components/{analysis,portfolio,viz,report}`), shared `ErrorBoundary.tsx`.
- Server state via SSE hook (`hooks/useSSE.ts`), analysis state via `hooks/useAnalysisState.ts`.
- API wrapper in `src/utils/api.ts` with matching test.

## Dependencies

### Internal
- Consumes REST + SSE from `backend/api/` and types from `backend/scripts/generate_types.py`.

### External
- React 18, Vite, TypeScript, Tailwind, Vitest, Playwright.
- Visualization libs for 3D viewer, charts, heatmaps (see `src/components/viz/`).

<!-- MANUAL: -->
