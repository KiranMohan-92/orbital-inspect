# Orbital Inspect Product Feature Research

**Date:** April 4, 2026
**Scope:** Research and strategic assessment of the most important product features for Orbital Inspect based on current and emerging directions from NASA, SpaceX/Starlink, HEO, Astroscale, Northrop Grumman, Axiom, Vast, OrbitsEdge, Starcloud, and adjacent orbital infrastructure players.

---

## 1. Deep Research Result

As of **April 4, 2026**, the strongest conclusion is this:

**Orbital Inspect should evolve into an `orbital asset health + servicing intelligence + infrastructure inspection` platform, not remain a one-off image-analysis/report product.**

The top-tier market signal is not “better AI captions for satellite photos.” It is:
- continuous monitoring instead of one-time inspection
- tasking and sensor orchestration instead of passive uploads
- geometry, metrology, and servicing-readiness instead of generic anomaly labels
- fleet operations and machine-speed coordination instead of static PDFs
- support for stations, servicers, power systems, and orbital compute assets, not just classic satellites

### What the leaders are signaling

- **NASA**: the October 1, 2025 ISAM State of Play treats **inspection and metrology** as a core capability, alongside RPO, repair, refueling, assembly, and manufacturing. It also treats **software/algorithms**, **operations/logistics**, and **laws/standards** as cross-cutting requirements. That means Orbital Inspect needs to be an operations system, not just an analysis tool.
- **NASA OSAM-1**: on the March 23, 2026 updated OSAM-1 page, NASA explicitly says the project was canceled after a shift away from **refueling unprepared spacecraft**. Product implication: prepared interfaces, serviceability, docking/readiness, and economic viability matter.
- **SpaceX / Starlink**: Starlink’s Stargaze and space traffic APIs point to a world of **minutes-level screening, hourly ephemeris sharing, autonomous response, and operator APIs**. Inference: SpaceX-class users will want live coordination, automation, and machine-readable outputs, not report-only workflows.
- **HEO**: HEO Inspect 3.0 already offers **explore, task, analyze**, plus pattern-of-life, attitude estimation, 3D modeling, mensuration, and anomaly attribution. Their GEO-focused Adler Mk2 adds short video, RGB, and onboard detection. This is the clearest signal that the market is moving toward **multi-sensor tasking + geometry + persistent insight**.
- **Astroscale**: ADRAS-J, ADRAS-J2, and LEXI-P show inspection as a precursor to **RPO, capture, robotic servicing, life extension, and multi-client missions**.
- **Northrop Grumman SpaceLogistics**: MRV/MEV show the market is heading toward **detailed robotic inspection, augmentation, relocation, repair, non-standard interfaces, and in-orbit assembly**.
- **Commercial stations**: Axiom Station and Vast Haven-1 mean future inspection targets include **modules, airlocks, windows, deployable arrays, external payloads, and human-rated systems**.
- **Orbital compute/data infrastructure**: OrbitsEdge, Starcloud, Starcloud-2, and Lonestar signal a real trend toward **space-based compute, storage, thermal, and power infrastructure**. There is no official public evidence here that SpaceX or NASA themselves are deploying orbital data centers today; that part is a forward-looking market inference from adjacent players.

### Features Orbital Inspect now needs

1. **Continuous asset timeline** with historical states, not just isolated analyses.
2. **Multi-sensor evidence graph**: uploaded imagery, external NEI tasking, ephemeris, conjunctions, telemetry summaries, operator notes, prior inspections.
3. **Tasking and feasibility engine**: when can this object be imaged, by what sensor, at what geometry/confidence/cost.
4. **Attitude / tumble / deployment verification** for arrays, antennas, radiators, appendages.
5. **Multi-epoch comparison** and anomaly attribution over time.
6. **3D modeling and mensuration** to estimate size, configuration, and subsystem geometry.
7. **Servicing-readiness scoring**: docking port pose, grapple features, obstruction analysis, keep-out zones, cooperative vs non-cooperative target state.
8. **RPO support mode** for close-approach inspections and pre-capture characterization.
9. **Conjunction / maneuver coordination APIs** and operator workflow integration.
10. **Fleet operations view** with prioritization, recurring anomalies, and service/deorbit candidates.
11. **Human-governed decision workflow** with signed artifacts, approvals, provenance, and auditability.
12. **Asset classes beyond satellites**: servicers, upper stages, station modules, solar arrays, radiators, compute platforms, power nodes.

### Features that become important next

- **Edge/onboard inference mode** so remote sensors send detections and clips, not only raw data.
- **Prepared/unprepared servicing interface library** aligned with real ISAM workflows.
- **Commissioning -> anomaly -> service -> post-service -> disposal** lifecycle workflows.
- **Station and orbital infrastructure inspection packs** for habitable modules, manufacturing payloads, power/thermal systems.
- **Cislunar / GEO / deep-orbit support** instead of staying LEO-only.

### Product call

If Orbital Inspect wants NASA / SpaceX / HEO / Astroscale relevance, it should aim to become the **control plane for orbital inspection and servicing intelligence**.

The moat will be:
- tasking
- evidence fusion
- geometry/metrology
- operations workflow

The weakest long-term position would be staying as an “AI-generated inspection report” product.

### Research Sources

- NASA ISAM State of Play 2025: https://ntrs.nasa.gov/citations/20250008988
- NASA OSAM-1: https://www.nasa.gov/mission/on-orbit-servicing-assembly-and-manufacturing-1/
- NASA ISAM: https://www.nasa.gov/isam/
- Starlink Stargaze: https://starlink.com/stargaze
- Starlink Satellite Operators: https://www.starlink.com/satellite-operators
- Starlink Space Traffic Coordination APIs: https://docs.space-safety.starlink.com/docs/
- HEO Inspect 3.0: https://www.heospace.com/technology/heo-inspect-3-0
- HEO Satellite Operators: https://www.heospace.com/solutions/satellite-operators-solutions
- HEO Inspect 2.0 product update: https://www.heospace.com/resources/stories/heo-inspect-2-0-product-update-february-2024
- HEO Adler Mk2 for GEO: https://www.heospace.com/resources/stories/heo-unveils-latest-non-earth-imaging-camera-bringing-commercial-satellite-inspection-to-geo
- Astroscale ADRAS-J update: https://www.astroscale.com/en/news/astroscales-adras-j-mission-completes-operations-begins-deorbit
- Astroscale ADRAS-J2: https://www.astroscale.com/en/missions/adras-j2
- Astroscale LEXI-P: https://www.astroscale.com/en/missions/lexi-p
- Northrop Grumman SpaceLogistics: https://www.northropgrumman.com/what-we-do/space/space-logistics-services
- Axiom Space Axiom Station: https://www.axiomspace.com/axiom-station
- Vast Haven-1: https://www.vastspace.com/haven-1
- OrbitsEdge: https://orbitsedge.com/
- Starcloud: https://www.starcloud.com/
- Starcloud-2: https://www.starcloud.com/starcloud-2
- Lonestar: https://www.lonestarlunar.com/

---

## 2. First-Principles, Musk-Style, Hard-to-Vary, Pareto Assessment

From a Musk-style first-principles view, the question is not:

> Can Orbital Inspect generate a smart inspection report?

It is:

> Can this system materially reduce the cost, uncertainty, and latency of operating, recovering, servicing, and scaling orbital infrastructure?

### Hard-to-Vary truths

These truths are unlikely to change whether the customer is SpaceX, NASA, HEO, Astroscale, Axiom, Vast, OrbitsEdge, or a future orbital data-center builder:

- Physical state matters more than narrative. A satellite, station module, servicer, radiator, or array is either deployed correctly, stable, damaged, drifting, obstructed, or not.
- Human review does not scale to mega-constellations or future orbital infrastructure fleets.
- Downlink, operator attention, and intervention windows are scarce resources.
- Inspection only matters if it changes an operational decision: continue, maneuver, service, defer, deorbit, insure, or escalate.
- Geometry beats opinion. Pose, motion, clearance, deployment angle, structural deviation, and keep-out zones are what operations teams actually need.
- Future value is in serviceability and infrastructure uptime, not just anomaly description.

### Pareto answer

If focusing on the 20% of features that could drive 80% of product value, these are the top 5:

1. **Continuous Fleet Anomaly Triage**
   - A live system that ranks which assets need attention now across the whole fleet.
   - Highest utility for SpaceX-scale or HEO-style operations because it compresses operator attention.

2. **Multi-Epoch Visual State Comparison**
   - Compare the same object over time to detect change in pose, deployment, damage, stability, thermal surface state, appendage motion, or structural deviation.
   - Single-image interpretation is weak evidence; deltas over time drive real decisions.

3. **Geometry / Metrology / Pose Estimation**
   - Estimate orientation, tumble, appendage deployment, dimensions, offsets, clearance, docking accessibility, and configuration state.
   - Top-tier operators need “solar array 18 degrees off nominal” rather than “possible anomaly.”

4. **Inspection Tasking + Sensor Orchestration**
   - Recommend and request the next best observation: when, from what platform, at what geometry, for what confidence gain.
   - Turns the product from passive analysis into an operational control layer.

5. **Action-Oriented Decision Workflow**
   - Every inspection should end in a machine-usable decision object:
     - continue operations
     - monitor
     - re-image
     - maneuver
     - service candidate
     - insurance escalation
     - deorbit / disposal review
   - Insight for insight’s sake is weak. Reduced decision latency is what customers pay for.

### What different buyers care about

- **Musk / SpaceX-like buyer**: fleet-scale autonomy, fewer humans per asset, faster anomaly closure, machine-readable actions, support for very high deployment cadence.
- **NASA-like buyer**: inspection plus metrology, servicing-readiness, autonomy with auditability, standards/compliance/provenance.
- **HEO / Astroscale / Northrop-like buyer**: taskable imaging, pose/geometry, anomaly attribution, close-approach inspection support, service planning.

### Best product thesis

Orbital Inspect should become:

**The operating system for orbital asset state estimation and action planning.**

Not:
- AI satellite report generator
- insurance-only tool
- image upload app

### Highest-leverage roadmap sequence

1. Fleet anomaly triage
2. Multi-epoch comparison
3. Geometry/metrology
4. Tasking orchestration
5. Action workflow

---

## 3. Deep Realistic Review of the 5 Core Features

### Scorecard

| Feature | Customer Value | Technical Feasibility | Data Dependency | Time To Useful MVP | Time To Credible Production | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Continuous Fleet Anomaly Triage | 10/10 | 8/10 | 6/10 | 2-4 months | 6-9 months | Build now |
| Multi-Epoch Visual State Comparison | 9/10 | 5/10 | 9/10 | 4-6 months | 12-24 months | Build narrowly |
| Geometry / Metrology / Pose Estimation | 10/10 | 3/10 | 10/10 | 6-9 months | 18-36 months | Start as constrained subsystem |
| Inspection Tasking + Sensor Orchestration | 9/10 | 6/10 | 8/10 | 3-6 months | 9-18 months | Build after partner access |
| Action-Oriented Decision Workflow | 10/10 | 9/10 | 5/10 | 1-3 months | 4-8 months | Build immediately |

### 3.1 Continuous Fleet Anomaly Triage

- This is the most obvious product fit for constellation operators and service providers because it compresses attention.
- It is feasible because it mainly needs a durable event model, scoring engine, evidence freshness, recurrence logic, and operator-facing ranking.
- The hard part is ranking credibility. If the ranking logic is unstable or opaque, operators will ignore it.
- The correct MVP is not “AI risk score.” It is a transparent priority queue driven by evidence quality, severity, confidence, recency, conjunction context, mission criticality, and repeat anomalies.
- The main failure mode is alert spam.
- This is a strong near-term wedge because top operators already live in fleet operations, not one-off analysis.
- **Verdict:** highest ROI feature after decision workflow.

### 3.2 Multi-Epoch Visual State Comparison

- This is where the product becomes genuinely useful instead of decorative.
- The difficulty is that orbital imagery is highly unconstrained: viewpoint, range, lighting, glare, specular reflections, compression, and attitude vary radically.
- If this is attempted generically from arbitrary uploaded images, it is likely to fail.
- It becomes feasible if the problem is constrained:
  - same asset
  - same or similar sensor family
  - bounded viewpoint differences
  - timestamped imagery
  - known mission or subsystem expectations
- The right MVP is not “automatic damage diff for all images.” It is “timeline-linked comparison with human-review overlays and structured change hypotheses.”
- This is a moat feature because it compounds with every inspection stored.
- **Verdict:** must build, but narrowly and honestly.

### 3.3 Geometry / Metrology / Pose Estimation

- This is the most strategically powerful feature because it converts imagery into operational facts: deployed angle, alignment, accessibility, clearance, capture readiness.
- It is also the most technically dangerous feature to overpromise.
- True metrology needs some combination of calibrated optics, known range, multiple views, object priors, CAD/digital twin references, or tightly bounded assumptions.
- Random monocular uploads will not support NASA-grade geometry.
- For non-cooperative targets, difficulty rises sharply due to occlusion, tumbling, glare, and sparse frames.
- The realistic path is staged:
  - coarse pose/state classification
  - deployment completeness and appendage state
  - bounded measurements on known target classes
  - later, real mensuration and servicing geometry
- If done correctly, this is a real moat. If done badly, it destroys trust.
- **Verdict:** foundational long-term moat, but should not be positioned as solved early.

### 3.4 Inspection Tasking + Sensor Orchestration

- Strategically excellent because it turns the product from passive analysis into an operational control layer.
- The software problem is manageable; the real barrier is partner and sensor access: APIs, tasking rights, economics, revisit constraints, priority conflicts, and SLAs.
- Without external sensor integration, this feature is only a recommendation engine. That is still useful, but it is not true orchestration.
- The correct first-principles objective is: maximize uncertainty reduction per unit time/cost/risk.
- A good MVP is a **next best observation planner** with recommended windows, angles, asset priority, and expected confidence improvement.
- Production orchestration later needs partner contracts, booking, callbacks, retries, and exception handling.
- **Verdict:** high value, but partner-dependent; build the planner before the booking layer.

### 3.5 Action-Oriented Decision Workflow

- This is the most commercially important feature in the near term because it is where analysis becomes decision support.
- Executives and operators do not buy anomaly descriptions. They buy faster, safer decisions.
- This is highly feasible because it is mainly workflow architecture: evidence thresholds, confidence rules, review states, approvals, machine-readable actions, and escalation logic.
- The critical warning is that decision workflow amplifies upstream model quality. Weak evidence plus authoritative actions is dangerous.
- The product must separate:
  - inferred observation
  - confidence
  - evidence completeness
  - recommended action
  - required human approval
- For NASA, insurers, and enterprise operators, this is mandatory. For SpaceX-like users, it must be API-first and automatable.
- **Verdict:** highest-priority feature overall.

---

## 4. Overall Conclusion

### Best near-term pair

- **Action-Oriented Decision Workflow**
- **Continuous Fleet Anomaly Triage**

These are the most realistic features to make Orbital Inspect commercially successful soon.

### Best medium-term moat pair

- **Multi-Epoch Comparison**
- **Tasking Planner**

These make the platform harder to replace and more operationally valuable.

### Most powerful but hardest long-term feature

- **Geometry / Metrology / Pose**

This can make Orbital Inspect elite, but it is also the easiest place to fail technically if overpromised.

### Brutal prioritization

1. Build **Action-Oriented Decision Workflow** now.
2. Build **Continuous Fleet Anomaly Triage** immediately after.
3. Build **Multi-Epoch Comparison**, but only under constrained imaging assumptions.
4. Build **Tasking Planner**, then later real orchestration.
5. Build **Geometry/Metrology** as a staged program, not a marketing promise.

### What to avoid

- Do not market generic “AI inspection intelligence” as if it equals operational geometry.
- Do not claim multi-image or time-series insight until inputs are controlled enough to support it.
- Do not start with full task booking/orchestration before real partner access exists.
- Do not let the workflow imply autonomy beyond the evidence quality.

### Bottom line

If being extremely strict:
- **Action Workflow** and **Fleet Triage** are the features most likely to make Orbital Inspect successful in the near term.
- **Multi-Epoch Comparison** is the feature most likely to make it genuinely defensible.
- **Geometry/Metrology** is the feature most likely to make it elite, but also the easiest place to fail technically.
- **Tasking/Orchestration** is the feature most likely to make it strategically sticky, but only once sensor and partner leverage exists.

---

## 5. Key Source List

- NASA ISAM State of Play 2025: https://ntrs.nasa.gov/citations/20250008988
- NASA OSAM-1: https://www.nasa.gov/mission/on-orbit-servicing-assembly-and-manufacturing-1/
- HEO Inspect 3.0: https://www.heospace.com/technology/heo-inspect-3-0
- HEO Satellite Operators: https://www.heospace.com/solutions/satellite-operators-solutions
- Astroscale ADRAS-J update: https://www.astroscale.com/en/news/astroscales-adras-j-mission-completes-operations-begins-deorbit
- Astroscale LEXI-P: https://www.astroscale.com/en/missions/lexi-p
- Northrop Grumman SpaceLogistics: https://www.northropgrumman.com/what-we-do/space/space-logistics-services
- Starlink Satellite Operators: https://www.starlink.com/satellite-operators
- Starlink Space Traffic Coordination APIs: https://docs.space-safety.starlink.com/docs/
- Axiom Station: https://www.axiomspace.com/axiom-station
- Vast Haven-1: https://www.vastspace.com/haven-1
- OrbitsEdge: https://orbitsedge.com/
- Starcloud: https://www.starcloud.com/
- Lonestar: https://www.lonestarlunar.com/
