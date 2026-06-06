<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-05-28 -->

# .agents

## Purpose
Multi-model AI engineering workflow configuration. Declares the three collaborating models (Claude builder, Codex GPT-5.4 auditor, Gemini 3.1 Pro verifier), the cross-model verification gates, deterministic agent-evolution evals, and the attribution contract enforced per commit.

## Key Files
| File | Description |
|------|-------------|
| `workflow.yaml` | Formal workflow definition - roles, handoffs, attribution tags |
| `verification-gates.yaml` | Cross-model verification gates |
| `evals/` | Deterministic agent-evolution eval suites and schema |

## For AI Agents

### Working In This Directory
- These files are the single source of truth for the multi-model workflow. Changes here ripple into `CLAUDE.md`, `.codex`, and the root `AGENTS.md` collaboration log.
- When adding a verification gate, also reflect it in `CLAUDE.md` "Cross-Model Verification Gates" section so Claude Code enforces it at authoring time.
- Current maturity: 6.8/10 overall (see root `AGENTS.md` Workflow Maturity table). Aim-of-work is to keep gates CI-blocking and make self-evolution eval-gated.

### Testing Requirements
- Validate YAML syntax before committing workflow or gate changes.
- Run `python scripts/run_agent_evals.py --suite .agents/evals/orbital_inspect_guardrails.json` after changing agent workflow, gates, prompts, or self-evolution rules.

## Dependencies

### Internal
- Referenced by root `AGENTS.md` (collaboration log), `CLAUDE.md` (Claude's project rules), `.codex` (Codex rules), and CI.

<!-- MANUAL: -->
