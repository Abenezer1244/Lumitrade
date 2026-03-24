"""
Execution Engine Tests — EX-001 to EX-040
=============================================
100% coverage required on execution_engine/*.py.
This module places real orders — every untested path is a potential financial loss.
Per QTS v2.0 and BDS Section 7.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from lumitrade.core.enums import (
    CircuitBreakerState,
    Direction,
    OrderStatus,
    TradingMode,
)
from lumitrade.core.exceptions import ExecutionError, OrderExpiredError
from lumitrade.core.models import ApprovedOrder, OrderResult
from lumitrade.execution_engine.circuit_breaker import (
    CircuitBreaker,
    FAILURE_THRESHOLD,
    FAILURE_WINDOW_SEC,
    RESET_TIMEOUT_SEC,
)
from lumitrade.execution_engine.fill_verifier import (
    FillVerifier,
    HIGH_SLIPPAGE_THRESHOLD_PIPS,
)
from lumitrade.execution_engine.order_machine import OrderStateMachine, VALID_TRANSITIONS
from lumitrade.execution_engine.paper_executor import PaperExecutor


# ── Shared Helpers ────────────────────────────────────────────────


def _make_config(trading_mode="PAPER"):
    config = MagicMock()
    config.trading_mode = trading_mode
    config.account_uuid = "test-account-uuid"
    return config


def _make_order(
    pair="EUR_USD",
    direction=Direction.BUY,
    units=1000,
    entry=Decimal("1.08430"),
    sl=Decimal("1.08230"),
    tp=Decimal("1.08730"),
    expired=False,
    mode=TradingMode.PAPER,
) -> ApprovedOrder:
    now = datetime.now(timezone.utc)
    expiry = now - timedelta(seconds=10) if expired else now + timedelta(seconds=30)
    return ApprovedOrder(
        order_ref=uuid4(),
        signal_id=uuid4(),
        pair=pair,
        direction=direction,
        units=units,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        risk_amount_usd=Decimal("3.00"),
        risk_pct=Decimal("0.01"),
        confidence=Decimal("0.80"),
        account_balance_at_approval=Decimal("300.00"),
        approved_at=now,
        expiry=expiry,
        mode=mode,
    )


def _make_order_result(order: ApprovedOrder, fill_price=None, fill_units=None):
    return OrderResult(
        order_ref=order.order_ref,
        broker_order_id="PAPER-abc123",
        broker_trade_id="PAPER-def456",
        status=OrderStatus.FILLED,
        fill_price=fill_price or order.entry_price,
        fill_units=fill_units or abs(order.units),
        fill_timestamp=datetime.now(timezone.utc),
        stop_loss_confirmed=order.stop_loss,
        take_profit_confirmed=order.take_profit,
        slippage_pips=Decimal("0.0"),
        raw_response={"mode": "PAPER"},
    )


# ══════════════════════════════════════════════════════════════════
# 1. OrderStateMachine Tests — EX-001 to EX-010
# ══════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestOrderStateMachine:
    """Tests for order lifecycle state transitions."""

    def test_ex_001_initial_state_is_pending(self):
        """EX-001: State machine starts in PENDING."""
        machine = OrderStateMachine()
        assert machine.status == OrderStatus.PENDING

    def test_ex_002_pending_to_submitted(self):
        """EX-002: PENDING -> SUBMITTED is valid."""
        machine = OrderStateMachine()
        machine.transition(OrderStatus.SUBMITTED)
        assert machine.status == OrderStatus.SUBMITTED

    def test_ex_003_full_happy_path(self):
        """EX-003: PENDING -> SUBMITTED -> ACKNOWLEDGED -> FILLED."""
        machine = OrderStateMachine()
        machine.transition(OrderStatus.SUBMITTED)
        machine.transition(OrderStatus.ACKNOWLEDGED)
        machine.transition(OrderStatus.FILLED)
        assert machine.status == OrderStatus.FILLED
        assert len(machine.history) == 4  # PENDING + 3 transitions

    def test_ex_004_pending_to_rejected(self):
        """EX-004: PENDING -> REJECTED is valid."""
        machine = OrderStateMachine()
        machine.transition(OrderStatus.REJECTED)
        assert machine.status == OrderStatus.REJECTED

    def test_ex_005_pending_to_timeout(self):
        """EX-005: PENDING -> TIMEOUT is valid."""
        machine = OrderStateMachine()
        machine.transition(OrderStatus.TIMEOUT)
        assert machine.status == OrderStatus.TIMEOUT

    def test_ex_006_invalid_transition_stays_in_current_state(self):
        """EX-006: Invalid transition (PENDING -> FILLED) is silently ignored."""
        machine = OrderStateMachine()
        machine.transition(OrderStatus.FILLED)
        assert machine.status == OrderStatus.PENDING  # unchanged

    def test_ex_007_expired_order_raises(self):
        """EX-007: Expired order raises OrderExpiredError and sets TIMEOUT."""
        machine = OrderStateMachine()
        order = _make_order(expired=True)
        with pytest.raises(OrderExpiredError):
            machine.check_expiry(order)
        assert machine.status == OrderStatus.TIMEOUT

    def test_ex_008_non_expired_order_passes(self):
        """EX-008: Non-expired order passes check_expiry without error."""
        machine = OrderStateMachine()
        order = _make_order(expired=False)
        machine.check_expiry(order)  # should not raise
        assert machine.status == OrderStatus.PENDING

    def test_ex_009_history_records_timestamps(self):
        """EX-009: History records each transition with a timestamp."""
        machine = OrderStateMachine()
        machine.transition(OrderStatus.SUBMITTED)
        machine.transition(OrderStatus.ACKNOWLEDGED)
        statuses = [s for s, _ in machine.history]
        assert statuses == [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
        ]
        for _, ts in machine.history:
            assert isinstance(ts, datetime)

    def test_ex_010_partial_fill_to_filled(self):
        """EX-010: ACKNOWLEDGED -> PARTIAL -> FILLED is valid."""
        machine = OrderStateMachine()
        machine.transition(OrderStatus.SUBMITTED)
        machine.transition(OrderStatus.ACKNOWLEDGED)
        machine.transition(OrderStatus.PARTIAL)
        assert machine.status == OrderStatus.PARTIAL
        machine.transition(OrderStatus.FILLED)
        assert machine.status == OrderStatus.FILLED


# ══════════════════════════════════════════════════════════════════
# 2. PaperExecutor Tests — EX-011 to EX-018
# ══════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestPaperExecutor:
    """Tests for the paper (simulated) executor."""

    @pytest.fixture
    def executor(self):
        return PaperExecutor()

    async def test_ex_011_fills_at_current_price(self, executor):
        """EX-011: Paper executor fills at the provided current price."""
        order = _make_order(entry=Decimal("1.08430"))
        current_price = Decimal("1.08450")
        result = await executor.execute(order, current_price)
        assert result.fill_price == current_price

    async def test_ex_012_returns_filled_status(self, executor):
        """EX-012: Paper executor always returns FILLED status."""
        order = _make_order()
        result = await executor.execute(order, Decimal("1.08430"))
        assert result.status == OrderStatus.FILLED

    async def test_ex_013_correct_fill_units(self, executor):
        """EX-013: fill_units equals abs(order.units)."""
        order = _make_order(units=-5000)
        result = await executor.execute(order, Decimal("1.08430"))
        assert result.fill_units == 5000

    async def test_ex_014_slippage_calculated_in_pips(self, executor):
        """EX-014: Slippage is correctly computed as pip difference."""
        order = _make_order(entry=Decimal("1.08430"), pair="EUR_USD")
        current_price = Decimal("1.08450")  # 2 pips away
        result = await executor.execute(order, current_price)
        assert result.slippage_pips == Decimal("2.0")

    async def test_ex_015_zero_slippage_at_entry(self, executor):
        """EX-015: Slippage is 0 when fill price equals entry price."""
        order = _make_order(entry=Decimal("1.08430"))
        result = await executor.execute(order, Decimal("1.08430"))
        assert result.slippage_pips == Decimal("0.0")

    async def test_ex_016_broker_ids_start_with_paper(self, executor):
        """EX-016: Paper fills have broker IDs prefixed with PAPER-."""
        order = _make_order()
        result = await executor.execute(order, Decimal("1.08430"))
        assert result.broker_order_id.startswith("PAPER-")
        assert result.broker_trade_id.startswith("PAPER-")

    async def test_ex_017_sl_tp_confirmed_from_order(self, executor):
        """EX-017: SL and TP confirmed values match the order."""
        order = _make_order(sl=Decimal("1.08200"), tp=Decimal("1.08800"))
        result = await executor.execute(order, Decimal("1.08430"))
        assert result.stop_loss_confirmed == Decimal("1.08200")
        assert result.take_profit_confirmed == Decimal("1.08800")

    async def test_ex_018_jpy_pair_slippage(self, executor):
        """EX-018: JPY pair slippage uses 0.01 pip size."""
        order = _make_order(
            pair="USD_JPY", entry=Decimal("149.500"), sl=Decimal("149.300"),
            tp=Decimal("149.800"),
        )
        current_price = Decimal("149.530")  # 3 pips away for JPY
        result = await executor.execute(order, current_price)
        assert result.slippage_pips == Decimal("3.0")


# ══════════════════════════════════════════════════════════════════
# 3. FillVerifier Tests — EX-019 to EX-027
# ══════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestFillVerifier:
    """Tests for post-fill verification and anomaly detection."""

    @pytest.fixture
    def alert_service(self):
        mock = AsyncMock()
        mock.send_warning = AsyncMock()
        mock.send_critical = AsyncMock()
        mock.send_info = AsyncMock()
        return mock

    @pytest.fixture
    def verifier(self, alert_service):
        return FillVerifier(alert_service)

    async def test_ex_019_exact_fill_passes(self, verifier, alert_service):
        """EX-019: Fill at entry price passes with no alerts."""
        order = _make_order(entry=Decimal("1.08430"))
        result = _make_order_result(order, fill_price=Decimal("1.08430"))
        verified = await verifier.verify(order, result)
        assert verified.slippage_pips == Decimal("0.0")
        alert_service.send_warning.assert_not_called()
        alert_service.send_critical.assert_not_called()

    async def test_ex_020_low_slippage_no_alert(self, verifier, alert_service):
        """EX-020: Slippage below threshold (2 pips) does not trigger alert."""
        order = _make_order(entry=Decimal("1.08430"))
        result = _make_order_result(order, fill_price=Decimal("1.08450"))
        verified = await verifier.verify(order, result)
        assert verified.slippage_pips == Decimal("2.0")
        alert_service.send_warning.assert_not_called()

    async def test_ex_021_high_slippage_triggers_warning(self, verifier, alert_service):
        """EX-021: Slippage above 3.0 pips triggers a warning alert."""
        order = _make_order(entry=Decimal("1.08430"))
        # 4 pips of slippage
        result = _make_order_result(order, fill_price=Decimal("1.08470"))
        verified = await verifier.verify(order, result)
        assert verified.slippage_pips == Decimal("4.0")
        alert_service.send_warning.assert_called_once()
        call_msg = alert_service.send_warning.call_args[0][0]
        assert "HIGH SLIPPAGE" in call_msg

    async def test_ex_022_exactly_at_threshold_no_alert(self, verifier, alert_service):
        """EX-022: Slippage exactly at 3.0 pips does NOT trigger alert (boundary)."""
        order = _make_order(entry=Decimal("1.08430"))
        result = _make_order_result(order, fill_price=Decimal("1.08460"))
        verified = await verifier.verify(order, result)
        assert verified.slippage_pips == Decimal("3.0")
        alert_service.send_warning.assert_not_called()

    async def test_ex_023_partial_fill_detected(self, verifier, alert_service):
        """EX-023: Partial fill (units mismatch) is logged but not rejected."""
        order = _make_order(units=1000)
        result = _make_order_result(order, fill_units=800)
        verified = await verifier.verify(order, result)
        # Should still return — partial fills are logged, not rejected
        assert verified is not None

    async def test_ex_024_missing_sl_triggers_critical(self, verifier, alert_service):
        """EX-024: Missing SL confirmation triggers CRITICAL alert."""
        order = _make_order()
        result = _make_order_result(order)
        # Simulate missing SL
        result = replace(result, stop_loss_confirmed=Decimal("0"))
        verified = await verifier.verify(order, result)
        alert_service.send_critical.assert_called_once()
        call_msg = alert_service.send_critical.call_args[0][0]
        assert "SL/TP NOT CONFIRMED" in call_msg

    async def test_ex_025_missing_tp_triggers_critical(self, verifier, alert_service):
        """EX-025: Missing TP confirmation triggers CRITICAL alert."""
        order = _make_order()
        result = _make_order_result(order)
        result = replace(result, take_profit_confirmed=Decimal("0"))
        verified = await verifier.verify(order, result)
        alert_service.send_critical.assert_called_once()

    async def test_ex_026_non_filled_status_returned_as_is(self, verifier):
        """EX-026: Non-FILLED result is returned without verification."""
        order = _make_order()
        result = _make_order_result(order)
        result = replace(result, status=OrderStatus.PARTIAL)
        returned = await verifier.verify(order, result)
        assert returned.status == OrderStatus.PARTIAL

    async def test_ex_027_slippage_recalculated_on_verified(self, verifier):
        """EX-027: Verified result has slippage recalculated from entry vs fill."""
        order = _make_order(entry=Decimal("1.08430"))
        result = _make_order_result(order, fill_price=Decimal("1.08450"))
        # The original result might have 0 slippage, but verifier recalculates
        verified = await verifier.verify(order, result)
        assert verified.slippage_pips == Decimal("2.0")


# ══════════════════════════════════════════════════════════════════
# 4. CircuitBreaker Tests — EX-028 to EX-034
# ══════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestCircuitBreaker:
    """Tests for the circuit breaker protecting OANDA API calls."""

    @pytest.fixture
    def breaker(self):
        return CircuitBreaker()

    async def test_ex_028_initial_state_closed(self, breaker):
        """EX-028: Circuit breaker starts CLOSED."""
        assert breaker.state == CircuitBreakerState.CLOSED
        assert not breaker.is_open

    async def test_ex_029_trips_after_threshold_failures(self, breaker):
        """EX-029: 3 failures within 60s trips the breaker to OPEN."""
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.is_open

    async def test_ex_030_failures_below_threshold_stay_closed(self, breaker):
        """EX-030: Fewer than 3 failures keeps breaker CLOSED."""
        for _ in range(FAILURE_THRESHOLD - 1):
            await breaker.record_failure()
        assert breaker.state == CircuitBreakerState.CLOSED

    async def test_ex_031_half_open_after_timeout(self, breaker):
        """EX-031: After RESET_TIMEOUT_SEC, OPEN transitions to HALF_OPEN."""
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN
        # Manually backdate the opened_at to simulate timeout elapsed
        breaker._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )
        state = await breaker.check_and_transition()
        assert state == CircuitBreakerState.HALF_OPEN

    async def test_ex_032_success_in_half_open_closes(self, breaker):
        """EX-032: A success in HALF_OPEN transitions back to CLOSED."""
        for _ in range(FAILURE_THRESHOLD):
            await breaker.record_failure()
        breaker._opened_at = datetime.now(timezone.utc) - timedelta(
            seconds=RESET_TIMEOUT_SEC + 1
        )
        await breaker.check_and_transition()
        assert breaker.state == CircuitBreakerState.HALF_OPEN
        await breaker.record_success()
        assert breaker.state == CircuitBreakerState.CLOSED
        assert not breaker.is_open

    async def test_ex_033_success_in_closed_is_noop(self, breaker):
        """EX-033: record_success when CLOSED does nothing."""
        await breaker.record_success()
        assert breaker.state == CircuitBreakerState.CLOSED

    async def test_ex_034_old_failures_expire(self, breaker):
        """EX-034: Failures older than FAILURE_WINDOW_SEC are pruned."""
        # Add 2 failures that are "old"
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=FAILURE_WINDOW_SEC + 10
        )
        breaker._failures = [old_time, old_time]
        # Add 1 new failure — total recent = 1, should not trip
        await breaker.record_failure()
        assert breaker.state == CircuitBreakerState.CLOSED


# ══════════════════════════════════════════════════════════════════
# 5. ExecutionEngine Integration Tests — EX-035 to EX-040
# ══════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestExecutionEngine:
    """Tests for the main ExecutionEngine orchestrator."""

    @pytest.fixture
    def mock_deps(self):
        """Create all mocked dependencies for ExecutionEngine."""
        config = _make_config(trading_mode="PAPER")
        trading_client = AsyncMock()
        state_manager = MagicMock()
        db = AsyncMock()
        db.insert = AsyncMock()
        alert_service = AsyncMock()
        alert_service.send_info = AsyncMock()
        alert_service.send_warning = AsyncMock()
        alert_service.send_critical = AsyncMock()
        return {
            "config": config,
            "trading_client": trading_client,
            "state_manager": state_manager,
            "db": db,
            "alert_service": alert_service,
        }

    @pytest.fixture
    def engine(self, mock_deps):
        from lumitrade.execution_engine.engine import ExecutionEngine

        eng = ExecutionEngine(
            config=mock_deps["config"],
            trading_client=mock_deps["trading_client"],
            state_manager=mock_deps["state_manager"],
            db=mock_deps["db"],
            alert_service=mock_deps["alert_service"],
        )
        return eng

    async def test_ex_035_paper_mode_routes_to_paper_executor(
        self, engine, mock_deps
    ):
        """EX-035: PAPER mode uses PaperExecutor, never calls OANDA."""
        order = _make_order()
        current_price = Decimal("1.08430")
        result = await engine.execute_order(order, current_price)
        assert result is not None
        assert result.status == OrderStatus.FILLED
        assert result.broker_order_id.startswith("PAPER-")
        # OANDA client should never be called
        mock_deps["trading_client"].place_market_order.assert_not_called()

    async def test_ex_036_expired_order_returns_none(self, engine):
        """EX-036: Expired order returns None immediately."""
        order = _make_order(expired=True)
        result = await engine.execute_order(order, Decimal("1.08430"))
        assert result is None

    async def test_ex_037_trade_saved_to_db(self, engine, mock_deps):
        """EX-037: Successful execution saves trade to DB."""
        order = _make_order()
        await engine.execute_order(order, Decimal("1.08430"))
        mock_deps["db"].insert.assert_called_once()
        call_args = mock_deps["db"].insert.call_args
        assert call_args[0][0] == "trades"
        trade_data = call_args[0][1]
        assert trade_data["pair"] == "EUR_USD"
        assert trade_data["direction"] == "BUY"
        assert trade_data["status"] == "OPEN"

    async def test_ex_038_info_alert_sent_on_success(self, engine, mock_deps):
        """EX-038: Successful execution sends an info alert."""
        order = _make_order()
        await engine.execute_order(order, Decimal("1.08430"))
        mock_deps["alert_service"].send_info.assert_called_once()
        msg = mock_deps["alert_service"].send_info.call_args[0][0]
        assert "Trade opened" in msg
        assert "EUR_USD" in msg

    async def test_ex_039_live_mode_circuit_breaker_open_blocks(self, mock_deps):
        """EX-039: LIVE mode with OPEN circuit breaker returns None."""
        from lumitrade.execution_engine.engine import ExecutionEngine

        mock_deps["config"].trading_mode = "LIVE"
        eng = ExecutionEngine(
            config=mock_deps["config"],
            trading_client=mock_deps["trading_client"],
            state_manager=mock_deps["state_manager"],
            db=mock_deps["db"],
            alert_service=mock_deps["alert_service"],
        )
        # Trip the circuit breaker
        for _ in range(FAILURE_THRESHOLD):
            await eng._circuit_breaker.record_failure()
        assert eng._circuit_breaker.is_open

        order = _make_order(mode=TradingMode.LIVE)
        result = await eng.execute_order(order, Decimal("1.08430"))
        assert result is None
        mock_deps["trading_client"].place_market_order.assert_not_called()

    async def test_ex_040_live_mode_oanda_failure_returns_none(self, mock_deps):
        """EX-040: LIVE mode OANDA failure is caught, returns None, records failure."""
        from lumitrade.execution_engine.engine import ExecutionEngine

        mock_deps["config"].trading_mode = "LIVE"
        mock_deps["trading_client"].place_market_order = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        eng = ExecutionEngine(
            config=mock_deps["config"],
            trading_client=mock_deps["trading_client"],
            state_manager=mock_deps["state_manager"],
            db=mock_deps["db"],
            alert_service=mock_deps["alert_service"],
        )
        order = _make_order(mode=TradingMode.LIVE)
        result = await eng.execute_order(order, Decimal("1.08430"))
        assert result is None
        # Circuit breaker should have recorded the failure
        assert len(eng._circuit_breaker._failures) == 1
