<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# components

## Purpose
Feature-folder React components. Each top-level folder owns one product surface (analysis, portfolio, viz, report). Shared primitives live at this root.

## Key Files
| File | Description |
|------|-------------|
| `ErrorBoundary.tsx` | App-wide error boundary — catches render errors and surfaces a recoverable UI |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `analysis/` | Analysis mode UI — live agent feed, evidence viewer, risk card (see `analysis/AGENTS.md`) |
| `portfolio/` | Fleet/portfolio view — summary, heat map, cards (see `portfolio/AGENTS.md`) |
| `viz/` | Visualization primitives — 3D, timeline, charts, matrix (see `viz/AGENTS.md`) |
| `report/` | Reserved for report-specific components (empty placeholder today) |

## For AI Agents

### Working In This Directory
- One feature surface per folder. Components shared across ≥2 features stay at this root.
- Props interfaces defined above the component; prefer named exports.
- Tailwind for all styling; no CSS modules, no styled-components.

### Testing Requirements
- Vitest unit tests colocated next to components, or in a sibling `__tests__/` dir (see `../hooks/__tests__/`).

## Dependencies

### Internal
- `../hooks/*`, `../utils/api.ts`, `../generated-types.ts`.

<!-- MANUAL: -->
