"""
BTC Risk Gate Tests
====================
Verifies the three BTC-specific production guards added 2026-04-29:
  1. Spread gate tightened from 500 → 50 pips
  2. Minimum R:R raised to 3.0 (vs 1.5 for forex)
  3. SL width capped at 2% of entry price

All tests use a real BTC price (~$85,000) and pip size = $1.00.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from lumitrade.core.enums import (
    Action,
    GenerationMethod,
    RiskState,
    Session,
    TradeDuration,
)
from lumitrade.core.models import ApprovedOrder, RiskRejection, SignalProposal


def _make_btc_config():
    cfg = MagicMock()
    cfg.max_open_trades = 10
    cfg.max_positions_per_pair = 10
    cfg.max_position_units = 500_000
    cfg.trade_cooldown_minutes = 0
    cfg.min_confidence = Decimal("0.65")
    cfg.max_confidence = Decimal("0.90")
    cfg.max_spread_pips = Decimal("5.0")
    cfg.min_rr_ratio = Decimal("1.5")
    cfg.btc_min_rr_ratio = Decimal("3.0")
    cfg.btc_max_sl_pct = Decimal("0.02")
    cfg.min_sl_pips = Decimal("15.0")
    cfg.min_tp_pips = Decimal("15.0")
    cfg.daily_loss_limit_pct = Decimal("0.05")
    cfg.weekly_loss_limit_pct = Decimal("0.10")
    cfg.no_trade_hours_utc = []
    cfg.blocked_weekdays_utc = []
    cfg.news_blackout_before_min = 30
    cfg.news_blackout_after_min = 15
    cfg.trading_mode = "PAPER"
    cfg.force_paper_mode = False
    cfg.effective_trading_mode = MagicMock(return_value="PAPER")
    cfg.oanda_account_id = "test-account"
    cfg.account_uuid = "00000000-0000-0000-0000-000000000001"
    cfg.min_position_units_forex = 1
    cfg.min_meaningful_risk_usd = Decimal("0.01")
    cfg.pairs = ["USD_CAD", "BTC_USD"]
    cfg.live_pairs = ["USD_CAD"]
    return cfg


def _make_btc_proposal(
    entry=Decimal("85000"),
    sl=Decimal("84150"),    # 850 pip distance = 1.0% of price
    tp=Decimal("87550"),    # 2550 pip distance = 3.0 R:R
    spread=Decimal("25"),   # $25 = 25 pips (below 50 gate)
    action=Action.BUY,
    confidence=Decimal("0.75"),
) -> SignalProposal:
    return SignalProposal(
        signal_id=uuid4(),
        pair="BTC_USD",
        action=action,
        confidence_raw=confidence,
        confidence_adjusted=confidence,
        confidence_adjustment_log={},
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        summary="BTC test signal",
        reasoning="BTC test reasoning " * 5,
        timeframe_scores={"h4": 0.75, "h1": 0.70, "m15": 0.65},
        indicators_snapshot={},
        key_levels=[],
        invalidation_level=sl,
        expected_duration=TradeDuration.INTRADAY,
        generation_method=GenerationMethod.AI,
        session=Session.LONDON,
        spread_pips=spread,
        news_context=[],
        ai_prompt_hash="btctest",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.insert = AsyncMock(return_value={})
    db.count = AsyncMock(return_value=0)
    db.select = AsyncMock(return_value=[])
    db.select_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_state():
    sm = MagicMock()
    sm.risk_state = RiskState.NORMAL
    return sm


@pytest.fixture
def engine(mock_state, mock_db):
    from lumitrade.risk_engine.engine import RiskEngine
    return RiskEngine(
        config=_make_btc_config(),
        state_manager=mock_state,
        db=mock_db,
    )


class TestBTCSpreadGate:
    """BTC spread gate: tightened from 500 → 50 pips (2026-04-29)."""

    @pytest.mark.asyncio
    async def test_btc_wide_spread_rejected(self, engine):
        """Spread > 50 pips must be rejected for BTC."""
        proposal = _make_btc_proposal(spread=Decimal("60"))
        result = await engine.evaluate(proposal, Decimal("100000"))
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "SPREAD"

    @pytest.mark.asyncio
    async def test_btc_tight_spread_passes(self, engine):
        """Spread <= 50 pips must pass the spread gate for BTC."""
        proposal = _make_btc_proposal(spread=Decimal("25"))
        result = await engine.evaluate(proposal, Decimal("100000"))
        assert isinstance(result, ApprovedOrder)

    @pytest.mark.asyncio
    async def test_btc_spread_exactly_at_limit_passes(self, engine):
        """Spread exactly at 50 pips must pass (boundary inclusive)."""
        proposal = _make_btc_proposal(spread=Decimal("50"))
        result = await engine.evaluate(proposal, Decimal("100000"))
        assert isinstance(result, ApprovedOrder)


class TestBTCRRGate:
    """BTC minimum R:R gate: 3.0 required (vs 1.5 for forex)."""

    @pytest.mark.asyncio
    async def test_btc_low_rr_rejected(self, engine):
        """R:R < 3.0 must be rejected for BTC (even if >= 1.5 forex minimum)."""
        # entry=85000, sl=84150 (850 dist), tp=86275 (1275 dist) → RR=1.5
        proposal = _make_btc_proposal(
            entry=Decimal("85000"),
            sl=Decimal("84150"),
            tp=Decimal("86275"),
            spread=Decimal("25"),
        )
        result = await engine.evaluate(proposal, Decimal("100000"))
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "RR_RATIO"

    @pytest.mark.asyncio
    async def test_btc_sufficient_rr_passes(self, engine):
        """R:R >= 3.0 must pass the RR gate for BTC."""
        # entry=85000, sl=84150 (850 dist), tp=87550 (2550 dist) → RR=3.0
        proposal = _make_btc_proposal(
            entry=Decimal("85000"),
            sl=Decimal("84150"),
            tp=Decimal("87550"),
            spread=Decimal("25"),
        )
        result = await engine.evaluate(proposal, Decimal("100000"))
        assert isinstance(result, ApprovedOrder)


class TestBTCSLWidthGate:
    """BTC SL width gate: SL must not exceed 2% of entry price."""

    @pytest.mark.asyncio
    async def test_btc_wide_sl_rejected(self, engine):
        """SL > 2% of price must be rejected for BTC."""
        # entry=85000, sl=82000 → 3000/85000 = 3.5% > 2%
        # tp must give >=3 RR on this SL: 3000 * 3 = 9000 → tp=94000
        proposal = _make_btc_proposal(
            entry=Decimal("85000"),
            sl=Decimal("82000"),
            tp=Decimal("94000"),
            spread=Decimal("25"),
        )
        result = await engine.evaluate(proposal, Decimal("100000"))
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "BTC_SL_PCT"

    @pytest.mark.asyncio
    async def test_btc_tight_sl_passes(self, engine):
        """SL <= 2% of price must pass the SL width gate for BTC."""
        # entry=85000, sl=84150 → 850/85000 = 1.0% ≤ 2%
        proposal = _make_btc_proposal(
            entry=Decimal("85000"),
            sl=Decimal("84150"),
            tp=Decimal("87550"),  # RR = 3.0
            spread=Decimal("25"),
        )
        result = await engine.evaluate(proposal, Decimal("100000"))
        assert isinstance(result, ApprovedOrder)
