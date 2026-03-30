"""
In-memory rate limiter with sliding window.

For production, replace with Redis-based sliding window.
"""

import logging
import time
from collections import defaultdict

log = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory sliding window rate limiter."""

    def __init__(self, default_limit: int = 100, window_seconds: int = 3600):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int | None = None) -> tuple[bool, dict]:
        """
        Check if request is allowed.

        Returns (allowed, info) where info contains remaining/reset metadata.
        """
        max_requests = limit or self.default_limit
        now = time.monotonic()
        window_start = now - self.window_seconds

        # Clean old entries
        self._requests[key] = [
            t for t in self._requests[key] if t > window_start
        ]

        current_count = len(self._requests[key])

        if current_count >= max_requests:
            reset_time = self._requests[key][0] + self.window_seconds - now
            return False, {
                "limit": max_requests,
                "remaining": 0,
                "reset_seconds": round(reset_time, 1),
            }

        self._requests[key].append(now)
        return True, {
            "limit": max_requests,
            "remaining": max_requests - current_count - 1,
            "reset_seconds": self.window_seconds,
        }


# Shared instance
rate_limiter = RateLimiter(default_limit=100, window_seconds=3600)
