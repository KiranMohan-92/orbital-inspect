<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# analysis

## Purpose
UI for the single-analysis flow — satellite input, demo selection, live agent feed (SSE), vision overlay, evidence viewer (Audit Rec #18), insurance risk card, and the final intelligence report.

## Key Files
| File | Description |
|------|-------------|
| `AnalysisMode.tsx` | Shell / orchestrator for the analysis flow |
| `SatelliteInput.tsx` | Target satellite input form |
| `DemoSelector.tsx` | Picker for preset demo scenarios |
| `AgentFeed.tsx` | Live SSE feed — per-stage events, degraded indicators |
| `VisualAnalysis.tsx` | Vision analysis panel with image + overlay |
| `BoundingBoxOverlay.tsx` | Bounding-box overlay layer on vision evidence |
| `DamageDetailPopover.tsx` | Drill-down popover for damage evidence |
| `EvidenceViewer.tsx` | Zoomable multi-evidence viewer (Audit Rec #18) |
| `InsuranceRiskCard.tsx` | Insurance risk matrix + recommendation card |
| `IntelligenceReport.tsx` | Final report view + PDF export trigger |

## For AI Agents

### Working In This Directory
- SSE consumption must go through `../../hooks/useSSE.ts` and `useAnalysisState.ts` — do not open `EventSource` directly.
- Degraded states must be visually surfaced — never mask a degraded stage as successful.
- Evidence viewer expects the bounding-box schema from `backend/models/evidence.py`; regen types after backend changes.

### Testing Requirements
- Covered end-to-end by `../../../e2e/analysis-flow.spec.ts`; add Vitest unit tests for pure components.

## Dependencies

### Internal
- `../../hooks/useSSE.ts`, `../../hooks/useAnalysisState.ts`, `../../utils/api.ts`, `../viz/*`.

<!-- MANUAL: -->
