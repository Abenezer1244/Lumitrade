"""
H4 Multi-Timeframe Trend Filter
=================================
USD_JPY-specific entry gate. Only allows H1 signals when H4 is strongly trending
AND the fast H4 EMA is aligned with the trade direction.

Filter conditions (both must pass):
  BUY:  H4 EMA5 > EMA10  AND  H4 ADX >= 25
  SELL: H4 EMA5 < EMA10  AND  H4 ADX >= 25

Backtest validation (April 2024 – April 2026, H4 data 3109 bars):
  33 trades | WR 54.5% | PF 4.19 | Sharpe 3.46 | MAR 5.71 | MaxDD 0.68% | MC 99.8%
  Walk-forward out-of-sample (30%): PF 6.82, Sharpe 5.60, MC 99.7%
  ADX plateau confirmed stable from ADX 23–29 (not a cliff cutoff).

Fail-open: returns None (allowed) when H4 candle data is insufficient.
Only applied to USD_JPY — other pairs pass through unchanged.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from ..core.models import Candle
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# Pairs that require the H4 EMA5/EMA10 + ADX trend filter
_H4_FILTERED_PAIRS: frozenset[str] = frozenset({"USD_JPY"})
_H4_EMA_FAST = 5
_H4_EMA_SLOW = 10
_H4_ADX_THRESHOLD = 25.0
_H4_MIN_CANDLES = 20


def compute_h4_trend_filter(
    candles_h4: list[Candle],
    action: str,
    pair: str,
) -> str | None:
    """
    Returns a blocking reason string if H4 trend conditions are not met,
    or None if the signal should be allowed through.

    Args:
        candles_h4: Recent H4 candles (fetched by CandleFetcher).
        action: "BUY", "SELL", or "HOLD".
        pair: Instrument pair (e.g. "USD_JPY").

    Returns:
        None  → signal is allowed.
        str   → human-readable reason the signal is blocked.
    """
    if pair not in _H4_FILTERED_PAIRS:
        return None  # filter only applies to designated pairs

    if action == "HOLD":
        return None

    if not candles_h4 or len(candles_h4) < _H4_MIN_CANDLES:
        logger.debug(
            "h4_trend_filter_skip_insufficient_data",
            pair=pair,
            candle_count=len(candles_h4) if candles_h4 else 0,
        )
        return None  # fail open — don't block on missing data

    closes = pd.Series([float(c.close) for c in candles_h4])
    highs  = pd.Series([float(c.high)  for c in candles_h4])
    lows   = pd.Series([float(c.low)   for c in candles_h4])

    try:
        ema_fast = ta.ema(closes, length=_H4_EMA_FAST)
        ema_slow = ta.ema(closes, length=_H4_EMA_SLOW)
        adx_df   = ta.adx(highs, lows, closes, length=14)
    except Exception as e:
        logger.warning("h4_trend_filter_compute_error", pair=pair, error=str(e))
        return None  # fail open

    if ema_fast is None or ema_slow is None or adx_df is None:
        return None

    e5  = ema_fast.iloc[-1]
    e10 = ema_slow.iloc[-1]

    adx_cols = [c for c in adx_df.columns if "ADX" in c.upper() and "DM" not in c.upper()]
    if not adx_cols:
        return None
    adx_val = adx_df[adx_cols[0]].iloc[-1]

    if pd.isna(e5) or pd.isna(e10) or pd.isna(adx_val):
        return None

    e5_f = float(e5)
    e10_f = float(e10)
    adx_f = float(adx_val)

    # Gate 1: H4 must be trending (ADX >= 25)
    if adx_f < _H4_ADX_THRESHOLD:
        logger.debug(
            "h4_trend_filter_adx_fail",
            pair=pair,
            action=action,
            h4_adx=f"{adx_f:.1f}",
            threshold=_H4_ADX_THRESHOLD,
        )
        return (
            f"H4 ADX={adx_f:.1f} < {_H4_ADX_THRESHOLD:.0f} "
            f"(H4 not trending — {action} blocked)"
        )

    # Gate 2: H4 fast EMA must be aligned with trade direction
    if action == "BUY" and e5_f <= e10_f:
        logger.debug(
            "h4_trend_filter_ema_fail",
            pair=pair,
            action=action,
            h4_ema5=f"{e5_f:.5f}",
            h4_ema10=f"{e10_f:.5f}",
        )
        return (
            f"H4 EMA{_H4_EMA_FAST}({e5_f:.5f}) <= EMA{_H4_EMA_SLOW}({e10_f:.5f}) "
            f"— bearish H4 momentum, BUY blocked"
        )

    if action == "SELL" and e5_f >= e10_f:
        logger.debug(
            "h4_trend_filter_ema_fail",
            pair=pair,
            action=action,
            h4_ema5=f"{e5_f:.5f}",
            h4_ema10=f"{e10_f:.5f}",
        )
        return (
            f"H4 EMA{_H4_EMA_FAST}({e5_f:.5f}) >= EMA{_H4_EMA_SLOW}({e10_f:.5f}) "
            f"— bullish H4 momentum, SELL blocked"
        )

    logger.info(
        "h4_trend_filter_passed",
        pair=pair,
        action=action,
        h4_adx=f"{adx_f:.1f}",
        h4_ema5=f"{e5_f:.5f}",
        h4_ema10=f"{e10_f:.5f}",
    )
    return None  # signal is allowed
