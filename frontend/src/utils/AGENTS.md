<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# utils

## Purpose
Frontend utilities — currently the backend API wrapper and its unit tests.

## Key Files
| File | Description |
|------|-------------|
| `api.ts` | Typed fetch wrapper — base URL, error envelope parsing, auth header injection |
| `api.test.ts` | Colocated Vitest suite for `api.ts` |

## For AI Agents

### Working In This Directory
- Every fetch goes through `api.ts`; do not call `fetch` directly from components.
- Error-envelope shape mirrors `backend/api/error_envelope.py` — keep them in sync.
- Auth token retrieval stays here; components should not touch storage APIs.

### Testing Requirements
- `api.test.ts` is the regression gate; extend when adding helpers.

## Dependencies

### Internal
- `../generated-types.ts`.

<!-- MANUAL: -->
