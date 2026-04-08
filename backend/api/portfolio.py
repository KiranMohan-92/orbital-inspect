"""
Portfolio monitoring API — fleet-level satellite health overview.
"""

import logging
from fastapi import APIRouter, Depends
from auth.dependencies import get_current_user, CurrentUser

log = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
async def get_portfolio(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    risk_tier: str | None = None,
    decision_status: str | None = None,
    recommended_action: str | None = None,
    urgency: str | None = None,
    degraded_only: bool = False,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Get asset-backed fleet triage ordered by operational priority."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            rows, total = await repo.list_latest_asset_analyses(
                org_id=user.org_id if user else None,
                limit=limit,
                offset=offset,
                status=status,
                risk_tier=risk_tier,
                decision_status=decision_status,
                recommended_action=recommended_action,
                urgency=urgency,
                degraded_only=degraded_only,
            )

            return {
                "satellites": [
                    {
                        "asset_id": getattr(analysis, "asset_id", None),
                        "asset_name": getattr(asset, "name", None) if asset else None,
                        "asset_external_id": getattr(asset, "external_asset_id", None) if asset else None,
                        "asset_identity_source": getattr(asset, "identity_source", None) if asset else None,
                        "operator_name": getattr(asset, "operator_name", None) if asset else None,
                        "norad_id": analysis.norad_id,
                        "subsystem_id": getattr(analysis, "subsystem_id", None),
                        "subsystem_key": getattr(getattr(analysis, "subsystem", None), "subsystem_key", None),
                        "analysis_id": analysis.id,
                        "status": analysis.status,
                        "asset_type": getattr(analysis, "asset_type", "satellite"),
                        "degraded": getattr(analysis, "degraded", False),
                        "risk_tier": (analysis.insurance_risk_result or {}).get("risk_tier", "UNKNOWN"),
                        "underwriting": (analysis.insurance_risk_result or {}).get("underwriting_recommendation", "UNKNOWN"),
                        "composite_score": (analysis.insurance_risk_result or {}).get("risk_matrix", {}).get("composite"),
                        "report_completeness": analysis.report_completeness,
                        "evidence_completeness_pct": getattr(analysis, "evidence_completeness_pct", None),
                        "classification": analysis.classification_result or {},
                        "decision_summary": getattr(analysis, "decision_summary", {}) or {},
                        "decision_status": getattr(analysis, "decision_status", "pending_policy"),
                        "recommended_action": getattr(analysis, "decision_recommended_action", None),
                        "urgency": getattr(analysis, "decision_urgency", None),
                        "decision_blocked_reason": getattr(analysis, "decision_blocked_reason", None),
                        "decision_approved_by": getattr(analysis, "decision_approved_by", None),
                        "decision_approved_at": (
                            analysis.decision_approved_at.isoformat()
                            if getattr(analysis, "decision_approved_at", None)
                            else None
                        ),
                        "decision_override_reason": getattr(analysis, "decision_override_reason", None),
                        "decision_last_evaluated_at": (
                            analysis.decision_last_evaluated_at.isoformat()
                            if getattr(analysis, "decision_last_evaluated_at", None)
                            else None
                        ),
                        "triage_score": getattr(analysis, "triage_score", None),
                        "triage_band": getattr(analysis, "triage_band", None),
                        "triage_factors": getattr(analysis, "triage_factors", {}) or {},
                        "recurrence_count": getattr(analysis, "recurrence_count", 0),
                        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
                        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
                    }
                    for analysis, asset in rows
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
    except ImportError:
        return {"satellites": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/summary")
async def get_portfolio_summary(user: CurrentUser | None = Depends(get_current_user)):
    """Get fleet health summary statistics."""
    try:
        from services.fleet_summary_service import get_or_compute_portfolio_summary
        return await get_or_compute_portfolio_summary(org_id=user.org_id if user else None)
    except ImportError:
        return {
            "total_assets": 0,
            "total_analyses": 0,
            "completed": 0,
            "risk_distribution": {},
            "underwriting_distribution": {},
            "decision_distribution": {},
            "recommended_action_distribution": {},
            "urgency_distribution": {},
            "status_distribution": {},
            "open_attention_queue": 0,
            "urgent_assets": 0,
            "approved_assets": 0,
        }
