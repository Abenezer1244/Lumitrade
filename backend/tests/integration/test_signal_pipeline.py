"""
Lumitrade Integration Tests — Signal Pipeline
================================================
SP-001 to SP-010: End-to-end signal-to-execution pipeline tests.
All external calls mocked (OANDA, Anthropic, Supabase).

Tests instantiate real RiskEngine with mocked dependencies
and verify the full evaluate() decision path.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from lumitrade.config import LumitradeConfig
from lumitrade.core.enums import (
    Action,
    Direction,
    GenerationMethod,
    NewsImpact,
    RiskState,
    Session,
    TradeDuration,
    TradingMode,
)
from lumitrade.core.models import (
    ApprovedOrder,
    NewsEvent,
    RiskRejection,
    SignalProposal,
)
from lumitrade.risk_engine.engine import RiskEngine


# ── Fixtures ──────────────────────────────────────────────────────


def _make_config(**overrides) -> LumitradeConfig:
    """Create a LumitradeConfig with test defaults."""
    defaults = {
        "OANDA_API_KEY_DATA": "test_key_data",
        "OANDA_API_KEY_TRADING": "test_key_trading",
        "OANDA_ACCOUNT_ID": "test_account",
        "OANDA_ENVIRONMENT": "practice",
        "ANTHROPIC_API_KEY": "test_key",
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test_service_key",
        "TELNYX_API_KEY": "test_telnyx_key",
        "TELNYX_FROM_NUMBER": "+10000000000",
        "ALERT_SMS_TO": "+10000000001",
        "SENDGRID_API_KEY": "test_sg_key",
        "ALERT_EMAIL_TO": "test@test.com",
        "INSTANCE_ID": "ci-test",
        "TRADING_MODE": "PAPER",
    }
    defaults.update(overrides)
    return LumitradeConfig(**defaults)


def _make_proposal(
    action: Action = Action.BUY,
    pair: str = "EUR_USD",
    confidence: Decimal = Decimal("0.82"),
    entry: Decimal = Decimal("1.08500"),
    stop_loss: Decimal = Decimal("1.08300"),
    take_profit: Decimal = Decimal("1.08900"),
    spread_pips: Decimal = Decimal("1.2"),
    news_context: list | None = None,
    recommended_risk_pct: Decimal | None = None,
) -> SignalProposal:
    """Create a realistic SignalProposal for testing."""
    now = datetime.now(timezone.utc)
    return SignalProposal(
        signal_id=uuid4(),
        pair=pair,
        action=action,
        confidence_raw=confidence,
        confidence_adjusted=confidence,
        confidence_adjustment_log={"base": str(confidence)},
        entry_price=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        summary="Test BUY signal on EUR/USD",
        reasoning="Strong bullish momentum on H1 timeframe",
        timeframe_scores={"M15": 0.7, "H1": 0.85, "H4": 0.6},
        indicators_snapshot={"rsi_14": "55.2", "ema_20": "1.08450"},
        key_levels=[Decimal("1.08000"), Decimal("1.09000")],
        invalidation_level=Decimal("1.08200"),
        expected_duration=TradeDuration.INTRADAY,
        generation_method=GenerationMethod.AI,
        session=Session.LONDON,
        spread_pips=spread_pips,
        news_context=news_context or [],
        ai_prompt_hash="abc123def456",
        created_at=now,
        recommended_risk_pct=recommended_risk_pct,
    )


def _make_state_manager(
    risk_state: RiskState = RiskState.NORMAL,
    open_trade_count: int = 0,
) -> MagicMock:
    """Create a mock StateManager with controlled properties."""
    sm = MagicMock()
    sm.risk_state = risk_state
    sm.open_trade_count = open_trade_count
    return sm


def _make_db(
    open_positions_count: int = 0,
    recent_trades: list | None = None,
) -> AsyncMock:
    """Create a mock DatabaseClient with controlled responses."""
    db = AsyncMock()

    async def mock_count(table, filters):
        if table == "open_positions":
            return open_positions_count
        return 0

    async def mock_select(table, filters, columns="*", order=None, limit=None):
        if table == "trades":
            return recent_trades or []
        return []

    async def mock_insert(table, data):
        return data

    db.count = AsyncMock(side_effect=mock_count)
    db.select = AsyncMock(side_effect=mock_select)
    db.insert = AsyncMock(side_effect=mock_insert)
    return db


# ── Test Class ────────────────────────────────────────────────────


@pytest.mark.integration
class TestSignalPipeline:
    """SP-001 to SP-010: Signal-to-execution pipeline integration tests."""

    @pytest.fixture
    def config(self):
        return _make_config()

    # ── SP-001: Valid BUY signal approved ─────────────────────────

    async def test_sp001_valid_buy_signal_produces_approved_order(self, config):
        """SP-001: Valid BUY signal flows through risk engine and produces ApprovedOrder."""
        db = _make_db(open_positions_count=0, recent_trades=[])
        state_manager = _make_state_manager(risk_state=RiskState.NORMAL)
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        proposal = _make_proposal(
            action=Action.BUY,
            confidence=Decimal("0.82"),
            entry=Decimal("1.08500"),
            stop_loss=Decimal("1.08300"),
            take_profit=Decimal("1.08900"),
            spread_pips=Decimal("1.2"),
        )

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, ApprovedOrder), (
            f"Expected ApprovedOrder, got {type(result).__name__}: "
            f"{getattr(result, 'rule_violated', 'N/A')}"
        )
        assert result.pair == "EUR_USD"
        assert result.direction == Direction.BUY
        assert result.units >= 1000
        assert result.mode == TradingMode.PAPER
        assert result.signal_id == proposal.signal_id

    # ── SP-002: HOLD signal rejected by action check ─────────────

    async def test_sp002_hold_signal_rejected_by_action_check(self, config):
        """SP-002: HOLD signal is rejected by risk engine action check."""
        db = _make_db()
        state_manager = _make_state_manager()
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        proposal = _make_proposal(action=Action.HOLD)

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "ACTION"

    # ── SP-003: Low confidence rejected ──────────────────────────

    async def test_sp003_low_confidence_rejected(self, config):
        """SP-003: Low confidence (0.50) signal rejected by risk engine."""
        db = _make_db()
        state_manager = _make_state_manager()
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        proposal = _make_proposal(confidence=Decimal("0.50"))

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "CONFIDENCE"
        assert result.current_value == "0.50"

    # ── SP-004: News blackout blocks execution ───────────────────

    async def test_sp004_news_blackout_blocks_execution(self, config):
        """SP-004: News blackout active blocks execution."""
        db = _make_db()
        state_manager = _make_state_manager()
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        # HIGH impact news event 10 minutes from now (within blackout window)
        news_event = NewsEvent(
            event_id="NFP-2026-03",
            title="Non-Farm Payrolls",
            currencies_affected=["USD"],
            impact=NewsImpact.HIGH,
            scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            minutes_until=10,
        )

        proposal = _make_proposal(
            confidence=Decimal("0.85"),
            news_context=[news_event],
        )

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "NEWS_BLACKOUT"

    # ── SP-005: Max positions blocks new trade ───────────────────

    async def test_sp005_max_positions_blocks_new_trade(self, config):
        """SP-005: Max positions (3 open) blocks new trade."""
        db = _make_db(open_positions_count=3)
        state_manager = _make_state_manager()
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        proposal = _make_proposal(confidence=Decimal("0.85"))

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "POSITION_COUNT"

    # ── SP-006: Invalid AI JSON caught by validator ──────────────

    async def test_sp006_invalid_rr_ratio_rejected(self, config):
        """SP-006: Signal with invalid R:R ratio (below 1.5:1) rejected."""
        db = _make_db()
        state_manager = _make_state_manager()
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        # Entry 1.08500, SL 1.08300 (20 pips risk), TP 1.08700 (20 pips reward)
        # R:R = 1.0:1 which is below minimum 1.5:1
        proposal = _make_proposal(
            confidence=Decimal("0.82"),
            entry=Decimal("1.08500"),
            stop_loss=Decimal("1.08300"),
            take_profit=Decimal("1.08700"),
        )

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "RR_RATIO"

    # ── SP-007: Circuit breaker OPEN blocks execution ────────────

    async def test_sp007_circuit_breaker_open_blocks_execution(self, config):
        """SP-007: CIRCUIT_OPEN risk state blocks execution."""
        db = _make_db()
        state_manager = _make_state_manager(risk_state=RiskState.CIRCUIT_OPEN)
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        proposal = _make_proposal(confidence=Decimal("0.90"))

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "RISK_STATE"
        assert result.risk_state == RiskState.CIRCUIT_OPEN

    # ── SP-008: DAILY_LIMIT risk state halts trading ─────────────

    async def test_sp008_daily_limit_halts_trading(self, config):
        """SP-008: DAILY_LIMIT risk state halts all trading."""
        db = _make_db()
        state_manager = _make_state_manager(risk_state=RiskState.DAILY_LIMIT)
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        proposal = _make_proposal(confidence=Decimal("0.90"))

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "RISK_STATE"
        assert result.risk_state == RiskState.DAILY_LIMIT

    # ── SP-009: Spread too wide rejects signal ───────────────────

    async def test_sp009_spread_too_wide_rejects_signal(self, config):
        """SP-009: Spread too wide (>3 pips) rejects signal."""
        db = _make_db()
        state_manager = _make_state_manager()
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        proposal = _make_proposal(
            confidence=Decimal("0.85"),
            spread_pips=Decimal("3.5"),
        )

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "SPREAD"

    # ── SP-010: Cooldown blocks repeat signal on same pair ───────

    async def test_sp010_cooldown_blocks_repeat_signal(self, config):
        """SP-010: Cooldown period blocks repeat signal on same pair."""
        # Simulate a trade closed 30 minutes ago (cooldown is 60 min)
        closed_at = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).isoformat()

        db = _make_db(
            recent_trades=[{"pair": "EUR_USD", "closed_at": closed_at}],
        )
        state_manager = _make_state_manager()
        engine = RiskEngine(config=config, state_manager=state_manager, db=db)

        proposal = _make_proposal(
            pair="EUR_USD",
            confidence=Decimal("0.85"),
        )

        result = await engine.evaluate(proposal, account_balance=Decimal("1000"))

        assert isinstance(result, RiskRejection)
        assert result.rule_violated == "COOLDOWN"
