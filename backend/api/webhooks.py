"""
Webhook management API — register, list, delete webhook endpoints.
"""

import hashlib
import ipaddress
import logging
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from auth.dependencies import get_current_user, require_role, CurrentUser

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# In-memory webhook store (replace with DB in production)
_webhooks: dict[str, dict] = {}
_next_id = 1

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal", "169.254.169.254"}
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
]


def _validate_webhook_url(url: str) -> None:
    """Prevent SSRF by blocking internal/private URLs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError("Webhook URL must use HTTP(S)")
    hostname = parsed.hostname or ""
    if hostname in _BLOCKED_HOSTS:
        raise ValueError("Internal hosts are not allowed")
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                raise ValueError("Private/internal IPs are not allowed")
    except ValueError as e:
        if "not allowed" in str(e):
            raise


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

    # Validate URL to prevent SSRF
    try:
        _validate_webhook_url(body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    org_id = user.org_id if user else "demo"
    _webhooks[wh_id] = {
        "id": wh_id,
        "org_id": org_id,
        "url": body.url,
        "secret_hash": hashlib.sha256(body.secret.encode()).hexdigest() if body.secret else "",
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
