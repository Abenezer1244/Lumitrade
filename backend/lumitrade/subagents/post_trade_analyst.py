"""
SA-02: Post-Trade Analyst Subagent
=====================================
Analyzes recent closed trades to identify patterns, strengths,
and weaknesses. Requires a minimum of 20 trades for statistical
significance.

Returns actionable recommendations: best/worst pair, win/loss
patterns, and one specific improvement recommendation.

Per BDS Section 16.3.
"""

from __future__ import annotations

from ..infrastructure.db import DatabaseClient
from ..infrastructure.event_publisher import EventPublisher
from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a quantitative trading performance analyst. "
    "Analyze the trade history below and identify concrete, actionable patterns. "
    "No generic advice. Be specific about what the data shows."
)

USER_PROMPT_TEMPLATE = (
    "Analyze these {trade_count} recent closed trades:\n\n"
    "{trade_summary}\n\n"
    "Provide analysis covering:\n"
    "1. BEST PAIR: Which pair performed best and why\n"
    "2. WORST PAIR: Which pair performed worst and why\n"
    "3. WIN/LOSS PATTERNS: Any patterns in wins vs losses "
    "(time of day, confidence levels, direction bias)\n"
    "4. ONE RECOMMENDATION: A single, specific, actionable change "
    "to improve performance\n\n"
    "Be data-driven. Reference specific numbers from the trades."
)


class PostTradeAnalystAgent(BaseSubagent):
    """
    SA-02: Analyzes closed trade history for performance patterns.

    Requires minimum 20 trades. Builds a compact trade summary and
    asks Claude to identify best/worst pairs, win/loss patterns,
    and a specific recommendation. On any error or insufficient
    data, returns empty dict (never raises).
    """

    MIN_TRADES: int = 20

    def __init__(self, config, db: DatabaseClient, events: EventPublisher | None = None):
        super().__init__(config)
        self.db = db
        self._events = events

    async def run(self, context: dict) -> dict:
        """
        Analyze recent trade history for patterns.

        Args:
            context: Must contain:
                - recent_trades (list[dict]): closed trades, each with
                  pair, direction, outcome, pnl_pips, confidence

        Returns:
            {"analysis": str, "trade_count": int} on success,
            {} on error or insufficient trades.
        """
        trades: list = context.get("recent_trades", [])

        if len(trades) < self.MIN_TRADES:
            logger.debug(
                "post_trade_analyst_insufficient_trades",
                trade_count=len(trades),
                min_required=self.MIN_TRADES,
            )
            return {}

        try:
            # Use the last 20 trades for analysis
            analysis_trades = trades[-self.MIN_TRADES:]
            trade_summary = self._build_trade_summary(analysis_trades)

            user_prompt = USER_PROMPT_TEMPLATE.format(
                trade_count=len(analysis_trades),
                trade_summary=trade_summary,
            )

            response = await self._call_claude(
                system=SYSTEM_PROMPT,
                user=user_prompt,
            )

            if not response:
                logger.warning("post_trade_analyst_empty_response")
                return {}

            logger.info(
                "post_trade_analysis_generated",
                trade_count=len(analysis_trades),
                analysis_length=len(response),
            )

            # Publish post-trade analysis event to Mission Control
            if self._events:
                self._events.publish(
                    "SA-02",
                    "ANALYSIS",
                    f"Post-trade analysis on {len(analysis_trades)} trades",
                    detail=response[:500],
                    metadata={
                        "trade_count": len(analysis_trades),
                        "analysis_length": len(response),
                    },
                )

            return {
                "analysis": response,
                "trade_count": len(analysis_trades),
            }

        except Exception as e:
            logger.error("post_trade_analyst_error", error=str(e))
            return {}

    @staticmethod
    def _build_trade_summary(trades: list) -> str:
        """Build a compact string summary of trades for the prompt."""
        lines: list[str] = []
        for i, trade in enumerate(trades, start=1):
            pair = trade.get("pair", "UNKNOWN")
            direction = trade.get("direction", "?")
            outcome = trade.get("outcome", "?")
            pnl_pips = trade.get("pnl_pips", "?")
            confidence = trade.get("confidence", "?")

            lines.append(
                f"  #{i}: {pair} {direction} | "
                f"Result: {outcome} | "
                f"P&L: {pnl_pips} pips | "
                f"Confidence: {confidence}"
            )
        return "\n".join(lines)
