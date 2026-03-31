"""
Lumitrade Execution Engine
============================
Orchestrates order execution, fill verification, and position management.
Routes to paper or OANDA executor based on TradingMode.
Per BDS Section 7 and SAS Section 3.2.5.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from ..analytics.performance_analyzer import PerformanceAnalyzer
from ..config import LumitradeConfig
from ..core.enums import OrderStatus, TradingMode
from ..core.exceptions import OrderExpiredError
from ..core.models import ApprovedOrder, OrderResult
from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
from ..infrastructure.event_publisher import EventPublisher
from ..infrastructure.oanda_client import OandaClient, OandaTradingClient
from ..utils.pip_math import pips_between
from ..infrastructure.secure_logger import get_logger
from .circuit_breaker import CircuitBreaker
from .fill_verifier import FillVerifier
from .oanda_executor import OandaExecutor
from .order_machine import OrderStateMachine
from .paper_executor import PaperExecutor

logger = get_logger(__name__)
POSITION_MONITOR_INTERVAL = 60


class ExecutionEngine:
    def __init__(
        self,
        config: LumitradeConfig,
        trading_client: OandaTradingClient,
        state_manager,
        db: DatabaseClient,
        alert_service: AlertService,
        subagents=None,
        oanda_read_client: OandaClient | None = None,
        events: EventPublisher | None = None,
    ):
        self.config = config
        self._state = state_manager
        self._db = db
        self._alerts = alert_service
        self._subagents = subagents
        self._oanda_read = oanda_read_client
        self._oanda_trade = trading_client
        self._events = events
        self._circuit_breaker = CircuitBreaker()
        self._fill_verifier = FillVerifier(alert_service)
        self._paper_executor = PaperExecutor()
        self._oanda_executor = OandaExecutor(trading_client)
        self.performance_analyzer = PerformanceAnalyzer(db)

    async def execute_order(
        self, order: ApprovedOrder, current_price: Decimal
    ) -> OrderResult | None:
        machine = OrderStateMachine()
        try:
            machine.check_expiry(order)
        except OrderExpiredError:
            logger.warning("order_expired", order_ref=str(order.order_ref))
            return None

        try:
            # Both PAPER and LIVE use real OANDA orders
            # PAPER connects to practice server, LIVE to production server
            # This ensures paper trades show real positions on OANDA
            state = await self._circuit_breaker.check_and_transition()
            from ..core.enums import CircuitBreakerState
            if state == CircuitBreakerState.OPEN:
                logger.error(
                    "circuit_breaker_open_order_rejected",
                    order_ref=str(order.order_ref),
                )
                return None
            try:
                result = await self._oanda_executor.execute(order)
                await self._circuit_breaker.record_success()
            except Exception:
                await self._circuit_breaker.record_failure()
                raise

            machine.transition(OrderStatus.SUBMITTED)
            machine.transition(OrderStatus.ACKNOWLEDGED)
            machine.transition(OrderStatus.FILLED)

            verified = await self._fill_verifier.verify(order, result)
            await self._save_trade(order, verified)
            await self._alerts.send_info(
                f"Trade opened: {order.pair} {(order.direction.value if hasattr(order.direction, "value") else str(order.direction))} "
                f"{abs(order.units)} units at {verified.fill_price}"
            )

            # Publish order event to Mission Control
            if self._events:
                self._events.publish(
                    "EXECUTION",
                    "ORDER",
                    f"ORDER PLACED: {(order.direction.value if hasattr(order.direction, "value") else str(order.direction))} {abs(order.units)} {order.pair} @ {verified.fill_price}",
                    severity="SUCCESS",
                    pair=order.pair,
                    metadata={
                        "direction": (order.direction.value if hasattr(order.direction, "value") else str(order.direction)),
                        "units": abs(order.units),
                        "fill_price": str(verified.fill_price),
                        "stop_loss": str(order.stop_loss),
                        "take_profit": str(order.take_profit),
                        "slippage_pips": str(verified.slippage_pips),
                        "mode": (order.mode.value if hasattr(order.mode, "value") else str(order.mode)),
                        "signal_id": str(order.signal_id),
                    },
                )

            return verified
        except Exception as e:
            logger.error(
                "execution_failed",
                order_ref=str(order.order_ref),
                error=str(e),
            )
            return None

    async def _save_trade(self, order: ApprovedOrder, result: OrderResult) -> None:
        # CRITICAL: Never save a trade without a valid broker_trade_id.
        # Empty broker_trade_id creates ghost trades that can't be matched
        # to OANDA and will never be cleaned up by position monitor.
        if not result.broker_trade_id or not result.broker_trade_id.strip():
            logger.critical(
                "trade_save_blocked_no_broker_id",
                order_ref=str(order.order_ref),
                pair=order.pair,
                raw_response_keys=list(result.raw_response.keys()) if result.raw_response else [],
            )
            await self._alerts.send_critical(
                f"BLOCKED: Trade {order.pair} saved without broker_trade_id. "
                f"Order filled but not tracked — manual OANDA review required."
            )
            return

        try:
            await self._db.insert(
                "trades",
                {
                    "account_id": self.config.account_uuid,
                    "signal_id": str(order.signal_id),
                    "broker_trade_id": result.broker_trade_id,
                    "pair": order.pair,
                    "direction": (order.direction.value if hasattr(order.direction, "value") else str(order.direction)),
                    "mode": (order.mode.value if hasattr(order.mode, "value") else str(order.mode)),
                    "entry_price": str(result.fill_price),
                    "stop_loss": str(order.stop_loss),
                    "take_profit": str(order.take_profit),
                    "position_size": abs(order.units),
                    "confidence_score": str(order.confidence),
                    "slippage_pips": str(result.slippage_pips),
                    "status": "OPEN",
                    "session": "",
                    "opened_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            logger.error("trade_save_failed", error=str(e))

    async def position_monitor(self) -> None:
        """Monitor open positions — detect closes, trail stops."""
        logger.info("position_monitor_started")
        try:
            while True:
                await asyncio.sleep(POSITION_MONITOR_INTERVAL)
                try:
                    await self._check_closed_positions()
                    await self._trail_stop_losses()
                except Exception as e:
                    logger.error("position_monitor_error", error=str(e))
        except asyncio.CancelledError:
            logger.info("position_monitor_cancelled")

    async def _check_closed_positions(self) -> None:
        """Compare DB open trades with OANDA open trades. Close any that are gone."""
        # Get DB trades marked OPEN
        db_open = await self._db.select(
            "trades", {"status": "OPEN", "account_id": self.config.account_uuid}
        )
        if not db_open:
            return

        # Get OANDA open trade IDs
        oanda_open_ids: set[str] = set()
        if self._oanda_read:
            try:
                oanda_trades = await self._oanda_read.get_open_trades()
                oanda_open_ids = {t["id"] for t in oanda_trades}
            except Exception as e:
                logger.warning("position_monitor_oanda_error", error=str(e))
                return  # Can't check — skip this cycle

        for trade in db_open:
            broker_id = trade.get("broker_trade_id", "")

            # Paper trades or trades with missing broker ID:
            # check SL/TP against current price
            if broker_id.startswith("PAPER-") or not broker_id:
                await self._check_paper_trade_exit(trade)
                continue

            # Live trades: if broker_trade_id not in OANDA open trades, it's closed
            if broker_id not in oanda_open_ids:
                await self._mark_trade_closed(trade)

    async def _check_paper_trade_exit(self, trade: dict) -> None:
        """Check if a paper trade's SL or TP has been hit by current price."""
        pair = trade.get("pair", "")
        if not pair or not self._oanda_read:
            return

        try:
            pricing = await self._oanda_read.get_pricing([pair])
            if not pricing:
                return
            prices = pricing.get("prices", [])
            if not prices:
                return
            p = prices[0]
            bids = p.get("bids", [{}])
            asks = p.get("asks", [{}])
            current_bid = Decimal(str(bids[0].get("price", "0"))) if bids else Decimal("0")
            current_ask = Decimal(str(asks[0].get("price", "0"))) if asks else Decimal("0")
            current_price = (current_bid + current_ask) / 2
        except Exception as e:
            logger.warning("paper_trade_pricing_error", pair=pair, error=str(e))
            return

        entry = Decimal(str(trade.get("entry_price", "0")))
        sl = Decimal(str(trade.get("stop_loss", "0")))
        tp = Decimal(str(trade.get("take_profit", "0")))
        direction = trade.get("direction", "BUY")

        hit_sl = False
        hit_tp = False

        if direction == "BUY":
            hit_sl = current_price <= sl
            hit_tp = current_price >= tp
        else:  # SELL
            hit_sl = current_price >= sl
            hit_tp = current_price <= tp

        if hit_sl or hit_tp:
            exit_price = sl if hit_sl else tp
            pnl_pips = pips_between(entry, exit_price, pair)
            if direction == "SELL":
                pnl_pips = -pnl_pips if hit_sl else pnl_pips
            elif hit_sl:
                pnl_pips = -abs(pnl_pips)

            units = int(trade.get("position_size", 0))
            from ..utils.pip_math import pip_value_per_unit
            pv = pip_value_per_unit(pair, exit_price)
            pnl_usd = pnl_pips * Decimal(str(units)) * pv

            outcome = "WIN" if pnl_usd > 0 else "LOSS"
            exit_reason = "TP_HIT" if hit_tp else "SL_HIT"

            await self._update_closed_trade(
                trade, exit_price, pnl_pips, pnl_usd, outcome, exit_reason
            )

    # ── Trailing Stop Loss ──────────────────────────────────────
    # Trail distance = original SL distance (entry to SL).
    # Activation threshold varies by instrument volatility.
    # Trail: once activated, move SL to lock in (current_price - trail_distance).
    # Never move SL backwards — only forward in the direction of profit.
    TRAIL_ACTIVATION_PIPS: dict[str, Decimal] = {
        # Forex majors — standard 20 pip activation
        "EUR_USD": Decimal("20"),
        "GBP_USD": Decimal("25"),     # GBP is more volatile
        "AUD_USD": Decimal("20"),
        "NZD_USD": Decimal("20"),
        "USD_CAD": Decimal("20"),
        "USD_CHF": Decimal("20"),
        # JPY pairs — same pip count but pips are 0.01 not 0.0001
        "USD_JPY": Decimal("20"),
        # Gold — much larger price, needs bigger activation
        "XAU_USD": Decimal("500"),    # $5.00 move (~0.1% of price)
    }
    DEFAULT_TRAIL_ACTIVATION = Decimal("20")

    async def _trail_stop_losses(self) -> None:
        """Check open trades and trail their stop losses on OANDA.
        Batches pricing calls by collecting all unique pairs first."""
        db_open = await self._db.select(
            "trades", {"status": "OPEN", "account_id": self.config.account_uuid}
        )
        if not db_open or not self._oanda_read:
            return

        # Filter to trades with valid broker IDs
        trailable = [t for t in db_open if t.get("broker_trade_id", "").strip()]
        if not trailable:
            return

        # Batch: fetch prices for all pairs at once (1 API call instead of N)
        all_pairs = list({t["pair"] for t in trailable if t.get("pair")})
        try:
            pricing = await self._oanda_read.get_pricing(all_pairs)
        except Exception as e:
            logger.warning("trailing_stop_pricing_error", error=str(e))
            return

        # Build price map
        price_map: dict[str, Decimal] = {}
        for p in pricing.get("prices", []):
            inst = p.get("instrument", "")
            bids = p.get("bids", [])
            asks = p.get("asks", [])
            if bids and asks:
                bid = Decimal(str(bids[0]["price"]))
                ask = Decimal(str(asks[0]["price"]))
                price_map[inst] = (bid + ask) / 2

        # Check each trade against current prices
        for trade in trailable:
            try:
                await self._check_and_trail(trade, price_map)
            except Exception as e:
                logger.warning(
                    "trailing_stop_error",
                    pair=trade.get("pair", ""),
                    broker_id=trade.get("broker_trade_id", ""),
                    error=str(e),
                )

    async def _check_and_trail(self, trade: dict, price_map: dict[str, Decimal]) -> None:
        """Check if a trade qualifies for trailing stop and update on OANDA."""
        pair = trade.get("pair", "")
        direction = trade.get("direction", "BUY")
        entry = Decimal(str(trade.get("entry_price", "0")))
        current_sl = Decimal(str(trade.get("stop_loss", "0")))
        tp = Decimal(str(trade.get("take_profit", "0")))
        broker_id = trade.get("broker_trade_id", "")

        current_price = price_map.get(pair)
        if not current_price or current_price == 0 or entry == 0:
            return

        # Calculate profit in pips (signed)
        if direction == "BUY":
            profit_pips = pips_between(entry, current_price, pair) if current_price > entry else -pips_between(current_price, entry, pair)
        else:
            profit_pips = pips_between(current_price, entry, pair) if current_price < entry else -pips_between(entry, current_price, pair)

        # Break-even stop: move SL to entry when +15 pips (gold: +300 pips)
        from ..utils.pip_math import pip_size as get_pip_size
        ps = get_pip_size(pair)
        be_threshold = Decimal("300") if pair == "XAU_USD" else Decimal("15")
        sl_is_behind_entry = (direction == "BUY" and current_sl < entry) or (direction == "SELL" and current_sl > entry)
        if profit_pips >= be_threshold and sl_is_behind_entry:
            # Move SL to entry (breakeven)
            be_sl = entry
            if ps >= Decimal("0.01"):
                be_sl = be_sl.quantize(Decimal("0.001"))
            else:
                be_sl = be_sl.quantize(Decimal("0.00001"))

            await self._oanda_trade.modify_trade(broker_id, be_sl, tp)
            await self._db.update(
                "trades",
                {"id": trade.get("id")},
                {"stop_loss": str(be_sl)},
            )
            logger.info(
                "breakeven_stop_set",
                pair=pair, broker_id=broker_id, direction=direction,
                entry=str(entry), old_sl=str(current_sl), new_sl=str(be_sl),
                profit_pips=str(profit_pips),
            )
            if self._events:
                self._events.publish(
                    "EXECUTION", "BREAKEVEN_STOP",
                    f"SL moved to breakeven: {pair} {direction} — {current_sl} → {be_sl} (+{profit_pips:.1f} pips)",
                    pair=pair, severity="INFO",
                )
            return  # Don't also trail in the same cycle

        # Per-instrument activation threshold for trailing stop
        activation = self.TRAIL_ACTIVATION_PIPS.get(pair, self.DEFAULT_TRAIL_ACTIVATION)
        if profit_pips < activation:
            return

        # Trail distance = original SL distance from entry
        original_sl_distance = abs(entry - current_sl)

        # Calculate new trailing SL
        if direction == "BUY":
            new_sl = current_price - original_sl_distance
            if new_sl <= current_sl:
                return
        else:  # SELL
            new_sl = current_price + original_sl_distance
            if new_sl >= current_sl:
                return

        # Round to appropriate decimal places
        if ps >= Decimal("0.01"):
            new_sl = new_sl.quantize(Decimal("0.001"))
        else:
            new_sl = new_sl.quantize(Decimal("0.00001"))

        # Update SL on OANDA
        await self._oanda_trade.modify_trade(broker_id, new_sl, tp)

        # Update SL in DB
        await self._db.update(
            "trades",
            {"id": trade.get("id")},
            {"stop_loss": str(new_sl)},
        )

        logger.info(
            "trailing_stop_moved",
            pair=pair,
            broker_id=broker_id,
            direction=direction,
            old_sl=str(current_sl),
            new_sl=str(new_sl),
            profit_pips=str(profit_pips),
            activation_threshold=str(activation),
        )

        if self._events:
            self._events.publish(
                "EXECUTION", "TRAILING_STOP",
                f"SL trailed: {pair} {direction} — {current_sl} → {new_sl} (+{profit_pips:.1f} pips)",
                pair=pair, severity="INFO",
                metadata={
                    "old_sl": str(current_sl),
                    "new_sl": str(new_sl),
                    "profit_pips": str(profit_pips),
                },
            )

    async def _mark_trade_closed(self, trade: dict) -> None:
        """Mark a live trade as closed — fetch real exit details from OANDA."""
        entry = Decimal(str(trade.get("entry_price", "0")))
        pair = trade.get("pair", "")
        direction = trade.get("direction", "BUY")
        broker_id = trade.get("broker_trade_id", "")

        # Fetch real close details from OANDA trade history
        exit_price = entry
        realized_pnl = Decimal("0")
        exit_reason = "UNKNOWN"
        try:
            if self._oanda_read and broker_id:
                oanda_trade = await self._oanda_read.get_trade(broker_id)
                trade_state = oanda_trade.get("state", "UNKNOWN")
                logger.info(
                    "oanda_trade_closure_data",
                    broker_id=broker_id,
                    pair=pair,
                    state=trade_state,
                    averageClosePrice=oanda_trade.get("averageClosePrice"),
                    realizedPL=oanda_trade.get("realizedPL"),
                    currentUnits=oanda_trade.get("currentUnits"),
                )
                # OANDA returns averageClosePrice and realizedPL for closed trades
                close_price = oanda_trade.get("averageClosePrice")
                if close_price and float(close_price) != 0:
                    exit_price = Decimal(str(close_price))
                real_pl = oanda_trade.get("realizedPL")
                if real_pl and float(real_pl) != 0:
                    realized_pnl = Decimal(str(real_pl))

                # Determine exit reason from OANDA close reason
                close_reason = oanda_trade.get("closingTransactionIDs", [])
                # Check SL/TP by comparing exit price to expected levels
                sl = Decimal(str(trade.get("stop_loss", "0")))
                tp = Decimal(str(trade.get("take_profit", "0")))
                sl_dist = abs(exit_price - sl)
                tp_dist = abs(exit_price - tp)
                from ..utils.pip_math import pip_size as get_pip_size
                ps = get_pip_size(pair)
                if sl_dist < ps * 5:  # Within 5 pips of SL
                    exit_reason = "SL_HIT"
                elif tp_dist < ps * 5:  # Within 5 pips of TP
                    exit_reason = "TP_HIT"
        except Exception as e:
            logger.warning("oanda_trade_fetch_failed", broker_id=broker_id, error=str(e))

        # Calculate P&L in pips
        pnl_pips = pips_between(entry, exit_price, pair)
        if direction == "BUY":
            pnl_pips = pnl_pips if exit_price > entry else -pnl_pips
        else:
            pnl_pips = pnl_pips if exit_price < entry else -pnl_pips

        # Use OANDA's realized P&L if available, otherwise calculate
        if realized_pnl == 0 and exit_price != entry:
            units = int(trade.get("position_size", 0))
            from ..utils.pip_math import pip_value_per_unit
            pv = pip_value_per_unit(pair, exit_price)
            realized_pnl = pnl_pips * Decimal(str(units)) * pv

        outcome = "WIN" if realized_pnl > 0 else ("LOSS" if realized_pnl < 0 else "BREAKEVEN")

        # Publish event
        if self._events:
            self._events.publish(
                "EXECUTION",
                "POSITION_CLOSED_DETECTED",
                f"Closed: {pair} {direction} | {outcome} | P&L: ${realized_pnl:.2f} | Exit: {exit_price}",
                severity="SUCCESS" if outcome == "WIN" else "WARNING",
                pair=pair,
                metadata={
                    "trade_id": trade.get("id", ""),
                    "broker_trade_id": broker_id,
                    "exit_price": str(exit_price),
                    "realized_pnl": str(realized_pnl),
                    "exit_reason": exit_reason,
                },
            )

        await self._update_closed_trade(
            trade, exit_price, pnl_pips, realized_pnl, outcome, exit_reason
        )

    async def _update_closed_trade(
        self,
        trade: dict,
        exit_price: Decimal,
        pnl_pips: Decimal,
        pnl_usd: Decimal,
        outcome: str,
        exit_reason: str,
    ) -> None:
        """Update trade record in DB as CLOSED."""
        trade_id = trade.get("id", "")
        now = datetime.now(timezone.utc)
        try:
            await self._db.update(
                "trades",
                {"id": trade_id},
                {
                    "status": "CLOSED",
                    "exit_price": str(exit_price),
                    "pnl_pips": str(pnl_pips),
                    "pnl_usd": str(pnl_usd),
                    "outcome": outcome,
                    "exit_reason": exit_reason,
                    "closed_at": now.isoformat(),
                },
            )
            logger.info(
                "trade_closed",
                trade_id=trade_id,
                pair=trade.get("pair"),
                outcome=outcome,
                pnl_usd=str(pnl_usd),
                pnl_pips=str(pnl_pips),
                exit_reason=exit_reason,
            )

            # Publish trade close event to Mission Control
            pair = trade.get("pair", "")
            direction = trade.get("direction", "")
            if self._events:
                self._events.publish(
                    "EXECUTION",
                    "TRADE_CLOSE",
                    f"CLOSED: {pair} {direction} | {outcome} | P&L: ${pnl_usd}",
                    severity="SUCCESS" if outcome == "WIN" else "WARNING",
                    pair=pair,
                    metadata={
                        "trade_id": trade_id,
                        "direction": direction,
                        "outcome": outcome,
                        "pnl_usd": str(pnl_usd),
                        "pnl_pips": str(pnl_pips),
                        "exit_price": str(exit_price),
                        "exit_reason": exit_reason,
                    },
                )

            # Update state
            if self._state:
                state = self._state
                if outcome == "LOSS":
                    current = state._state.get("consecutive_losses", 0)
                    state._state["consecutive_losses"] = current + 1
                elif outcome == "WIN":
                    state._state["consecutive_losses"] = 0

                daily_pnl = Decimal(str(state._state.get("daily_pnl", "0")))
                state._state["daily_pnl"] = str(daily_pnl + pnl_usd)

            # Trigger SA-02 post-trade analysis + performance insights
            asyncio.create_task(
                self._run_post_trade_analysis(trade),
                name=f"post_trade_{trade_id[:8]}",
            )

        except Exception as e:
            logger.error("trade_close_update_failed", trade_id=trade_id, error=str(e))

    async def _run_post_trade_analysis(self, trade: dict) -> None:
        """Fire SA-02 post-trade analyst and insight analysis after trade closes."""
        try:
            if self._subagents:
                recent = await self._db.select(
                    "trades",
                    {"status": "CLOSED", "account_id": self.config.account_uuid},
                    order="closed_at",
                    limit=20,
                )
                await self._subagents.run_post_trade(
                    trade=trade,
                    signal={"recent_trades": recent},
                )
        except Exception as e:
            logger.warning("post_trade_analysis_failed", error=str(e))

        await self._trigger_insight_analysis(trade)

    async def _trigger_insight_analysis(self, trade: dict) -> None:
        min_trades = 50
        every_n = 10
        try:
            count = await self._db.count("trades", {"status": "CLOSED"})
            if count < min_trades:
                return
            if count % every_n == 0:
                logger.info("insight_analysis_triggered", trade_count=count)
                asyncio.create_task(
                    self.performance_analyzer.analyze(
                        trade.get("account_id", "")
                    ),
                    name=f"insight_{count}",
                )
        except Exception as e:
            logger.warning("insight_trigger_failed", error=str(e))
