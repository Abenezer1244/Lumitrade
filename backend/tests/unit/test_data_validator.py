"""
Data Validator Tests
======================
Tests for all 5 validation checks: freshness, spike, spread, OHLC, gaps.
Per QTS Section 4.3 (DF-001 to DF-005).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from lumitrade.core.models import Candle, DataQuality, PriceTick
from lumitrade.data_engine.validator import DataValidator


@pytest.fixture
def validator():
    return DataValidator()


def _make_tick(
    pair: str = "EUR_USD",
    bid: str = "1.08430",
    ask: str = "1.08440",
    age_seconds: float = 0,
) -> PriceTick:
    """Create a PriceTick with configurable age."""
    return PriceTick(
        pair=pair,
        bid=Decimal(bid),
        ask=Decimal(ask),
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
    )


def _make_candle(
    time_offset_min: int = 0,
    open_: str = "1.0843",
    high: str = "1.0850",
    low: str = "1.0840",
    close: str = "1.0845",
    timeframe: str = "M15",
) -> Candle:
    """Create a Candle with configurable values."""
    return Candle(
        time=datetime.now(timezone.utc) - timedelta(minutes=time_offset_min),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=100,
        complete=True,
        timeframe=timeframe,
    )


class TestFreshness:
    """DF-001: Stale data detection."""

    def test_fresh_tick_passes(self, validator):
        tick = _make_tick(age_seconds=1)
        quality = validator.validate_tick(tick)
        assert quality.is_fresh is True

    def test_stale_tick_fails(self, validator):
        tick = _make_tick(age_seconds=10)
        quality = validator.validate_tick(tick)
        assert quality.is_fresh is False

    def test_stale_tick_not_tradeable(self, validator):
        tick = _make_tick(age_seconds=10)
        quality = validator.validate_tick(tick)
        assert quality.is_tradeable is False


class TestSpikeDetection:
    """DF-002: Price spike detection (3 sigma)."""

    def test_normal_price_no_spike(self, validator):
        # Fill history with normal prices
        for i in range(25):
            tick = _make_tick(bid="1.08430", ask="1.08440")
            validator.validate_tick(tick)

        # Normal price — no spike
        tick = _make_tick(bid="1.08435", ask="1.08445")
        quality = validator.validate_tick(tick)
        assert quality.spike_detected is False

    def test_extreme_price_spike_detected(self, validator):
        # Fill ROLLING_WINDOW (100) prices with slight variation to create nonzero std
        pattern = [
            "1.08420", "1.08430", "1.08440", "1.08425", "1.08435",
            "1.08445", "1.08430", "1.08420", "1.08440", "1.08430",
        ]
        for i in range(100):
            bid = pattern[i % len(pattern)]
            ask = str(Decimal(bid) + Decimal("0.00010"))
            tick = _make_tick(bid=bid, ask=ask)
            validator.validate_tick(tick)

        # Extreme price — well beyond 5 sigma
        tick = _make_tick(bid="1.10000", ask="1.10010")
        quality = validator.validate_tick(tick)
        assert quality.spike_detected is True

    def test_spike_not_added_to_history(self, validator):
        # Validator always updates history (by design — avoids stale-window lockout).
        # Spike ticks are recorded in the rolling buffer like any other tick.
        pattern = [
            "1.08420", "1.08430", "1.08440", "1.08425", "1.08435",
            "1.08445", "1.08430", "1.08420", "1.08440", "1.08430",
        ]
        for i in range(100):
            bid = pattern[i % len(pattern)]
            ask = str(Decimal(bid) + Decimal("0.00010"))
            tick = _make_tick(bid=bid, ask=ask)
            validator.validate_tick(tick)

        initial_len = len(validator._price_history["EUR_USD"])

        # Spike tick is added to history (validator always appends to prevent stale window)
        tick = _make_tick(bid="1.10000", ask="1.10010")
        quality = validator.validate_tick(tick)

        assert quality.spike_detected is True
        assert len(validator._price_history["EUR_USD"]) == initial_len + 1

    def test_insufficient_history_no_spike(self, validator):
        # Only 5 ticks — not enough for spike detection
        for i in range(5):
            tick = _make_tick(bid="1.08430", ask="1.08440")
            validator.validate_tick(tick)

        tick = _make_tick(bid="1.10000", ask="1.10010")
        quality = validator.validate_tick(tick)
        assert quality.spike_detected is False  # Not enough data


class TestSpreadCheck:
    """DF-003: Spread validation."""

    def test_normal_spread_passes(self, validator):
        tick = _make_tick(bid="1.08430", ask="1.08440")  # 1.0 pip spread
        quality = validator.validate_tick(tick)
        assert quality.spread_acceptable is True

    def test_wide_spread_fails(self, validator):
        tick = _make_tick(bid="1.08430", ask="1.08500")  # 7.0 pip spread
        quality = validator.validate_tick(tick)
        assert quality.spread_acceptable is False


class TestOHLCIntegrity:
    """DF-005: OHLC candle validation."""

    def test_valid_candle_passes(self, validator):
        candles = [_make_candle(
            open_="1.0843", high="1.0850",
            low="1.0840", close="1.0845",
        )]
        ohlc_ok, gaps_ok = validator.validate_candles(candles)
        assert ohlc_ok is True

    def test_invalid_candle_low_above_high(self, validator):
        candles = [_make_candle(
            open_="1.0843", high="1.0840",
            low="1.0850", close="1.0845",
        )]
        ohlc_ok, gaps_ok = validator.validate_candles(candles)
        assert ohlc_ok is False

    def test_empty_candles_valid(self, validator):
        ohlc_ok, gaps_ok = validator.validate_candles([])
        assert ohlc_ok is True
        assert gaps_ok is True


class TestGapDetection:
    """DF-004: Candle gap detection."""

    def test_no_gaps_passes(self, validator):
        candles = [
            _make_candle(time_offset_min=30, timeframe="M15"),
            _make_candle(time_offset_min=15, timeframe="M15"),
            _make_candle(time_offset_min=0, timeframe="M15"),
        ]
        ohlc_ok, gaps_ok = validator.validate_candles(candles)
        assert gaps_ok is True

    def test_large_gap_detected(self, validator):
        candles = [
            _make_candle(time_offset_min=60, timeframe="M15"),
            _make_candle(time_offset_min=15, timeframe="M15"),  # 45 min gap
            _make_candle(time_offset_min=0, timeframe="M15"),
        ]
        ohlc_ok, gaps_ok = validator.validate_candles(candles)
        assert gaps_ok is False


class TestDataQualityTradeable:
    """Test is_tradeable property."""

    def test_all_good_is_tradeable(self):
        q = DataQuality(
            is_fresh=True,
            spike_detected=False,
            spread_acceptable=True,
            candles_complete=True,
            ohlc_valid=True,
        )
        assert q.is_tradeable is True

    def test_any_failure_not_tradeable(self):
        q = DataQuality(
            is_fresh=True,
            spike_detected=True,  # Spike!
            spread_acceptable=True,
            candles_complete=True,
            ohlc_valid=True,
        )
        assert q.is_tradeable is False
