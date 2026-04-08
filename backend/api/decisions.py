"""
Decision review API for analysis-level operational guidance.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import CurrentUser, require_rate_limit, require_role
from config import settings

router = APIRouter(tags=["decisions"])


class DecisionReviewRequest(BaseModel):
    action: str
    comments: str = ""
    override_action: str | None = None
    reason_code: str | None = None


OVERRIDE_REASON_CODES = {
    "new_evidence",
    "mission_priority",
    "customer_policy",
    "operator_context",
    "temporary_exception",
}


def _derive_override_urgency(action: str | None) -> str | None:
    if action in {"maneuver_review", "disposal_review"}:
        return "urgent"
    if action in {"reimage", "insurance_escalation", "servicing_candidate"}:
        return "priority"
    if action:
        return "routine"
    return None


@router.post("/analyses/{analysis_id}/decision/review")
async def review_decision(
    analysis_id: str,
    body: DecisionReviewRequest,
    user: CurrentUser | None = Depends(require_role("analyst")),
    _rate_limit=Depends(require_rate_limit("report")),
):
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository, AuditLogRepository
        from services.decision_policy_service import ACTION_TYPES, compute_triage
        from services.post_analysis_service import apply_review_action
        from services.webhook_service import dispatch_registered_webhooks

        valid_actions = {"approve", "block", "request_reimage", "override_action", "reset_review"}
        demo_mode_admin = not settings.AUTH_ENABLED and user is None
        actor_is_admin = demo_mode_admin or bool(user and user.role == "admin")
        actor_id = user.user_id if user else ("demo-admin" if demo_mode_admin else "demo-reviewer")
        actor_org_id = user.org_id if user else None
        if body.action not in valid_actions:
            raise HTTPException(status_code=400, detail=f"action must be one of: {', '.join(sorted(valid_actions))}")
        if body.action in {"block", "request_reimage"} and not body.comments.strip():
            raise HTTPException(status_code=400, detail="Review comments are required")
        if body.action == "override_action":
            if not actor_is_admin:
                raise HTTPException(status_code=403, detail="Only admins may override recommended action")
            if body.override_action not in ACTION_TYPES:
                allowed = ", ".join(sorted(ACTION_TYPES))
                raise HTTPException(status_code=400, detail=f"override_action must be one of: {allowed}")
            if body.reason_code not in OVERRIDE_REASON_CODES:
                allowed = ", ".join(sorted(OVERRIDE_REASON_CODES))
                raise HTTPException(status_code=400, detail=f"reason_code must be one of: {allowed}")
            if not body.comments.strip():
                raise HTTPException(status_code=400, detail="Override requires comments")

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            audit_logs = AuditLogRepository(session)
            analysis = await repo.get(analysis_id, org_id=actor_org_id)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
            if not getattr(analysis, "decision_summary", None):
                raise HTTPException(status_code=409, detail="Decision has not been evaluated yet")

            previous_summary = deepcopy(analysis.decision_summary or {})
            previous_status = getattr(analysis, "decision_status", "pending_policy")

            try:
                next_status, override_action = apply_review_action(
                    current_status=previous_status,
                    action=body.action,
                    override_action=body.override_action,
                    actor_is_admin=actor_is_admin,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            next_summary = deepcopy(previous_summary)
            approved_by = None
            approved_at = None
            override_reason = None
            review_metadata = {
                "review_action": body.action,
                "reason_code": body.reason_code,
                "comments": body.comments.strip(),
                "reviewed_by": actor_id,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }

            if body.action == "approve":
                next_summary["blocked"] = False
                next_summary["blocked_reason"] = None
                approved_by = actor_id
                approved_at = datetime.now(timezone.utc)
                next_summary["review"] = review_metadata
            elif body.action == "reset_review":
                next_summary["blocked"] = False
                next_summary["blocked_reason"] = None
                next_summary["review"] = review_metadata
            elif body.action == "block":
                next_summary["blocked"] = True
                next_summary["blocked_reason"] = body.comments.strip() or "Blocked by reviewer"
                next_summary["review"] = review_metadata
            elif body.action == "request_reimage":
                next_summary["blocked"] = True
                next_summary["blocked_reason"] = body.comments.strip() or "Reviewer requested new imagery"
                next_summary["recommended_action"] = "reimage"
                next_summary["decision_confidence"] = "low"
                next_summary["urgency"] = "priority"
                next_summary["decision_rationale"] = body.comments.strip() or "Reviewer requested re-imaging before use"
                next_summary["review"] = review_metadata
            elif body.action == "override_action":
                next_summary["blocked"] = False
                next_summary["blocked_reason"] = None
                next_summary["policy_recommended_action"] = previous_summary.get("recommended_action")
                next_summary["recommended_action"] = override_action
                next_summary["decision_confidence"] = "medium"
                next_summary["urgency"] = _derive_override_urgency(override_action)
                next_summary["decision_rationale"] = (
                    f"Administrative override to {override_action.replace('_', ' ')}. {body.comments.strip()}".strip()
                )
                next_summary["override_active"] = True
                next_summary["override_reason_code"] = body.reason_code
                next_summary["override_reason"] = body.comments.strip()
                next_summary["review"] = review_metadata
                approved_by = actor_id
                approved_at = datetime.now(timezone.utc)
                override_reason = f"{body.reason_code}: {body.comments.strip()}".strip(": ")

            triage_score, triage_band, triage_factors = compute_triage(
                analysis,
                decision_summary=next_summary,
                decision_status=next_status,
                recurrence_count=getattr(analysis, "recurrence_count", 0) or 0,
            )
            await repo.update_decision_state(
                analysis_id,
                decision_summary=next_summary,
                decision_status=next_status,
                decision_recommended_action=next_summary.get("recommended_action"),
                decision_confidence=next_summary.get("decision_confidence"),
                decision_urgency=next_summary.get("urgency"),
                decision_blocked_reason=next_summary.get("blocked_reason"),
                triage_score=triage_score,
                triage_band=triage_band,
                triage_factors=triage_factors,
                recurrence_count=getattr(analysis, "recurrence_count", 0) or 0,
                decision_override_reason=override_reason,
                decision_approved_by=approved_by,
                decision_approved_at=approved_at,
            )
            await audit_logs.create(
                org_id=actor_org_id,
                actor_id=actor_id,
                action="analysis.decision_reviewed",
                resource_type="analysis",
                resource_id=analysis_id,
                metadata_json={
                    "review_action": body.action,
                    "reason_code": body.reason_code,
                    "comments": body.comments,
                    "previous_status": previous_status,
                    "next_status": next_status,
                    "override_action": override_action,
                    "previous_summary": previous_summary,
                    "next_summary": next_summary,
                },
                analysis_id=analysis_id,
            )
            await dispatch_registered_webhooks(
                org_id=actor_org_id,
                event_type="decision.reviewed",
                payload={
                    "analysis_id": analysis_id,
                    "decision_status": next_status,
                    "recommended_action": next_summary.get("recommended_action"),
                    "review_action": body.action,
                },
            )
            return {
                "analysis_id": analysis_id,
                "asset_id": getattr(analysis, "asset_id", None),
                "decision_status": next_status,
                "decision_summary": next_summary,
                "decision_approved_by": approved_by,
                "decision_approved_at": approved_at.isoformat() if approved_at else None,
                "decision_override_reason": override_reason,
                "triage_score": triage_score,
                "triage_band": triage_band,
            }
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")
