# Multi-Model Agent Collaboration Log

> This document tracks the structured multi-model AI engineering workflow used to build Orbital Inspect.
> Updated manually after each significant collaboration event. See `.agents/workflow.yaml` for the formal workflow definition.

## Model Registry

| Model | Tool | Version | Role | Co-Author Tag |
|-------|------|---------|------|---------------|
| Claude Opus 4.6 | Claude Code | 1M context | **Builder** — features, refactoring, tests, docs | `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>` |
| GPT 5.4 | Codex CLI | v0.118.0 | **Auditor** — architecture audits, security review, verification | `Co-Authored-By: Codex GPT 5.4 <noreply@openai.com>` |
| Gemini 3.1 Pro | Gemini CLI | v0.36.0 | **Verifier** — independent validation, domain checks, tie-breaking | `Co-Authored-By: Gemini 3.1 Pro <noreply@google.com>` |

## Commit Attribution Summary

_As of 2026-04-06 (24 total commits):_

| Model | Co-Authored Commits | Referenced In (body) | Primary Contribution |
|-------|--------------------:|---------------------:|----------------------|
| Claude Opus 4.6 | 16 | 16 | Scaffold, frontend, Sprints 2-6, provenance, durable jobs, decision workflow, observability |
| Codex GPT 5.4 | 1 | 5 | Architecture audit (20 recs), telemetry services, E2E tests, runtime bug root causes |
| Gemini 3.1 Pro | 0 | 2 | Runtime LLM model; first verification session 2026-04-05 |

## Verification Events

| Date | Type | Trigger | Model | Key Finding | Resolution |
|------|------|---------|-------|-------------|------------|
| 2026-03-30 | Architecture Audit | Post-scaffold review | Codex GPT 5.4 | 7/10 demo, 3/10 production. 6 critical findings, 20 recommendations. | AUDIT-GPT54.md → Sprints 2-6 |
| 2026-03-30 | Gap Closure | Post-Sprint 5 | Codex GPT 5.4 | 5 gaps: unmounted routers, missing SSE fields, permissive parse, viz not wired, test dep missing | `713c9ad` — all 5 closed |
| 2026-03-30 | Root Cause Analysis | Runtime crash | Codex GPT 5.4 | async session needs await (ADK 1.20.0), GEMINI_API_KEY not in os.environ, deprecated model | `2a6a4e9` — 3 root causes fixed |
| 2026-04-01 | Deutsch Verification | Post-provenance feature | Codex GPT 5.4 | `is not None` vs truthiness bug (0.0 skipped stubs), sensitivity range ±1→±2, missing 3 provenance fields | `d9bc1cf` — 24min turnaround |
| 2026-04-01 | Feature Build | Telemetry gap | Codex GPT 5.4 | Built 3 telemetry services + 12 E2E tests. Fixed test_reports_api hang. | `b45dc87` — dual co-author |
| 2026-04-05 | Cross-Model Verification | Percentile claim check | All 3 models | Claude estimated 99.98th, GPT-5.4 corrected to ~99.97th (5K-20K people), verified repo forensics | This session |

## Audit Recommendation Traceability

_AUDIT-GPT54.md (2026-03-30) — 20 recommendations, all implemented:_

| Rec # | Recommendation | Implemented In | Commit |
|------:|----------------|----------------|--------|
| 1 | Durable jobs (Postgres + Redis + workflow) | Sprint 2 | `56a070f` |
| 2 | Remove permissive fallbacks → degraded state | Sprint 1 safety | `63cdf4c` |
| 3 | Per-stage timeout, retry, circuit breaker | Sprint 3 | `e6b85a2` |
| 4 | Block downstream on missing upstream evidence | Sprint 1 safety | `63cdf4c` |
| 5 | Persist analyses, events, outputs | Sprint 2 | `56a070f` |
| 6 | Auth, org tenancy, RBAC, rate limits | Sprint 3 | `e6b85a2` |
| 7 | Version SSE contract | Sprint 1 safety | `63cdf4c` |
| 8 | Fix SSE parser (CRLF, disconnects) | Sprint 1 safety | `63cdf4c` |
| 9 | Generate shared TS types from backend | Sprint 1 | `ad7c9f2` |
| 10 | Structured logging, traces, metrics | Sprint 2 | `56a070f` |
| 11 | Human review + approval workflow | Sprint 4 | `68e493f` |
| 12 | Server-side PDF report service | Sprint 4 | `68e493f` |
| 13 | Evidence fusion (TLE, orbit, telemetry) | Sprint 5 | `9a49010` |
| 14 | Portfolio & constellation monitoring | Sprint 5 | `9a49010` |
| 15 | Precedent + claims knowledge base | Sprint 4 | `68e493f` |
| 16 | Webhooks, outbound integrations | Sprint 4 | `68e493f` |
| 17 | Surface demo/offline mode in UI | Sprint 4 | `68e493f` |
| 18 | Zoomable multi-evidence viewer | Sprint 5 | `9a49010` |
| 19 | 3D visualization, degradation timelines | Sprint 5 | `9a49010` |
| 20 | Regression/eval harness with golden tests | Sprint 1 | `ad7c9f2` |

## Cross-Model Metrics

| Metric | Value |
|--------|-------|
| Total commits | 24 |
| AI-attributed commits | 16 (67%) |
| Cross-model reference commits | 5 (commits referencing another model's work) |
| Audit recommendations | 20 |
| Recommendations implemented | 20 (100%) |
| Tightest verification loop | 24 minutes (`3c6e441` → `d9bc1cf`, Apr 1) |
| Avg audit finding → fix time | ~4 hours |
| Cross-model bugs found | 3 (async session, provenance truthiness, sensitivity range) |
| Models with co-author commits | 2 of 3 (Gemini pending first commit) |

## Workflow Maturity Assessment

_Self-assessed against the 5-layer upgrade framework (2026-04-06):_

| Layer | Status | Score |
|-------|--------|-------|
| 1. Attribution Consistency | Enforced via CLAUDE.md + .codex rules | 8/10 |
| 2. Agent Config in Repo | .agents/ directory with workflow + gates | 8/10 |
| 3. Verification Gates | Defined in .agents/verification-gates.yaml (advisory mode) | 6/10 |
| 4. Audit Trail & Metrics | This document (AGENTS.md) | 7/10 |
| 5. Three-Model Mesh | Two active, Gemini onboarding | 5/10 |
| **Overall** | **Structured, documented, partially automated** | **6.8/10** |

### Next Steps to World-Class
1. Get Gemini's first co-authored commit (promote from runtime model to active collaborator)
2. Move verification gates from advisory to CI-blocking
3. Add automated attribution checking in CI
4. Run first three-model pre-release sign-off
5. Track cross-model metrics automatically via git hooks
