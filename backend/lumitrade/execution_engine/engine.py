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
from ..infrastructure.oanda_client import OandaTradingClient
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
    ):
        self.config = config
        self._state = state_manager
        self._db = db
        self._alerts = alert_service
        self._subagents = subagents
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

        mode = TradingMode(self.config.trading_mode)
        try:
            if mode == TradingMode.PAPER:
                result = await self._paper_executor.execute(order, current_price)
            else:
                state = await self._circuit_breaker.check_and_transition()
                if state == state.OPEN:
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
                    "account_id": self.config.oanda_account_id,
                    "signal_id": str(order.signal_id),
                    "broker_trade_id": result.broker_trade_id,
                    "pair": order.pair,
                    "direction": order.direction.value,
                    "mode": order.mode.value,
                    "entry_price": str(result.fill_price),
                    "stop_loss": str(order.stop_loss),
                    "take_profit": str(order.take_profit),
                    "position_size": abs(order.units),
                    "confidence_score": str(order.risk_pct),
                    "slippage_pips": str(result.slippage_pips),
                    "status": "OPEN",
                    "session": "",
                    "opened_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            logger.error("trade_save_failed", error=str(e))

    async def position_monitor(self) -> None:
        logger.info("position_monitor_started")
        try:
            while True:
                await asyncio.sleep(POSITION_MONITOR_INTERVAL)
                logger.debug("position_monitor_tick")
        except asyncio.CancelledError:
            logger.info("position_monitor_cancelled")

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
