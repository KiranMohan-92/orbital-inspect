"""
Batch analysis API — submit and track fleet-scan or metadata-only reanalysis batches.

Endpoints:
  POST /batch/analyses  — create a new batch job
  GET  /batch/{batch_id} — get batch job status with per-item progress
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.dependencies import CurrentUser, get_current_user, require_role

log = logging.getLogger(__name__)

# Strong references to background tasks prevent GC from dropping in-flight batch jobs
_BATCH_TASKS: set[asyncio.Task] = set()

router = APIRouter(prefix="/batch", tags=["batch"])


async def _process_batch_items(batch_id: str, items: list[dict], org_id: str | None) -> None:
    """Background task to process batch items via fleet evidence ingestion."""
    from db.base import async_session_factory
    from db.repository import AssetRepository, EvidenceRepository
    from services.batch_service import BatchService
    from services.fleet_ingestion_service import FleetIngestionService

    async with async_session_factory() as session:
        service = BatchService(session)
        await service.update_batch_status(batch_id, "running")

    for index, item in enumerate(items):
        norad_id = item.get("norad_id")
        if not norad_id:
            async with async_session_factory() as session:
                bs = BatchService(session)
                await bs.update_item_failed(batch_id, index, "Missing norad_id")
            continue

        try:
            ingestion = FleetIngestionService(org_id=org_id)
            async with async_session_factory() as session:
                asset_repo = AssetRepository(session)
                evidence_repo = EvidenceRepository(session)

                asset = await asset_repo.resolve_or_create(
                    org_id=org_id,
                    norad_id=norad_id,
                    external_asset_id=item.get("external_asset_id") or None,
                    asset_type=item.get("asset_type", "satellite"),
                    name=item.get("asset_name") or None,
                )

                await ingestion._ingest_asset(
                    session=session,
                    evidence_repo=evidence_repo,
                    asset_id=asset.id,
                    norad_id=norad_id,
                    org_id=org_id,
                )

                bs = BatchService(session)
                # Track asset_id — batch items run fleet ingestion, not full analysis
                await bs.update_item_completed(batch_id, asset.id)
        except Exception as exc:
            log.warning("Batch item %d (NORAD %s) failed: %s", index, norad_id, exc)
            async with async_session_factory() as session:
                bs = BatchService(session)
                await bs.update_item_failed(batch_id, index, str(exc))

    async with async_session_factory() as session:
        bs = BatchService(session)
        await bs.finalize_batch(batch_id)


class BatchAnalysisItem(BaseModel):
    norad_id: str | None = None
    context: str = ""
    asset_type: str = "satellite"
    asset_name: str = ""
    external_asset_id: str = ""
    inspection_epoch: str = ""
    target_subsystem: str = ""
    # Note: no image in batch — batch is for metadata-only reanalysis or fleet scans


class BatchCreateRequest(BaseModel):
    items: list[BatchAnalysisItem] = Field(..., min_length=1, max_length=100)


class BatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    item_asset_ids: list[str]
    item_errors: list[dict]
    created_at: str | None
    completed_at: str | None


@router.post("/analyses")
async def create_batch_analysis(
    request: BatchCreateRequest,
    user: CurrentUser | None = Depends(require_role("analyst")),
):
    """Create a batch of analysis jobs. Returns batch ID for tracking."""
    from db.base import async_session_factory
    from services.batch_service import BatchService

    org_id = user.org_id if user else None
    item_dicts = [item.model_dump() for item in request.items]

    async with async_session_factory() as session:
        service = BatchService(session)
        batch = await service.create_batch(org_id=org_id, items=item_dicts)
        batch_id = batch.id
        total_items = batch.total_items

    # Launch background processing — retain strong reference to prevent GC
    task = asyncio.create_task(_process_batch_items(batch_id, item_dicts, org_id=org_id))
    _BATCH_TASKS.add(task)
    task.add_done_callback(_BATCH_TASKS.discard)

    return {"batch_id": batch_id, "status": "pending", "total_items": total_items}


@router.get("/{batch_id}")
async def get_batch_status(
    batch_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Get batch job status with per-item progress."""
    from db.base import async_session_factory
    from services.batch_service import BatchService

    async with async_session_factory() as session:
        service = BatchService(session)
        batch = await service.get_batch(batch_id, org_id=user.org_id if user else None)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        return BatchStatusResponse(
            batch_id=batch.id,
            status=batch.status,
            total_items=batch.total_items,
            completed_items=batch.completed_items,
            failed_items=batch.failed_items,
            item_asset_ids=batch.item_analysis_ids or [],
            item_errors=batch.item_errors or [],
            created_at=batch.created_at.isoformat() if batch.created_at else None,
            completed_at=batch.completed_at.isoformat() if batch.completed_at else None,
        )
