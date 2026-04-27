"""
SA-01: Market Analyst Subagent
================================
Generates a concise market briefing for a given currency pair
using current indicator data and recent candle history.

Calls Claude to produce a 200-word briefing covering:
- Trend direction
- Key support/resistance levels
- Momentum assessment
- Concerns or risks

Per BDS Section 16.2.
"""

from typing import Any, TypedDict

from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)


class MarketAnalystContext(TypedDict, total=False):
    """Expected shape of the context dict passed to ``MarketAnalystAgent.run``.

    All keys are optional (``total=False``). Annotation-only; runtime is a
    plain ``dict``.
    """

    pair: str
    indicators: dict[str, Any]
    candles: list[dict[str, Any]]


class MarketBriefing(TypedDict, total=False):
    """Return shape of ``MarketAnalystAgent.run``.

    status is always present: "ok" | "error".
    On error, ``error`` describes the failure; ``briefing`` is "".
    """

    status: str
    briefing: str
    error: str

SYSTEM_PROMPT = (
    "You are a senior forex market analyst for an automated trading system. "
    "Provide concise, actionable analysis. No fluff, no disclaimers. "
    "Stick to technical facts from the data provided."
)

USER_PROMPT_TEMPLATE = (
    "Analyze {pair} for a potential trade entry.\n\n"
    "INDICATORS:\n{indicators}\n\n"
    "RECENT CANDLES (last {candle_count}, newest first):\n{candles}\n\n"
    "Provide a concise ~200-word market briefing covering:\n"
    "1. TREND: Current direction and strength\n"
    "2. SUPPORT/RESISTANCE: Key levels from the data\n"
    "3. MOMENTUM: RSI, MACD, or other momentum signals\n"
    "4. CONCERNS: Any red flags or conflicting signals\n\n"
    "Be specific with price levels. No generic advice."
)


class MarketAnalystAgent(BaseSubagent):
    """
    SA-01: Generates a structured market briefing for a currency pair.

    Extracts pair, indicators, and candles from context, then calls Claude
    to produce an actionable briefing. On any error, returns an empty
    briefing string (never raises).
    """

    async def run(self, context: dict) -> dict:
        """
        Produce a market briefing from context data.

        Args:
            context: Must contain:
                - pair (str): e.g. "EUR_USD"
                - indicators (dict): current indicator values
                - candles (list[dict]): recent OHLCV candle data

        Returns:
            {"briefing": str} — the analysis text, or "" on error.
        """
        pair: str = context.get("pair", "")
        indicators: dict = context.get("indicators", {})
        candles: list = context.get("candles", [])

        if not pair:
            logger.warning("market_analyst_missing_pair")
            return {"status": "error", "error": "missing_pair", "briefing": ""}

        try:
            indicators_str = self._format_indicators(indicators)
            candles_str = self._format_candles(candles)

            user_prompt = USER_PROMPT_TEMPLATE.format(
                pair=pair,
                indicators=indicators_str,
                candle_count=len(candles),
                candles=candles_str,
            )

            response = await self._call_claude(
                system=SYSTEM_PROMPT,
                user=user_prompt,
            )

            if not response:
                logger.warning("market_analyst_empty_response", pair=pair)
                return {"status": "error", "error": "empty_response", "briefing": ""}

            logger.info(
                "market_analyst_briefing_generated",
                pair=pair,
                briefing_length=len(response),
            )
            return {"status": "ok", "briefing": response}

        except Exception as e:
            logger.error("market_analyst_error", pair=pair, error=str(e))
            return {"status": "error", "error": str(e), "briefing": ""}

    @staticmethod
    def _format_indicators(indicators: dict) -> str:
        """Format indicator dict into a readable string for the prompt."""
        if not indicators:
            return "No indicator data available."

        lines: list[str] = []
        for key, value in indicators.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _format_candles(candles: list) -> str:
        """Format candle list into a compact string for the prompt."""
        if not candles:
            return "No candle data available."

        lines: list[str] = []
        for i, candle in enumerate(candles[:30]):  # Cap at 30 to limit token usage
            if isinstance(candle, dict):
                o = candle.get("open", "?")
                h = candle.get("high", "?")
                l = candle.get("low", "?")
                c = candle.get("close", "?")
                v = candle.get("volume", "?")
                t = candle.get("time", f"candle_{i}")
                lines.append(f"  {t}: O={o} H={h} L={l} C={c} V={v}")
            else:
                lines.append(f"  {candle}")
        return "\n".join(lines)
