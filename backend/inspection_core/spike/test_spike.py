"""Spike tests: CDM parsing + analytic Pc vs Monte-Carlo + fail-closed behaviour.

Run from backend/:
    .venv/bin/python -m pytest inspection_core/spike/test_spike.py -q
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from inspection_core.spike.cdm import parse_cdm_kvn
from inspection_core.spike.pc import (
    combined_position_covariance,
    project_to_encounter_plane,
    compute_pc_2d,
    compute_pc_from_cdm,
    is_positive_semidefinite,
)
from inspection_core.spike.montecarlo import pc_monte_carlo, pc_monte_carlo_3d


SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "sample_cdm.txt")

# Hard-body radius used for the correctness proof (metres). Large enough that
# the analytic vs MC comparison is statistically stable at the sample geometry.
HBR_M = 25.0


def _load_sample():
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return parse_cdm_kvn(f.read())


# --------------------------------------------------------------------------- #
# (a) parsing
# --------------------------------------------------------------------------- #
def test_parse_sample_cdm():
    cdm = _load_sample()
    assert cdm.ccsds_cdm_vers == "1.0"
    assert cdm.tca == "2026-06-01T12:34:56.789"
    assert cdm.miss_distance_m == pytest.approx(184.0)
    assert cdm.relative_speed_m_s == pytest.approx(14820.0)

    # Relative position RTN parsed into a 3-vector (metres).
    assert cdm.relative_position_rtn_m is not None
    np.testing.assert_allclose(
        cdm.relative_position_rtn_m, [40.0, 30.0, 178.0]
    )

    # Object designators / names.
    assert cdm.sat1.object_designator == "25544"
    assert cdm.sat2.object_designator == "39208"

    # A representative covariance term parses correctly (km^2).
    assert cdm.sat1.ct_t == pytest.approx(9.0e-03)
    assert cdm.sat2.cn_n == pytest.approx(1.6e-02)

    # Covariance assembles into a symmetric 3x3 PSD matrix.
    cov1 = cdm.sat1.position_covariance_rtn()
    assert cov1 is not None
    np.testing.assert_allclose(cov1, cov1.T)
    assert is_positive_semidefinite(cov1)


# --------------------------------------------------------------------------- #
# (b) KEY PROOF: analytic Pc ≈ Monte-Carlo Pc
# --------------------------------------------------------------------------- #
def test_analytic_matches_monte_carlo():
    cdm = _load_sample()

    cov1 = cdm.sat1.position_covariance_rtn()
    cov2 = cdm.sat2.position_covariance_rtn()
    cov_comb = combined_position_covariance(cov1, cov2)  # km^2

    # Convert covariance km^2 -> m^2 so it is consistent with metre geometry.
    cov_comb_m2 = cov_comb * 1.0e6

    rel_pos_m = cdm.relative_position_rtn_m  # metres
    v1 = np.array([cdm.sat1.x_dot, cdm.sat1.y_dot, cdm.sat1.z_dot])
    v2 = np.array([cdm.sat2.x_dot, cdm.sat2.y_dot, cdm.sat2.z_dot])
    rel_vel = v1 - v2  # km/s; only its direction matters for the plane

    miss_2d, cov_2d = project_to_encounter_plane(rel_pos_m, rel_vel, cov_comb_m2)

    pc_analytic = compute_pc_2d(miss_2d, cov_2d, HBR_M)
    # (1) 2D MC on the projected plane: validates the integrator (shares projection).
    pc_mc = pc_monte_carlo(miss_2d, cov_2d, HBR_M, n=2_000_000, seed=20260531)
    # (2) INDEPENDENT 3D MC: samples full 3D rel-position, scores by perpendicular
    #     distance to the velocity axis. Shares NONE of pc.py's projection/units
    #     code, so it validates the analytic path end-to-end (non-circular).
    pc_mc_3d = pc_monte_carlo_3d(
        rel_pos_m, cov_comb_m2, rel_vel, HBR_M, n=2_000_000, seed=20260531
    )

    assert pc_analytic > 0.0
    assert pc_mc > 0.0
    assert pc_mc_3d > 0.0

    rel_err = abs(pc_analytic - pc_mc) / pc_mc
    assert rel_err < 0.12, (
        f"analytic={pc_analytic:.6e} mc2d={pc_mc:.6e} rel_err={rel_err:.4f}"
    )
    # The non-circular check: independent 3D MC must also agree.
    rel_err_3d = abs(pc_analytic - pc_mc_3d) / pc_mc_3d
    assert rel_err_3d < 0.12, (
        f"analytic={pc_analytic:.6e} mc3d={pc_mc_3d:.6e} rel_err={rel_err_3d:.4f}"
    )


# --------------------------------------------------------------------------- #
# (c) fail-closed: missing covariance -> None
# --------------------------------------------------------------------------- #
def test_fail_closed_missing_covariance():
    cdm = _load_sample()
    # Strip one covariance term from object2 -> covariance becomes absent.
    cdm.sat2.cn_n = None
    assert cdm.sat2.position_covariance_rtn() is None
    assert compute_pc_from_cdm(cdm, hbr=HBR_M) is None


# --------------------------------------------------------------------------- #
# (d) fail-closed: non-PSD covariance -> None
# --------------------------------------------------------------------------- #
def test_fail_closed_non_psd():
    cdm = _load_sample()
    # Inject a covariance with a guaranteed negative eigenvalue into object1:
    # a strongly off-diagonal-dominant matrix (|CT_R| >> sqrt(CR_R*CT_T)).
    cdm.sat1.cr_r = 1.0e-04
    cdm.sat1.ct_t = 1.0e-04
    cdm.sat1.ct_r = 1.0e-02  # huge cross term -> negative eigenvalue
    cdm.sat1.cn_r = 0.0
    cdm.sat1.cn_t = 0.0
    cdm.sat1.cn_n = 1.0e-04

    cov1 = cdm.sat1.position_covariance_rtn()
    assert cov1 is not None
    assert not is_positive_semidefinite(cov1)  # confirm we built a non-PSD matrix

    assert compute_pc_from_cdm(cdm, hbr=HBR_M) is None


# --------------------------------------------------------------------------- #
# (e) sanity: larger miss distance => strictly smaller Pc
# --------------------------------------------------------------------------- #
def test_larger_miss_gives_smaller_pc():
    cdm = _load_sample()
    cov1 = cdm.sat1.position_covariance_rtn()
    cov2 = cdm.sat2.position_covariance_rtn()
    cov_comb_m2 = combined_position_covariance(cov1, cov2) * 1.0e6

    rel_pos_m = cdm.relative_position_rtn_m
    v1 = np.array([cdm.sat1.x_dot, cdm.sat1.y_dot, cdm.sat1.z_dot])
    v2 = np.array([cdm.sat2.x_dot, cdm.sat2.y_dot, cdm.sat2.z_dot])
    rel_vel = v1 - v2

    miss_2d, cov_2d = project_to_encounter_plane(rel_pos_m, rel_vel, cov_comb_m2)

    pc_near = compute_pc_2d(miss_2d, cov_2d, HBR_M)
    # Push the miss vector 3x farther out in the encounter plane.
    pc_far = compute_pc_2d(miss_2d * 3.0, cov_2d, HBR_M)

    assert pc_far < pc_near
    assert pc_near > 0.0
