"""
Administrative endpoints for org-scoped operations.
"""

import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import require_role, CurrentUser
from config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/api-key/rotate")
async def rotate_api_key(user: CurrentUser | None = Depends(require_role("admin"))):
    if user is None:
        raise HTTPException(status_code=403, detail="Admin authentication required")

    try:
        from db.base import async_session_factory
        from db.repository import OrganizationRepository, AuditLogRepository
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")

    api_key = f"{settings.API_KEY_PREFIX}_{user.org_id}_{secrets.token_urlsafe(32)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    async with async_session_factory() as session:
        org_repo = OrganizationRepository(session)
        audit_logs = AuditLogRepository(session)
        org = await org_repo.get(user.org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        await org_repo.update_api_key_hash(user.org_id, api_key_hash)
        await audit_logs.create(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="org.api_key_rotated",
            resource_type="organization",
            resource_id=user.org_id,
            metadata_json={"tier": org.tier},
        )

    return {"api_key": api_key, "org_id": user.org_id}


@router.get("/audit")
async def list_audit_logs(
    limit: int = 100,
    user: CurrentUser | None = Depends(require_role("admin")),
):
    try:
        from db.base import async_session_factory
        from db.repository import AuditLogRepository
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")

    async with async_session_factory() as session:
        repo = AuditLogRepository(session)
        items = await repo.list_for_org(user.org_id if user else None, limit=limit)
        return {
            "items": [
                {
                    "id": item.id,
                    "action": item.action,
                    "resource_type": item.resource_type,
                    "resource_id": item.resource_id,
                    "actor_id": item.actor_id,
                    "metadata": item.metadata_json,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in items
            ]
        }
