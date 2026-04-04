"""
Readiness checks for database, queue, and storage backends.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from config import settings
from db.base import engine
from services.observability_service import telemetry_state
from services.queue_service import check_redis_health, should_use_queue_dispatch


async def check_database_health() -> dict[str, object]:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def check_storage_health() -> dict[str, object]:
    try:
        if settings.STORAGE_BACKEND == "local":
            root = settings.storage_local_root_path
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".readiness"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return {"ok": True, "backend": "local"}

        from services.storage_service import get_storage_backend

        backend = get_storage_backend()
        if hasattr(backend, "_ensure_bucket"):
            backend._ensure_bucket()  # type: ignore[attr-defined]
        return {"ok": True, "backend": settings.STORAGE_BACKEND}
    except Exception as exc:
        return {"ok": False, "backend": settings.STORAGE_BACKEND, "error": str(exc)}


async def readiness_snapshot() -> dict[str, object]:
    db = await check_database_health()
    try:
        queue = await check_redis_health()
    except Exception as exc:
        queue = {"ok": False, "error": str(exc)}
    storage = await check_storage_health()
    observability = telemetry_state()
    queue_required = settings.REDIS_REQUIRED or should_use_queue_dispatch()
    observability_required = settings.OTEL_REQUIRED
    return {
        "ok": bool(
            db.get("ok")
            and storage.get("ok")
            and (queue.get("ok") or not queue_required)
            and (observability.get("instrumented") or not observability_required)
        ),
        "database": db,
        "queue": queue,
        "storage": storage,
        "observability": observability,
        "queue_required": queue_required,
        "observability_required": observability_required,
    }
