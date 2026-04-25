"""Tests for _enforce_consistency() in insurance_risk_agent.py."""
import pytest
from pydantic import ValidationError
from agents.insurance_risk_agent import _enforce_consistency
from models.satellite import (
    InsuranceRiskReport,
    RiskMatrix,
    RiskMatrixDimension,
    ConsistencyCheck,
)


def _make_report(
    severity: int,
    probability: int,
    consequence: int,
    composite: int,
    risk_tier: str,
    recommendation: str,
    anomalies: list[str] | None = None,
) -> InsuranceRiskReport:
    """Helper to construct a minimal InsuranceRiskReport."""
    return InsuranceRiskReport(
        consistency_check=ConsistencyCheck(
            passed=True,
            anomalies=anomalies or [],
            confidence_adjustment="",
        ),
        risk_matrix=RiskMatrix(
            severity=RiskMatrixDimension(score=severity, reasoning="test"),
            probability=RiskMatrixDimension(score=probability, reasoning="test"),
            consequence=RiskMatrixDimension(score=consequence, reasoning="test"),
            composite=composite,
        ),
        risk_tier=risk_tier,
        underwriting_recommendation=recommendation,
        summary="test",
    )


# ─── Composite mismatch ──────────────────────────────────────────────────────

def test_composite_mismatch_is_corrected():
    """S=3, P=3, C=3, but composite=30 — should fix to 27."""
    report = _make_report(3, 3, 3, composite=30, risk_tier="MEDIUM", recommendation="FURTHER_INVESTIGATION")
    result = _enforce_consistency(report)
    assert result.risk_matrix.composite == 27
    assert any("Composite mismatch" in a for a in result.consistency_check.anomalies)
    assert result.consistency_check.passed is False


def test_composite_correct_no_anomaly():
    """S=2, P=2, C=3, composite=12 — should pass."""
    report = _make_report(2, 2, 3, composite=12, risk_tier="LOW", recommendation="INSURABLE_STANDARD")
    result = _enforce_consistency(report)
    assert result.risk_matrix.composite == 12
    assert not any("Composite mismatch" in a for a in result.consistency_check.anomalies)


# ─── Tier mismatch ───────────────────────────────────────────────────────────

def test_tier_mismatch_is_corrected():
    """composite=15, tier='HIGH' — should fix tier to 'LOW'."""
    report = _make_report(3, 1, 5, composite=15, risk_tier="HIGH", recommendation="FURTHER_INVESTIGATION")
    result = _enforce_consistency(report)
    assert result.risk_tier == "LOW"
    assert any("Tier mismatch" in a for a in result.consistency_check.anomalies)


def test_tier_correct_no_anomaly():
    """composite=27, tier='MEDIUM' — should pass."""
    report = _make_report(3, 3, 3, composite=27, risk_tier="MEDIUM", recommendation="FURTHER_INVESTIGATION")
    result = _enforce_consistency(report)
    assert result.risk_tier == "MEDIUM"
    assert not any("Tier mismatch" in a for a in result.consistency_check.anomalies)


# ─── Recommendation too lenient ──────────────────────────────────────────────

def test_recommendation_too_lenient_is_corrected():
    """composite=90, rec='INSURABLE_STANDARD' — should fix to 'UNINSURABLE'."""
    report = _make_report(5, 4, 5, composite=100, risk_tier="CRITICAL", recommendation="INSURABLE_STANDARD")
    result = _enforce_consistency(report)
    assert result.underwriting_recommendation == "UNINSURABLE"
    assert any("too lenient" in a for a in result.consistency_check.anomalies)


def test_recommendation_elevated_premium_too_lenient_is_corrected():
    """composite=90, rec='INSURABLE_ELEVATED_PREMIUM' — should also fix to 'UNINSURABLE'."""
    report = _make_report(5, 4, 5, composite=100, risk_tier="CRITICAL", recommendation="INSURABLE_ELEVATED_PREMIUM")
    result = _enforce_consistency(report)
    assert result.underwriting_recommendation == "UNINSURABLE"


# ─── Recommendation too harsh ────────────────────────────────────────────────

def test_recommendation_too_harsh_is_corrected():
    """composite=5, rec='UNINSURABLE' — should fix to 'INSURABLE_STANDARD'."""
    report = _make_report(1, 1, 5, composite=5, risk_tier="LOW", recommendation="UNINSURABLE")
    result = _enforce_consistency(report)
    assert result.underwriting_recommendation == "INSURABLE_STANDARD"
    assert any("too harsh" in a for a in result.consistency_check.anomalies)


# ─── All pass case ───────────────────────────────────────────────────────────

def test_all_pass_no_anomalies():
    """Valid report — no anomalies, consistency_check.passed stays True."""
    report = _make_report(2, 2, 3, composite=12, risk_tier="LOW", recommendation="INSURABLE_STANDARD")
    result = _enforce_consistency(report)
    assert result.consistency_check.passed is True
    assert result.consistency_check.anomalies == []
    assert result.consistency_check.confidence_adjustment == ""


def test_confidence_adjustment_set_on_anomaly():
    """When anomalies are found, confidence_adjustment should be set."""
    report = _make_report(3, 3, 3, composite=30, risk_tier="MEDIUM", recommendation="FURTHER_INVESTIGATION")
    result = _enforce_consistency(report)
    assert result.consistency_check.confidence_adjustment == "Server-side corrections applied"


def test_risk_matrix_rejects_score_below_minimum():
    with pytest.raises(ValidationError):
        RiskMatrixDimension(score=0, reasoning="invalid")


def test_risk_matrix_rejects_score_above_maximum():
    with pytest.raises(ValidationError):
        RiskMatrixDimension(score=6, reasoning="invalid")


def test_insurance_report_rejects_invalid_recommendation():
    with pytest.raises(ValidationError):
        _make_report(3, 3, 3, composite=27, risk_tier="MEDIUM", recommendation="INSURABLE_MADE_UP")


def test_insurance_report_rejects_out_of_range_probability():
    with pytest.raises(ValidationError):
        InsuranceRiskReport(
            consistency_check={"passed": True, "anomalies": [], "confidence_adjustment": ""},
            risk_matrix={
                "severity": {"score": 3, "reasoning": "test"},
                "probability": {"score": 3, "reasoning": "test"},
                "consequence": {"score": 3, "reasoning": "test"},
                "composite": 27,
            },
            risk_tier="MEDIUM",
            underwriting_recommendation="FURTHER_INVESTIGATION",
            total_loss_probability=1.5,
        )
