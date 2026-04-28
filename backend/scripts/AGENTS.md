<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# scripts

## Purpose
Backend maintenance and codegen scripts — schema snapshotting, type sync with the frontend, data backfills, and benchmark seeding. Run manually or via CI; not executed at runtime.

## Key Files
| File | Description |
|------|-------------|
| `export_openapi.py` | Dumps FastAPI OpenAPI schema to disk |
| `generate_types.py` | Generates `frontend/src/generated-types.ts` from OpenAPI (Audit Rec #9) |
| `backfill_decisions.py` | Backfills decision records for legacy analyses |
| `seed_benchmark_datasets.py` | Seeds the benchmark/eval dataset registry |

## For AI Agents

### Working In This Directory
- `generate_types.py` is the contract bridge to the frontend — run it after any `../models/` or `../api/` schema change.
- Scripts should be idempotent and safe to re-run; log what they skipped vs applied.
- Do not import FastAPI app globals if the script can work with bare SQLAlchemy sessions.

### Testing Requirements
- Exercised implicitly by integration tests; no dedicated test file today.

## Dependencies

### Internal
- `../main.py` (for OpenAPI), `../db/`, `../models/`.

<!-- MANUAL: -->
