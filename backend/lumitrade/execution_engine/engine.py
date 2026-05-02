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

from ..ai_brain.lesson_analyzer import LessonAnalyzer
from ..analytics.performance_analyzer import PerformanceAnalyzer
from ..config import LumitradeConfig
from ..core.enums import CircuitBreakerState, OrderStatus, TradingMode
from ..core.exceptions import ExecutionError, OrderExpiredError
from ..core.models import ApprovedOrder, OrderResult
from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
from ..infrastructure.event_publisher import EventPublisher
from ..infrastructure.oanda_client import OandaClient, OandaTradingClient
from ..utils.pip_math import pip_size as get_pip_size
from ..utils.pip_math import pip_value_per_unit, pips_between, _FRACTIONAL_UNIT_PAIRS
from ..utils.time_utils import session_label_for_lesson
from ..infrastructure.secure_logger import get_logger
from .circuit_breaker import CircuitBreaker
from .fill_verifier import FillVerifier
from .oanda_executor import OandaExecutor
from .order_machine import OrderStateMachine
from .paper_executor import PaperExecutor

logger = get_logger(__name__)
POSITION_MONITOR_INTERVAL = 60


class ExecutionEngine:
    # Instruments routed to Capital.com instead of OANDA
    CAPITAL_INSTRUMENTS = {"XAU_USD"}

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
        capital_client=None,
    ):
        self.config = config
        self._state = state_manager
        self._db = db
        self._alerts = alert_service
        self._subagents = subagents
        self._oanda_read = oanda_read_client
        self._oanda_trade = trading_client
        self._events = events
        self._capital_client = capital_client
        self._circuit_breaker = CircuitBreaker()
        self._fill_verifier = FillVerifier(alert_service)
        self._paper_executor = PaperExecutor()
        self._oanda_executor = OandaExecutor(trading_client)
        if capital_client:
            from .capital_executor import CapitalExecutor
            self._capital_executor = CapitalExecutor(capital_client)
        else:
            self._capital_executor = None
        self.performance_analyzer = PerformanceAnalyzer(db)
        self._lesson_analyzer = LessonAnalyzer(db, config)

    async def execute_order(
        self, order: ApprovedOrder, current_price: Decimal
    ) -> OrderResult | None:
        # Kill-switch guard: block any new order placement once the kill
        # switch is active, even if a signal slipped through the loop's
        # kill check. Refresh from DB first so we observe activations from
        # the HTTP endpoint without waiting for the next loop tick.
        if self._state is not None:
            try:
                if hasattr(self._state, "refresh_kill_switch_from_db"):
                    await self._state.refresh_kill_switch_from_db()
                if getattr(self._state, "kill_switch_active", False):
                    logger.warning(
                        "execute_order_blocked_kill_switch_active",
                        order_ref=str(order.order_ref),
                        pair=order.pair,
                    )
                    return None
            except Exception:
                logger.exception("execute_order_kill_switch_check_failed")
                # Refresh failed — honour cached state rather than proceeding blind.
                # If kill was active before the refresh, block. Unknown = allow
                # (loop-level check is the primary gate). Codex+Claude audit 2026-04-30 — P2 fix.
                if getattr(self._state, "kill_switch_active", False):
                    logger.warning(
                        "execute_order_blocked_kill_switch_cached",
                        order_ref=str(order.order_ref),
                        pair=order.pair,
                    )
                    return None

        machine = OrderStateMachine()
        try:
            machine.check_expiry(order)
        except OrderExpiredError:
            logger.warning("order_expired", order_ref=str(order.order_ref))
            return None

        try:
            # Effective mode (env_var AND dashboard_toggle): PAPER -> simulated
            # fills via PaperExecutor (no broker calls). LIVE -> real OANDA /
            # Capital.com orders. Either gate set to PAPER blocks live fills.
            effective_mode = self.config.effective_trading_mode()

            state = await self._circuit_breaker.check_and_transition()
            if state == CircuitBreakerState.OPEN:
                logger.error(
                    "circuit_breaker_open_order_rejected",
                    order_ref=str(order.order_ref),
                )
                return None
            # Final kill-switch recheck immediately before the broker call.
            # The top-of-method check has a window: kill could activate during
            # _circuit_breaker.check_and_transition() (which makes a DB call
            # and may sleep). Refreshing once more here closes that window
            # for live orders.
            if effective_mode == "LIVE" and self._state is not None:
                try:
                    if hasattr(self._state, "refresh_kill_switch_from_db"):
                        await self._state.refresh_kill_switch_from_db()
                    if getattr(self._state, "kill_switch_active", False):
                        logger.warning(
                            "execute_order_blocked_kill_switch_active_pre_broker",
                            order_ref=str(order.order_ref),
                            pair=order.pair,
                        )
                        return None
                except Exception:
                    logger.exception("execute_order_pre_broker_kill_check_failed")
                    # Pre-broker, LIVE mode: any cached active state blocks.
                    # Safer to miss one trade than fire a live order through a
                    # broken kill check. Codex+Claude audit 2026-04-30 — P2 fix.
                    if getattr(self._state, "kill_switch_active", False):
                        logger.warning(
                            "execute_order_blocked_kill_switch_cached_pre_broker",
                            order_ref=str(order.order_ref),
                            pair=order.pair,
                        )
                        return None

            try:
                pair_is_live_approved = order.pair in self.config.live_pairs
                # Shadow: pair scanned for telemetry but not eligible for live execution.
                # Stored as PAPER_SHADOW so position counts and daily_pnl stay clean.
                is_shadow = effective_mode == "LIVE" and not pair_is_live_approved
                if effective_mode == "PAPER" or is_shadow:
                    # Simulated fill — no broker call. Lands here when:
                    # - effective_mode is PAPER (either switch is PAPER), OR
                    # - pair is not in live_pairs (shadow-scan pairs like USD_JPY
                    #   always paper even when mode=LIVE, because their backtest
                    #   stats don't meet the live threshold).
                    logger.info(
                        "paper_mode_simulated_fill",
                        order_ref=str(order.order_ref),
                        pair=order.pair,
                        env_mode=self.config.trading_mode,
                        db_mode=self.config.db_mode_override,
                        reason="paper_mode" if effective_mode == "PAPER" else "pair_not_live_approved",
                    )
                    result = await self._paper_executor.execute(order, current_price)
                elif order.pair in self.CAPITAL_INSTRUMENTS and self._capital_executor:
                    # Live metals via Capital.com
                    result = await self._capital_executor.execute(order)
                else:
                    # Live forex via OANDA.
                    try:
                        result = await self._oanda_executor.execute(order)
                    except ExecutionError as _exec_err:
                        if "INSTRUMENT_NOT_TRADEABLE" in str(_exec_err):
                            # In LIVE mode this is a fatal configuration failure.
                            # Silently papering here would write a fake LIVE row to
                            # the DB — operators would see a "live" trade that never
                            # hit the broker. Hard-fail and page instead.
                            logger.critical(
                                "oanda_instrument_not_tradeable_live_mode",
                                pair=order.pair,
                                order_ref=str(order.order_ref),
                            )
                            await self._alerts.send_critical(
                                f"CRITICAL: {order.pair} is not tradeable on this OANDA account. "
                                "Enable CFD trading in OANDA account settings. Order skipped."
                            )
                            raise ExecutionError(
                                f"INSTRUMENT_NOT_TRADEABLE in LIVE mode for {order.pair}: "
                                "enable CFD trading in OANDA account settings"
                            ) from _exec_err
                        else:
                            raise
                await self._circuit_breaker.record_success()
            except Exception:
                await self._circuit_breaker.record_failure()
                raise

            machine.transition(OrderStatus.SUBMITTED)
            machine.transition(OrderStatus.ACKNOWLEDGED)
            machine.transition(OrderStatus.FILLED)

            verified = await self._fill_verifier.verify(order, result)
            await self._save_trade(order, verified, is_shadow=is_shadow)

            direction_str = order.direction.value if hasattr(order.direction, "value") else str(order.direction)
            if is_shadow:
                # Shadow fills: log only, no Slack/email alert. These are not
                # real broker positions and must not be confused with live exposure.
                logger.info(
                    "paper_shadow_fill_opened",
                    pair=order.pair,
                    direction=direction_str,
                    units=abs(order.units),
                    fill_price=str(verified.fill_price),
                )
            else:
                await self._alerts.send_info(
                    f"Trade opened: {order.pair} {direction_str} "
                    f"{abs(order.units)} units at {verified.fill_price}"
                )

            # Publish order event to Mission Control
            execution_mode_str = "PAPER_SHADOW" if is_shadow else (
                order.mode.value if hasattr(order.mode, "value") else str(order.mode)
            )
            if self._events:
                self._events.publish(
                    "EXECUTION",
                    "ORDER",
                    f"{'SHADOW ' if is_shadow else ''}ORDER PLACED: {direction_str} {abs(order.units)} {order.pair} @ {verified.fill_price}",
                    severity="INFO" if is_shadow else "SUCCESS",
                    pair=order.pair,
                    metadata={
                        "direction": direction_str,
                        "units": abs(order.units),
                        "fill_price": str(verified.fill_price),
                        "stop_loss": str(order.stop_loss),
                        "take_profit": str(order.take_profit),
                        "slippage_pips": str(verified.slippage_pips),
                        "mode": execution_mode_str,
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

    async def _save_trade(self, order: ApprovedOrder, result: OrderResult, *, is_shadow: bool = False) -> None:
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

        # Shadow trades are stored with mode=PAPER_SHADOW so position-count
        # queries and daily_pnl can exclude them from the live book.
        stored_mode = "PAPER_SHADOW" if is_shadow else (
            order.mode.value if hasattr(order.mode, "value") else str(order.mode)
        )

        # Persist the original SL at open so the trailing-stop logic can
        # compute trail distance from a fixed value, not the current SL
        # (which collapses to entry after breakeven). Migration 016 added
        # the `initial_stop_loss` column. If the column is not present in
        # the deployed schema yet, retry without it so the trade row still
        # saves and the dashboard can show the position. Trailing-stop
        # logic already has a legacy-row fallback for this case
        # (test_trailing_stop_breakeven.py:113-123 covers no-initial-SL).
        trade_row = {
            "account_id": self.config.account_uuid,
            "signal_id": str(order.signal_id),
            "broker_trade_id": result.broker_trade_id,
            "pair": order.pair,
            "direction": (
                order.direction.value
                if hasattr(order.direction, "value")
                else str(order.direction)
            ),
            "mode": stored_mode,
            "entry_price": str(result.fill_price),
            "stop_loss": str(order.stop_loss),
            "initial_stop_loss": str(order.stop_loss),
            "take_profit": str(order.take_profit),
            "position_size": str(abs(order.units)),
            "confidence_score": str(order.confidence),
            "slippage_pips": str(result.slippage_pips),
            "status": "OPEN",
            "session": session_label_for_lesson(),
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await self._db.insert("trades", trade_row)
        except Exception as e:
            err_str = str(e)
            # PostgREST PGRST204 — column missing from schema cache.
            # Strip the post-016 columns and retry once before giving up.
            if "initial_stop_loss" in err_str or "PGRST204" in err_str:
                logger.warning(
                    "trade_save_schema_fallback",
                    detail="initial_stop_loss column missing; "
                    "saving without it (migration 016 not applied)",
                )
                trade_row.pop("initial_stop_loss", None)
                try:
                    await self._db.insert("trades", trade_row)
                except Exception as retry_e:
                    logger.error(
                        "trade_save_failed_after_fallback",
                        error=str(retry_e),
                    )
                    if not is_shadow:
                        await self._alerts.send_critical(
                            f"CRITICAL: Live trade {order.pair} broker_id={result.broker_trade_id} "
                            f"NOT SAVED to DB after fallback — manual OANDA reconciliation required. "
                            f"Error: {retry_e}"
                        )
            else:
                logger.error("trade_save_failed", error=err_str)
                if not is_shadow:
                    await self._alerts.send_critical(
                        f"CRITICAL: Live trade {order.pair} broker_id={result.broker_trade_id} "
                        f"NOT SAVED to DB — manual OANDA reconciliation required. "
                        f"Error: {err_str}"
                    )

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
                oanda_trades = await self._oanda_read.get_all_open_trades()
                oanda_open_ids = {t["id"] for t in oanda_trades}
            except Exception as e:
                logger.warning("position_monitor_oanda_error", error=str(e))
                return  # Can't check — skip this cycle

        for trade in db_open:
            broker_id = trade.get("broker_trade_id", "")

            # Max hold time: per-pair (USD_CAD allows longer holds — its edge
            # runs in trades >24h per backtest_2026Q2_results.md ablation).
            opened_at = trade.get("opened_at", "")
            pair = trade.get("pair", "")
            max_hold = self.config.max_hold_hours_for(pair)
            if opened_at and broker_id and not broker_id.startswith("PAPER-"):
                try:
                    from datetime import datetime as _dt
                    open_time = _dt.fromisoformat(opened_at.replace("Z", "+00:00"))
                    age_hours = (datetime.now(timezone.utc) - open_time).total_seconds() / 3600
                    if age_hours >= max_hold:
                        # Only attempt close during market hours (Sun 22:00 - Fri 22:00 UTC)
                        now = datetime.now(timezone.utc)
                        weekday = now.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
                        hour = now.hour
                        market_open = not (
                            (weekday == 5) or  # All Saturday
                            (weekday == 6 and hour < 22) or  # Sunday before 22:00
                            (weekday == 4 and hour >= 22)  # Friday after 22:00
                        )
                        if not market_open:
                            # Log once per hour instead of every 60 seconds
                            if age_hours % 1 < 0.02:  # roughly once per hour
                                logger.info("max_hold_market_closed", pair=trade.get("pair", ""), broker_id=broker_id)
                            continue

                        logger.warning(
                            "max_hold_closing",
                            pair=trade.get("pair", ""),
                            broker_id=broker_id,
                            age_hours=round(age_hours, 1),
                        )
                        try:
                            await self._oanda_trade.close_trade(broker_id, pair=pair)
                            await self._circuit_breaker.record_success()
                            if self._events:
                                self._events.publish(
                                    "EXECUTION", "MAX_HOLD_CLOSE",
                                    f"Auto-closed {pair} after {age_hours:.1f}h (max {max_hold}h)",
                                    pair=pair, severity="WARNING",
                                )
                        except Exception as e:
                            await self._circuit_breaker.record_failure()
                            logger.error("max_hold_close_failed", broker_id=broker_id, error=str(e))
                        continue
                except (ValueError, TypeError):
                    pass

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

        # ── Partial scale-out (paper mode) ───────────────────────────────
        if (self.config.partial_close_enabled
                and not trade.get("partial_closed")
                and trade.get("initial_stop_loss")):
            fired = await self._try_paper_partial_close(trade, current_price, entry, direction)
            if fired:
                return  # SL/TP re-evaluated on next monitor cycle

        hit_sl = False
        hit_tp = False

        if direction == "BUY":
            hit_sl = current_price <= sl
            hit_tp = tp != Decimal("0") and current_price >= tp
        else:  # SELL
            hit_sl = current_price >= sl
            hit_tp = tp != Decimal("0") and current_price <= tp

        if hit_sl or hit_tp:
            exit_price = sl if hit_sl else tp
            pnl_pips = pips_between(entry, exit_price, pair)
            if direction == "SELL":
                pnl_pips = -pnl_pips if hit_sl else pnl_pips
            elif hit_sl:
                pnl_pips = -abs(pnl_pips)

            units = Decimal(str(trade.get("position_size", 0)))
            pv = pip_value_per_unit(pair, exit_price)
            pnl_usd = pnl_pips * units * pv

            outcome = "WIN" if pnl_usd > 0 else "LOSS"
            exit_reason = "TP_HIT" if hit_tp else "SL_HIT"

            await self._update_closed_trade(
                trade, exit_price, pnl_pips, pnl_usd, outcome, exit_reason
            )

    async def _try_paper_partial_close(
        self,
        trade: dict,
        current_price: Decimal,
        entry: Decimal,
        direction: str,
    ) -> bool:
        """Fire partial scale-out for a paper trade if price has reached the target.
        Reduces position_size, moves SL to entry (breakeven), marks partial_closed=True.
        Returns True if partial close executed, False otherwise."""
        from decimal import ROUND_DOWN

        initial_sl = Decimal(str(trade.get("initial_stop_loss", "0")))
        if initial_sl == 0 or entry == 0:
            return False

        initial_sl_dist = abs(entry - initial_sl)
        if initial_sl_dist == 0:
            return False

        rr = self.config.partial_close_rr_trigger
        target = (entry + initial_sl_dist * rr) if direction == "BUY" else (entry - initial_sl_dist * rr)

        reached = (current_price >= target) if direction == "BUY" else (current_price <= target)
        if not reached:
            return False

        pair = trade.get("pair", "")
        position_size = Decimal(str(trade.get("position_size", "0")))
        pc_pct = self.config.partial_close_pct

        if pair in _FRACTIONAL_UNIT_PAIRS:
            pc_units = (position_size * pc_pct).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            min_remain = Decimal("0.01")
        else:
            pc_units = Decimal(int(position_size * pc_pct))
            min_remain = Decimal("1")

        remaining = position_size - pc_units
        if pc_units <= 0 or remaining < min_remain:
            logger.info(
                "partial_close_skipped_min_units",
                pair=pair,
                position_size=str(position_size),
                pc_units=str(pc_units),
                remaining=str(remaining),
            )
            return False

        try:
            await self._db.update(
                "trades",
                {"id": trade.get("id")},
                {
                    "partial_closed": True,
                    "partial_close_price": str(current_price),
                    "partial_close_units": str(pc_units),
                    "position_size": str(remaining),
                    "stop_loss": str(entry),   # move to breakeven
                },
            )
            logger.info(
                "paper_partial_close_executed",
                pair=pair,
                direction=direction,
                pc_units=str(pc_units),
                remaining_units=str(remaining),
                close_price=str(current_price),
                target=str(target),
            )
            if self._events:
                self._events.publish(
                    "EXECUTION", "PARTIAL_CLOSE",
                    f"PARTIAL CLOSE: {pair} {direction} closed {pc_units} units @ {current_price} (BE locked)",
                    pair=pair, severity="SUCCESS",
                    metadata={
                        "pc_units": str(pc_units),
                        "remaining": str(remaining),
                        "close_price": str(current_price),
                        "rr_trigger": str(rr),
                    },
                )
            return True
        except Exception as e:
            logger.warning("paper_partial_close_db_error", pair=pair, error=str(e))
            return False

    # ── Trailing Stop Loss ──────────────────────────────────────
    # Trail distance = original SL distance (entry to SL).
    # Activation threshold varies by instrument volatility.
    # Trail: once activated, move SL to lock in (current_price - trail_distance).
    # Never move SL backwards — only forward in the direction of profit.
    TRAIL_ACTIVATION_PIPS: dict[str, Decimal] = {
        # Tuned from trade data — tighter for pairs with smaller moves
        "EUR_USD": Decimal("18"),
        "GBP_USD": Decimal("25"),     # GBP is more volatile
        "AUD_USD": Decimal("15"),     # AUD moves less — activate earlier
        "NZD_USD": Decimal("15"),     # NZD similar to AUD
        "USD_CAD": Decimal("18"),
        "USD_CHF": Decimal("18"),
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

        # Filter to trades with valid REAL broker IDs. PAPER- prefixed IDs are
        # simulated fills (PaperExecutor) and must NOT trigger any OANDA
        # mutation calls — modify_trade() against PAPER-* would 404, waste API
        # calls, pollute logs, and potentially trip the circuit breaker.
        trailable = [
            t for t in db_open
            if t.get("broker_trade_id", "").strip()
            and not t.get("broker_trade_id", "").startswith("PAPER-")
        ]
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

            try:
                await self._oanda_trade.modify_trade(broker_id, be_sl, tp, pair=pair)
                await self._circuit_breaker.record_success()
            except Exception as _be_err:
                await self._circuit_breaker.record_failure()
                logger.error("breakeven_stop_modify_failed", broker_id=broker_id, error=str(_be_err))
                return
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

        # Trail distance = ORIGINAL SL distance from entry. Computing this
        # from current_sl is broken: after breakeven moves SL to entry,
        # abs(entry - current_sl) collapses to zero and the next cycle moves
        # SL onto the current price — exiting a winner on noise. Use the
        # persisted initial_stop_loss from trade open. Fall back to
        # current_sl only when initial is missing (legacy rows pre-migration
        # 016 with no backfill).
        initial_sl_raw = trade.get("initial_stop_loss")
        if initial_sl_raw is not None and str(initial_sl_raw).strip():
            initial_sl = Decimal(str(initial_sl_raw))
        else:
            initial_sl = current_sl
        original_sl_distance = abs(entry - initial_sl)
        if original_sl_distance == 0:
            # Defensive: if initial_sl == entry (degenerate trade or backfill
            # error), do not trail — would set SL onto the market price.
            logger.warning(
                "trailing_stop_skipped_zero_initial_distance",
                pair=pair, broker_id=broker_id,
                entry=str(entry), initial_sl=str(initial_sl),
            )
            return

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

        # Guard: never set SL past TP — OANDA rejects and the trade is likely
        # already at or past TP (should be closed by _check_closed_positions).
        if tp and tp > Decimal("0"):
            if direction == "BUY" and new_sl >= tp:
                logger.warning(
                    "trailing_stop_skipped_sl_past_tp",
                    pair=pair, broker_id=broker_id,
                    new_sl=str(new_sl), tp=str(tp), current_price=str(current_price),
                )
                return
            if direction == "SELL" and new_sl <= tp:
                logger.warning(
                    "trailing_stop_skipped_sl_past_tp",
                    pair=pair, broker_id=broker_id,
                    new_sl=str(new_sl), tp=str(tp), current_price=str(current_price),
                )
                return

        # Update SL on OANDA
        try:
            await self._oanda_trade.modify_trade(broker_id, new_sl, tp, pair=pair)
            await self._circuit_breaker.record_success()
        except Exception as _trail_err:
            await self._circuit_breaker.record_failure()
            logger.error("trailing_stop_modify_failed", broker_id=broker_id, error=str(_trail_err))
            return

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
                oanda_trade = await self._oanda_read.get_trade(broker_id, pair=pair)
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

                # Check SL/TP by comparing exit price to expected levels
                sl = Decimal(str(trade.get("stop_loss", "0")))
                tp = Decimal(str(trade.get("take_profit", "0")))
                sl_dist = abs(exit_price - sl)
                tp_dist = abs(exit_price - tp)
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
            units = Decimal(str(trade.get("position_size", 0)))
            pv = pip_value_per_unit(pair, exit_price)
            realized_pnl = pnl_pips * units * pv

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

        # Compute duration_minutes from opened_at so every closed trade has
        # a complete audit trail (required by lesson_analyzer and SA-02).
        duration_minutes = None
        opened_at_raw = trade.get("opened_at")
        if opened_at_raw:
            try:
                opened_dt = (
                    datetime.fromisoformat(opened_at_raw.replace("Z", "+00:00"))
                    if isinstance(opened_at_raw, str)
                    else opened_at_raw
                )
                duration_minutes = int((now - opened_dt).total_seconds() // 60)
            except Exception:
                duration_minutes = None

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
                    "duration_minutes": duration_minutes,
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

            # Update state — skip shadow trades so simulated P&L doesn't
            # affect daily_pnl limits or consecutive_loss counts on the live book.
            trade_mode = trade.get("mode", "")
            if self._state and trade_mode != "PAPER_SHADOW":
                state = self._state
                if outcome == "LOSS":
                    current = state._state.get("consecutive_losses", 0)
                    state._state["consecutive_losses"] = current + 1
                elif outcome == "WIN":
                    state._state["consecutive_losses"] = 0

                daily_pnl = Decimal(str(state._state.get("daily_pnl", "0")))
                state._state["daily_pnl"] = str(daily_pnl + pnl_usd)

                weekly_pnl = Decimal(str(state._state.get("weekly_pnl", "0")))
                state._state["weekly_pnl"] = str(weekly_pnl + pnl_usd)

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

        # Update trading memory — extract patterns and create/update BLOCK/BOOST rules
        try:
            signal_row = await self._db.select_one(
                "signals", {"id": trade.get("signal_id", "")}
            )
            indicators = (signal_row or {}).get("indicators_snapshot") or {}
            rules = await self._lesson_analyzer.analyze_trade(trade, indicators)
            if rules:
                logger.info(
                    "lesson_analysis_post_trade",
                    trade_id=trade.get("id", ""),
                    rules_updated=len(rules),
                )
        except Exception as e:
            logger.warning("lesson_analysis_failed", error=str(e))

        await self._trigger_insight_analysis(trade)

    async def _trigger_insight_analysis(self, trade: dict) -> None:
        min_trades = 50
        every_n = 10
        try:
            # Account-scoped count — without this filter, another tenant's
            # closed trades would spuriously trigger or suppress this
            # account's analysis cadence.
            count = await self._db.count(
                "trades",
                {"status": "CLOSED", "account_id": self.config.account_uuid},
            )
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

    async def close_all_positions(self, reason: str) -> dict:
        """
        Emergency close-out of every open OANDA position. Implements PRD:579
        kill-switch contract: "closes all positions at market".

        Background: kill_switch previously only suppressed scanning; existing
        positions stayed live and unmanaged through disorderly markets. This
        method is the missing close-out.

        Behavior:
          - PAPER mode: no-op (no live broker positions to close).
          - LIVE mode: fetch open trades from OANDA via the trading client,
            close each via close_trade(), record the result, and emit a
            CRITICAL severity event.
          - Failures on individual closes are logged but do NOT stop the
            sweep — best-effort close-as-many-as-possible.

        Returns: {"attempted": N, "closed": N, "failed": [...broker_trade_ids]}
        """
        # In PAPER, the trading_client is the OANDA practice client but the
        # ExecutionEngine never opens real positions on it — close-all is a
        # no-op for safety.
        if self.config.effective_trading_mode() != TradingMode.LIVE.value:
            logger.info("kill_switch_close_all_skipped_not_live", reason=reason)
            return {"attempted": 0, "closed": 0, "failed": []}

        attempted = 0
        closed = 0
        failed: list[str] = []

        # Sweep both brokers (OANDA forex + Capital.com metals). The original
        # sweep only hit OANDA, leaving any live XAU_USD position on
        # Capital.com unmanaged after kill.
        broker_clients: list[tuple[str, object]] = [("oanda", self._oanda_trade)]
        if self._capital_client is not None:
            broker_clients.append(("capital", self._capital_client))

        for broker_name, broker_client in broker_clients:
            try:
                # OANDA: get_all_open_trades merges main + spot crypto sub-account.
                # Other brokers (Capital.com) only have get_open_trades.
                if broker_name == "oanda":
                    open_trades = await broker_client.get_all_open_trades()  # type: ignore[attr-defined]
                else:
                    open_trades = await broker_client.get_open_trades()  # type: ignore[attr-defined]
            except Exception as e:
                logger.error(
                    "kill_switch_get_open_trades_failed",
                    broker=broker_name,
                    error=str(e),
                    reason=reason,
                )
                failed.append(f"{broker_name}:fetch_failed")
                continue

            logger.critical(
                "kill_switch_close_all_initiated",
                broker=broker_name,
                reason=reason,
                open_trade_count=len(open_trades),
            )

            for trade in open_trades:
                broker_trade_id = str(trade.get("id", "") or trade.get("dealId", ""))
                if not broker_trade_id:
                    continue
                attempted += 1
                _kill_pair = trade.get("instrument", "") or trade.get("epic", "") or ""
                try:
                    if broker_name == "oanda":
                        await broker_client.close_trade(broker_trade_id, pair=_kill_pair)  # type: ignore[attr-defined]
                    else:
                        await broker_client.close_trade(broker_trade_id)  # type: ignore[attr-defined]
                    if broker_name == "oanda":
                        await self._circuit_breaker.record_success()
                    closed += 1
                    logger.warning(
                        "kill_switch_position_closed",
                        broker=broker_name,
                        broker_trade_id=broker_trade_id,
                        instrument=trade.get("instrument") or trade.get("epic"),
                        units=trade.get("currentUnits") or trade.get("size"),
                        reason=reason,
                    )
                except Exception as e:
                    if broker_name == "oanda":
                        await self._circuit_breaker.record_failure()
                    failed.append(f"{broker_name}:{broker_trade_id}")
                    logger.error(
                        "kill_switch_close_failed",
                        broker=broker_name,
                        broker_trade_id=broker_trade_id,
                        instrument=trade.get("instrument") or trade.get("epic"),
                        error=str(e),
                        reason=reason,
                    )

        if any(f.endswith(":fetch_failed") for f in failed):
            await self._alerts.send_critical(
                f"KILL SWITCH: one or more brokers failed get_open_trades — "
                f"{[f for f in failed if f.endswith(':fetch_failed')]}. "
                f"Manual intervention required."
            )

        await self._alerts.send_critical(
            f"KILL SWITCH ACTIVATED ({reason}): closed {closed}/{attempted} "
            f"positions. Failed: {len(failed)}."
        )
        if self._events:
            try:
                self._events.publish(
                    "EXECUTION",
                    "KILL_SWITCH",
                    f"KILL SWITCH: closed {closed}/{attempted} positions ({reason})",
                    severity="CRITICAL",
                    metadata={
                        "reason": reason,
                        "attempted": attempted,
                        "closed": closed,
                        "failed_ids": failed,
                    },
                )
            except Exception:
                # Mission Control publish failure must NEVER propagate
                # (observability is not critical path), but the kill-switch
                # forensic trail must survive in the structured log so we
                # can reconstruct what happened post-mortem.
                logger.exception(
                    "kill_switch_audit_log_failed",
                    reason=reason,
                    attempted=attempted,
                    closed=closed,
                    failed=failed,
                )

        return {"attempted": attempted, "closed": closed, "failed": failed}
