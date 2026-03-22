"""
Lumitrade Indicator Computer
===============================
Computes technical indicators using pandas-ta.
RSI(14), MACD(12,26,9), EMA(20,50,200), ATR(14), Bollinger Bands(20,2).
All values returned as Decimal in IndicatorSet dataclass.
Per BDS Section 4 and PRD Section 10.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import pandas as pd
import pandas_ta as ta

from ..core.models import Candle, IndicatorSet
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


def _to_decimal(value: float | None, default: str = "0") -> Decimal:
    """Safely convert a float/NaN to Decimal."""
    if value is None or pd.isna(value):
        return Decimal(default)
    try:
        return Decimal(str(round(value, 10)))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def compute_indicators(candles: list[Candle]) -> IndicatorSet:
    """
    Compute all required technical indicators from candle data.
    Requires at least 200 candles for EMA(200) to be meaningful.
    Returns IndicatorSet with all values as Decimal.
    """
    if not candles:
        return _empty_indicator_set()

    # Build DataFrame from candles
    df = pd.DataFrame(
        [
            {
                "time": c.time,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": c.volume,
            }
            for c in candles
        ]
    )
    df.set_index("time", inplace=True)
    df.sort_index(inplace=True)

    if len(df) < 14:
        logger.warning(
            "insufficient_candles_for_indicators", count=len(df)
        )
        return _empty_indicator_set()

    # Compute indicators
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # RSI(14)
    rsi = ta.rsi(close, length=14)
    rsi_val = rsi.iloc[-1] if rsi is not None and len(rsi) > 0 else None

    # MACD(12, 26, 9) — returns DataFrame with 3 columns
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and len(macd_df) > 0:
        macd_line = macd_df.iloc[-1, 0]  # MACD line
        macd_signal = macd_df.iloc[-1, 1]  # Signal line
        macd_hist = macd_df.iloc[-1, 2]  # Histogram
    else:
        macd_line = macd_signal = macd_hist = None

    # EMA(20, 50, 200)
    ema_20 = ta.ema(close, length=20)
    ema_50 = ta.ema(close, length=50)
    ema_200 = ta.ema(close, length=200)

    ema_20_val = ema_20.iloc[-1] if ema_20 is not None and len(ema_20) > 0 else None
    ema_50_val = ema_50.iloc[-1] if ema_50 is not None and len(ema_50) > 0 else None
    ema_200_val = ema_200.iloc[-1] if ema_200 is not None and len(ema_200) > 0 else None

    # ATR(14)
    atr = ta.atr(high, low, close, length=14)
    atr_val = atr.iloc[-1] if atr is not None and len(atr) > 0 else None

    # Bollinger Bands(20, 2)
    bb = ta.bbands(close, length=20, std=2)
    if bb is not None and len(bb) > 0:
        bb_lower = bb.iloc[-1, 0]  # Lower band
        bb_mid = bb.iloc[-1, 1]  # Mid band
        bb_upper = bb.iloc[-1, 2]  # Upper band
    else:
        bb_lower = bb_mid = bb_upper = None

    return IndicatorSet(
        rsi_14=_to_decimal(rsi_val),
        macd_line=_to_decimal(macd_line),
        macd_signal=_to_decimal(macd_signal),
        macd_histogram=_to_decimal(macd_hist),
        ema_20=_to_decimal(ema_20_val),
        ema_50=_to_decimal(ema_50_val),
        ema_200=_to_decimal(ema_200_val),
        atr_14=_to_decimal(atr_val),
        bb_upper=_to_decimal(bb_upper),
        bb_mid=_to_decimal(bb_mid),
        bb_lower=_to_decimal(bb_lower),
        computed_at=datetime.now(timezone.utc),
    )


def _empty_indicator_set() -> IndicatorSet:
    """Return an IndicatorSet with all zeros for insufficient data."""
    return IndicatorSet(
        rsi_14=Decimal("0"),
        macd_line=Decimal("0"),
        macd_signal=Decimal("0"),
        macd_histogram=Decimal("0"),
        ema_20=Decimal("0"),
        ema_50=Decimal("0"),
        ema_200=Decimal("0"),
        atr_14=Decimal("0"),
        bb_upper=Decimal("0"),
        bb_mid=Decimal("0"),
        bb_lower=Decimal("0"),
        computed_at=datetime.now(timezone.utc),
    )
