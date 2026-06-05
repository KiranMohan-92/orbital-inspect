# SPIKE: CCSDS CDM + Pc-from-covariance

**Status:** spike / proof-of-moat. Self-contained. Touches no production code.
**Built + independently verified:** 2026-05-31 (builder agent + adversarial verifier agent).

## Why this exists

Orbital Inspect's authority gate already *names* `covariance_cdm_quality` as a required
evidence class (`backend/services/assessment_mode_service.py`), but there was **no engine behind
the gate** — collision probability was read-through from a SOCRATES column
(`conjunction_service.py:199`), never computed; there was no CCSDS parsing and no covariance math.
This spike proves the moat — standards-native conjunction screening that NASA CARA / SpaceX
Starlink Space Safety would recognize — is buildable.

## What is PROVEN here

| Capability | File | Evidence |
|---|---|---|
| Parse a CCSDS CDM (508.0-B) in KVN | `cdm.py` | `test_parse_sample_cdm` |
| Compute 2D Pc (Foster / Akella-Alfriend short-encounter) | `pc.py` | `test_analytic_matches_monte_carlo` |
| **Analytic Pc validated vs Monte-Carlo** | `pc.py` + `montecarlo.py` | analytic `1.6770e-2` vs **independent 3D MC** `~1.680e-2` (≈0.2%) and 2D MC `1.663e-2` |
| **Fail closed: NULL Pc when covariance missing** | `pc.py::compute_pc_from_cdm` | `test_fail_closed_missing_covariance` (returns `None`, not `0.0`) |
| **Fail closed: NULL Pc when covariance non-PSD** | `pc.py::is_positive_semidefinite` | `test_fail_closed_non_psd` (negative eigenvalue → `None`) |
| Monotonic sanity (larger miss → smaller Pc) | `pc.py` | `test_larger_miss_gives_smaller_pc` |

This mirrors the real **Starlink Space Safety** rule: `COLLISION_PROBABILITY` is NULL when
covariance is absent or non-positive-semidefinite. Documented thresholds: classic operational
red line `Pc > 1e-4`; Starlink maneuver-screening `Pc > 3e-7`. (Thresholds are *not* enforced
here — `compute_pc_from_cdm` returns the raw Pc or `None`; policy stays with the caller.)

Run:
```bash
cd backend && .venv/bin/python -m pytest inspection_core/spike/test_spike.py -q   # 5 passed
```

### Why the Pc number is trustworthy (non-circular)
Test (b) checks the analytic Pc against **two** Monte-Carlos: a 2D MC on the projected plane
(validates the integrator) and a **3D MC that samples the full relative position and scores by
perpendicular distance to the velocity axis** (`pc_monte_carlo_3d`) — it shares none of `pc.py`'s
projection or unit-conversion code, so it validates the analytic path end-to-end. An adversarial
reviewer's fully independent quadrature matched to 7 significant figures.

## What is NOT production-ready (honest gaps before this leaves spike status)

1. **Per-object frame rotation.** Each object's RTN covariance is in its *own* RTN frame; the spike
   sums them directly. Production must rotate both to a common frame (RIC→ECI or a shared encounter
   frame) before combining. Correct for the synthetic fixture; a known simplification otherwise.
2. **Velocity-frame consistency.** The encounter plane uses the RTN relative-velocity *direction*;
   production needs the state velocity and covariance in mutually consistent frames.
3. **HBR provenance.** Defaults to `DEFAULT_HBR_M = 20.0 m` when absent; production must source the
   hard-body radius per object (or sum of radii) with provenance.
4. **Degenerate sentinels.** `compute_pc_2d` returns `nan` on degenerate 2D covariance while
   `compute_pc_from_cdm` guards with `None`; unify on the fail-closed `None`.
5. **Only short-encounter 2D Pc.** Long-encounter / non-linear-relative-motion cases (e.g. some
   GEO or low-relative-velocity conjunctions) need a different method.
6. **No XML (NDM) CDM, no OEM/OMM ingestion, no SP propagation** — those are the next moat pieces.

## Provenance
Built by an Opus builder agent; independently re-verified by a separate Opus adversarial agent
(verdict: CONFIRMED-with-caveats; independent Pc agreed to 0.19% MC / 7 sig-figs quadrature).
See `docs/improvements/NASA-READINESS-GAMEPLAN-2026-05-30.md` §4 (the moat) and §9 Phase 1-2.
