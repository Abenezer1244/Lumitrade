"""
Lumitrade Chaos Tests — Data Failures (DF-001 to DF-008)
==========================================================
Validates the DataValidator rejects bad market data and passes clean data.
These are the gatekeepers: if bad data leaks through, we trade on garbage.

Per QTS v2.0 Section 4.2.
"""

import pytest
from collections import deque
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from lumitrade.core.models import Candle, PriceTick
from lumitrade.data_engine.validator import DataValidator, ROLLING_WINDOW


@pytest.mark.chaos
class TestDataFailures:
    """DF-001 to DF-008: Data validation under hostile conditions."""

    @pytest.fixture
    def validator(self) -> DataValidator:
        return DataValidator()

    @pytest.fixture
    def fresh_tick(self) -> PriceTick:
        """A clean EUR_USD tick with tight spread, timestamped now."""
        return PriceTick(
            pair="EUR_USD",
            bid=Decimal("1.10000"),
            ask=Decimal("1.10020"),  # 2 pip spread
            timestamp=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def validator_with_history(self, validator: DataValidator) -> DataValidator:
        """Validator pre-loaded with 20 stable prices for spike detection."""
        history = deque(maxlen=200)
        for i in range(ROLLING_WINDOW):
            # Tight range around 1.10010
            history.append(Decimal("1.10010") + Decimal(str(i)) * Decimal("0.00001"))
        validator._price_history["EUR_USD"] = history
        return validator

    # ── DF-001: Stale price detected ──────────────────────────────

    def test_df001_stale_price_detected(self, validator: DataValidator):
        """DF-001: Price tick older than 5 seconds is marked stale and not tradeable."""
        stale_tick = PriceTick(
            pair="EUR_USD",
            bid=Decimal("1.10000"),
            ask=Decimal("1.10020"),
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        quality = validator.validate_tick(stale_tick)

        assert quality.is_fresh is False
        assert quality.is_tradeable is False

    # ── DF-002: Price spike detected ──────────────────────────────

    def test_df002_price_spike_detected(
        self, validator_with_history: DataValidator
    ):
        """DF-002: Price >3 sigma from rolling mean is flagged as spike."""
        # The history is centered around ~1.10020. A massive jump triggers spike.
        spike_tick = PriceTick(
            pair="EUR_USD",
            bid=Decimal("1.15000"),
            ask=Decimal("1.15020"),
            timestamp=datetime.now(timezone.utc),
        )
        quality = validator_with_history.validate_tick(spike_tick)

        assert quality.spike_detected is True
        assert quality.is_tradeable is False

    # ── DF-003: Wide spread rejected ──────────────────────────────

    def test_df003_wide_spread_rejected(self, validator: DataValidator):
        """DF-003: Spread wider than 5 pips is rejected."""
        wide_spread_tick = PriceTick(
            pair="EUR_USD",
            bid=Decimal("1.10000"),
            ask=Decimal("1.10060"),  # 6 pip spread
            timestamp=datetime.now(timezone.utc),
        )
        quality = validator.validate_tick(wide_spread_tick)

        assert quality.spread_acceptable is False
        assert quality.is_tradeable is False

    # ── DF-004: Candle gap detected ───────────────────────────────

    def test_df004_candle_gap_detected(self, validator: DataValidator):
        """DF-004: Gap between candles > 1.5x expected interval returns (True, False)."""
        base_time = datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc)
        candles = [
            Candle(
                time=base_time,
                open=Decimal("1.1000"),
                high=Decimal("1.1010"),
                low=Decimal("1.0990"),
                close=Decimal("1.1005"),
                volume=100,
                complete=True,
                timeframe="M15",
            ),
            # Gap: 45 minutes instead of 15 (3x expected, > 1.5x threshold)
            Candle(
                time=base_time + timedelta(minutes=45),
                open=Decimal("1.1005"),
                high=Decimal("1.1015"),
                low=Decimal("1.0995"),
                close=Decimal("1.1010"),
                volume=100,
                complete=True,
                timeframe="M15",
            ),
        ]
        ohlc_valid, candles_complete = validator.validate_candles(candles)

        assert ohlc_valid is True
        assert candles_complete is False

    # ── DF-005: OHLC integrity violation ──────────────────────────

    def test_df005_ohlc_integrity_violation(self, validator: DataValidator):
        """DF-005: Candle with low > open returns (False, True)."""
        base_time = datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc)
        candles = [
            Candle(
                time=base_time,
                open=Decimal("1.0990"),  # open < low — OHLC violation
                high=Decimal("1.1010"),
                low=Decimal("1.1000"),
                close=Decimal("1.1005"),
                volume=100,
                complete=True,
                timeframe="M15",
            ),
        ]
        ohlc_valid, candles_complete = validator.validate_candles(candles)

        assert ohlc_valid is False
        assert candles_complete is True

    # ── DF-006: Spike not added to history ────────────────────────

    def test_df006_spike_not_added_to_history(
        self, validator_with_history: DataValidator
    ):
        """DF-006: When a spike is detected, the tick is NOT added to price history."""
        history_len_before = len(
            validator_with_history._price_history["EUR_USD"]
        )

        spike_tick = PriceTick(
            pair="EUR_USD",
            bid=Decimal("1.15000"),
            ask=Decimal("1.15020"),
            timestamp=datetime.now(timezone.utc),
        )
        validator_with_history.validate_tick(spike_tick)

        history_len_after = len(
            validator_with_history._price_history["EUR_USD"]
        )
        assert history_len_after == history_len_before

    # ── DF-007: Clean data passes all checks ──────────────────────

    def test_df007_clean_data_passes(self, validator: DataValidator, fresh_tick: PriceTick):
        """DF-007: A perfectly valid tick passes all checks and is tradeable."""
        quality = validator.validate_tick(fresh_tick)

        assert quality.is_fresh is True
        assert quality.spike_detected is False
        assert quality.spread_acceptable is True
        assert quality.is_tradeable is True

    # ── DF-008: Empty candle list returns (True, True) ────────────

    def test_df008_empty_candle_list(self, validator: DataValidator):
        """DF-008: Empty candle list is valid — no data to fail on."""
        ohlc_valid, candles_complete = validator.validate_candles([])

        assert ohlc_valid is True
        assert candles_complete is True
