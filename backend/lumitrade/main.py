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
from decimal import Decimal
from typing import Any

from .config import LumitradeConfig
from .core.models import ApprovedOrder
from .infrastructure.alert_service import AlertService
from .infrastructure.db import DatabaseClient
from .infrastructure.oanda_client import OandaClient, OandaTradingClient
from .infrastructure.secure_logger import configure_logging, get_logger
from .state.lock import DistributedLock
from .state.manager import StateManager

logger = get_logger("orchestrator")


def _action_str(action) -> str:
    """Safely get string value from an Action enum or plain string."""
    return action.value if hasattr(action, "value") else str(action)


# ── Sentry Integration (DOS Section 6.2) ─────────────────────────


def scrub_sentry_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Strip sensitive data from Sentry events before transmission.

    Removes request headers/cookies and local variables from stack frames
    to prevent accidental credential leakage to Sentry servers.
    """
    # Remove request headers and cookies
    request = event.get("request")
    if request and isinstance(request, dict):
        request.pop("headers", None)
        request.pop("cookies", None)

    # Remove local variables from all stack frames
    exception = event.get("exception")
    if exception and isinstance(exception, dict):
        for exc_value in exception.get("values", []):
            stacktrace = exc_value.get("stacktrace")
            if stacktrace and isinstance(stacktrace, dict):
                for frame in stacktrace.get("frames", []):
                    frame.pop("vars", None)

    return event


def configure_sentry(config: LumitradeConfig) -> None:
    """Initialize Sentry error tracking if DSN is configured.

    Safe no-op if sentry-sdk is not installed or DSN is empty.
    Called once at startup after configure_logging().
    """
    if not config.sentry_dsn:
        logger.debug("sentry_skipped", reason="no_dsn_configured")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
    except ImportError:
        logger.debug("sentry_skipped", reason="sentry_sdk_not_installed")
        return

    sentry_sdk.init(
        dsn=config.sentry_dsn,
        integrations=[AsyncioIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        environment=config.oanda_environment,
        before_send=scrub_sentry_event,
    )
    logger.info("sentry_initialized", environment=config.oanda_environment)


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

        # 1b. Initialize Sentry error tracking (DOS Section 6.2)
        configure_sentry(self.config)

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
        from .infrastructure.event_publisher import EventPublisher
        from .infrastructure.watchdog import Watchdog
        from .risk_engine.engine import RiskEngine
        from .subagents.subagent_orchestrator import SubagentOrchestrator

        self.events = EventPublisher(self.db, self.config.account_uuid)
        self.subagents = SubagentOrchestrator(self.config, self.db, self.alerts, events=self.events)
        self.data_eng = DataEngine(self.config, self.oanda, self.db)
        self.claude = ClaudeClient(self.config)
        self.scanner = SignalScanner(
            self.config, self.data_eng, self.db, self.claude, self.subagents,
            events=self.events,
        )
        self.risk_eng = RiskEngine(
            self.config, self.state, self.db, events=self.events,
        )
        self.exec_eng = ExecutionEngine(
            self.config, self.oanda_trade, self.state, self.db,
            self.alerts, self.subagents,
            oanda_read_client=self.oanda,
            events=self.events,
        )
        self.watchdog = Watchdog(self.config, self.state, self.alerts)

        # 8. Start background tasks
        self._tasks = [
            asyncio.create_task(
                self.data_eng.stream_task(self.config.pairs),
                name="price_stream",
            ),
            asyncio.create_task(
                self._signal_to_trade_loop(), name="signal_scan"
            ),
            asyncio.create_task(
                self.exec_eng.position_monitor(), name="position_monitor"
            ),
            asyncio.create_task(
                self.state.persist_loop(oanda_client=self.oanda), name="state_persist"
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

    async def _signal_to_trade_loop(self) -> None:
        """Full pipeline: scan → risk evaluate → execute if approved."""
        logger.info("signal_to_trade_loop_started", pairs=self.config.pairs)
        try:
            while True:
                # Refresh account balance from OANDA every cycle
                try:
                    acct = await self.oanda.get_account_summary()
                    if acct and self.state:
                        self.state._state["account_balance"] = str(acct.get("balance", "0"))
                        self.state._state["account_equity"] = str(acct.get("equity", acct.get("NAV", "0")))
                except Exception:
                    pass  # Non-critical — balance stays at last known value

                for pair in self.config.pairs:
                    # Kill switch check — skip all scanning if halted
                    if self.state and self.state.kill_switch_active:
                        logger.info("kill_switch_active_skipping_scan")
                        break

                    try:
                        # 1. Scan for signal
                        proposal = await self.scanner.execute_scan(pair)
                        if not proposal:
                            continue
                        if _action_str(proposal.action) == "HOLD":
                            logger.info("signal_hold_skipped", pair=pair)
                            continue
                        if proposal.confidence_adjusted < self.config.min_confidence:
                            logger.info(
                                "signal_below_threshold",
                                pair=pair,
                                confidence=str(proposal.confidence_adjusted),
                                threshold=str(self.config.min_confidence),
                            )
                            continue

                        # 2. Get account balance for risk sizing
                        account = await self.oanda.get_account_summary()
                        balance = Decimal(str(account.get("balance", "0")))

                        # 3. Risk evaluation
                        logger.info(
                            "signal_evaluating_risk",
                            pair=pair,
                            action=_action_str(proposal.action),
                            confidence=str(proposal.confidence_adjusted),
                            balance=str(balance),
                        )
                        result = await self.risk_eng.evaluate(proposal, balance)
                        if not isinstance(result, ApprovedOrder):
                            logger.info(
                                "signal_risk_rejected",
                                pair=pair,
                                reason=getattr(result, "rule_violated", "unknown"),
                            )
                            continue
                        approved = result

                        # 4. Execute trade
                        current_price = proposal.entry_price
                        logger.info(
                            "signal_executing_trade",
                            pair=pair,
                            action=_action_str(proposal.action),
                            confidence=str(proposal.confidence_adjusted),
                            price=str(current_price),
                        )
                        await self.exec_eng.execute_order(approved, current_price)
                        logger.info(
                            "trade_executed_successfully",
                            pair=pair,
                            action=_action_str(proposal.action),
                        )
                    except Exception as e:
                        logger.error(
                            "signal_to_trade_error",
                            pair=pair,
                            error=str(e),
                        )

                    # Stagger between pairs
                    await asyncio.sleep(5)

                # Wait for next scan cycle
                await asyncio.sleep(self.config.signal_interval_minutes * 60)
        except asyncio.CancelledError:
            logger.info("signal_to_trade_loop_cancelled")

    async def _risk_monitor_loop(self) -> None:
        """SA-03: Run risk monitor every 30 minutes while positions open."""
        while True:
            await asyncio.sleep(1800)  # 30 minutes
            try:
                # Fetch real open trades from DB with full details
                open_trades = await self.db.select(
                    "trades",
                    {"status": "OPEN", "account_id": self.config.account_uuid},
                )
                if open_trades:
                    # Get current prices for each pair
                    pairs_in_trades = list({t["pair"] for t in open_trades})
                    try:
                        pricing = await self.oanda_data.get_pricing(pairs_in_trades)
                        prices = {}
                        for p in pricing.get("prices", []):
                            inst = p.get("instrument", "")
                            bids = p.get("bids", [])
                            asks = p.get("asks", [])
                            if bids and asks:
                                mid = (float(bids[0]["price"]) + float(asks[0]["price"])) / 2
                                prices[inst] = mid
                    except Exception:
                        prices = {}

                    # Enrich trades with current price
                    enriched = []
                    for t in open_trades:
                        enriched.append({
                            "trade_id": t.get("id", ""),
                            "pair": t.get("pair", ""),
                            "direction": t.get("direction", ""),
                            "entry_price": t.get("entry_price", 0),
                            "current_price": prices.get(t.get("pair", ""), 0),
                        })

                    snapshot = await self.data_eng.get_snapshot(
                        pairs_in_trades[0]
                    )
                    if snapshot:
                        await self.subagents.run_risk_monitor(
                            enriched, snapshot
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
    config = LumitradeConfig()
    configure_sentry(config)
    orchestrator = OrchestratorService()
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
