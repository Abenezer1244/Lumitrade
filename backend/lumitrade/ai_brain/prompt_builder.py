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
  "expected_duration": "SCALP" | "INTRADAY" | "SWING",
  "risks_to_watch": ["string", "string"],
  "signal_alignment_count": 0-5
}

SIGNAL ALIGNMENT RULE:
Before recommending BUY or SELL, count how many of these 5 indicators
confirm your direction:
1. EMA20 vs EMA50 alignment
2. RSI in favorable zone (not overbought for BUY, not oversold for SELL)
3. MACD histogram confirms direction
4. Price above/below Bollinger mid
5. Price above/below EMA200
Set signal_alignment_count to the number that confirm. If fewer than 3
confirm, you MUST return HOLD. Do not force a trade with weak alignment.

RISKS TO WATCH:
Always include 2-3 specific risks in risks_to_watch. Examples:
- "RSI approaching overbought at 68 — momentum may stall"
- "Price near resistance at 150.20 — rejection likely"
- "Low volume suggests move may not sustain"
These help the system monitor and exit early if conditions change."""


class PromptBuilder:
    """Assembles prompts for Claude API signal generation."""

    def __init__(self, db=None, account_id: str = ""):
        self.db = db
        self.account_id = account_id

    def get_system_prompt(self) -> str:
        """Return the static system prompt."""
        return SYSTEM_PROMPT

    def _assess_usd_strength(self, snapshot: MarketSnapshot) -> str:
        """Derive USD strength from current pair's EMA alignment and price position."""
        ind = snapshot.indicators
        pair = snapshot.pair
        price = float(snapshot.bid)
        ema50 = float(ind.ema_50)
        ema200 = float(ind.ema_200)

        if not price or not ema50 or not ema200:
            return "UNKNOWN — insufficient indicator data"

        # For USD_XXX pairs (USD is base): price up = USD strengthening
        # For XXX_USD pairs (USD is quote): price up = USD weakening
        usd_is_base = pair.startswith("USD_")

        above_ema50 = price > ema50
        above_ema200 = price > ema200

        if usd_is_base:
            if above_ema50 and above_ema200:
                return "STRONG — USD trending up (price > EMA50 > EMA200)"
            elif not above_ema50 and not above_ema200:
                return "WEAK — USD trending down (price < EMA50, EMA200)"
            else:
                return "MIXED — USD direction unclear"
        else:
            if above_ema50 and above_ema200:
                return "WEAK — counter-currency rising vs USD"
            elif not above_ema50 and not above_ema200:
                return "STRONG — counter-currency falling vs USD"
            else:
                return "MIXED — USD direction unclear"

    async def build_prompt(
        self,
        snapshot: MarketSnapshot,
        analyst_briefing: str = "",
        sentiment_context: str = "",
        boost_lessons: list[str] | None = None,
        has_chart: bool = False,
    ) -> str:
        """Assemble the full user prompt from a MarketSnapshot."""
        ind = snapshot.indicators
        acc = snapshot.account_context

        # Get performance insights (Addition Set 1B)
        perf_insights = await self._get_performance_insights(snapshot.pair)

        # Format performance context (Addition Set 2C)
        perf_context = self._format_performance_context(
            snapshot.performance_context
        )

        # Derive USD strength from EMA alignment
        usd_strength = self._assess_usd_strength(snapshot)

        sections = [
            "=== MARKET CONTEXT ===",
            f"Pair: {snapshot.pair}",
            f"Session: {snapshot.session.value if hasattr(snapshot.session, 'value') else str(snapshot.session)}",
            f"Timestamp: {snapshot.timestamp.isoformat()}",
            f"Current Bid: {snapshot.bid}  Ask: {snapshot.ask}",
            f"Spread: {snapshot.spread_pips} pips",
            "",
            "=== MACRO CONTEXT ===",
            f"USD Strength Assessment: {usd_strength}",
            "Consider this when trading USD pairs — if USD is strengthening,",
            "USD_JPY and USD_CAD tend to rise. If weakening, they tend to fall.",
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
            "=== CURRENCY SENTIMENT ===",
            sentiment_context if sentiment_context else "No sentiment data available.",
            "",
            "=== ANALYST BRIEFING (SA-01) ===",
            analyst_briefing if analyst_briefing else "No briefing available.",
            "",
            "",
            "=== TREND DETERMINATION (DO THIS FIRST) ===",
            "Step 1: Determine H4 trend direction from EMA alignment:",
            "  - BULLISH: EMA20 > EMA50 > EMA200 (or price > EMA50 > EMA200)",
            "  - BEARISH: EMA20 < EMA50 < EMA200 (or price < EMA50 < EMA200)",
            "  - NEUTRAL: EMAs tangled or flat — no clear direction",
            "",
            "Step 2: MANDATORY RULE — Trade WITH the H4 trend, NEVER against it:",
            "  - H4 BULLISH → You may only BUY or HOLD. SELL is FORBIDDEN.",
            "  - H4 BEARISH → You may only SELL or HOLD. BUY is FORBIDDEN.",
            "  - H4 NEUTRAL → HOLD only. No trades in directionless markets.",
            "  Violating this rule causes consistent losses. This is non-negotiable.",
            "",
            "Step 3: Use H1 for structure (is price at support/resistance?)",
            "Step 4: Use M15 for precise entry timing only.",
            "",
            "=== YOUR TASK ===",
            f"Analyze {snapshot.pair} and return your trading decision as JSON.",
            "Follow the trend determination steps above BEFORE making any decision.",
            "Only recommend BUY or SELL if the H4 trend supports the direction.",
            "Minimum risk/reward ratio: 1.5:1. If not achievable — return HOLD.",
            "",
            "=== POSITION SIZING GUIDANCE ===",
            "Set stop_loss at a logical technical level (support/resistance, swing low/high).",
            "",
            "CRITICAL — TURTLE STRATEGY (let winners run):",
            "  - Set take_profit to 0. We do NOT use fixed TP targets.",
            "  - The trailing stop will manage the exit automatically.",
            "  - Winners ride the trend until the trailing stop catches up.",
            "  - This means some trades run for 50, 100, even 200+ pips.",
            "  - Our edge is NOT win rate — it's making winners 3-5x bigger than losers.",
            f"  Current ATR(14): {ind.atr_14} — this is the average range per candle.",
            "  - Set SL at 1.5x ATR from entry (gives room to breathe).",
            "  - A wider SL means fewer stop-outs from normal volatility.",
            "  - Only trade setups where you believe a sustained move is likely.",
            "",
            "=== GOLD (XAU_USD) SPECIFIC RULES ===" if snapshot.pair == "XAU_USD" else "",
            (
                "Gold trades at ~$3000-5000/oz. SL/TP must reflect this scale:\n"
                "  - Typical SL: $15-50 from entry (1500-5000 pips at 0.01 pip size)\n"
                "  - Typical TP: $25-100+ from entry (must be ≥1.5x SL distance)\n"
                "  - ATR for gold is in dollars, not micro-pips. A $30 ATR = 3000 pips.\n"
                "  - Gold is volatile — use WIDE SL/TP or return HOLD.\n"
                "  - If you cannot find TP ≥ 1.5x SL distance, return HOLD.\n"
                "  - NEVER set TP closer to entry than SL — this guarantees RR < 1.0."
            ) if snapshot.pair == "XAU_USD" else "",
        ]

        # ── Trading Memory: BOOST lessons (historically profitable) ──
        if boost_lessons:
            sections.append("")
            sections.append(
                "=== TRADING MEMORY (historically profitable patterns) ==="
            )
            sections.append(
                "The following setups have >65% win rate based on historical data:"
            )
            for lesson in boost_lessons:
                sections.append(f"  - {lesson}")
            sections.append(
                "Prioritize these patterns when you see them in the chart."
            )

        # ── Visual Analysis Instructions (only when chart is sent) ──
        if has_chart:
            sections.append("")
            sections.append("=== VISUAL ANALYSIS INSTRUCTIONS ===")
            sections.append(
                "You are receiving a multi-timeframe candlestick chart. "
                "Analyze it like a professional trader:"
            )
            sections.append(
                "1. H4 (top): Identify the dominant trend. "
                "Look for trend continuation or reversal patterns."
            )
            sections.append(
                "2. H1 (middle): Identify key support/resistance levels. "
                "Is price at a decision point?"
            )
            sections.append(
                "3. M15 (bottom): Look for entry timing patterns — "
                "pin bars, engulfing candles, breakouts."
            )
            sections.append(
                "Combine what you SEE in the chart with the indicator "
                "data above. If the chart shows a clear pattern that "
                "contradicts the indicators, trust the chart — price "
                "action is king."
            )

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
