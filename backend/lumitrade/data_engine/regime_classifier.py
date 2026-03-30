"""
Lumitrade Market Regime Classifier
=====================================
Classifies current market regime from technical indicators and spread data.

Classification priority (first match wins):
  1. LOW_LIQUIDITY  — spread_pips > 4.0
  2. HIGH_VOLATILITY — atr_14 > 2.0 * avg_atr_30d (requires 30d avg)
  3. TRENDING        — abs(ema_20 - ema_200) / atr_14 > 1.5
  4. RANGING         — abs(ema_20 - ema_200) / atr_14 < 0.5
  5. UNKNOWN         — none of the above

Per BDS Section 13.1 and SAS v2.0.
"""

from decimal import Decimal

from ..core.enums import MarketRegime
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# Classification thresholds — all Decimal to avoid float contamination
_LOW_LIQ_SPREAD_THRESHOLD = Decimal("6.0")
_HIGH_VOL_ATR_MULTIPLIER = Decimal("2.0")
_TRENDING_EMA_ATR_RATIO = Decimal("1.5")
_RANGING_EMA_ATR_RATIO = Decimal("0.5")


class RegimeClassifier:
    """
    Classifies current market regime based on EMA separation, ATR volatility,
    and spread width. Uses strict priority ordering so the most severe
    condition always wins.
    """

    def classify(
        self,
        ema_20: Decimal,
        ema_50: Decimal,
        ema_200: Decimal,
        atr_14: Decimal,
        current_price: Decimal,
        spread_pips: Decimal,
        avg_atr_30d: Decimal | None = None,
    ) -> MarketRegime:
        """Classify market regime with priority: LOW_LIQ > HIGH_VOL > TRENDING > RANGING > UNKNOWN.

        Args:
            ema_20: 20-period exponential moving average.
            ema_50: 50-period exponential moving average.
            ema_200: 200-period exponential moving average.
            atr_14: 14-period average true range.
            current_price: Latest bid/ask midpoint.
            spread_pips: Current spread in pips.
            avg_atr_30d: Rolling 30-day average ATR. None if insufficient history.

        Returns:
            MarketRegime enum value.
        """
        # --- Priority 1: Low liquidity (wide spread) ---
        if spread_pips > _LOW_LIQ_SPREAD_THRESHOLD:
            logger.info(
                "regime_classified",
                regime=MarketRegime.LOW_LIQUIDITY.value,
                reason="spread_exceeds_threshold",
                spread_pips=str(spread_pips),
                threshold=str(_LOW_LIQ_SPREAD_THRESHOLD),
            )
            return MarketRegime.LOW_LIQUIDITY

        # --- Priority 2: High volatility (ATR spike vs 30d average) ---
        if avg_atr_30d is not None and avg_atr_30d > Decimal("0"):
            vol_threshold = _HIGH_VOL_ATR_MULTIPLIER * avg_atr_30d
            if atr_14 > vol_threshold:
                logger.info(
                    "regime_classified",
                    regime=MarketRegime.HIGH_VOLATILITY.value,
                    reason="atr_exceeds_30d_avg",
                    atr_14=str(atr_14),
                    avg_atr_30d=str(avg_atr_30d),
                    threshold=str(vol_threshold),
                )
                return MarketRegime.HIGH_VOLATILITY

        # --- EMA separation ratio (used by both TRENDING and RANGING) ---
        # Guard against zero ATR to prevent DivisionByZero
        if atr_14 <= Decimal("0"):
            logger.warning(
                "regime_classifier_zero_atr",
                atr_14=str(atr_14),
                fallback=MarketRegime.UNKNOWN.value,
            )
            return MarketRegime.UNKNOWN

        ema_separation = abs(ema_20 - ema_200)
        ema_atr_ratio = ema_separation / atr_14

        # --- Priority 3: Trending (strong EMA divergence) ---
        if ema_atr_ratio > _TRENDING_EMA_ATR_RATIO:
            logger.info(
                "regime_classified",
                regime=MarketRegime.TRENDING.value,
                reason="ema_separation_high",
                ema_atr_ratio=str(ema_atr_ratio),
                threshold=str(_TRENDING_EMA_ATR_RATIO),
            )
            return MarketRegime.TRENDING

        # --- Priority 4: Ranging (tight EMA convergence) ---
        if ema_atr_ratio < _RANGING_EMA_ATR_RATIO:
            logger.info(
                "regime_classified",
                regime=MarketRegime.RANGING.value,
                reason="ema_separation_low",
                ema_atr_ratio=str(ema_atr_ratio),
                threshold=str(_RANGING_EMA_ATR_RATIO),
            )
            return MarketRegime.RANGING

        # --- Priority 5: Indeterminate ---
        logger.info(
            "regime_classified",
            regime=MarketRegime.UNKNOWN.value,
            reason="no_condition_matched",
            ema_atr_ratio=str(ema_atr_ratio),
            spread_pips=str(spread_pips),
        )
        return MarketRegime.UNKNOWN
