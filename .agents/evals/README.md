# Agent Evolution Evals

This directory contains deterministic eval suites for Orbital Inspect's agentic engineering system.

The purpose is narrow: agent, prompt, workflow, and automation changes may be proposed freely, but they must be promoted only when measurable eval evidence says they preserve or improve the system.

## Layout

| File | Purpose |
| --- | --- |
| `agent-eval-suite.schema.json` | Human-readable JSON schema for eval suite files |
| `orbital_inspect_guardrails.json` | Seed suite for fail-closed, authority, privacy, and NASA/SpaceX readiness guardrails |

## Operating Rules

- Keep evals deterministic whenever possible.
- Prefer static/code graders over model graders for release-critical invariants.
- Any model-graded eval must be non-release-critical unless a human review artifact also exists.
- Runtime safety boundaries are stronger than learned instincts. No eval may approve weakening `PUBLIC_SCREEN`, evidence provenance, human review, or `FURTHER_INVESTIGATION`.
- External-agent review of private repo contents requires a sanctioned sanitized artifact. The default path is local-only.

## Runner

Run the seed suite from the repository root:

```powershell
python scripts/run_agent_evals.py --suite .agents/evals/orbital_inspect_guardrails.json
```

The runner exits non-zero on any failed eval. Command graders are disabled by default and require `--allow-commands`.
