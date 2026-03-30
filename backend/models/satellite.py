"""Satellite domain models for Orbital Inspect."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class OrbitalRegime(str, Enum):
    LEO = "LEO"       # Low Earth Orbit (200-2000km)
    MEO = "MEO"       # Medium Earth Orbit (2000-35786km)
    GEO = "GEO"       # Geostationary (35786km)
    HEO = "HEO"       # Highly Elliptical Orbit
    SSO = "SSO"       # Sun-Synchronous Orbit
    UNKNOWN = "UNKNOWN"


class SatelliteType(str, Enum):
    COMMUNICATIONS = "communications"
    EARTH_OBSERVATION = "earth_observation"
    NAVIGATION = "navigation"
    SCIENTIFIC = "scientific"
    WEATHER = "weather"
    MILITARY = "military"
    TECHNOLOGY_DEMO = "technology_demo"
    MEGA_CONSTELLATION = "mega_constellation"
    SPACE_STATION = "space_station"
    OTHER = "other"


class SatelliteTarget(BaseModel):
    """Target satellite for condition assessment."""
    id: str
    name: str | None = None
    norad_id: str | None = None
    cospar_id: str | None = None
    operator: str | None = None
    satellite_type: str = "other"
    bus_platform: str | None = None
    orbital_regime: str = "UNKNOWN"
    altitude_km: float | None = None
    inclination_deg: float | None = None
    launch_date: str | None = None
    design_life_years: float | None = None
    age_years: float | None = None
    mass_kg: float | None = None
    power_watts: float | None = None
    expected_components: list[str] = []
    insured: bool | None = None
    insured_value_usd: float | None = None


class ClassificationResult(BaseModel):
    """Output of the Orbital Classification Agent."""
    valid: bool = True
    rejection_reason: str | None = None
    satellite_type: str = "other"
    bus_platform: str | None = None
    orbital_regime: str = "UNKNOWN"
    expected_components: list[str] = []
    design_life_years: float | None = None
    estimated_age_years: float | None = None
    operator: str | None = None
    notes: str = ""
    degraded: bool = False


class SatelliteDamageItem(BaseModel):
    """Individual damage finding on a satellite."""
    id: int
    type: str                           # micrometeorite_crater, cell_degradation, thermal_blanket_damage, etc.
    description: str
    bounding_box: list[int]             # [y_min, x_min, y_max, x_max] normalized 0-1000
    label: str                          # Short label for overlay (max 5 words)
    severity: str                       # MINOR | MODERATE | SEVERE | CRITICAL
    confidence: float                   # 0.0-1.0
    uncertain: bool = False
    estimated_power_impact_pct: float = 0.0  # Estimated power loss from this damage


class SatelliteDamagesAssessment(BaseModel):
    """Output of the Satellite Vision Agent."""
    damages: list[SatelliteDamageItem] = []
    overall_pattern: str = ""           # e.g., "cumulative micrometeorite bombardment"
    overall_severity: str = "MINOR"
    overall_confidence: float = 0.0
    total_power_impact_pct: float = 0.0
    healthy_areas_noted: str = ""
    component_assessed: str = ""        # Which component was analyzed (solar_array, antenna, bus)
    degraded: bool = False


class OrbitalStressor(BaseModel):
    """Environmental stressor in the orbital environment."""
    name: str
    severity: str                       # LOW | MEDIUM | HIGH
    measured_value: str = ""
    description: str = ""
    source: str = ""


class OrbitalEnvironmentAnalysis(BaseModel):
    """Output of the Orbital Environment Agent."""
    orbital_regime: str = ""
    altitude_km: float | None = None
    inclination_deg: float | None = None
    debris_flux_density: str = ""       # particles/m²/year at this altitude
    collision_probability: str = ""     # per year
    radiation_dose_rate: str = ""       # rad/year
    thermal_cycling_range: str = ""     # e.g., "-150°C to +150°C"
    atomic_oxygen_flux: str = ""        # atoms/cm²/s
    stressors: list[OrbitalStressor] = []
    accelerating_factors: list[str] = []
    mitigating_factors: list[str] = []
    data_sources: list[str] = []
    degraded: bool = False


class SatellitePrecedent(BaseModel):
    """Historical satellite failure/damage precedent."""
    event: str
    satellite: str = ""
    operator: str = ""
    year: str = ""
    outcome: str = ""
    claim_amount_usd: str = ""
    relevance: str = ""
    source: str = ""


class SatelliteFailureModeAnalysis(BaseModel):
    """Output of the Satellite Failure Mode Agent."""
    failure_mode: str = ""
    mechanism: str = ""
    root_cause_chain: list[str] = []
    progression_rate: str = "MODERATE"
    power_degradation_estimate_pct: float = 0.0
    remaining_life_revision_years: float | None = None
    time_to_critical: str = ""
    historical_precedents: list[SatellitePrecedent] = []
    degraded: bool = False


class RiskMatrixDimension(BaseModel):
    score: int                          # 1-5
    reasoning: str = ""


class RiskMatrix(BaseModel):
    severity: RiskMatrixDimension
    probability: RiskMatrixDimension
    consequence: RiskMatrixDimension
    composite: int                      # 1-125


class ConsistencyCheck(BaseModel):
    passed: bool = True
    anomalies: list[str] = []
    confidence_adjustment: str = ""


class UnderwritingRecommendation(str, Enum):
    INSURABLE_STANDARD = "INSURABLE_STANDARD"
    INSURABLE_ELEVATED_PREMIUM = "INSURABLE_ELEVATED_PREMIUM"
    INSURABLE_WITH_EXCLUSIONS = "INSURABLE_WITH_EXCLUSIONS"
    FURTHER_INVESTIGATION = "FURTHER_INVESTIGATION"
    UNINSURABLE = "UNINSURABLE"


class InsuranceRiskReport(BaseModel):
    """Output of the Insurance Risk Agent — the key differentiator."""
    consistency_check: ConsistencyCheck
    risk_matrix: RiskMatrix
    risk_tier: str                      # LOW | MEDIUM | MEDIUM-HIGH | HIGH | CRITICAL

    # Insurance-specific metrics
    estimated_remaining_life_years: float | None = None
    power_margin_percentage: float | None = None
    annual_degradation_rate_pct: float | None = None
    replacement_cost_usd: float | None = None
    depreciated_value_usd: float | None = None
    revenue_at_risk_annual_usd: float | None = None
    total_loss_probability: float | None = None  # 0.0-1.0 over remaining life

    underwriting_recommendation: str = "FURTHER_INVESTIGATION"
    recommendation_rationale: str = ""
    recommended_actions: list[dict] = []
    worst_case_scenario: str = ""
    summary: str = ""
    degraded: bool = False
    evidence_gaps: list[str] = []
    report_completeness: str = "COMPLETE"


class SatelliteConditionReport(BaseModel):
    """Full Satellite Condition Report — the product deliverable."""
    target: SatelliteTarget
    classification: ClassificationResult
    vision: SatelliteDamagesAssessment | None = None
    environment: OrbitalEnvironmentAnalysis | None = None
    failure_mode: SatelliteFailureModeAnalysis | None = None
    insurance_risk: InsuranceRiskReport | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    report_version: str = "1.0"
