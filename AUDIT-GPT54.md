# Orbital Inspect — GPT 5.4 Architecture Audit

**Date:** 2026-03-30
**Model:** GPT 5.4 (Codex CLI v0.114.0, headless mode)
**Verdict:** 7/10 Demo-Ready, 3/10 Production-Ready

## Architecture Ratings

| Dimension | Score | Notes |
|-----------|-------|-------|
| Domain framing | 8/10 | Strong satellite damage taxonomy, real ORDEM/SWPC data, insurance precedents |
| UI polish | 7/10 | Deep space design system is compelling, but static image viewer only |
| Service architecture | 5/10 | Clean agent pattern, but prompt wrappers not production agents |
| SSE streaming | 4/10 | Works but no analysis_id, sequence numbers, resume semantics |
| Reliability | 2/10 | No timeouts, retries, circuit breakers, or durable jobs |
| Security/Compliance | 1/10 | No auth, no RBAC, no audit logging, no encryption |

## 6 Critical Findings

1. **Silent failure looks like success** — Bad JSON becomes permissive defaults in gemini_service.py:96, classification exceptions return valid=True in orbital_classification_agent.py:98
2. **Pipeline underwrites on partial evidence** — orchestrator.py:109 converts failed stages to {} and still runs downstream risk analysis
3. **SSE contract is brittle** — No analysis_id, sequence numbers, schema version, or resume semantics
4. **No durable report/job architecture** — SatelliteConditionReport model exists but is never constructed
5. **Single-process bottleneck** — Long analysis ties up one HTTP request. REDIS_URL declared but unused
6. **Frontend/backend types drift** — types.ts omits SUDDEN, expects timeline where backend emits rationale

## Top 20 Recommendations

| # | Value | Effort | Recommendation |
|---|-------|--------|----------------|
| 1 | Very High | Medium | Move analysis to durable jobs (Postgres + Redis + workflow engine) |
| 2 | Very High | Small | Remove permissive fallbacks — errors must produce explicit degraded state |
| 3 | Very High | Medium | Add per-stage timeout, retry, circuit breaker, token/cost budgets |
| 4 | Very High | Small | Block downstream underwriting when upstream evidence missing |
| 5 | Very High | Medium | Persist analyses, events, prompts, outputs, source artifacts |
| 6 | Very High | Medium | Add auth, org tenancy, RBAC, API rate limits |
| 7 | Very High | Small | Version SSE contract — add analysis_id, event_id, sequence, schema_version |
| 8 | Very High | Small | Fix SSE parser for CRLF, disconnects, broken streams, cancellations |
| 9 | Very High | Small | Generate shared TS types from backend schemas |
| 10 | High | Medium | Add structured logging, traces, metrics, cost accounting |
| 11 | High | Medium | Build human review + approval workflow for underwriting |
| 12 | High | Medium | Server-side HTML-to-PDF report service |
| 13 | High | Large | Evidence fusion: telemetry, TLE/orbit history, operator notes |
| 14 | High | Large | Portfolio & constellation monitoring |
| 15 | High | Medium | Precedent + claims knowledge base with citations |
| 16 | High | Medium | Webhooks, email/Slack notifications, outbound integrations |
| 17 | Medium | Small | Surface demo/offline mode in UI |
| 18 | Medium | Medium | Zoomable multi-evidence viewer + annotation workspace |
| 19 | Medium | Large | 3D satellite visualization, degradation timelines, comparative analysis |
| 20 | Medium | Medium | Regression/eval harness with golden test cases |
