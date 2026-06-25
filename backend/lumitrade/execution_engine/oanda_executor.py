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

        # Defense-in-depth: SL must be non-zero before a live broker call.
        # RiskEngine enforces R:R which requires a valid SL, but a malformed
        # ApprovedOrder or future refactor could bypass that path.
        if not order.stop_loss or order.stop_loss <= Decimal("0"):
            raise ExecutionError(
                f"Order rejected pre-broker: stop_loss is zero or missing for {order.pair} "
                f"(order_ref={order.order_ref})"
            )

        try:
            response = await self._client.place_market_order(
                pair=order.pair,
                units=units,
                sl=order.stop_loss,
                tp=order.take_profit,
                client_request_id=client_request_id,
            )
            return await self._parse_response(order, response)
        except Exception as e:
            # Permanent broker rejections (instrument not available on this account,
            # bad parameters, etc.) never committed at OANDA — skip recovery entirely.
            # Recovery is only useful for network timeouts where the order MAY have
            # reached OANDA before the connection dropped.
            _err_str = str(e)
            _PERMANENT_REJECTS = (
                "INSTRUMENT_NOT_TRADEABLE",
                "INSTRUMENT_HALTED",
                "STOP_LOSS_ON_FILL_LOSS_TOO_LARGE",
                "TAKE_PROFIT_ON_FILL_LOSS",
                "UNITS_PRECISION_EXCEEDED",
                "INSUFFICIENT_MARGIN",
                "MARGIN_CLOSEOUT_REQUIRED",
                "MARKET_ORDER_MARGIN_CLOSEOUT_REQUIRED",
                "UNITS_LIMIT_EXCEEDED",
                "OANDA_REJECT:",  # prefix injected by place_market_order from response body
            )
            if any(code in _err_str for code in _PERMANENT_REJECTS):
                # Extract the specific reject reason for a clear log message.
                reject_code = next(
                    (code for code in _PERMANENT_REJECTS if code in _err_str),
                    "BROKER_PERMANENT_REJECT",
                )
                logger.error(
                    "oanda_order_permanent_reject",
                    error=reject_code,
                    order_ref=str(order.order_ref),
                    pair=order.pair,
                )
                raise ExecutionError(
                    f"Order permanently rejected by broker ({reject_code}): "
                    f"{order.pair} is not tradeable on this account. "
                    f"Enable {order.pair} CFD trading in OANDA account settings."
                ) from e

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
                recovered = await self._client.lookup_order_status(client_request_id, pair=order.pair)
            except Exception as lookup_err:
                logger.error(
                    "oanda_order_recovery_lookup_failed",
                    error=str(lookup_err),
                    order_ref=str(order.order_ref),
                )
                recovered = None

            if recovered is not None and not isinstance(recovered, dict):
                logger.warning(
                    "oanda_order_recovery_lookup_malformed",
                    order_ref=str(order.order_ref),
                    recovered_type=type(recovered).__name__,
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
                return await self._parse_response(order, recovered)

            # No recovery — order either never reached OANDA or is still
            # in-flight. Failing closed is the only safe choice; reconciler
            # will sweep up any orphaned trade on the next cycle.
            logger.error(
                "oanda_order_failed",
                error=str(e),
                order_ref=str(order.order_ref),
            )
            raise ExecutionError(f"Order placement failed: {e}") from e

    async def _parse_response(self, order: ApprovedOrder, response: dict) -> OrderResult:
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

        sl_requested = order.stop_loss is not None and order.stop_loss != 0
        tp_requested = order.take_profit is not None and order.take_profit != 0
        # Confirm protection by reading the ACTUAL trade back from OANDA, not by
        # echoing the requested values or counting relatedTransactionIDs (a
        # filled order can return enough txn IDs while the SL/TP was rejected).
        sl_confirmed, tp_confirmed = await self._verify_protection(
            str(trade_id), order, sl_requested, tp_requested
        )

        order_create = response.get("orderCreateTransaction", {})
        order_id = order_create.get("id", order_fill.get("id", ""))
        fill_price = Decimal(str(order_fill.get("price", order.entry_price)))
        fill_units = Decimal(str(order_fill.get("units", abs(order.units))))
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
            # Actual broker-confirmed SL/TP prices (None == could not confirm —
            # FillVerifier escalates). See _verify_protection.
            stop_loss_confirmed=sl_confirmed,
            take_profit_confirmed=tp_confirmed,
            slippage_pips=slippage,
            raw_response=response,
        )

    @staticmethod
    def _price_or_none(raw: object) -> Decimal | None:
        """Parse an OANDA order price string to Decimal, or None if absent."""
        if raw is None or raw == "":
            return None
        try:
            d = Decimal(str(raw))
        except (ArithmeticError, ValueError, TypeError):
            return None
        # Reject NaN/Infinity — a non-finite "price" is never a real stop.
        return d if d.is_finite() else None

    async def _read_protection(
        self, trade_id: str, pair: str
    ) -> tuple[Decimal | None, Decimal | None, bool]:
        """Read the live trade's actual stopLossOrder/takeProfitOrder prices.

        Returns ``(sl_price, tp_price, readback_ok)``. ``readback_ok`` is False
        if the trade could not be fetched — in which case absence is unknown,
        NOT proof the stop is missing.
        """
        # The fetch AND the parsing are both inside the try: a malformed
        # response (non-dict trade, non-dict stopLossOrder/takeProfitOrder) must
        # become readback_ok=False (uncertain), never propagate to the caller's
        # corrective path where it would emergency-close a protected trade.
        try:
            trade = await self._client.get_trade(trade_id, pair=pair)
            sl_raw = (trade.get("stopLossOrder") or {}).get("price")
            tp_raw = (trade.get("takeProfitOrder") or {}).get("price")
        except Exception as e:
            logger.error(
                "oanda_protection_readback_failed",
                trade_id=trade_id,
                pair=pair,
                error=str(e),
            )
            return None, None, False
        return self._price_or_none(sl_raw), self._price_or_none(tp_raw), True

    async def _verify_protection(
        self, trade_id: str, order: ApprovedOrder, sl_requested: bool, tp_requested: bool
    ) -> tuple[Decimal | None, Decimal | None]:
        """Confirm SL/TP are actually attached at the broker; correct if not.

        - Reads the trade back. If a REQUESTED protective order is positively
          confirmed missing, attempts an idempotent corrective modify_trade and
          re-reads. If it is STILL missing, emergency-closes the unprotected
          position (capital must never sit unprotected).
        - If the readback itself fails (transient), we re-assert the protection
          best-effort but do NOT emergency-close on mere uncertainty, and report
          (None, None) so FillVerifier surfaces the unconfirmed state.

        Returns the confirmed (sl, tp) prices; None means not confirmed.
        """
        if not trade_id:
            return None, None

        sl, tp, ok = await self._read_protection(trade_id, order.pair)

        if not ok:
            # Couldn't verify. Best-effort idempotent re-assert (harmless if the
            # stop is already set); never emergency-close on uncertainty alone.
            if sl_requested or tp_requested:
                try:
                    await self._client.modify_trade(
                        broker_trade_id=trade_id,
                        sl=order.stop_loss or Decimal("0"),
                        tp=order.take_profit or Decimal("0"),
                        pair=order.pair,
                    )
                    logger.warning(
                        "oanda_protection_reasserted_unverified",
                        trade_id=trade_id,
                        pair=order.pair,
                    )
                except Exception as e:
                    logger.critical(
                        "oanda_protection_reassert_failed",
                        trade_id=trade_id,
                        pair=order.pair,
                        error=str(e),
                    )
            return None, None

        sl_missing = sl_requested and sl is None
        tp_missing = tp_requested and tp is None
        if not (sl_missing or tp_missing):
            return sl, tp

        logger.critical(
            "oanda_protection_missing_after_fill",
            trade_id=trade_id,
            pair=order.pair,
            sl_missing=sl_missing,
            tp_missing=tp_missing,
        )
        try:
            await self._client.modify_trade(
                broker_trade_id=trade_id,
                sl=order.stop_loss or Decimal("0"),
                tp=order.take_profit or Decimal("0"),
                pair=order.pair,
            )
            sl, tp, ok2 = await self._read_protection(trade_id, order.pair)
            if not ok2:
                # Correction was ACCEPTED (modify_trade did not raise) but we
                # cannot re-confirm it. Do NOT close on uncertainty — the modify
                # almost certainly set the stop. Report unconfirmed so
                # FillVerifier surfaces it.
                logger.warning(
                    "oanda_protection_correction_unverified",
                    trade_id=trade_id,
                    pair=order.pair,
                )
                return None, None
            # Re-read positively confirmed the state. Emergency-close ONLY when
            # the requested protection is still genuinely absent.
            still_missing = (sl_requested and sl is None) or (tp_requested and tp is None)
            if still_missing:
                raise ExecutionError("protection still missing after corrective modify")
            logger.info("oanda_protection_corrected", trade_id=trade_id, pair=order.pair)
            return sl, tp
        except Exception as corr_err:
            logger.critical(
                "oanda_corrective_protection_failed_closing_trade",
                trade_id=trade_id,
                pair=order.pair,
                error=str(corr_err),
            )
            try:
                await self._client.close_trade(trade_id, pair=order.pair)
                logger.info("oanda_unprotected_trade_closed", trade_id=trade_id)
            except Exception as close_err:
                logger.critical(
                    "oanda_emergency_close_failed",
                    trade_id=trade_id,
                    error=str(close_err),
                )
            return None, None
