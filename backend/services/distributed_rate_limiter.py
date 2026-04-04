"""
Rate limiting with Redis-backed fixed windows and memory fallback.
"""

from __future__ import annotations

import time

from redis.asyncio import Redis

from config import settings


class MemoryFixedWindowLimiter:
    def __init__(self):
        self._state: dict[str, tuple[int, float]] = {}

    async def check(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, dict]:
        now = time.time()
        count, expires_at = self._state.get(key, (0, now + window_seconds))
        if now >= expires_at:
            count, expires_at = 0, now + window_seconds
        if count >= limit:
            return False, {
                "limit": limit,
                "remaining": 0,
                "reset_seconds": max(0, int(expires_at - now)),
            }
        count += 1
        self._state[key] = (count, expires_at)
        return True, {
            "limit": limit,
            "remaining": max(0, limit - count),
            "reset_seconds": max(0, int(expires_at - now)),
        }


_memory_limiter = MemoryFixedWindowLimiter()


async def _redis_client() -> Redis:
    return Redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


async def _check_redis_limit(
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> tuple[bool, dict]:
    redis = await _redis_client()
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        current_count, ttl = await pipe.execute()
        if current_count == 1:
            await redis.expire(key, window_seconds)
            ttl = window_seconds
        remaining = max(0, limit - int(current_count))
        allowed = int(current_count) <= limit
        return allowed, {
            "limit": limit,
            "remaining": remaining,
            "reset_seconds": max(0, ttl if ttl and ttl > 0 else window_seconds),
        }
    finally:
        await redis.close()


async def check_rate_limit(
    bucket: str,
    subject: str,
    *,
    limit: int,
    window_seconds: int = 3600,
) -> tuple[bool, dict]:
    key = f"ratelimit:{bucket}:{subject}:{int(time.time() // window_seconds)}"
    if settings.RATE_LIMIT_BACKEND == "redis":
        try:
            return await _check_redis_limit(key, limit=limit, window_seconds=window_seconds)
        except Exception:
            if not settings.RATE_LIMIT_FAIL_OPEN:
                raise
    return await _memory_limiter.check(key, limit=limit, window_seconds=window_seconds)
