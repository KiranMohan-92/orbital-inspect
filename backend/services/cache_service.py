"""Fleet-scale caching layer for external data lookups."""

import json
import logging
import time
from typing import Any, Callable, Awaitable

log = logging.getLogger(__name__)


class CacheService:
    """Redis-backed cache with in-memory LRU fallback."""

    def __init__(self, redis_url: str | None = None, prefix: str = "oi:cache", default_ttl: int = 900):
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._redis = None
        self._memory_cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)
        self._redis_url = redis_url

    async def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is None and self._redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception:
                log.warning("Redis unavailable for cache, using in-memory fallback")
                self._redis = None
        return self._redis

    def _key(self, namespace: str, identifier: str) -> str:
        return f"{self._prefix}:{namespace}:{identifier}"

    async def get(self, namespace: str, identifier: str) -> Any | None:
        """Get cached value. Returns None on miss."""
        key = self._key(namespace, identifier)

        # Try Redis first
        r = await self._get_redis()
        if r:
            try:
                raw = await r.get(key)
                if raw is not None:
                    return json.loads(raw)
            except Exception:
                pass

        # Fall back to memory
        entry = self._memory_cache.get(key)
        if entry and entry[1] > time.monotonic():
            return entry[0]
        elif entry:
            del self._memory_cache[key]
        return None

    async def set(self, namespace: str, identifier: str, value: Any, ttl: int | None = None) -> None:
        """Store value with TTL."""
        key = self._key(namespace, identifier)
        ttl = ttl or self._default_ttl
        serialized = json.dumps(value, default=str)

        # Try Redis
        r = await self._get_redis()
        if r:
            try:
                await r.setex(key, ttl, serialized)
                return
            except Exception:
                pass

        # Fall back to memory (cap at 10,000 entries)
        if len(self._memory_cache) > 10_000:
            # Evict oldest 20%
            sorted_keys = sorted(self._memory_cache.keys(), key=lambda k: self._memory_cache[k][1])
            for k in sorted_keys[:2000]:
                del self._memory_cache[k]
        self._memory_cache[key] = (value, time.monotonic() + ttl)

    async def get_or_fetch(
        self,
        namespace: str,
        identifier: str,
        fetcher: Callable[[], Awaitable[Any]],
        ttl: int | None = None,
    ) -> Any:
        """Get from cache or call fetcher on miss. Stale-while-revalidate."""
        cached = await self.get(namespace, identifier)
        if cached is not None:
            return cached

        value = await fetcher()
        if value is not None:
            await self.set(namespace, identifier, value, ttl)
        return value

    async def invalidate(self, namespace: str, identifier: str) -> None:
        """Remove a specific cache entry."""
        key = self._key(namespace, identifier)
        r = await self._get_redis()
        if r:
            try:
                await r.delete(key)
            except Exception:
                pass
        self._memory_cache.pop(key, None)


# Module-level singleton, initialized from config
_instance: CacheService | None = None


def get_cache_service() -> CacheService:
    global _instance
    if _instance is None:
        from config import settings
        _instance = CacheService(
            redis_url=settings.REDIS_URL if not settings.DEMO_MODE else None,
            prefix="oi:cache",
            default_ttl=settings.CACHE_DEFAULT_TTL_SECONDS,
        )
    return _instance
