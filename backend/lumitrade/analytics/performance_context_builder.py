"""
Lumitrade Performance Context Builder
========================================
Builds PerformanceContext from trade history for each signal scan.
Phase 0: Returns empty context (insufficient data).
Per Addition Set 2B.
"""

from decimal import Decimal
from datetime import datetime, timezone, timedelta

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
        self, account_id: str, pair: str, current_atr: Decimal
    ) -> PerformanceContext:
        """Build context. Returns empty defaults if insufficient data."""
        try:
            return await self._build_context(account_id, pair, current_atr)
        except Exception as e:
            logger.warning("performance_context_build_failed", error=str(e))
            return self._empty_context()

    async def _build_context(
        self, account_id: str, pair: str, current_atr: Decimal
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

        return PerformanceContext(
            last_10_win_rate=win_rate,
            last_10_avg_pips=avg_pips,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            current_drawdown_from_peak=Decimal("0"),
            account_growth_this_week=Decimal("0"),
            market_volatility=volatility,
            trend_strength="MODERATE",
            sample_size=len(recent_trades),
            is_sufficient_data=True,
        )

    def _empty_context(self) -> PerformanceContext:
        """Safe default when insufficient data exists."""
        return PerformanceContext()
