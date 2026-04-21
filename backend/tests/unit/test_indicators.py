"""Indicator compute tests.

Regression tests for indicator pipeline. Primarily guards against
Bug #1 (candle_fetcher fetched 50 candles, making EMA(200) silently 0
for every signal ever produced).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from lumitrade.core.models import Candle
from lumitrade.data_engine.candle_fetcher import CandleFetcher
from lumitrade.data_engine.indicators import compute_indicators


def _synthetic_candles(n: int, start: Decimal = Decimal("1.3700")) -> list[Candle]:
    """Build n synthetic H1 candles with a slight uptrend + oscillation."""
    out: list[Candle] = []
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        # gentle uptrend + oscillation so EMAs separate meaningfully
        base = start + Decimal(str(i)) * Decimal("0.00010")
        osc = Decimal(str(math.sin(i / 5.0) * 0.0005))
        price = base + osc
        out.append(
            Candle(
                time=t0 + timedelta(hours=i),
                open=price,
                high=price + Decimal("0.00020"),
                low=price - Decimal("0.00020"),
                close=price + Decimal("0.00005"),
                volume=100,
                complete=True,
                timeframe="H1",
            )
        )
    return out


class TestIndicatorCompute:
    def test_ema200_zero_with_insufficient_candles(self) -> None:
        """Guard-rail: fewer than 200 candles → ema_200 must be 0 (current behavior)."""
        ind = compute_indicators(_synthetic_candles(150))
        assert ind.ema_20 > 0, "ema_20 should compute with 150 candles"
        assert ind.ema_50 > 0, "ema_50 should compute with 150 candles"
        assert ind.ema_200 == 0, "ema_200 should be 0 with <200 candles"

    def test_ema200_computes_with_sufficient_candles(self) -> None:
        """Core Bug #1 regression: feeding 200+ candles must produce ema_200 > 0.

        Before the fix, candle_fetcher returned 50 candles per timeframe,
        which silently produced ema_200 = 0 on EVERY signal. The quant
        engine's EMA_TREND strategy then short-circuited to HOLD on every
        call, collapsing the 3-strategy ensemble to MOMENTUM-only.
        """
        ind = compute_indicators(_synthetic_candles(250))
        assert ind.ema_20 > 0
        assert ind.ema_50 > 0
        assert ind.ema_200 > 0, (
            "ema_200 is 0 despite 250 candles — Bug #1 is back. "
            "Check candle_fetcher.fetch_all_timeframes and indicator compute."
        )

    def test_all_indicators_populated_at_250_candles(self) -> None:
        """At the production candle count (250 H1), every indicator must be non-zero."""
        ind = compute_indicators(_synthetic_candles(250))
        assert ind.rsi_14 > 0
        assert ind.ema_20 > 0
        assert ind.ema_50 > 0
        assert ind.ema_200 > 0
        assert ind.atr_14 > 0
        assert ind.bb_upper > 0
        assert ind.bb_mid > 0
        assert ind.bb_lower > 0
        assert ind.adx_14 > 0


class TestCandleFetcherContract:
    def test_fetch_all_timeframes_uses_production_counts(self) -> None:
        """Contract test: fetch_all_timeframes must request ≥200 H1 candles.

        Complements the unit test above — even if compute_indicators is
        correct, a regression in the fetcher undoes the fix silently.
        """
        import inspect

        src = inspect.getsource(CandleFetcher.fetch_all_timeframes)
        assert "H1" in src, "H1 timeframe missing from fetch_all_timeframes"
        # Must request at least 200 H1 candles. Current setting: 250.
        # We assert the minimum (200) so tuning the count doesn't break the test.
        import re

        h1_count_match = re.search(r'"H1"\s*:\s*(\d+)', src)
        assert h1_count_match, "Could not parse H1 count from fetch_all_timeframes"
        h1_count = int(h1_count_match.group(1))
        assert h1_count >= 200, (
            f"H1 candle count is {h1_count}; EMA(200) requires ≥200 candles. "
            "Bug #1 regression risk — raise the count."
        )
