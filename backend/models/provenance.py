"""
Data provenance, confidence calibration, and sensitivity analysis models.

Implements David Deutsch's 'hard to vary' principle — every number must be
traceable to its source, every confidence calibrated, every probability derived.
"""

from pydantic import BaseModel
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
    confidence: float = 0.5
    derivation_chain: list[str] = []
    caveats: list[str] = []


class ConfidenceCalibration(BaseModel):
    evidence_sufficiency: float = 0.5
    model_uncertainty: float = 0.5
    consensus_strength: float = 0.5
    calibrated_confidence: float = 0.5
    confidence_tier: str = "MODERATE"
    basis: str = ""


class FinancialEstimate(BaseModel):
    value_usd: float = 0
    source: str = ""
    confidence_range_low: float = 0
    confidence_range_high: float = 0
    comparable_precedents: list[str] = []
    derivation: str = ""


class ProbabilityComponent(BaseModel):
    mechanism: str = ""
    base_rate: float = 0
    observed_evidence_factor: float = 1.0
    adjusted_probability: float = 0
    source: str = ""


class LossProbabilityDerivation(BaseModel):
    components: list[ProbabilityComponent] = []
    aggregation_method: str = "independent_sum"
    total_loss_probability: float = 0
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
    parameters: list[SensitivityParameter] = []
    baseline_recommendation: str = ""
    recommendation_robustness: str = "MODERATE"
    critical_thresholds: list[str] = []
    key_drivers: list[str] = []
