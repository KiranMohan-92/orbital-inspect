<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# .agents

## Purpose
Multi-model AI engineering workflow configuration. Declares the three collaborating models (Claude builder, Codex GPT-5.4 auditor, Gemini 3.1 Pro verifier), the cross-model verification gates, and the attribution contract enforced per commit.

## Key Files
| File | Description |
|------|-------------|
| `workflow.yaml` | Formal workflow definition — roles, handoffs, attribution tags |
| `verification-gates.yaml` | Cross-model verification gates (currently advisory; CI-blocking is Next Step #2 in root log) |

## For AI Agents

### Working In This Directory
- These files are the single source of truth for the multi-model workflow. Changes here ripple into `CLAUDE.md`, `.codex`, and the root `AGENTS.md` collaboration log.
- When adding a verification gate, also reflect it in `CLAUDE.md` "Cross-Model Verification Gates" section so Claude Code enforces it at authoring time.
- Current maturity: 6.8/10 overall (see root `AGENTS.md` Workflow Maturity table). Aim-of-work is to move gates from advisory → CI-blocking.

### Testing Requirements
- No automated tests today. Validate YAML syntax before committing.

## Dependencies

### Internal
- Referenced by root `AGENTS.md` (collaboration log), `CLAUDE.md` (Claude's project rules), `.codex` (Codex rules).

<!-- MANUAL: -->
