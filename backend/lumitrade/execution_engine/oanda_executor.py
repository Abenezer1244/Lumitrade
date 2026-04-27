"""
Lumitrade OANDA Executor
==========================
Places real orders via OandaTradingClient. Idempotent via order_ref.
Per BDS Section 7 + QTS Section 765 (idempotent recovery on timeout).
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from ..core.enums import OrderStatus
from ..core.exceptions import ExecutionError
from ..core.models import ApprovedOrder, OrderResult
from ..infrastructure.oanda_client import OandaTradingClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)
FILL_VERIFY_TIMEOUT_SEC = 2

# Time to wait before lookup_order_status to give OANDA a chance to commit
# the order to durable storage before we query for it.
RECOVERY_LOOKUP_DELAY_SEC = 2.0


class OandaExecutor:
    def __init__(self, trading_client: OandaTradingClient):
        self._client = trading_client

    async def execute(self, order: ApprovedOrder) -> OrderResult:
        client_request_id = str(order.order_ref)
        # OANDA uses negative units for SELL orders
        direction_str = order.direction.value if hasattr(order.direction, "value") else str(order.direction)
        units = -abs(order.units) if direction_str == "SELL" else abs(order.units)
        try:
            response = await self._client.place_market_order(
                pair=order.pair,
                units=units,
                sl=order.stop_loss,
                tp=order.take_profit,
                client_request_id=client_request_id,
            )
            return self._parse_response(order, response)
        except Exception as e:
            # Codex 2026-04-25 audit finding [critical] #3: place_market_order
            # may have raised AFTER OANDA committed the order. Without an
            # idempotent status lookup, a restart-and-rescan creates a duplicate
            # live position. Try to recover via client_request_id before
            # declaring failure.
            logger.warning(
                "oanda_order_attempt_error_attempting_recovery",
                error=str(e),
                order_ref=str(order.order_ref),
                pair=order.pair,
            )
            try:
                await asyncio.sleep(RECOVERY_LOOKUP_DELAY_SEC)
                recovered = await self._client.lookup_order_status(client_request_id)
            except Exception as lookup_err:
                logger.error(
                    "oanda_order_recovery_lookup_failed",
                    error=str(lookup_err),
                    order_ref=str(order.order_ref),
                )
                recovered = None

            if recovered is not None:
                logger.warning(
                    "oanda_order_recovered_via_client_id",
                    order_ref=str(order.order_ref),
                    pair=order.pair,
                    has_fill=bool(recovered.get("orderFillTransaction")),
                    has_cancel=bool(recovered.get("orderCancelTransaction")),
                )
                # _parse_response handles both FILLED and CANCELLED branches —
                # it raises ExecutionError on cancellation, otherwise returns
                # an OrderResult exactly as if the original POST had succeeded.
                return self._parse_response(order, recovered)

            # No recovery — order either never reached OANDA or is still
            # in-flight. Failing closed is the only safe choice; reconciler
            # will sweep up any orphaned trade on the next cycle.
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
        # Log cancel reason if order was rejected
        order_cancel = response.get("orderCancelTransaction", {})
        cancel_reason = order_cancel.get("reason", "") if order_cancel else ""
        if cancel_reason:
            logger.warning(
                "oanda_order_cancelled",
                order_ref=str(order.order_ref),
                reason=cancel_reason,
                reject_reason=order_cancel.get("rejectReason", ""),
            )

        logger.info(
            "oanda_response_parsed",
            order_ref=str(order.order_ref),
            broker_trade_id=trade_id,
            has_fill=bool(order_fill),
            cancel_reason=cancel_reason,
            response_keys=list(response.keys()),
            fill_keys=list(order_fill.keys()) if order_fill else [],
        )
        # If OANDA cancelled the order (e.g. TP within spread), treat as rejected
        if cancel_reason:
            logger.error(
                "oanda_order_rejected",
                order_ref=str(order.order_ref),
                pair=order.pair,
                reason=cancel_reason,
            )
            raise ExecutionError(
                f"OANDA rejected order for {order.pair}: {cancel_reason}"
            )

        # If no fill transaction at all, treat as failed
        if not order_fill:
            logger.error(
                "oanda_order_no_fill",
                order_ref=str(order.order_ref),
                pair=order.pair,
                response_keys=list(response.keys()),
            )
            raise ExecutionError(
                f"OANDA returned no orderFillTransaction for {order.pair}. Keys: {list(response.keys())}"
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
