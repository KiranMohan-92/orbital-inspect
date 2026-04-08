"""Data retention and purge service.

Implements configurable retention policies per data type:
- Analysis results: 7 years (insurance regulatory requirement)
- SSE events: 90 days
- Webhook delivery logs: 30 days
- Dead letter jobs: 180 days

Designed to run as a scheduled ARQ periodic job.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

log = logging.getLogger(__name__)

# Default retention periods in days
DEFAULT_RETENTION = {
    "analysis_events": 90,
    "webhook_deliveries": 30,
    "dead_letter_jobs": 180,
    "audit_logs": 365 * 2,  # 2 years
}


class RetentionService:
    """Purges expired data with full audit trail."""

    def __init__(self, retention_days: dict[str, int] | None = None):
        self.retention = {**DEFAULT_RETENTION, **(retention_days or {})}

    async def purge_expired(self) -> dict[str, Any]:
        """Run a single purge pass across all data types.

        Returns summary of rows purged per table.
        """
        from db.base import async_session_factory

        results = {}
        async with async_session_factory() as session:
            results["analysis_events"] = await self._purge_analysis_events(session)
            results["webhook_deliveries"] = await self._purge_webhook_deliveries(session)
            results["dead_letter_jobs"] = await self._purge_dead_letters(session)

            # Log the purge as an audit event
            try:
                from db.repository import AuditLogRepository
                audit = AuditLogRepository(session)
                await audit.create(
                    org_id=None,
                    actor_id="system:retention",
                    action="retention.purge_completed",
                    resource_type="system",
                    resource_id="retention",
                    metadata_json=results,
                )
            except Exception as exc:
                log.warning("Failed to create audit log for purge: %s", exc)

        log.info("Retention purge completed", extra={"results": results})
        return {
            "purged_at": datetime.now(timezone.utc).isoformat(),
            **results,
        }

    async def _purge_analysis_events(self, session) -> int:
        """Purge analysis events older than retention period."""
        from sqlalchemy import delete
        from db.models import AnalysisEvent

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention["analysis_events"])
        result = await session.execute(
            delete(AnalysisEvent).where(AnalysisEvent.created_at < cutoff)
        )
        await session.commit()
        return result.rowcount or 0

    async def _purge_webhook_deliveries(self, session) -> int:
        """Purge webhook delivery logs older than retention period."""
        from sqlalchemy import delete
        from db.models import WebhookDelivery

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention["webhook_deliveries"])
        result = await session.execute(
            delete(WebhookDelivery).where(WebhookDelivery.created_at < cutoff)
        )
        await session.commit()
        return result.rowcount or 0

    async def _purge_dead_letters(self, session) -> int:
        """Purge dead letter jobs older than retention period."""
        from sqlalchemy import delete
        from db.models import DeadLetterJob

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention["dead_letter_jobs"])
        result = await session.execute(
            delete(DeadLetterJob).where(DeadLetterJob.created_at < cutoff)
        )
        await session.commit()
        return result.rowcount or 0


async def run_retention_purge() -> dict[str, Any]:
    """Convenience function for ARQ periodic job scheduling."""
    service = RetentionService()
    return await service.purge_expired()
