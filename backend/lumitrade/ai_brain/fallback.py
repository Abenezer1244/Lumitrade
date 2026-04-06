"""
Lumitrade Rule-Based Fallback
================================
When Claude API is unavailable: generate signal using indicator thresholds only.
Per BDS Section 5 and Master Prompt Phase 3.
"""

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ..core.enums import Action, GenerationMethod, TradeDuration
from ..core.models import MarketSnapshot, SignalProposal
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


def _direction_reasoning(action: Action) -> str:
    """Return directional reasoning string for fallback."""
    if action == Action.BUY:
        return (
            "EMA 50 above EMA 200 with oversold RSI "
            "suggests bullish setup."
        )
    if action == Action.SELL:
        return (
            "EMA 50 below EMA 200 with overbought RSI "
            "suggests bearish setup."
        )
    return "No clear directional bias from indicators."


class RuleBasedFallback:
    """Generates signals from indicator thresholds when AI is unavailable."""

    def generate(self, snapshot: MarketSnapshot) -> SignalProposal:
        """
        Generate a signal using simple indicator rules.
        EMA 50 > EMA 200 + RSI < 30 -> BUY
        EMA 50 < EMA 200 + RSI > 70 -> SELL
        Otherwise -> HOLD
        """
        ind = snapshot.indicators
        action = Action.HOLD
        confidence = Decimal("0.50")
        entry = snapshot.bid
        sl = entry
        tp = entry

        if ind.ema_50 > ind.ema_200 and ind.rsi_14 < Decimal("30"):
            action = Action.BUY
            confidence = Decimal("0.70")
            atr = ind.atr_14 if ind.atr_14 > 0 else Decimal("0.0010")
            sl = entry - atr * Decimal("1.5")
            tp = entry + atr * Decimal("2.5")

        elif ind.ema_50 < ind.ema_200 and ind.rsi_14 > Decimal("70"):
            action = Action.SELL
            confidence = Decimal("0.70")
            atr = ind.atr_14 if ind.atr_14 > 0 else Decimal("0.0010")
            sl = entry + atr * Decimal("1.5")
            tp = entry - atr * Decimal("2.5")

        prompt_text = f"RULE_BASED:{snapshot.pair}:{snapshot.timestamp.isoformat()}"

        logger.info(
            "rule_based_signal_generated",
            pair=snapshot.pair,
            action=action.value,
            confidence=str(confidence),
        )

        return SignalProposal(
            signal_id=uuid4(),
            pair=snapshot.pair,
            action=action,
            confidence_raw=confidence,
            confidence_adjusted=confidence,
            confidence_adjustment_log={},
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            summary=(
                f"Rule-based {action.value} signal "
                f"for {snapshot.pair}. AI was unavailable."
            ),
            reasoning=(
                "Rule-based fallback signal generated "
                "because Claude API was unavailable. "
                f"EMA 50: {ind.ema_50}, "
                f"EMA 200: {ind.ema_200}, "
                f"RSI: {ind.rsi_14}. "
                f"{_direction_reasoning(action)} "
                f"ATR: {ind.atr_14}. "
                f"MACD histogram: {ind.macd_histogram}. "
                f"Bollinger Bands: upper {ind.bb_upper}, "
                f"mid {ind.bb_mid}, "
                f"lower {ind.bb_lower}."
            ),
            timeframe_scores={"h4": 0.5, "h1": 0.5, "m15": 0.5},
            indicators_snapshot=ind.to_dict(),
            key_levels=[],
            invalidation_level=sl,
            expected_duration=TradeDuration.INTRADAY,
            generation_method=GenerationMethod.RULE_BASED,
            session=snapshot.session,
            spread_pips=snapshot.spread_pips,
            news_context=snapshot.news_events,
            ai_prompt_hash=hashlib.sha256(prompt_text.encode()).hexdigest(),
            created_at=datetime.now(timezone.utc),
        )
