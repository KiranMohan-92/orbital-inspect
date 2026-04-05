"""
Deterministic decision policy for post-analysis operational guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from config import settings


ACTION_TYPES = {
    "continue_operations",
    "monitor",
    "reimage",
    "maneuver_review",
    "servicing_candidate",
    "insurance_escalation",
    "disposal_review",
}
DECISION_STATUSES = {"pending_policy", "pending_human_review", "approved_for_use", "blocked"}
URGENCY_SCORES = {"routine": 0.2, "priority": 0.65, "urgent": 1.0}
TRIAGE_BANDS = (
    (0.80, "urgent"),
    (0.60, "priority"),
    (0.35, "elevated"),
    (0.00, "routine"),
)


@dataclass
class DecisionOutcome:
    summary: dict[str, Any]
    status: str


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _evidence_bucket(evidence_completeness_pct: float | None) -> str:
    if evidence_completeness_pct is None:
        return "insufficient"
    if evidence_completeness_pct >= 85:
        return "sufficient"
    if evidence_completeness_pct >= 60:
        return "partial"
    return "insufficient"


def _parse_composite(insurance_result: dict[str, Any]) -> int:
    risk_matrix = insurance_result.get("risk_matrix") or {}
    composite = risk_matrix.get("composite")
    try:
        return max(0, min(125, int(composite)))
    except (TypeError, ValueError):
        return 0


def _needs_maneuver_review(environment_result: dict[str, Any] | None, composite: int) -> bool:
    if composite < 90 or not environment_result:
        return False
    collision_probability = str(environment_result.get("collision_probability") or "").lower()
    if collision_probability and any(token in collision_probability for token in ("high", "elevated", "critical")):
        return True
    for stressor in environment_result.get("stressors") or []:
        if not isinstance(stressor, dict):
            continue
        name = str(stressor.get("name") or "").lower()
        severity = str(stressor.get("severity") or "").upper()
        if severity == "HIGH" and any(token in name for token in ("debris", "collision", "conjunction")):
            return True
    return False


def evaluate_decision_policy(analysis) -> DecisionOutcome:
    insurance_result = dict(getattr(analysis, "insurance_risk_result", {}) or {})
    environment_result = dict(getattr(analysis, "environment_result", {}) or {})
    evidence_completeness_pct = getattr(analysis, "evidence_completeness_pct", None)
    evidence_bucket = _evidence_bucket(evidence_completeness_pct)
    degraded = bool(getattr(analysis, "degraded", False))
    failure_reasons = list(getattr(analysis, "failure_reasons", []) or [])
    evidence_gaps = list(insurance_result.get("evidence_gaps") or getattr(analysis, "evidence_gaps", []) or [])
    human_review_required = bool(getattr(analysis, "human_review_required", True))
    status = getattr(analysis, "status", "failed")
    asset_type = getattr(analysis, "asset_type", "satellite")
    composite = _parse_composite(insurance_result)
    risk_tier = str(insurance_result.get("risk_tier") or "UNKNOWN")
    underwriting = str(insurance_result.get("underwriting_recommendation") or "FURTHER_INVESTIGATION")

    blocked_reason = None
    recommended_action: str | None = None
    decision_confidence = "low"

    if status == "failed":
        blocked_reason = "analysis failed before a trustworthy operational decision could be produced"
    elif status == "rejected":
        blocked_reason = "target rejected as unsupported or non-orbital imagery"
    elif not insurance_result:
        blocked_reason = "risk synthesis unavailable"

    if blocked_reason:
        urgency = "priority"
        summary = {
            "recommended_action": None,
            "decision_confidence": "low",
            "decision_rationale": blocked_reason,
            "required_human_review": True,
            "blocked": True,
            "blocked_reason": blocked_reason,
            "evidence_completeness_bucket": evidence_bucket,
            "urgency": urgency,
            "policy_version": settings.GOVERNANCE_POLICY_VERSION,
        }
        return DecisionOutcome(summary=summary, status="blocked")

    if evidence_bucket == "insufficient" or degraded or getattr(analysis, "report_completeness", "COMPLETE") == "PARTIAL":
        recommended_action = "reimage" if evidence_bucket == "insufficient" or evidence_gaps or failure_reasons else "monitor"
        urgency = "priority" if composite >= 60 else "routine"
        decision_confidence = "low"
        rationale = "Evidence quality is not sufficient for stronger operational use."
        if evidence_gaps:
            rationale += f" Missing or degraded stages: {', '.join(evidence_gaps)}."
        if failure_reasons:
            rationale += " Pipeline recorded failure reasons."
    else:
        if _needs_maneuver_review(environment_result, composite):
            recommended_action = "maneuver_review"
        elif underwriting == "UNINSURABLE":
            recommended_action = "disposal_review" if composite >= 100 else "insurance_escalation"
        elif underwriting == "INSURABLE_WITH_EXCLUSIONS":
            recommended_action = (
                "servicing_candidate"
                if asset_type in {"servicer", "station_module", "solar_array", "radiator", "power_node", "compute_platform"}
                else "insurance_escalation"
            )
        elif underwriting == "INSURABLE_ELEVATED_PREMIUM":
            recommended_action = "insurance_escalation"
        elif underwriting == "FURTHER_INVESTIGATION":
            recommended_action = "monitor"
        elif composite >= 80:
            recommended_action = "insurance_escalation"
        elif composite >= 60:
            recommended_action = "monitor"
        else:
            recommended_action = "continue_operations"

        urgency = (
            "urgent"
            if recommended_action in {"maneuver_review", "disposal_review"} or composite >= 90
            else "priority"
            if recommended_action in {"reimage", "insurance_escalation", "servicing_candidate"} or composite >= 60
            else "routine"
        )
        decision_confidence = "high" if evidence_bucket == "sufficient" and composite < 60 else "medium"
        rationale = (
            f"Policy mapped {underwriting} at composite {composite}/125 with {risk_tier} risk "
            f"to {recommended_action.replace('_', ' ')}."
        )

    decision_status = "pending_human_review" if human_review_required else "approved_for_use"
    summary = {
        "recommended_action": recommended_action,
        "decision_confidence": decision_confidence,
        "decision_rationale": rationale,
        "required_human_review": human_review_required,
        "blocked": False,
        "blocked_reason": None,
        "evidence_completeness_bucket": evidence_bucket,
        "urgency": urgency,
        "policy_version": settings.GOVERNANCE_POLICY_VERSION,
    }
    return DecisionOutcome(summary=summary, status=decision_status)


def compute_triage(
    analysis,
    *,
    decision_summary: dict[str, Any],
    decision_status: str,
    recurrence_count: int,
    as_of: datetime | None = None,
) -> tuple[float, str, dict[str, float | int | str]]:
    as_of = _coerce_utc(as_of or datetime.now(timezone.utc)) or datetime.now(timezone.utc)
    insurance_result = dict(getattr(analysis, "insurance_risk_result", {}) or {})
    composite = _parse_composite(insurance_result)
    evidence_pct = getattr(analysis, "evidence_completeness_pct", None)
    completed_at = _coerce_utc(
        getattr(analysis, "completed_at", None) or getattr(analysis, "created_at", None)
    )
    age_days = 0.0
    if completed_at is not None:
        age_days = max((as_of - completed_at).total_seconds() / 86400.0, 0.0)

    normalized_risk = _clamp(composite / 125.0, 0.0, 1.0)
    urgency = str(decision_summary.get("urgency") or "routine")
    urgency_score = URGENCY_SCORES.get(urgency, URGENCY_SCORES["routine"])
    evidence_penalty = 1.0 if evidence_pct is None else 1.0 - _clamp(float(evidence_pct) / 100.0, 0.0, 1.0)
    staleness_score = _clamp(age_days / 90.0, 0.0, 1.0)
    recurrence_score = _clamp(recurrence_count / 3.0, 0.0, 1.0)
    blocked_or_pending_score = 1.0 if decision_status in {"pending_human_review", "blocked"} else 0.0

    triage_score = round(
        (
            0.35 * normalized_risk
            + 0.25 * urgency_score
            + 0.15 * evidence_penalty
            + 0.10 * staleness_score
            + 0.10 * recurrence_score
            + 0.05 * blocked_or_pending_score
        ),
        4,
    )

    triage_band = "routine"
    for threshold, band in TRIAGE_BANDS:
        if triage_score >= threshold:
            triage_band = band
            break

    factors = {
        "normalized_risk": round(normalized_risk, 4),
        "urgency_score": round(urgency_score, 4),
        "evidence_penalty": round(evidence_penalty, 4),
        "staleness_score": round(staleness_score, 4),
        "recurrence_score": round(recurrence_score, 4),
        "blocked_or_pending_score": round(blocked_or_pending_score, 4),
        "age_days": round(age_days, 2),
        "recurrence_count": recurrence_count,
    }
    return triage_score, triage_band, factors
