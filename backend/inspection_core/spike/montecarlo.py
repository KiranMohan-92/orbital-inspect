"""Monte-Carlo ground-truth check for the analytic 2D Pc.

Independent of the analytic quadrature in pc.py: draw samples from the 2D
encounter-plane Gaussian N(miss_2d, cov_2d), count the fraction that land
within HBR of the origin (the hard body). This is the empirical collision
probability and should agree with the analytic Pc.
"""

from __future__ import annotations

import numpy as np


def pc_monte_carlo(
    miss_2d: np.ndarray,
    cov_2d: np.ndarray,
    hbr: float,
    n: int = 200_000,
    seed: int = 1234,
) -> float:
    """Estimate Pc by sampling N(miss_2d, cov_2d) and counting hits in the disk.

    A "hit" (collision) is a sample whose distance from the origin is <= hbr,
    because the hard body sits at the origin and the relative position is
    distributed about the miss vector.
    """
    miss = np.asarray(miss_2d, dtype=float).reshape(2)
    cov = np.asarray(cov_2d, dtype=float).reshape(2, 2)
    hbr = float(hbr)
    if hbr <= 0.0:
        return 0.0

    rng = np.random.default_rng(seed)
    # multivariate_normal samples relative positions distributed about `miss`.
    samples = rng.multivariate_normal(mean=miss, cov=cov, size=n)
    dist2 = samples[:, 0] ** 2 + samples[:, 1] ** 2
    hits = np.count_nonzero(dist2 <= hbr * hbr)
    return hits / float(n)


def pc_monte_carlo_3d(
    miss_3d: np.ndarray,
    cov_3d: np.ndarray,
    rel_vel: np.ndarray,
    hbr: float,
    n: int = 2_000_000,
    seed: int = 1234,
) -> float:
    """Fully independent ground truth: sample the 3D relative position and score
    the in-encounter-plane miss WITHOUT using pc.py's projection.

    This validates the entire analytic path end-to-end — the 3D->2D projection,
    the km^2->m^2 unit handling, AND the integrator — because it shares none of
    that code. A sample "collides" if its distance from the conjunction axis
    (the relative-velocity direction through the origin) is <= hbr, i.e. the
    perpendicular component d_perp^2 = |s|^2 - (s . v_hat)^2 <= hbr^2.
    """
    miss = np.asarray(miss_3d, dtype=float).reshape(3)
    cov = np.asarray(cov_3d, dtype=float).reshape(3, 3)
    v = np.asarray(rel_vel, dtype=float).reshape(3)
    hbr = float(hbr)
    if hbr <= 0.0:
        return 0.0

    v_hat = v / np.linalg.norm(v)
    rng = np.random.default_rng(seed)
    samples = rng.multivariate_normal(mean=miss, cov=cov, size=n)  # (n, 3)
    along = samples @ v_hat                                        # (n,)
    d_perp2 = np.einsum("ij,ij->i", samples, samples) - along * along
    hits = np.count_nonzero(d_perp2 <= hbr * hbr)
    return hits / float(n)
