"""
Lumitrade Chaos Tests — Broker Failures (BF-001 to BF-010)
============================================================
Validates the CircuitBreaker protects the account when OANDA goes down.
A broken circuit breaker = unlimited failed API calls = rate limits = account lockout.

Per QTS v2.0 Section 7.1.
"""

import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from lumitrade.core.enums import CircuitBreakerState
from lumitrade.execution_engine.circuit_breaker import (
    CircuitBreaker,
    FAILURE_THRESHOLD,
    FAILURE_WINDOW_SEC,
    RESET_TIMEOUT_SEC,
)


@pytest.mark.chaos
class TestBrokerFailures:
    """BF-001 to BF-010: Circuit breaker under hostile broker conditions."""

    @pytest.fixture
    def cb(self) -> CircuitBreaker:
        return CircuitBreaker()

    # ── BF-001: Circuit trips after 3 failures ────────────────────

    @pytest.mark.asyncio
    async def test_bf001_circuit_trips_after_threshold(self, cb: CircuitBreaker):
        """BF-001: 3 failures within 60s window trips circuit to OPEN."""
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open is True

    # ── BF-002: OPEN circuit blocks requests ──────────────────────

    @pytest.mark.asyncio
    async def test_bf002_open_circuit_stays_open(self, cb: CircuitBreaker):
        """BF-002: check_and_transition returns OPEN when recently tripped."""
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()

        state = await cb.check_and_transition()
        assert state == CircuitBreakerState.OPEN

    # ── BF-003: Transitions to HALF_OPEN after timeout ────────────

    @pytest.mark.asyncio
    async def test_bf003_transitions_to_half_open(self, cb: CircuitBreaker):
        """BF-003: After RESET_TIMEOUT_SEC, OPEN transitions to HALF_OPEN."""
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()

        # Simulate time passage by backdating _opened_at
        cb._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )

        state = await cb.check_and_transition()
        assert state == CircuitBreakerState.HALF_OPEN

    # ── BF-004: Success in HALF_OPEN resets to CLOSED ─────────────

    @pytest.mark.asyncio
    async def test_bf004_half_open_success_closes(self, cb: CircuitBreaker):
        """BF-004: A successful call in HALF_OPEN resets to CLOSED."""
        # Trip the breaker
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()

        # Transition to HALF_OPEN
        cb._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )
        await cb.check_and_transition()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Record success — should close
        await cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_open is False

    # ── BF-005: Failure in HALF_OPEN reopens circuit ──────────────

    @pytest.mark.asyncio
    async def test_bf005_half_open_failure_reopens(self, cb: CircuitBreaker):
        """BF-005: A failure in HALF_OPEN reopens the circuit to OPEN."""
        # Trip the breaker
        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()

        # Transition to HALF_OPEN
        cb._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )
        await cb.check_and_transition()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Failure in HALF_OPEN — record_failure adds to _failures list
        # which already has >= FAILURE_THRESHOLD entries, so it re-trips
        await cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    # ── BF-006: Old failures expire outside window ────────────────

    @pytest.mark.asyncio
    async def test_bf006_old_failures_expire(self, cb: CircuitBreaker):
        """BF-006: Failures older than 60s are pruned and don't count."""
        # Add 2 failures in the past (outside the window)
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=FAILURE_WINDOW_SEC + 10
        )
        cb._failures = [old_time, old_time]

        # Add 1 recent failure — total recent = 1, below threshold
        await cb.record_failure()

        assert cb.state == CircuitBreakerState.CLOSED
        # Old failures should have been pruned
        assert len(cb._failures) == 1

    # ── BF-007: 2 failures does not trip ──────────────────────────

    @pytest.mark.asyncio
    async def test_bf007_below_threshold_stays_closed(self, cb: CircuitBreaker):
        """BF-007: 2 failures (below threshold of 3) keeps circuit CLOSED."""
        await cb.record_failure()
        await cb.record_failure()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_open is False

    # ── BF-008: Success in CLOSED is noop ─────────────────────────

    @pytest.mark.asyncio
    async def test_bf008_success_in_closed_is_noop(self, cb: CircuitBreaker):
        """BF-008: record_success in CLOSED state does nothing."""
        await cb.record_success()

        assert cb.state == CircuitBreakerState.CLOSED
        assert len(cb._failures) == 0

    # ── BF-009: is_open property reflects state ───────────────────

    @pytest.mark.asyncio
    async def test_bf009_is_open_reflects_state(self, cb: CircuitBreaker):
        """BF-009: is_open is True only when state is OPEN."""
        assert cb.is_open is False

        for _ in range(FAILURE_THRESHOLD):
            await cb.record_failure()
        assert cb.is_open is True

        # Transition to HALF_OPEN
        cb._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )
        await cb.check_and_transition()
        assert cb.is_open is False  # HALF_OPEN is not OPEN

    # ── BF-010: Concurrent failures don't corrupt state ───────────

    @pytest.mark.asyncio
    async def test_bf010_concurrent_failures_safe(self, cb: CircuitBreaker):
        """BF-010: Multiple concurrent record_failure calls don't corrupt state."""
        # Fire 5 concurrent failures — the lock should serialize them
        await asyncio.gather(*[cb.record_failure() for _ in range(5)])

        # State should be OPEN (>= 3 failures), not corrupted
        assert cb.state == CircuitBreakerState.OPEN
        # Failures list should have exactly 5 entries
        assert len(cb._failures) == 5
