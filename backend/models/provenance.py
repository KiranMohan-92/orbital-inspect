"""
Data provenance, confidence calibration, and sensitivity analysis models.

Implements David Deutsch's 'hard to vary' principle — every number must be
traceable to its source, every confidence calibrated, every probability derived.
"""

from pydantic import BaseModel, Field
from enum import Enum


class DataSourceType(str, Enum):
    MEASURED = "measured"
    INFERRED = "inferred"
    ESTIMATED = "estimated"
    REFERENCE = "reference"
    OPERATOR_REPORTED = "reported"


class FieldProvenance(BaseModel):
    source_type: DataSourceType = DataSourceType.ESTIMATED
    primary_source: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    derivation_chain: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class ConfidenceCalibration(BaseModel):
    evidence_sufficiency: float = Field(default=0.5, ge=0.0, le=1.0)
    model_uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    consensus_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    calibrated_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence_tier: str = "MODERATE"
    basis: str = ""


class FinancialEstimate(BaseModel):
    value_usd: float = Field(default=0, ge=0)
    source: str = ""
    confidence_range_low: float = Field(default=0, ge=0)
    confidence_range_high: float = Field(default=0, ge=0)
    comparable_precedents: list[str] = Field(default_factory=list)
    derivation: str = ""


class ProbabilityComponent(BaseModel):
    mechanism: str = ""
    base_rate: float = Field(default=0, ge=0.0, le=1.0)
    observed_evidence_factor: float = Field(default=1.0, ge=0.0)
    adjusted_probability: float = Field(default=0, ge=0.0, le=1.0)
    source: str = ""


class LossProbabilityDerivation(BaseModel):
    components: list[ProbabilityComponent] = Field(default_factory=list)
    aggregation_method: str = "independent_sum"
    total_loss_probability: float = Field(default=0, ge=0.0, le=1.0)
    derivation_narrative: str = ""


class SensitivityParameter(BaseModel):
    name: str = ""
    baseline_value: float = 0
    test_range_low: float = 0
    test_range_high: float = 0
    recommendation_at_low: str = ""
    recommendation_at_high: str = ""
    is_critical: bool = False


class SensitivityAnalysis(BaseModel):
    parameters: list[SensitivityParameter] = Field(default_factory=list)
    baseline_recommendation: str = ""
    recommendation_robustness: str = "MODERATE"
    critical_thresholds: list[str] = Field(default_factory=list)
    key_drivers: list[str] = Field(default_factory=list)
