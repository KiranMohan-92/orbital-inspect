from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services.decision_policy_service import compute_triage, evaluate_decision_policy
from services.post_analysis_service import apply_review_action


def _analysis(
    *,
    status="completed",
    composite=16,
    risk_tier="LOW",
    underwriting="INSURABLE_STANDARD",
    evidence_pct=100.0,
    degraded=False,
    report_completeness="COMPLETE",
    asset_type="satellite",
    failure_reasons=None,
    evidence_gaps=None,
):
    return SimpleNamespace(
        id="analysis-1",
        status=status,
        asset_type=asset_type,
        insurance_risk_result={
            "risk_matrix": {"composite": composite},
            "risk_tier": risk_tier,
            "underwriting_recommendation": underwriting,
            "evidence_gaps": evidence_gaps or [],
        } if status not in {"failed", "rejected"} else {},
        environment_result={},
        evidence_completeness_pct=evidence_pct,
        degraded=degraded,
        failure_reasons=failure_reasons or [],
        evidence_gaps=evidence_gaps or [],
        human_review_required=True,
        report_completeness=report_completeness,
        created_at=datetime.now(timezone.utc) - timedelta(days=5),
        completed_at=datetime.now(timezone.utc) - timedelta(days=2),
    )


def test_low_risk_sufficient_evidence_maps_to_continue_operations():
    decision = evaluate_decision_policy(_analysis())
    assert decision.status == "pending_human_review"
    assert decision.summary["recommended_action"] == "continue_operations"
    assert decision.summary["decision_confidence"] == "high"
    assert decision.summary["blocked"] is False


def test_partial_or_degraded_evidence_forces_reimage_or_monitor():
    decision = evaluate_decision_policy(
        _analysis(
            composite=75,
            risk_tier="HIGH",
            underwriting="INSURABLE_WITH_EXCLUSIONS",
            evidence_pct=45.0,
            degraded=True,
            report_completeness="PARTIAL",
            evidence_gaps=["satellite_vision"],
        )
    )
    assert decision.status == "pending_human_review"
    assert decision.summary["recommended_action"] == "reimage"
    assert decision.summary["decision_confidence"] == "low"


def test_failed_analysis_is_blocked():
    decision = evaluate_decision_policy(_analysis(status="failed"))
    assert decision.status == "blocked"
    assert decision.summary["recommended_action"] is None
    assert decision.summary["blocked"] is True


def test_triage_formula_respects_recurrence_and_pending_review():
    analysis = _analysis(composite=80, risk_tier="HIGH", underwriting="INSURABLE_WITH_EXCLUSIONS")
    decision = evaluate_decision_policy(analysis)
    score, band, factors = compute_triage(
        analysis,
        decision_summary=decision.summary,
        decision_status=decision.status,
        recurrence_count=3,
    )
    assert score > 0.5
    assert band in {"elevated", "priority", "urgent"}
    assert factors["recurrence_count"] == 3


def test_triage_accepts_naive_persisted_timestamps():
    analysis = _analysis()
    analysis.completed_at = datetime.now() - timedelta(days=1)
    analysis.created_at = datetime.now() - timedelta(days=3)
    decision = evaluate_decision_policy(analysis)

    score, band, factors = compute_triage(
        analysis,
        decision_summary=decision.summary,
        decision_status=decision.status,
        recurrence_count=0,
    )

    assert score >= 0.0
    assert band in {"routine", "elevated", "priority", "urgent"}
    assert factors["age_days"] >= 0.0


def test_review_state_machine_rejects_direct_blocked_to_approved():
    with pytest.raises(ValueError):
        apply_review_action(current_status="blocked", action="approve")


def test_review_state_machine_allows_admin_override():
    status, override_action = apply_review_action(
        current_status="pending_human_review",
        action="override_action",
        override_action="monitor",
        actor_is_admin=True,
    )
    assert status == "approved_for_use"
    assert override_action == "monitor"


def test_review_state_machine_rejects_override_from_blocked():
    with pytest.raises(ValueError):
        apply_review_action(
            current_status="blocked",
            action="override_action",
            override_action="monitor",
            actor_is_admin=True,
        )


def test_review_state_machine_allows_reset_to_pending_review():
    status, override_action = apply_review_action(
        current_status="blocked",
        action="reset_review",
    )
    assert status == "pending_human_review"
    assert override_action is None
