"""
Lumitrade Prompt Builder
==========================
Assembles the system prompt and dynamic user prompt for Claude API.
Includes injection prevention for external text (news titles).
Per BDS Section 5.1 + SS Section 4.2 + Addition Sets 1B and 2C.
"""

import re

from ..core.models import MarketSnapshot, NewsEvent, PerformanceContext, TradeSummary
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# ── Injection prevention ───────────────────────────────────────
MAX_NEWS_TITLE_LEN = 100
ALLOWED_CHARS = re.compile(r"[^a-zA-Z0-9 .,\-()%/]")

SYSTEM_PROMPT = """You are Lumitrade's professional forex trading analyst.
Your role: analyze multi-timeframe market data and generate high-probability
trading signals with disciplined risk management.

CRITICAL RULES:
1. Respond ONLY with valid JSON matching the exact schema below.
2. No text outside the JSON object. No markdown. No code fences.
3. If conditions are unclear or conflicting — return action: HOLD.
4. Never force a trade. Capital preservation over opportunity.
5. confidence must reflect genuine conviction — never inflate it.

REQUIRED JSON SCHEMA:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "entry_price": float,
  "stop_loss": float,
  "take_profit": float,
  "recommended_risk_pct": 0.0025-0.02,
  "risk_reasoning": "1-2 sentences explaining position size recommendation",
  "summary": "2-4 plain English sentences. No jargon.",
  "reasoning": "Full technical analysis. Min 100 words. Cite values.",
  "timeframe_h4_score": 0.0-1.0,
  "timeframe_h1_score": 0.0-1.0,
  "timeframe_m15_score": 0.0-1.0,
  "key_levels": [float, float],
  "invalidation_level": float,
  "expected_duration": "SCALP" | "INTRADAY" | "SWING"
}"""


class PromptBuilder:
    """Assembles prompts for Claude API signal generation."""

    def __init__(self, db=None, account_id: str = ""):
        self.db = db
        self.account_id = account_id

    def get_system_prompt(self) -> str:
        """Return the static system prompt."""
        return SYSTEM_PROMPT

    async def build_prompt(self, snapshot: MarketSnapshot, analyst_briefing: str = "") -> str:
        """Assemble the full user prompt from a MarketSnapshot."""
        ind = snapshot.indicators
        acc = snapshot.account_context

        # Get performance insights (Addition Set 1B)
        perf_insights = await self._get_performance_insights(snapshot.pair)

        # Format performance context (Addition Set 2C)
        perf_context = self._format_performance_context(
            snapshot.performance_context
        )

        sections = [
            "=== MARKET CONTEXT ===",
            f"Pair: {snapshot.pair}",
            f"Session: {snapshot.session.value if hasattr(snapshot.session, 'value') else str(snapshot.session)}",
            f"Timestamp: {snapshot.timestamp.isoformat()}",
            f"Current Bid: {snapshot.bid}  Ask: {snapshot.ask}",
            f"Spread: {snapshot.spread_pips} pips",
            "",
            "=== TECHNICAL INDICATORS ===",
            f"RSI(14): {ind.rsi_14}",
            f"MACD Line: {ind.macd_line} | Signal: "
            f"{ind.macd_signal} | Histogram: {ind.macd_histogram}",
            f"EMA 20: {ind.ema_20} | EMA 50: {ind.ema_50} | EMA 200: {ind.ema_200}",
            f"ATR(14): {ind.atr_14}",
            f"Bollinger Upper: {ind.bb_upper} | "
            f"Mid: {ind.bb_mid} | Lower: {ind.bb_lower}",
            "",
            "=== CANDLE DATA (last 20 candles each timeframe) ===",
            "H4 OHLCV (newest first):",
            _format_candles(snapshot.candles_h4[-20:]),
            "H1 OHLCV (newest first):",
            _format_candles(snapshot.candles_h1[-20:]),
            "M15 OHLCV (newest first):",
            _format_candles(snapshot.candles_m15[-20:]),
            "",
            "=== ECONOMIC CALENDAR (next 4 hours) ===",
            _format_news(snapshot.news_events),
            "",
            "=== ACCOUNT CONTEXT ===",
            f"Balance: ${acc.balance}  Equity: ${acc.equity}",
            f"Open trades: {acc.open_trade_count}  Daily P&L: ${acc.daily_pnl}",
            "",
            "=== PERFORMANCE CONTEXT ===",
            perf_context,
            "",
            "=== RECENT TRADES ON THIS PAIR (last 3) ===",
            _format_recent_trades(snapshot.recent_trades),
            "",
            "=== PERFORMANCE INSIGHTS ===",
            perf_insights,
            "",
            "=== ANALYST BRIEFING (SA-01) ===",
            analyst_briefing if analyst_briefing else "No briefing available.",
            "",
            "=== YOUR TASK ===",
            f"Analyze {snapshot.pair} and return your trading decision as JSON.",
            "Apply multi-timeframe confluence: H4 trend + H1 structure + M15 entry.",
            "Only recommend BUY or SELL if all three timeframes confirm the bias.",
            "Minimum risk/reward ratio: 1.5:1. If not achievable — return HOLD.",
        ]
        return "\n".join(sections)

    async def _get_performance_insights(self, pair: str) -> str:
        """
        Returns recent performance insights for this currency pair.
        Reads from performance_insights table (written by PerformanceAnalyzer + SA-02).
        """
        if not self.db:
            return "  No performance insights available."

        try:
            # Get pair-specific insights
            pair_insights = await self.db.select(
                "performance_insights",
                {"pair": pair, "is_actionable": True},
                order="created_at",
                limit=3,
            )
            # Get general insights (not pair-specific)
            general_insights = await self.db.select(
                "performance_insights",
                {"pair": None, "is_actionable": True},
                order="created_at",
                limit=2,
            )
            insights = pair_insights + general_insights
        except Exception:
            return "  No performance insights available."

        if not insights:
            return "  No performance insights yet — insufficient trade history."

        lines = [f"Performance patterns identified for {pair}:"]
        for insight in insights:
            metric = insight.get("metric_name", "unknown")
            value = insight.get("metric_value", "")
            insight_type = insight.get("insight_type", "")
            recommendation = insight.get("recommendation", "")
            lines.append(f"  - [{insight_type}] {metric}: {value}")
            if recommendation:
                lines.append(f"    Action: {recommendation}")
        return "\n".join(lines)

    def _format_performance_context(self, ctx: PerformanceContext) -> str:
        """Format recent performance context for the AI. Per Addition Set 2C."""
        if not ctx.is_sufficient_data:
            return (
                "  Insufficient trade history for adaptive sizing.\n"
                "  Use standard confidence-based position sizing."
            )

        lines = [
            f"  Recent win rate (last 10 trades): {ctx.last_10_win_rate:.0%}",
            f"  Average pips (last 10 trades):    {ctx.last_10_avg_pips:+.1f}",
            "  Current streak: "
            + (
                f"{ctx.consecutive_wins} consecutive wins"
                if ctx.consecutive_wins > 0
                else (
                    f"{ctx.consecutive_losses} consecutive losses"
                    if ctx.consecutive_losses > 0
                    else "no streak"
                )
            ),
            f"  Account growth this week:          {ctx.account_growth_this_week:+.1%}",
            f"  Market volatility (ATR):           {ctx.market_volatility}",
            f"  Trend strength (EMA alignment):    {ctx.trend_strength}",
            "",
            "  When recommending risk_pct, consider:",
            "  - Win rate >60% + strong trend + low vol -> up to 1.5%",
            "  - Recent win rate below 40% OR 3+ consecutive losses -> cap at 0.5%",
            "  - Default: 0.5% to 1.0% based on signal confidence",
            "  - Hard limits enforced by risk engine: min 0.25%, max 2.0%",
        ]
        return "\n".join(lines)


def _sanitize_news_title(title: str) -> str:
    """Strip characters that could be used for prompt injection. Per SS Section 4.2."""
    sanitized = ALLOWED_CHARS.sub("", title)
    return sanitized[:MAX_NEWS_TITLE_LEN]


def _format_candles(candles: list) -> str:
    """Format candle data for the prompt."""
    if not candles:
        return "  No candle data available."
    lines = []
    for c in reversed(candles):
        lines.append(
            f"  {c.time.strftime('%Y-%m-%d %H:%M')} "
            f"O:{c.open} H:{c.high} L:{c.low} C:{c.close} V:{c.volume}"
        )
    return "\n".join(lines)


def _format_news(events: list[NewsEvent]) -> str:
    """Format news events with injection prevention."""
    if not events:
        return "  No high/medium impact events in next 4 hours."
    lines = []
    for e in events:
        safe_title = _sanitize_news_title(e.title)
        currencies = ",".join(c for c in e.currencies_affected if c.isalpha())
        lines.append(
            f"  [{e.impact.value if hasattr(e.impact, 'value') else str(e.impact)}] {safe_title} ({currencies}) in {e.minutes_until}m"
        )
    return "\n".join(lines)


def _format_recent_trades(trades: list[TradeSummary]) -> str:
    """Format recent trade context."""
    if not trades:
        return "  No recent trades on this pair."
    lines = []
    for t in trades:
        outcome_str = t.outcome.value if hasattr(t.outcome, "value") else str(t.outcome or "OPEN")
        direction_str = t.direction.value if hasattr(t.direction, "value") else str(t.direction)
        lines.append(f"  {direction_str} | {outcome_str} | {t.pnl_pips} pips")
    return "\n".join(lines)
