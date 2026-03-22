"""
Lumitrade Risk Engine
=======================
Core risk evaluation pipeline. Receives a SignalProposal from the AI Brain,
runs 8 sequential risk checks, and either approves (ApprovedOrder) or
rejects (RiskRejection) the trade.

Per BDS Section 6.1 + Addition Set 2E (adaptive position sizing).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from ..config import LumitradeConfig
from ..core.enums import Action, Direction, RiskState, TradingMode
from ..core.models import ApprovedOrder, RiskRejection, SignalProposal
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from .calendar_guard import CalendarGuard
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
    ) -> None:
        self._config = config
        self._state_manager = state_manager
        self._db = db
        self._position_sizer = PositionSizer()
        self._calendar_guard = CalendarGuard()

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

        # ── Check 3: Cooldown ────────────────────────────────────
        result = await self._check_cooldown(proposal.pair)
        checks.append(result)
        if not result[1]:
            return await self._reject(proposal, result, risk_state, now)

        # ── Check 4: Confidence ──────────────────────────────────
        result = self._check_confidence(proposal, risk_state)
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

        # ── All checks passed — calculate position size ──────────
        risk_pct = self._determine_risk_pct(proposal)
        units, risk_amount_usd = self._position_sizer.calculate(
            balance=account_balance,
            risk_pct=risk_pct,
            entry=proposal.entry_price,
            stop_loss=proposal.stop_loss,
            pair=proposal.pair,
        )

        # Minimum position size gate
        if units < 1000:
            min_result: CheckResult = (
                "MINIMUM_POSITION_SIZE",
                False,
                "Calculated position size below minimum 1000 units",
                str(units),
                "1000",
            )
            return await self._reject(proposal, min_result, risk_state, now)

        # ── Build ApprovedOrder ──────────────────────────────────
        direction = Direction.BUY if proposal.action == Action.BUY else Direction.SELL
        mode = TradingMode(self._config.trading_mode)

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
        """Check 2: Max open positions not exceeded."""
        max_positions = self._config.max_open_trades
        try:
            current_count = await self._db.count(
                "open_positions", {"status": "OPEN"},
            )
        except Exception:
            # If DB unavailable, assume 0 — fail-open on read
            logger.warning("position_count_db_error", msg="Could not query open positions")
            current_count = 0

        passed = current_count < max_positions
        return (
            "POSITION_COUNT",
            passed,
            "OK" if passed else f"Max {max_positions} positions reached",
            str(current_count),
            str(max_positions),
        )

    async def _check_cooldown(self, pair: str) -> CheckResult:
        """Check 3: Enforce cooldown period per pair."""
        cooldown_minutes = self._config.trade_cooldown_minutes
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
        try:
            recent = await self._db.select(
                "trades",
                {"pair": pair},
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
                        minutes_ago = int(
                            (datetime.now(timezone.utc) - last_closed_dt).total_seconds() / 60
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
            "OK" if passed else f"Confidence {proposal.confidence_adjusted} < {threshold}",
            str(proposal.confidence_adjusted),
            str(threshold),
        )

    def _check_spread(self, proposal: SignalProposal) -> CheckResult:
        """Check 5: Spread must be within acceptable limit."""
        max_spread = self._config.max_spread_pips
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
        """Check 7: Minimum risk/reward ratio."""
        min_rr = self._config.min_rr_ratio

        entry = proposal.entry_price
        sl = proposal.stop_loss
        tp = proposal.take_profit

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
            "OK" if passed else f"Action is {proposal.action.value}, expected BUY or SELL",
            proposal.action.value,
            "BUY or SELL",
        )

    # ── Position Sizing (Addition Set 2E) ────────────────────────

    def _determine_risk_pct(self, proposal: SignalProposal) -> Decimal:
        """
        Determine the risk percentage for position sizing.

        Per Addition Set 2E:
          - If AI recommended_risk_pct is present and performance data is
            sufficient: use AI recommendation, clamped to [0.25%, 2.0%].
          - Otherwise: standard confidence-based tiers:
              * confidence >= 0.90 -> 2.0%
              * confidence >= 0.80 -> 1.0%
              * else              -> 0.5%
        """
        min_risk = Decimal("0.0025")  # 0.25%
        max_risk = Decimal("0.02")    # 2.0%

        # Check for AI-recommended risk with sufficient performance data
        if proposal.recommended_risk_pct is not None:
            clamped = max(min_risk, min(max_risk, proposal.recommended_risk_pct))
            logger.info(
                "risk_pct_ai_recommended",
                raw=str(proposal.recommended_risk_pct),
                clamped=str(clamped),
            )
            return clamped

        # Standard confidence-based tiers
        confidence = proposal.confidence_adjusted
        if confidence >= Decimal("0.90"):
            risk_pct = Decimal("0.02")   # 2.0%
        elif confidence >= Decimal("0.80"):
            risk_pct = Decimal("0.01")   # 1.0%
        else:
            risk_pct = Decimal("0.005")  # 0.5%

        logger.info(
            "risk_pct_confidence_based",
            confidence=str(confidence),
            risk_pct=str(risk_pct),
        )
        return risk_pct

    # ── Helpers ───────────────────────────────────────────────────

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
                "signal_id": str(proposal.signal_id),
                "pair": proposal.pair,
                "event_type": "REJECTION",
                "rule_violated": rule_name,
                "current_value": current_value,
                "threshold": threshold,
                "risk_state": risk_state.value,
                "reason": reason,
                "created_at": now.isoformat(),
            })
        except Exception:
            logger.warning(
                "risk_event_log_failed",
                signal_id=str(proposal.signal_id),
                rule=rule_name,
            )

        return rejection
