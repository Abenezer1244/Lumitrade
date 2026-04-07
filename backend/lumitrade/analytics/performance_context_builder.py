"""
Lumitrade Performance Context Builder
========================================
Builds PerformanceContext from trade history for each signal scan.
Phase 0: Returns empty context (insufficient data).
Per Addition Set 2B.
"""

from decimal import Decimal

from ..core.models import PerformanceContext
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

MIN_TRADES_FOR_CONTEXT = 20


class PerformanceContextBuilder:
    """Builds PerformanceContext from the trade history database."""

    def __init__(self, db: DatabaseClient):
        self.db = db

    async def build(
        self, account_id: str, pair: str, current_atr: Decimal, indicators=None
    ) -> PerformanceContext:
        """Build context. Returns empty defaults if insufficient data."""
        try:
            return await self._build_context(account_id, pair, current_atr, indicators)
        except Exception as e:
            logger.warning("performance_context_build_failed", error=str(e))
            return self._empty_context()

    async def _build_context(
        self, account_id: str, pair: str, current_atr: Decimal, indicators=None
    ) -> PerformanceContext:
        """Build full context from trade history."""
        recent_trades = await self.db.select(
            "trades",
            {"account_id": account_id, "status": "CLOSED"},
            order="closed_at",
            limit=10,
        )

        if len(recent_trades) < MIN_TRADES_FOR_CONTEXT:
            return self._empty_context()

        wins = sum(1 for t in recent_trades if t.get("outcome") == "WIN")
        win_rate = Decimal(str(wins)) / Decimal("10")

        pnl_values = [
            Decimal(str(t["pnl_pips"]))
            for t in recent_trades
            if t.get("pnl_pips") is not None
        ]
        avg_pips = (
            sum(pnl_values) / Decimal(str(len(pnl_values)))
            if pnl_values
            else Decimal("0")
        )

        consecutive_wins = 0
        consecutive_losses = 0
        for t in reversed(recent_trades):
            if t.get("outcome") == "WIN":
                if consecutive_losses > 0:
                    break
                consecutive_wins += 1
            elif t.get("outcome") == "LOSS":
                if consecutive_wins > 0:
                    break
                consecutive_losses += 1
            else:
                break

        if current_atr < Decimal("0.0005"):
            volatility = "LOW"
        elif current_atr > Decimal("0.0015"):
            volatility = "HIGH"
        else:
            volatility = "NORMAL"

        # Derive trend_strength from EMA alignment (20/50/200)
        if indicators and indicators.ema_20 and indicators.ema_50 and indicators.ema_200:
            if indicators.ema_20 > indicators.ema_50 > indicators.ema_200:
                trend_strength = "STRONG"  # All EMAs aligned bullish
            elif indicators.ema_20 < indicators.ema_50 < indicators.ema_200:
                trend_strength = "STRONG"  # All EMAs aligned bearish
            elif indicators.ema_20 > indicators.ema_200:
                trend_strength = "MODERATE"  # Short-term above long-term
            else:
                trend_strength = "WEAK"  # EMAs not aligned
        else:
            # Fallback to ATR-based estimate when EMA data unavailable
            if current_atr > Decimal("0.0020"):
                trend_strength = "STRONG"
            elif current_atr < Decimal("0.0008"):
                trend_strength = "WEAK"
            else:
                trend_strength = "MODERATE"

        # Calculate drawdown and weekly growth from system_state
        current_drawdown = Decimal("0")
        account_growth_this_week = Decimal("0")
        try:
            state_row = await self.db.select_one("system_state", {"id": "singleton"})
            if state_row:
                current_balance = Decimal(str(state_row.get("daily_opening_balance", "0")))
                weekly_opening = Decimal(str(state_row.get("weekly_opening_balance", "0")))
                if weekly_opening > 0:
                    account_growth_this_week = (current_balance - weekly_opening) / weekly_opening
                peak_balance = max(current_balance, weekly_opening)
                if peak_balance > 0:
                    current_drawdown = (peak_balance - current_balance) / peak_balance
        except Exception as e:
            logger.warning("drawdown_growth_calc_failed", error=str(e))

        return PerformanceContext(
            last_10_win_rate=win_rate,
            last_10_avg_pips=avg_pips,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            current_drawdown_from_peak=current_drawdown,
            account_growth_this_week=account_growth_this_week,
            market_volatility=volatility,
            trend_strength=trend_strength,
            sample_size=len(recent_trades),
            is_sufficient_data=True,
        )

    def _empty_context(self) -> PerformanceContext:
        """Safe default when insufficient data exists."""
        return PerformanceContext()
