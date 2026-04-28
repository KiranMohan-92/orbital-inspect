"""Spacecraft state contracts for deterministic public-risk screening."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import find_spec
from typing import Literal

from pydantic import BaseModel, Field


class PropagationCapability(BaseModel):
    method: Literal["SGP4", "UNAVAILABLE"] = "UNAVAILABLE"
    available: bool = False
    reason: str = "sgp4 package is not installed"


class SpacecraftState(BaseModel):
    """Minimum state required before numerical orbital risk models can be trusted."""

    object_id: str
    epoch: datetime
    frame: str = "TEME"
    tle_line1: str | None = None
    tle_line2: str | None = None
    omm_source: str | None = None
    state_freshness_hours: float | None = Field(default=None, ge=0.0)
    propagated_state_km: tuple[float, float, float] | None = None
    propagated_velocity_km_s: tuple[float, float, float] | None = None
    covariance_available: bool = False
    mass_kg: float | None = Field(default=None, gt=0.0)
    projected_area_m2: float | None = Field(default=None, gt=0.0)
    maneuverability: Literal["unknown", "none", "limited", "active"] = "unknown"
    geometry_assumptions: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)

    @property
    def is_fresh(self) -> bool:
        return self.state_freshness_hours is not None and self.state_freshness_hours <= 24.0

    @classmethod
    def from_tle(
        cls,
        *,
        object_id: str,
        tle_line1: str,
        tle_line2: str,
        epoch: datetime | None = None,
    ) -> "SpacecraftState":
        now = datetime.now(timezone.utc)
        epoch = epoch or now
        freshness = max(0.0, (now - epoch).total_seconds() / 3600.0)
        return cls(
            object_id=object_id,
            epoch=epoch,
            tle_line1=tle_line1,
            tle_line2=tle_line2,
            state_freshness_hours=freshness,
            covariance_available=False,
            uncertainty_notes=[
                "TLE/OMM public state has no covariance by default",
                "SGP4 propagation must be available before propagated state is populated",
            ],
        )


def propagation_capability() -> PropagationCapability:
    if find_spec("sgp4") is None:
        return PropagationCapability()
    return PropagationCapability(method="SGP4", available=True, reason="")
