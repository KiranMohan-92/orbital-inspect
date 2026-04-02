"""
Portfolio monitoring API — fleet-level satellite health overview.
"""

import logging
from fastapi import APIRouter, Depends
from auth.dependencies import get_current_user, CurrentUser

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
_COMPLETED_STATUSES = {"completed", "completed_partial"}


@router.get("")
async def get_portfolio(user: CurrentUser | None = Depends(get_current_user)):
    """Get portfolio overview — all satellites grouped by risk tier."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            analyses, total = await repo.list_analyses(
                org_id=user.org_id if user else None,
                limit=100,
            )

            # Group by satellite (NORAD ID)
            satellites: dict[str, dict] = {}
            for a in analyses:
                key = a.norad_id or a.id
                if key not in satellites or (a.completed_at and (
                    not satellites[key].get("completed_at") or
                    a.completed_at > satellites[key]["completed_at"]
                )):
                    risk = a.insurance_risk_result or {}
                    satellites[key] = {
                        "norad_id": a.norad_id,
                        "analysis_id": a.id,
                        "status": a.status,
                        "asset_type": getattr(a, "asset_type", "satellite"),
                        "degraded": getattr(a, "degraded", False),
                        "risk_tier": risk.get("risk_tier", "UNKNOWN"),
                        "underwriting": risk.get("underwriting_recommendation", "UNKNOWN"),
                        "composite_score": risk.get("risk_matrix", {}).get("composite"),
                        "report_completeness": a.report_completeness,
                        "evidence_completeness_pct": getattr(a, "evidence_completeness_pct", None),
                        "classification": a.classification_result or {},
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                        "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                    }

            return {
                "satellites": list(satellites.values()),
                "total": len(satellites),
            }
    except ImportError:
        return {"satellites": [], "total": 0}


@router.get("/summary")
async def get_portfolio_summary(user: CurrentUser | None = Depends(get_current_user)):
    """Get fleet health summary statistics."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            analyses, total = await repo.list_analyses(
                org_id=user.org_id if user else None,
                limit=100,
            )

            tier_counts: dict[str, int] = {}
            uw_counts: dict[str, int] = {}
            status_counts: dict[str, int] = {}

            for a in analyses:
                status_counts[a.status] = status_counts.get(a.status, 0) + 1
                if a.status in _COMPLETED_STATUSES:
                    risk = a.insurance_risk_result or {}
                    tier = risk.get("risk_tier", "UNKNOWN")
                    uw = risk.get("underwriting_recommendation", "UNKNOWN")
                    tier_counts[tier] = tier_counts.get(tier, 0) + 1
                    uw_counts[uw] = uw_counts.get(uw, 0) + 1

            return {
                "total_analyses": total,
                "completed": sum(1 for a in analyses if a.status in _COMPLETED_STATUSES),
                "status_distribution": status_counts,
                "risk_distribution": tier_counts,
                "underwriting_distribution": uw_counts,
            }
    except ImportError:
        return {"total_analyses": 0, "completed": 0, "risk_distribution": {}, "underwriting_distribution": {}}
