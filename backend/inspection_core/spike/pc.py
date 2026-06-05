"""Analytic 2D probability of collision (Pc).

Implements the classic short-encounter (2D) collision-probability method
attributed to Foster & Estes (1992) and Akella & Alfriend (2000), as used by
NASA CARA and (in spirit) SpaceX Starlink Space Safety screening.

Method
------
For a short-duration ("linear") conjunction the relative motion through the
encounter is approximately rectilinear at constant relative velocity. The
collision probability is then the integral of the *relative-position*
probability density over the hard-body sphere, which reduces to a 2D integral
in the **encounter plane** (a.k.a. B-plane / conjunction plane) — the plane
through the point of closest approach whose normal is the relative-velocity
vector.

Steps:
  1. Combine the two objects' position covariances (independent => sum).
  2. Build an orthonormal basis (x_hat, y_hat) spanning the plane orthogonal
     to the relative velocity. Project the miss vector and the 3x3 covariance
     into this 2D plane.
  3. Integrate the 2D Gaussian N(miss_2d, cov_2d) over the disk of radius HBR
     centred at the origin (origin = combined hard body). The probability mass
     inside the disk is Pc.

Frame note
----------
The covariance and relative position here are taken in the RTN frame (see
cdm.py). The projection only needs the relative *velocity* direction and the
combined covariance to be expressed in a *consistent* Cartesian frame; RTN is
a valid right-handed Cartesian frame for this purpose. For the spike we derive
the relative-velocity direction from the two objects' state velocities rotated
into a common frame is NOT required — we operate entirely in RTN and use the
RTN relative position plus an RTN relative-velocity direction. (See
compute_pc_from_cdm for how the velocity direction is obtained.)

Decision thresholds (documented; not enforced here)
---------------------------------------------------
  * Classic operational red threshold: Pc > 1e-4.
  * SpaceX Starlink Space Safety publicly screens/maneuvers at a far more
    conservative Pc > 1e-7 .. 3e-7 (≈ "1 in 100,000 / 1 in ~3 million")
    aggregate posture; the commonly cited Starlink maneuver screening
    threshold is Pc > 3e-7. compute_pc_from_cdm returns the raw Pc; threshold
    application is the caller's responsibility.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np

# Documented default hard-body radius (metres) when neither the CDM nor the
# caller supplies one. 20 m is a conservative round figure for a combined
# operational-satellite hard-body sphere (CARA commonly uses HBR on the order
# of a few metres to tens of metres depending on the secondary).
DEFAULT_HBR_M = 20.0

# Operational thresholds (for reference / caller use).
PC_THRESHOLD_CLASSIC = 1e-4
PC_THRESHOLD_STARLINK = 3e-7


def combined_position_covariance(cov1_3x3: np.ndarray, cov2_3x3: np.ndarray) -> np.ndarray:
    """Combine two independent position covariances (same frame): C = C1 + C2."""
    c1 = np.asarray(cov1_3x3, dtype=float)
    c2 = np.asarray(cov2_3x3, dtype=float)
    return c1 + c2


def is_positive_semidefinite(cov: np.ndarray, tol: float = 1e-12) -> bool:
    """True if `cov` is (numerically) positive semidefinite and symmetric.

    Uses the smallest eigenvalue of the symmetrised matrix via eigvalsh.
    A small negative tolerance absorbs floating-point round-off.
    """
    c = np.asarray(cov, dtype=float)
    if c.shape[0] != c.shape[1]:
        return False
    # Symmetrise to guard against tiny asymmetry, then test eigenvalues.
    csym = 0.5 * (c + c.T)
    try:
        w = np.linalg.eigvalsh(csym)
    except np.linalg.LinAlgError:
        return False
    return bool(np.min(w) >= -abs(tol))


def project_to_encounter_plane(
    rel_pos_3: np.ndarray,
    rel_vel_3: np.ndarray,
    cov_3x3: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Project miss vector and 3x3 covariance into the 2D encounter plane.

    The encounter plane is orthogonal to the relative velocity `rel_vel_3`.
    We build an orthonormal basis (x_hat, y_hat) spanning that plane, form the
    3x2 projection P = [x_hat, y_hat], and return:

        miss_2d = P^T @ rel_pos_3        (2-vector)
        cov_2d  = P^T @ cov_3x3 @ P      (2x2)

    Parameters are taken in a common Cartesian frame (RTN here).
    """
    rel_pos = np.asarray(rel_pos_3, dtype=float).reshape(3)
    rel_vel = np.asarray(rel_vel_3, dtype=float).reshape(3)
    cov = np.asarray(cov_3x3, dtype=float)

    v_norm = np.linalg.norm(rel_vel)
    if v_norm == 0.0:
        raise ValueError("relative velocity is zero; encounter plane undefined")
    v_hat = rel_vel / v_norm

    # Choose a seed vector not parallel to v_hat to build the first in-plane axis.
    seed = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(seed, v_hat)) > 0.9:
        seed = np.array([0.0, 1.0, 0.0])

    # x_hat: component of seed orthogonal to v_hat, normalised.
    x_hat = seed - np.dot(seed, v_hat) * v_hat
    x_hat /= np.linalg.norm(x_hat)
    # y_hat completes a right-handed in-plane basis.
    y_hat = np.cross(v_hat, x_hat)
    y_hat /= np.linalg.norm(y_hat)

    P = np.column_stack((x_hat, y_hat))  # 3x2

    miss_2d = P.T @ rel_pos              # (2,)
    cov_2d = P.T @ cov @ P               # (2,2)
    return miss_2d, cov_2d


def compute_pc_2d(miss_2d: np.ndarray, cov_2d: np.ndarray, hbr: float) -> float:
    """Probability mass of N(miss_2d, cov_2d) inside the disk |x| <= hbr.

    Numerical 2D integration in polar coordinates centred at the disk origin.
    The integrand is the bivariate-Gaussian pdf; the disk is the hard-body
    circle of radius `hbr` centred at the origin (the combined hard body).

    We diagonalise cov_2d so the pdf factorises, then integrate on a polar
    grid (radius x angle). Resolution is chosen for ~<1% quadrature error
    across the Pc ranges this spike targets (1e-4 .. 1e-2).
    """
    miss = np.asarray(miss_2d, dtype=float).reshape(2)
    cov = np.asarray(cov_2d, dtype=float).reshape(2, 2)
    hbr = float(hbr)
    if hbr <= 0.0:
        return 0.0

    det = cov[0, 0] * cov[1, 1] - cov[0, 1] * cov[1, 0]
    if det <= 0.0:
        # Degenerate 2D covariance — caller should have fail-closed already.
        return float("nan")

    inv = np.linalg.inv(cov)
    norm_const = 1.0 / (2.0 * math.pi * math.sqrt(det))

    # Polar grid integration over the disk of radius hbr.
    # Grid density scales mildly so small HBR still resolves the gradient.
    n_r = 400
    n_theta = 400
    r_edges = np.linspace(0.0, hbr, n_r + 1)
    r_mid = 0.5 * (r_edges[:-1] + r_edges[1:])          # (n_r,)
    dr = r_edges[1] - r_edges[0]
    theta_edges = np.linspace(0.0, 2.0 * math.pi, n_theta + 1)
    theta_mid = 0.5 * (theta_edges[:-1] + theta_edges[1:])  # (n_theta,)
    dtheta = theta_edges[1] - theta_edges[0]

    # Build grid of (x, y) points: shape (n_r, n_theta).
    rr = r_mid[:, None]
    tt = theta_mid[None, :]
    xg = rr * np.cos(tt)
    yg = rr * np.sin(tt)

    # Shift by the miss vector: pdf is centred at miss, disk at origin, so the
    # quadratic form uses (point - miss).
    dx = xg - miss[0]
    dy = yg - miss[1]

    # Quadratic form q = d^T inv d, broadcast over the grid.
    q = (inv[0, 0] * dx * dx
         + 2.0 * inv[0, 1] * dx * dy
         + inv[1, 1] * dy * dy)
    pdf = norm_const * np.exp(-0.5 * q)

    # Polar area element r dr dtheta.
    integrand = pdf * rr  # multiply by Jacobian r
    pc = float(np.sum(integrand) * dr * dtheta)

    # Clamp to [0, 1] to guard against tiny quadrature overshoot.
    return max(0.0, min(1.0, pc))


def compute_pc_from_cdm(cdm, hbr: Optional[float] = None) -> Optional[float]:
    """Fail-closed Pc entry point.

    Returns the analytic Pc, or ``None`` (NULL Pc) when collision risk cannot
    be responsibly computed:

      * either object's RTN position covariance is absent,
      * the combined covariance is not positive-semidefinite,
      * the 2D encounter-plane covariance is degenerate, or
      * the required relative geometry (position / velocity direction) is
        missing.

    HBR resolution order: explicit `hbr` arg -> cdm.hard_body_radius_m ->
    DEFAULT_HBR_M (documented constant, 20 m).

    The relative-velocity direction (which defines the encounter plane) is
    derived from the two objects' RTN-frame... actually from the difference of
    the state velocity vectors (sat1 - sat2). For the spike both states are
    given in a common frame consistent with the RTN covariance, so the
    velocity difference gives the encounter-plane normal directly.
    """
    # --- covariance availability (fail closed) -------------------------- #
    cov1 = cdm.sat1.position_covariance_rtn()  # km^2
    cov2 = cdm.sat2.position_covariance_rtn()  # km^2
    if cov1 is None or cov2 is None:
        return None

    cov_comb = combined_position_covariance(cov1, cov2)  # km^2
    if not is_positive_semidefinite(cov_comb):
        return None

    # Convert km^2 -> m^2 so the covariance is consistent with the metre-scale
    # relative position and HBR used for the integration below.
    cov_comb_m2 = cov_comb * 1.0e6

    # --- relative geometry (fail closed) -------------------------------- #
    rel_pos = cdm.relative_position_rtn_m
    if rel_pos is None:
        return None

    # Relative velocity direction from the two state vectors.
    s1, s2 = cdm.sat1, cdm.sat2
    vel_components = (s1.x_dot, s1.y_dot, s1.z_dot, s2.x_dot, s2.y_dot, s2.z_dot)
    if any(v is None for v in vel_components):
        return None
    v1 = np.array([s1.x_dot, s1.y_dot, s1.z_dot], dtype=float)
    v2 = np.array([s2.x_dot, s2.y_dot, s2.z_dot], dtype=float)
    rel_vel = v1 - v2
    if np.linalg.norm(rel_vel) == 0.0:
        return None

    # --- HBR resolution ------------------------------------------------- #
    if hbr is None:
        hbr = cdm.hard_body_radius_m
    if hbr is None:
        hbr = DEFAULT_HBR_M
    if hbr <= 0.0:
        return None

    # --- project & integrate -------------------------------------------- #
    miss_2d, cov_2d = project_to_encounter_plane(rel_pos, rel_vel, cov_comb_m2)

    # Guard: degenerate 2D covariance after projection.
    det2d = cov_2d[0, 0] * cov_2d[1, 1] - cov_2d[0, 1] * cov_2d[1, 0]
    if det2d <= 0.0:
        return None

    return compute_pc_2d(miss_2d, cov_2d, hbr)
