"""Production collision-probability service for buyer-supplied CDMs.

Wraps the deterministic Foster/Akella-Alfriend 2D Pc engine. The LLM is
never in this path. Missing or non-PSD covariance returns NULL (None), never 0.0.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from inspection_core.spike.cdm import Cdm, parse_cdm_kvn
from inspection_core.spike.pc import (
    DEFAULT_HBR_M,
    compute_pc_from_cdm,
    is_positive_semidefinite,
)

METHOD_NAME = "foster_akella_alfriend_2d"


@dataclass(frozen=True)
class PcComputation:
    """Fail-closed Pc result used by the Evidence Pack."""

    collision_probability: Optional[float]
    null_reason: Optional[str]
    method: str
    hard_body_radius_m: Optional[float]
    covariance_quality: str
    tca: Optional[str]
    miss_distance_m: Optional[float]
    primary_designator: Optional[str]
    secondary_designator: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _diagnose_null(cdm: Cdm) -> str:
    cov1 = cdm.sat1.position_covariance_rtn()
    cov2 = cdm.sat2.position_covariance_rtn()
    if cov1 is None or cov2 is None:
        missing = []
        if cov1 is None:
            missing.append("OBJECT1 RTN position covariance")
        if cov2 is None:
            missing.append("OBJECT2 RTN position covariance")
        return (
            "Pc is NULL because required covariance is missing: "
            + ", ".join(missing)
            + ". A Conjunction Data Message must include the CR_R/CT_T/CN_N "
            "lower-triangle for both objects."
        )
    combined = cov1 + cov2
    if not is_positive_semidefinite(combined):
        return (
            "Pc is NULL because the combined RTN position covariance is not "
            "positive-semidefinite. Starlink Space Safety and NASA CARA treat "
            "non-PSD covariance as a failed calculation, not as Pc = 0."
        )
    if cdm.relative_position_rtn_m is None:
        return (
            "Pc is NULL because relative position (RELATIVE_POSITION_R/T/N) "
            "is missing from the CDM."
        )
    vel_components = (
        cdm.sat1.x_dot,
        cdm.sat1.y_dot,
        cdm.sat1.z_dot,
        cdm.sat2.x_dot,
        cdm.sat2.y_dot,
        cdm.sat2.z_dot,
    )
    if any(v is None for v in vel_components):
        return "Pc is NULL because one or both state-vector velocities are missing."
    return (
        "Pc is NULL because the encounter-plane covariance is degenerate or "
        "the hard-body radius is not usable."
    )


def _resolved_hbr(cdm: Cdm, hbr: Optional[float]) -> Optional[float]:
    if hbr is not None:
        return float(hbr)
    if cdm.hard_body_radius_m is not None:
        return float(cdm.hard_body_radius_m)
    return float(DEFAULT_HBR_M)


def compute_pc_from_cdm_text(
    cdm_text: str,
    hbr: Optional[float] = None,
) -> PcComputation:
    """Parse a CCSDS CDM (KVN) and compute Pc or return NULL with a written reason."""
    if not (cdm_text or "").strip():
        return PcComputation(
            collision_probability=None,
            null_reason="Pc is NULL because no CDM text was supplied.",
            method=METHOD_NAME,
            hard_body_radius_m=hbr,
            covariance_quality="absent",
            tca=None,
            miss_distance_m=None,
            primary_designator=None,
            secondary_designator=None,
        )

    cdm = parse_cdm_kvn(cdm_text)
    resolved_hbr = _resolved_hbr(cdm, hbr)
    pc = compute_pc_from_cdm(cdm, hbr=resolved_hbr)

    if pc is None:
        quality = "missing"
        cov1 = cdm.sat1.position_covariance_rtn()
        cov2 = cdm.sat2.position_covariance_rtn()
        if cov1 is not None and cov2 is not None and not is_positive_semidefinite(cov1 + cov2):
            quality = "non_psd"
        return PcComputation(
            collision_probability=None,
            null_reason=_diagnose_null(cdm),
            method=METHOD_NAME,
            hard_body_radius_m=resolved_hbr,
            covariance_quality=quality,
            tca=cdm.tca,
            miss_distance_m=cdm.miss_distance_m,
            primary_designator=cdm.sat1.object_designator,
            secondary_designator=cdm.sat2.object_designator,
        )

    return PcComputation(
        collision_probability=float(pc),
        null_reason=None,
        method=METHOD_NAME,
        hard_body_radius_m=resolved_hbr,
        covariance_quality="usable_psd",
        tca=cdm.tca,
        miss_distance_m=cdm.miss_distance_m,
        primary_designator=cdm.sat1.object_designator,
        secondary_designator=cdm.sat2.object_designator,
    )
