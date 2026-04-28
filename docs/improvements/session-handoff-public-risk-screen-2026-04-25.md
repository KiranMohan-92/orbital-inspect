# Session Handoff: Public Risk Screen Direction

Date: 2026-04-25
Audience: Other active project sessions / future implementation work

## Context

This session reviewed the underlying functional core of Orbital Inspect's 5-agent pipeline: Classification -> Vision -> Environment -> Failure Mode -> Insurance Risk.

The review focused on whether the current physics, environmental modeling, visual inspection claims, and insurance-risk synthesis are strong enough for a SpaceX/NASA-grade or underwriting-grade product.

Conclusion:

Orbital Inspect should not position the free/public-data version as definitive satellite inspection or underwriting-grade risk. The strongest credible product direction is:

> Public-source satellite risk intelligence, evidence-gap scoring, and defensible pre-underwriting triage.

Useful shorthand:

> The public-data "credit report" for satellite risk.

## Review Findings

### Finding 1: Altitude-only debris risk is not physically defensible

File: `backend/services/ordem_service.py`
Lines: 34-48
Priority: P1

ORDEM risk is currently reduced to static altitude bands and a scalar collision probability per square meter. Real MMOD risk depends on orbit epoch, flux by particle size, speed, direction, material density, projected area, shielding, component vulnerability, and mission duration.

Impact:

Two spacecraft at the same altitude can have very different risk. The current model gives them the same environmental prior.

Required direction:

```text
MMOD risk = integral(flux(size, speed, direction, epoch, orbit)
                    * projected_area(component, attitude)
                    * vulnerability(component, material, shielding)
                    * mission_duration)
```

### Finding 2: Radiation model ignores the variables that drive dose and SEE

File: `backend/services/ordem_service.py`
Lines: 93-120
Priority: P1

Radiation is bucketed only by altitude using static AE-8/AP-8-style values. Dose and single-event rates require orbit geometry, inclination/SAA exposure, epoch/solar cycle, particle spectra, shielding depth, parts sensitivity, and confidence bounds.

Impact:

The current radiation values cannot support underwriting-grade remaining-life or loss-probability claims.

Required direction:

Use model-derived radiation products such as IRENE AE9/AP9/SPM, SPENVIS, or cached dose-depth runs with provenance:

```text
radiation_risk = f(orbit, epoch, solar_cycle, particle_spectrum,
                   shielding_depth, component_sensitivity, exposure_duration)
```

### Finding 3: Conjunction risk is scored from miss distance heuristics

File: `backend/services/conjunction_service.py`
Lines: 187-223
Priority: P1

The service parses miss distance and sometimes probability of collision, then maps values through thresholds. Operational conjunction assessment requires state/covariance, hard-body radius, uncertainty realism, time-to-TCA, maneuverability, and a documented probability-of-collision method.

Impact:

Miss distance alone is not a risk metric. Large miss distance with poor covariance can be more dangerous than smaller miss distance with tight covariance.

Required direction:

Use CCSDS CDM-style records where available:

```text
conjunction_risk = f(relative_state_at_TCA, covariance, hard_body_radius,
                     covariance_realism, time_to_TCA, maneuverability)
```

Fallback public-data assessments must be labeled "screening only."

### Finding 4: Vision estimates physical damage without a measurement model

File: `backend/prompts/satellite_vision_prompt.txt`
Lines: 20-39
Priority: P1

The prompt asks the model to identify millimeter-scale craters and estimate power impact from arbitrary imagery, but the pipeline does not require range, resolution, focal length, pose, GSD, MTF, illumination, or component scale.

Impact:

Physical damage size and functional impact are not defensible without a measurement chain.

Required direction:

Add image measurement gates:

```text
resolvable_feature_size = f(range, focal_length, sensor_pitch, image_quality,
                            pose, scale_reference, MTF, illumination)
```

If metadata is missing, output qualitative observations and evidence gaps only.

### Finding 5: Insurance probability is not actuarial yet

File: `backend/prompts/insurance_risk_prompt.txt`
Lines: 59-80
Priority: P1

The prompt asks for total loss probability and financial values, but upstream stages do not provide calibrated posterior distributions, component reliability curves, fleet priors, or likelihood functions. The server checks arithmetic consistency, but not scientific validity.

Impact:

The output can look internally consistent while not being actuarially grounded.

Required direction:

Move total-loss probability into a deterministic reliability layer:

```text
posterior_loss_probability = BayesianUpdate(
    fleet_prior,
    evidence_likelihoods,
    component_reliability_curves,
    environment_exposure,
    mission_consequence_model
)
```

The LLM should explain the model, not invent probability.

## Product Impact Of Implementing These Changes

Implementing the findings would shift Orbital Inspect from an AI-generated report product to a defensible public-data risk intelligence platform.

Expected impacts:

- Trust increases because physics numbers come from deterministic models, not LLM judgment.
- Claims become narrower but more defensible.
- Evidence gaps become a feature, not a weakness.
- Reports become harder to dismiss because every number has units, method, source, epoch, assumptions, and uncertainty.
- Free/public tier becomes a clear risk screen instead of an unsupported underwriting oracle.
- Enterprise upsell becomes clearer: customers provide telemetry, calibrated imagery, geometry, or claims context for stronger conclusions.

Recommended report language shift:

From:

> Risk tier: HIGH, total loss probability: 18%.

To:

> Public-data risk screen: elevated. Main drivers: debris exposure, conjunction density, and TLE stability. Missing evidence blocks underwriting conclusion: power telemetry, calibrated imagery, covariance, and operator anomaly logs.

## Research Verdict On Industry Utility

Deep-research conclusion:

There is real utility in the space industry for this direction. The utility is not in claiming definitive satellite health from public data. The utility is in reducing information asymmetry and helping operators, insurers, analysts, and smaller missions understand public-data risk and missing evidence.

Industry demand signals found:

- ESA reports increasingly crowded orbits, growing collision alerts, and regular avoidance maneuvers.
- OECD frames debris and congestion as an economic sustainability problem.
- NASA CARA exists because determining which conjunctions are truly risky requires disciplined analysis.
- ESA conjunction workflows explicitly depend on object size, miss distance, flyby geometry, and orbit uncertainty.
- Lloyd's treats space as a growing insurance risk category and highlights debris, in-orbit risk, and third-party collision liability.
- Commercial competitors such as LeoLabs, Kayhan, and Slingshot validate market demand for orbital risk intelligence and space traffic coordination.

Recommended market position:

Do not compete head-on with LeoLabs/Kayhan/Slingshot for live collision avoidance operations.

Instead, position Orbital Inspect as:

- public-data portfolio risk screen,
- evidence-gap intelligence layer,
- pre-underwriting triage system,
- analyst and operator briefing generator,
- public-data monitoring layer for satellite fleets.

## Go / No-Go Recommendation

Go if the product is narrowed to:

> Public-source orbital risk intelligence and evidence triage for satellites.

No-go if the product continues to claim:

> Definitive AI satellite inspection or underwriting-grade loss probability from free web data alone.

That claim is not technically honest and will not survive serious aerospace or insurance diligence.

## Near-Term Implementation Recommendation

Highest-value next phase:

1. Rename the core deliverable from "Inspection Report" to "Public Risk Screen" for free/public-data mode.
2. Add report modes:
   - `PUBLIC_SCREEN`
   - `ENHANCED_TECHNICAL`
   - `UNDERWRITING_GRADE`
3. Add numeric provenance and uncertainty to every physics-derived field.
4. Prevent unsupported LLM estimates, especially physical damage size, power impact, and total-loss probability.
5. Add SGP4/TLE health, public exposure models, and evidence-gap scoring.
6. Make "what data is needed next" a central report deliverable.

## Free/Public Data Boundary

Free/public data is enough for a strong risk screening product:

- CelesTrak GP/TLE/OMM
- NOAA SWPC
- SatNOGS
- UCS satellite metadata, with staleness caveats
- NASA ORDEM/DAS, request-gated but public
- IRENE AE9/AP9/SPM and SPENVIS, free or registration-gated
- Space-Track CDMs, account-gated with redistribution restrictions

Free/public data is not enough for definitive inspection or underwriting-grade probability because these are usually private:

- operator telemetry,
- calibrated close-range imagery and camera metadata,
- spacecraft geometry, attitude, shielding, and material stackups,
- parts-level radiation sensitivity,
- maneuver plans and high-fidelity ephemerides,
- claims, policy, premium, and exclusion data.

## Existing Detailed Backlog

A more detailed improvement backlog was also written to:

`docs/improvements/inspection-functional-core-improvements-2026-04-25.md`
