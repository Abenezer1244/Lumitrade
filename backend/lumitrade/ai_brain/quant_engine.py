"""
Lumitrade Quantitative Strategy Engine
========================================
Pure math — no AI. Generates trade signals from proven technical strategies.
Each strategy independently scores the setup. A signal fires when 2+ strategies
agree on direction with sufficient score.

Claude's role is FILTER, not DECISION MAKER. This engine decides. Claude
reviews the decision and approves/rejects based on chart + context.

Strategies implemented:
1. EMA Trend Crossover — trades with the trend when fast EMA crosses slow
2. Bollinger Mean Reversion — fades extremes when price touches outer band
3. Momentum Breakout — enters on strong moves confirmed by RSI + MACD
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import TypedDict

from ..core.models import MarketSnapshot
from ..infrastructure.secure_logger import get_logger
from ..utils.pip_math import pip_size


class StrategyVote(TypedDict):
    """Result of a single quant strategy evaluation. Shape is invariant
    across all strategy methods on QuantEngine — see _ema_trend_crossover,
    _bollinger_mean_reversion, _momentum_breakout."""
    name: str       # Strategy name: "EMA_TREND" | "BB_REVERT" | "MOMENTUM"
    action: str     # "BUY" | "SELL" | "HOLD"
    score: float    # 0.0-1.0 confidence
    reason: str     # human-readable explanation

logger = get_logger(__name__)


@dataclass
class QuantSignal:
    """Output of the quantitative engine."""
    action: str           # "BUY", "SELL", "HOLD"
    score: float          # 0.0-1.0 composite score
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal  # 0 for Turtle (trailing stop)
    strategies_fired: list[str]  # which strategies triggered
    reasoning: str        # human-readable explanation


class QuantEngine:
    """Generates signals from proven quantitative strategies."""

    def evaluate(self, snapshot: MarketSnapshot) -> QuantSignal:
        """
        Run all strategies against the snapshot. Return a composite signal.

        REGIME-AWARE VOTING:
        ADX determines which strategies are active:
        - ADX >= 25 (TRENDING): EMA Trend + Momentum active, Bollinger disabled
        - ADX < 25 (RANGING): Bollinger Reversion active, EMA Trend disabled
        - Momentum works in both regimes (confirms moves)

        This single filter transformed -7% to +45% in published backtests.
        """
        ind = snapshot.indicators
        pair = snapshot.pair
        price = snapshot.bid

        # Determine market regime from ADX
        adx = float(ind.adx_14) if hasattr(ind, 'adx_14') else 0.0
        is_trending = adx >= 25
        is_ranging = adx < 25 and adx > 0

        # Run strategies filtered by regime
        # In trending markets: EMA Trend + Momentum (never mean-revert against a trend)
        # In ranging markets: Bollinger Reversion + Momentum (never trend-follow in a range)
        if is_trending:
            ema_signal = self._ema_trend_crossover(ind, price, pair)
            bb_signal = {"name": "BB_REVERT", "action": "HOLD", "score": 0.0,
                         "reason": f"Disabled: ADX={adx:.1f} (trending market)"}
            mom_signal = self._momentum_breakout(ind, price, pair)
        elif is_ranging:
            ema_signal = {"name": "EMA_TREND", "action": "HOLD", "score": 0.0,
                          "reason": f"Disabled: ADX={adx:.1f} (ranging market)"}
            bb_signal = self._bollinger_mean_reversion(ind, price, pair)
            mom_signal = self._momentum_breakout(ind, price, pair)
        else:
            # ADX = 0 (not computed) — run all strategies
            ema_signal = self._ema_trend_crossover(ind, price, pair)
            bb_signal = self._bollinger_mean_reversion(ind, price, pair)
            mom_signal = self._momentum_breakout(ind, price, pair)

        signals = [ema_signal, bb_signal, mom_signal]

        # Count BUY and SELL votes (non-HOLD only)
        buy_votes = [s for s in signals if s["action"] == "BUY"]
        sell_votes = [s for s in signals if s["action"] == "SELL"]

        buy_score = sum(s["score"] for s in buy_votes)
        sell_score = sum(s["score"] for s in sell_votes)

        # Decision tree: 2+ agreement > single strong > HOLD
        action = "HOLD"
        score = 0.0
        fired: list[str] = []
        sl = Decimal("0")
        reasoning = ""

        # Tier 1: Multi-strategy agreement (strongest signal)
        if len(buy_votes) >= 2 and buy_score > sell_score:
            action = "BUY"
            score = min(0.70 + (buy_score / 3) * 0.30, 1.0)
            fired = [s["name"] for s in buy_votes]
            sl = self._calculate_sl(ind, price, pair, "BUY")
            reasoning = "MULTI: " + " | ".join(s["reason"] for s in buy_votes)
        elif len(sell_votes) >= 2 and sell_score > buy_score:
            action = "SELL"
            score = min(0.70 + (sell_score / 3) * 0.30, 1.0)
            fired = [s["name"] for s in sell_votes]
            sl = self._calculate_sl(ind, price, pair, "SELL")
            reasoning = "MULTI: " + " | ".join(s["reason"] for s in sell_votes)
        # Tier 2: Single strong strategy (score >= 0.65) with no opposition
        elif buy_votes and len(sell_votes) == 0:
            best = max(buy_votes, key=lambda s: s["score"])
            if best["score"] >= 0.65:
                action = "BUY"
                score = 0.55 + (best["score"] - 0.65) * 0.5
                fired = [best["name"]]
                sl = self._calculate_sl(ind, price, pair, "BUY")
                reasoning = f"SOLO({best['name']}): {best['reason']}"
        elif sell_votes and len(buy_votes) == 0:
            best = max(sell_votes, key=lambda s: s["score"])
            if best["score"] >= 0.65:
                action = "SELL"
                score = 0.55 + (best["score"] - 0.65) * 0.5
                fired = [best["name"]]
                sl = self._calculate_sl(ind, price, pair, "SELL")
                reasoning = f"SOLO({best['name']}): {best['reason']}"

        if action == "HOLD":
            reasons = [f"{s['name']}={s['action']}({s['score']:.2f})" for s in signals]
            reasoning = f"No signal: {', '.join(reasons)}"

        result = QuantSignal(
            action=action,
            score=score,
            entry_price=price,
            stop_loss=sl,
            take_profit=Decimal("0"),  # Turtle: trailing stop manages exit
            strategies_fired=fired,
            reasoning=reasoning,
        )

        regime = "TRENDING" if is_trending else ("RANGING" if is_ranging else "UNKNOWN")
        logger.info(
            "quant_signal",
            pair=pair,
            action=action,
            score=f"{score:.2f}",
            regime=regime,
            adx=f"{adx:.1f}",
            strategies=fired,
            ema=f"{ema_signal['action']}({ema_signal['score']:.2f})",
            bb=f"{bb_signal['action']}({bb_signal['score']:.2f})",
            mom=f"{mom_signal['action']}({mom_signal['score']:.2f})",
        )

        return result

    # ── Strategy 1: EMA Trend Crossover ──────────────────────────

    def _ema_trend_crossover(self, ind, price, pair) -> StrategyVote:
        """
        BUY: EMA20 > EMA50 AND price > EMA200 (trend confirmed)
        SELL: EMA20 < EMA50 AND price < EMA200
        Score boosted when all 3 EMAs are aligned.
        """
        ema20 = float(ind.ema_20)
        ema50 = float(ind.ema_50)
        ema200 = float(ind.ema_200)
        px = float(price)

        if ema20 == 0 or ema50 == 0 or ema200 == 0:
            return {"name": "EMA_TREND", "action": "HOLD", "score": 0.0,
                    "reason": "EMA data missing"}

        # Full bullish alignment: EMA20 > EMA50 > EMA200
        full_bull = ema20 > ema50 > ema200
        # Full bearish alignment: EMA20 < EMA50 < EMA200
        full_bear = ema20 < ema50 < ema200

        # Basic crossover
        cross_bull = ema20 > ema50
        cross_bear = ema20 < ema50

        if full_bull and px > ema200:
            score = 0.85 if px > ema20 else 0.65
            return {"name": "EMA_TREND", "action": "BUY", "score": score,
                    "reason": f"Full bullish EMA alignment (20>{ema20:.3f} > 50>{ema50:.3f} > 200>{ema200:.3f})"}
        elif full_bear and px < ema200:
            score = 0.85 if px < ema20 else 0.65
            return {"name": "EMA_TREND", "action": "SELL", "score": score,
                    "reason": f"Full bearish EMA alignment (20<{ema20:.3f} < 50<{ema50:.3f} < 200<{ema200:.3f})"}
        elif cross_bull and px > ema50:
            return {"name": "EMA_TREND", "action": "BUY", "score": 0.45,
                    "reason": f"EMA20 above EMA50, partial bull"}
        elif cross_bear and px < ema50:
            return {"name": "EMA_TREND", "action": "SELL", "score": 0.45,
                    "reason": f"EMA20 below EMA50, partial bear"}
        else:
            return {"name": "EMA_TREND", "action": "HOLD", "score": 0.0,
                    "reason": "EMAs tangled — no clear trend"}

    # ── Strategy 2: Bollinger Mean Reversion ─────────────────────

    def _bollinger_mean_reversion(self, ind, price, pair) -> StrategyVote:
        """
        BUY: Price at/below lower BB + RSI < 35 (oversold bounce)
        SELL: Price at/above upper BB + RSI > 65 (overbought rejection)
        Best in ranging markets (BB width not expanding).
        """
        px = float(price)
        bb_upper = float(ind.bb_upper)
        bb_lower = float(ind.bb_lower)
        bb_mid = float(ind.bb_mid)
        rsi = float(ind.rsi_14)

        if bb_upper == 0 or bb_lower == 0 or bb_mid == 0:
            return {"name": "BB_REVERT", "action": "HOLD", "score": 0.0,
                    "reason": "Bollinger data missing"}

        # How close is price to the bands (0=mid, 1=at band, >1=outside)
        bb_width = bb_upper - bb_lower
        if bb_width == 0:
            return {"name": "BB_REVERT", "action": "HOLD", "score": 0.0,
                    "reason": "BB width zero"}

        # Distance from mid as fraction of half-width
        dist_from_mid = (px - bb_mid) / (bb_width / 2)

        # Oversold bounce
        if dist_from_mid <= -0.85 and rsi < 35:
            score = 0.75 if rsi < 25 else 0.55
            return {"name": "BB_REVERT", "action": "BUY", "score": score,
                    "reason": f"Price at lower BB ({px:.5f} near {bb_lower:.5f}), RSI oversold at {rsi:.1f}"}

        # Overbought rejection
        if dist_from_mid >= 0.85 and rsi > 65:
            score = 0.75 if rsi > 75 else 0.55
            return {"name": "BB_REVERT", "action": "SELL", "score": score,
                    "reason": f"Price at upper BB ({px:.5f} near {bb_upper:.5f}), RSI overbought at {rsi:.1f}"}

        return {"name": "BB_REVERT", "action": "HOLD", "score": 0.0,
                "reason": f"Price in mid-range (BB dist={dist_from_mid:+.2f}, RSI={rsi:.1f})"}

    # ── Strategy 3: Momentum Breakout ────────────────────────────

    def _momentum_breakout(self, ind, price, pair) -> StrategyVote:
        """
        BUY: MACD histogram positive + RSI 50-70 (rising momentum, not exhausted)
        SELL: MACD histogram negative + RSI 30-50 (falling momentum, not exhausted)
        Requires MACD and RSI agreement — filters out weak moves.
        """
        macd_hist = float(ind.macd_histogram)
        macd_line = float(ind.macd_line)
        macd_signal = float(ind.macd_signal)
        rsi = float(ind.rsi_14)

        # MACD bullish: histogram positive and growing (line > signal)
        macd_bull = macd_hist > 0 and macd_line > macd_signal
        # MACD bearish: histogram negative and falling
        macd_bear = macd_hist < 0 and macd_line < macd_signal

        if macd_bull and 45 < rsi < 72:
            # Strong momentum if histogram is decisively positive
            score = 0.70 if abs(macd_hist) > abs(macd_signal) * 0.3 else 0.45
            return {"name": "MOMENTUM", "action": "BUY", "score": score,
                    "reason": f"MACD bullish (hist={macd_hist:.6f}), RSI={rsi:.1f} in sweet spot"}

        if macd_bear and 28 < rsi < 55:
            score = 0.70 if abs(macd_hist) > abs(macd_signal) * 0.3 else 0.45
            return {"name": "MOMENTUM", "action": "SELL", "score": score,
                    "reason": f"MACD bearish (hist={macd_hist:.6f}), RSI={rsi:.1f} in sweet spot"}

        return {"name": "MOMENTUM", "action": "HOLD", "score": 0.0,
                "reason": f"No momentum consensus (MACD hist={macd_hist:.6f}, RSI={rsi:.1f})"}

    # ── Stop Loss Calculation ────────────────────────────────────

    def _calculate_sl(self, ind, price, pair, action) -> Decimal:
        """
        SL at 3.0x ATR from entry. Backtested: 3x ATR turned -$3.4K loss
        into +$11K profit on USD_CAD (1.5x was too tight, stopped out by noise).
        """
        atr = ind.atr_14
        if atr == 0:
            ps = pip_size(pair)
            atr = Decimal("500") * ps if "XAU" in pair else Decimal("25") * ps

        sl_distance = atr * Decimal("3.0")

        if action == "BUY":
            sl = price - sl_distance
        else:
            sl = price + sl_distance

        # Round appropriately
        if "JPY" in pair:
            sl = sl.quantize(Decimal("0.001"))
        elif "XAU" in pair:
            sl = sl.quantize(Decimal("0.01"))
        else:
            sl = sl.quantize(Decimal("0.00001"))

        return sl
