"""
Webhook dispatch service with HMAC signing and retry.

Sends notifications to registered endpoints when analyses complete,
reports are approved, etc.
"""

import hashlib
import hmac
import json
import logging
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
    url: str,
    event_type: str,
    payload: dict,
    secret: str = "",
    max_retries: int = 3,
) -> bool:
    """
    Send a webhook with HMAC signature and retry.

    Returns True if delivery succeeded, False otherwise.
    """
    body = json.dumps({
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Orbital-Event": event_type,
    }
    if secret:
        headers["X-Orbital-Signature"] = f"sha256={sign_payload(body, secret)}"

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, content=body, headers=headers)
                if resp.status_code < 300:
                    log.info(
                        "Webhook delivered",
                        extra={"url": url, "event": event_type, "status": resp.status_code},
                    )
                    return True
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

        if attempt < max_retries - 1:
            import asyncio
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    log.error("Webhook delivery failed after all retries", extra={"url": url, "event": event_type})
    return False
