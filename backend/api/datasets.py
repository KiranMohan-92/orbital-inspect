"""Dataset registry API — read-only listing and admin registration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import CurrentUser, get_current_user, require_role

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize_dataset(dataset) -> dict[str, Any]:
    return {
        "id": dataset.id,
        "name": dataset.name,
        "dataset_type": dataset.dataset_type,
        "source_url": dataset.source_url,
        "license": dataset.license,
        "intended_use": dataset.intended_use,
        "local_storage_uri": dataset.local_storage_uri,
        "version": dataset.version,
        "record_count": dataset.record_count,
        "checksum_sha256": dataset.checksum_sha256,
        "notes": dataset.notes,
        "created_at": _iso(dataset.created_at),
        "updated_at": _iso(dataset.updated_at),
    }


@router.get("")
async def list_datasets(
    dataset_type: str | None = None,
    intended_use: str | None = None,
    user: CurrentUser | None = Depends(get_current_user),
):
    """List registered benchmark/evaluation datasets."""
    from db.base import async_session_factory
    from db.repository import EvidenceRepository

    async with async_session_factory() as session:
        evidence_repo = EvidenceRepository(session)
        datasets = await evidence_repo.list_datasets(
            org_id=user.org_id if user else None,
            dataset_type=dataset_type,
            intended_use=intended_use,
        )
        return {
            "datasets": [_serialize_dataset(d) for d in datasets],
            "total": len(datasets),
        }


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Get details for a single registered dataset."""
    from db.base import async_session_factory
    from db.repository import EvidenceRepository

    async with async_session_factory() as session:
        evidence_repo = EvidenceRepository(session)
        dataset = await evidence_repo.get_dataset(
            dataset_id,
            org_id=user.org_id if user else None,
        )
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return _serialize_dataset(dataset)


@router.post("/seed")
async def seed_benchmark_datasets_endpoint(
    user: CurrentUser | None = Depends(require_role("admin")),
):
    """Seed known benchmark datasets into the registry. Idempotent."""
    from db.base import async_session_factory
    from services.dataset_registry_service import seed_benchmark_datasets

    async with async_session_factory() as session:
        results = await seed_benchmark_datasets(session)
        return {
            "seeded": len(results),
            "datasets": results,
        }
