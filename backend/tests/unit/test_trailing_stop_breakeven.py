"""
Regression test for Codex 2026-04-25 audit finding [high] #5:
'Trailing-stop logic can collapse the trail gap to zero after breakeven.
Breakeven moves SL to entry, then later trailing recomputes distance as
abs(entry - current_sl) = 0. Failure scenario: the next monitor cycle
moves SL essentially to current market and exits a winner on noise.'

Fix: persist initial_stop_loss at trade open (migration 016) and trail
from that fixed value in _check_and_trail.

These tests cover the exact scenario the audit flagged:
  1. Trade opens with SL 20 pips behind entry.
  2. Breakeven fires at +15 pips (SL moved to entry).
  3. Price runs further in our favor (+50 pips).
  4. Trailing stop must place new SL ~20 pips behind current price,
     NOT at current price. Verifies original_sl_distance is preserved.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from lumitrade.core.enums import TradingMode
from lumitrade.execution_engine.engine import ExecutionEngine


def _build_engine_for_trail() -> ExecutionEngine:
    config = MagicMock()
    config.effective_trading_mode = MagicMock(return_value=TradingMode.LIVE.value)
    config.account_uuid = "test-acct"

    trading_client = MagicMock()
    trading_client.modify_trade = AsyncMock(return_value={"ok": True})

    db = MagicMock()
    db.update = AsyncMock(return_value=None)

    alerts = MagicMock(send_critical=AsyncMock(), send_info=AsyncMock())

    return ExecutionEngine(
        config=config,
        trading_client=trading_client,
        state_manager=MagicMock(),
        db=db,
        alert_service=alerts,
    )


def _trade(pair="USD_CAD", direction="BUY", entry="1.40000",
           current_sl="1.40000", initial_sl="1.39800",
           tp="1.40500", broker_id="BT-1"):
    """Build a trade dict matching the shape consumed by _check_and_trail."""
    return {
        "id": "trade-uuid-1",
        "pair": pair,
        "direction": direction,
        "entry_price": entry,
        "stop_loss": current_sl,
        "initial_stop_loss": initial_sl,
        "take_profit": tp,
        "broker_trade_id": broker_id,
    }


@pytest.mark.asyncio
async def test_trailing_uses_initial_distance_after_breakeven():
    """The bug: after breakeven (SL at entry), trail must NOT collapse to zero.
    This test simulates the broken state Codex flagged: BUY at 1.40000 with
    initial SL 1.39800 (20 pips), breakeven already fired (current_sl = entry),
    price now at 1.40500 (+50 pips). New SL must be ~20 pips behind 1.40500."""
    engine = _build_engine_for_trail()
    trade = _trade(
        entry="1.40000",
        current_sl="1.40000",       # post-breakeven: SL was moved to entry
        initial_sl="1.39800",       # original SL at open: 20 pips behind
    )
    price_map = {"USD_CAD": Decimal("1.40500")}  # +50 pips from entry

    await engine._check_and_trail(trade, price_map)

    # New SL must be ~20 pips behind current price (1.40500 - 0.00200 = 1.40300),
    # NOT at the current price (1.40500). The original bug would set new_sl
    # = 1.40500 - 0 = 1.40500, exiting the trade on the next tick.
    engine._oanda_trade.modify_trade.assert_awaited_once()
    new_sl = engine._oanda_trade.modify_trade.await_args.args[1]
    assert isinstance(new_sl, Decimal)
    # The trail uses absolute(entry - initial_sl) = abs(1.40000 - 1.39800) = 0.00200
    # New SL = 1.40500 - 0.00200 = 1.40300, then quantized to 5dp.
    assert new_sl == Decimal("1.40300")


@pytest.mark.asyncio
async def test_trailing_skips_when_initial_distance_is_zero():
    """If initial_stop_loss == entry (degenerate row or bad backfill), do NOT
    set SL onto the current market price. Skip and warn."""
    engine = _build_engine_for_trail()
    trade = _trade(
        entry="1.40000",
        current_sl="1.40000",
        initial_sl="1.40000",  # degenerate: zero initial distance
    )
    price_map = {"USD_CAD": Decimal("1.40500")}

    await engine._check_and_trail(trade, price_map)

    engine._oanda_trade.modify_trade.assert_not_awaited()
    engine._db.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_trailing_legacy_row_post_breakeven_skips_safely():
    """Pre-migration-016 rows have no initial_stop_loss. If such a trade was
    already moved to breakeven (current_sl == entry), the fallback to
    current_sl gives zero original distance — the trailer must SKIP rather
    than collapse SL onto the market. Worse to skip than to mis-trail."""
    engine = _build_engine_for_trail()
    trade = _trade(
        entry="1.40000",
        current_sl="1.40000",   # already at breakeven
        initial_sl=None,         # legacy row, no initial_stop_loss
    )
    trade.pop("initial_stop_loss")

    price_map = {"USD_CAD": Decimal("1.40500")}  # +50 pips

    await engine._check_and_trail(trade, price_map)

    # Trailer must skip: zero-distance guard prevents SL collapse to market.
    engine._oanda_trade.modify_trade.assert_not_awaited()
    engine._db.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_trailing_buy_does_not_move_sl_backwards():
    """Trail must never move SL backwards (away from current price)."""
    engine = _build_engine_for_trail()
    # Already-trailed trade: current SL is closer to current price than the
    # naive initial_sl-distance trail would set it.
    trade = _trade(
        entry="1.40000",
        current_sl="1.40400",  # already trailed up tight
        initial_sl="1.39800",  # 20 pip original distance
    )
    price_map = {"USD_CAD": Decimal("1.40500")}  # +50 pips
    # Naive trail: 1.40500 - 0.00200 = 1.40300, which is < current_sl 1.40400.
    # Must NOT move SL backwards.

    await engine._check_and_trail(trade, price_map)

    engine._oanda_trade.modify_trade.assert_not_awaited()
