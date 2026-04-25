# Inspection Functional Core Improvements

Date: 2026-04-25
Scope: Physics, science, and actuarial foundations of the 5-agent inspection pipeline

## Product Boundary

Orbital Inspect can be production-ready with free and public data as a public-source satellite risk screening product. It should not claim definitive satellite inspection, actual spacecraft health, or underwriting-grade loss probability without operator telemetry, calibrated imagery, spacecraft geometry, material/shielding data, and validated actuarial loss data.

Recommended positioning:

> Public-source orbital risk intelligence and evidence triage for satellites.

The system should separate:

- Public Risk Screen: free/open data only, suitable for prioritization and monitoring.
- Enhanced Technical Assessment: gated public tools such as ORDEM, DAS, IRENE, SPENVIS, and Space-Track CDMs.
- Underwriting-Grade Assessment: operator-supplied telemetry, calibrated imagery, geometry, claims/loss data, and human review.

## Review Findings

### Finding 1: Altitude-only debris risk is not physically defensible

File: `backend/services/ordem_service.py`
Lines: 34-48
Priority: P1

Current ORDEM risk is reduced to static altitude bands and a scalar collision probability per square meter. Real MMOD risk depends on orbit epoch, flux by particle size, speed, direction, material density, projected area, shielding, component vulnerability, and mission duration.

Why it matters:

Two spacecraft at the same altitude can have very different MMOD risk because they can differ in area, attitude, shielding, material stack, mission duration, inclination, local debris environment, and exposed critical components.

Future improvement:

Replace static altitude-band scoring with an exposure model:

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

Radiation is bucketed only by altitude using static AE-8/AP-8-style values. Dose and single-event rates require orbit geometry, inclination, South Atlantic Anomaly exposure, epoch and solar cycle, particle spectra, shielding depth, part sensitivity, and confidence bounds.

Why it matters:

Altitude alone cannot support defensible total ionizing dose, displacement damage, or single-event-effect estimates. These are subsystem and part dependent, not just orbit-regime dependent.

Future improvement:

Introduce radiation model outputs with explicit assumptions:

```text
radiation_risk = f(orbit, epoch, solar_cycle, particle_spectrum,
                   shielding_depth, component_sensitivity, exposure_duration)
```

Use IRENE AE9/AP9/SPM, SPENVIS, OMERE-like workflows, or cached model runs with provenance.

### Finding 3: Conjunction risk is scored from miss distance heuristics

File: `backend/services/conjunction_service.py`
Lines: 187-223
Priority: P1

The conjunction service parses miss distance and sometimes probability of collision, then maps them through thresholds. Operational conjunction assessment requires state vectors, covariance, hard-body radius, uncertainty realism, time to closest approach, maneuverability, and a documented probability-of-collision method.

Why it matters:

Miss distance alone is not a risk metric. A large miss distance with high uncertainty can be worse than a smaller miss distance with tight covariance. Probability of collision is only meaningful if the covariance and hard-body assumptions are known.

Future improvement:

Use CCSDS CDM-style records when available and model:

```text
conjunction_risk = f(relative_state_at_TCA, covariance, hard_body_radius,
                     covariance_realism, time_to_TCA, maneuverability)
```

Fallback public-data views should be labeled as "screening only."

### Finding 4: Vision estimates physical damage without a measurement model

File: `backend/prompts/satellite_vision_prompt.txt`
Lines: 20-39
Priority: P1

The prompt asks the model to identify millimeter-scale damage and estimate power impact from arbitrary imagery, but the pipeline does not require range, resolution, focal length, pose, ground sample distance, modulation transfer function, illumination, or component scale.

Why it matters:

Physical size and functional impact cannot be inferred from image pixels alone. A claim like "3 mm crater" is not defensible unless the image measurement chain can resolve that feature.

Future improvement:

Add image measurement gates before accepting physical claims:

```text
resolvable_feature_size = f(range, focal_length, sensor_pitch, image_quality,
                            pose, scale_reference, MTF, illumination)
```

If metadata is absent, constrain output to qualitative findings and evidence-gap requests.

### Finding 5: Insurance probability is not actuarial yet

File: `backend/prompts/insurance_risk_prompt.txt`
Lines: 59-80
Priority: P1

The prompt asks for total loss probability and financial values, but upstream stages do not provide calibrated posterior distributions, component reliability curves, fleet priors, or likelihood functions. The server checks arithmetic consistency, but not scientific validity.

Why it matters:

The current output can look internally consistent while still lacking actuarial grounding. A risk matrix product is not a probability model.

Future improvement:

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

LLM output should explain the model, not invent the probability.

## Target Architecture Improvements

1. Create a deterministic `inspection_core` package that owns all numerical physics and risk calculations.
2. Add a `SpacecraftState` model with epoch, frame, TLE/OMM source, state freshness, propagated state, covariance if available, mass, area, maneuverability, and geometry assumptions.
3. Add SGP4 propagation and validation tests against known ephemeris cases.
4. Replace altitude-band debris summaries with orbit, epoch, area, material, shielding, and duration-aware MMOD exposure.
5. Add ballistic-limit and vulnerability equations for MMOD-to-component damage probability.
6. Replace radiation buckets with model-derived dose-depth, TID, DDD, and SEE estimates.
7. Add thermal exposure modeling using beta angle, eclipse duration, attitude, optical properties, and fatigue curves.
8. Add atmospheric drag and atomic oxygen exposure for LEO assets using solar activity inputs.
9. Add image measurement bounds and reject sub-resolution physical claims.
10. Add Bayesian or reliability-model-based loss probability with explicit priors and likelihoods.
11. Require all numeric report fields to include value, units, source, method, epoch, uncertainty, and assumptions.

## Free/Public Data Feasibility

Free and public data is enough for a strong public risk screening product:

- CelesTrak GP/TLE/OMM for public orbital elements.
- NOAA SWPC for space weather.
- SatNOGS for public RF observations.
- UCS satellite database for public reference metadata, with staleness caveats.
- NASA ORDEM and DAS, request-gated but public.
- IRENE AE9/AP9/SPM and SPENVIS, free or registration-gated.
- Space-Track CDMs, account-gated with redistribution restrictions.

Free/public data is not enough for definitive inspection or underwriting-grade probability because the following are usually private:

- Operator telemetry.
- Calibrated close-range imagery and camera metadata.
- Spacecraft geometry, attitude, shielding, and material stackups.
- Parts-level radiation sensitivity.
- Maneuver plans and high-fidelity ephemerides.
- Claims, loss, policy, premium, and exclusion data.

## Implementation Priority

First production-worthy milestone:

1. Rename and frame outputs as public-data screening.
2. Add numeric provenance and uncertainty to every physics-derived field.
3. Build `SpacecraftState` and SGP4 propagation.
4. Add evidence-gap enforcement for unavailable telemetry, calibrated imagery, covariance, and geometry.
5. Downgrade unsupported outputs from "estimate" to "not determinable from public data."

This keeps the product technically honest while making the free-data tier genuinely useful.
