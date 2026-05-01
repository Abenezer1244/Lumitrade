"""
Regression tests for Codex 2026-04-25 audit finding [high] #4:
'The emergency kill switch does not implement the PRD contract: current
runtime only skips new scans, state only stores a flag, but live close-out
is required (PRD:579). Failure scenario: operator hits kill during a
disorderly market and existing positions remain live and unmanaged.'

Tests cover ExecutionEngine.close_all_positions() — the close-out
implementation wired to the kill_switch transition in main.py.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from lumitrade.core.enums import TradingMode
from lumitrade.execution_engine.engine import ExecutionEngine


def _build_engine(*, effective_mode: str = TradingMode.LIVE.value, open_trades=None,
                  get_open_trades_raises=None, close_trade_side_effect=None) -> ExecutionEngine:
    """Construct an ExecutionEngine with all dependencies mocked."""
    config = MagicMock()
    config.effective_trading_mode = MagicMock(return_value=effective_mode)
    config.account_uuid = "test-acct-uuid"

    trading_client = MagicMock()
    # Engine calls get_all_open_trades (merges main + spot crypto sub-account).
    if get_open_trades_raises is not None:
        trading_client.get_all_open_trades = AsyncMock(side_effect=get_open_trades_raises)
    else:
        trading_client.get_all_open_trades = AsyncMock(return_value=open_trades or [])
    trading_client.get_open_trades = AsyncMock(return_value=open_trades or [])

    if close_trade_side_effect is not None:
        trading_client.close_trade = AsyncMock(side_effect=close_trade_side_effect)
    else:
        trading_client.close_trade = AsyncMock(return_value={"orderFillTransaction": {"id": "x"}})

    state_manager = MagicMock()
    db = MagicMock()
    alerts = MagicMock()
    alerts.send_critical = AsyncMock()

    engine = ExecutionEngine(
        config=config,
        trading_client=trading_client,
        state_manager=state_manager,
        db=db,
        alert_service=alerts,
    )
    return engine


@pytest.mark.asyncio
async def test_close_all_paper_mode_is_noop():
    """In PAPER mode, close_all_positions must NOT touch the broker."""
    engine = _build_engine(effective_mode=TradingMode.PAPER.value)

    result = await engine.close_all_positions(reason="test")

    assert result == {"attempted": 0, "closed": 0, "failed": []}
    engine._oanda_trade.get_all_open_trades.assert_not_awaited()
    engine._oanda_trade.close_trade.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_all_live_closes_every_open_trade():
    """LIVE mode: every open trade must be closed via close_trade()."""
    open_trades = [
        {"id": "100", "instrument": "USD_CAD", "currentUnits": "1000"},
        {"id": "101", "instrument": "USD_JPY", "currentUnits": "-500"},
        {"id": "102", "instrument": "EUR_USD", "currentUnits": "750"},
    ]
    engine = _build_engine(open_trades=open_trades)

    result = await engine.close_all_positions(reason="kill_switch_test")

    assert result["attempted"] == 3
    assert result["closed"] == 3
    assert result["failed"] == []

    # Each broker_trade_id must have been passed to close_trade
    closed_ids = [c.args[0] for c in engine._oanda_trade.close_trade.call_args_list]
    assert sorted(closed_ids) == ["100", "101", "102"]

    # Critical alert must fire
    engine._alerts.send_critical.assert_awaited_once()
    alert_msg = engine._alerts.send_critical.await_args.args[0]
    assert "KILL SWITCH" in alert_msg
    assert "3/3" in alert_msg


@pytest.mark.asyncio
async def test_close_all_continues_on_partial_failure():
    """If one close fails, the sweep must still attempt the rest."""
    open_trades = [
        {"id": "200", "instrument": "USD_CAD", "currentUnits": "1000"},
        {"id": "201", "instrument": "USD_JPY", "currentUnits": "-500"},
        {"id": "202", "instrument": "EUR_USD", "currentUnits": "750"},
    ]
    # Middle trade fails to close
    side_effect = [
        {"orderFillTransaction": {"id": "ok1"}},
        Exception("OANDA timeout on trade 201"),
        {"orderFillTransaction": {"id": "ok3"}},
    ]
    engine = _build_engine(
        open_trades=open_trades,
        close_trade_side_effect=side_effect,
    )

    result = await engine.close_all_positions(reason="kill_switch_test")

    # All 3 attempted, 2 succeeded, 1 failed — but the sweep didn't bail early.
    # Failed IDs are broker-scoped now (Codex round-2 review of finding #4).
    assert result["attempted"] == 3
    assert result["closed"] == 2
    assert result["failed"] == ["oanda:201"]
    assert engine._oanda_trade.close_trade.await_count == 3


@pytest.mark.asyncio
async def test_close_all_handles_get_open_trades_failure():
    """If we can't fetch open trades, alert and return — do not crash the engine."""
    engine = _build_engine(get_open_trades_raises=RuntimeError("OANDA down"))

    result = await engine.close_all_positions(reason="kill_switch_test")

    assert result["attempted"] == 0
    assert result["closed"] == 0
    assert result["failed"] == ["oanda:fetch_failed"]
    engine._oanda_trade.close_trade.assert_not_awaited()
    # Two alerts: fetch-failure warning + sweep summary
    assert engine._alerts.send_critical.await_count == 2


@pytest.mark.asyncio
async def test_close_all_skips_trades_without_id():
    """A malformed open-trades response with missing IDs must not crash."""
    open_trades = [
        {"instrument": "USD_CAD"},  # no id
        {"id": "300", "instrument": "USD_JPY", "currentUnits": "1000"},
    ]
    engine = _build_engine(open_trades=open_trades)

    result = await engine.close_all_positions(reason="test")

    # Only the well-formed one is attempted
    assert result["attempted"] == 1
    assert result["closed"] == 1
    engine._oanda_trade.close_trade.assert_awaited_once_with("300", pair="USD_JPY")


@pytest.mark.asyncio
async def test_close_all_sweeps_capital_when_present():
    """Per Codex round-2 review of finding #4: Capital.com positions must
    also be closed when a Capital client is wired in."""
    config = MagicMock()
    config.effective_trading_mode = MagicMock(return_value=TradingMode.LIVE.value)
    config.account_uuid = "test-acct"

    oanda_client = MagicMock()
    oanda_client.get_all_open_trades = AsyncMock(
        return_value=[{"id": "O1", "instrument": "USD_CAD"}]
    )
    oanda_client.get_open_trades = AsyncMock(return_value=[])
    oanda_client.close_trade = AsyncMock()

    capital_client = MagicMock()
    # Capital.com only has get_open_trades (no get_all_open_trades); engine falls back via getattr.
    capital_client.get_open_trades = AsyncMock(
        return_value=[{"id": "C1", "epic": "GOLD", "size": "1.0"}]
    )
    capital_client.close_trade = AsyncMock()

    alerts = MagicMock()
    alerts.send_critical = AsyncMock()

    engine = ExecutionEngine(
        config=config,
        trading_client=oanda_client,
        state_manager=MagicMock(),
        db=MagicMock(),
        alert_service=alerts,
        capital_client=capital_client,
    )

    result = await engine.close_all_positions(reason="kill_switch_dual_broker")

    assert result["attempted"] == 2
    assert result["closed"] == 2
    oanda_client.close_trade.assert_awaited_once_with("O1", pair="USD_CAD")
    capital_client.close_trade.assert_awaited_once_with("C1")


@pytest.mark.asyncio
async def test_execute_order_blocked_when_kill_switch_active():
    """Codex round-2 review: an order placed concurrently with kill activation
    must be blocked at the executor level, not just the scan loop."""
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    from lumitrade.core.enums import Direction
    from lumitrade.core.models import ApprovedOrder

    config = MagicMock()
    config.effective_trading_mode = MagicMock(return_value=TradingMode.LIVE.value)
    config.account_uuid = "test"

    state_manager = MagicMock()
    state_manager.kill_switch_active = True  # Simulate active kill
    state_manager.refresh_kill_switch_from_db = AsyncMock(return_value=True)

    oanda_client = MagicMock()
    oanda_client.get_open_trades = AsyncMock(return_value=[])

    engine = ExecutionEngine(
        config=config,
        trading_client=oanda_client,
        state_manager=state_manager,
        db=MagicMock(),
        alert_service=MagicMock(send_critical=AsyncMock(), send_info=AsyncMock()),
    )

    # Replace executors with mocks so we can verify they were never called
    engine._oanda_executor = MagicMock(execute=AsyncMock())
    engine._paper_executor = MagicMock(execute=AsyncMock())

    now = datetime.now(timezone.utc)
    order = ApprovedOrder(
        order_ref=uuid4(),
        signal_id=uuid4(),
        pair="EUR_USD",
        direction=Direction.BUY,
        units=1000,
        entry_price=Decimal("1.08"),
        stop_loss=Decimal("1.07"),
        take_profit=Decimal("1.09"),
        risk_amount_usd=Decimal("3"),
        risk_pct=Decimal("0.01"),
        confidence=Decimal("0.8"),
        account_balance_at_approval=Decimal("300"),
        approved_at=now,
        expiry=now + timedelta(seconds=30),
        mode=TradingMode.LIVE,
    )

    result = await engine.execute_order(order, current_price=Decimal("1.08"))

    assert result is None
    # At minimum the top-of-method check fires; the second pre-broker check
    # may also fire on the LIVE path. Either way, no broker call must happen.
    assert state_manager.refresh_kill_switch_from_db.await_count >= 1
    engine._oanda_executor.execute.assert_not_awaited()
    engine._paper_executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_order_blocked_when_kill_flips_after_circuit_breaker():
    """Codex round-2 review: kill-switch can flip True between the top-of-method
    refresh and the broker call (during _circuit_breaker.check_and_transition).
    The pre-broker recheck must catch it."""
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    from lumitrade.core.enums import Direction
    from lumitrade.core.models import ApprovedOrder

    config = MagicMock()
    config.effective_trading_mode = MagicMock(return_value=TradingMode.LIVE.value)
    config.account_uuid = "test"

    state_manager = MagicMock()
    # Simulate flip-during-circuit-breaker by tracking call count:
    # 1st refresh -> kill stays False (top of method passes)
    # 2nd refresh -> kill flips True (pre-broker recheck catches it)
    call_count = {"n": 0}
    def _kill_flag():
        return state_manager._mock_kill_state

    state_manager._mock_kill_state = False
    type(state_manager).kill_switch_active = property(lambda self: self._mock_kill_state)

    async def _refresh():
        call_count["n"] += 1
        if call_count["n"] >= 2:
            state_manager._mock_kill_state = True
        return state_manager._mock_kill_state
    state_manager.refresh_kill_switch_from_db = AsyncMock(side_effect=_refresh)

    oanda_client = MagicMock()
    oanda_client.get_open_trades = AsyncMock(return_value=[])

    engine = ExecutionEngine(
        config=config,
        trading_client=oanda_client,
        state_manager=state_manager,
        db=MagicMock(),
        alert_service=MagicMock(send_critical=AsyncMock(), send_info=AsyncMock()),
    )
    engine._oanda_executor = MagicMock(execute=AsyncMock())
    engine._paper_executor = MagicMock(execute=AsyncMock())

    now = datetime.now(timezone.utc)
    order = ApprovedOrder(
        order_ref=uuid4(),
        signal_id=uuid4(),
        pair="EUR_USD",
        direction=Direction.BUY,
        units=1000,
        entry_price=Decimal("1.08"),
        stop_loss=Decimal("1.07"),
        take_profit=Decimal("1.09"),
        risk_amount_usd=Decimal("3"),
        risk_pct=Decimal("0.01"),
        confidence=Decimal("0.8"),
        account_balance_at_approval=Decimal("300"),
        approved_at=now,
        expiry=now + timedelta(seconds=30),
        mode=TradingMode.LIVE,
    )

    result = await engine.execute_order(order, current_price=Decimal("1.08"))

    # Top-of-method passed (kill was False), but pre-broker recheck caught
    # the flip and aborted before the broker call.
    assert result is None
    assert call_count["n"] >= 2  # Both refreshes happened
    engine._oanda_executor.execute.assert_not_awaited()
    engine._paper_executor.execute.assert_not_awaited()
