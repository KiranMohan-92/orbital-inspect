<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# agents

## Purpose
The 5-agent pipeline and its orchestrator. Each agent wraps a Gemini LLM call against its prompt template in `../prompts/`, parses the JSON response, and emits evidence + a stage verdict. The orchestrator enforces `AGENT_ORDER`, fails closed on classification rejection, propagates degraded state, and blocks downstream stages when upstream evidence is missing (Audit Rec #4).

## Key Files
| File | Description |
|------|-------------|
| `orbital_classification_agent.py` | Stage 1 — classify whether target is a satellite (fail-closed on rejection) |
| `satellite_vision_agent.py` | Stage 2 — vision analysis with bounding-box evidence |
| `orbital_environment_agent.py` | Stage 3 — environment risks (debris, weather, conjunctions) |
| `satellite_failure_mode_agent.py` | Stage 4 — probable failure modes and degradation |
| `insurance_risk_agent.py` | Stage 5 — insurance risk matrix + underwriting recommendation |
| `orchestrator.py` | Pipeline driver — `AGENT_ORDER`, resilient_call, SSE emission, degraded propagation |
| `__init__.py` | Package exports |

## For AI Agents

### Working In This Directory
- **Never** add an agent without registering it in `AGENT_ORDER` in `orchestrator.py`.
- Every agent must return `degraded=True` on error — never silently succeed.
- LLM output handling goes through `services/gemini_service.py` (`parse_json_response`); do not parse JSON ad-hoc.
- The classification rejection is fail-closed: if stage 1 rejects, downstream stages must not run.
- Evidence gaps must force `FURTHER_INVESTIGATION` in the final recommendation — do not backfill with defaults.
- Changes here trigger cross-model review (pipeline changes + LLM output handling per `CLAUDE.md`).

### Testing Requirements
- Add a test in `../tests/` for every new agent covering both happy path and degraded path.
- Consistency contracts live in `test_insurance_consistency.py`; extend there when changing risk logic.

### Common Patterns
- One agent per file, instantiated at module import, invoked via `resilient_call(agent, ...)`.
- Prompts are loaded from `../prompts/<agent>_prompt.txt` at construction.

## Dependencies

### Internal
- `../prompts/` (LLM prompt templates), `../services/gemini_service.py` (LLM client + JSON parsing), `../services/resilience.py` (timeout / retry / circuit breaker), `../models/` (Pydantic contracts for evidence + events).

<!-- MANUAL: -->
