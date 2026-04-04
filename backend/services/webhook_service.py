"""
Webhook dispatch service with HMAC signing and retry.

Sends notifications to registered endpoints when analyses complete,
reports are approved, etc.
"""

import hashlib
import hmac
import json
import logging
import uuid
import httpx
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, read=15.0)


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


async def dispatch_webhook(
    webhook_id: str | None,
    url: str,
    event_type: str,
    payload: dict,
    secret: str = "",
    max_retries: int = 3,
) -> dict[str, object]:
    """
    Send a webhook with HMAC signature and retry.

    Returns delivery metadata including status and retry count.
    """
    delivery_id = uuid.uuid4().hex
    body = json.dumps({
        "delivery_id": delivery_id,
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_checksum = hashlib.sha256(body).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Orbital-Event": event_type,
        "X-Orbital-Delivery-ID": delivery_id,
    }
    if webhook_id:
        headers["X-Orbital-Webhook-ID"] = webhook_id
    if secret:
        headers["X-Orbital-Signature"] = f"sha256={sign_payload(body, secret)}"

    last_status_code: int | None = None
    last_excerpt: str | None = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, content=body, headers=headers)
                last_status_code = resp.status_code
                last_excerpt = resp.text[:500]
                if resp.status_code < 300:
                    log.info(
                        "Webhook delivered",
                        extra={"url": url, "event": event_type, "status": resp.status_code},
                    )
                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "attempt_count": attempt + 1,
                        "response_excerpt": last_excerpt,
                        "delivery_id": delivery_id,
                        "request_body_checksum": body_checksum,
                    }
                log.warning(
                    "Webhook failed",
                    extra={
                        "url": url,
                        "status": resp.status_code,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                    },
                )
        except Exception as e:
            log.warning(
                "Webhook error",
                extra={
                    "url": url,
                    "error": str(e),
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                },
            )
            last_excerpt = str(e)[:500]

        if attempt < max_retries - 1:
            import asyncio
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    log.error("Webhook delivery failed after all retries", extra={"url": url, "event": event_type})
    return {
        "success": False,
        "status_code": last_status_code,
        "attempt_count": max_retries,
        "response_excerpt": last_excerpt,
        "delivery_id": delivery_id,
        "request_body_checksum": body_checksum,
    }


async def dispatch_registered_webhooks(
    *,
    org_id: str | None,
    event_type: str,
    payload: dict,
) -> None:
    try:
        from db.base import async_session_factory
        from db.repository import WebhookRepository, WebhookDeliveryRepository
    except ImportError:
        return

    async with async_session_factory() as session:
        webhook_repo = WebhookRepository(session)
        delivery_repo = WebhookDeliveryRepository(session)
        hooks = await webhook_repo.list_for_org(org_id)
        for hook in hooks:
            if event_type not in (hook.events or []):
                continue
            secret = ""
            try:
                from services.secret_service import decrypt_webhook_secret

                secret = decrypt_webhook_secret(getattr(hook, "secret_ciphertext", "") or "")
            except ValueError as exc:
                await delivery_repo.create(
                    webhook_id=hook.id,
                    event_type=event_type,
                    success=False,
                    status_code=None,
                    attempt_count=0,
                    response_excerpt=str(exc),
                    request_body_checksum=None,
                    delivered_at=None,
                )
                continue
            result = await dispatch_webhook(
                hook.id,
                hook.url,
                event_type,
                payload,
                secret=secret,
            )
            await delivery_repo.create(
                webhook_id=hook.id,
                event_type=event_type,
                success=bool(result["success"]),
                status_code=result.get("status_code"),
                attempt_count=int(result.get("attempt_count", 1)),
                response_excerpt=result.get("response_excerpt"),
                request_body_checksum=result.get("request_body_checksum"),
                delivered_at=datetime.now(timezone.utc) if result["success"] else None,
            )
