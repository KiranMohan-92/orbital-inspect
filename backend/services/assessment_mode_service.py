"""Assessment-mode authority boundaries for public-data risk screens."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from models.satellite import (
    AssessmentMode,
    DecisionAuthority,
    EvidenceGap,
    InsuranceRiskReport,
    SatelliteDamagesAssessment,
)


UNDERWRITING_EVIDENCE_REQUIREMENTS: tuple[dict[str, str], ...] = (
    {
        "id": "operator_telemetry",
        "label": "Operator telemetry",
        "description": "Power, thermal, attitude, command, and anomaly telemetry are required before underwriting conclusions.",
    },
    {
        "id": "calibrated_imagery",
        "label": "Calibrated imagery",
        "description": "Imagery needs range, scale, calibration, and image-quality metadata before physical damage dimensions are defensible.",
    },
    {
        "id": "camera_range_metadata",
        "label": "Camera and range metadata",
        "description": "Focal length, sensor pitch, GSD/range, pose, illumination, and scale reference are missing or incomplete.",
    },
    {
        "id": "spacecraft_geometry",
        "label": "Spacecraft geometry",
        "description": "Mass, projected area, subsystem geometry, materials, and exposed components are required for exposure modeling.",
    },
    {
        "id": "shielding_materials",
        "label": "Shielding and materials",
        "description": "Shielding depth and material stackups are required for MMOD/radiation vulnerability estimates.",
    },
    {
        "id": "covariance_cdm_quality",
        "label": "Covariance/CDM quality",
        "description": "Conjunction conclusions require state covariance, CDM quality, hard-body radius, and uncertainty realism.",
    },
    {
        "id": "operator_anomaly_logs",
        "label": "Operator anomaly logs",
        "description": "Private anomaly, maintenance, and operations logs are required to connect public observations to spacecraft health.",
    },
    {
        "id": "actuarial_priors",
        "label": "Actuarial priors",
        "description": "Validated fleet loss priors, policy context, and claims history are required for loss probability and financial exposure.",
    },
)


PUBLIC_UNSUPPORTED_CLAIMS = [
    "physical_damage_dimensions_without_calibrated_imagery",
    "power_impact_without_telemetry_or_measurement_chain",
    "total_loss_probability_without_actuarial_model",
    "financial_exposure_without_policy_or_operator_financials",
    "underwriting_recommendation_without_private_evidence",
]


def normalize_assessment_mode(value: str | AssessmentMode | None) -> AssessmentMode:
    if isinstance(value, AssessmentMode):
        return value
    normalized = (value or AssessmentMode.PUBLIC_SCREEN.value).strip().upper()
    try:
        return AssessmentMode(normalized)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in AssessmentMode)
        raise ValueError(f"assessment_mode must be one of: {allowed}") from exc


def build_assessment_contract(
    *,
    assessment_mode: str | AssessmentMode | None,
    capture_metadata: dict[str, Any] | None,
    telemetry_summary: dict[str, Any] | None,
    baseline_reference: dict[str, Any] | None,
    evidence_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = normalize_assessment_mode(assessment_mode)
    capture = capture_metadata or {}
    telemetry = telemetry_summary or {}
    baseline = baseline_reference or {}
    evidence_quality = evidence_quality or {}

    present = _presence_map(capture, telemetry, baseline, evidence_quality)
    gaps = [
        EvidenceGap(
            id=req["id"],
            label=req["label"],
            status="missing",
            description=req["description"],
            required_for=AssessmentMode.UNDERWRITING_GRADE,
        ).model_dump(mode="json")
        for req in UNDERWRITING_EVIDENCE_REQUIREMENTS
        if not present.get(req["id"], False)
    ]

    if mode == AssessmentMode.UNDERWRITING_GRADE and not gaps:
        authority = DecisionAuthority.UNDERWRITING_REVIEW
    elif mode == AssessmentMode.ENHANCED_TECHNICAL:
        authority = DecisionAuthority.TECHNICAL_ASSESSMENT
    else:
        authority = DecisionAuthority.SCREENING_ONLY

    unsupported = []
    if authority != DecisionAuthority.UNDERWRITING_REVIEW:
        unsupported = list(PUBLIC_UNSUPPORTED_CLAIMS)
    elif not present["calibrated_imagery"] or not present["camera_range_metadata"]:
        unsupported.extend(PUBLIC_UNSUPPORTED_CLAIMS[:2])

    return {
        "assessment_mode": mode.value,
        "decision_authority": authority.value,
        "required_evidence_gaps": gaps,
        "unsupported_claims_blocked": unsupported,
        "evidence_presence": present,
        "report_title": "Public Risk Screen" if authority == DecisionAuthority.SCREENING_ONLY else "Technical Risk Assessment",
        "authority_rationale": _authority_rationale(mode, authority, gaps),
    }


def enforce_vision_claim_boundary(
    assessment: SatelliteDamagesAssessment,
    contract: dict[str, Any],
) -> SatelliteDamagesAssessment:
    result = assessment.model_copy(deep=True)
    presence = contract.get("evidence_presence") or {}
    has_measurement_chain = bool(presence.get("calibrated_imagery") and presence.get("camera_range_metadata"))
    has_power_basis = bool(has_measurement_chain and presence.get("operator_telemetry"))

    blocked = set(result.unsupported_claims_blocked)
    if not has_measurement_chain:
        blocked.add("physical_damage_dimensions_without_calibrated_imagery")
        result.required_evidence_gaps = _model_gaps(contract)
    if not has_power_basis:
        blocked.add("power_impact_without_telemetry_or_measurement_chain")
        result.total_power_impact_pct = None
        for item in result.damages:
            item.estimated_power_impact_pct = None

    result.unsupported_claims_blocked = sorted(blocked)
    return result


def enforce_report_authority(
    report: InsuranceRiskReport,
    contract: dict[str, Any],
) -> InsuranceRiskReport:
    result = report.model_copy(deep=True)
    mode = normalize_assessment_mode(contract.get("assessment_mode"))
    authority = DecisionAuthority(contract.get("decision_authority", DecisionAuthority.SCREENING_ONLY.value))

    result.assessment_mode = mode
    result.decision_authority = authority
    result.report_title = contract.get("report_title") or "Public Risk Screen"
    result.required_evidence_gaps = _model_gaps(contract)
    result.unsupported_claims_blocked = sorted(
        set(result.unsupported_claims_blocked) | set(contract.get("unsupported_claims_blocked") or [])
    )

    if authority != DecisionAuthority.UNDERWRITING_REVIEW:
        _suppress_underwriting_only_fields(result)
        result.underwriting_recommendation = "FURTHER_INVESTIGATION"
        result.report_completeness = "PARTIAL"
        result.degraded = True
        gap_labels = [gap.label for gap in result.required_evidence_gaps]
        for label in gap_labels:
            if label not in result.evidence_gaps:
                result.evidence_gaps.append(label)
        note = (
            "Public-data screening only: underwriting-grade conclusions require "
            "operator telemetry, calibrated imagery, spacecraft geometry, covariance/CDM quality, "
            "and actuarial priors."
        )
        result.recommendation_rationale = _prepend_sentence(result.recommendation_rationale, note)
        result.summary = _prepend_sentence(result.summary, "Public Risk Screen result; not an underwriting-grade decision.")
        if result.consistency_check:
            if note not in result.consistency_check.anomalies:
                result.consistency_check.anomalies.append(note)
            result.consistency_check.passed = False
            result.consistency_check.confidence_adjustment = "Decision authority limited to screening"

    return result


def contract_from_analysis_metadata(analysis: Any) -> dict[str, Any]:
    capture = getattr(analysis, "capture_metadata", {}) or {}
    return build_assessment_contract(
        assessment_mode=capture.get("assessment_mode"),
        capture_metadata=capture,
        telemetry_summary=getattr(analysis, "telemetry_summary", {}) or {},
        baseline_reference=getattr(analysis, "baseline_reference", {}) or {},
        evidence_quality=(getattr(analysis, "evidence_bundle_summary", {}) or {}).get("evidence_quality"),
    )


def _presence_map(
    capture: dict[str, Any],
    telemetry: dict[str, Any],
    baseline: dict[str, Any],
    evidence_quality: dict[str, Any],
) -> dict[str, bool]:
    keys = set(capture) | set(telemetry) | set(baseline)
    return {
        "operator_telemetry": bool(telemetry),
        "calibrated_imagery": bool(
            capture.get("calibrated") is True
            or {"range_m", "focal_length_mm", "sensor_pitch_um", "scale_reference"} <= set(capture)
            or {"range_m", "ground_sample_distance_m"} <= set(capture)
        ),
        "camera_range_metadata": bool(
            {"range_m", "focal_length_mm"} <= set(capture)
            or {"range_m", "ground_sample_distance_m"} <= set(capture)
        ),
        "spacecraft_geometry": bool(
            {"geometry", "dimensions", "dimensions_json", "projected_area_m2", "cross_section_area_m2", "mass_kg"} & set(baseline)
        ),
        "shielding_materials": bool({"shielding", "shielding_depth_mm", "material_stack", "materials"} & set(baseline)),
        "covariance_cdm_quality": bool(
            {"covariance", "cdm", "cdm_quality", "hard_body_radius_m"} & keys
        ),
        "operator_anomaly_logs": bool({"anomaly_logs", "operator_anomaly_logs", "maintenance_records"} & keys),
        "actuarial_priors": bool({"actuarial_priors", "claims_history", "fleet_loss_priors", "policy_context"} & set(baseline)),
    }


def _authority_rationale(
    mode: AssessmentMode,
    authority: DecisionAuthority,
    gaps: list[dict[str, Any]],
) -> str:
    if authority == DecisionAuthority.UNDERWRITING_REVIEW:
        return "Required underwriting evidence classes are present; final use still requires human review."
    if mode == AssessmentMode.UNDERWRITING_GRADE:
        return f"Underwriting-grade mode requested but {len(gaps)} required evidence classes are missing."
    if mode == AssessmentMode.ENHANCED_TECHNICAL:
        return "Enhanced technical mode may summarize gated public tools but cannot issue underwriting conclusions."
    return "Public/open data supports screening and evidence triage only."


def _model_gaps(contract: dict[str, Any]) -> list[EvidenceGap]:
    return [EvidenceGap(**deepcopy(gap)) for gap in contract.get("required_evidence_gaps") or []]


def _suppress_underwriting_only_fields(result: InsuranceRiskReport) -> None:
    result.estimated_remaining_life_years = None
    result.power_margin_percentage = None
    result.annual_degradation_rate_pct = None
    result.replacement_cost_usd = None
    result.depreciated_value_usd = None
    result.revenue_at_risk_annual_usd = None
    result.total_loss_probability = None
    result.replacement_cost_detail = None
    result.depreciated_value_detail = None
    result.revenue_at_risk_detail = None
    result.loss_probability_derivation = None
    result.remaining_life_provenance = None
    result.power_margin_provenance = None
    result.degradation_rate_provenance = None


def _prepend_sentence(value: str, sentence: str) -> str:
    value = value.strip()
    if not value:
        return sentence
    if sentence in value:
        return value
    return f"{sentence} {value}"
