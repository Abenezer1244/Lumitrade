"""
Lumitrade — Main Entry Point
================================
OrchestratorService coordinates all components.
Run via: python -m lumitrade.main
Managed by Supervisord in production.
Per BDS Section 11.1.
"""

import asyncio
import signal
import sys
from datetime import datetime, timedelta, timezone

from .config import LumitradeConfig
from .infrastructure.alert_service import AlertService
from .infrastructure.db import DatabaseClient
from .infrastructure.oanda_client import OandaClient, OandaTradingClient
from .infrastructure.secure_logger import configure_logging, get_logger
from .state.lock import DistributedLock
from .state.manager import StateManager

logger = get_logger("orchestrator")


class OrchestratorService:
    """Top-level coordinator for all Lumitrade components."""

    def __init__(self) -> None:
        self.config = LumitradeConfig()
        self._shutdown = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

        # Infrastructure
        self.db = DatabaseClient(self.config)
        self.oanda = OandaClient(self.config)
        self.oanda_trade = OandaTradingClient(self.config)
        self.alerts = AlertService(self.config, self.db)
        self.lock = DistributedLock(self.db)

        # Core services (lazy init after DB connect)
        self.state: StateManager | None = None

    async def startup(self) -> None:
        """Full startup sequence — must complete before trading begins."""
        logger.info("lumitrade_starting", instance_id=self.config.instance_id)

        # 1. Configure logging
        configure_logging(self.config.log_level)

        # 2. Connect database
        await self.db.connect()
        logger.info("database_connected")

        # 3. Initialize state manager
        self.state = StateManager(self.config, self.db, self.oanda)

        # 4. Restore persisted system state
        await self.state.restore()
        logger.info("state_restored")

        # 5. Try to acquire primary lock
        is_primary = await self.lock.acquire(self.config.instance_id)
        logger.info("lock_status", is_primary=is_primary)

        if not is_primary:
            logger.info("running_as_standby", instance_id=self.config.instance_id)

        # 6. Validate OANDA connection
        try:
            account = await self.oanda.get_account_summary()
            logger.info("oanda_connected", balance=account.get("balance"))
        except Exception as e:
            logger.error("oanda_connection_failed", error=str(e))

        # 7. Initialize trading components (import here to avoid circular deps)
        from .ai_brain.claude_client import ClaudeClient
        from .ai_brain.scanner import SignalScanner
        from .data_engine.engine import DataEngine
        from .execution_engine.engine import ExecutionEngine
        from .infrastructure.watchdog import Watchdog
        from .risk_engine.engine import RiskEngine
        from .subagents.subagent_orchestrator import SubagentOrchestrator

        self.subagents = SubagentOrchestrator(self.config, self.db, self.alerts)
        self.data_eng = DataEngine(self.config, self.oanda, self.db)
        self.claude = ClaudeClient(self.config)
        self.scanner = SignalScanner(
            self.config, self.data_eng, self.db, self.claude, self.subagents
        )
        self.risk_eng = RiskEngine(self.config, self.state, self.db)
        self.exec_eng = ExecutionEngine(
            self.config, self.oanda_trade, self.state, self.db,
            self.alerts, self.subagents,
        )
        self.watchdog = Watchdog(self.config, self.state, self.alerts)

        # 8. Start background tasks
        self._tasks = [
            asyncio.create_task(
                self.data_eng.stream_task(self.config.pairs),
                name="price_stream",
            ),
            asyncio.create_task(
                self.scanner.scan_loop(), name="signal_scan"
            ),
            asyncio.create_task(
                self.exec_eng.position_monitor(), name="position_monitor"
            ),
            asyncio.create_task(
                self.state.persist_loop(), name="state_persist"
            ),
            asyncio.create_task(
                self.lock.renew_loop(self.config.instance_id),
                name="heartbeat",
            ),
            asyncio.create_task(self.watchdog.run(), name="watchdog"),
            asyncio.create_task(
                self._risk_monitor_loop(), name="risk_monitor"
            ),
            asyncio.create_task(
                self._weekly_intelligence_loop(), name="intelligence"
            ),
        ]

        logger.info("lumitrade_running", mode=self.config.trading_mode)
        await self.alerts.send_info(
            f"Lumitrade started ({self.config.trading_mode} mode) "
            f"on {self.config.instance_id}"
        )

    async def shutdown(self, reason: str = "SIGTERM") -> None:
        """Graceful shutdown — waits for in-flight orders, persists state."""
        logger.info("lumitrade_shutting_down", reason=reason)
        self._shutdown.set()

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Persist final state
        if self.state:
            await self.state.save()
        await self.lock.release(self.config.instance_id)
        await self.oanda.close()
        logger.info("lumitrade_stopped")

    async def _risk_monitor_loop(self) -> None:
        """SA-03: Run risk monitor every 30 minutes while positions open."""
        while True:
            await asyncio.sleep(1800)  # 30 minutes
            try:
                if self.state:
                    state_data = await self.state.get()
                    open_trades = state_data.get("open_trades", []) if state_data else []
                    if open_trades:
                        snapshot = await self.data_eng.get_snapshot(
                            self.config.pairs[0]
                        )
                        if snapshot:
                            await self.subagents.run_risk_monitor(
                                open_trades, snapshot
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("risk_monitor_loop_error", error=str(e))

    async def _weekly_intelligence_loop(self) -> None:
        """SA-04: Fire intelligence report every Sunday at 19:00 EST."""
        while True:
            try:
                now = datetime.now(timezone.utc)
                # Calculate seconds until next Sunday 00:00 UTC (approx 19:00 EST)
                days_ahead = (6 - now.weekday()) % 7
                if days_ahead == 0 and now.hour >= 0:
                    days_ahead = 7
                next_sunday = now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=days_ahead)
                wait_seconds = (next_sunday - now).total_seconds()
                await asyncio.sleep(max(wait_seconds, 60))

                await self.subagents.run_weekly_intelligence(
                    self.config.oanda_account_id
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("intelligence_loop_error", error=str(e))

    async def run(self) -> None:
        """Main entry point."""
        loop = asyncio.get_event_loop()

        # Handle signals (Unix only — skip on Windows)
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(
                        self.shutdown(s.name)
                    ),
                )
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

        await self.startup()
        await self._shutdown.wait()


def main() -> None:
    """Entry point for python -m lumitrade.main."""
    configure_logging()
    orchestrator = OrchestratorService()
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
