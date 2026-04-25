<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# portfolio

## Purpose
Fleet/portfolio and constellation monitoring UI (Audit Rec #14). Aggregates many analyses into fleet-level views — summaries, a geographic health map, a risk heat map, and individual satellite cards.

## Key Files
| File | Description |
|------|-------------|
| `PortfolioView.tsx` | Top-level portfolio page composition |
| `FleetSummary.tsx` | Aggregate counts, status distribution, SLAs |
| `FleetHealthMap.tsx` | Geographic / orbital health map |
| `RiskHeatmap.tsx` | Risk matrix heat map across fleet |
| `SatelliteCard.tsx` | Per-satellite summary card |

## For AI Agents

### Working In This Directory
- Data comes from `backend/api/portfolio.py` and `fleet_*_service.py`; do not fan out to per-satellite endpoints for aggregates.
- Heavy lists must virtualize — fleets can be hundreds of satellites.

### Testing Requirements
- Add Vitest unit tests for pure visualization logic; rely on E2E for integration.

## Dependencies

### Internal
- `../../utils/api.ts`, `../../generated-types.ts`, `../viz/*`.

<!-- MANUAL: -->
