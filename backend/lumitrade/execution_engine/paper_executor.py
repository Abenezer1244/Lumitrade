"""
Lumitrade Paper Executor
==========================
Simulates trade execution using real market prices. Mode=PAPER.
NEVER calls OandaTradingClient. Per BDS Section 5.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ..core.enums import OrderStatus
from ..core.models import ApprovedOrder, OrderResult
from ..infrastructure.secure_logger import get_logger
from ..utils.pip_math import pip_size, pips_between

logger = get_logger(__name__)


class PaperExecutor:
    async def execute(
        self, order: ApprovedOrder, current_price: Decimal,
    ) -> OrderResult:
        # Simulate realistic fill: current_price is the bid.
        # BUY orders execute at ask (bid + ~1 pip spread).
        # SELL orders execute at bid (current_price as-is).
        direction_str = order.direction.value if hasattr(order.direction, "value") else str(order.direction)
        ps = pip_size(order.pair)
        fill_price = current_price + ps if direction_str == "BUY" else current_price
        slippage = pips_between(order.entry_price, fill_price, order.pair)
        logger.info(
            "paper_trade_executed",
            pair=order.pair,
            direction=order.direction.value,
            units=order.units,
            fill_price=str(fill_price),
        )
        return OrderResult(
            order_ref=order.order_ref,
            broker_order_id=f"PAPER-{uuid4().hex[:12]}",
            broker_trade_id=f"PAPER-{uuid4().hex[:12]}",
            status=OrderStatus.FILLED,
            fill_price=fill_price,
            fill_units=abs(order.units),
            fill_timestamp=datetime.now(timezone.utc),
            stop_loss_confirmed=order.stop_loss,
            take_profit_confirmed=order.take_profit,
            slippage_pips=slippage,
            raw_response={"mode": "PAPER", "simulated": True},
        )
