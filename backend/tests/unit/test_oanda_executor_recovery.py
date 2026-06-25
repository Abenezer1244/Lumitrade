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
        "relatedTransactionIDs": ["tx-create-1", "tx-fill-1", "tx-sl-1", "tx-tp-1"],
    }


def _ok_trade(sl: str | None = "1.08230", tp: str | None = "1.08730") -> dict:
    """A live OANDA trade object with attached SL/TP orders, as get_trade returns.
    Pass sl=None / tp=None to simulate a missing protective order."""
    trade: dict = {"id": "12345", "currentUnits": "1000"}
    if sl is not None:
        trade["stopLossOrder"] = {"id": "sl-1", "price": sl}
    if tp is not None:
        trade["takeProfitOrder"] = {"id": "tp-1", "price": tp}
    return trade


@pytest.mark.asyncio
async def test_place_succeeds_no_recovery_path_taken():
    """Happy path: place_market_order returns normally; lookup is never called."""
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    client.lookup_order_status = AsyncMock()  # should never be called
    client.get_trade = AsyncMock(return_value=_ok_trade())

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
    client.get_trade = AsyncMock(return_value=_ok_trade())

    executor = OandaExecutor(client)
    order = _make_order()
    result = await executor.execute(order)

    # Recovery succeeded — same OrderResult as if the original POST had returned
    assert result.broker_trade_id == "trade-RECOVERED"
    assert result.status == OrderStatus.FILLED
    client.place_market_order.assert_awaited_once()
    # Lookup must use the same client_request_id (order_ref) so OANDA's
    # @<id> specifier finds the order that was actually committed.
    client.lookup_order_status.assert_awaited_once_with(str(order.order_ref), pair=order.pair)


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


# ── Audit 2026-06-25: SL/TP confirmation via real trade readback (Phase 3) ──


@pytest.mark.asyncio
async def test_protection_confirmed_from_actual_trade_readback():
    """SL/TP confirmed values come from the LIVE trade (get_trade), not the
    requested order. The broker-attached prices are what we report."""
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    client.get_trade = AsyncMock(return_value=_ok_trade(sl="1.08230", tp="1.08730"))
    client.modify_trade = AsyncMock()

    executor = OandaExecutor(client)
    result = await executor.execute(_make_order())

    assert result.stop_loss_confirmed == Decimal("1.08230")
    assert result.take_profit_confirmed == Decimal("1.08730")
    client.get_trade.assert_awaited_once()
    client.modify_trade.assert_not_awaited()  # nothing missing -> no correction


@pytest.mark.asyncio
async def test_protection_missing_triggers_corrective_then_confirms():
    """If the readback shows the SL is missing, the executor places a corrective
    modify_trade and re-reads; the corrected SL is then confirmed."""
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    # 1st readback: SL missing. 2nd readback (after correction): SL present.
    client.get_trade = AsyncMock(side_effect=[
        _ok_trade(sl=None, tp="1.08730"),
        _ok_trade(sl="1.08230", tp="1.08730"),
    ])
    client.modify_trade = AsyncMock()
    client.close_trade = AsyncMock()

    executor = OandaExecutor(client)
    result = await executor.execute(_make_order())

    client.modify_trade.assert_awaited_once()
    client.close_trade.assert_not_awaited()  # correction succeeded -> no close
    assert result.stop_loss_confirmed == Decimal("1.08230")


@pytest.mark.asyncio
async def test_protection_missing_and_correction_fails_closes_trade():
    """If the SL is confirmed missing AND the corrective modify fails, the
    unprotected position is emergency-closed and protection reported as None."""
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    client.get_trade = AsyncMock(return_value=_ok_trade(sl=None, tp="1.08730"))
    client.modify_trade = AsyncMock(side_effect=RuntimeError("modify rejected"))
    client.close_trade = AsyncMock()

    executor = OandaExecutor(client)
    result = await executor.execute(_make_order())

    client.modify_trade.assert_awaited_once()
    client.close_trade.assert_awaited_once()  # unprotected -> emergency close
    assert result.stop_loss_confirmed is None


@pytest.mark.asyncio
async def test_correction_succeeds_but_recheck_fails_does_not_close():
    """Codex catch: after a SUCCESSFUL corrective modify_trade, if the second
    readback transiently fails, the trade must NOT be emergency-closed — the
    correction almost certainly set the stop. Report unconfirmed, never close."""
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    # 1st readback: SL missing (positively). 2nd readback (post-correction): FAILS.
    client.get_trade = AsyncMock(side_effect=[
        _ok_trade(sl=None, tp="1.08730"),
        RuntimeError("recheck timeout"),
    ])
    client.modify_trade = AsyncMock()       # correction accepted
    client.close_trade = AsyncMock()

    executor = OandaExecutor(client)
    result = await executor.execute(_make_order())

    client.modify_trade.assert_awaited_once()
    client.close_trade.assert_not_awaited()  # MUST NOT close on post-fix uncertainty
    assert result.stop_loss_confirmed is None  # unconfirmed -> FillVerifier alerts


@pytest.mark.asyncio
async def test_malformed_recheck_response_does_not_close():
    """Codex catch #2: a MALFORMED (but successful) second readback after a
    corrective modify must be treated as uncertain (ok=False) and must NOT
    emergency-close a potentially protected trade."""
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    # 1st readback: SL positively missing. 2nd readback: malformed (a list, not a
    # trade dict) -> parsing raises inside _read_protection -> ok=False.
    client.get_trade = AsyncMock(side_effect=[
        _ok_trade(sl=None, tp="1.08730"),
        ["not", "a", "dict"],
    ])
    client.modify_trade = AsyncMock()  # correction accepted
    client.close_trade = AsyncMock()

    executor = OandaExecutor(client)
    result = await executor.execute(_make_order())

    client.modify_trade.assert_awaited_once()
    client.close_trade.assert_not_awaited()  # malformed recheck != confirmed missing
    assert result.stop_loss_confirmed is None


@pytest.mark.asyncio
async def test_falsy_malformed_protective_order_is_uncertain_not_missing():
    """Codex catch #3: a present-but-malformed protective order (e.g. an empty
    list, or a dict with no/garbage price) must mark the readback UNCERTAIN
    (ok=False), not 'missing' — otherwise persistently-malformed data could
    drive an emergency close of a protected trade. A genuinely ABSENT order
    (key missing) is still treated as no-protection."""
    # Present-but-malformed stopLossOrder ([] is falsy non-dict) on every read.
    bad_trade = {"id": "12345", "stopLossOrder": [], "takeProfitOrder": {"price": "1.08730"}}
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    client.get_trade = AsyncMock(return_value=bad_trade)
    client.modify_trade = AsyncMock()
    client.close_trade = AsyncMock()

    executor = OandaExecutor(client)
    result = await executor.execute(_make_order())

    # Malformed SL -> readback uncertain -> best-effort reassert, NEVER close.
    client.close_trade.assert_not_awaited()
    assert result.stop_loss_confirmed is None

    # _parse_protective_order contract:
    assert OandaExecutor._parse_protective_order(None) is None        # absent
    assert OandaExecutor._parse_protective_order({"price": "1.5"}) == Decimal("1.5")
    for bad in ([], "", 0, {"price": None}, {"price": "NaN"}, {}):
        try:
            OandaExecutor._parse_protective_order(bad)
            raised = False
        except Exception:
            raised = True
        assert raised, f"malformed protective order {bad!r} must raise (uncertain)"


def test_price_or_none_rejects_non_finite_and_garbage():
    """A non-finite ("NaN"/"Infinity") or unparsable price must become None, not
    a bogus 'confirmed' stop."""
    assert OandaExecutor._price_or_none("1.08230") == Decimal("1.08230")
    assert OandaExecutor._price_or_none(None) is None
    assert OandaExecutor._price_or_none("") is None
    assert OandaExecutor._price_or_none("NaN") is None
    assert OandaExecutor._price_or_none("Infinity") is None
    assert OandaExecutor._price_or_none("not-a-price") is None


@pytest.mark.asyncio
async def test_readback_failure_reasserts_but_does_not_close():
    """A transient readback failure must NOT emergency-close (absence unknown).
    The executor re-asserts protection best-effort and reports unconfirmed."""
    client = MagicMock()
    client.place_market_order = AsyncMock(return_value=_ok_response("trade-A"))
    client.get_trade = AsyncMock(side_effect=RuntimeError("trade fetch timeout"))
    client.modify_trade = AsyncMock()
    client.close_trade = AsyncMock()

    executor = OandaExecutor(client)
    result = await executor.execute(_make_order())

    client.modify_trade.assert_awaited_once()       # best-effort re-assert
    client.close_trade.assert_not_awaited()         # never close on uncertainty
    assert result.stop_loss_confirmed is None
    assert result.take_profit_confirmed is None
