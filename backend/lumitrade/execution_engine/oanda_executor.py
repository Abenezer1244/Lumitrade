"""
Lumitrade OANDA Executor
==========================
Places real orders via OandaTradingClient. Idempotent via order_ref.
Per BDS Section 7.
"""
from datetime import datetime, timezone
from decimal import Decimal

from ..core.enums import OrderStatus
from ..core.exceptions import ExecutionError
from ..core.models import ApprovedOrder, OrderResult
from ..infrastructure.oanda_client import OandaTradingClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)
FILL_VERIFY_TIMEOUT_SEC = 2


class OandaExecutor:
    def __init__(self, trading_client: OandaTradingClient):
        self._client = trading_client

    async def execute(self, order: ApprovedOrder) -> OrderResult:
        client_request_id = str(order.order_ref)
        try:
            response = await self._client.place_market_order(
                pair=order.pair,
                units=order.units,
                sl=order.stop_loss,
                tp=order.take_profit,
                client_request_id=client_request_id,
            )
            return self._parse_response(order, response)
        except Exception as e:
            logger.error(
                "oanda_order_failed",
                error=str(e),
                order_ref=str(order.order_ref),
            )
            raise ExecutionError(f"Order placement failed: {e}") from e

    def _parse_response(self, order: ApprovedOrder, response: dict) -> OrderResult:
        order_fill = response.get("orderFillTransaction", {})
        trade_id = ""
        if order_fill:
            # Primary: new trade opened
            trade_opened = order_fill.get("tradeOpened", {})
            if trade_opened:
                trade_id = trade_opened.get("tradeID", "")
            # Fallback: trade reduced (adding to existing position)
            if not trade_id:
                trades_reduced = order_fill.get("tradeReduced", {})
                if trades_reduced:
                    trade_id = trades_reduced.get("tradeID", "")
            # Last resort: use the fill transaction ID itself
            if not trade_id:
                trade_id = str(order_fill.get("id", ""))
        logger.info(
            "oanda_response_parsed",
            order_ref=str(order.order_ref),
            broker_trade_id=trade_id,
            has_fill=bool(order_fill),
            response_keys=list(response.keys()),
            fill_keys=list(order_fill.keys()) if order_fill else [],
        )
        order_create = response.get("orderCreateTransaction", {})
        order_id = order_create.get("id", order_fill.get("id", ""))
        fill_price = Decimal(str(order_fill.get("price", order.entry_price)))
        fill_units = int(order_fill.get("units", abs(order.units)))
        from ..utils.pip_math import pips_between
        slippage = pips_between(order.entry_price, fill_price, order.pair)

        return OrderResult(
            order_ref=order.order_ref,
            broker_order_id=str(order_id),
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
