"""
Lumitrade Data Validator
==========================
Validates all incoming market data before use.
5 checks: freshness, spike detection, spread, OHLC integrity, gap detection.
Per BDS Section 4.2.
"""

from collections import deque
from datetime import datetime, timezone
from decimal import Decimal

from ..core.models import Candle, DataQuality, PriceTick
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

STALE_THRESHOLD_SECONDS = 5
SPIKE_STD_MULTIPLIER = Decimal("5.0")  # 5 stddev — avoid false positives on normal tick noise
ROLLING_WINDOW = 100  # ~25 seconds of ticks at 250ms — larger window = more stable baseline

# Per-instrument max spread (in pips). Gold/metals have wider spreads.
MAX_SPREAD_PIPS: dict[str, Decimal] = {
    "EUR_USD": Decimal("5.0"),
    "GBP_USD": Decimal("5.0"),
    "USD_JPY": Decimal("5.0"),
    "USD_CHF": Decimal("5.0"),
    "AUD_USD": Decimal("5.0"),
    "USD_CAD": Decimal("5.0"),
    "NZD_USD": Decimal("5.0"),
    "XAU_USD": Decimal("200"),   # Gold spread wider on practice account
    "BTC_USD": Decimal("200"),   # BTC pip=$1; $200 ceiling catches pathological spreads only
}
DEFAULT_MAX_SPREAD = Decimal("5.0")


class DataValidator:
    """Validates all incoming market data before use."""

    def __init__(self) -> None:
        self._price_history: dict[str, deque[Decimal]] = {}

    def validate_tick(self, tick: PriceTick) -> DataQuality:
        """Full validation pipeline for a price tick."""
        is_fresh = self._check_freshness(tick)
        spike_detected = self._check_spike(tick)
        spread_ok = self._check_spread(tick)

        # Always update history — skipping on spike causes stale-window lockout
        self._update_price_history(tick)

        quality = DataQuality(
            is_fresh=is_fresh,
            spike_detected=spike_detected,
            spread_acceptable=spread_ok,
            candles_complete=True,  # Set by candle validator separately
            ohlc_valid=True,
        )

        if not quality.is_tradeable:
            logger.warning(
                "data_quality_check_failed",
                pair=tick.pair,
                fresh=is_fresh,
                spike=spike_detected,
                spread=spread_ok,
            )
        return quality

    def validate_candles(self, candles: list[Candle]) -> tuple[bool, bool]:
        """
        Validate candle series integrity.
        Returns (ohlc_valid, candles_complete) tuple.
        """
        if not candles:
            return True, True

        ohlc_valid = True
        for candle in candles:
            if not self._check_ohlc(candle):
                logger.error(
                    "ohlc_integrity_failed",
                    candle_time=str(candle.time),
                    timeframe=candle.timeframe,
                )
                ohlc_valid = False
                break

        gaps_ok = self._check_gaps(candles)
        return ohlc_valid, gaps_ok

    def _check_freshness(self, tick: PriceTick) -> bool:
        """Price must be less than STALE_THRESHOLD_SECONDS old."""
        age = (datetime.now(timezone.utc) - tick.timestamp).total_seconds()
        return age <= STALE_THRESHOLD_SECONDS

    def _check_spike(self, tick: PriceTick) -> bool:
        """Detect price spikes beyond 3 standard deviations from rolling mean."""
        history = self._price_history.get(tick.pair)
        if not history or len(history) < ROLLING_WINDOW:
            return False  # Not enough history to detect spike

        mean = sum(history) / len(history)
        variance = sum((p - mean) ** 2 for p in history) / len(history)
        std = variance ** Decimal("0.5")

        if std == 0:
            return False

        z_score = abs(tick.mid - mean) / std
        return z_score > SPIKE_STD_MULTIPLIER

    def _check_spread(self, tick: PriceTick) -> bool:
        """Spread must be within per-instrument ceiling."""
        max_spread = MAX_SPREAD_PIPS.get(tick.pair, DEFAULT_MAX_SPREAD)
        return tick.spread_pips <= max_spread

    def _check_ohlc(self, c: Candle) -> bool:
        """Validate Low <= Open/Close <= High."""
        return c.low <= c.open <= c.high and c.low <= c.close <= c.high

    def _check_gaps(self, candles: list[Candle]) -> bool:
        """Detect unexpected gaps between consecutive candles.

        Weekend gaps (Fri 21:00 UTC → Sun/Mon) are normal in forex
        and should NOT fail validation.
        """
        tf_seconds = {
            "M5": 300,
            "M15": 900,
            "H1": 3600,
            "H4": 14400,
            "D": 86400,
        }
        if len(candles) < 2:
            return True

        expected = tf_seconds.get(candles[0].timeframe, 900)
        for i in range(1, len(candles)):
            gap = (candles[i].time - candles[i - 1].time).total_seconds()
            if gap > expected * 1.5:
                # Check if this is a normal weekend gap
                prev_day = candles[i - 1].time.weekday()  # 0=Mon, 4=Fri
                if prev_day == 4 and gap < 260000:  # Friday → Monday, max ~72h
                    continue  # Normal weekend gap — skip
                logger.warning(
                    "candle_gap_detected",
                    gap_seconds=gap,
                    expected=expected,
                    candle_time=str(candles[i].time),
                )
                return False
        return True

    def _update_price_history(self, tick: PriceTick) -> None:
        """Add tick to rolling price buffer for spike detection."""
        if tick.pair not in self._price_history:
            self._price_history[tick.pair] = deque(maxlen=200)
        self._price_history[tick.pair].append(tick.mid)
