"""Tests for resilience patterns: timeout, retry, circuit breaker."""
import asyncio
import time
from unittest.mock import patch

import pytest

from services.resilience import (
    CircuitBreaker,
    CircuitBreakerOpen,
    resilient_call,
    with_retry,
    with_timeout,
)


# ─── with_timeout ────────────────────────────────────────────────────────────

async def test_with_timeout_succeeds_within_limit():
    async def fast():
        return "ok"

    result = await with_timeout(fast(), timeout_seconds=5.0)
    assert result == "ok"


async def test_with_timeout_raises_on_exceeded():
    async def slow():
        await asyncio.sleep(10)
        return "never"

    with pytest.raises(asyncio.TimeoutError):
        await with_timeout(slow(), timeout_seconds=0.01)


# ─── with_retry ──────────────────────────────────────────────────────────────

async def test_with_retry_succeeds_first_attempt():
    calls = []

    async def fn():
        calls.append(1)
        return "done"

    result = await with_retry(fn, max_attempts=3, backoff_base=0.0)
    assert result == "done"
    assert len(calls) == 1


async def test_with_retry_succeeds_on_second_attempt():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("transient")
        return "recovered"

    result = await with_retry(fn, max_attempts=3, backoff_base=0.0)
    assert result == "recovered"
    assert len(calls) == 2


async def test_with_retry_exhausts_all_attempts():
    calls = []

    async def fn():
        calls.append(1)
        raise RuntimeError("always fails")

    with pytest.raises(RuntimeError, match="always fails"):
        await with_retry(fn, max_attempts=3, backoff_base=0.0)

    assert len(calls) == 3


async def test_with_retry_respects_retryable_exceptions():
    """Non-retryable exceptions should propagate immediately without retry."""
    calls = []

    async def fn():
        calls.append(1)
        raise KeyError("not retryable")

    with pytest.raises(KeyError):
        await with_retry(
            fn,
            max_attempts=3,
            backoff_base=0.0,
            retryable_exceptions=(ValueError,),
        )

    # Should have only tried once since KeyError is not in retryable_exceptions
    assert len(calls) == 1


# ─── CircuitBreaker ──────────────────────────────────────────────────────────

async def test_circuit_breaker_stays_closed_on_success():
    cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60.0)

    async def fn():
        return "ok"

    result = await cb.call(fn)
    assert result == "ok"
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0


async def test_circuit_breaker_transitions_closed_to_open():
    cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60.0)

    async def failing():
        raise RuntimeError("boom")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(failing)

    assert cb.state == "OPEN"
    assert cb.failure_count == 3


async def test_circuit_breaker_raises_when_open():
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60.0)

    async def failing():
        raise RuntimeError("boom")

    # Trip the breaker
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(failing)

    assert cb.state == "OPEN"

    # Next call should raise CircuitBreakerOpen immediately
    with pytest.raises(CircuitBreakerOpen):
        await cb.call(failing)


async def test_circuit_breaker_open_to_half_open_after_recovery_timeout():
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30.0)

    async def failing():
        raise RuntimeError("boom")

    # Trip the breaker
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(failing)

    assert cb.state == "OPEN"

    # Simulate recovery timeout elapsed
    with patch("services.resilience.time.monotonic", return_value=cb.last_failure_time + 31.0):
        cb._check_state()

    assert cb.state == "HALF_OPEN"


async def test_circuit_breaker_half_open_to_closed_on_success():
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30.0)

    async def failing():
        raise RuntimeError("boom")

    async def succeeding():
        return "ok"

    # Trip the breaker
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(failing)

    # Force HALF_OPEN
    cb.state = "HALF_OPEN"

    result = await cb.call(succeeding)
    assert result == "ok"
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0


async def test_circuit_breaker_record_success_resets_failure_count():
    cb = CircuitBreaker("test", failure_threshold=5, recovery_timeout=60.0)
    cb.failure_count = 3
    cb.record_success()
    assert cb.failure_count == 0
    assert cb.state == "CLOSED"


async def test_circuit_breaker_does_not_catch_circuit_breaker_open():
    """CircuitBreakerOpen must propagate without recording as failure."""
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60.0)

    # Trip the breaker
    async def failing():
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(failing)

    failure_count_before = cb.failure_count

    # CircuitBreakerOpen should not increment failure_count
    with pytest.raises(CircuitBreakerOpen):
        await cb.call(failing)

    assert cb.failure_count == failure_count_before


# ─── resilient_call ──────────────────────────────────────────────────────────

async def test_resilient_call_succeeds():
    async def fn():
        return 42

    result = await resilient_call(fn, timeout_seconds=5.0, max_retries=2)
    assert result == 42


async def test_resilient_call_with_circuit_breaker_succeeds():
    cb = CircuitBreaker("integration-test", failure_threshold=5, recovery_timeout=60.0)

    async def fn():
        return "success"

    result = await resilient_call(fn, timeout_seconds=5.0, max_retries=2, circuit_breaker=cb)
    assert result == "success"
    assert cb.state == "CLOSED"


async def test_resilient_call_raises_circuit_breaker_open_when_tripped():
    cb = CircuitBreaker("integration-test", failure_threshold=2, recovery_timeout=60.0)

    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("service down")

    # Exhaust attempts to trip the breaker (max_retries=1 means 1 attempt per resilient_call)
    with pytest.raises(RuntimeError):
        await resilient_call(fn, timeout_seconds=5.0, max_retries=1, circuit_breaker=cb)

    with pytest.raises(RuntimeError):
        await resilient_call(fn, timeout_seconds=5.0, max_retries=1, circuit_breaker=cb)

    assert cb.state == "OPEN"

    # Now the breaker is open, next call should raise CircuitBreakerOpen
    with pytest.raises(CircuitBreakerOpen):
        await resilient_call(fn, timeout_seconds=5.0, max_retries=1, circuit_breaker=cb)


async def test_resilient_call_timeout_propagates():
    async def slow():
        await asyncio.sleep(10)
        return "never"

    with pytest.raises(asyncio.TimeoutError):
        await resilient_call(slow, timeout_seconds=0.01, max_retries=1)
