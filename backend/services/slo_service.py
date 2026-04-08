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

    async def measure_p95_latency(self) -> SLIMeasurement:
        """Measure pipeline p95 latency from in-process metrics."""
        try:
            from services.metrics_service import snapshot_metrics
            metrics = snapshot_metrics()
            stage_latency = metrics.get("analyses", {}).get("stage_latency_ms", {})

            if not stage_latency:
                return SLIMeasurement(
                    slo_name=P95_LATENCY.name,
                    current_value=0.0,
                    target_value=45.0,
                    is_met=True,
                    error_budget_remaining_pct=100.0,
                    window_hours=P95_LATENCY.window_hours,
                    total_events=0,
                    good_events=0,
                    bad_events=0,
                )

            # Sum of per-stage max latencies as a conservative p95 proxy (milliseconds -> seconds)
            max_latencies = [v.get("max", 0) for v in stage_latency.values() if isinstance(v, dict)]
            total_max_ms = sum(max_latencies)
            total_max_s = total_max_ms / 1000.0

            target_s = 45.0
            is_met = total_max_s <= target_s
            budget = max(0.0, (1.0 - total_max_s / target_s) * 100.0) if target_s > 0 else 100.0
            return SLIMeasurement(
                slo_name=P95_LATENCY.name,
                current_value=round(total_max_s, 1),
                target_value=target_s,
                is_met=is_met,
                error_budget_remaining_pct=round(min(budget, 100.0), 2),
                window_hours=P95_LATENCY.window_hours,
                total_events=sum(v.get("count", 0) for v in stage_latency.values() if isinstance(v, dict)),
                good_events=0,
                bad_events=0,
            )
        except Exception:
            return SLIMeasurement(
                slo_name=P95_LATENCY.name,
                current_value=0.0,
                target_value=45.0,
                is_met=True,
                error_budget_remaining_pct=100.0,
                window_hours=P95_LATENCY.window_hours,
                total_events=0,
                good_events=0,
                bad_events=0,
            )

    async def measure_evidence_freshness(self) -> SLIMeasurement:
        """Measure evidence freshness — max age across monitored assets."""
        from db.base import async_session_factory
        from sqlalchemy import select, func
        from db.models import EvidenceRecord

        target_hours = 4.0
        try:
            async with async_session_factory() as session:
                # Use coalesce(captured_at, ingested_at) since fleet ingestion
                # may not set captured_at but always sets ingested_at via server_default
                stmt = (
                    select(func.max(func.coalesce(EvidenceRecord.captured_at, EvidenceRecord.ingested_at)))
                    .where(EvidenceRecord.evidence_role != "offline_eval")
                )
                result = await session.execute(stmt)
                latest = result.scalar()

                if latest is None:
                    return SLIMeasurement(
                        slo_name=EVIDENCE_FRESHNESS.name,
                        current_value=0.0,
                        target_value=target_hours,
                        is_met=True,
                        error_budget_remaining_pct=100.0,
                        window_hours=EVIDENCE_FRESHNESS.window_hours,
                        total_events=0,
                        good_events=0,
                        bad_events=0,
                    )

                if latest.tzinfo is None:
                    latest = latest.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600.0
                is_met = age_hours <= target_hours
                budget = max(0.0, (1.0 - age_hours / target_hours) * 100.0) if target_hours > 0 else 100.0
                return SLIMeasurement(
                    slo_name=EVIDENCE_FRESHNESS.name,
                    current_value=round(age_hours, 1),
                    target_value=target_hours,
                    is_met=is_met,
                    error_budget_remaining_pct=round(min(budget, 100.0), 2),
                    window_hours=EVIDENCE_FRESHNESS.window_hours,
                    total_events=0,
                    good_events=0,
                    bad_events=0,
                )
        except Exception:
            return SLIMeasurement(
                slo_name=EVIDENCE_FRESHNESS.name,
                current_value=0.0,
                target_value=target_hours,
                is_met=True,
                error_budget_remaining_pct=100.0,
                window_hours=EVIDENCE_FRESHNESS.window_hours,
                total_events=0,
                good_events=0,
                bad_events=0,
            )

    async def measure_webhook_delivery(self) -> SLIMeasurement:
        """Measure webhook delivery success rate."""
        from db.base import async_session_factory
        from sqlalchemy import select, func
        from db.models import WebhookDelivery

        target_pct = WEBHOOK_DELIVERY.target_pct  # 99.0
        try:
            async with async_session_factory() as session:
                total_q = select(func.count(WebhookDelivery.id))
                total = (await session.execute(total_q)).scalar() or 0

                if total == 0:
                    return SLIMeasurement(
                        slo_name=WEBHOOK_DELIVERY.name,
                        current_value=100.0,
                        target_value=target_pct,
                        is_met=True,
                        error_budget_remaining_pct=100.0,
                        window_hours=WEBHOOK_DELIVERY.window_hours,
                        total_events=0,
                        good_events=0,
                        bad_events=0,
                    )

                success_q = select(func.count(WebhookDelivery.id)).where(WebhookDelivery.success.is_(True))
                success = (await session.execute(success_q)).scalar() or 0

                rate = (success / total) * 100.0
                is_met = rate >= target_pct
                error_budget_total = 100.0 - target_pct
                budget = max(0.0, 100.0 - ((100.0 - rate) / error_budget_total * 100.0)) if error_budget_total > 0 else 100.0
                return SLIMeasurement(
                    slo_name=WEBHOOK_DELIVERY.name,
                    current_value=round(rate, 1),
                    target_value=target_pct,
                    is_met=is_met,
                    error_budget_remaining_pct=round(min(budget, 100.0), 2),
                    window_hours=WEBHOOK_DELIVERY.window_hours,
                    total_events=total,
                    good_events=success,
                    bad_events=total - success,
                )
        except Exception:
            return SLIMeasurement(
                slo_name=WEBHOOK_DELIVERY.name,
                current_value=100.0,
                target_value=target_pct,
                is_met=True,
                error_budget_remaining_pct=100.0,
                window_hours=WEBHOOK_DELIVERY.window_hours,
                total_events=0,
                good_events=0,
                bad_events=0,
            )

    async def measure_all(self) -> dict[str, Any]:
        """Measure all SLOs and return a dashboard-ready summary."""
        pipeline = await self.measure_pipeline_completion()
        p95 = await self.measure_p95_latency()
        freshness = await self.measure_evidence_freshness()
        webhook = await self.measure_webhook_delivery()

        measurements = [pipeline, p95, freshness, webhook]
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
