"""
Performance Latency Tests — PF-001 to PF-012
================================================
Per QTS v2.0 Section 6.1: Backend latency benchmarks.
These tests verify that critical path operations complete within
their specified time budgets using local (non-network) operations.

No real API calls — tests measure computation overhead only.
"""

import asyncio
import time
from decimal import Decimal
from datetime import datetime, timezone

import pytest

from lumitrade.core.enums import (
    Action,
    Direction,
    MarketRegime,
    NewsImpact,
    Outcome,
    Session,
)
from lumitrade.core.models import (
    AccountContext,
    Candle,
    DataQuality,
    IndicatorSet,
    MarketSnapshot,
    NewsEvent,
    PerformanceContext,
    PriceTick,
    TradeSummary,
)
from lumitrade.utils.pip_math import (
    calculate_position_size,
    pip_size,
    pip_value_per_unit,
    pips_between,
)
from lumitrade.utils.time_utils import get_current_session, is_market_open
from lumitrade.data_engine.validator import DataValidator
from lumitrade.data_engine.indicators import compute_indicators
from lumitrade.ai_brain.validator import AIOutputValidator
from lumitrade.ai_brain.confidence import ConfidenceAdjuster
from lumitrade.ai_brain.fallback import RuleBasedFallback
from lumitrade.execution_engine.circuit_breaker import CircuitBreaker


# ── Helpers ────────────────────────────────────────────────────

NOW = datetime.now(timezone.utc)


def _make_candle(idx: int) -> Candle:
    base = Decimal("1.10000") + Decimal(str(idx)) * Decimal("0.00010")
    # Unique timestamps: spread across multiple days to avoid duplicates
    day = 1 + (idx // 24)
    hour = idx % 24
    return Candle(
        time=datetime(2026, 3, day, hour, 0, tzinfo=timezone.utc),
        open=base,
        high=base + Decimal("0.00050"),
        low=base - Decimal("0.00030"),
        close=base + Decimal("0.00020"),
        volume=1000 + idx * 10,
        complete=True,
        timeframe="H1",
    )


def _make_tick(pair: str = "EUR_USD") -> PriceTick:
    return PriceTick(
        pair=pair,
        bid=Decimal("1.10000"),
        ask=Decimal("1.10020"),
        timestamp=NOW,
    )


def _make_indicators() -> IndicatorSet:
    return IndicatorSet(
        rsi_14=Decimal("55"),
        macd_line=Decimal("0.0002"),
        macd_signal=Decimal("0.0001"),
        macd_histogram=Decimal("0.0001"),
        ema_20=Decimal("1.0990"),
        ema_50=Decimal("1.0980"),
        ema_200=Decimal("1.0950"),
        atr_14=Decimal("0.0040"),
        bb_upper=Decimal("1.1050"),
        bb_mid=Decimal("1.1000"),
        bb_lower=Decimal("1.0950"),
        computed_at=NOW,
    )


def _make_snapshot(pair: str = "EUR_USD") -> MarketSnapshot:
    candles = [_make_candle(i) for i in range(50)]
    return MarketSnapshot(
        pair=pair,
        session=Session.LONDON,
        timestamp=NOW,
        bid=Decimal("1.10000"),
        ask=Decimal("1.10020"),
        spread_pips=Decimal("2.0"),
        candles_m15=candles,
        candles_h1=candles,
        candles_h4=candles,
        indicators=_make_indicators(),
        news_events=[],
        recent_trades=[],
        account_context=AccountContext(
            account_id="test-account",
            balance=Decimal("100000"),
            equity=Decimal("100000"),
            margin_used=Decimal("0"),
            open_trade_count=0,
            daily_pnl=Decimal("0"),
            fetched_at=NOW,
        ),
        data_quality=DataQuality(
            is_fresh=True,
            spike_detected=False,
            spread_acceptable=True,
            candles_complete=True,
            ohlc_valid=True,
        ),
    )


# ── PF-001: Pip Math Throughput ────────────────────────────────

class TestPipMathPerformance:
    """PF-001 to PF-003: Pip math operations must complete < 1ms each."""

    def test_pip_size_throughput(self):
        """PF-001: 10,000 pip_size lookups < 100ms."""
        start = time.perf_counter()
        for _ in range(10_000):
            pip_size("EUR_USD")
            pip_size("USD_JPY")
            pip_size("GBP_USD")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"10K pip_size calls took {elapsed:.3f}s (limit 0.1s)"

    def test_pips_between_throughput(self):
        """PF-002: 10,000 pips_between calculations < 200ms."""
        start = time.perf_counter()
        for _ in range(10_000):
            pips_between(Decimal("1.10000"), Decimal("1.10500"), "EUR_USD")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"10K pips_between took {elapsed:.3f}s (limit 0.2s)"

    def test_position_sizing_throughput(self):
        """PF-003: 1,000 position size calculations < 200ms."""
        start = time.perf_counter()
        for _ in range(1_000):
            calculate_position_size(
                balance=Decimal("100000"),
                risk_pct=Decimal("0.02"),
                sl_pips=Decimal("25"),
                pair="EUR_USD",
                current_rate=Decimal("1.10000"),
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"1K sizing calls took {elapsed:.3f}s (limit 0.2s)"


# ── PF-004: Data Validation Throughput ─────────────────────────

class TestDataValidationPerformance:
    """PF-004 to PF-005: Tick validation must be fast."""

    def test_tick_validation_throughput(self):
        """PF-004: 1,000 tick validations < 200ms."""
        validator = DataValidator()
        tick = _make_tick()
        start = time.perf_counter()
        for _ in range(1_000):
            validator.validate_tick(tick)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"1K tick validations took {elapsed:.3f}s (limit 0.2s)"

    def test_candle_validation_throughput(self):
        """PF-005: 100 candle batch validations < 500ms."""
        validator = DataValidator()
        candles = [_make_candle(i) for i in range(200)]
        start = time.perf_counter()
        for _ in range(100):
            validator.validate_candles(candles)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"100 candle validations took {elapsed:.3f}s (limit 0.5s)"


# ── PF-006: Indicator Computation ──────────────────────────────

class TestIndicatorPerformance:
    """PF-006: Indicator computation on 200 candles < 500ms."""

    def test_indicator_computation_latency(self):
        """PF-006: compute_indicators on 200 candles < 500ms."""
        candles = [_make_candle(i) for i in range(200)]
        start = time.perf_counter()
        compute_indicators(candles)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"Indicator computation took {elapsed:.3f}s (limit 0.5s)"


# ── PF-007: AI Output Validation ──────────────────────────────

class TestAIValidationPerformance:
    """PF-007: AI output validation must complete < 10ms."""

    def test_ai_validation_throughput(self):
        """PF-007: 1,000 AI validations < 500ms."""
        validator = AIOutputValidator()
        valid_output = (
            '{"action":"BUY","confidence":0.82,"entry_price":1.10000,'
            '"stop_loss":1.09700,"take_profit":1.10500,'
            '"summary":"Strong bullish momentum with EMA alignment across all timeframes.",'
            '"reasoning":"H4 shows clear uptrend with price above EMA200. '
            'RSI at 55 indicates room for upside. MACD histogram positive and expanding. '
            'London session provides optimal liquidity. No high-impact news events nearby.",'
            '"h4_score":0.85,"h1_score":0.80,"m15_score":0.78}'
        )
        start = time.perf_counter()
        for _ in range(1_000):
            validator.validate(valid_output, Decimal("1.10000"))
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"1K AI validations took {elapsed:.3f}s (limit 0.5s)"


# ── PF-008: Confidence Adjustment ─────────────────────────────

class TestConfidencePerformance:
    """PF-008: Confidence adjustment must complete < 5ms."""

    def test_confidence_adjustment_throughput(self):
        """PF-008: 1,000 confidence adjustments < 200ms."""
        adjuster = ConfidenceAdjuster()
        snapshot = _make_snapshot()
        start = time.perf_counter()
        for _ in range(1_000):
            adjuster.adjust(
                raw_confidence=Decimal("0.82"),
                snapshot=snapshot,
                action="BUY",
                consecutive_losses=0,
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"1K adjustments took {elapsed:.3f}s (limit 0.2s)"


# ── PF-009: Fallback Signal Generation ────────────────────────

class TestFallbackPerformance:
    """PF-009: Rule-based fallback must complete < 10ms."""

    def test_fallback_generation_throughput(self):
        """PF-009: 1,000 fallback generations < 500ms."""
        fallback = RuleBasedFallback()
        snapshot = _make_snapshot()
        start = time.perf_counter()
        for _ in range(1_000):
            fallback.generate(snapshot)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"1K fallback generations took {elapsed:.3f}s (limit 0.5s)"


# ── PF-010: Circuit Breaker ───────────────────────────────────

class TestCircuitBreakerPerformance:
    """PF-010: Circuit breaker state checks < 1ms."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_check_throughput(self):
        """PF-010: 10,000 circuit breaker checks < 200ms."""
        cb = CircuitBreaker()
        start = time.perf_counter()
        for _ in range(10_000):
            await cb.check_and_transition()
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"10K CB checks took {elapsed:.3f}s (limit 0.2s)"


# ── PF-011: Time Utils ───────────────────────────────────────

class TestTimeUtilsPerformance:
    """PF-011: Session detection and market open checks < 1ms."""

    def test_session_detection_throughput(self):
        """PF-011: 10,000 session detections < 100ms."""
        now = datetime.now(timezone.utc)
        start = time.perf_counter()
        for _ in range(10_000):
            get_current_session(now)
            is_market_open(now)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"10K session checks took {elapsed:.3f}s (limit 0.1s)"


# ── PF-012: Snapshot Assembly (Memory) ────────────────────────

class TestSnapshotPerformance:
    """PF-012: MarketSnapshot creation must be lightweight."""

    def test_snapshot_creation_throughput(self):
        """PF-012: 100 snapshot creations < 500ms."""
        start = time.perf_counter()
        for _ in range(100):
            _make_snapshot("EUR_USD")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"100 snapshot creations took {elapsed:.3f}s (limit 0.5s)"
