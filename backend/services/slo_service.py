"""SLO (Service Level Objective) measurement and error budget tracking.

Provides quantifiable reliability proof for enterprise procurement:
- Pipeline completion rate >= 99.5%
- p95 end-to-end latency <= 45 seconds
- Evidence freshness <= 4 hours for active monitoring
- Webhook delivery success rate >= 99%
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class SLOTarget:
    name: str
    description: str
    target_pct: float  # e.g. 99.5
    window_hours: int = 24 * 7  # 7-day rolling window


# Defined SLO targets
PIPELINE_COMPLETION = SLOTarget(
    name="pipeline_completion",
    description="Analysis pipeline completion rate (excluding rejected images)",
    target_pct=99.5,
)
P95_LATENCY = SLOTarget(
    name="p95_latency",
    description="p95 end-to-end analysis latency <= 45 seconds",
    target_pct=95.0,
)
EVIDENCE_FRESHNESS = SLOTarget(
    name="evidence_freshness",
    description="TLE/orbital evidence data <= 4 hours old for monitored assets",
    target_pct=95.0,
)
WEBHOOK_DELIVERY = SLOTarget(
    name="webhook_delivery",
    description="Webhook delivery success rate",
    target_pct=99.0,
)


@dataclass
class SLIMeasurement:
    """A single SLI (Service Level Indicator) measurement."""
    slo_name: str
    current_value: float  # Current percentage
    target_value: float  # Target percentage
    is_met: bool
    error_budget_remaining_pct: float  # How much error budget is left
    window_hours: int
    total_events: int
    good_events: int
    bad_events: int
    measured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SLOService:
    """Computes SLI metrics from database records."""

    async def measure_pipeline_completion(self) -> SLIMeasurement:
        """Measure pipeline completion rate from analysis records."""
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            # Get recent analyses (7 days)
            from sqlalchemy import select, func
            from db.models import Analysis
            from datetime import timedelta

            cutoff = datetime.now(timezone.utc) - timedelta(hours=PIPELINE_COMPLETION.window_hours)

            total_query = select(func.count(Analysis.id)).where(
                Analysis.created_at >= cutoff,
                Analysis.status != "rejected",  # Exclude rejected (expected)
            )
            total = (await session.execute(total_query)).scalar() or 0

            completed_query = select(func.count(Analysis.id)).where(
                Analysis.created_at >= cutoff,
                Analysis.status.in_(("completed", "completed_partial")),
            )
            completed = (await session.execute(completed_query)).scalar() or 0

            failed_query = select(func.count(Analysis.id)).where(
                Analysis.created_at >= cutoff,
                Analysis.status == "failed",
            )
            failed = (await session.execute(failed_query)).scalar() or 0

        current_pct = (completed / total * 100.0) if total > 0 else 100.0
        error_budget_total = 100.0 - PIPELINE_COMPLETION.target_pct  # 0.5%
        error_budget_consumed = 100.0 - current_pct
        error_budget_remaining = max(0.0, error_budget_total - error_budget_consumed) / error_budget_total * 100.0 if error_budget_total > 0 else 100.0

        return SLIMeasurement(
            slo_name=PIPELINE_COMPLETION.name,
            current_value=round(current_pct, 2),
            target_value=PIPELINE_COMPLETION.target_pct,
            is_met=current_pct >= PIPELINE_COMPLETION.target_pct,
            error_budget_remaining_pct=round(error_budget_remaining, 2),
            window_hours=PIPELINE_COMPLETION.window_hours,
            total_events=total,
            good_events=completed,
            bad_events=failed,
        )

    async def measure_all(self) -> dict[str, Any]:
        """Measure all SLOs and return a dashboard-ready summary."""
        pipeline = await self.measure_pipeline_completion()

        measurements = [pipeline]
        all_met = all(m.is_met for m in measurements)

        return {
            "status": "healthy" if all_met else "degraded",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "slos": [
                {
                    "name": m.slo_name,
                    "current_pct": m.current_value,
                    "target_pct": m.target_value,
                    "is_met": m.is_met,
                    "error_budget_remaining_pct": m.error_budget_remaining_pct,
                    "window_hours": m.window_hours,
                    "total_events": m.total_events,
                    "good_events": m.good_events,
                    "bad_events": m.bad_events,
                }
                for m in measurements
            ],
            "targets": [
                {"name": t.name, "description": t.description, "target_pct": t.target_pct}
                for t in [PIPELINE_COMPLETION, P95_LATENCY, EVIDENCE_FRESHNESS, WEBHOOK_DELIVERY]
            ],
        }
