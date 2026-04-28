<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# alertmanager

## Purpose
Alertmanager routing, grouping, and inhibition configuration. Consumes alerts from Prometheus and dispatches to the configured receivers.

## For AI Agents

### Working In This Directory
- Validate configs with `amtool check-config <file>` before committing.
- Route severities must match labels set by rules in `../prometheus/`.
- Silencing logic + receiver secrets: reference via environment, never inline.

## Dependencies

### Internal
- Consumes alerts from `../prometheus/`.

### External
- Alertmanager.

<!-- MANUAL: -->
