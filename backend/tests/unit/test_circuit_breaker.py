"""
Circuit Breaker Tests
=======================
Per QTS Table 11 (BF-001 to BF-004).
100% coverage required.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from lumitrade.core.enums import CircuitBreakerState
from lumitrade.execution_engine.circuit_breaker import (
    CircuitBreaker,
    FAILURE_THRESHOLD,
    FAILURE_WINDOW_SEC,
    RESET_TIMEOUT_SEC,
)


@pytest.fixture
def cb():
    return CircuitBreaker()


class TestCircuitBreakerStates:
    """BF-001 to BF-004: State transitions."""

    @pytest.mark.asyncio
    async def test_starts_closed(self, cb):
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_open is False

    @pytest.mark.asyncio
    async def test_trips_after_3_failures(self, cb):
        """BF-001: 3 failures in 60s -> OPEN."""
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open is True

    @pytest.mark.asyncio
    async def test_does_not_trip_below_threshold(self, cb):
        for _ in range(FAILURE_THRESHOLD - 1):
            await cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_after_reset_timeout(self, cb):
        """BF-002: OPEN -> HALF_OPEN after 30s."""
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        # Simulate time passing
        cb._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )
        state = await cb.check_and_transition()
        assert state == CircuitBreakerState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_after_success_in_half_open(self, cb):
        """BF-003: HALF_OPEN + success -> CLOSED."""
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()
        cb._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )
        await cb.check_and_transition()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        await cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_open is False

    @pytest.mark.asyncio
    async def test_reopens_after_failure_in_half_open(self, cb):
        """BF-004: HALF_OPEN + failure -> OPEN."""
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()
        cb._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )
        await cb.check_and_transition()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        await cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_old_failures_expire_outside_window(self, cb):
        """Failures older than 60s are pruned."""
        # Add 2 failures that are old
        cb._failures = [
            datetime.now(timezone.utc) - timedelta(seconds=FAILURE_WINDOW_SEC + 10),
            datetime.now(timezone.utc) - timedelta(seconds=FAILURE_WINDOW_SEC + 5),
        ]
        # Add 1 recent failure — should not trip (only 1 in window)
        await cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_success_in_closed_state_is_noop(self, cb):
        """Success while CLOSED doesn't change state."""
        await cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_check_and_transition_stays_closed(self, cb):
        """check_and_transition returns CLOSED when no failures."""
        state = await cb.check_and_transition()
        assert state == CircuitBreakerState.CLOSED
