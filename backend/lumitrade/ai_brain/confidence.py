"""
Lumitrade Confidence Adjustment Pipeline
===========================================
Applies 6 adjustment factors to raw AI confidence score.
Per PRD Section 10.3.
"""

from decimal import Decimal

from ..core.enums import NewsImpact, Session
from ..core.models import MarketSnapshot
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class ConfidenceAdjuster:
    """Adjusts raw AI confidence based on market conditions."""

    def adjust(
        self,
        raw_confidence: Decimal,
        snapshot: MarketSnapshot,
        action: str,
        consecutive_losses: int = 0,
        has_chart: bool = False,
    ) -> tuple[Decimal, dict]:
        """
        Apply adjustment factors to raw confidence.
        When has_chart=True (Claude analyzed a TradingView chart),
        skip indicator alignment penalty — Claude's visual analysis
        replaces numeric indicator confirmation.
        Returns (adjusted_confidence, adjustment_log dict).
        """
        adjustments: dict[str, float] = {}
        adjusted = raw_confidence

        # Factor 1: Indicator alignment
        # Always computed — chart mode no longer bypasses this.
        # Chart gives Claude visual context but indicators are measurable ground
        # truth. Codex review 2026-04-29: bypassing alignment in chart mode let
        # Claude's self-reported confidence pass the min_confidence gate even
        # when all 5 indicators disagreed with the proposed direction.
        alignment = self._indicator_alignment(snapshot, action)
        if alignment >= 0.6:
            multiplier = Decimal("1.0")
        elif alignment >= 0.4:
            multiplier = Decimal("0.90")
        else:
            multiplier = Decimal("0.75")
        factor = adjusted * multiplier - adjusted
        adjustments["indicator_alignment"] = float(factor)
        adjusted = adjusted * multiplier

        # Hard cap: if fewer than 2/5 indicators agree, cap adjusted confidence
        # below the minimum threshold regardless of Claude's self-reported score.
        if alignment < 0.4:
            adjusted = min(adjusted, Decimal("0.64"))

        # Factor 2: News proximity — always apply (chart doesn't show news)
        news_adj = self._news_proximity(snapshot)
        adjustments["news_proximity"] = float(news_adj)
        adjusted += news_adj

        # Factor 3: Session quality (pair-aware) — always apply
        session_adj = self._session_quality(snapshot.session, snapshot.pair)
        adjustments["session_quality"] = float(session_adj)
        adjusted += session_adj

        # Factor 4: Spread penalty — always apply (execution cost)
        spread_adj = self._spread_penalty(snapshot.spread_pips, snapshot.pair)
        adjustments["spread_penalty"] = float(spread_adj)
        adjusted += spread_adj

        # Factor 5: Consecutive losses — lower adjusted confidence so it's
        # harder to pass the min_confidence gate after a losing streak.
        # Previously computed but never applied (dead code — Codex 2026-04-29).
        loss_adj = self._consecutive_loss_adjustment(consecutive_losses)
        adjustments["consecutive_losses"] = float(-loss_adj)
        adjusted -= loss_adj

        # Factor 6: Recent pair performance
        # With chart: halve the penalty — chart gives fresh context
        pair_adj = self._recent_pair_performance(snapshot)
        if has_chart:
            pair_adj = pair_adj / 2
        adjustments["recent_pair_performance"] = float(pair_adj)
        adjusted += pair_adj

        # Clamp to [0.0, 1.0]
        adjusted = max(Decimal("0"), min(Decimal("1"), adjusted))

        logger.info(
            "confidence_adjusted",
            raw=str(raw_confidence),
            adjusted=str(adjusted),
            factors=adjustments,
        )

        return adjusted, adjustments

    def _indicator_alignment(self, snapshot: MarketSnapshot, action: str) -> float:
        """Score 0.0-1.0 based on how many indicators confirm the direction."""
        ind = snapshot.indicators
        confirms = 0
        total = 5

        if action == "BUY":
            if ind.rsi_14 < Decimal("70"):
                confirms += 1
            if ind.macd_histogram > 0:
                confirms += 1
            if ind.ema_20 > ind.ema_50:
                confirms += 1
            if ind.ema_50 > ind.ema_200:
                confirms += 1
            bid = snapshot.bid
            if bid > ind.bb_mid:
                confirms += 1
        elif action == "SELL":
            if ind.rsi_14 > Decimal("30"):
                confirms += 1
            if ind.macd_histogram < 0:
                confirms += 1
            if ind.ema_20 < ind.ema_50:
                confirms += 1
            if ind.ema_50 < ind.ema_200:
                confirms += 1
            bid = snapshot.bid
            if bid < ind.bb_mid:
                confirms += 1
        else:
            return 0.5  # HOLD — neutral

        return confirms / total

    def _news_proximity(self, snapshot: MarketSnapshot) -> Decimal:
        """Reduce confidence near high-impact news events."""
        for event in (snapshot.news_events or []):
            if event.impact == NewsImpact.HIGH:
                if 0 < event.minutes_until <= 30:
                    return Decimal("-0.25")
                elif 30 < event.minutes_until <= 60:
                    return Decimal("-0.15")
            elif event.impact == NewsImpact.MEDIUM:
                if 0 < event.minutes_until <= 15:
                    return Decimal("-0.10")
        return Decimal("0")

    # Pairs that are native to each session (no penalty applied)
    _TOKYO_PAIRS = {"USD_JPY", "AUD_USD", "NZD_USD", "AUD_JPY", "NZD_JPY"}
    _LONDON_PAIRS = {"EUR_USD", "GBP_USD", "EUR_GBP", "USD_CHF", "EUR_CHF"}
    _NY_PAIRS = {"USD_CAD", "EUR_USD", "GBP_USD", "USD_CHF", "XAU_USD"}

    def _session_quality(self, session: Session, pair: str = "") -> Decimal:
        """
        Adjust for trading session quality, accounting for pair relevance.

        A pair native to the current session gets no penalty — e.g. USD/JPY
        during Tokyo has full liquidity and tight spreads.
        """
        if session == Session.OVERLAP:
            return Decimal("0.05")
        elif session == Session.TOKYO:
            if pair in self._TOKYO_PAIRS:
                return Decimal("0")  # Native pair — no penalty
            return Decimal("-0.05")
        elif session == Session.LONDON:
            return Decimal("0")  # London is always good liquidity
        elif session == Session.NEW_YORK:
            return Decimal("0")  # NY is always good liquidity
        elif session == Session.OTHER:
            return Decimal("-0.10")
        return Decimal("0")

    # Per-instrument spread thresholds for confidence penalty.
    # BTC pip = $1; typical OANDA BTC spread is $20-30 (20-30 pips).
    # XAU pip = $0.01; typical OANDA gold spread is 25-50 pips.
    # Default (forex) reject at 3 pips is correct for EUR/USD etc.
    _SPREAD_REJECT: dict[str, Decimal] = {
        "XAU_USD": Decimal("150"),
        "BTC_USD": Decimal("50"),    # Matches risk engine _MAX_SPREAD_BY_PAIR ceiling
    }
    _SPREAD_WARN: dict[str, Decimal] = {
        "XAU_USD": Decimal("100"),
        "BTC_USD": Decimal("30"),    # Slight penalty above normal $20-30 range
    }
    _DEFAULT_SPREAD_REJECT = Decimal("3.0")
    _DEFAULT_SPREAD_WARN = Decimal("2.0")

    def _spread_penalty(self, spread_pips: Decimal, pair: str = "") -> Decimal:
        """Penalize wide spreads, with per-instrument thresholds."""
        reject = self._SPREAD_REJECT.get(pair, self._DEFAULT_SPREAD_REJECT)
        warn = self._SPREAD_WARN.get(pair, self._DEFAULT_SPREAD_WARN)
        if spread_pips > reject:
            return Decimal("-999")
        elif spread_pips > warn:
            return Decimal("-0.05")
        return Decimal("0")

    def _consecutive_loss_adjustment(self, consecutive_losses: int) -> Decimal:
        """Return threshold increase based on consecutive losses."""
        if consecutive_losses >= 5:
            return Decimal("0.20")  # Threshold raised to 0.85
        elif consecutive_losses >= 3:
            return Decimal("0.10")  # Threshold raised to 0.75
        return Decimal("0")

    def _recent_pair_performance(self, snapshot: MarketSnapshot) -> Decimal:
        """Reduce confidence if pair has poor recent performance."""
        trades = snapshot.recent_trades
        if len(trades) < 5:
            return Decimal("0")

        wins = sum(1 for t in trades if t.outcome and (t.outcome.value if hasattr(t.outcome, "value") else str(t.outcome)) == "WIN")
        win_rate = wins / len(trades)
        if win_rate < 0.4:
            return Decimal("-0.10")
        return Decimal("0")
