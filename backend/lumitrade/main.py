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

        # 3. ACQUIRE PRIMARY LOCK FIRST. Codex round-4 finding #1 — startup
        # must NOT do any mutating work before becoming primary. Otherwise
        # a standby (rolling redeploy overlap, manual second instance, lost
        # failover race) can corrupt DB state and place duplicate live OANDA
        # orders during the ~30s window before it figures out it lost.
        is_primary = await self.lock.acquire(self.config.instance_id)
        logger.info("lock_status", is_primary=is_primary)

        if not is_primary:
            logger.warning(
                "lock_not_acquired_exiting",
                instance_id=self.config.instance_id,
                msg="Refusing to run as standby — exit cleanly so Railway "
                    "respawns and the survivor can re-attempt the lock.",
            )
            raise SystemExit(
                f"Lock acquisition failed for {self.config.instance_id}. "
                "Another instance holds the primary lock; this process refuses "
                "to start trading loops as a standby. Restart will retry."
            )

        # 4. Initialize state manager — safe now that we hold the lock
        self.state = StateManager(self.config, self.db, self.oanda)
        self.state.mark_as_primary()

        # 5. Restore persisted system state — performs reconciliation +
        # writes; only safe to run as the verified primary.
        await self.state.restore()
        logger.info("state_restored")

        # 6. Validate OANDA connection
        try:
            account = await self.oanda.get_account_summary_for_pairs(self.config.pairs)
            logger.info("oanda_connected", balance=account.get("balance"))
        except Exception as e:
            logger.error("oanda_connection_failed", error=str(e))

        # 6b. Validate which instruments are tradeable on this account.
        # live_pairs are explicitly approved (backtest-validated) and must not
        # be silently removed — BTC_USD is a CFD not listed on OANDA practice.
        try:
            tradeable = await self._validate_tradeable_instruments()
            live_approved = set(self.config.live_pairs)
            original = self.config.pairs[:]
            self.config.pairs = [p for p in self.config.pairs if p in tradeable or p in live_approved]
            removed = set(original) - set(self.config.pairs)
            if removed:
                logger.warning(
                    "instruments_not_tradeable_removed",
                    removed=list(removed),
                    remaining=self.config.pairs,
                )
        except Exception as e:
            logger.warning("instrument_validation_failed", error=str(e))

        # 6c. Paper-shadow scan: all configured pairs are scanned regardless of
        # live_pairs. Non-live pairs are routed to PaperExecutor at execution time
        # (see execution_engine/engine.py). This lets USD_JPY generate shadow signals
        # while USD_CAD runs live. Startup filter removed — DB mode is not yet loaded
        # at this point so effective_trading_mode() always returns PAPER here.
        paper_only = [p for p in self.config.pairs if p not in self.config.live_pairs]
        if paper_only:
            logger.info(
                "paper_shadow_pairs_active",
                paper_only_pairs=paper_only,
                live_pairs=self.config.live_pairs,
                note="these pairs scan but execution routes to PaperExecutor",
            )

        # 7. Initialize trading components (import here to avoid circular deps)
        from .ai_brain.claude_client import ClaudeClient
        from .ai_brain.consensus_engine import ConsensusEngine
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
        self.consensus = ConsensusEngine(self.config)
        self.scanner = SignalScanner(
            self.config, self.data_eng, self.db, self.claude, self.subagents,
            events=self.events,
        )
        self.risk_eng = RiskEngine(
            self.config, self.state, self.db, events=self.events,
        )
        # Initialize Capital.com client for gold/metals (if configured)
        capital_client = None
        if self.config.capital_api_key and self.config.capital_identifier:
            from .infrastructure.capital_client import CapitalComClient
            capital_client = CapitalComClient(self.config)
            logger.info("capital_client_initialized")
            # Re-add XAU_USD to pairs if it was removed by OANDA validation
            if "XAU_USD" not in self.config.pairs:
                self.config.pairs.append("XAU_USD")
                logger.info("xau_usd_restored_via_capital", pairs=self.config.pairs)

        self.exec_eng = ExecutionEngine(
            self.config, self.oanda_trade, self.state, self.db,
            self.alerts, self.subagents,
            oanda_read_client=self.oanda,
            events=self.events,
            capital_client=capital_client,
        )
        self.risk_eng._circuit_breaker = self.exec_eng._circuit_breaker
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
            asyncio.create_task(
                self._periodic_reconciliation(), name="reconciliation"
            ),
        ]

        await self._log_startup_diagnostics()
        logger.info("lumitrade_running", mode=self.config.trading_mode)
        await self.alerts.send_info(
            f"Lumitrade started ({self.config.trading_mode} mode) "
            f"on {self.config.instance_id}"
        )

    async def _log_startup_diagnostics(self) -> None:
        """One-shot snapshot of dual-switch + OANDA wiring at boot.

        The risk engine loads `db_mode_override` lazily on first scan, so
        a fresh process always reports `effective_mode=PAPER` from
        `config.effective_trading_mode()` until then. This handler reads
        the dashboard toggle directly from the settings row so the
        operator sees what mode the FIRST SCAN will actually use, not
        the safe-default returned mid-boot.
        """
        env_mode = self.config.trading_mode

        db_dashboard_mode: str = "unknown"
        settings_row_present = False
        try:
            row = await self.db.select_one(
                "system_state", {"id": "settings"}
            )
            if row and isinstance(row.get("open_trades"), dict):
                settings_row_present = True
                db_dashboard_mode = row["open_trades"].get("mode", "PAPER")
            else:
                db_dashboard_mode = "missing_or_malformed"
        except Exception as e:
            db_dashboard_mode = f"fetch_failed: {type(e).__name__}"

        will_be_effective = (
            "LIVE"
            if (env_mode == "LIVE" and db_dashboard_mode == "LIVE")
            else "PAPER"
        )

        balance: str = "unknown"
        try:
            acct = await self.oanda.get_account_summary_for_pairs(self.config.pairs)
            balance = str(acct.get("balance", "0"))
        except Exception as e:
            balance = f"fetch_failed: {type(e).__name__}"

        kill_switch = bool(
            self.state
            and self.state._state.get("kill_switch_active", False)
        )

        force_paper = bool(getattr(self.config, "force_paper_mode", False))
        # Lockdown wins over both switches — surface the actual gate the
        # execution engine will use, not just the dual-switch result.
        effective_with_lockdown = "PAPER" if force_paper else will_be_effective

        logger.info(
            "startup_diagnostics",
            env_trading_mode=env_mode,
            db_dashboard_mode=db_dashboard_mode,
            settings_row_present=settings_row_present,
            force_paper_mode=force_paper,
            effective_mode_at_first_scan=effective_with_lockdown,
            oanda_environment=self.config.oanda_environment,
            oanda_endpoint=self.config.oanda_base_url,
            oanda_account_id=self.config.oanda_account_id,
            oanda_balance=balance,
            pairs=self.config.pairs,
            live_pairs=self.config.live_pairs,
            kill_switch_active=kill_switch,
            signal_interval_min=self.config.signal_interval_minutes,
        )

    async def _validate_tradeable_instruments(self) -> set[str]:
        """Check OANDA account for tradeable instruments. Returns set of tradeable pair names."""
        import httpx
        account_ids = {
            self.config.account_id_for(pair)
            for pair in self.config.pairs
        }
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.config.oanda_api_key_data}"},
            timeout=10.0, verify=True,
        ) as client:
            tradeable = set()
            for account_id in account_ids:
                url = f"{self.config.oanda_base_url}/v3/accounts/{account_id}/instruments"
                resp = await client.get(url)
                resp.raise_for_status()
                instruments = resp.json().get("instruments", [])
                for inst in instruments:
                    name = inst.get("name", "")
                    if name in self.config.pairs:
                        tradeable.add(name)
                        logger.info(
                            "instrument_tradeable",
                            pair=name,
                            account_id=account_id,
                            type=inst.get("type", ""),
                        )
            return tradeable

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

    @staticmethod
    def _is_market_open() -> bool:
        """Check if forex market is open.
        Forex closes Friday ~22:00 UTC and reopens Sunday ~22:00 UTC.
        Also closed daily 22:00-22:05 UTC for maintenance."""
        now = datetime.now(timezone.utc)
        weekday = now.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        hour = now.hour

        # Saturday: always closed
        if weekday == 5:
            return False
        # Sunday: closed until 22:00 UTC
        if weekday == 6 and hour < 22:
            return False
        # Friday: closed after 22:00 UTC
        if weekday == 4 and hour >= 22:
            return False
        return True

    async def _signal_to_trade_loop(self) -> None:
        """Full pipeline: scan → risk evaluate → execute if approved."""
        logger.info("signal_to_trade_loop_started", pairs=self.config.pairs)
        try:
            while True:
                # Kill-switch handling MUST be first — before market-hours and
                # weekday-blackout early-continues. Otherwise an HTTP-initiated
                # kill that lands during a market-closed or weekday-blackout
                # window would be deferred until the next "live" tick, leaving
                # positions open through the very condition the operator was
                # responding to.
                if self.state:
                    try:
                        await self.state.refresh_kill_switch_from_db()
                    except Exception:
                        logger.exception("kill_switch_db_refresh_failed")
                if self.state and self.state.kill_switch_active:
                    if not getattr(self, "_kill_switch_handled", False):
                        logger.critical("kill_switch_transition_detected_closing_all")
                        try:
                            result = await self.exec_eng.close_all_positions(
                                reason="kill_switch_activated"
                            )
                            logger.critical(
                                "kill_switch_close_all_complete",
                                attempted=result.get("attempted"),
                                closed=result.get("closed"),
                                failed_count=len(result.get("failed", [])),
                            )
                        except Exception as e:
                            logger.exception(
                                "kill_switch_close_all_raised", error=str(e)
                            )
                        self._kill_switch_handled = True
                    logger.info("kill_switch_active_skipping_scan")
                    await asyncio.sleep(self.config.signal_interval_minutes * 60)
                    continue
                else:
                    self._kill_switch_handled = False

                # Check market hours — skip only when ALL active pairs require forex hours.
                # Spot crypto pairs (BTC_USD, ETH_USD) trade 24/7 and must not be
                # blocked by the forex weekend/maintenance closure.
                _has_crypto = any(
                    p in self.config.SPOT_CRYPTO_PAIRS for p in self.config.pairs
                )
                if not _has_crypto and not self._is_market_open():
                    logger.info("market_closed_skipping_scan")
                    await asyncio.sleep(300)  # Check again in 5 minutes
                    continue

                # Weekday blackout — default empty list (no block). Flip on via
                # blocked_weekdays_utc (e.g. [1] for Tue) if a weekday-specific
                # drawdown appears on current pair set. See config.py for
                # audit context.
                current_weekday = datetime.now(timezone.utc).weekday()
                if current_weekday in self.config.blocked_weekdays_utc:
                    logger.info(
                        "weekday_blackout_skipping_scan",
                        weekday=current_weekday,
                        blocked=self.config.blocked_weekdays_utc,
                    )
                    await asyncio.sleep(self.config.signal_interval_minutes * 60)
                    continue

                # Refresh account balance from OANDA every cycle
                try:
                    acct = await self.oanda.get_account_summary_for_pairs(self.config.pairs)
                    if acct and self.state:
                        self.state._state["account_balance"] = str(acct.get("balance", "0"))
                        self.state._state["account_equity"] = str(acct.get("equity", acct.get("NAV", "0")))
                except Exception as _bal_err:
                    logger.debug("balance_refresh_failed", error=str(_bal_err))

                # Daily loss circuit breaker — stop scanning if daily P&L breaches limit.
                # Uses config.daily_loss_limit_pct * balance for a dynamic threshold.
                # Falls back to -$2000 when balance is unavailable (startup race).
                daily_pnl = Decimal(str(self.state._state.get("daily_pnl", "0"))) if self.state else Decimal("0")
                _raw_balance = self.state._state.get("account_balance", "0") if self.state else "0"
                _balance = Decimal(str(_raw_balance or "0"))
                _daily_limit = -(self.config.daily_loss_limit_pct * _balance) if _balance > 0 else Decimal("-2000")
                if daily_pnl < _daily_limit:
                    logger.warning(
                        "daily_loss_limit_hit",
                        daily_pnl=str(daily_pnl),
                        limit=str(_daily_limit),
                        limit_pct=str(self.config.daily_loss_limit_pct),
                    )
                    if self.events:
                        self.events.publish(
                            "RISK", "DAILY_LIMIT",
                            f"Trading paused — daily loss limit hit: ${daily_pnl:.2f} (limit {float(self.config.daily_loss_limit_pct)*100:.1f}%)",
                            severity="ERROR",
                        )
                    await asyncio.sleep(self.config.signal_interval_minutes * 60)
                    continue

                # Session time filter — trade Asian + London + London/NY overlap
                # 00-05 UTC: Asian session (100% WR in 85-trade data)
                # 05-13 UTC: London session (strong)
                # 13-17 UTC: London/NY overlap (peak liquidity, tightest spreads per BIS data)
                # 17-24 UTC: late NY + dead zone (0% WR 18-20 UTC, confirmed by industry research)
                # Spot crypto pairs (BTC_USD) are 24/7 — they bypass this gate.
                current_hour = datetime.now(timezone.utc).hour
                if not _has_crypto and current_hour >= 17:
                    logger.info("session_filter_skip", hour=current_hour, reason="Outside 00-17 UTC (forex only)")
                    await asyncio.sleep(self.config.signal_interval_minutes * 60)
                    continue

                # Per-pair optimal session windows (from data + research)
                _pair_hours = {
                    "USD_JPY": (0, 17),   # Asian + London/NY overlap — JPY active both sessions
                    "USD_CAD": (8, 17),   # London + NY overlap — CAD most liquid during NY
                    "AUD_USD": (0, 8),    # Asian only — best in early session
                    "NZD_USD": (0, 8),    # Asian only — best in early session
                    # All configured spot crypto pairs are 24/7 — no session restriction
                    **{cp: (0, 24) for cp in self.config.SPOT_CRYPTO_PAIRS},
                }

                # (Kill-switch handling moved to the top of the loop body —
                # before market-hours / weekday / session early-continues.)

                for pair in self.config.pairs:

                    # Per-pair session window check
                    pair_window = _pair_hours.get(pair, (0, 13))
                    if not (pair_window[0] <= current_hour < pair_window[1]):
                        logger.debug(
                            "pair_session_skip",
                            pair=pair,
                            hour=current_hour,
                            window=f"{pair_window[0]}-{pair_window[1]}",
                        )
                        continue

                    # Forex pairs additionally obey market hours (no weekend trading).
                    # Spot crypto (BTC_USD, ETH_USD) trades 24/7 — exempt from this gate.
                    if pair not in self.config.SPOT_CRYPTO_PAIRS and not self._is_market_open():
                        logger.debug("pair_market_closed_skip", pair=pair)
                        continue

                    try:
                        # 1. Scan for signal
                        proposal = await self.scanner.execute_scan(pair)

                        # Record scan time for AI Brain status reporting
                        # (even for HOLD/None — shows scanner is alive)
                        if self.state:
                            signal_times = self.state._state.get("last_signal_at") or {}
                            if not isinstance(signal_times, dict):
                                signal_times = {}
                            signal_times[pair] = datetime.now(timezone.utc).isoformat()
                            self.state._state["last_signal_at"] = signal_times

                        if not proposal:
                            continue
                        if _action_str(proposal.action) == "HOLD":
                            logger.info("signal_hold_skipped", pair=pair)
                            continue

                        # Telemetry: directional signal generated — visible in logs
                        # as "signal_candidate". Track candidate vs executed ratio
                        # to detect regime decay before it shows in P&L.
                        logger.info(
                            "signal_candidate",
                            pair=pair,
                            action=_action_str(proposal.action),
                            confidence=str(proposal.confidence_adjusted),
                        )

                        # 1b. Consensus validation — second Claude opinion
                        try:
                            consensus_context = (
                                f"{pair} | Price: {proposal.entry_price} | "
                                f"Indicators: {proposal.indicators_snapshot}\n"
                                f"Analysis: {proposal.summary}"
                            )
                            proposal = await self.consensus.validate(
                                proposal, market_context=consensus_context,
                            )
                            logger.info(
                                "consensus_complete",
                                pair=pair,
                                confidence_after=str(proposal.confidence_adjusted),
                            )
                        except Exception as e:
                            logger.warning("consensus_failed", pair=pair, error=str(e))

                        # Confidence threshold is checked by risk engine
                        # (which also accounts for CAUTIOUS state)

                        # 2. Get account balance for risk sizing — route spot crypto
                        # pairs (BTC_USD) to the sub-account so risk sizing uses
                        # the correct equity base, not the main forex account balance.
                        account = await self.oanda.get_account_summary_for(pair)
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
                            rule = getattr(result, "rule_violated", "unknown")
                            current = getattr(result, "current_value", "")
                            threshold = getattr(result, "threshold", "")
                            rejection_text = (
                                f"{rule}: {current} vs {threshold}"
                                if current or threshold
                                else rule
                            )
                            logger.info(
                                "signal_risk_rejected",
                                pair=pair,
                                reason=rule,
                                detail=rejection_text,
                            )
                            # Persist rejection reason on the signal row so
                            # the dashboard "Rejected" badge has a why. Without
                            # this, every reject looks identical in the UI.
                            # Codex observability review 2026-04-28.
                            try:
                                await self.db.update(
                                    "signals",
                                    {"id": str(proposal.signal_id)},
                                    {"rejection_reason": rejection_text},
                                )
                            except Exception:
                                logger.warning(
                                    "signal_rejection_reason_save_failed",
                                    signal_id=str(proposal.signal_id),
                                )
                            continue
                        approved = result

                        # 4. Fixed 1x position size — no confidence scaling.
                        #    Data showed 80%+ confidence has WORSE win rate (16.7%)
                        #    than 70-80% (48.1%). Scaling up on high confidence
                        #    was amplifying losses, not gains.
                        num_orders = 1

                        current_price = proposal.entry_price
                        logger.info(
                            "signal_executing_trade",
                            pair=pair,
                            action=_action_str(proposal.action),
                            confidence=str(proposal.confidence_adjusted),
                            price=str(current_price),
                            num_orders=num_orders,
                        )

                        # Execute multiple orders for high-confidence signals
                        from uuid import uuid4 as _uuid4
                        for order_num in range(num_orders):
                            try:
                                if order_num == 0:
                                    # First order uses the original approved order
                                    exec_result = await self.exec_eng.execute_order(approved, current_price)
                                else:
                                    # Subsequent orders get a fresh order_ref
                                    scaled_order = ApprovedOrder(
                                        order_ref=_uuid4(),
                                        signal_id=approved.signal_id,
                                        pair=approved.pair,
                                        direction=approved.direction,
                                        units=approved.units,
                                        entry_price=approved.entry_price,
                                        stop_loss=approved.stop_loss,
                                        take_profit=approved.take_profit,
                                        risk_amount_usd=approved.risk_amount_usd,
                                        risk_pct=approved.risk_pct,
                                        confidence=approved.confidence,
                                        account_balance_at_approval=approved.account_balance_at_approval,
                                        approved_at=datetime.now(timezone.utc),
                                        expiry=datetime.now(timezone.utc) + timedelta(seconds=30),
                                        mode=approved.mode,
                                    )
                                    exec_result = await self.exec_eng.execute_order(scaled_order, current_price)
                                if exec_result is None:
                                    logger.warning(
                                        "trade_execution_failed",
                                        pair=pair,
                                        action=_action_str(proposal.action),
                                        order_num=order_num + 1,
                                    )
                                    self.events.publish(
                                        "EXECUTION", "ORDER_FAILED",
                                        f"FAILED: {_action_str(proposal.action)} {pair} — execution returned None",
                                        severity="ERROR", pair=pair,
                                    )
                                    break
                                logger.info(
                                    "trade_executed_successfully",
                                    pair=pair,
                                    action=_action_str(proposal.action),
                                    order_num=order_num + 1,
                                    total_orders=num_orders,
                                )
                                if order_num == 0:
                                    try:
                                        await self.db.update(
                                            "signals",
                                            {"id": str(proposal.signal_id)},
                                            {"executed": True},
                                        )
                                    except Exception:
                                        pass
                            except Exception as e:
                                logger.error(
                                    "scaled_order_failed",
                                    pair=pair,
                                    order_num=order_num + 1,
                                    error=str(e),
                                )
                                self.events.publish(
                                    "EXECUTION", "ORDER_FAILED",
                                    f"FAILED: {_action_str(proposal.action)} {pair} — {str(e)[:200]}",
                                    severity="ERROR", pair=pair,
                                )
                                break  # Stop scaling if one fails
                            # Small delay between scaled orders
                            if order_num < num_orders - 1:
                                await asyncio.sleep(1)
                    except Exception as e:
                        import traceback
                        logger.error(
                            "signal_to_trade_error",
                            pair=pair,
                            error=str(e),
                            traceback=traceback.format_exc(),
                        )

                    # Stagger between pairs
                    await asyncio.sleep(5)

                # Wait for next scan cycle (read interval from user settings)
                scan_minutes = self.config.signal_interval_minutes
                try:
                    settings_row = await self.db.select_one("system_state", {"id": "settings"})
                    if settings_row and settings_row.get("open_trades") and isinstance(settings_row["open_trades"], dict):
                        scan_minutes = int(settings_row["open_trades"].get("scanInterval", scan_minutes))
                except Exception as _si_err:
                    logger.debug("scan_interval_settings_fetch_failed", error=str(_si_err))
                await asyncio.sleep(scan_minutes * 60)
        except asyncio.CancelledError:
            logger.info("signal_to_trade_loop_cancelled")

    async def _risk_monitor_loop(self) -> None:
        """SA-03: Run risk monitor every 30 minutes while positions open."""
        while True:
            await asyncio.sleep(1800)  # 30 minutes
            # Skip when forex market is closed — but always run when spot crypto
            # pairs are configured (BTC_USD positions need monitoring 24/7).
            if not self._is_market_open() and not any(
                p in self.config.SPOT_CRYPTO_PAIRS for p in self.config.pairs
            ):
                continue
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
                        # Bug fix (Track 6 follow-up): was self.oanda_data which
                        # is never assigned. The correct attribute is self.oanda
                        # (the OandaClient instantiated in __init__). The typo
                        # was masked by the broad except below — risk-monitor
                        # subagent always ran with empty prices.
                        pricing = await self.oanda.get_pricing(pairs_in_trades)
                        prices = {}
                        for p in pricing.get("prices", []):
                            inst = p.get("instrument", "")
                            bids = p.get("bids", [])
                            asks = p.get("asks", [])
                            if bids and asks:
                                mid = (float(bids[0]["price"]) + float(asks[0]["price"])) / 2
                                prices[inst] = mid
                    except Exception as e:
                        logger.warning(
                            "risk_monitor_pricing_fetch_failed",
                            pairs=pairs_in_trades,
                            error=str(e),
                        )
                        prices = {}

                    # Enrich trades with current price
                    enriched = []
                    for t in open_trades:
                        signal = {}
                        signal_id = t.get("signal_id")
                        if signal_id:
                            try:
                                signal = await self.db.select_one(
                                    "signals", {"id": str(signal_id)}
                                ) or {}
                            except Exception as e:
                                logger.warning(
                                    "risk_monitor_signal_fetch_failed",
                                    trade_id=t.get("id", ""),
                                    signal_id=str(signal_id),
                                    error=str(e),
                                )
                        enriched.append({
                            "trade_id": t.get("id", ""),
                            "signal_id": signal_id or "",
                            "pair": t.get("pair", ""),
                            "direction": t.get("direction", ""),
                            "entry_price": t.get("entry_price", 0),
                            "stop_loss": t.get("stop_loss", 0),
                            "take_profit": t.get("take_profit", 0),
                            "current_price": prices.get(t.get("pair", ""), 0),
                            "signal_summary": signal.get("summary", ""),
                            "signal_reasoning": signal.get("reasoning", ""),
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

    async def _periodic_reconciliation(self) -> None:
        """Run position reconciliation every 5 minutes to detect ghost/phantom trades."""
        RECONCILE_INTERVAL = 300  # 5 minutes
        while True:
            try:
                await asyncio.sleep(RECONCILE_INTERVAL)
                # Always reconcile when spot crypto pairs are configured —
                # BTC_USD positions can be opened/closed 24/7 and ghost trades
                # must be detected on weekends too.
                if not self._is_market_open() and not any(
                    p in self.config.SPOT_CRYPTO_PAIRS for p in self.config.pairs
                ):
                    continue
                from .infrastructure.alert_service import AlertService
                from .state.reconciler import PositionReconciler

                reconciler = PositionReconciler(
                    self.db, self.oanda, self.alerts,
                    account_uuid=self.config.account_uuid,
                )
                result = await reconciler.reconcile()

                ghosts = len(result.get("ghosts", []))
                phantoms = len(result.get("phantoms", []))
                if ghosts > 0 or phantoms > 0:
                    logger.warning(
                        "periodic_reconciliation_found_issues",
                        ghosts=ghosts,
                        phantoms=phantoms,
                        matched=len(result.get("matched", [])),
                    )
                else:
                    logger.debug(
                        "periodic_reconciliation_clean",
                        matched=len(result.get("matched", [])),
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("periodic_reconciliation_error", error=str(e))

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

                # account_uuid (DB row identifier), not oanda_account_id
                # — same fix as scanner.py.
                await self.subagents.run_weekly_intelligence(
                    self.config.account_uuid
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
