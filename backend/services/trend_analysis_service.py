"""Degradation trend analysis for predictive fleet intelligence.

For assets with 3+ historical analyses, computes risk score trajectory,
degradation velocity, and predicted time-to-threshold. Transforms
orbital-inspect from reactive inspection to predictive intelligence.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class TrendDataPoint:
    """A single point on the degradation timeline."""
    analysis_id: str
    composite_score: float
    timestamp: datetime
    risk_tier: str | None = None
    triage_band: str | None = None


@dataclass
class DegradationTrend:
    """Computed degradation trend for an asset."""
    asset_id: str
    asset_name: str | None
    norad_id: str | None
    data_points: list[TrendDataPoint]
    slope: float  # Risk score change per day (positive = degrading)
    intercept: float
    r_squared: float  # Goodness of fit
    current_score: float
    predicted_score_30d: float
    predicted_score_90d: float
    days_to_threshold: float | None  # Days until "UNINSURABLE" threshold (85)
    degradation_velocity: str  # stable, slow, moderate, rapid, critical
    trend_direction: str  # improving, stable, degrading

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_name": self.asset_name,
            "norad_id": self.norad_id,
            "data_points": [
                {
                    "analysis_id": dp.analysis_id,
                    "composite_score": dp.composite_score,
                    "timestamp": dp.timestamp.isoformat(),
                    "risk_tier": dp.risk_tier,
                    "triage_band": dp.triage_band,
                }
                for dp in self.data_points
            ],
            "slope_per_day": round(self.slope, 4),
            "r_squared": round(self.r_squared, 3),
            "current_score": round(self.current_score, 1),
            "predicted_score_30d": round(self.predicted_score_30d, 1),
            "predicted_score_90d": round(self.predicted_score_90d, 1),
            "days_to_threshold": round(self.days_to_threshold, 1) if self.days_to_threshold else None,
            "degradation_velocity": self.degradation_velocity,
            "trend_direction": self.trend_direction,
        }


# Threshold for "UNINSURABLE" — the critical risk level
UNINSURABLE_THRESHOLD = 85.0
MIN_DATA_POINTS = 3


def _linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Simple linear regression returning (slope, intercept, r_squared).

    Uses numpy-free implementation for minimal dependencies.
    """
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0, 0.0

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)

    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-10:
        return 0.0, sum_y / n, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R-squared
    y_mean = sum_y / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return slope, intercept, max(0.0, r_squared)


def _classify_velocity(slope_per_day: float) -> str:
    """Classify degradation velocity based on score change per day."""
    if slope_per_day <= -0.1:
        return "improving"  # Negative slope = score decreasing = improving
    if slope_per_day <= 0.05:
        return "stable"
    if slope_per_day <= 0.2:
        return "slow"
    if slope_per_day <= 0.5:
        return "moderate"
    if slope_per_day <= 1.0:
        return "rapid"
    return "critical"


def _classify_direction(slope_per_day: float) -> str:
    """Classify trend direction."""
    if slope_per_day <= -0.05:
        return "improving"
    if slope_per_day <= 0.05:
        return "stable"
    return "degrading"


def compute_trend(
    asset_id: str,
    asset_name: str | None,
    norad_id: str | None,
    data_points: list[TrendDataPoint],
) -> DegradationTrend | None:
    """Compute degradation trend from historical analysis data points.

    Requires at least MIN_DATA_POINTS data points with composite scores.
    Returns None if insufficient data.
    """
    # Filter to points with valid scores and sort by time
    valid = sorted(
        [dp for dp in data_points if dp.composite_score is not None],
        key=lambda dp: dp.timestamp,
    )

    if len(valid) < MIN_DATA_POINTS:
        return None

    # Convert timestamps to days since first observation
    t0 = valid[0].timestamp
    x = [(dp.timestamp - t0).total_seconds() / 86400.0 for dp in valid]
    y = [dp.composite_score for dp in valid]

    slope, intercept, r_squared = _linear_regression(x, y)

    current_score = valid[-1].composite_score
    current_day = x[-1]

    # Predict future scores
    predicted_30d = slope * (current_day + 30) + intercept
    predicted_90d = slope * (current_day + 90) + intercept

    # Clamp predictions to 0-100
    predicted_30d = max(0.0, min(100.0, predicted_30d))
    predicted_90d = max(0.0, min(100.0, predicted_90d))

    # Time to threshold
    days_to_threshold = None
    if slope > 0.001 and current_score < UNINSURABLE_THRESHOLD:
        days_remaining = (UNINSURABLE_THRESHOLD - current_score) / slope
        if days_remaining > 0:
            days_to_threshold = days_remaining

    return DegradationTrend(
        asset_id=asset_id,
        asset_name=asset_name,
        norad_id=norad_id,
        data_points=valid,
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        current_score=current_score,
        predicted_score_30d=predicted_30d,
        predicted_score_90d=predicted_90d,
        days_to_threshold=days_to_threshold,
        degradation_velocity=_classify_velocity(slope),
        trend_direction=_classify_direction(slope),
    )


class TrendAnalysisService:
    """Computes and serves degradation trends for fleet assets."""

    async def get_asset_trend(self, asset_id: str, org_id: str | None = None) -> dict[str, Any] | None:
        """Compute trend for a single asset from its analysis history."""
        from db.base import async_session_factory
        from db.repository import AssetRepository

        async with async_session_factory() as session:
            repo = AssetRepository(session)
            asset = await repo.get(asset_id, org_id=org_id)
            if not asset:
                return None

            analyses = await repo.list_analysis_timeline(
                asset_id=asset_id,
                org_id=org_id,
                limit=50,
            )

            data_points = []
            for analysis in analyses:
                insurance = getattr(analysis, "insurance_risk_result", {}) or {}
                composite = insurance.get("risk_matrix", {}).get("composite")
                if composite is not None and analysis.completed_at:
                    data_points.append(TrendDataPoint(
                        analysis_id=analysis.id,
                        composite_score=float(composite),
                        timestamp=analysis.completed_at,
                        risk_tier=insurance.get("risk_tier"),
                        triage_band=getattr(analysis, "triage_band", None),
                    ))

            trend = compute_trend(
                asset_id=asset_id,
                asset_name=asset.name,
                norad_id=asset.norad_id,
                data_points=data_points,
            )

            if trend is None:
                return {
                    "asset_id": asset_id,
                    "asset_name": asset.name,
                    "norad_id": asset.norad_id,
                    "status": "insufficient_data",
                    "data_points_available": len(data_points),
                    "minimum_required": MIN_DATA_POINTS,
                }

            return trend.to_dict()

    async def get_fleet_trends(self, org_id: str | None = None, limit: int = 10) -> dict[str, Any]:
        """Get fleet-wide degradation summary — worst trending assets."""
        from db.base import async_session_factory
        from db.repository import AssetRepository

        async with async_session_factory() as session:
            repo = AssetRepository(session)
            assets = await repo.list_fleet_assets(org_id=org_id, limit=100)

            trends: list[dict[str, Any]] = []
            for asset in assets:
                try:
                    trend = await self.get_asset_trend(asset.id, org_id=org_id)
                    if trend and trend.get("status") != "insufficient_data":
                        trends.append(trend)
                except Exception as exc:
                    log.debug("Trend computation failed for asset %s: %s", asset.id, exc)

            # Sort by slope (degradation velocity) — worst first
            trends.sort(key=lambda t: t.get("slope_per_day", 0), reverse=True)

            return {
                "total_assets_analyzed": len(trends),
                "worst_trending": trends[:limit],
                "fleet_avg_slope": (
                    sum(t["slope_per_day"] for t in trends) / len(trends)
                    if trends else 0.0
                ),
                "assets_degrading": sum(1 for t in trends if t["trend_direction"] == "degrading"),
                "assets_stable": sum(1 for t in trends if t["trend_direction"] == "stable"),
                "assets_improving": sum(1 for t in trends if t["trend_direction"] == "improving"),
            }
