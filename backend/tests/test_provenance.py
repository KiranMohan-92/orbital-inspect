"""Tests for provenance models and backward compatibility."""
import os
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

import pytest
from models.provenance import (
    DataSourceType, FieldProvenance, ConfidenceCalibration,
    FinancialEstimate, ProbabilityComponent, LossProbabilityDerivation,
    SensitivityParameter, SensitivityAnalysis,
)
from models.satellite import InsuranceRiskReport, SatelliteFailureModeAnalysis


def test_field_provenance_defaults():
    fp = FieldProvenance()
    assert fp.source_type == DataSourceType.ESTIMATED
    assert fp.confidence == 0.5
    assert fp.derivation_chain == []


def test_confidence_calibration_defaults():
    cc = ConfidenceCalibration()
    assert cc.confidence_tier == "MODERATE"
    assert cc.calibrated_confidence == 0.5


def test_financial_estimate_with_derivation():
    fe = FinancialEstimate(
        value_usd=350_000_000,
        source="satellite_class_lookup",
        confidence_range_low=280_000_000,
        confidence_range_high=420_000_000,
        comparable_precedents=["Inmarsat 6-F2", "ViaSat-3"],
        derivation="SSL-1300 GEO platform, market rate $300-450M",
    )
    assert fe.value_usd == 350_000_000
    assert len(fe.comparable_precedents) == 2


def test_probability_component():
    pc = ProbabilityComponent(
        mechanism="solar_array_failure",
        base_rate=0.03,
        observed_evidence_factor=1.5,
        adjusted_probability=0.045,
        source="fleet_historical_data",
    )
    assert pc.adjusted_probability == pytest.approx(0.045)


def test_loss_probability_derivation():
    lpd = LossProbabilityDerivation(
        components=[
            ProbabilityComponent(mechanism="solar", base_rate=0.03, adjusted_probability=0.045),
            ProbabilityComponent(mechanism="thermal", base_rate=0.02, adjusted_probability=0.024),
        ],
        aggregation_method="independent_sum",
        total_loss_probability=0.069,
        derivation_narrative="Base rates from 25-year GEO fleet data",
    )
    assert len(lpd.components) == 2
    assert lpd.total_loss_probability == pytest.approx(0.069)


def test_sensitivity_analysis():
    sa = SensitivityAnalysis(
        parameters=[
            SensitivityParameter(name="severity", baseline_value=3, test_range_low=2, test_range_high=4, is_critical=True),
        ],
        baseline_recommendation="INSURABLE_WITH_EXCLUSIONS",
        recommendation_robustness="MARGINAL",
        critical_thresholds=["severity >= 4 → FURTHER_INVESTIGATION"],
        key_drivers=["consequence", "severity"],
    )
    assert sa.recommendation_robustness == "MARGINAL"
    assert sa.parameters[0].is_critical is True


def test_insurance_risk_report_backward_compatible_without_provenance():
    """Existing reports without provenance fields still work."""
    report = InsuranceRiskReport(
        consistency_check={"passed": True, "anomalies": [], "confidence_adjustment": ""},
        risk_matrix={
            "severity": {"score": 3, "reasoning": "test"},
            "probability": {"score": 2, "reasoning": "test"},
            "consequence": {"score": 3, "reasoning": "test"},
            "composite": 18,
        },
        risk_tier="MEDIUM",
    )
    assert report.confidence_calibration is None
    assert report.replacement_cost_detail is None
    assert report.sensitivity_analysis is None


def test_insurance_risk_report_with_provenance():
    """Reports with provenance fields also work."""
    report = InsuranceRiskReport(
        consistency_check={"passed": True, "anomalies": [], "confidence_adjustment": ""},
        risk_matrix={
            "severity": {"score": 3, "reasoning": "test"},
            "probability": {"score": 2, "reasoning": "test"},
            "consequence": {"score": 3, "reasoning": "test"},
            "composite": 18,
        },
        risk_tier="MEDIUM",
        confidence_calibration=ConfidenceCalibration(
            evidence_sufficiency=0.6,
            confidence_tier="MODERATE",
            basis="Single-epoch imagery",
        ),
        replacement_cost_detail=FinancialEstimate(
            value_usd=350_000_000,
            source="satellite_class_lookup",
        ),
    )
    assert report.confidence_calibration.confidence_tier == "MODERATE"
    assert report.replacement_cost_detail.value_usd == 350_000_000


def test_failure_mode_with_probability_components():
    fma = SatelliteFailureModeAnalysis(
        failure_mode="Solar Array Degradation",
        mechanism="Cumulative MMOD",
        probability_components=[
            ProbabilityComponent(mechanism="solar", base_rate=0.03),
        ],
    )
    assert len(fma.probability_components) == 1


def test_failure_mode_backward_compatible():
    fma = SatelliteFailureModeAnalysis()
    assert fma.probability_components == []
