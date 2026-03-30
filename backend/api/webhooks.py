"""
Webhook management API — register, list, delete webhook endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from auth.dependencies import get_current_user, require_role, CurrentUser

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# In-memory webhook store (replace with DB in production)
_webhooks: dict[str, dict] = {}
_next_id = 1


class WebhookCreate(BaseModel):
    url: str
    secret: str = ""
    events: list[str] = ["analysis.completed"]


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    active: bool


@router.post("")
async def create_webhook(
    body: WebhookCreate,
    user: CurrentUser | None = Depends(require_role("admin")),
):
    """Register a new webhook endpoint."""
    global _next_id
    wh_id = str(_next_id)
    _next_id += 1

    org_id = user.org_id if user else "demo"
    _webhooks[wh_id] = {
        "id": wh_id,
        "org_id": org_id,
        "url": body.url,
        "secret": body.secret,
        "events": body.events,
        "active": True,
    }
    log.info("Webhook registered", extra={"id": wh_id, "url": body.url})
    return {"id": wh_id, "url": body.url, "events": body.events, "active": True}


@router.get("")
async def list_webhooks(user: CurrentUser | None = Depends(get_current_user)):
    """List all webhooks for the current org."""
    org_id = user.org_id if user else "demo"
    hooks = [v for v in _webhooks.values() if v["org_id"] == org_id]
    return {"webhooks": hooks}


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    user: CurrentUser | None = Depends(require_role("admin")),
):
    """Delete a webhook."""
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")
    del _webhooks[webhook_id]
    log.info("Webhook deleted", extra={"id": webhook_id})
    return {"deleted": True}
