# Phase 9: Paper Trading — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clear all test debt from Phases 2-7, set up monitoring infrastructure (Sentry + UptimeRobot), deploy to Railway in PAPER mode, define and verify the 13 Go/No-Go gates, and prepare the system for live trading after 50+ successful paper trades.

**Architecture:** This plan is organized into 4 waves. Wave 1 backfills all missing test suites (chaos, integration, security, performance). Wave 2 integrates Sentry error tracking and creates the critical test runner script. Wave 3 handles Railway deployment and external monitoring. Wave 4 defines Go/No-Go gates and checklists for live readiness.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio, respx (HTTP mocking), hypothesis, structlog, sentry-sdk, Railway CLI, UptimeRobot, Supabase

**Spec References:**
- `docs/specs/Lumitrade_QTS_v2.0.md` — Test specs, Go/No-Go gates (Section 8.2)
- `docs/specs/Lumitrade_DOS_v2.0.md` — Infra checklist (Section 9.1), Sentry (Section 6.2)
- `docs/specs/Lumitrade_SS_v2.0.md` — Security audit (Section 9.1)
- `docs/specs/Lumitrade_BDS_v2.0.md` — All module implementations
- `docs/specs/Lumitrade_MASTER_PROMPT_FINAL.md` — Phase 9 steps

---

## Wave 1: Test Backfill (Chaos + Integration + Security)

### Task 1: Chaos Tests — Data Feed Failures (test_data_failures.py)

**Files:**
- Create: `backend/tests/chaos/test_data_failures.py`
- Reference: `backend/lumitrade/data_engine/validator.py`
- Reference: `backend/lumitrade/data_engine/engine.py`
- Reference: `backend/lumitrade/data_engine/price_stream.py`

Tests the system's resilience when data feeds fail, corrupt, or go stale. All external APIs mocked with respx. These tests verify the DataValidator and DataEngine handle every failure gracefully.

- [ ] **Step 1: Write DF-001 through DF-008 chaos tests**

```python
"""
Chaos tests for data feed failures.
Verifies the system handles corrupt, stale, and missing data gracefully.
File: tests/chaos/test_data_failures.py
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from lumitrade.data_engine.validator import DataValidator
from lumitrade.core.models import PriceTick, Candle, DataQuality


@pytest.fixture
def validator():
    return DataValidator()


def _make_tick(pair="EUR_USD", bid="1.08430", ask="1.08450",
               age_seconds=0):
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return PriceTick(
        pair=pair,
        bid=Decimal(bid),
        ask=Decimal(ask),
        timestamp=ts,
    )


def _make_candle(timeframe="M15", offset_minutes=0,
                 o="1.0840", h="1.0850", l="1.0830", c="1.0845"):
    return Candle(
        time=datetime.now(timezone.utc) - timedelta(minutes=offset_minutes),
        open=Decimal(o), high=Decimal(h), low=Decimal(l), close=Decimal(c),
        volume=100, complete=True, timeframe=timeframe,
    )


class TestDataFeedFailures:
    """DF-001 to DF-008: Data feed chaos scenarios."""

    def test_df001_stale_price_detected_and_rejected(self, validator):
        """DF-001: Price feed goes stale (>5s old) — must be flagged."""
        tick = _make_tick(age_seconds=10)
        quality = validator.validate_tick(tick)
        assert not quality.is_fresh
        assert not quality.is_tradeable

    def test_df002_spike_price_detected_and_rejected(self, validator):
        """DF-002: Artificial price spike (>3 sigma) — must be caught."""
        # Build stable price history first
        for i in range(25):
            normal = _make_tick(bid=f"1.{8430 + i % 3:05d}",
                                ask=f"1.{8450 + i % 3:05d}")
            validator.validate_tick(normal)

        # Inject spike — 500 pips away from mean
        spike = _make_tick(bid="1.13000", ask="1.13020")
        quality = validator.validate_tick(spike)
        assert quality.spike_detected
        assert not quality.is_tradeable

    def test_df003_wide_spread_rejected(self, validator):
        """DF-003: Spread exceeds 5 pip hard ceiling — trade blocked."""
        tick = _make_tick(bid="1.08400", ask="1.08470")  # 7 pip spread
        quality = validator.validate_tick(tick)
        assert not quality.spread_acceptable
        assert not quality.is_tradeable

    def test_df004_candle_gap_detected(self, validator):
        """DF-004: Large gap between candles — must be caught."""
        candles = [
            _make_candle(offset_minutes=0),
            _make_candle(offset_minutes=60),  # 60 min gap on M15 (expected ~15)
        ]
        result = validator.validate_candles(candles)
        assert not result

    def test_df005_ohlc_integrity_violation_caught(self, validator):
        """DF-005: OHLC integrity broken (low > high) — must reject."""
        bad_candle = _make_candle(o="1.0840", h="1.0830", l="1.0850", c="1.0845")
        # low=1.0850 > high=1.0830 — invalid
        result = validator.validate_candles([bad_candle])
        assert not result

    def test_df006_spike_not_added_to_price_history(self, validator):
        """DF-006: Detected spikes must NOT contaminate rolling history."""
        # Seed history
        for i in range(25):
            normal = _make_tick(bid="1.08430", ask="1.08450")
            validator.validate_tick(normal)

        history_before = len(validator._price_history.get("EUR_USD", []))

        # Inject spike
        spike = _make_tick(bid="1.13000", ask="1.13020")
        validator.validate_tick(spike)

        history_after = len(validator._price_history.get("EUR_USD", []))
        assert history_after == history_before  # No growth from spike

    def test_df007_all_validations_pass_for_clean_data(self, validator):
        """DF-007: Clean, fresh, normal data passes all checks."""
        tick = _make_tick(age_seconds=0)
        quality = validator.validate_tick(tick)
        assert quality.is_fresh
        assert not quality.spike_detected
        assert quality.spread_acceptable
        assert quality.is_tradeable

    def test_df008_empty_candle_list_is_valid(self, validator):
        """DF-008: Empty candle list should not crash."""
        result = validator.validate_candles([])
        assert result  # No candles = no gaps = valid
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/chaos/test_data_failures.py -v`
Expected: 8 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/chaos/test_data_failures.py
git commit -m "test: add chaos tests for data feed failures (DF-001 to DF-008)"
```

---

### Task 2: Chaos Tests — Broker API Failures (test_broker_failures.py)

**Files:**
- Create: `backend/tests/chaos/test_broker_failures.py`
- Reference: `backend/lumitrade/execution_engine/circuit_breaker.py`
- Reference: `backend/lumitrade/infrastructure/oanda_client.py`

Tests system resilience when OANDA API fails — timeouts, 5xx errors, rate limits, partial fills, malformed responses.

- [ ] **Step 1: Write BF-001 through BF-010 broker failure tests**

```python
"""
Chaos tests for OANDA broker API failures.
Verifies circuit breaker, retry logic, and graceful degradation.
File: tests/chaos/test_broker_failures.py
"""
import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from lumitrade.execution_engine.circuit_breaker import (
    CircuitBreaker, FAILURE_THRESHOLD, RESET_TIMEOUT_SEC
)
from lumitrade.core.enums import CircuitBreakerState


@pytest.fixture
def breaker():
    return CircuitBreaker()


class TestBrokerFailures:
    """BF-001 to BF-010: Broker API failure scenarios."""

    @pytest.mark.asyncio
    async def test_bf001_circuit_trips_after_3_failures(self, breaker):
        """BF-001: 3 failures within 60s trips circuit to OPEN."""
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_bf002_open_circuit_blocks_requests(self, breaker):
        """BF-002: OPEN circuit returns OPEN state on check."""
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()
        state = await breaker.check_and_transition()
        assert state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_bf003_half_open_after_timeout(self, breaker):
        """BF-003: Circuit transitions to HALF_OPEN after reset timeout."""
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()

        # Simulate time passing
        breaker._opened_at = datetime.now(timezone.utc) - \
            __import__('datetime').timedelta(seconds=RESET_TIMEOUT_SEC + 1)

        state = await breaker.check_and_transition()
        assert state == CircuitBreakerState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_bf004_success_in_half_open_closes_circuit(self, breaker):
        """BF-004: Success during HALF_OPEN resets to CLOSED."""
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()

        breaker._opened_at = datetime.now(timezone.utc) - \
            __import__('datetime').timedelta(seconds=RESET_TIMEOUT_SEC + 1)
        await breaker.check_and_transition()

        await breaker.record_success()
        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_bf005_failure_in_half_open_reopens(self, breaker):
        """BF-005: Failure during HALF_OPEN reopens circuit."""
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()

        breaker._opened_at = datetime.now(timezone.utc) - \
            __import__('datetime').timedelta(seconds=RESET_TIMEOUT_SEC + 1)
        await breaker.check_and_transition()

        await breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_bf006_old_failures_expire(self, breaker):
        """BF-006: Failures older than 60s window are discarded."""
        # Record 2 failures with old timestamps
        breaker._failures = [
            datetime.now(timezone.utc) - __import__('datetime').timedelta(seconds=120),
            datetime.now(timezone.utc) - __import__('datetime').timedelta(seconds=90),
        ]
        # Record a 3rd recent failure — should NOT trip (old ones pruned)
        await breaker.record_failure()
        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_bf007_two_failures_does_not_trip(self, breaker):
        """BF-007: Below threshold (2 of 3) keeps circuit CLOSED."""
        await breaker.record_failure()
        await breaker.record_failure()
        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_bf008_success_in_closed_is_noop(self, breaker):
        """BF-008: Recording success in CLOSED state has no effect."""
        await breaker.record_success()
        assert breaker.state == CircuitBreakerState.CLOSED
        assert len(breaker._failures) == 0

    @pytest.mark.asyncio
    async def test_bf009_is_open_property(self, breaker):
        """BF-009: is_open property reflects OPEN state correctly."""
        assert not breaker.is_open
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()
        assert breaker.is_open

    @pytest.mark.asyncio
    async def test_bf010_concurrent_failures_thread_safe(self, breaker):
        """BF-010: Concurrent failure recordings don't corrupt state."""
        async def record():
            await breaker.record_failure()

        await asyncio.gather(*[record() for _ in range(10)])
        assert breaker.state == CircuitBreakerState.OPEN
        # Should not crash or have more than 10 failures
        assert len(breaker._failures) <= 10
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/chaos/test_broker_failures.py -v`
Expected: 10 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/chaos/test_broker_failures.py
git commit -m "test: add chaos tests for broker API failures (BF-001 to BF-010)"
```

---

### Task 3: Chaos Tests — Crash Recovery (test_crash_recovery.py)

**Files:**
- Create: `backend/tests/chaos/test_crash_recovery.py`
- Reference: `backend/lumitrade/state/manager.py`
- Reference: `backend/lumitrade/state/lock.py`
- Reference: `backend/lumitrade/state/reconciler.py`

Tests that the system recovers correctly after crashes — state restoration, lock release, position reconciliation.

- [ ] **Step 1: Write CR-001 through CR-010 crash recovery tests**

```python
"""
Chaos tests for crash recovery.
Verifies state persistence, lock management, and position reconciliation.
File: tests/chaos/test_crash_recovery.py
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestCrashRecovery:
    """CR-001 to CR-010: Crash and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_cr001_state_persisted_to_db(self):
        """CR-001: System state is written to DB on persist_loop."""
        db = AsyncMock()
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "risk_state": "NORMAL",
            "open_trades": "[]",
            "pending_orders": "[]",
            "daily_pnl_usd": "0",
            "weekly_pnl_usd": "0",
            "daily_trade_count": 0,
            "consecutive_losses": 0,
            "circuit_breaker_state": "CLOSED",
            "circuit_breaker_failures": 0,
            "last_signal_time": "{}",
            "confidence_threshold_override": None,
            "is_primary_instance": True,
            "instance_id": "test",
            "lock_expires_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        db.upsert = AsyncMock(return_value={})

        from lumitrade.state.manager import StateManager
        oanda = AsyncMock()
        oanda.get_open_trades = AsyncMock(return_value=[])
        manager = StateManager(db, oanda)
        await manager.restore()
        await manager.save()

        db.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_cr002_lock_acquired_on_startup(self):
        """CR-002: Lock is acquired during startup sequence."""
        from lumitrade.state.lock import DistributedLock

        db = AsyncMock()
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "instance_id": None,
            "lock_expires_at": None,
        })
        db.update = AsyncMock(return_value={})

        lock = DistributedLock(db)
        acquired = await lock.acquire("cloud-primary")
        assert acquired is True

    @pytest.mark.asyncio
    async def test_cr003_lock_not_acquired_when_held_by_other(self):
        """CR-003: Cannot acquire lock when another instance holds it."""
        from lumitrade.state.lock import DistributedLock

        future = datetime.now(timezone.utc) + timedelta(seconds=120)
        db = AsyncMock()
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "instance_id": "other-instance",
            "lock_expires_at": future.isoformat(),
        })

        lock = DistributedLock(db)
        acquired = await lock.acquire("cloud-primary")
        assert acquired is False

    @pytest.mark.asyncio
    async def test_cr004_expired_lock_can_be_taken_over(self):
        """CR-004: Expired lock allows takeover by new instance."""
        from lumitrade.state.lock import DistributedLock

        past = datetime.now(timezone.utc) - timedelta(seconds=300)
        db = AsyncMock()
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "instance_id": "dead-instance",
            "lock_expires_at": past.isoformat(),
        })
        db.update = AsyncMock(return_value={})

        lock = DistributedLock(db)
        acquired = await lock.acquire("cloud-primary")
        assert acquired is True

    @pytest.mark.asyncio
    async def test_cr005_lock_released_on_shutdown(self):
        """CR-005: Lock is released during graceful shutdown."""
        from lumitrade.state.lock import DistributedLock

        db = AsyncMock()
        db.update = AsyncMock(return_value={})

        lock = DistributedLock(db)
        await lock.release("cloud-primary")

        db.update.assert_called_once()
        call_args = db.update.call_args
        assert call_args[0][2]["is_primary_instance"] is False

    @pytest.mark.asyncio
    async def test_cr006_state_restored_from_db(self):
        """CR-006: State is correctly restored from DB on startup."""
        db = AsyncMock()
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "risk_state": "CAUTIOUS",
            "open_trades": '[{"pair": "EUR_USD"}]',
            "pending_orders": "[]",
            "daily_pnl_usd": "-15.50",
            "weekly_pnl_usd": "-20.00",
            "daily_trade_count": 3,
            "consecutive_losses": 2,
            "circuit_breaker_state": "CLOSED",
            "circuit_breaker_failures": 0,
            "last_signal_time": '{"EUR_USD": "2026-03-22T10:00:00Z"}',
            "confidence_threshold_override": None,
            "is_primary_instance": True,
            "instance_id": "test",
            "lock_expires_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

        oanda = AsyncMock()
        oanda.get_open_trades = AsyncMock(return_value=[])

        from lumitrade.state.manager import StateManager
        manager = StateManager(db, oanda)
        await manager.restore()

        state = await manager.get()
        assert state.risk_state.value == "CAUTIOUS"

    @pytest.mark.asyncio
    async def test_cr007_missing_db_state_creates_defaults(self):
        """CR-007: If DB has no state row, system starts with safe defaults."""
        db = AsyncMock()
        db.select_one = AsyncMock(return_value=None)
        db.upsert = AsyncMock(return_value={})

        oanda = AsyncMock()
        oanda.get_open_trades = AsyncMock(return_value=[])

        from lumitrade.state.manager import StateManager
        manager = StateManager(db, oanda)
        await manager.restore()

        state = await manager.get()
        assert state.risk_state.value == "NORMAL"

    @pytest.mark.asyncio
    async def test_cr008_lock_holder_can_reacquire_own_lock(self):
        """CR-008: Instance that already holds lock can re-acquire it."""
        from lumitrade.state.lock import DistributedLock

        future = datetime.now(timezone.utc) + timedelta(seconds=60)
        db = AsyncMock()
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "instance_id": "cloud-primary",
            "lock_expires_at": future.isoformat(),
        })
        db.update = AsyncMock(return_value={})

        lock = DistributedLock(db)
        acquired = await lock.acquire("cloud-primary")
        assert acquired is True

    @pytest.mark.asyncio
    async def test_cr009_state_not_lost_on_db_write_failure(self):
        """CR-009: If DB write fails during save, in-memory state preserved."""
        db = AsyncMock()
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "risk_state": "NORMAL",
            "open_trades": "[]",
            "pending_orders": "[]",
            "daily_pnl_usd": "0",
            "weekly_pnl_usd": "0",
            "daily_trade_count": 0,
            "consecutive_losses": 0,
            "circuit_breaker_state": "CLOSED",
            "circuit_breaker_failures": 0,
            "last_signal_time": "{}",
            "confidence_threshold_override": None,
            "is_primary_instance": True,
            "instance_id": "test",
            "lock_expires_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        db.upsert = AsyncMock(side_effect=Exception("DB write failed"))

        oanda = AsyncMock()
        oanda.get_open_trades = AsyncMock(return_value=[])

        from lumitrade.state.manager import StateManager
        manager = StateManager(db, oanda)
        await manager.restore()

        # Save should fail but not crash
        try:
            await manager.save()
        except Exception:
            pass

        # In-memory state should still be accessible
        state = await manager.get()
        assert state is not None

    @pytest.mark.asyncio
    async def test_cr010_lock_acquire_fails_gracefully_on_no_state(self):
        """CR-010: Lock acquire returns False if no system_state row."""
        from lumitrade.state.lock import DistributedLock

        db = AsyncMock()
        db.select_one = AsyncMock(return_value=None)

        lock = DistributedLock(db)
        acquired = await lock.acquire("cloud-primary")
        assert acquired is False
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/chaos/test_crash_recovery.py -v`
Expected: 10 tests PASS (some may need minor adjustments based on actual StateManager implementation)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/chaos/test_crash_recovery.py
git commit -m "test: add chaos tests for crash recovery (CR-001 to CR-010)"
```

---

### Task 4: Chaos Tests — Failover (test_failover.py)

**Files:**
- Create: `backend/tests/chaos/test_failover.py`
- Reference: `backend/lumitrade/state/lock.py`

Tests the distributed lock failover mechanism — primary dies, standby takes over.

- [ ] **Step 1: Write FO-001 through FO-006 failover tests**

```python
"""
Chaos tests for distributed lock failover.
Verifies standby instance takes over when primary fails.
File: tests/chaos/test_failover.py
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock
from lumitrade.state.lock import DistributedLock, LOCK_TTL_SECONDS


@pytest.fixture
def db():
    return AsyncMock()


class TestFailover:
    """FO-001 to FO-006: Primary/standby failover scenarios."""

    @pytest.mark.asyncio
    async def test_fo001_standby_waits_while_primary_healthy(self, db):
        """FO-001: Standby does not acquire lock while primary is active."""
        future = datetime.now(timezone.utc) + timedelta(seconds=60)
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "instance_id": "cloud-primary",
            "lock_expires_at": future.isoformat(),
        })

        lock = DistributedLock(db)
        acquired = await lock.acquire("local-backup")
        assert acquired is False

    @pytest.mark.asyncio
    async def test_fo002_standby_takes_over_expired_lock(self, db):
        """FO-002: Standby acquires lock when primary's lock expires."""
        past = datetime.now(timezone.utc) - timedelta(seconds=LOCK_TTL_SECONDS + 60)
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "instance_id": "cloud-primary",
            "lock_expires_at": past.isoformat(),
        })
        db.update = AsyncMock(return_value={})

        lock = DistributedLock(db)
        acquired = await lock.acquire("local-backup")
        assert acquired is True

    @pytest.mark.asyncio
    async def test_fo003_primary_reclaims_after_recovery(self, db):
        """FO-003: Primary can reclaim lock when standby releases."""
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "instance_id": None,
            "lock_expires_at": None,
        })
        db.update = AsyncMock(return_value={})

        lock = DistributedLock(db)
        acquired = await lock.acquire("cloud-primary")
        assert acquired is True

    @pytest.mark.asyncio
    async def test_fo004_lock_release_clears_instance_id(self, db):
        """FO-004: Releasing lock clears instance_id and sets primary=False."""
        db.update = AsyncMock(return_value={})

        lock = DistributedLock(db)
        await lock.release("local-backup")

        call_data = db.update.call_args[0][2]
        assert call_data["is_primary_instance"] is False
        assert call_data["instance_id"] is None

    @pytest.mark.asyncio
    async def test_fo005_no_state_row_returns_false(self, db):
        """FO-005: If system_state table is empty, lock acquire fails safely."""
        db.select_one = AsyncMock(return_value=None)

        lock = DistributedLock(db)
        acquired = await lock.acquire("cloud-primary")
        assert acquired is False

    @pytest.mark.asyncio
    async def test_fo006_same_instance_can_renew(self, db):
        """FO-006: Instance holding the lock can re-acquire (renew) it."""
        future = datetime.now(timezone.utc) + timedelta(seconds=30)
        db.select_one = AsyncMock(return_value={
            "id": "singleton",
            "instance_id": "cloud-primary",
            "lock_expires_at": future.isoformat(),
        })
        db.update = AsyncMock(return_value={})

        lock = DistributedLock(db)
        acquired = await lock.acquire("cloud-primary")
        assert acquired is True
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/chaos/test_failover.py -v`
Expected: 6 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/chaos/test_failover.py
git commit -m "test: add chaos tests for failover (FO-001 to FO-006)"
```

---

### Task 5: Integration Tests — Signal Pipeline (test_signal_pipeline.py)

**Files:**
- Create: `backend/tests/integration/test_signal_pipeline.py`
- Reference: `backend/lumitrade/data_engine/engine.py`
- Reference: `backend/lumitrade/ai_brain/scanner.py`
- Reference: `backend/lumitrade/risk_engine/engine.py`
- Reference: `backend/lumitrade/execution_engine/engine.py`

Tests the full chain: DataEngine -> SignalScanner -> RiskEngine -> ExecutionEngine (paper mode). All external APIs mocked with respx/AsyncMock.

- [ ] **Step 1: Write SP-001 through SP-010 signal pipeline integration tests**

These tests mock all external calls (OANDA, Anthropic, Supabase) and verify the full signal flow from data fetch through execution decision. Each test targets a specific pipeline behavior.

Key test cases:
- SP-001: Full pipeline produces a paper trade from valid signal
- SP-002: HOLD signal stops pipeline at AI stage
- SP-003: Low confidence signal rejected by risk engine
- SP-004: News blackout blocks execution
- SP-005: Max positions reached blocks new trade
- SP-006: Invalid AI output caught by validator
- SP-007: Circuit breaker OPEN blocks execution
- SP-008: Daily loss limit halts trading
- SP-009: Spread too wide rejects signal
- SP-010: Cooldown period blocks repeat signal on same pair

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/integration/test_signal_pipeline.py -v`
Expected: 10 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_signal_pipeline.py
git commit -m "test: add integration tests for signal pipeline (SP-001 to SP-010)"
```

---

### Task 6: Security Tests (test_security.py + test_prompt_injection.py)

**Files:**
- Create: `backend/tests/security/test_security.py`
- Create: `backend/tests/security/test_prompt_injection.py`
- Reference: `backend/lumitrade/infrastructure/secure_logger.py`
- Reference: `backend/lumitrade/ai_brain/prompt_builder.py`
- Reference: `backend/lumitrade/infrastructure/db.py`

Tests security controls: log scrubbing, prompt injection prevention, no secrets in code.

- [ ] **Step 1: Write security tests**

`test_security.py` covers:
- SEC-001: Bearer tokens scrubbed from logs
- SEC-002: Anthropic keys scrubbed from logs
- SEC-003: Email addresses scrubbed from logs
- SEC-004: Phone numbers scrubbed from logs
- SEC-005: Normal trading text preserved (no false positives)
- SEC-006: Nested dict values scrubbed recursively
- SEC-007: No verify=False anywhere in codebase (grep test)
- SEC-008: No hardcoded API keys in source (grep test)

`test_prompt_injection.py` covers:
- INJ-001: Special characters stripped from news titles
- INJ-002: News title truncated to max length
- INJ-003: SQL-like injection in news title neutralized
- INJ-004: Prompt override attempt in news title neutralized
- INJ-005: Normal news title preserved correctly

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/security/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/security/test_security.py backend/tests/security/test_prompt_injection.py
git commit -m "test: add security tests and prompt injection prevention tests"
```

---

### Task 7: Unit Tests — Position Sizer (test_position_sizer.py)

**Files:**
- Create: `backend/tests/unit/test_position_sizer.py`
- Reference: `backend/lumitrade/risk_engine/position_sizer.py`
- Reference: `backend/lumitrade/utils/pip_math.py`

Tests position sizing calculations with Decimal precision.

- [ ] **Step 1: Write position sizer tests**

Key test cases:
- PS-001: Standard EUR/USD position size calculation
- PS-002: USD/JPY position size (different pip size)
- PS-003: Rounds down to micro lot (1000 units)
- PS-004: Zero SL pips returns 0 units
- PS-005: Minimum account balance produces valid size
- PS-006: Risk amount matches position * pip_value * SL_pips
- PS-007: High confidence (2%) produces larger position
- PS-008: Low confidence (0.5%) produces smaller position

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_position_sizer.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_position_sizer.py
git commit -m "test: add position sizer unit tests"
```

---

## Wave 2: Sentry Integration + Critical Test Runner

### Task 8: Integrate Sentry Error Tracking

**Files:**
- Modify: `backend/lumitrade/main.py`
- Modify: `backend/lumitrade/config.py` (verify sentry_dsn field exists)
- Reference: `docs/specs/Lumitrade_DOS_v2.0.md` Section 6.2

Per DOS Section 6.2, add Sentry initialization with AsyncioIntegration, event scrubbing, and environment tagging.

- [ ] **Step 1: Read current main.py and config.py**
- [ ] **Step 2: Add Sentry initialization to main.py startup**

Add `configure_sentry()` function per DOS 6.2 spec:
- `sentry_sdk.init()` with AsyncioIntegration
- `traces_sample_rate=0.1`
- `before_send=scrub_sentry_event` to strip API keys
- Environment tag from `config.oanda_environment`
- Only init if `config.sentry_dsn` is set

- [ ] **Step 3: Verify no secrets leak through Sentry**

Add test in `tests/security/test_security.py`:
```python
def test_sentry_scrubber_strips_vars():
    """Sentry before_send removes stack frame vars."""
    # Test the scrub_sentry_event function
```

- [ ] **Step 4: Commit**

```bash
git add backend/lumitrade/main.py
git commit -m "feat: integrate Sentry error tracking with event scrubbing"
```

---

### Task 9: Create Critical Test Runner Script

**Files:**
- Create: `backend/scripts/run_critical_tests.sh`

Per QTS Section 9.2, create a script that runs all deployment-blocking tests.

- [ ] **Step 1: Write the script**

```bash
#!/bin/bash
set -e
echo "=== Running CRITICAL test suite ==="
echo "--- AI Validator (100% required) ---"
pytest tests/unit/test_ai_validator.py -v --tb=short
echo "--- Risk Engine (100% required) ---"
pytest tests/unit/test_risk_engine.py -v --tb=short
echo "--- Pip Math / Position Sizer (100% required) ---"
pytest tests/unit/test_pip_math.py -v --tb=short
echo "--- Data Failure Chaos Tests ---"
pytest tests/chaos/test_data_failures.py -v --tb=short
echo "--- Broker Failure Chaos Tests ---"
pytest tests/chaos/test_broker_failures.py -v --tb=short
echo "--- Crash Recovery Chaos Tests ---"
pytest tests/chaos/test_crash_recovery.py -v --tb=short
echo "--- Security Tests ---"
pytest tests/security/ -v --tb=short
echo "--- Signal Pipeline Integration ---"
pytest tests/integration/test_signal_pipeline.py -v --tb=short
echo "=== ALL CRITICAL TESTS PASSED ==="
echo "Safe to deploy."
```

- [ ] **Step 2: Run the full critical test suite**

Run: `cd backend && bash scripts/run_critical_tests.sh`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/run_critical_tests.sh
git commit -m "feat: add critical test runner script for pre-deployment"
```

---

## Wave 3: Deployment + Monitoring

### Task 10: Deploy Backend to Railway

**Prerequisite:** All critical tests pass. Railway account set up. Environment variables configured in Railway dashboard.

- [ ] **Step 1: Verify CI passes on push**

Push to main. Confirm GitHub Actions `test.yml` workflow passes.

- [ ] **Step 2: Verify Railway deploys**

Confirm Railway auto-deploys from main. Check Railway logs for successful startup.

- [ ] **Step 3: Verify health endpoint**

```bash
curl -s https://lumitrade-engine.railway.app/health | python -m json.tool
```
Expected: `{"status": "healthy", ...}` with HTTP 200

- [ ] **Step 4: Verify dashboard deploys**

Check frontend deployment on Railway. Confirm landing page loads.

---

### Task 11: Configure UptimeRobot Monitoring

**Reference:** DOS Section 6.1

- [ ] **Step 1: Create UptimeRobot monitor for engine health**

Configure at uptimerobot.com:
- URL: `https://lumitrade-engine.railway.app/health`
- Check interval: 5 minutes
- Alert contacts: SMS + email
- Keyword check: response contains `"status":"healthy"`

- [ ] **Step 2: Create UptimeRobot monitor for dashboard**

Configure:
- URL: `https://lumitrade-dashboard.railway.app`
- Check interval: 5 minutes
- Alert contacts: SMS + email

- [ ] **Step 3: Test alert delivery**

Temporarily take service down (Railway pause) and verify SMS alert fires within 5 minutes. Resume service and verify recovery alert.

---

### Task 12: Verify Sentry Receives Events

- [ ] **Step 1: Set SENTRY_DSN in Railway env vars**
- [ ] **Step 2: Trigger a test error** (check Railway logs for Sentry confirmation)
- [ ] **Step 3: Verify event appears in Sentry dashboard**

---

## Wave 4: Go/No-Go Gates + Live Readiness

### Task 13: Define and Document 13 Go/No-Go Gates

**Files:**
- Create: `docs/go-no-go-gates.md`

Per QTS Section 8.2 and PRD Section 18.2, formally document all 13 gates with verification method and status.

- [ ] **Step 1: Write the Go/No-Go gates document**

The 13 gates (from QTS 8.2 + PRD 18.1):

1. **50+ paper trades logged** — Query trades table: `SELECT count(*) FROM trades WHERE mode='PAPER' AND status='CLOSED'`
2. **Win rate >= 40%** — Query: wins/total >= 0.40
3. **7 consecutive days without crash** — Check Railway uptime logs
4. **No single trade loss > 2% of account** — Query max loss trade
5. **Daily loss limit never breached** — Check risk_events for DAILY_LIMIT
6. **All critical tests pass** — Run `scripts/run_critical_tests.sh`
7. **Zero API keys in source code** — Run `gitleaks detect --source .`
8. **Kill switch tested** — Manual test: activate and verify halt
9. **Crash recovery tested** — Kill process, verify auto-restart < 60s
10. **Data validation active** — Verify stale data detected in logs
11. **AI validation 100%** — Zero trades from failed validation (query DB)
12. **Position reconciliation working** — Compare DB vs OANDA positions
13. **SMS alerts delivering** — Verify Telnyx alerts received

- [ ] **Step 2: Commit**

```bash
git add docs/go-no-go-gates.md
git commit -m "docs: define 13 Go/No-Go gates for live trading authorization"
```

---

### Task 14: Security Audit Checklist

**Files:**
- Create: `docs/security-audit.md`

Per SS Section 9.1, create a checkable 27-item security audit.

- [ ] **Step 1: Write security audit document with all 27 items**
- [ ] **Step 2: Run gitleaks full history scan**

```bash
gitleaks detect --source . --log-opts="--all"
```
Expected: Zero findings

- [ ] **Step 3: Run npm audit on frontend**

```bash
cd frontend && npm audit
```
Expected: Zero high/critical vulnerabilities

- [ ] **Step 4: Verify no verify=False in codebase**

```bash
grep -r "verify=False" backend/lumitrade/
```
Expected: Zero matches

- [ ] **Step 5: Commit**

```bash
git add docs/security-audit.md
git commit -m "docs: add 27-item security audit checklist"
```

---

### Task 15: DevOps Pre-Go-Live Checklist

**Files:**
- Create: `docs/devops-checklist.md`

Per DOS Section 9.1, create the 25-item infrastructure readiness checklist.

- [ ] **Step 1: Write DevOps checklist**

Covers: Railway config verified, health check active, supervisord running, Sentry receiving events, UptimeRobot monitoring, GitHub Actions passing, Docker build clean, env vars all set, local backup configured, rotation calendar set.

- [ ] **Step 2: Commit**

```bash
git add docs/devops-checklist.md
git commit -m "docs: add DevOps pre-go-live infrastructure checklist"
```

---

## Execution Order Summary

| Wave | Tasks | Description | Parallel? |
|------|-------|-------------|-----------|
| 1 | 1-7 | Test backfill: chaos, integration, security, unit | Tasks 1-4 parallel, then 5-7 parallel |
| 2 | 8-9 | Sentry integration + critical test runner | Sequential |
| 3 | 10-12 | Railway deploy + UptimeRobot + Sentry verify | Sequential |
| 4 | 13-15 | Go/No-Go gates + security audit + DevOps checklist | Tasks 13-15 parallel |

**After Wave 4:** System runs in PAPER mode for 2+ weeks, accumulating 50+ trades. Then verify all 13 Go/No-Go gates before switching to LIVE.
