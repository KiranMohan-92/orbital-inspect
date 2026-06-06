# Agent Evolution Control Plane

Date: 2026-05-28

Scope: production-grade self-evolving agentic system for Orbital Inspect

## Fit With The Original Goal

This fits Orbital Inspect's original goal because the product is already an evidence-first satellite risk intelligence system. A self-evolving agent layer is valuable only if it improves the evidence pipeline, review discipline, and NASA/SpaceX readiness without weakening the product's public-screen authority boundaries.

The hard-to-vary explanation is simple: Orbital Inspect is not valuable because it has many agents. It is valuable if its agents preserve truth under uncertainty. That means the next layer should measure and improve agent behavior, not merely add more autonomous workers.

## System Shape

The control plane is a closed loop:

```text
agent run
  -> trace
  -> failure taxonomy
  -> eval case
  -> isolated experiment
  -> promotion gate
  -> rollback monitor
```

This creates compounding improvement because every failure can become a permanent test of the system's future behavior.

## Hermes-Like Capabilities, Production-Bounded

The target is Hermes-like autonomy with Orbital Inspect safety boundaries:

- task queue for proposed improvements, review findings, and research missions
- local-first memory for project-scoped learned instincts
- validator-gated research loop for NASA/SpaceX requirement tracking
- scheduled dry-run evals and readiness reports
- tool registry through explicit scripts and MCP surfaces
- promotion gate before any learned behavior becomes active
- rollback monitor after promotion

Private repository content stays local by default. External review requires a sanitized artifact path that strips private code, secrets, credentials, customer data, and proprietary context. This is not optional because the session already showed that private repo handoff to an external OpenCode/provider path can be blocked by policy.

## Autoresearch-Style Loop

The research loop should be validator-gated:

1. Define the mission: for example, "verify current Starlink CDM API expectations."
2. Define the validator: source URLs, required fields, and pass/fail checks.
3. Produce an artifact: concise requirement delta, cited evidence, and affected eval cases.
4. Run an architect review: approve, reject, or require more evidence.
5. Convert approved deltas into eval cases or implementation tasks.

The loop stops on validation evidence, not on model confidence. This is the same reason Orbital Inspect forces `FURTHER_INVESTIGATION` when evidence is incomplete.

## NASA/SpaceX Readiness Direction

For NASA/SpaceX relevance, the agent evolution system should prioritize evals around standards-native orbital evidence:

- CCSDS OEM trajectory handling
- OMM/TLE role separation
- CDM-compatible screening artifacts
- covariance presence, frame, timestamp, and quality checks
- operator ephemeris evidence distinct from public TLE evidence
- positive semidefinite covariance validation
- null collision probability when covariance is absent or invalid
- software assurance traceability
- NASA-style IV&V evidence
- model credibility and uncertainty artifacts

This matters because NASA/SpaceX acceptance is not a language-quality problem. It is an evidence, standards, assurance, and operations problem.

## Promotion Rules

No self-merging.

No self-approval.

No agent, prompt, workflow, or learned instinct becomes active unless:

- deterministic evals pass
- release-critical regressions stay green
- triggered review artifacts exist
- privacy classification is explicit
- cost or latency regressions are accepted intentionally
- human review approves high-risk authority changes

The promotion gate is stricter than ordinary development because bad agent rules compound across future work.

## Rollback Monitor

After promotion, monitor:

- eval pass rate
- degraded run rate
- `FURTHER_INVESTIGATION` rate
- review rejection rate
- cost per successful task
- latency per successful task
- privacy or external-tool incidents

If a promoted change increases critical failures or weakens authority boundaries, freeze rollout and roll back.

## Phase 1 Implementation

The first production-grade slice is intentionally small:

- dependency-free eval runner
- versioned eval schema
- seeded guardrail suite
- CI job for agent-evolution guardrails
- architecture doc tying self-evolution to Orbital Inspect's product truth model

This is the right first step because it makes improvement measurable before adding persistent schedules, memory promotion, or autonomous task execution.
