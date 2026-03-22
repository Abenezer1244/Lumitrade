"""
Risk Engine Tests — RE-001 to RE-025
========================================
100% coverage required on risk_engine/engine.py.
Per QTS Table 5. All 25 test cases.
"""

from datetime import datetime, timedelta, timezone
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


def _make_config():
    """Create a mock config with default trading parameters."""
    config = MagicMock()
    config.max_open_trades = 3
    config.trade_cooldown_minutes = 60
    config.min_confidence = Decimal("0.65")
    config.max_spread_pips = Decimal("3.0")
    config.min_rr_ratio = Decimal("1.5")
    config.trading_mode = "PAPER"
    config.oanda_account_id = "test-account"
    return config


def _make_state(
    risk_state=RiskState.NORMAL,
    open_trades=None,
    last_signal_time=None,
    confidence_override=None,
    consecutive_losses=0,
):
    """Create a mock system state."""
    state = MagicMock()
    state.risk_state = risk_state
    state.open_trades = open_trades or []
    state.last_signal_time = last_signal_time or {}
    state.confidence_threshold_override = confidence_override
    state.consecutive_losses = consecutive_losses
    return state


def _make_proposal(
    action=Action.BUY,
    confidence=Decimal("0.80"),
    entry=Decimal("1.08430"),
    sl=Decimal("1.08230"),
    tp=Decimal("1.08730"),
    spread=Decimal("1.2"),
    pair="EUR_USD",
) -> SignalProposal:
    """Create a valid SignalProposal for testing."""
    return SignalProposal(
        signal_id=uuid4(),
        pair=pair,
        action=action,
        confidence_raw=Decimal("0.82"),
        confidence_adjusted=confidence,
        confidence_adjustment_log={},
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        summary="Test signal summary for testing purposes.",
        reasoning="Test reasoning " * 10,
        timeframe_scores={"h4": 0.8, "h1": 0.75, "m15": 0.7},
        indicators_snapshot={},
        key_levels=[],
        invalidation_level=sl,
        expected_duration=TradeDuration.INTRADAY,
        generation_method=GenerationMethod.AI,
        session=Session.OVERLAP,
        spread_pips=spread,
        news_context=[],
        ai_prompt_hash="abc123",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_state_manager():
    sm = MagicMock()
    sm.risk_state = RiskState.NORMAL
    sm.get = AsyncMock(return_value=_make_state())
    return sm


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.insert = AsyncMock(return_value={})
    db.count = AsyncMock(return_value=0)  # No open positions by default
    db.select = AsyncMock(return_value=[])  # No recent trades by default
    return db


@pytest.fixture
def engine(mock_state_manager, mock_db):
    from lumitrade.risk_engine.engine import RiskEngine
    config = _make_config()
    eng = RiskEngine(config, mock_state_manager, mock_db)
    eng._calendar_guard = MagicMock()
    eng._calendar_guard.is_blackout = AsyncMock(return_value=False)
    return eng


class TestApproval:
    """RE-001, RE-006, RE-008, RE-010, RE-012, RE-014: Valid signals approved."""

    @pytest.mark.asyncio
    async def test_approves_valid_signal_normal_state(self, engine):
        """RE-001"""
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, ApprovedOrder)

    @pytest.mark.asyncio
    async def test_approves_when_state_cautious(self, engine, mock_state_manager):
        """RE-006"""
        mock_state_manager.risk_state = RiskState.CAUTIOUS
        # Confidence 0.80 is above CAUTIOUS threshold (0.75)
        result = await engine.evaluate(
            _make_proposal(confidence=Decimal("0.80")), Decimal("300")
        )
        assert isinstance(result, ApprovedOrder)

    @pytest.mark.asyncio
    async def test_approves_when_2_of_3_positions_open(self, engine, mock_db):
        """RE-008"""
        mock_db.count.return_value = 2
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, ApprovedOrder)

    @pytest.mark.asyncio
    async def test_approves_pair_outside_cooldown_window(self, engine, mock_db):
        """RE-010"""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=61)
        mock_db.select.return_value = [{"closed_at": old_time.isoformat()}]
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, ApprovedOrder)

    @pytest.mark.asyncio
    async def test_accepts_confidence_at_threshold_boundary(self, engine):
        """RE-012"""
        result = await engine.evaluate(
            _make_proposal(confidence=Decimal("0.65")), Decimal("5000")
        )
        assert isinstance(result, ApprovedOrder)

    @pytest.mark.asyncio
    async def test_approves_spread_at_max_boundary(self, engine):
        """RE-014"""
        result = await engine.evaluate(
            _make_proposal(spread=Decimal("3.0")), Decimal("300")
        )
        assert isinstance(result, ApprovedOrder)


class TestRejections:
    """RE-002 to RE-005, RE-007, RE-009, RE-011, RE-013, RE-015-017."""

    @pytest.mark.asyncio
    async def test_rejects_when_risk_state_daily_limit(
        self, engine, mock_state_manager,
    ):
        """RE-002"""
        mock_state_manager.risk_state = RiskState.DAILY_LIMIT
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "RISK_STATE"

    @pytest.mark.asyncio
    async def test_rejects_when_risk_state_weekly_limit(
        self, engine, mock_state_manager,
    ):
        """RE-003"""
        mock_state_manager.risk_state = RiskState.WEEKLY_LIMIT
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, RiskRejection)

    @pytest.mark.asyncio
    async def test_rejects_when_risk_state_emergency_halt(
        self, engine, mock_state_manager,
    ):
        """RE-004"""
        mock_state_manager.risk_state = RiskState.EMERGENCY_HALT
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, RiskRejection)

    @pytest.mark.asyncio
    async def test_rejects_when_circuit_breaker_open(self, engine, mock_state_manager):
        """RE-005"""
        mock_state_manager.risk_state = RiskState.CIRCUIT_OPEN
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, RiskRejection)

    @pytest.mark.asyncio
    async def test_rejects_when_max_3_positions_open(self, engine, mock_db):
        """RE-007"""
        mock_db.count.return_value = 3
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "POSITION_COUNT"

    @pytest.mark.asyncio
    async def test_rejects_pair_within_cooldown_window(self, engine, mock_db):
        """RE-009"""
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        mock_db.select.return_value = [{"closed_at": recent_time.isoformat()}]
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "COOLDOWN"

    @pytest.mark.asyncio
    async def test_rejects_confidence_below_threshold(self, engine):
        """RE-011"""
        result = await engine.evaluate(
            _make_proposal(confidence=Decimal("0.64")), Decimal("300")
        )
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "CONFIDENCE"

    @pytest.mark.asyncio
    async def test_rejects_spread_above_max(self, engine):
        """RE-013"""
        result = await engine.evaluate(
            _make_proposal(spread=Decimal("3.1")), Decimal("300")
        )
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "SPREAD"

    @pytest.mark.asyncio
    async def test_rejects_during_news_blackout(self, engine):
        """RE-015"""
        engine._calendar_guard.is_blackout = AsyncMock(return_value=True)
        result = await engine.evaluate(_make_proposal(), Decimal("300"))
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "NEWS_BLACKOUT"

    @pytest.mark.asyncio
    async def test_rejects_rr_below_minimum(self, engine):
        """RE-016: RR ratio below 1.5"""
        # Entry 1.0843, SL 1.0800 (43 pips), TP 1.0870 (27 pips) = 0.63 RR
        result = await engine.evaluate(
            _make_proposal(
                entry=Decimal("1.08430"),
                sl=Decimal("1.08000"),
                tp=Decimal("1.08700"),
            ),
            Decimal("300"),
        )
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "RR_RATIO"

    @pytest.mark.asyncio
    async def test_rejects_hold_action(self, engine):
        """RE-017"""
        result = await engine.evaluate(
            _make_proposal(action=Action.HOLD), Decimal("300")
        )
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "ACTION"


class TestPositionSizing:
    """RE-018 to RE-021: Risk percentage and position sizing."""

    @pytest.mark.asyncio
    async def test_position_size_0_5pct_for_low_confidence(self, engine):
        """RE-018"""
        result = await engine.evaluate(
            _make_proposal(confidence=Decimal("0.70")), Decimal("1000")
        )
        assert isinstance(result, ApprovedOrder)
        assert result.risk_pct == Decimal("0.005")

    @pytest.mark.asyncio
    async def test_position_size_1pct_for_mid_confidence(self, engine):
        """RE-019"""
        result = await engine.evaluate(
            _make_proposal(confidence=Decimal("0.82")), Decimal("1000")
        )
        assert isinstance(result, ApprovedOrder)
        assert result.risk_pct == Decimal("0.01")

    @pytest.mark.asyncio
    async def test_position_size_2pct_for_high_confidence(self, engine):
        """RE-020"""
        result = await engine.evaluate(
            _make_proposal(confidence=Decimal("0.92")), Decimal("1000")
        )
        assert isinstance(result, ApprovedOrder)
        assert result.risk_pct == Decimal("0.02")

    @pytest.mark.asyncio
    async def test_rejects_when_calculated_units_below_1000(self, engine):
        """RE-021: Small balance + large SL = units < 1000."""
        result = await engine.evaluate(
            _make_proposal(
                confidence=Decimal("0.65"),
                entry=Decimal("1.08430"),
                sl=Decimal("1.07430"),  # 100 pips SL
                tp=Decimal("1.09930"),  # 150 pips TP (1.5 RR)
            ),
            Decimal("10"),  # Very small balance
        )
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "MINIMUM_POSITION_SIZE"


class TestOrderDetails:
    """RE-022 to RE-025: ApprovedOrder field verification."""

    @pytest.mark.asyncio
    async def test_approved_order_has_30s_expiry(self, engine):
        """RE-022"""
        result = await engine.evaluate(_make_proposal(), Decimal("1000"))
        assert isinstance(result, ApprovedOrder)
        delta = (result.expiry - result.approved_at).total_seconds()
        assert 29 <= delta <= 31

    @pytest.mark.asyncio
    async def test_rejection_logged_to_db(self, engine, mock_state_manager, mock_db):
        """RE-023"""
        mock_state_manager.risk_state = RiskState.DAILY_LIMIT
        await engine.evaluate(_make_proposal(), Decimal("300"))
        mock_db.insert.assert_called()
        # Find the risk_events insert call
        found = any(
            call[0][0] == "risk_events"
            for call in mock_db.insert.call_args_list
        )
        assert found

    @pytest.mark.asyncio
    async def test_rejection_contains_correct_rule_name(self, engine):
        """RE-024"""
        result = await engine.evaluate(
            _make_proposal(spread=Decimal("3.5")), Decimal("300")
        )
        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "SPREAD"

    @pytest.mark.asyncio
    async def test_all_rejections_include_signal_id(self, engine, mock_state_manager):
        """RE-025"""
        mock_state_manager.risk_state = RiskState.DAILY_LIMIT
        proposal = _make_proposal()
        result = await engine.evaluate(proposal, Decimal("300"))
        assert isinstance(result, RiskRejection)
        assert result.signal_id == proposal.signal_id
