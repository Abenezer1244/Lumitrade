"""
Lumitrade Risk Engine
=======================
Core risk evaluation pipeline. Receives a SignalProposal from the AI Brain,
runs 8 sequential risk checks, and either approves (ApprovedOrder) or
rejects (RiskRejection) the trade.

Per BDS Section 6.1 + Addition Set 2E (adaptive position sizing).
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from ..config import LumitradeConfig
from ..core.enums import Action, Direction, RiskState, TradingMode
from ..core.models import ApprovedOrder, RiskRejection, SignalProposal
from ..infrastructure.db import DatabaseClient
from ..infrastructure.event_publisher import EventPublisher
from ..infrastructure.secure_logger import get_logger
from ..utils.pip_math import pip_value_per_unit, pips_between
from .calendar_guard import CalendarGuard
from .correlation_matrix import CorrelationMatrix
from .position_sizer import PositionSizer

logger = get_logger(__name__)

# Type alias for individual check results
CheckResult = tuple[str, bool, str, str, str]
# (rule_name, passed, reason, current_value, threshold)


class RiskEngine:
    """
    Evaluate trading signals against 8 risk checks.
    First failure = immediate rejection with reason logged.
    """

    def __init__(
        self,
        config: LumitradeConfig,
        state_manager,
        db: DatabaseClient,
        events: EventPublisher | None = None,
    ) -> None:
        self._config = config
        self._state_manager = state_manager
        self._db = db
        self._events = events
        self._position_sizer = PositionSizer()
        self._calendar_guard = CalendarGuard()
        self._correlation_matrix = CorrelationMatrix()

    async def evaluate(
        self,
        proposal: SignalProposal,
        account_balance: Decimal,
    ) -> ApprovedOrder | RiskRejection:
        """
        Run 8 sequential risk checks on a signal proposal.

        Args:
            proposal: AI-generated signal to evaluate.
            account_balance: Current account balance in USD.

        Returns:
            ApprovedOrder if all checks pass, RiskRejection on first failure.
        """
        now = datetime.now(timezone.utc)
        await self._load_user_settings()
        risk_state = await self._get_current_risk_state()

        checks: list[CheckResult] = []

        # ── Check 1: Risk State ──────────────────────────────────
        result = self._check_risk_state(risk_state)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 2: Position Count ──────────────────────────────
        result = await self._check_position_count()
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 2b: Per-Pair Position Count ──────────────────
        result = await self._check_position_count_per_pair(proposal.pair)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 3: Cooldown ────────────────────────────────────
        result = await self._check_cooldown(proposal.pair)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 4: Confidence (floor) ──────────────────────────
        result = self._check_confidence(proposal, risk_state)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 4b: Confidence Ceiling ─────────────────────────
        result = self._check_confidence_ceiling(proposal)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 4c: No-Trade Hours ────────────────────────────
        result = self._check_no_trade_hours(now)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 5: Spread ──────────────────────────────────────
        result = self._check_spread(proposal)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 6: News Blackout ───────────────────────────────
        result = await self._check_news(proposal)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 7: Risk/Reward Ratio ───────────────────────────
        result = self._check_rr_ratio(proposal)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 8: Action ──────────────────────────────────────
        result = self._check_action(proposal)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── All checks passed — publish approval event ────────────
        if self._events:
            self._events.publish(
                "RISK_ENGINE", "RISK_CHECK",
                f"APPROVED {proposal.pair} — all {len(checks)} checks passed",
                pair=proposal.pair, severity="SUCCESS",
                metadata={
                    "checks_passed": len(checks),
                    "signal_id": str(proposal.signal_id),
                },
            )

        # ── Calculate position size ────────────────────────────────
        risk_pct = self._determine_risk_pct(proposal)
        units, risk_amount_usd = self._position_sizer.calculate(
            balance=account_balance,
            risk_pct=risk_pct,
            entry=proposal.entry_price,
            stop_loss=proposal.stop_loss,
            pair=proposal.pair,
        )

        # ── Correlation adjustment ─────────────────────────────────
        # Reduce position size when correlated pairs are already open.
        open_pairs = await self._get_open_pairs()
        corr_multiplier = self._correlation_matrix.get_position_size_multiplier(
            open_pairs=open_pairs,
            new_pair=proposal.pair,
        )
        is_metal = proposal.pair.startswith("XAU") or proposal.pair.startswith("XAG")
        if corr_multiplier < Decimal("1.0"):
            original_units = units
            units = int(Decimal(str(units)) * corr_multiplier)
            # OANDA accepts integer units down to 1 for both forex and
            # metals. The previous "round to 1000-unit micro lot" logic
            # was a holdover from broker-conflation that zeroed out
            # small-account corrections — dropped in the two-gate
            # rework (Claude + Codex 2026-04-27).
            if units < 0:
                units = 0
            risk_amount_usd = risk_amount_usd * corr_multiplier
            logger.info(
                "correlation_units_reduced",
                pair=proposal.pair,
                original_units=original_units,
                adjusted_units=units,
                multiplier=str(corr_multiplier),
                open_correlated_pairs=open_pairs,
            )

        # Maximum position size cap
        max_units = self._config.max_position_units
        if units > max_units:
            logger.info(
                "position_size_capped",
                original_units=units,
                capped_units=max_units,
                pair=proposal.pair,
            )
            sl_pips = pips_between(proposal.entry_price, proposal.stop_loss, proposal.pair)
            pv = pip_value_per_unit(proposal.pair, proposal.entry_price)
            units = max_units
            risk_amount_usd = Decimal(str(units)) * sl_pips * pv

        # Publish position sizing result
        if self._events:
            self._events.publish(
                "RISK_ENGINE", "POSITION_SIZE",
                f"{proposal.pair}: {units} units @ {risk_pct*100:.1f}% risk"
                f" (corr: {corr_multiplier})",
                pair=proposal.pair, severity="INFO",
                metadata={
                    "units": units,
                    "risk_pct": str(risk_pct),
                    "risk_usd": str(risk_amount_usd),
                    "correlation_multiplier": str(corr_multiplier),
                },
            )

        # ── Two-gate position sizing (Claude + Codex review 2026-04-27)
        #
        # Gate A — broker feasibility. OANDA accepts integer units >=1
        # for both forex and metals. This guard enforces ONLY what the
        # broker requires; policy decisions live in Gate B.
        min_units = 1 if is_metal else self._config.min_position_units_forex
        if units < min_units:
            min_result: CheckResult = (
                "MINIMUM_POSITION_SIZE",
                False,
                f"Calculated position size {units} below broker minimum "
                f"{min_units} units",
                str(units),
                str(min_units),
            )
            return await self._reject(proposal, min_result, risk_state, now)

        # Gate B — policy meaningfulness. A trade with so little risk
        # budget that operational cost (Claude API call ~$0.02, DB rows,
        # OANDA REST quota, log volume) outweighs any plausible P&L is
        # not worth executing. Configurable via MIN_MEANINGFUL_RISK_USD.
        # This is what the old hard-coded 1000-unit floor was actually
        # trying to express, but it was encoded as a broker constraint.
        min_risk_usd = self._config.min_meaningful_risk_usd
        if risk_amount_usd < min_risk_usd:
            risk_result: CheckResult = (
                "MIN_RISK_BUDGET",
                False,
                f"Trade risk ${risk_amount_usd} below meaningful "
                f"threshold ${min_risk_usd}",
                str(risk_amount_usd),
                str(min_risk_usd),
            )
            return await self._reject(proposal, risk_result, risk_state, now)

        # ── Build ApprovedOrder ──────────────────────────────────
        direction = Direction.BUY if proposal.action == Action.BUY else Direction.SELL
        # Use effective mode (env + dashboard + force_paper_mode lockdown)
        # so that downstream `_save_trade()` persists the actual execution
        # mode rather than the raw env var. Without this, FORCE_PAPER_MODE
        # routes orders to PaperExecutor but the trades table still gets
        # mode='LIVE' rows, which corrupts analytics and reconciliation.
        # Codex review 2026-04-27 finding #2.
        mode = TradingMode(self._config.effective_trading_mode())

        approved = ApprovedOrder(
            order_ref=uuid4(),
            signal_id=proposal.signal_id,
            pair=proposal.pair,
            direction=direction,
            units=units,
            entry_price=proposal.entry_price,
            stop_loss=proposal.stop_loss,
            take_profit=proposal.take_profit,
            risk_amount_usd=risk_amount_usd,
            risk_pct=risk_pct,
            confidence=proposal.confidence_adjusted,
            account_balance_at_approval=account_balance,
            approved_at=now,
            expiry=now + timedelta(seconds=30),
            mode=mode,
        )

        logger.info(
            "risk_approved",
            signal_id=str(proposal.signal_id),
            pair=proposal.pair,
            units=units,
            risk_pct=str(risk_pct),
            risk_usd=str(risk_amount_usd),
            checks_passed=len(checks),
        )

        return approved

    # ── Individual Risk Checks ───────────────────────────────────

    def _check_risk_state(self, risk_state: RiskState) -> CheckResult:
        """Check 1: Reject if risk state blocks trading."""
        blocked_states = {
            RiskState.EMERGENCY_HALT,
            RiskState.WEEKLY_LIMIT,
            RiskState.DAILY_LIMIT,
            RiskState.CIRCUIT_OPEN,
        }
        passed = risk_state not in blocked_states
        return (
            "RISK_STATE",
            passed,
            f"Risk state is {risk_state.value}" if not passed else "OK",
            risk_state.value,
            "NORMAL or CAUTIOUS or NEWS_BLOCK",
        )

    async def _check_position_count(self) -> CheckResult:
        """Check 2: Max open positions not exceeded.
        Scoped to this account_id — prevents one account's open trades from
        blocking another account. In LIVE mode, shadow trades (PAPER_SHADOW)
        are excluded — they have no broker exposure and must not consume slots."""
        max_positions = self._config.max_open_trades
        try:
            filters: dict = {"status": "OPEN", "account_id": self._config.account_uuid}
            if self._config.effective_trading_mode() == "LIVE":
                filters["mode"] = "LIVE"
            current_count = await self._db.count("trades", filters)
        except Exception:
            # Fail-CLOSED: if DB unavailable, block trading
            logger.warning(
                "position_count_db_error",
                msg="Could not query open trades — blocking",
            )
            current_count = max_positions

        passed = current_count < max_positions
        return (
            "POSITION_COUNT",
            passed,
            "OK" if passed else f"Max {max_positions} positions reached ({current_count} open)",
            str(current_count),
            str(max_positions),
        )

    async def _check_position_count_per_pair(self, pair: str) -> CheckResult:
        """Check 2b: Max positions per pair not exceeded (this account only).
        In LIVE mode, shadow trades are excluded from the count."""
        max_per_pair = self._config.max_positions_per_pair
        try:
            filters: dict = {"status": "OPEN", "pair": pair, "account_id": self._config.account_uuid}
            if self._config.effective_trading_mode() == "LIVE":
                filters["mode"] = "LIVE"
            pair_count = await self._db.count("trades", filters)
        except Exception:
            logger.warning(
                "pair_position_count_db_error",
                pair=pair,
                msg="Could not query pair trades — blocking",
            )
            pair_count = max_per_pair

        passed = pair_count < max_per_pair
        return (
            "PAIR_POSITION_COUNT",
            passed,
            "OK" if passed else f"Max {max_per_pair} positions for {pair} reached ({pair_count} open)",
            str(pair_count),
            str(max_per_pair),
        )

    async def _check_cooldown(self, pair: str) -> CheckResult:
        """Check 3: Enforce cooldown period per pair (this account only)."""
        cooldown_minutes = self._config.trade_cooldown_minutes
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
        try:
            recent = await self._db.select(
                "trades",
                {"pair": pair, "account_id": self._config.account_uuid},
                order="closed_at",
                limit=1,
            )
            if recent:
                last_closed = recent[0].get("closed_at")
                if last_closed:
                    if isinstance(last_closed, str):
                        last_closed_dt = datetime.fromisoformat(last_closed)
                    else:
                        last_closed_dt = last_closed
                    if last_closed_dt.tzinfo is None:
                        last_closed_dt = last_closed_dt.replace(tzinfo=timezone.utc)
                    if last_closed_dt > cutoff:
                        elapsed = (
                            datetime.now(timezone.utc) - last_closed_dt
                        )
                        minutes_ago = int(
                            elapsed.total_seconds() / 60
                        )
                        return (
                            "COOLDOWN",
                            False,
                            f"Last trade on {pair} closed {minutes_ago}min ago, "
                            f"cooldown is {cooldown_minutes}min",
                            str(minutes_ago),
                            str(cooldown_minutes),
                        )
        except Exception:
            logger.warning("cooldown_check_db_error", pair=pair)

        return (
            "COOLDOWN",
            True,
            "OK",
            "N/A",
            str(cooldown_minutes),
        )

    def _check_confidence(
        self,
        proposal: SignalProposal,
        risk_state: RiskState,
    ) -> CheckResult:
        """Check 4: Minimum confidence threshold (raised in CAUTIOUS state)."""
        base_threshold = self._config.min_confidence
        # Raise threshold by 10% when cautious
        threshold = (
            base_threshold + Decimal("0.10")
            if risk_state == RiskState.CAUTIOUS
            else base_threshold
        )
        passed = proposal.confidence_adjusted >= threshold
        return (
            "CONFIDENCE",
            passed,
            "OK"
            if passed
            else f"Confidence {proposal.confidence_adjusted} < {threshold}",
            str(proposal.confidence_adjusted),
            str(threshold),
        )

    def _check_confidence_ceiling(
        self, proposal: SignalProposal
    ) -> CheckResult:
        """Check 4b: Reject overconfident signals — 85-trade analysis shows 80%+ has 14% WR."""
        max_conf = self._config.max_confidence
        passed = proposal.confidence_adjusted <= max_conf
        return (
            "CONFIDENCE_CEILING",
            passed,
            "OK"
            if passed
            else f"Confidence {proposal.confidence_adjusted} > {max_conf} ceiling — overconfident signals underperform",
            str(proposal.confidence_adjusted),
            str(max_conf),
        )

    def _check_no_trade_hours(self, now: datetime) -> CheckResult:
        """Check 4c: Block trading during historically unprofitable hours (UTC)."""
        current_hour = now.hour
        blocked = self._config.no_trade_hours_utc
        passed = current_hour not in blocked
        return (
            "NO_TRADE_HOURS",
            passed,
            "OK"
            if passed
            else f"Hour {current_hour}:00 UTC is in no-trade window {blocked} — 0% win rate historically",
            str(current_hour),
            str(blocked),
        )

    # Per-instrument max spread for risk check (in pips)
    _MAX_SPREAD_BY_PAIR: dict[str, Decimal] = {
        "XAU_USD": Decimal("200"),
    }

    def _check_spread(self, proposal: SignalProposal) -> CheckResult:
        """Check 5: Spread must be within acceptable limit."""
        max_spread = self._MAX_SPREAD_BY_PAIR.get(
            proposal.pair, self._config.max_spread_pips
        )
        passed = proposal.spread_pips <= max_spread
        return (
            "SPREAD",
            passed,
            "OK" if passed else f"Spread {proposal.spread_pips} > max {max_spread}",
            str(proposal.spread_pips),
            str(max_spread),
        )

    async def _check_news(self, proposal: SignalProposal) -> CheckResult:
        """Check 6: News blackout via CalendarGuard."""
        is_blocked = await self._calendar_guard.is_blackout(
            pair=proposal.pair,
            news_events=proposal.news_context,
        )
        return (
            "NEWS_BLACKOUT",
            not is_blocked,
            "Pair in news blackout window" if is_blocked else "OK",
            "BLOCKED" if is_blocked else "CLEAR",
            "CLEAR",
        )

    def _check_rr_ratio(self, proposal: SignalProposal) -> CheckResult:
        """Check 7: Minimum risk/reward ratio. Skip if TP=0 (trailing stop mode)."""
        min_rr = self._config.min_rr_ratio

        entry = proposal.entry_price
        sl = proposal.stop_loss
        tp = proposal.take_profit

        # TP=0 means no fixed TP — trailing stop manages exit (Turtle strategy)
        if tp == Decimal("0"):
            return (
                "RR_RATIO",
                True,
                "OK — trailing stop mode (no fixed TP)",
                "N/A",
                str(min_rr),
            )

        risk_distance = abs(entry - sl)
        reward_distance = abs(tp - entry)

        if risk_distance == Decimal("0"):
            return (
                "RR_RATIO",
                False,
                "Stop loss equals entry price",
                "0",
                str(min_rr),
            )

        rr_ratio = reward_distance / risk_distance
        passed = rr_ratio >= min_rr
        return (
            "RR_RATIO",
            passed,
            "OK" if passed else f"R:R {rr_ratio:.2f} < min {min_rr}",
            f"{rr_ratio:.2f}",
            str(min_rr),
        )

    def _check_action(self, proposal: SignalProposal) -> CheckResult:
        """Check 8: Action must be BUY or SELL (not HOLD)."""
        passed = proposal.action in (Action.BUY, Action.SELL)
        return (
            "ACTION",
            passed,
            "OK"
            if passed
            else f"Action is {(proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action))}, expected BUY or SELL",
            (proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action)),
            "BUY or SELL",
        )

    # ── Position Sizing (Addition Set 2E) ────────────────────────

    def _determine_risk_pct(self, proposal: SignalProposal) -> Decimal:
        """
        Determine the risk percentage for position sizing.

        Uses a deterministic confidence-based schedule only.
        AI recommended_risk_pct is logged for future calibration but does NOT
        override sizing — it has no empirical validation yet and bypassed the
        confidence-band protection (Codex review 2026-04-27 finding #1).

        Confidence tiers (capped by max_confidence=0.80):
          * confidence >= 0.80 -> 1.0%
          * else               -> 0.5%
        """
        confidence = proposal.confidence_adjusted
        if confidence >= Decimal("0.80"):
            risk_pct = Decimal("0.01")   # 1.0%
        else:
            risk_pct = Decimal("0.005")  # 0.5%

        # Log AI recommendation as advisory telemetry only — not applied
        if proposal.recommended_risk_pct is not None:
            logger.info(
                "risk_pct_ai_advisory_not_applied",
                ai_recommended=str(proposal.recommended_risk_pct),
                deterministic=str(risk_pct),
                reason="advisory_only_pending_empirical_validation",
            )

        logger.info(
            "risk_pct_confidence_based",
            confidence=str(confidence),
            risk_pct=str(risk_pct),
        )
        return risk_pct

    # ── User Settings from DB ────────────────────────────────────

    async def _load_user_settings(self) -> None:
        """Load user-adjustable settings from Supabase, fail closed to PAPER on failure.

        Reads:
          - riskPct, maxPositions, maxPerPair, confidence (numeric guardrails)
          - mode ("PAPER" | "LIVE") — written by the dashboard ModeToggle.
            Stored on `config.db_mode_override`. The actual paper/live switch
            is `config.effective_trading_mode()` which ANDs env + db.

        Safety contract (Codex review 2026-04-25 finding #2 — fail-closed):
        - On DB exception → reset db_mode_override to PAPER. Never trust a stale
          LIVE if Supabase is unreachable.
        - On missing/malformed row → reset to PAPER.
        - On invalid `mode` value (not "PAPER"/"LIVE") → reset to PAPER.
        - Numeric guardrails fall back to existing config values on failure.
        Otherwise an outage that follows a LIVE read would silently keep the
        engine in LIVE despite losing the dashboard kill-switch.
        """
        # ── STEP 1: PRE-EMPTIVELY FAIL CLOSED ──────────────────────
        # Codex follow-up review #2: numeric parsing happened AFTER the fail-closed
        # checks but BEFORE db_mode_override was reassigned. A malformed riskPct
        # would raise mid-parse and leave a stale LIVE in memory. Fix: reset to
        # PAPER FIRST, validate the entire payload into local variables, then
        # commit the parsed values to self._config only if every field parsed.
        previous_mode = self._config.db_mode_override
        self._config.db_mode_override = "PAPER"

        # ── STEP 2: READ ───────────────────────────────────────────
        try:
            row = await self._db.select_one("system_state", {"id": "settings"})
        except Exception as e:
            logger.warning(
                "user_settings_load_failed_fail_closed",
                error=str(e),
                previous_mode=previous_mode,
                forced_mode="PAPER",
            )
            return

        # Missing or malformed row — already failed closed at step 1, just log
        if not row or not row.get("open_trades") or not isinstance(row["open_trades"], dict):
            logger.warning(
                "user_settings_malformed_fail_closed",
                row_present=bool(row),
                previous_mode=previous_mode,
                forced_mode="PAPER",
            )
            return

        # ── STEP 3: PARSE TO LOCALS (validate-then-commit) ─────────
        s = row["open_trades"]
        try:
            parsed_risk_pct = Decimal(str(s.get("riskPct", float(self._config.max_risk_pct) * 100))) / Decimal("100")
            parsed_max_open = int(s.get("maxPositions", self._config.max_open_trades))
            parsed_max_per_pair = int(s.get("maxPerPair", self._config.max_positions_per_pair))
            parsed_min_conf = Decimal(str(s.get("confidence", int(self._config.min_confidence * 100)))) / Decimal("100")
        except (TypeError, ValueError, ArithmeticError) as e:
            # Numeric field corrupt (e.g., riskPct: "abc"). Already in PAPER from
            # step 1; don't commit any partial values.
            logger.warning(
                "user_settings_numeric_parse_failed_fail_closed",
                error=str(e),
                previous_mode=previous_mode,
                forced_mode="PAPER",
            )
            return

        raw_mode = s.get("mode")
        if isinstance(raw_mode, str) and raw_mode.upper() in ("PAPER", "LIVE"):
            parsed_mode = raw_mode.upper()
        else:
            parsed_mode = "PAPER"

        # ── STEP 4: COMMIT (everything parsed, safe to mutate config) ──
        self._config.max_risk_pct = parsed_risk_pct
        self._config.max_open_trades = parsed_max_open
        self._config.max_positions_per_pair = parsed_max_per_pair
        self._config.min_confidence = parsed_min_conf

        if parsed_mode != previous_mode:
            logger.info(
                "db_mode_override_changed",
                old=previous_mode,
                new=parsed_mode,
                env_mode=self._config.trading_mode,
                effective=("LIVE" if (self._config.trading_mode == "LIVE" and parsed_mode == "LIVE") else "PAPER"),
            )
        self._config.db_mode_override = parsed_mode

        logger.info(
            "user_settings_loaded",
            max_risk_pct=str(self._config.max_risk_pct),
            max_open_trades=self._config.max_open_trades,
            max_per_pair=self._config.max_positions_per_pair,
            min_confidence=str(self._config.min_confidence),
            db_mode=self._config.db_mode_override,
            effective_mode=self._config.effective_trading_mode(),
        )

    # ── Helpers ───────────────────────────────────────────────────

    async def _get_open_pairs(self) -> list[str]:
        """Return list of currency pairs with currently open positions for THIS
        account only. Used by correlation sizing — without account_id scoping,
        another account's open correlated pair would shrink this account's
        position size. Codex follow-up review #3."""
        try:
            rows = await self._db.select(
                "trades",
                {"status": "OPEN", "account_id": self._config.account_uuid},
            )
            pairs = list({row["pair"] for row in rows if "pair" in row})
            return pairs
        except Exception:
            logger.warning("open_pairs_query_failed", msg="Returning empty list")
            return []

    async def _get_current_risk_state(self) -> RiskState:
        """Read current risk state from state manager."""
        if self._state_manager is None:
            return RiskState.NORMAL
        try:
            state = getattr(self._state_manager, "risk_state", RiskState.NORMAL)
            if callable(state):
                return await state()
            return state
        except Exception:
            logger.warning("risk_state_read_failed", msg="Defaulting to NORMAL")
            return RiskState.NORMAL

    async def _reject(
        self,
        proposal: SignalProposal,
        check_result: CheckResult,
        risk_state: RiskState,
        now: datetime,
    ) -> RiskRejection:
        """Build a RiskRejection and log to risk_events table."""
        rule_name, _passed, reason, current_value, threshold = check_result

        # Publish rejection event to Mission Control
        if self._events:
            self._events.publish(
                "RISK_ENGINE", "RISK_CHECK",
                f"REJECTED {proposal.pair} — {rule_name}: {reason}",
                pair=proposal.pair, severity="WARNING",
                metadata={
                    "rule": rule_name,
                    "current_value": current_value,
                    "threshold": threshold,
                    "signal_id": str(proposal.signal_id),
                },
            )

        rejection = RiskRejection(
            signal_id=proposal.signal_id,
            rule_violated=rule_name,
            current_value=current_value,
            threshold=threshold,
            risk_state=risk_state,
            rejected_at=now,
        )

        logger.info(
            "risk_rejected",
            signal_id=str(proposal.signal_id),
            pair=proposal.pair,
            rule=rule_name,
            reason=reason,
            current_value=current_value,
            threshold=threshold,
            risk_state=risk_state.value,
        )

        # Log rejection to risk_events table
        try:
            await self._db.insert("risk_events", {
                "account_id": str(self._config.account_uuid),
                "signal_id": str(proposal.signal_id),
                "event_type": "REJECTION",
                "risk_state": risk_state.value,
                "detail": json.dumps({
                    "pair": proposal.pair,
                    "rule_violated": rule_name,
                    "current_value": current_value,
                    "threshold": threshold,
                    "reason": reason,
                }),
            })
        except Exception:
            logger.warning(
                "risk_event_log_failed",
                signal_id=str(proposal.signal_id),
                rule=rule_name,
            )

        return rejection
