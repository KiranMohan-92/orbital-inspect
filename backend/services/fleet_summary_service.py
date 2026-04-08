"""Fleet summary service — precomputed, cached portfolio statistics.

Caches the portfolio summary per-org so fleet-scale queries respond
in sub-second time. Invalidated on analysis completion.
"""

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

# In-memory cache: org_id -> (summary_dict, expires_at_monotonic)
_summary_cache: dict[str | None, tuple[dict[str, Any], float]] = {}
_DEFAULT_TTL = 60  # 1 minute cache


async def get_cached_portfolio_summary(org_id: str | None = None) -> dict[str, Any] | None:
    """Get portfolio summary from cache if available and fresh."""
    entry = _summary_cache.get(org_id)
    if entry is None:
        return None
    summary, expires_at = entry
    if time.monotonic() > expires_at:
        del _summary_cache[org_id]
        return None
    return summary


async def cache_portfolio_summary(org_id: str | None, summary: dict[str, Any], ttl: int = _DEFAULT_TTL) -> None:
    """Store portfolio summary in cache with TTL."""
    _summary_cache[org_id] = (summary, time.monotonic() + ttl)
    log.debug("Cached portfolio summary for org=%s (ttl=%ds)", org_id, ttl)


async def invalidate_portfolio_summary(org_id: str | None = None) -> None:
    """Invalidate cached summary for an org (called on analysis completion)."""
    _summary_cache.pop(org_id, None)
    log.debug("Invalidated portfolio summary cache for org=%s", org_id)


async def get_or_compute_portfolio_summary(org_id: str | None = None) -> dict[str, Any]:
    """Get portfolio summary from cache or compute fresh from DB.

    This is the main entry point for the portfolio summary endpoint.
    """
    # Check cache first
    cached = await get_cached_portfolio_summary(org_id)
    if cached is not None:
        return cached

    # Compute fresh from DB
    from db.base import async_session_factory
    from db.repository import AnalysisRepository

    async with async_session_factory() as session:
        repo = AnalysisRepository(session)
        summary = await repo.get_asset_portfolio_summary(org_id=org_id)

    # Cache it
    await cache_portfolio_summary(org_id, summary)
    return summary
