"""
Lumitrade Capital.com Executor
================================
Places orders via Capital.com REST API. Used for instruments
not available on OANDA (e.g., XAU/USD gold).
Mirrors OandaExecutor interface.
"""
from datetime import datetime, timezone
from decimal import Decimal

from ..core.enums import OrderStatus
from ..core.exceptions import ExecutionError
from ..core.models import ApprovedOrder, OrderResult
from ..infrastructure.capital_client import CapitalComClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class CapitalExecutor:
    def __init__(self, capital_client: CapitalComClient):
        self._client = capital_client

    async def execute(self, order: ApprovedOrder) -> OrderResult:
        direction_str = order.direction.value if hasattr(order.direction, "value") else str(order.direction)
        units = -abs(order.units) if direction_str == "SELL" else abs(order.units)
        try:
            response = await self._client.place_market_order(
                pair=order.pair,
                units=units,
                sl=order.stop_loss,
                tp=order.take_profit,
                client_request_id=str(order.order_ref),
            )
            return self._parse_response(order, response)
        except Exception as e:
            logger.error(
                "capital_order_failed",
                error=str(e),
                order_ref=str(order.order_ref),
            )
            raise ExecutionError(f"Capital.com order failed: {e}") from e

    def _parse_response(self, order: ApprovedOrder, response: dict) -> OrderResult:
        order_fill = response.get("orderFillTransaction", {})
        order_cancel = response.get("orderCancelTransaction", {})

        # Check for rejection
        cancel_reason = order_cancel.get("reason", "") if order_cancel else ""
        if cancel_reason:
            raise ExecutionError(
                f"Capital.com rejected order for {order.pair}: {cancel_reason}"
            )

        if not order_fill:
            raise ExecutionError(
                f"Capital.com returned no fill for {order.pair}. Keys: {list(response.keys())}"
            )

        trade_opened = order_fill.get("tradeOpened", {})
        trade_id = trade_opened.get("tradeID", "")
        if not trade_id:
            trade_id = str(order_fill.get("id", ""))

        fill_price = Decimal(str(order_fill.get("price", order.entry_price)))
        fill_units = int(order_fill.get("units", abs(order.units)))

        from ..utils.pip_math import pips_between
        slippage = pips_between(order.entry_price, fill_price, order.pair)

        logger.info(
            "capital_order_filled",
            order_ref=str(order.order_ref),
            broker_trade_id=trade_id,
            fill_price=str(fill_price),
            pair=order.pair,
        )

        return OrderResult(
            order_ref=order.order_ref,
            broker_order_id=str(order_fill.get("id", "")),
            broker_trade_id=str(trade_id),
            status=OrderStatus.FILLED,
            fill_price=fill_price,
            fill_units=abs(fill_units),
            fill_timestamp=datetime.now(timezone.utc),
            stop_loss_confirmed=order.stop_loss,
            take_profit_confirmed=order.take_profit,
            slippage_pips=slippage,
            raw_response=response,
        )
