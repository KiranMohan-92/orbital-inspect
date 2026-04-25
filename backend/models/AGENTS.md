<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# models

## Purpose
Pydantic data contracts that cross the API and inter-service boundaries. Distinct from `../db/models.py`, which holds ORM entities — these are DTOs/events/value objects.

## Key Files
| File | Description |
|------|-------------|
| `events.py` | SSE event schemas (versioned, Audit Rec #7) |
| `evidence.py` | Evidence + bounding-box schemas shared by vision + report |
| `provenance.py` | Provenance fields — source, confidence, timestamp, method |
| `satellite.py` | Satellite identity + catalogue fields |
| `__init__.py` | Package exports |

## For AI Agents

### Working In This Directory
- Changes here propagate to the frontend via `../scripts/generate_types.py` (Audit Rec #9). Regenerate types after every change.
- SSE event schema changes must be versioned — do not rename fields in place.
- Provenance: all fields listed in the schema are mandatory; prior bug was truthiness-vs-`is not None` (0.0 was silently dropped).

### Testing Requirements
- `../tests/test_provenance.py` enforces completeness; extend when adding fields.

## Dependencies

### Internal
- Consumed by `../agents/`, `../services/`, `../api/`, and (via generated types) the frontend.

<!-- MANUAL: -->
