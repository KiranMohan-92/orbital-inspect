"""Satellite domain models for Orbital Inspect."""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, Optional
from datetime import datetime, timezone
from enum import Enum
from models.provenance import (
    ConfidenceCalibration, FinancialEstimate,
    LossProbabilityDerivation, SensitivityAnalysis, FieldProvenance,
    ProbabilityComponent,
)


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


class AssessmentMode(str, Enum):
    PUBLIC_SCREEN = "PUBLIC_SCREEN"
    ENHANCED_TECHNICAL = "ENHANCED_TECHNICAL"
    UNDERWRITING_GRADE = "UNDERWRITING_GRADE"


class DecisionAuthority(str, Enum):
    SCREENING_ONLY = "SCREENING_ONLY"
    TECHNICAL_ASSESSMENT = "TECHNICAL_ASSESSMENT"
    UNDERWRITING_REVIEW = "UNDERWRITING_REVIEW"


class EvidenceGap(BaseModel):
    id: str
    label: str
    status: Literal["missing", "insufficient", "present"] = "missing"
    description: str
    required_for: AssessmentMode = AssessmentMode.UNDERWRITING_GRADE


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
    expected_components: list[str] = Field(default_factory=list)
    insured: bool | None = None
    insured_value_usd: float | None = None


class ClassificationResult(BaseModel):
    """Output of the Orbital Classification Agent."""
    valid: bool = True
    rejection_reason: str | None = None
    satellite_type: str = "other"
    bus_platform: str | None = None
    orbital_regime: str = "UNKNOWN"
    expected_components: list[str] = Field(default_factory=list)
    design_life_years: float | None = None
    estimated_age_years: float | None = None
    operator: str | None = None
    notes: str = ""
    degraded: bool = False

    @field_validator("expected_components", mode="before")
    @classmethod
    def _normalize_expected_components(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [
                item.strip(" -\t")
                for item in value.replace("\n", ",").split(",")
                if item.strip()
            ]
        return value


class SatelliteDamageItem(BaseModel):
    """Individual damage finding on a satellite."""
    id: int
    type: str                           # micrometeorite_crater, cell_degradation, thermal_blanket_damage, etc.
    description: str
    bounding_box: list[int] = Field(min_length=4, max_length=4)  # [y_min, x_min, y_max, x_max] normalized 0-1000
    label: str                          # Short label for overlay (max 5 words)
    severity: Literal["MINOR", "MODERATE", "SEVERE", "CRITICAL"]
    confidence: float = Field(ge=0.0, le=1.0)
    uncertain: bool = False
    estimated_power_impact_pct: float | None = None  # Only populated when measurement metadata supports it.

    @field_validator("bounding_box")
    @classmethod
    def _validate_bounding_box(cls, value: list[int]) -> list[int]:
        if any(coord < 0 or coord > 1000 for coord in value):
            raise ValueError("bounding_box coordinates must be normalized 0-1000")
        y_min, x_min, y_max, x_max = value
        if y_min > y_max or x_min > x_max:
            raise ValueError("bounding_box minimum coordinates must not exceed maximum coordinates")
        return value


class SatelliteDamagesAssessment(BaseModel):
    """Output of the Satellite Vision Agent."""
    damages: list[SatelliteDamageItem] = Field(default_factory=list)
    overall_pattern: str = ""           # e.g., "cumulative micrometeorite bombardment"
    overall_severity: Literal["MINOR", "MODERATE", "SEVERE", "CRITICAL"] = "MINOR"
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    total_power_impact_pct: float | None = None
    healthy_areas_noted: str = ""
    component_assessed: str = ""        # Which component was analyzed (solar_array, antenna, bus)
    degraded: bool = False
    measurement_metadata: dict = Field(default_factory=dict)
    unsupported_claims_blocked: list[str] = Field(default_factory=list)
    required_evidence_gaps: list[EvidenceGap] = Field(default_factory=list)


class OrbitalStressor(BaseModel):
    """Environmental stressor in the orbital environment."""
    name: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
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
    stressors: list[OrbitalStressor] = Field(default_factory=list)
    accelerating_factors: list[str] = Field(default_factory=list)
    mitigating_factors: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
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
    root_cause_chain: list[str] = Field(default_factory=list)
    progression_rate: str = "MODERATE"
    power_degradation_estimate_pct: float = 0.0
    remaining_life_revision_years: float | None = None
    time_to_critical: str = ""
    historical_precedents: list[SatellitePrecedent] = Field(default_factory=list)
    degraded: bool = False
    probability_components: list[ProbabilityComponent] = Field(default_factory=list)


class RiskMatrixDimension(BaseModel):
    score: int = Field(ge=1, le=5)
    reasoning: str = ""


class RiskMatrix(BaseModel):
    severity: RiskMatrixDimension
    probability: RiskMatrixDimension
    consequence: RiskMatrixDimension
    composite: int = Field(ge=1, le=125)


class ConsistencyCheck(BaseModel):
    passed: bool = True
    anomalies: list[str] = Field(default_factory=list)
    confidence_adjustment: str = ""


class UnderwritingRecommendation(str, Enum):
    INSURABLE_STANDARD = "INSURABLE_STANDARD"
    INSURABLE_ELEVATED_PREMIUM = "INSURABLE_ELEVATED_PREMIUM"
    INSURABLE_WITH_EXCLUSIONS = "INSURABLE_WITH_EXCLUSIONS"
    FURTHER_INVESTIGATION = "FURTHER_INVESTIGATION"
    UNINSURABLE = "UNINSURABLE"


class InsuranceRiskReport(BaseModel):
    """Output of the Insurance Risk Agent — the key differentiator."""
    model_config = ConfigDict(use_enum_values=True)

    consistency_check: ConsistencyCheck
    risk_matrix: RiskMatrix
    risk_tier: Literal["LOW", "MEDIUM", "MEDIUM-HIGH", "HIGH", "CRITICAL", "UNKNOWN"]
    assessment_mode: AssessmentMode = AssessmentMode.PUBLIC_SCREEN
    decision_authority: DecisionAuthority = DecisionAuthority.SCREENING_ONLY
    report_title: str = "Public Risk Screen"
    unsupported_claims_blocked: list[str] = Field(default_factory=list)
    required_evidence_gaps: list[EvidenceGap] = Field(default_factory=list)

    # Insurance-specific metrics
    estimated_remaining_life_years: float | None = None
    power_margin_percentage: float | None = None
    annual_degradation_rate_pct: float | None = None
    replacement_cost_usd: float | None = None
    depreciated_value_usd: float | None = None
    revenue_at_risk_annual_usd: float | None = None
    total_loss_probability: float | None = Field(default=None, ge=0.0, le=1.0)

    underwriting_recommendation: UnderwritingRecommendation = UnderwritingRecommendation.FURTHER_INVESTIGATION
    recommendation_rationale: str = ""
    recommended_actions: list[dict] = Field(default_factory=list)
    worst_case_scenario: str = ""
    summary: str = ""
    degraded: bool = False
    evidence_gaps: list[str] = Field(default_factory=list)
    report_completeness: Literal["COMPLETE", "PARTIAL", "FAILED"] = "COMPLETE"

    # Deutsch Layer: Provenance & Calibration (all Optional, backward compatible)
    confidence_calibration: ConfidenceCalibration | None = None
    replacement_cost_detail: FinancialEstimate | None = None
    depreciated_value_detail: FinancialEstimate | None = None
    revenue_at_risk_detail: FinancialEstimate | None = None
    loss_probability_derivation: LossProbabilityDerivation | None = None
    sensitivity_analysis: SensitivityAnalysis | None = None
    remaining_life_provenance: FieldProvenance | None = None
    power_margin_provenance: FieldProvenance | None = None
    degradation_rate_provenance: FieldProvenance | None = None


class SatelliteConditionReport(BaseModel):
    """Full Satellite Condition Report — the product deliverable."""
    target: SatelliteTarget
    assessment_mode: AssessmentMode = AssessmentMode.PUBLIC_SCREEN
    decision_authority: DecisionAuthority = DecisionAuthority.SCREENING_ONLY
    classification: ClassificationResult
    vision: SatelliteDamagesAssessment | None = None
    environment: OrbitalEnvironmentAnalysis | None = None
    failure_mode: SatelliteFailureModeAnalysis | None = None
    insurance_risk: InsuranceRiskReport | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    report_version: str = "1.0"
