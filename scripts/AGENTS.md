<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-05-28 -->

# scripts

## Purpose
Container directory for repo-root developer tooling scripts. Backend-specific scripts live in `backend/scripts/` and ops scripts live in `ops/scripts/`.

## Key Files
| File | Description |
|------|-------------|
| `check_verification_gates.py` | CI guard for blocking cross-model review artifacts |
| `run_agent_evals.py` | Dependency-free deterministic runner for agent-evolution eval suites |

## For AI Agents

### Working In This Directory
- Only add scripts here that cross the backend/frontend boundary or set up the whole monorepo.
- Language-specific scripts belong in `backend/scripts/` or `frontend/` `package.json` scripts.

### Testing Requirements
- Run `python -m py_compile scripts/<script>.py` for Python scripts.
- Run the script's smallest deterministic smoke check before claiming completion.

<!-- MANUAL: -->
