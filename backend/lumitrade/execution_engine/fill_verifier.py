"""
Lumitrade Fill Verifier
=========================
Verifies every order fill meets expectations. Alerts on anomalies.
Per BDS Section 7.2.
"""
from dataclasses import replace
from decimal import Decimal

from ..core.enums import OrderStatus
from ..core.models import ApprovedOrder, OrderResult
from ..infrastructure.alert_service import AlertService
from ..infrastructure.secure_logger import get_logger
from ..utils.pip_math import pips_between

logger = get_logger(__name__)
HIGH_SLIPPAGE_THRESHOLD_PIPS = Decimal("3.0")


class FillVerifier:
    def __init__(self, alert_service: AlertService):
        self.alerts = alert_service

    async def verify(self, order: ApprovedOrder, result: OrderResult) -> OrderResult:
        if result.status != OrderStatus.FILLED:
            logger.warning(
                "fill_not_complete",
                status=result.status.value,
                order_ref=str(order.order_ref),
            )
            return result

        slippage = pips_between(order.entry_price, result.fill_price, order.pair)
        if slippage > HIGH_SLIPPAGE_THRESHOLD_PIPS:
            msg = (
                f"HIGH SLIPPAGE: {slippage:.1f} pips on {order.pair} "
                f"(intended {order.entry_price}, filled {result.fill_price})"
            )
            # Extreme slippage (>10 pips) escalates to CRITICAL
            if slippage > Decimal("10.0"):
                logger.critical(
                    "extreme_slippage_detected",
                    slippage_pips=str(slippage),
                    pair=order.pair,
                    order_ref=str(order.order_ref),
                )
                await self.alerts.send_critical(f"EXTREME {msg}")
            else:
                logger.warning(
                    "high_slippage_detected",
                    slippage_pips=str(slippage),
                    pair=order.pair,
                )
                await self.alerts.send_warning(msg)

        if result.fill_units != abs(order.units):
            logger.warning(
                "partial_fill_detected",
                expected=abs(order.units),
                actual=result.fill_units,
            )

        if not result.stop_loss_confirmed or not result.take_profit_confirmed:
            logger.error(
                "sl_tp_not_confirmed",
                order_ref=str(order.order_ref),
                broker_trade_id=result.broker_trade_id or "unknown",
            )
            await self.alerts.send_critical(
                f"SL/TP NOT CONFIRMED on trade {result.broker_trade_id or str(order.order_ref)}!"
            )

        logger.info(
            "fill_verified",
            pair=order.pair,
            fill_price=str(result.fill_price),
            slippage_pips=str(slippage),
            broker_trade_id=result.broker_trade_id,
        )
        return replace(result, slippage_pips=slippage)
