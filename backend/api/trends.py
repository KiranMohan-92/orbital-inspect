"""Degradation trend API — predictive fleet intelligence endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/assets/{asset_id}")
async def get_asset_trend(
    asset_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Get degradation trend for a single asset.

    Requires at least 3 historical analyses with composite risk scores.
    Returns trajectory, predicted scores, and time-to-threshold.
    """
    from services.trend_analysis_service import TrendAnalysisService

    service = TrendAnalysisService()
    result = await service.get_asset_trend(asset_id, org_id=user.org_id if user else None)
    if result is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return result


@router.get("/portfolio")
async def get_fleet_trends(
    limit: int = 10,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Get fleet-wide degradation summary.

    Returns the worst-trending assets, fleet average degradation velocity,
    and distribution of trend directions (improving/stable/degrading).
    """
    from services.trend_analysis_service import TrendAnalysisService

    service = TrendAnalysisService()
    return await service.get_fleet_trends(org_id=user.org_id if user else None, limit=limit)
