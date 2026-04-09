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
Your role: analyze TradingView charts and market data to generate
high-probability trading signals with disciplined risk management.

PROFESSIONAL TRADING PRINCIPLES (from institutional best practices):
- Trade what you SEE on the chart, not what you THINK should happen.
- A breakout that fails is a reversal signal — respect it.
- High confidence is earned by MULTIPLE confirmations, not one strong signal.
- If your past trades in this direction lost money, demand extra confirmation.
- The best trade is often NO trade. HOLD preserves capital for better setups.
- Support/resistance levels that have been tested 3+ times are strongest.
- False breakouts are more common than real ones — wait for the retest.
- Divergence between price and RSI is one of the strongest reversal signals.
- Trade with the higher timeframe trend unless M15 shows a CLEAR reversal.
- Never chase a move that already happened. If you missed the entry, wait.

LEARNING FROM YOUR HISTORY:
You will receive your own trade history on this pair. STUDY IT CAREFULLY:
- If your BUYs consistently lose on this pair, DO NOT BUY unless the chart
  shows overwhelming evidence (reversal pattern + volume + key level bounce).
- If your SELLs consistently win, the market has a directional bias — respect it.
- High confidence in the past did NOT mean high win rate. A 0.85 confidence
  BUY that loses is WORSE than a 0.70 HOLD that preserves capital.
- Your track record is data. Use it. Adjust your aggression based on results.

CRITICAL RULES:
1. Respond ONLY with valid JSON matching the exact schema below.
2. No text outside the JSON object. No markdown. No code fences.
3. If conditions are unclear or conflicting — return action: HOLD.
4. Never force a trade. Capital preservation over opportunity.
5. confidence must reflect genuine conviction weighted by your track record.
6. If your history shows losses in this direction, lower your confidence by 0.10-0.20.

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
  "reasoning": "Full technical analysis. Min 100 words. Cite values. MUST reference your trade history on this pair.",
  "timeframe_h4_score": 0.0-1.0,
  "timeframe_h1_score": 0.0-1.0,
  "timeframe_m15_score": 0.0-1.0,
  "key_levels": [float, float],
  "invalidation_level": float,
  "expected_duration": "SCALP" | "INTRADAY" | "SWING",
  "risks_to_watch": ["string", "string"],
  "signal_alignment_count": 0-5
}

RISKS TO WATCH:
Always include 2-3 specific risks in risks_to_watch. Examples:
- "RSI approaching overbought at 68 — momentum may stall"
- "Price near resistance at 150.20 — rejection likely"
- "Past 3 BUYs on this pair lost — pattern may repeat"
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
        quant_signal=None,
    ) -> str:
        """Assemble the full user prompt from a MarketSnapshot."""
        ind = snapshot.indicators
        acc = snapshot.account_context

        # Get performance insights (Addition Set 1B)
        perf_insights = await self._get_performance_insights(snapshot.pair)

        # Get detailed trade history for this pair — Claude learns from past results
        trade_history = await self._get_trade_history(snapshot.pair)

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
            "=== YOUR TRADE HISTORY ON THIS PAIR ===",
            trade_history,
            "",
            "=== PERFORMANCE INSIGHTS ===",
            perf_insights,
            "",
            "=== CURRENCY SENTIMENT ===",
            self._sanitize_db_text(sentiment_context, max_len=400) if sentiment_context else "No sentiment data available.",
            "",
            "=== ANALYST BRIEFING (SA-01) ===",
            self._sanitize_db_text(analyst_briefing, max_len=400) if analyst_briefing else "No briefing available.",
            "",
            "",
            "=== TREND & STRUCTURE ANALYSIS ===",
        ]

        if has_chart:
            # Chart mode: Claude decides based on what it SEES
            sections.extend([
                "You have the TradingView chart. Analyze it visually:",
                "Step 1: Look at H4 panel — what is the trend? Is it turning?",
                "Step 2: Look at H1 panel — is price at support/resistance?",
                "Step 3: Look at M15 panel — is there an entry pattern?",
                "",
                "You may BUY or SELL in any trend direction if the chart shows:",
                "  - A clear reversal pattern (double bottom, head & shoulders, etc.)",
                "  - A support/resistance bounce with confirmation",
                "  - A breakout with volume",
                "Trading WITH the trend is preferred but NOT mandatory.",
                "If you see a high-probability counter-trend setup, take it.",
            ])
        else:
            # Text-only mode: enforce H4 trend rule (no chart to verify reversals)
            sections.extend([
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
            ])

        # Inject quant signal context if available
        if quant_signal and quant_signal.action != "HOLD":
            sections.extend([
                "",
                "=== QUANTITATIVE ENGINE SIGNAL (MATH-BASED) ===",
                f"The quant engine recommends: {quant_signal.action} {snapshot.pair}",
                f"Score: {quant_signal.score:.2f}/1.00",
                f"Strategies that agree: {', '.join(quant_signal.strategies_fired)}",
                f"Reasoning: {quant_signal.reasoning}",
                f"Proposed SL: {quant_signal.stop_loss}",
                "",
                "YOUR ROLE: You are the FILTER. The quant engine made the math decision.",
                "You review the chart and context to APPROVE or REJECT this trade.",
                "- If the chart CONFIRMS the quant signal → APPROVE (return same action)",
                "- If the chart shows danger the math missed → REJECT (return HOLD)",
                "- You may ADJUST the entry/SL if the chart shows a better level",
                "- Check your trade history — if this direction keeps losing, REJECT",
                "",
                "Reasons to REJECT (return HOLD):",
                "  - Chart shows price at major resistance/support against the trade",
                "  - Your past trades in this direction consistently lost money",
                "  - News event within 30 minutes could cause volatility",
                "  - RSI divergence warns of reversal against the trade",
                "  - The breakout the math detected looks like a false breakout on chart",
            ])

        sections.extend([
            "",
            "=== YOUR TASK ===",
            f"Analyze {snapshot.pair} and return your trading decision as JSON.",
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
        ])

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
            sections.append("=== VISUAL CHART ANALYSIS (PRIMARY INPUT) ===")
            sections.append(
                "You are receiving a TradingView chart screenshot — the same "
                "professional charting platform used by institutional traders. "
                "THIS CHART IS YOUR PRIMARY DECISION INPUT. Analyze it like "
                "a professional trader:"
            )
            sections.append(
                "1. H4 (top panel): Identify the dominant trend direction. "
                "Look at EMA alignment (20/50/200), Bollinger Band position, "
                "and trend continuation or reversal patterns."
            )
            sections.append(
                "2. H1 (middle panel): Identify key support/resistance levels. "
                "Is price at a decision point? Look for breakout/rejection setups."
            )
            sections.append(
                "3. M15 (bottom panel): Look for entry timing patterns — "
                "pin bars, engulfing candles, breakouts, RSI divergence."
            )
            sections.append(
                "The chart is your primary evidence. The numeric indicators "
                "above are supplementary confirmation. If the chart shows a "
                "clear pattern that contradicts the indicators, TRUST THE "
                "CHART — price action is king. Base your BUY/SELL/HOLD "
                "decision primarily on what you see in the chart."
            )

        return "\n".join(sections)

    async def _get_trade_history(self, pair: str) -> str:
        """
        Get detailed trade history for this pair — BUY and SELL results separately.
        Claude sees its own track record and learns from wins/losses.
        """
        if not self.db:
            return "  No trade history available."

        try:
            trades = await self.db.select(
                "trades",
                {"pair": pair, "status": "CLOSED"},
                order="closed_at",
                limit=10,
            )
        except Exception:
            return "  No trade history available."

        if not trades:
            return "  No closed trades on this pair yet."

        # Separate by direction
        buy_trades = [t for t in trades if t.get("direction") == "BUY"]
        sell_trades = [t for t in trades if t.get("direction") == "SELL"]

        lines = []

        for direction, dir_trades in [("BUY", buy_trades), ("SELL", sell_trades)]:
            if not dir_trades:
                lines.append(f"  {direction}: No history")
                continue

            wins = [t for t in dir_trades if t.get("outcome") == "WIN"]
            losses = [t for t in dir_trades if t.get("outcome") == "LOSS"]
            total_pnl = sum(float(t.get("pnl_usd") or 0) for t in dir_trades)
            wr = len(wins) / len(dir_trades) * 100 if dir_trades else 0

            lines.append(
                f"  {direction}: {len(dir_trades)} trades | "
                f"Win rate: {wr:.0f}% | "
                f"Total P&L: ${total_pnl:+,.0f}"
            )

            # Show last 3 trades with detail
            recent = dir_trades[-3:]
            for t in recent:
                pnl = float(t.get("pnl_usd") or 0)
                conf = t.get("confidence_score") or "?"
                outcome = t.get("outcome") or "?"
                dt = (t.get("closed_at") or "")[:10]
                lines.append(
                    f"    {dt} | {outcome} | ${pnl:+,.0f} | confidence: {conf}"
                )

        # Add explicit warning if one direction is clearly losing
        for direction, dir_trades in [("BUY", buy_trades), ("SELL", sell_trades)]:
            if len(dir_trades) >= 3:
                total_pnl = sum(float(t.get("pnl_usd") or 0) for t in dir_trades)
                losses = [t for t in dir_trades if t.get("outcome") == "LOSS"]
                wr = (len(dir_trades) - len(losses)) / len(dir_trades)
                if wr < 0.35 and total_pnl < -200:
                    lines.append("")
                    lines.append(
                        f"  *** WARNING: {direction} on {pair} has {wr:.0%} win rate "
                        f"and ${total_pnl:+,.0f} total P&L. "
                        f"Think twice before entering {direction}. "
                        f"If the chart shows {direction}, demand VERY strong "
                        f"confirmation (clear reversal, key level bounce, volume). ***"
                    )

        return "\n".join(lines)

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
            recommendation = self._sanitize_db_text(insight.get("recommendation", ""))
            lines.append(f"  - [{insight_type}] {metric}: {value}")
            if recommendation:
                lines.append(f"    Action: {recommendation}")
        return "\n".join(lines)

    @staticmethod
    def _sanitize_db_text(text: str, max_len: int = 200) -> str:
        """Sanitize DB-sourced text before prompt injection. Prevents indirect prompt injection."""
        if not text or not isinstance(text, str):
            return ""
        # Strip potential prompt injection patterns
        injection_patterns = re.compile(
            r"^(you are|ignore|system:|important:|forget|disregard|override)",
            re.IGNORECASE | re.MULTILINE,
        )
        cleaned = injection_patterns.sub("", text)
        # Allow only safe characters
        cleaned = re.sub(r"[^a-zA-Z0-9\s.,;:!?\-+%/()']+", " ", cleaned)
        # Truncate
        cleaned = cleaned[:max_len].strip()
        return f"[DATA] {cleaned}" if cleaned else ""

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
