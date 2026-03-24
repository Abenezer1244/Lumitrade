"""
Lumitrade State Manager
=========================
Persists and restores full system state to/from the Supabase
system_state table. Acts as the central in-memory state store
for the running engine.

Per DOS Section 7.1.

State lifecycle:
  1. On startup: restore() reads DB, reconciles with OANDA, merges.
  2. During operation: persist_loop() saves state every 30s.
  3. Components read state via get() and risk_state property.
  4. On shutdown: final save() before lock release.

DB schema (system_state singleton row):
  id TEXT PRIMARY KEY DEFAULT 'singleton'
  risk_state TEXT
  open_trades JSONB
  daily_pnl_usd DECIMAL
  weekly_pnl_usd DECIMAL
  consecutive_losses INT
  last_signal_time JSONB
  confidence_threshold_override DECIMAL
  is_primary_instance BOOLEAN
  instance_id TEXT
  lock_expires_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ
"""

import asyncio
from datetime import datetime, timezone

from ..config import LumitradeConfig
from ..core.enums import RiskState, TradingMode
from ..infrastructure.db import DatabaseClient
from ..infrastructure.oanda_client import OandaClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

STATE_ROW_ID = "singleton"
PERSIST_INTERVAL_SECONDS = 30


class StateManager:
    """
    Central system state store. Persists to Supabase and reconciles
    with OANDA on restore.
    """

    def __init__(
        self,
        config: LumitradeConfig,
        db: DatabaseClient,
        oanda: OandaClient,
    ) -> None:
        self._config = config
        self._db = db
        self._oanda = oanda
        self._persist_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

        # In-memory state
        self._state: dict = {
            "instance_id": config.instance_id,
            "trading_mode": config.trading_mode,
            "risk_state": RiskState.NORMAL.value,
            "kill_switch_active": False,
            "pairs": config.pairs,
            "open_trades": [],
            "daily_pnl": "0",
            "weekly_pnl": "0",
            "consecutive_losses": 0,
            "last_signal_at": None,
            "last_trade_at": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_persisted_at": None,
            "reconciliation": None,
            "account_balance": "0",
            "account_equity": "0",
            "confidence_threshold_override": None,
        }

    async def restore(self) -> None:
        """
        Restore system state from DB and reconcile with OANDA.

        Sequence:
          1. Read persisted state from system_state table (singleton row).
          2. Fetch live account data from OANDA.
          3. Run position reconciliation.
          4. Merge results into in-memory state.
        """
        logger.info("state_restore_started", instance_id=self._config.instance_id)

        # 1. Read persisted state from DB (flat columns, not key-value)
        try:
            row = await self._db.select_one(
                "system_state",
                {"id": STATE_ROW_ID},
            )
            if row:
                # Map DB columns to in-memory state keys
                if row.get("risk_state") is not None:
                    self._state["risk_state"] = row["risk_state"]
                if row.get("open_trades") is not None:
                    self._state["open_trades"] = row["open_trades"]
                if row.get("daily_pnl_usd") is not None:
                    self._state["daily_pnl"] = str(row["daily_pnl_usd"])
                if row.get("weekly_pnl_usd") is not None:
                    self._state["weekly_pnl"] = str(row["weekly_pnl_usd"])
                if row.get("consecutive_losses") is not None:
                    self._state["consecutive_losses"] = row["consecutive_losses"]
                if row.get("last_signal_time") is not None:
                    self._state["last_signal_at"] = row["last_signal_time"]
                if row.get("confidence_threshold_override") is not None:
                    self._state["confidence_threshold_override"] = str(
                        row["confidence_threshold_override"]
                    )

                logger.info(
                    "state_restored_from_db",
                    persisted_at=row.get("updated_at"),
                )
            else:
                logger.info("state_no_persisted_state", msg="Starting with defaults")
        except Exception:
            logger.exception("state_restore_db_failed")

        # 2. Fetch live account data from OANDA
        try:
            account = await self._oanda.get_account_summary()
            self._state["account_balance"] = account.get("balance", "0")
            self._state["account_equity"] = account.get("NAV", "0")
            logger.info(
                "state_account_fetched",
                balance=account.get("balance"),
                equity=account.get("NAV"),
            )
        except Exception:
            logger.exception("state_account_fetch_failed")

        # 3. Run position reconciliation
        try:
            from ..infrastructure.alert_service import AlertService
            from .reconciler import PositionReconciler

            alerts = AlertService(self._config, self._db)
            reconciler = PositionReconciler(self._db, self._oanda, alerts)
            result = await reconciler.reconcile()

            self._state["reconciliation"] = {
                "ghosts": len(result.get("ghosts", [])),
                "phantoms": len(result.get("phantoms", [])),
                "matched": len(result.get("matched", [])),
                "reconciled_at": result.get("reconciled_at"),
            }

            # Update open trades from matched list
            self._state["open_trades"] = [
                m.get("broker_trade_id") for m in result.get("matched", [])
            ]

            logger.info(
                "state_reconciliation_complete",
                ghosts=len(result.get("ghosts", [])),
                phantoms=len(result.get("phantoms", [])),
                matched=len(result.get("matched", [])),
            )
        except Exception:
            logger.exception("state_reconciliation_failed")

        # 4. Persist the restored state
        await self.save()
        logger.info(
            "state_restore_complete",
            instance_id=self._config.instance_id,
            trading_mode=self._config.trading_mode,
        )

    async def save(self) -> None:
        """
        Write full in-memory state to the system_state singleton row.
        Maps in-memory keys to flat DB columns.
        """
        now = datetime.now(timezone.utc)
        self._state["last_persisted_at"] = now.isoformat()

        try:
            await self._db.upsert(
                "system_state",
                {
                    "id": STATE_ROW_ID,
                    "risk_state": self._state.get("risk_state", "NORMAL"),
                    "open_trades": self._state.get("open_trades", []),
                    "daily_pnl_usd": self._state.get("daily_pnl", "0"),
                    "weekly_pnl_usd": self._state.get("weekly_pnl", "0"),
                    "consecutive_losses": self._state.get("consecutive_losses", 0),
                    "last_signal_time": self._state.get("last_signal_at"),
                    "confidence_threshold_override": self._state.get(
                        "confidence_threshold_override"
                    ),
                    "account_balance": self._state.get("account_balance", "0"),
                    "account_equity": self._state.get("account_equity", "0"),
                    "updated_at": now.isoformat(),
                },
            )
            logger.debug(
                "state_persisted",
                instance_id=self._config.instance_id,
            )
        except Exception:
            logger.exception("state_persist_failed")

    async def persist_loop(self) -> None:
        """
        Background task that calls save() every PERSIST_INTERVAL_SECONDS.
        Runs until shutdown event is set or task is cancelled.
        """
        self._shutdown_event.clear()
        logger.info(
            "state_persist_loop_started",
            interval_seconds=PERSIST_INTERVAL_SECONDS,
        )

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(PERSIST_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                logger.info("state_persist_loop_cancelled")
                # Final save before exit
                await self.save()
                return

            if self._shutdown_event.is_set():
                break

            await self.save()

        # Final save on shutdown
        await self.save()
        logger.info("state_persist_loop_stopped")

    async def get(self) -> dict:
        """Return a copy of the current in-memory state."""
        return dict(self._state)

    @property
    def risk_state(self) -> RiskState:
        """Current risk state as a RiskState enum."""
        raw = self._state.get("risk_state", RiskState.NORMAL.value)
        try:
            return RiskState(raw)
        except ValueError:
            logger.warning(
                "invalid_risk_state_value",
                raw_value=raw,
                fallback=RiskState.NORMAL.value,
            )
            return RiskState.NORMAL

    @risk_state.setter
    def risk_state(self, value: RiskState) -> None:
        """Update the in-memory risk state."""
        self._state["risk_state"] = value.value

    @property
    def kill_switch_active(self) -> bool:
        """Whether the emergency kill switch is engaged."""
        return bool(self._state.get("kill_switch_active", False))

    @kill_switch_active.setter
    def kill_switch_active(self, value: bool) -> None:
        self._state["kill_switch_active"] = value

    @property
    def trading_mode(self) -> TradingMode:
        """Current trading mode."""
        raw = self._state.get("trading_mode", TradingMode.PAPER.value)
        try:
            return TradingMode(raw)
        except ValueError:
            return TradingMode.PAPER

    @property
    def open_trade_count(self) -> int:
        """Number of currently tracked open trades."""
        return len(self._state.get("open_trades", []))

    def update(self, **kwargs) -> None:
        """
        Update specific state fields in-memory.
        Changes are written to DB on the next persist_loop cycle.
        """
        for key, value in kwargs.items():
            if key in self._state:
                self._state[key] = value
            else:
                logger.warning(
                    "state_update_unknown_key",
                    key=key,
                )

    def start_persist_loop(self) -> asyncio.Task:
        """Start the persistence background task and return the task handle."""
        self._persist_task = asyncio.create_task(
            self.persist_loop(),
            name="state_persist_loop",
        )
        return self._persist_task

    async def shutdown(self) -> None:
        """Graceful shutdown: stop persist loop and save final state."""
        self._shutdown_event.set()
        if self._persist_task is not None and not self._persist_task.done():
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass
            self._persist_task = None
        await self.save()
        logger.info("state_manager_shutdown_complete")
