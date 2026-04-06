# Orbital Inspect — Claude Code Instructions

## Project Context

Orbital Inspect is a multi-agent satellite insurance underwriting intelligence platform.
5-agent pipeline: Classification -> Vision -> Environment -> Failure Mode -> Insurance Risk.
Backend: Python/FastAPI. Frontend: React/Vite/TypeScript/Tailwind. DB: Postgres (prod), SQLite (dev).

## Multi-Model Workflow

This project uses a structured multi-model AI engineering workflow. You (Claude) are the **primary builder**.

### Your Role: Builder
- Feature implementation, refactoring, bug fixes
- Test writing and CI maintenance
- Documentation and code comments
- Responding to audit findings from other models

### Other Models in This Project
- **Codex GPT 5.4** (via Codex CLI): Architecture auditor, verifier, targeted feature builds
- **Gemini 3.1 Pro** (via Gemini CLI): Independent validator, cross-check, tie-breaker

### Attribution Rules (MANDATORY)

Every commit MUST include `Co-Authored-By` tags for ALL AI models that contributed:

```
Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

If implementing findings from another model's audit or review, ALSO credit that model in the commit body:

```
Implements findings from GPT 5.4 architecture audit (AUDIT-GPT54.md, Rec #3).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

Never omit attribution. The git history is the audit trail for the multi-model workflow.

### Cross-Model Verification Gates

When making changes in these areas, flag that cross-model review is recommended:
- **Security**: auth, crypto, SSRF prevention, input validation
- **LLM output handling**: gemini_service.py, parse_json_response, agent error paths
- **New agents or pipeline changes**: orchestrator.py, any new agent
- **Insurance risk logic**: risk matrix, underwriting recommendations, provenance
- **Schema changes**: alembic migrations, db/models.py

### Code Conventions
- Python: async/await, structlog for logging, Pydantic models for all data
- Frontend: TypeScript strict mode, no `any` types, Tailwind for styling
- Tests: pytest (backend), vitest (frontend), playwright (e2e)
- All agent error handlers must return `degraded=True`, never silently succeed
- Evidence gaps must force `FURTHER_INVESTIGATION` recommendation

### What NOT to Do
- Do not remove or weaken the fail-closed classification rejection
- Do not bypass resilient_call() for agent invocations
- Do not add agents without updating AGENT_ORDER in orchestrator.py
- Do not commit .env files or API keys
