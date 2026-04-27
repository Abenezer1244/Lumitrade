"""
Regression tests for Codex 2026-04-25 audit finding [critical] #3:
'Live execution has no query-broker-status before retry path. OandaExecutor
places once and parses once; ExecutionEngine swallows exceptions to None.
Failure scenario: OANDA accepts the order but the client times out, Lumitrade
thinks it failed, and a later restart creates a duplicate live position.'

These tests cover the recovery path added to OandaExecutor:
1. place_market_order succeeds normally -> OrderResult returned (no recovery)
2. place_market_order raises BUT broker actually filled -> recovery via
   lookup_order_status returns OrderResult (NO duplicate position created)
3. place_market_order raises AND broker cancelled -> recovery surfaces
   ExecutionError (clean failure, no dup risk)
4. place_market_order raises AND lookup finds nothing (404) -> ExecutionError
   raised (genuine failure; reconciler will sweep up if needed)
5. place_market_order raises AND lookup itself fails -> ExecutionError raised
   (fail closed)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from lumitrade.core.enums import Direction, OrderStatus, TradingMode
from lumitrade.core.exceptions import ExecutionError
from lumitrade.core.models import ApprovedOrder
from lumitrade.execution_engine.oanda_executor import OandaExecutor


def _make_order(pair="EUR_USD") -> ApprovedOrder:
    now = datetime.now(timezone.utc)
    return ApprovedOrder(
        order_ref=uuid4(),
        signal_id=uuid4(),
        pair=pair,
        direction=Direction.BUY,
        units=1000,
        entry_price=Decimal("1.08430"),
        stop_loss=Decimal("1.08230"),
        take_profit=Decimal("1.08730"),
        risk_amount_usd=Decimal("3.00"),
        risk_pct=Decimal("0.01"),
        confidence=Decimal("0.80"),
        account_balance_at_approval=Decimal("300.00"),
        approved_at=now,
        expiry=now + timedelta(seconds=30),
        mode=TradingMode.LIVE,
    )


def _ok_response(broker_trade_id: str = "12345", fill_price: str = "1.08431") -> dict:
    return {
        "orderCreateTransaction": {"id": "tx-create-1"},
        "orderFillTransaction": {
            "id": "tx-fill-1",
            "tradeOpened": {"tradeID": broker_trade_id},
            "price": fill_price,
            "units": "1000",
        },
    }


@pytest.mark.asyncio
async def test_place_succeeds_no_recovery_path_taken():
    """Happy path: place_market_order returns normally; lookup is never called."""
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    client.lookup_order_status = AsyncMock()  # should never be called

    executor = OandaExecutor(client)
    result = await executor.execute(_make_order())

    assert result.broker_trade_id == "trade-A"
    assert result.status == OrderStatus.FILLED
    client.lookup_order_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_timeout_recovers_when_broker_already_filled(monkeypatch):
    """The critical scenario: place raises, but order was actually filled.
    Recovery via lookup_order_status produces an OrderResult — no dup risk."""
    # Skip the 2-second sleep to keep the test fast
    monkeypatch.setattr(
        "lumitrade.execution_engine.oanda_executor.RECOVERY_LOOKUP_DELAY_SEC", 0
    )

    client = MagicMock()
    client.place_market_order = AsyncMock(side_effect=TimeoutError("read timeout"))
    client.lookup_order_status = AsyncMock(return_value=_ok_response("trade-RECOVERED"))

    executor = OandaExecutor(client)
    order = _make_order()
    result = await executor.execute(order)

    # Recovery succeeded — same OrderResult as if the original POST had returned
    assert result.broker_trade_id == "trade-RECOVERED"
    assert result.status == OrderStatus.FILLED
    client.place_market_order.assert_awaited_once()
    # Lookup must use the same client_request_id (order_ref) so OANDA's
    # @<id> specifier finds the order that was actually committed.
    client.lookup_order_status.assert_awaited_once_with(str(order.order_ref))


@pytest.mark.asyncio
async def test_timeout_recovers_when_broker_cancelled(monkeypatch):
    """Place raises; broker cancelled the order. Recovery surfaces ExecutionError
    (clean failure — no dup risk because no trade was opened)."""
    monkeypatch.setattr(
        "lumitrade.execution_engine.oanda_executor.RECOVERY_LOOKUP_DELAY_SEC", 0
    )

    cancel_response = {
        "orderCreateTransaction": {"id": "tx-create-2"},
        "orderCancelTransaction": {
            "reason": "TAKE_PROFIT_ON_FILL_LOSS",
            "rejectReason": "TAKE_PROFIT_ON_FILL_LOSS",
        },
    }

    client = MagicMock()
    client.place_market_order = AsyncMock(side_effect=TimeoutError("read timeout"))
    client.lookup_order_status = AsyncMock(return_value=cancel_response)

    executor = OandaExecutor(client)

    with pytest.raises(ExecutionError, match="TAKE_PROFIT_ON_FILL_LOSS"):
        await executor.execute(_make_order())


@pytest.mark.asyncio
async def test_timeout_no_order_found_raises(monkeypatch):
    """Place raises; lookup returns None (order never reached OANDA).
    ExecutionError raised — caller fails closed; reconciler picks it up."""
    monkeypatch.setattr(
        "lumitrade.execution_engine.oanda_executor.RECOVERY_LOOKUP_DELAY_SEC", 0
    )

    client = MagicMock()
    client.place_market_order = AsyncMock(side_effect=TimeoutError("connection timeout"))
    client.lookup_order_status = AsyncMock(return_value=None)

    executor = OandaExecutor(client)

    with pytest.raises(ExecutionError, match="Order placement failed"):
        await executor.execute(_make_order())


@pytest.mark.asyncio
async def test_timeout_lookup_itself_fails_raises(monkeypatch):
    """Place raises AND lookup raises. Fail closed with ExecutionError."""
    monkeypatch.setattr(
        "lumitrade.execution_engine.oanda_executor.RECOVERY_LOOKUP_DELAY_SEC", 0
    )

    client = MagicMock()
    client.place_market_order = AsyncMock(side_effect=TimeoutError("read timeout"))
    client.lookup_order_status = AsyncMock(side_effect=RuntimeError("network down"))

    executor = OandaExecutor(client)

    with pytest.raises(ExecutionError):
        await executor.execute(_make_order())
