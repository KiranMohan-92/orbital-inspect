<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# prompts

## Purpose
LLM prompt templates — one per pipeline agent. Each file is plain text, loaded by its agent at construction, and formatted with runtime context before being sent to Gemini.

## Key Files
| File | Description |
|------|-------------|
| `orbital_classification_prompt.txt` | Stage 1 — classify target as satellite (drives fail-closed rejection) |
| `satellite_vision_prompt.txt` | Stage 2 — vision analysis with bounding boxes |
| `orbital_environment_prompt.txt` | Stage 3 — environment risks |
| `satellite_failure_mode_prompt.txt` | Stage 4 — probable failure modes |
| `insurance_risk_prompt.txt` | Stage 5 — risk matrix + underwriting recommendation |

## For AI Agents

### Working In This Directory
- **Editing a prompt is LLM output handling** — triggers cross-model review per `CLAUDE.md`.
- The JSON schema expected back from each prompt is contracted with the matching agent in `../agents/` and parsed via `../services/gemini_service.py:parse_json_response`. Change one side → update all three.
- Run `../tests/test_offline_eval.py` after any prompt change to catch regressions.
- Never remove the explicit "return JSON only" guard — silent natural-language returns historically broke the parser.

### Testing Requirements
- `../tests/test_gemini_service.py`, `../tests/test_insurance_consistency.py`, `../tests/test_offline_eval.py`.

## Dependencies

### Internal
- Loaded by `../agents/*`, parsed by `../services/gemini_service.py`.

<!-- MANUAL: -->
