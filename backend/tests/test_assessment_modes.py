import pytest
from fastapi import HTTPException

from models.satellite import InsuranceRiskReport, SatelliteDamagesAssessment
from main import _assessment_contract_or_400
from inspection_core import SpacecraftState, propagation_capability
from services.assessment_mode_service import (
    build_assessment_contract,
    enforce_report_authority,
    enforce_vision_claim_boundary,
)


def _sample_report() -> InsuranceRiskReport:
    return InsuranceRiskReport(
        consistency_check={"passed": True, "anomalies": [], "confidence_adjustment": ""},
        risk_matrix={
            "severity": {"score": 2, "reasoning": "minor visible anomaly"},
            "probability": {"score": 2, "reasoning": "slow progression"},
            "consequence": {"score": 3, "reasoning": "moderate mission impact"},
            "composite": 12,
        },
        risk_tier="LOW",
        estimated_remaining_life_years=6.5,
        power_margin_percentage=22.0,
        annual_degradation_rate_pct=1.2,
        replacement_cost_usd=50_000_000,
        depreciated_value_usd=35_000_000,
        revenue_at_risk_annual_usd=7_000_000,
        total_loss_probability=0.04,
        underwriting_recommendation="INSURABLE_STANDARD",
        summary="Low apparent risk.",
    )


def test_public_screen_forces_further_investigation_and_nulls_unsupported_metrics():
    contract = build_assessment_contract(
        assessment_mode="PUBLIC_SCREEN",
        capture_metadata={},
        telemetry_summary={},
        baseline_reference={},
    )

    result = enforce_report_authority(_sample_report(), contract)

    assert result.assessment_mode == "PUBLIC_SCREEN"
    assert result.decision_authority == "SCREENING_ONLY"
    assert result.underwriting_recommendation == "FURTHER_INVESTIGATION"
    assert result.total_loss_probability is None
    assert result.replacement_cost_usd is None
    assert result.power_margin_percentage is None
    assert "total_loss_probability_without_actuarial_model" in result.unsupported_claims_blocked
    assert {gap.id for gap in result.required_evidence_gaps} >= {
        "operator_telemetry",
        "calibrated_imagery",
        "spacecraft_geometry",
        "actuarial_priors",
    }


def test_underwriting_grade_authority_requires_all_private_evidence_classes():
    contract = build_assessment_contract(
        assessment_mode="UNDERWRITING_GRADE",
        capture_metadata={
            "calibrated": True,
            "range_m": 120.0,
            "focal_length_mm": 800.0,
            "sensor_pitch_um": 5.5,
            "scale_reference": "known bus width",
            "cdm_quality": "operator_supplied",
            "anomaly_logs": [{"id": "A-1"}],
        },
        telemetry_summary={"power_margin_pct": 24.0, "attitude_mode": "nominal"},
        baseline_reference={
            "geometry": {"bus": "known"},
            "shielding_depth_mm": 3.0,
            "material_stack": ["aluminum", "MLI"],
            "actuarial_priors": {"fleet": "operator validated"},
        },
    )

    assert contract["decision_authority"] == "UNDERWRITING_REVIEW"
    assert contract["required_evidence_gaps"] == []


def test_vision_claim_boundary_blocks_power_impact_without_measurement_chain():
    assessment = SatelliteDamagesAssessment(
        damages=[
            {
                "id": 1,
                "type": "surface_anomaly",
                "description": "Visible panel discoloration",
                "bounding_box": [1, 2, 3, 4],
                "label": "Anomaly",
                "severity": "MINOR",
                "confidence": 0.8,
                "estimated_power_impact_pct": 1.5,
            }
        ],
        overall_confidence=0.8,
        total_power_impact_pct=1.5,
    )
    contract = build_assessment_contract(
        assessment_mode="PUBLIC_SCREEN",
        capture_metadata={},
        telemetry_summary={},
        baseline_reference={},
    )

    result = enforce_vision_claim_boundary(assessment, contract)

    assert result.total_power_impact_pct is None
    assert result.damages[0].estimated_power_impact_pct is None
    assert "power_impact_without_telemetry_or_measurement_chain" in result.unsupported_claims_blocked


def test_create_analysis_rejects_underwriting_grade_without_required_evidence():
    with pytest.raises(HTTPException) as exc:
        _assessment_contract_or_400(
            assessment_mode="UNDERWRITING_GRADE",
            capture_metadata={},
            telemetry_summary={},
            baseline_reference={},
        )

    assert exc.value.status_code == 400
    assert "UNDERWRITING_GRADE requires missing evidence classes" in exc.value.detail


def test_spacecraft_state_records_sgp4_capability_boundary():
    state = SpacecraftState.from_tle(
        object_id="25544",
        tle_line1="1 25544U 98067A   26001.00000000  .00010000  00000-0  10000-3 0  9991",
        tle_line2="2 25544  51.6400 100.0000 0005000  90.0000 270.0000 15.50000000123456",
    )
    capability = propagation_capability()

    assert state.object_id == "25544"
    assert state.covariance_available is False
    assert capability.method in {"SGP4", "UNAVAILABLE"}
    if capability.available is False:
        assert "sgp4 package is not installed" in capability.reason
