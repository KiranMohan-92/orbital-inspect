"""
Governance rules for model-backed inspection decisions.
"""

from __future__ import annotations

from copy import deepcopy

from config import settings


def build_model_manifest() -> dict:
    return {
        "policy_version": settings.GOVERNANCE_POLICY_VERSION,
        "gemini_model": settings.GEMINI_MODEL,
        "requires_human_review": settings.REQUIRE_HUMAN_REVIEW_FOR_DECISIONS,
        "minimum_evidence_completeness_pct": settings.MIN_EVIDENCE_COMPLETENESS_FOR_DECISION,
    }


def apply_decision_governance(
    insurance_result: dict | None,
    *,
    evidence_completeness_pct: float | None,
    degraded: bool,
    failure_reasons: list[str],
    decision_authority: str | None = None,
) -> tuple[dict, dict]:
    result = deepcopy(insurance_result or {})
    blocked_reasons: list[str] = []

    if evidence_completeness_pct is None:
        blocked_reasons.append("evidence completeness unavailable")
    elif evidence_completeness_pct < settings.MIN_EVIDENCE_COMPLETENESS_FOR_DECISION:
        blocked_reasons.append(
            f"evidence completeness {evidence_completeness_pct:.1f}% below policy threshold"
        )

    if degraded:
        blocked_reasons.append("one or more pipeline stages degraded")
    if failure_reasons:
        blocked_reasons.append("pipeline recorded failure reasons")
    if decision_authority == "SCREENING_ONLY":
        blocked_reasons.append("decision authority is screening-only")
    elif decision_authority == "TECHNICAL_ASSESSMENT":
        blocked_reasons.append("decision authority is technical assessment, not underwriting review")

    if blocked_reasons:
        result["underwriting_recommendation"] = "FURTHER_INVESTIGATION"
        rationale = result.get("recommendation_rationale") or result.get("summary") or ""
        governance_note = "Governance hold: " + "; ".join(blocked_reasons)
        result["recommendation_rationale"] = (
            f"{rationale} {governance_note}".strip()
        )
        result["summary"] = (
            f"{result.get('summary', '')} {governance_note}".strip()
        )
        result["report_completeness"] = "PARTIAL"

    governance = {
        "policy_version": settings.GOVERNANCE_POLICY_VERSION,
        "human_review_required": settings.REQUIRE_HUMAN_REVIEW_FOR_DECISIONS,
        "decision_blocked_reason": "; ".join(blocked_reasons) if blocked_reasons else None,
        "minimum_evidence_completeness_pct": settings.MIN_EVIDENCE_COMPLETENESS_FOR_DECISION,
        "decision_authority": decision_authority,
    }
    return result, governance
