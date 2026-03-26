"""
Lumitrade Execution Engine
============================
Orchestrates order execution, fill verification, and position management.
Routes to paper or OANDA executor based on TradingMode.
Per BDS Section 7 and SAS Section 3.2.5.
"""
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
    ):
        self.config = config
        self._state = state_manager
        self._db = db
        self._alerts = alert_service
        self._subagents = subagents
        self._oanda_read = oanda_read_client
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
                f"Trade opened: {order.pair} {order.direction.value} "
                f"{abs(order.units)} units at {verified.fill_price}"
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
        try:
            await self._db.insert(
                "trades",
                {
                    "account_id": self.config.account_uuid,
                    "signal_id": str(order.signal_id),
                    "broker_trade_id": result.broker_trade_id,
                    "pair": order.pair,
                    "direction": order.direction.value,
                    "mode": order.mode.value,
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
        """Monitor open positions — detect closes (SL/TP hit) and update DB."""
        logger.info("position_monitor_started")
        try:
            while True:
                await asyncio.sleep(POSITION_MONITOR_INTERVAL)
                try:
                    await self._check_closed_positions()
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
            # Rough P&L: pips * units * pip_value (simplified)
            pip_size = Decimal("0.01") if "JPY" in pair else Decimal("0.0001")
            pnl_usd = pnl_pips * Decimal(str(units)) * pip_size

            outcome = "WIN" if pnl_usd > 0 else "LOSS"
            exit_reason = "TAKE_PROFIT" if hit_tp else "STOP_LOSS"

            await self._update_closed_trade(
                trade, exit_price, pnl_pips, pnl_usd, outcome, exit_reason
            )

    async def _mark_trade_closed(self, trade: dict) -> None:
        """Mark a live trade as closed — fetch final details from context."""
        entry = Decimal(str(trade.get("entry_price", "0")))
        pair = trade.get("pair", "")
        # Without OANDA trade history API, we mark as closed with unknown P&L
        await self._update_closed_trade(
            trade, entry, Decimal("0"), Decimal("0"), "BREAKEVEN", "UNKNOWN"
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

        except Exception as e:
            logger.error("trade_close_update_failed", trade_id=trade_id, error=str(e))

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
