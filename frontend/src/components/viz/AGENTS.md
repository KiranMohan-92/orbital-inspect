<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# viz

## Purpose
Visualization primitives reused across analysis and portfolio views — 3D satellite viewer, degradation timelines, trend charts, and a drillable risk matrix (Audit Recs #18, #19).

## Key Files
| File | Description |
|------|-------------|
| `SatelliteViewer3D.tsx` | 3D satellite viewer (Audit Rec #19) |
| `DegradationTimeline.tsx` | Time-series degradation timeline (Audit Rec #19) |
| `TrendChart.tsx` | Generic trend chart with regression line |
| `RiskMatrixDrilldown.tsx` | Clickable risk matrix with drill-down |
| `index.tsx` | Barrel export |

## For AI Agents

### Working In This Directory
- Keep components presentational — data wiring belongs in `analysis/` and `portfolio/`.
- Memoize expensive renders; 3D viewer is GPU-sensitive, don't remount on prop churn.
- Export everything through `index.tsx` for stable imports.

### Testing Requirements
- Visual / snapshot tests where stable; prefer Vitest unit tests for data transforms.

## Dependencies

### External
- Three.js (or react-three-fiber) for 3D, a charting lib for timelines/trends.

<!-- MANUAL: -->
