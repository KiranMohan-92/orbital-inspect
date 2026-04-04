"""
Queue dispatch helpers for durable analysis execution.
"""

from __future__ import annotations

import logging

from arq.connections import RedisSettings, create_pool

from config import settings

log = logging.getLogger(__name__)


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.REDIS_URL)


def should_use_queue_dispatch() -> bool:
    return not settings.DEMO_MODE and not settings.E2E_TEST_MODE


async def enqueue_analysis_job(analysis_id: str) -> str:
    redis = await create_pool(
        _redis_settings(),
        default_queue_name=settings.ANALYSIS_QUEUE_NAME,
    )
    try:
        job_id = f"analysis:{analysis_id}"
        job = await redis.enqueue_job(
            "run_analysis_job",
            analysis_id,
            _job_id=job_id,
            _queue_name=settings.ANALYSIS_QUEUE_NAME,
        )
        if job is None:
            return job_id
        return job.job_id
    finally:
        await redis.close(close_connection_pool=True)


async def check_redis_health() -> dict[str, object]:
    redis = await create_pool(
        _redis_settings(),
        default_queue_name=settings.ANALYSIS_QUEUE_NAME,
    )
    try:
        pong = await redis.ping()
        queue_name = settings.ANALYSIS_QUEUE_NAME
        queued = await redis.llen(queue_name)
        return {
            "ok": bool(pong),
            "queue_name": queue_name,
            "queued_jobs": queued,
        }
    finally:
        await redis.close(close_connection_pool=True)
