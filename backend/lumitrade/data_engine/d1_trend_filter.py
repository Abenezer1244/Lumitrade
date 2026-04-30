"""
D1 Multi-Timeframe Trend Filter
=================================
BTC_USD-specific entry gate. Only allows H1 signals when the D1 (daily)
trend is aligned with the proposed trade direction.

Filter condition:
  BUY:  D1 EMA5 > EMA10  (daily uptrend)
  SELL: D1 EMA5 < EMA10  (daily downtrend)
  ADX gate: not required (plateau sweep confirmed ADX adds no information for BTC D1)

Backtest validation (April 2024 – April 2026, H1 data 12434 bars):
  16 trades | WR 81.2% | PF 5.29 | Sharpe 4.84 | MAR 5.51 | MaxDD 0.53% | MC 99.7%
  Walk-forward in-sample (70%): N=12, PF=3.41, Sharpe=3.47, MC=96.2% [5/5]
  Walk-forward OOS (30%): N=4, PF=999, MC=100% [4/5] — OOS sample small, PAPER MODE only

  NOTE: N=16 is below the N>=20 statistical confidence threshold used for USD_CAD/USD_JPY.
  BTC is permitted in live_pairs but risk is capped at default 0.5% per trade (~8/year).
  Promote to full live confidence after accumulating 20+ real-market trades under this filter.

D1 bars are synthesized from the 30 most recent D-granularity candles fetched by CandleFetcher.

Fail-open: returns None (allowed) when D1 candle data is insufficient.
Only applied to BTC_USD — other pairs pass through unchanged.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from ..core.models import Candle
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

_D1_FILTERED_PAIRS: frozenset[str] = frozenset({"BTC_USD"})
_D1_EMA_FAST = 5
_D1_EMA_SLOW = 10
_D1_MIN_CANDLES = 12


def compute_d1_trend_filter(
    candles_d1: list[Candle],
    action: str,
    pair: str,
) -> str | None:
    """
    Returns a blocking reason string if D1 trend is not aligned with the signal,
    or None if the signal should be allowed through.

    Args:
        candles_d1: Recent D1 candles (30 bars, fetched by CandleFetcher with granularity=D).
        action: "BUY", "SELL", or "HOLD".
        pair: Instrument pair (e.g. "BTC_USD").

    Returns:
        None  -> signal is allowed.
        str   -> human-readable reason the signal is blocked.
    """
    if pair not in _D1_FILTERED_PAIRS:
        return None

    if action == "HOLD":
        return None

    if not candles_d1 or len(candles_d1) < _D1_MIN_CANDLES:
        logger.debug(
            "d1_trend_filter_skip_insufficient_data",
            pair=pair,
            candle_count=len(candles_d1) if candles_d1 else 0,
        )
        return None  # fail open

    closes = pd.Series([float(c.close) for c in candles_d1])

    try:
        ema_fast = ta.ema(closes, length=_D1_EMA_FAST)
        ema_slow = ta.ema(closes, length=_D1_EMA_SLOW)
    except Exception as e:
        logger.warning("d1_trend_filter_compute_error", pair=pair, error=str(e))
        return None  # fail open

    if ema_fast is None or ema_slow is None:
        return None

    e5  = ema_fast.iloc[-1]
    e10 = ema_slow.iloc[-1]

    if pd.isna(e5) or pd.isna(e10):
        return None

    e5_f  = float(e5)
    e10_f = float(e10)

    if action == "BUY" and e5_f <= e10_f:
        logger.debug(
            "d1_trend_filter_ema_fail",
            pair=pair,
            action=action,
            d1_ema5=f"{e5_f:.2f}",
            d1_ema10=f"{e10_f:.2f}",
        )
        return (
            f"D1 EMA{_D1_EMA_FAST}({e5_f:.2f}) <= EMA{_D1_EMA_SLOW}({e10_f:.2f}) "
            f"-- bearish D1 momentum, BUY blocked"
        )

    if action == "SELL" and e5_f >= e10_f:
        logger.debug(
            "d1_trend_filter_ema_fail",
            pair=pair,
            action=action,
            d1_ema5=f"{e5_f:.2f}",
            d1_ema10=f"{e10_f:.2f}",
        )
        return (
            f"D1 EMA{_D1_EMA_FAST}({e5_f:.2f}) >= EMA{_D1_EMA_SLOW}({e10_f:.2f}) "
            f"-- bullish D1 momentum, SELL blocked"
        )

    logger.info(
        "d1_trend_filter_passed",
        pair=pair,
        action=action,
        d1_ema5=f"{e5_f:.2f}",
        d1_ema10=f"{e10_f:.2f}",
    )
    return None  # signal is allowed
