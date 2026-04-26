# Orbital Inspect Demo Runbook

This document turns the README demo section into a repeatable product demo that can be recorded, narrated live, or adapted for different audiences.

## Goal

Show Orbital Inspect as an operational decision system for orbital asset risk, not as a generic AI vision toy.

The demo should leave the audience with four conclusions:

1. Orbital Inspect reaches a useful decision surface quickly.
2. The system exposes evidence and stage-by-stage outputs instead of hiding behind a single score.
3. Human review remains in control of the outcome.
4. The product scales from a single incident to a fleet-wide operational queue.

## Default demo path

Use this sequence unless there is a strong reason to tailor it:

1. Launch the app in local demo mode.
2. Start with `ISS — Debris Strike` or `SENTINEL-1A — Impact`.
3. Let the 5-agent pipeline stream without interruption.
4. Pause on the recommendation and explain the fail-closed behavior.
5. Generate the PDF report.
6. Switch to `PORTFOLIO`.
7. Show filters, triage, and the attention queue.

## Local setup

```bash
# Terminal 1
cd backend
DEMO_MODE=true GEMINI_API_KEY=test-dummy-key \
  python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Open `http://localhost:5173`.

## Refresh README assets

```bash
cd frontend
npm run demo:assets
```

This command boots the E2E-backed local stack, runs a deterministic capture flow, and rewrites the PNG assets used by the README demo section.

## Three-minute talk track

### 0:00 to 0:20

"Orbital Inspect answers a simple but expensive question for operators, insurers, and defense teams: what does public evidence show, what is missing, and what needs human review before anyone treats this as an operational or underwriting decision?"

### 0:20 to 0:45

"I am starting with a built-in incident so the demo is reproducible every time. Instead of a static score, the product runs a five-stage analysis pipeline with orbital classification, visual assessment, environmental hazard analysis, failure mode analysis, and insurance risk synthesis."

### 0:45 to 1:30

"As the pipeline runs, notice that each stage contributes evidence to the final judgment. This is not one opaque model call. The UI shows the live feed, the evolving visual interpretation, and the intelligence panel that will drive the operator decision."

### 1:30 to 2:05

"The key trust behavior is fail-closed escalation. If evidence is incomplete or a stage fails, Orbital Inspect does not manufacture certainty. It forces `FURTHER_INVESTIGATION` so the operator sees uncertainty as a surfaced decision state."

### 2:05 to 2:30

"Now I generate the Public Risk Screen report. That converts the analysis into an artifact that can move into operations review, underwriting evidence collection, or a formal audit trail without claiming public data is enough for a final underwriting decision."

### 2:30 to 3:00

"The same system also operates at fleet level. When I switch to the portfolio view, I can rank assets by urgency, filter by decision state, inspect degradation, and work the open attention queue without changing tools."

## Audience-specific emphasis

| Audience | Emphasize | De-emphasize |
|---|---|---|
| **Satellite operators** | anomaly triage, degradation tracking, attention queue, operator context | deep insurance language |
| **Insurers / underwriters** | screening priority, missing evidence, PDF report, auditable review actions | low-level frontend details |
| **Defense / national security** | deployment flexibility, classification controls, audit trail, no SaaS dependency | commercial-market framing |
| **Technical evaluators** | public data fusion, fail-closed pipeline, SSE flow, deployment path | marketing language |

## Shot list for recorded media

| Asset | Target file | What to capture |
|---|---|---|
| Hero still | `docs/demo/assets/orbital-inspect-demo-hero.png` | Full live-app hero capture for the top of the README |
| Analyze still | `docs/demo/assets/orbital-inspect-demo-analyze.png` | Visual analysis surface with uploaded orbital asset and overlays |
| Decision still | `docs/demo/assets/orbital-inspect-demo-decision.png` | Review controls and report/export surface |
| Portfolio still | `docs/demo/assets/orbital-inspect-demo-portfolio.png` | Summary cards, filters, attention queue, and asset detail |

The current PNG files are generated captures. The SVG files in `docs/demo/assets/` remain as editable storyboard/source placeholders when a static redesign is needed.

## Recording checklist

- Use demo mode, not a custom live-input scenario, for the first recording.
- Pick one case and finish the whole story before branching into optional screens.
- Keep the browser zoom stable so the three-panel analysis layout is readable.
- Wait long enough on the recommendation panel for the audience to read the risk tier and recommended action.
- End on `PORTFOLIO`; do not let the story end on the upload form.

## README integration rule

Do not add a large screenshot gallery above the product value proposition. Keep one hero asset near the top, then one compact three-image strip, then link here for the deeper runbook.
