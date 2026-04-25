<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# hooks

## Purpose
Custom React hooks for SSE consumption and analysis state. Centralizes event-stream parsing so components stay presentational.

## Key Files
| File | Description |
|------|-------------|
| `useSSE.ts` | Server-Sent Events hook — CRLF-safe parser, reconnect, versioned envelope (Audit Rec #8) |
| `useSSE.test.ts` | Colocated Vitest suite for `useSSE` |
| `useAnalysisState.ts` | Derives per-stage analysis state from the SSE event stream |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `__tests__/` | Vitest tests — `useAnalysisState.test.ts` (see `__tests__/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- SSE parser must tolerate CRLF and mid-stream disconnects (Audit Rec #8 — regression gate).
- The SSE envelope is versioned; match `backend/models/events.py`. Do not silently drop unknown event types — log and continue.
- State hook must treat degraded stages as terminal for that stage, not success.

### Testing Requirements
- `useSSE.test.ts` colocated; add reconnect / CRLF edge cases when you touch the parser.

## Dependencies

### Internal
- `../generated-types.ts` for event schemas, `../utils/api.ts` for base URL.

<!-- MANUAL: -->
