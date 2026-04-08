"""
Batch analysis service — manages BatchJob lifecycle.

Provides create, read, and update operations for batch jobs.
Callers are responsible for dispatching individual items and reporting results.
"""

from __future__ import annotations

from sqlalchemy import select, update

from db.batch_models import BatchJob

_MAX_BATCH_SIZE = 100


class BatchService:
    def __init__(self, session):
        self.session = session

    async def create_batch(self, org_id: str | None, items: list[dict]) -> BatchJob:
        """Create a batch job record. Items are validated but not yet dispatched."""
        if len(items) > _MAX_BATCH_SIZE:
            raise ValueError(f"Batch size {len(items)} exceeds maximum of {_MAX_BATCH_SIZE}")

        batch = BatchJob(
            org_id=org_id,
            status="pending",
            total_items=len(items),
            completed_items=0,
            failed_items=0,
            item_analysis_ids=[],
            item_errors=[],
        )
        self.session.add(batch)
        await self.session.commit()
        await self.session.refresh(batch)
        return batch

    async def get_batch(self, batch_id: str, org_id: str | None = None) -> BatchJob | None:
        """Get batch by ID with optional org scoping."""
        stmt = select(BatchJob).where(BatchJob.id == batch_id)
        if org_id is not None:
            stmt = stmt.where(BatchJob.org_id == org_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_item_completed(self, batch_id: str, analysis_id: str) -> None:
        """Increment completed count and append analysis_id."""
        batch = await self.get_batch(batch_id)
        if batch is None:
            return
        analysis_ids = list(batch.item_analysis_ids or [])
        analysis_ids.append(analysis_id)
        await self.session.execute(
            update(BatchJob)
            .where(BatchJob.id == batch_id)
            .values(
                completed_items=BatchJob.completed_items + 1,
                item_analysis_ids=analysis_ids,
            )
        )
        await self.session.commit()

    async def update_item_failed(self, batch_id: str, index: int, error: str) -> None:
        """Increment failed count and append error."""
        batch = await self.get_batch(batch_id)
        if batch is None:
            return
        errors = list(batch.item_errors or [])
        errors.append({"index": index, "error": error})
        await self.session.execute(
            update(BatchJob)
            .where(BatchJob.id == batch_id)
            .values(
                failed_items=BatchJob.failed_items + 1,
                item_errors=errors,
            )
        )
        await self.session.commit()

    async def update_batch_status(self, batch_id: str, status: str) -> None:
        """Update the status field of a batch job."""
        await self.session.execute(
            update(BatchJob).where(BatchJob.id == batch_id).values(status=status)
        )
        await self.session.commit()

    async def finalize_batch(self, batch_id: str) -> None:
        """Mark batch as completed or partial_failure based on counts."""
        from datetime import datetime, timezone

        batch = await self.get_batch(batch_id)
        if batch is None:
            return

        if batch.failed_items == 0:
            final_status = "completed"
        elif batch.completed_items == 0:
            final_status = "failed"
        else:
            final_status = "partial_failure"

        await self.session.execute(
            update(BatchJob)
            .where(BatchJob.id == batch_id)
            .values(
                status=final_status,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await self.session.commit()
