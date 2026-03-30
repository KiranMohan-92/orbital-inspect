"""Tests for satellite domain models."""
import pytest
from models.satellite import (
    ClassificationResult,
    InsuranceRiskReport,
    RiskMatrix,
    RiskMatrixDimension,
    ConsistencyCheck,
    OrbitalRegime,
    UnderwritingRecommendation,
    SatelliteConditionReport,
    SatelliteTarget,
    SatelliteDamagesAssessment,
    OrbitalEnvironmentAnalysis,
    SatelliteFailureModeAnalysis,
)


# ─── ClassificationResult ───────────────────────────────────────────────────

def test_classification_result_with_valid_data(sample_classification_result):
    result = ClassificationResult(**sample_classification_result)
    assert result.valid is True
    assert result.satellite_type == "communications"
    assert result.bus_platform == "SSL-1300"
    assert result.orbital_regime == "GEO"
    assert result.expected_components == ["solar_array", "antenna_reflector", "bus"]
    assert result.design_life_years == 15.0
    assert result.estimated_age_years == 8.0
    assert result.operator == "SES"
    assert result.notes == ""
    assert result.degraded is False


def test_classification_result_defaults():
    """Missing optional fields should use defaults."""
    result = ClassificationResult()
    assert result.valid is True
    assert result.satellite_type == "other"
    assert result.bus_platform is None
    assert result.orbital_regime == "UNKNOWN"
    assert result.expected_components == []
    assert result.design_life_years is None
    assert result.estimated_age_years is None
    assert result.operator is None
    assert result.notes == ""
    assert result.degraded is False


def test_classification_result_degraded_defaults_to_false():
    result = ClassificationResult(valid=True, satellite_type="communications")
    assert result.degraded is False


# ─── InsuranceRiskReport ─────────────────────────────────────────────────────

def test_insurance_risk_report_with_valid_data(sample_insurance_risk_result):
    report = InsuranceRiskReport(**sample_insurance_risk_result)
    assert report.risk_tier == "LOW"
    assert report.underwriting_recommendation == "INSURABLE_STANDARD"
    assert report.estimated_remaining_life_years == 7.0
    assert report.power_margin_percentage == 25.0
    assert report.degraded is False
    assert report.report_completeness == "COMPLETE"


def test_insurance_risk_report_degraded_defaults_to_false(sample_insurance_risk_result):
    data = {**sample_insurance_risk_result}
    data.pop("degraded")
    report = InsuranceRiskReport(**data)
    assert report.degraded is False


def test_insurance_risk_report_consistency_check(sample_insurance_risk_result):
    report = InsuranceRiskReport(**sample_insurance_risk_result)
    assert report.consistency_check.passed is True
    assert report.consistency_check.anomalies == []
    assert report.consistency_check.confidence_adjustment == ""


# ─── RiskMatrix ──────────────────────────────────────────────────────────────

def test_risk_matrix_composite():
    rm = RiskMatrix(
        severity=RiskMatrixDimension(score=3, reasoning="moderate"),
        probability=RiskMatrixDimension(score=2, reasoning="slow"),
        consequence=RiskMatrixDimension(score=4, reasoning="high value"),
        composite=24,
    )
    assert rm.composite == 24
    assert rm.severity.score == 3
    assert rm.probability.score == 2
    assert rm.consequence.score == 4


def test_risk_matrix_dimension_defaults():
    dim = RiskMatrixDimension(score=1)
    assert dim.score == 1
    assert dim.reasoning == ""


# ─── Enums ──────────────────────────────────────────────────────────────────

def test_orbital_regime_enum_values():
    assert OrbitalRegime.LEO == "LEO"
    assert OrbitalRegime.MEO == "MEO"
    assert OrbitalRegime.GEO == "GEO"
    assert OrbitalRegime.HEO == "HEO"
    assert OrbitalRegime.SSO == "SSO"
    assert OrbitalRegime.UNKNOWN == "UNKNOWN"


def test_underwriting_recommendation_enum_values():
    assert UnderwritingRecommendation.INSURABLE_STANDARD == "INSURABLE_STANDARD"
    assert UnderwritingRecommendation.INSURABLE_ELEVATED_PREMIUM == "INSURABLE_ELEVATED_PREMIUM"
    assert UnderwritingRecommendation.INSURABLE_WITH_EXCLUSIONS == "INSURABLE_WITH_EXCLUSIONS"
    assert UnderwritingRecommendation.FURTHER_INVESTIGATION == "FURTHER_INVESTIGATION"
    assert UnderwritingRecommendation.UNINSURABLE == "UNINSURABLE"


# ─── SatelliteConditionReport assembly ──────────────────────────────────────

def test_satellite_condition_report_assembly(
    sample_classification_result,
    sample_vision_result,
    sample_insurance_risk_result,
):
    target = SatelliteTarget(id="test-001", name="TEST-SAT")
    classification = ClassificationResult(**sample_classification_result)
    vision = SatelliteDamagesAssessment(**sample_vision_result)
    insurance_risk = InsuranceRiskReport(**sample_insurance_risk_result)

    report = SatelliteConditionReport(
        target=target,
        classification=classification,
        vision=vision,
        insurance_risk=insurance_risk,
    )

    assert report.target.id == "test-001"
    assert report.classification.satellite_type == "communications"
    assert report.vision is not None
    assert len(report.vision.damages) == 1
    assert report.insurance_risk is not None
    assert report.insurance_risk.risk_tier == "LOW"
    assert report.environment is None
    assert report.failure_mode is None
    assert report.report_version == "1.0"


def test_satellite_condition_report_optional_fields_are_none():
    target = SatelliteTarget(id="minimal-001")
    classification = ClassificationResult()
    report = SatelliteConditionReport(target=target, classification=classification)
    assert report.vision is None
    assert report.environment is None
    assert report.failure_mode is None
    assert report.insurance_risk is None


# ─── degraded field defaults ─────────────────────────────────────────────────

def test_damages_assessment_degraded_defaults_to_false():
    assessment = SatelliteDamagesAssessment()
    assert assessment.degraded is False


def test_orbital_environment_degraded_defaults_to_false():
    env = OrbitalEnvironmentAnalysis()
    assert env.degraded is False


def test_failure_mode_degraded_defaults_to_false():
    fm = SatelliteFailureModeAnalysis()
    assert fm.degraded is False
