"""
Resilience patterns for external service calls.

Provides timeout, retry with exponential backoff, and circuit breaker
for Gemini API, CelesTrak, and NOAA SWPC calls.
"""

import asyncio
import logging
import time
from typing import TypeVar, Callable, Awaitable

log = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is in OPEN state."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern for external services.

    States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing recovery)
    """

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN

    def _check_state(self):
        if self.state == "OPEN":
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                log.info("Circuit breaker %s: OPEN → HALF_OPEN", self.name)
            else:
                raise CircuitBreakerOpen(f"Circuit breaker '{self.name}' is OPEN")

    def record_success(self):
        if self.state == "HALF_OPEN":
            log.info("Circuit breaker %s: HALF_OPEN → CLOSED", self.name)
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            log.warning(
                "Circuit breaker %s: CLOSED → OPEN (failures=%d)",
                self.name, self.failure_count,
            )

    async def call(self, coro_factory: Callable[[], Awaitable[T]]) -> T:
        """Execute a coroutine through the circuit breaker."""
        self._check_state()
        try:
            result = await coro_factory()
            self.record_success()
            return result
        except CircuitBreakerOpen:
            raise
        except Exception:
            self.record_failure()
            raise


# Shared circuit breakers for external services
gemini_breaker = CircuitBreaker("gemini", failure_threshold=5, recovery_timeout=60.0)
celestrak_breaker = CircuitBreaker("celestrak", failure_threshold=3, recovery_timeout=30.0)
swpc_breaker = CircuitBreaker("swpc", failure_threshold=3, recovery_timeout=30.0)


async def with_timeout(coro: Awaitable[T], timeout_seconds: float) -> T:
    """Wrap an awaitable with a timeout."""
    try:
        async with asyncio.timeout(timeout_seconds):
            return await coro
    except asyncio.TimeoutError:
        log.error("Operation timed out after %.1fs", timeout_seconds)
        raise


async def with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    retryable_exceptions: tuple = (Exception,),
) -> T:
    """
    Retry a coroutine with exponential backoff.

    Args:
        coro_factory: Callable that returns a new coroutine on each call
        max_attempts: Maximum number of attempts
        backoff_base: Base delay in seconds (multiplied by 2^attempt)
        retryable_exceptions: Tuple of exception types to retry on
    """
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await coro_factory()
        except retryable_exceptions as e:
            last_error = e
            if attempt < max_attempts - 1:
                delay = backoff_base * (2 ** attempt)
                log.warning(
                    "Attempt %d/%d failed, retrying in %.1fs",
                    attempt + 1, max_attempts, delay,
                    exc_info=False,
                )
                await asyncio.sleep(delay)
            else:
                log.error("All %d attempts failed", max_attempts)
    raise last_error  # type: ignore[misc]


async def resilient_call(
    coro_factory: Callable[[], Awaitable[T]],
    timeout_seconds: float = 120.0,
    max_retries: int = 2,
    circuit_breaker: CircuitBreaker | None = None,
) -> T:
    """
    Execute with full resilience stack: circuit breaker → retry → timeout.

    This is the main entry point for wrapping agent calls.
    """
    if circuit_breaker:
        return await circuit_breaker.call(
            lambda: with_retry(
                lambda: with_timeout(coro_factory(), timeout_seconds),
                max_attempts=max_retries,
            )
        )
    else:
        return await with_retry(
            lambda: with_timeout(coro_factory(), timeout_seconds),
            max_attempts=max_retries,
        )
