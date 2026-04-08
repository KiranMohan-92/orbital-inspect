"""
Batch analysis API — submit and track fleet-scan or metadata-only reanalysis batches.

Endpoints:
  POST /batch/analyses  — create a new batch job
  GET  /batch/{batch_id} — get batch job status with per-item progress
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.dependencies import CurrentUser, get_current_user, require_role

router = APIRouter(prefix="/batch", tags=["batch"])


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
    item_analysis_ids: list[str]
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

    async with async_session_factory() as session:
        service = BatchService(session)
        batch = await service.create_batch(
            org_id=user.org_id if user else None,
            items=[item.model_dump() for item in request.items],
        )
        return {"batch_id": batch.id, "status": batch.status, "total_items": batch.total_items}


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
            item_analysis_ids=batch.item_analysis_ids or [],
            item_errors=batch.item_errors or [],
            created_at=batch.created_at.isoformat() if batch.created_at else None,
            completed_at=batch.completed_at.isoformat() if batch.completed_at else None,
        )
