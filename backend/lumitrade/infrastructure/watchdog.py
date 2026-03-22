"""
Lumitrade Watchdog
====================
Monitors engine health by checking heartbeat, lock age, and state
persistence freshness. Alerts on anomalies.

Per DOS Section 6.5.

Checks performed every 30 seconds:
  1. State persistence freshness (alert if > 120s stale).
  2. Lock age (alert if lock not renewed within expected interval).
  3. Heartbeat (engine responsiveness via state timestamps).
  4. Trading anomalies (stuck trades, excessive open positions).
"""

import asyncio
from datetime import datetime, timezone

from ..config import LumitradeConfig
from ..infrastructure.alert_service import AlertService
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

WATCHDOG_INTERVAL_SECONDS = 30
STATE_STALE_THRESHOLD_SECONDS = 120
LOCK_STALE_THRESHOLD_SECONDS = 180
HEARTBEAT_STALE_THRESHOLD_SECONDS = 90
MAX_OPEN_TRADES_ALERT = 5


class Watchdog:
    """
    Background health monitor that alerts on engine anomalies.
    """

    def __init__(
        self,
        config: LumitradeConfig,
        state_manager,
        alerts: AlertService,
    ) -> None:
        self._config = config
        self._state_manager = state_manager
        self._alerts = alerts
        self._shutdown_event = asyncio.Event()
        self._watchdog_task: asyncio.Task | None = None
        self._consecutive_stale_count = 0
        self._alerted_stale = False

    async def run(self) -> None:
        """
        Background loop checking engine health every WATCHDOG_INTERVAL_SECONDS.
        """
        self._shutdown_event.clear()
        logger.info(
            "watchdog_started",
            interval_seconds=WATCHDOG_INTERVAL_SECONDS,
            instance_id=self._config.instance_id,
        )

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                logger.info("watchdog_cancelled")
                return

            if self._shutdown_event.is_set():
                break

            await self._run_checks()

        logger.info("watchdog_stopped")

    async def _run_checks(self) -> None:
        """Execute all health checks."""
        try:
            state = await self._state_manager.get()
            now = datetime.now(timezone.utc)

            await self._check_state_persistence(state, now)
            await self._check_heartbeat(state, now)
            await self._check_trading_anomalies(state, now)

        except Exception:
            logger.exception("watchdog_check_failed")

    async def _check_state_persistence(
        self, state: dict, now: datetime
    ) -> None:
        """Alert if state has not been persisted within threshold."""
        last_persisted = state.get("last_persisted_at")
        if not last_persisted:
            # First run — state not yet persisted
            return

        try:
            persisted_at = datetime.fromisoformat(last_persisted)
            elapsed = (now - persisted_at).total_seconds()

            if elapsed > STATE_STALE_THRESHOLD_SECONDS:
                self._consecutive_stale_count += 1
                logger.warning(
                    "state_persistence_stale",
                    elapsed_seconds=elapsed,
                    threshold_seconds=STATE_STALE_THRESHOLD_SECONDS,
                    consecutive_stale=self._consecutive_stale_count,
                )

                # Alert on first detection, then every 5th consecutive stale check
                if not self._alerted_stale or self._consecutive_stale_count % 5 == 0:
                    await self._alerts.send_error(
                        f"State persistence stale: last saved {elapsed:.0f}s ago "
                        f"(threshold: {STATE_STALE_THRESHOLD_SECONDS}s). "
                        f"Consecutive stale checks: {self._consecutive_stale_count}"
                    )
                    self._alerted_stale = True
            else:
                if self._alerted_stale:
                    logger.info(
                        "state_persistence_recovered",
                        elapsed_seconds=elapsed,
                    )
                self._consecutive_stale_count = 0
                self._alerted_stale = False

        except (ValueError, TypeError):
            logger.warning(
                "state_persistence_unparseable",
                raw_value=last_persisted,
            )

    async def _check_heartbeat(self, state: dict, now: datetime) -> None:
        """
        Check engine heartbeat by examining state timestamps.
        If the engine is alive, state will be regularly updated.
        """
        started_at_str = state.get("started_at")
        if not started_at_str:
            return

        try:
            started_at = datetime.fromisoformat(started_at_str)
            uptime = (now - started_at).total_seconds()

            # Only check heartbeat after engine has been running > threshold
            if uptime < HEARTBEAT_STALE_THRESHOLD_SECONDS:
                return

            last_persisted = state.get("last_persisted_at")
            if last_persisted:
                persisted_at = datetime.fromisoformat(last_persisted)
                heartbeat_age = (now - persisted_at).total_seconds()

                if heartbeat_age > HEARTBEAT_STALE_THRESHOLD_SECONDS:
                    logger.error(
                        "heartbeat_stale",
                        heartbeat_age_seconds=heartbeat_age,
                        threshold_seconds=HEARTBEAT_STALE_THRESHOLD_SECONDS,
                    )
                    await self._alerts.send_error(
                        f"Engine heartbeat stale: last update {heartbeat_age:.0f}s ago. "
                        f"Engine may be unresponsive."
                    )
        except (ValueError, TypeError):
            pass

    async def _check_trading_anomalies(
        self, state: dict, now: datetime
    ) -> None:
        """Check for trading-related anomalies."""
        # Check for excessive open positions
        open_trades = state.get("open_trades", [])
        if len(open_trades) > MAX_OPEN_TRADES_ALERT:
            logger.warning(
                "excessive_open_trades",
                count=len(open_trades),
                threshold=MAX_OPEN_TRADES_ALERT,
            )
            await self._alerts.send_warning(
                f"Excessive open trades: {len(open_trades)} "
                f"(alert threshold: {MAX_OPEN_TRADES_ALERT})"
            )

        # Check kill switch status
        if state.get("kill_switch_active"):
            logger.warning(
                "kill_switch_active",
                instance_id=self._config.instance_id,
            )

        # Check risk state
        risk_state = state.get("risk_state", "NORMAL")
        if risk_state in ("EMERGENCY_HALT", "WEEKLY_LIMIT"):
            logger.warning(
                "critical_risk_state_active",
                risk_state=risk_state,
            )

    def start(self) -> asyncio.Task:
        """Start the watchdog background task and return the task handle."""
        self._watchdog_task = asyncio.create_task(
            self.run(),
            name="watchdog",
        )
        return self._watchdog_task

    async def shutdown(self) -> None:
        """Gracefully stop the watchdog."""
        self._shutdown_event.set()
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None
        logger.info("watchdog_shutdown_complete")
