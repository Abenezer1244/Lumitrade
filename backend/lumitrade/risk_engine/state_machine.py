"""
Lumitrade Risk State Machine
===============================
7-state finite state machine for risk level management.
Per SAS Section 3.2.5.

States (priority order, highest first):
  EMERGENCY_HALT > WEEKLY_LIMIT > DAILY_LIMIT > CIRCUIT_OPEN >
  NEWS_BLOCK > CAUTIOUS > NORMAL

Transitions are evaluated on every risk check cycle based on
current P&L, consecutive losses, and circuit breaker state.
"""

from ..core.enums import CircuitBreakerState, RiskState
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class RiskStateMachine:
    """Evaluates trading conditions and returns the appropriate RiskState."""

    def __init__(self, state_manager) -> None:
        self._state_manager = state_manager
        self._current_state = RiskState.NORMAL

    @property
    def current_state(self) -> RiskState:
        return self._current_state

    async def evaluate_transitions(
        self,
        daily_pnl_pct: float,
        weekly_pnl_pct: float,
        consecutive_losses: int,
        circuit_breaker_state: CircuitBreakerState,
        daily_loss_limit: float,
        weekly_loss_limit: float,
    ) -> RiskState:
        """
        Evaluate all risk conditions and return the highest-priority
        applicable RiskState.

        Priority (highest first):
          1. EMERGENCY_HALT  — kill switch engaged (external flag)
          2. WEEKLY_LIMIT    — weekly P&L breaches weekly_loss_limit
          3. DAILY_LIMIT     — daily P&L breaches daily_loss_limit
          4. CIRCUIT_OPEN    — circuit breaker is OPEN
          5. NEWS_BLOCK      — handled externally by CalendarGuard
          6. CAUTIOUS        — 3+ consecutive losses OR daily P&L < -2.5%
          7. NORMAL          — all clear

        Args:
            daily_pnl_pct: Today's P&L as a signed decimal (e.g. -0.03 = -3%).
            weekly_pnl_pct: This week's P&L as a signed decimal.
            consecutive_losses: Number of consecutive losing trades.
            circuit_breaker_state: Current circuit breaker FSM state.
            daily_loss_limit: Maximum allowed daily loss (positive, e.g. 0.05 = 5%).
            weekly_loss_limit: Maximum allowed weekly loss (positive, e.g. 0.10 = 10%).

        Returns:
            The highest-priority RiskState that applies.
        """
        previous_state = self._current_state

        # 1. Emergency halt — check external kill switch via state manager
        if await self._is_emergency_halt():
            new_state = RiskState.EMERGENCY_HALT
            self._transition(previous_state, new_state)
            return new_state

        # 2. Weekly loss limit
        if daily_pnl_pct is not None and weekly_pnl_pct is not None:
            if weekly_pnl_pct <= -abs(weekly_loss_limit):
                new_state = RiskState.WEEKLY_LIMIT
                self._transition(previous_state, new_state)
                return new_state

        # 3. Daily loss limit
        if daily_pnl_pct is not None:
            if daily_pnl_pct <= -abs(daily_loss_limit):
                new_state = RiskState.DAILY_LIMIT
                self._transition(previous_state, new_state)
                return new_state

        # 4. Circuit breaker OPEN
        if circuit_breaker_state == CircuitBreakerState.OPEN:
            new_state = RiskState.CIRCUIT_OPEN
            self._transition(previous_state, new_state)
            return new_state

        # 5. NEWS_BLOCK is evaluated externally by CalendarGuard,
        #    so we skip it here — the RiskEngine checks it separately.

        # 6. Cautious — 3+ consecutive losses OR daily P&L worse than -2.5%
        cautious_loss_threshold = -0.025
        if (
            consecutive_losses >= 3
            or (daily_pnl_pct is not None and daily_pnl_pct <= cautious_loss_threshold)
        ):
            new_state = RiskState.CAUTIOUS
            self._transition(previous_state, new_state)
            return new_state

        # 7. All clear
        new_state = RiskState.NORMAL
        self._transition(previous_state, new_state)
        return new_state

    async def _is_emergency_halt(self) -> bool:
        """Check if emergency kill switch is engaged via state manager.

        On read failure: FAIL CLOSED (return True / EMERGENCY_HALT). The
        kill switch is a SAFETY contract — a transient state-manager error
        must NOT allow trading to continue. This harmonizes with
        ``StateManager.refresh_kill_switch_from_db`` which already fails
        closed on the same read. Recovery is automatic on the next
        successful evaluate cycle once the state manager is healthy.
        """
        if self._state_manager is None:
            return False
        try:
            kill_switch = getattr(self._state_manager, "kill_switch_active", False)
            if callable(kill_switch):
                return await kill_switch()
            return bool(kill_switch)
        except Exception:
            # Fail-closed for safety — read failure must not allow trading.
            logger.error(
                "kill_switch_read_failed_blocking_trading",
                exc_info=True,
            )
            return True

    def _transition(self, old: RiskState, new: RiskState) -> None:
        """Log state transitions and update internal state."""
        if old != new:
            logger.info(
                "risk_state_transition",
                old_state=old.value,
                new_state=new.value,
            )
        self._current_state = new
