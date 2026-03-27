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

from ..core.enums import ExitReason
from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
from ..infrastructure.oanda_client import OandaClient
from ..infrastructure.secure_logger import get_logger

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
    ) -> None:
        self._db = db
        self._oanda = oanda
        self._alerts = alerts

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
            # Fetch DB open trades
            db_trades = await self._db.select(
                "trades",
                {"status": "OPEN"},
            )

            # Fetch OANDA open trades
            oanda_trades = await self._oanda.get_open_trades()

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

        # Mark as closed in DB
        # NOTE: Only use columns that exist on the trades table.
        # reconciliation_note does NOT exist — don't include it.
        try:
            await self._db.update(
                "trades",
                {"id": trade_id},
                {
                    "status": "CLOSED",
                    "exit_reason": ExitReason.UNKNOWN.value,
                    "outcome": "BREAKEVEN",
                    "pnl_usd": 0,
                    "pnl_pips": 0,
                    "closed_at": now.isoformat(),
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
            direction = "BUY" if int(str(units).replace(",", "")) > 0 else "SELL"
            abs_units = abs(int(str(units).replace(",", "")))
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
                    "position_size": abs_units,
                    "entry_price": str(price),
                    "stop_loss": str(price),
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
