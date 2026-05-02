"""
Lumitrade Position Reconciler
================================
Compares DB open trades with OANDA actual open trades to detect
ghosts (DB says open, broker says closed) and phantoms (broker has
trade not in DB).

Per DOS Section 7.3.

Reconciliation runs:
  1. On engine startup (via StateManager.restore)
  2. Periodically during runtime (via Watchdog)

Any discrepancy triggers a CRITICAL alert — positions and money are
at stake.
"""

from datetime import datetime, timezone
from decimal import Decimal

from ..core.enums import ExitReason
from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
from ..infrastructure.oanda_client import OandaClient
from ..infrastructure.secure_logger import get_logger
from ..utils.pip_math import pips_between

logger = get_logger(__name__)


class PositionReconciler:
    """
    Detect and resolve position discrepancies between DB and OANDA.

    Ghost: trade marked OPEN in DB but not found on OANDA.
    Phantom: trade on OANDA with no corresponding DB record.
    Matched: trade exists in both DB and OANDA — consistent.
    """

    def __init__(
        self,
        db: DatabaseClient,
        oanda: OandaClient,
        alerts: AlertService,
        account_uuid: str = "",
    ) -> None:
        self._db = db
        self._oanda = oanda
        self._alerts = alerts
        # account_uuid scopes all DB reads/writes to this account.
        # Empty string = legacy unscoped behavior (only acceptable in
        # single-account dev/test). Without scoping, another tenant's
        # open positions are misclassified as ghosts and force-closed.
        self._account_uuid = account_uuid

    async def reconcile(self) -> dict:
        """
        Run full position reconciliation.

        Returns:
            {
                "ghosts": [...],     # DB open but not on broker
                "phantoms": [...],   # On broker but not in DB
                "matched": [...],    # Consistent between DB and broker
                "reconciled_at": "ISO timestamp",
            }
        """
        now = datetime.now(timezone.utc)
        ghosts: list[dict] = []
        phantoms: list[dict] = []
        matched: list[dict] = []

        try:
            # Fetch DB open trades — scoped to this account when account_uuid
            # is set. Unscoped query would treat other tenants' open trades
            # as ghosts and force-close them.
            db_filter = {"status": "OPEN"}
            if self._account_uuid:
                db_filter["account_id"] = self._account_uuid
            db_trades = await self._db.select("trades", db_filter)

            # Fetch OANDA open trades
            oanda_trades = await self._oanda.get_all_open_trades()

            # Index OANDA trades by broker_trade_id for O(1) lookup
            oanda_by_id: dict[str, dict] = {}
            for ot in oanda_trades:
                trade_id = str(ot.get("id", ""))
                if trade_id:
                    oanda_by_id[trade_id] = ot

            # Index DB trades by broker_trade_id
            db_by_broker_id: dict[str, dict] = {}
            for dt in db_trades:
                broker_id = str(dt.get("broker_trade_id", ""))
                if broker_id:
                    db_by_broker_id[broker_id] = dt

            # Detect ghosts: in DB as OPEN but not on OANDA
            for dt in db_trades:
                broker_id = str(dt.get("broker_trade_id", ""))
                if not broker_id:
                    # No broker_trade_id means we can't match to OANDA —
                    # treat as ghost (leftover from old parsing bug)
                    ghost = await self._handle_ghost(dt, now)
                    ghosts.append(ghost)
                elif broker_id not in oanda_by_id:
                    ghost = await self._handle_ghost(dt, now)
                    ghosts.append(ghost)
                else:
                    matched.append({
                        "trade_id": dt.get("id"),
                        "broker_trade_id": broker_id,
                        "pair": dt.get("pair"),
                    })

            # Detect phantoms: on OANDA but not in DB
            for trade_id, ot in oanda_by_id.items():
                if trade_id not in db_by_broker_id:
                    phantom = await self._handle_phantom(ot, now)
                    phantoms.append(phantom)

            # Log summary
            logger.info(
                "reconciliation_complete",
                ghosts=len(ghosts),
                phantoms=len(phantoms),
                matched=len(matched),
            )

            return {
                "ghosts": ghosts,
                "phantoms": phantoms,
                "matched": matched,
                "reconciled_at": now.isoformat(),
            }

        except Exception:
            logger.exception("reconciliation_failed")
            await self._alerts.send_critical(
                "Position reconciliation failed — manual review required"
            )
            return {
                "ghosts": ghosts,
                "phantoms": phantoms,
                "matched": matched,
                "reconciled_at": now.isoformat(),
                "error": True,
            }

    async def _handle_ghost(self, db_trade: dict, now: datetime) -> dict:
        """
        Handle a ghost trade: exists in DB as OPEN but not on OANDA.

        Action: Mark the trade as CLOSED with exit_reason UNKNOWN and
        send a CRITICAL alert.
        """
        trade_id = db_trade.get("id")
        broker_trade_id = db_trade.get("broker_trade_id")
        pair = db_trade.get("pair", "UNKNOWN")

        logger.critical(
            "ghost_trade_detected",
            trade_id=trade_id,
            broker_trade_id=broker_trade_id,
            pair=pair,
        )

        # Mark as closed in DB — try to fetch real P&L from OANDA first.
        try:
            opened_at_raw = db_trade.get("opened_at") or now.isoformat()
            entry_price_raw = db_trade.get("entry_price")
            outcome = "BREAKEVEN"
            pnl_usd: float = 0.0
            pnl_pips: Decimal = Decimal("0")
            exit_price = entry_price_raw
            close_time = opened_at_raw
            exit_reason = ExitReason.UNKNOWN.value
            oanda_close_reason: str | None = None

            # Attempt to get real P&L from OANDA if we have a broker_trade_id
            if broker_trade_id:
                try:
                    oanda_trade = await self._oanda.get_trade(broker_trade_id, pair=pair)
                    real_pl = float(oanda_trade.get("realizedPL", 0))
                    if real_pl != 0:
                        pnl_usd = real_pl
                        outcome = "WIN" if real_pl > 0 else "LOSS"
                    close_price = oanda_trade.get("averageClosePrice")
                    if close_price:
                        exit_price = close_price
                    close_t = oanda_trade.get("closeTime")
                    if close_t:
                        close_time = close_t
                    # Infer exit reason from the close-transaction reasons
                    # OANDA populates these fields when a stop/tp order filled.
                    tx_reasons = [
                        oanda_trade.get(k)
                        for k in (
                            "stopLossOrderFillReason",
                            "takeProfitOrderFillReason",
                            "trailingStopLossOrderFillReason",
                        )
                        if oanda_trade.get(k)
                    ]
                    oanda_close_reason = tx_reasons[0] if tx_reasons else None
                    logger.info(
                        "ghost_trade_real_pnl_fetched",
                        trade_id=trade_id,
                        pnl_usd=pnl_usd,
                        outcome=outcome,
                        oanda_close_reason=oanda_close_reason,
                    )
                except Exception:
                    logger.warning(
                        "ghost_trade_pnl_fetch_failed",
                        trade_id=trade_id,
                        broker_trade_id=broker_trade_id,
                    )

            # Best-effort exit_reason classification:
            #   1. If OANDA reported a specific fill reason, use it.
            #   2. Otherwise infer from P&L sign: wins on ghost trades almost
            #      always come from trailing-stop fills (we don't set fixed TP);
            #      losses come from the fixed SL.
            if oanda_close_reason:
                if "TRAILING" in oanda_close_reason.upper():
                    exit_reason = ExitReason.TRAILING_STOP.value
                elif "STOP_LOSS" in oanda_close_reason.upper():
                    exit_reason = ExitReason.SL_HIT.value
                elif "TAKE_PROFIT" in oanda_close_reason.upper():
                    exit_reason = ExitReason.TP_HIT.value
            elif outcome == "WIN":
                exit_reason = ExitReason.TRAILING_STOP.value
            elif outcome == "LOSS":
                exit_reason = ExitReason.SL_HIT.value

            # Compute pnl_pips from real entry/exit so downstream analysis
            # (lesson_analyzer, audit, dashboard) has complete data.
            try:
                if entry_price_raw and exit_price:
                    direction = (db_trade.get("direction") or "").upper()
                    entry_d = Decimal(str(entry_price_raw))
                    exit_d = Decimal(str(exit_price))
                    raw_pips = pips_between(entry_d, exit_d, pair)
                    if direction == "BUY":
                        pnl_pips = raw_pips if exit_d >= entry_d else -raw_pips
                    elif direction == "SELL":
                        pnl_pips = raw_pips if exit_d <= entry_d else -raw_pips
            except Exception:
                pnl_pips = Decimal("0")

            # Duration in minutes — opened_at → close_time.
            duration_minutes = None
            try:
                opened_dt = (
                    datetime.fromisoformat(opened_at_raw.replace("Z", "+00:00"))
                    if isinstance(opened_at_raw, str)
                    else opened_at_raw
                )
                closed_dt = (
                    datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                    if isinstance(close_time, str)
                    else close_time
                )
                duration_minutes = int((closed_dt - opened_dt).total_seconds() // 60)
            except Exception:
                duration_minutes = None

            await self._db.update(
                "trades",
                {"id": trade_id},
                {
                    "status": "CLOSED",
                    "exit_reason": exit_reason,
                    "outcome": outcome,
                    "pnl_usd": pnl_usd,
                    "pnl_pips": str(pnl_pips),
                    "exit_price": str(exit_price) if exit_price else None,
                    "closed_at": close_time,
                    "duration_minutes": duration_minutes,
                },
            )
            logger.info(
                "ghost_trade_closed",
                trade_id=trade_id,
                broker_trade_id=broker_trade_id,
                pair=pair,
            )
        except Exception:
            logger.exception(
                "ghost_trade_update_failed",
                trade_id=trade_id,
            )

        await self._alerts.send_critical(
            f"GHOST TRADE: {pair} trade {broker_trade_id} is OPEN in DB but "
            f"not found on OANDA. Marked CLOSED/UNKNOWN. Manual P&L review required."
        )

        return {
            "trade_id": trade_id,
            "broker_trade_id": broker_trade_id,
            "pair": pair,
            "action": "marked_closed_unknown",
            "detected_at": now.isoformat(),
        }

    async def _handle_phantom(self, oanda_trade: dict, now: datetime) -> dict:
        """
        Handle a phantom trade: exists on OANDA but not in DB.

        Action: Create an emergency record in the trades table and
        send a CRITICAL alert.
        """
        trade_id = str(oanda_trade.get("id", ""))
        instrument = oanda_trade.get("instrument", "UNKNOWN")
        units = oanda_trade.get("currentUnits", oanda_trade.get("initialUnits", "0"))
        open_time = oanda_trade.get("openTime", now.isoformat())
        price = oanda_trade.get("price", "0")

        logger.critical(
            "phantom_trade_detected",
            broker_trade_id=trade_id,
            instrument=instrument,
            units=units,
        )

        # Create emergency DB record
        # NOTE: Only use columns that exist on the trades table schema.
        try:
            units_decimal = Decimal(str(units).replace(",", ""))
            direction = "BUY" if units_decimal > 0 else "SELL"
            abs_units = abs(units_decimal)
            # Get the account_id from an existing trade, or use config
            from ..config import LumitradeConfig
            config = LumitradeConfig()  # type: ignore[call-arg]

            await self._db.insert(
                "trades",
                {
                    "account_id": config.account_uuid,
                    "broker_trade_id": trade_id,
                    "pair": instrument,
                    "direction": direction,
                    "position_size": str(abs_units),
                    "entry_price": str(price),
                    "stop_loss": str(price),
                    # Phantom rows have no real SL distance — set
                    # initial_stop_loss = entry so the trailing-stop
                    # zero-distance guard explicitly skips them. These rows
                    # are emergency reconciler inserts representing trades
                    # opened outside our pipeline; they should be reviewed
                    # manually, not algorithmically trailed.
                    "initial_stop_loss": str(price),
                    "take_profit": str(price),
                    "mode": "PAPER",
                    "status": "OPEN",
                    "opened_at": open_time,
                },
            )
        except Exception:
            logger.exception(
                "phantom_trade_insert_failed",
                broker_trade_id=trade_id,
            )

        await self._alerts.send_critical(
            f"PHANTOM TRADE: {instrument} trade {trade_id} ({units} units) found on "
            f"OANDA but has no DB record. Emergency record created. "
            f"Manual review required."
        )

        return {
            "broker_trade_id": trade_id,
            "instrument": instrument,
            "units": str(units),
            "action": "emergency_record_created",
            "detected_at": now.isoformat(),
        }
