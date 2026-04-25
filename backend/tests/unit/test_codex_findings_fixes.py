"""
Regression tests for the 5 Codex adversarial-review findings (2026-04-25).

These tests guard against re-introducing safety-critical bugs that an
independent code review caught. Each test maps to a specific finding.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def env_keys(monkeypatch):
    for k, v in {
        "OANDA_API_KEY_DATA": "x", "OANDA_API_KEY_TRADING": "x",
        "OANDA_ACCOUNT_ID": "001-001-1234567-001", "ANTHROPIC_API_KEY": "x",
        "SUPABASE_URL": "https://t.supabase.co", "SUPABASE_SERVICE_KEY": "x",
        "TELNYX_API_KEY": "x", "TELNYX_FROM_NUMBER": "+1", "ALERT_SMS_TO": "+1",
        "SENDGRID_API_KEY": "x", "ALERT_EMAIL_TO": "x@x.com", "INSTANCE_ID": "x",
    }.items():
        monkeypatch.setenv(k, v)
    yield


# ─── Finding #1: Distributed lock CAS verification ──────────────────────────


@pytest.mark.asyncio
async def test_lock_update_returns_false_on_zero_rows(env_keys):
    """`_update_lock` must return False when conditional update matches 0 rows
    (Codex finding #1: previous code returned True unconditionally, allowing
    split-brain primaries after a failover race)."""
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.update = AsyncMock(return_value=[])  # zero rows updated
    lock = DistributedLock(db)
    ok = await lock._update_lock("instance-A", datetime.now(timezone.utc), expected_holder="instance-B")
    assert ok is False, "CAS failure must return False, not silently succeed"


@pytest.mark.asyncio
async def test_lock_update_returns_true_on_one_row(env_keys):
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.update = AsyncMock(return_value=[{"id": "primary"}])  # exactly one row
    lock = DistributedLock(db)
    ok = await lock._update_lock("instance-A", datetime.now(timezone.utc), expected_holder="instance-A")
    assert ok is True


@pytest.mark.asyncio
async def test_lock_update_returns_false_on_multiple_rows(env_keys):
    """Defensive: multiple rows shouldn't be possible on a singleton, but if
    the table got polluted, treat it as a CAS failure rather than silent OK."""
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.update = AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])
    lock = DistributedLock(db)
    ok = await lock._update_lock("x", datetime.now(timezone.utc), expected_holder="x")
    assert ok is False


# ─── Finding #2: Settings load fails closed to PAPER ────────────────────────


def _make_engine(env_keys, db_select_one_behavior):
    """Helper: spin up a RiskEngine with a mocked db.select_one."""
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    db = MagicMock()
    db.select_one = AsyncMock(side_effect=db_select_one_behavior) if callable(db_select_one_behavior) \
        else AsyncMock(return_value=db_select_one_behavior)
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    engine._db = db
    return engine, cfg


@pytest.mark.asyncio
async def test_settings_load_fails_closed_on_db_exception(env_keys):
    """If Supabase raises, db_mode_override MUST reset to PAPER, even if
    a previous read had set it to LIVE. Codex finding #2."""
    def boom(*args, **kwargs):
        raise RuntimeError("supabase unreachable")
    engine, cfg = _make_engine(env_keys, boom)
    cfg.db_mode_override = "LIVE"  # simulate stale LIVE from a previous good read
    await engine._load_user_settings()
    assert cfg.db_mode_override == "PAPER", \
        "DB exception must force db_mode_override to PAPER (fail-closed)"


@pytest.mark.asyncio
async def test_settings_load_fails_closed_on_missing_row(env_keys):
    engine, cfg = _make_engine(env_keys, None)  # row not found
    cfg.db_mode_override = "LIVE"
    await engine._load_user_settings()
    assert cfg.db_mode_override == "PAPER"


@pytest.mark.asyncio
async def test_settings_load_fails_closed_on_malformed_payload(env_keys):
    """Row exists but `open_trades` is not a dict (corrupt or migration glitch)."""
    engine, cfg = _make_engine(env_keys, {"id": "settings", "open_trades": "this is not a dict"})
    cfg.db_mode_override = "LIVE"
    await engine._load_user_settings()
    assert cfg.db_mode_override == "PAPER"


@pytest.mark.asyncio
async def test_settings_load_fails_closed_on_missing_open_trades(env_keys):
    engine, cfg = _make_engine(env_keys, {"id": "settings"})  # no open_trades key
    cfg.db_mode_override = "LIVE"
    await engine._load_user_settings()
    assert cfg.db_mode_override == "PAPER"


@pytest.mark.asyncio
async def test_settings_load_invalid_mode_falls_to_paper(env_keys):
    """An unknown mode value (typo, future enum we don't recognize) must NOT
    keep a stale LIVE — must fall back to PAPER."""
    engine, cfg = _make_engine(env_keys, {
        "id": "settings",
        "open_trades": {"riskPct": 0.5, "maxPositions": 3, "maxPerPair": 1,
                        "confidence": 70, "mode": "MAINNET"},
    })
    cfg.db_mode_override = "LIVE"
    await engine._load_user_settings()
    assert cfg.db_mode_override == "PAPER"


@pytest.mark.asyncio
async def test_settings_load_valid_live_succeeds(env_keys):
    """Sanity check: the fail-closed changes did NOT break the happy path."""
    engine, cfg = _make_engine(env_keys, {
        "id": "settings",
        "open_trades": {"riskPct": 0.25, "maxPositions": 1, "maxPerPair": 1,
                        "confidence": 70, "mode": "LIVE"},
    })
    await engine._load_user_settings()
    assert cfg.db_mode_override == "LIVE"
    assert cfg.max_risk_pct == Decimal("0.0025")
    assert cfg.max_open_trades == 1


# ─── Finding #4: Risk checks scoped to account_id ───────────────────────────


@pytest.mark.asyncio
async def test_position_count_filters_by_account_id(env_keys):
    """`_check_position_count` must include account_id in the filter so one
    account's open trades cannot block another account's signals.
    Codex finding #4."""
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    db = MagicMock()
    db.count = AsyncMock(return_value=0)
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    engine._db = db

    await engine._check_position_count()
    call = db.count.call_args
    assert call is not None, "db.count was never called"
    # call_args is ((table, filters),) with positional args
    args, _ = call
    table, filters = args[0], args[1]
    assert table == "trades"
    assert "account_id" in filters, \
        f"account_id missing from position-count filter: {filters}"
    assert filters["account_id"] == cfg.account_uuid


@pytest.mark.asyncio
async def test_position_count_per_pair_filters_by_account_id(env_keys):
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    db = MagicMock()
    db.count = AsyncMock(return_value=0)
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    engine._db = db

    await engine._check_position_count_per_pair("USD_CAD")
    call = db.count.call_args
    args, _ = call
    filters = args[1]
    assert filters.get("account_id") == cfg.account_uuid
    assert filters.get("pair") == "USD_CAD"


@pytest.mark.asyncio
async def test_cooldown_check_filters_by_account_id(env_keys):
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    db = MagicMock()
    db.select = AsyncMock(return_value=[])
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    engine._db = db

    await engine._check_cooldown("USD_CAD")
    call = db.select.call_args
    args, _ = call
    filters = args[1]
    assert filters.get("account_id") == cfg.account_uuid
    assert filters.get("pair") == "USD_CAD"


# ─── Finding #3: PAPER- broker IDs excluded from OANDA mutation path ────────


@pytest.mark.asyncio
async def test_trail_stop_losses_excludes_paper_trades(env_keys):
    """`_trail_stop_losses` must filter out PAPER- broker IDs so simulated
    fills don't trigger real OANDA modify_trade calls. Codex finding #3."""
    from lumitrade.config import LumitradeConfig
    from lumitrade.execution_engine.engine import ExecutionEngine
    cfg = LumitradeConfig()
    eng = ExecutionEngine.__new__(ExecutionEngine)
    eng.config = cfg
    eng._db = MagicMock()
    eng._db.select = AsyncMock(return_value=[
        {"id": "1", "broker_trade_id": "PAPER-abc123", "pair": "USD_CAD"},
        {"id": "2", "broker_trade_id": "PAPER-def456", "pair": "USD_JPY"},
    ])
    eng._oanda_read = MagicMock()
    eng._oanda_read.get_pricing = AsyncMock(return_value={"prices": []})
    # If paper trades leaked through, _check_and_trail would be called and
    # then _oanda_trade.modify_trade. Mock both to detect the leak.
    eng._oanda_trade = MagicMock()
    eng._oanda_trade.modify_trade = AsyncMock()
    eng._check_and_trail = AsyncMock()

    await eng._trail_stop_losses()

    # Either: no trailable trades (early return), OR _check_and_trail never called
    eng._check_and_trail.assert_not_called()
    eng._oanda_trade.modify_trade.assert_not_called()


@pytest.mark.asyncio
async def test_trail_stop_losses_includes_real_oanda_trades(env_keys):
    """Sanity check: real OANDA broker IDs (no PAPER- prefix) still flow through."""
    from lumitrade.config import LumitradeConfig
    from lumitrade.execution_engine.engine import ExecutionEngine
    cfg = LumitradeConfig()
    eng = ExecutionEngine.__new__(ExecutionEngine)
    eng.config = cfg
    eng._db = MagicMock()
    eng._db.select = AsyncMock(return_value=[
        {"id": "1", "broker_trade_id": "12345", "pair": "USD_CAD"},  # real OANDA ID
    ])
    eng._oanda_read = MagicMock()
    eng._oanda_read.get_pricing = AsyncMock(return_value={
        "prices": [{"instrument": "USD_CAD",
                    "bids": [{"price": "1.39000"}],
                    "asks": [{"price": "1.39010"}]}]
    })
    eng._oanda_trade = MagicMock()
    eng._oanda_trade.modify_trade = AsyncMock()
    eng._check_and_trail = AsyncMock()

    await eng._trail_stop_losses()

    eng._check_and_trail.assert_called_once()


# ─── Finding #5: Walk-forward aggregate doesn't drop losing folds ───────────


def test_wfa_aggregate_includes_losing_folds(env_keys):
    """Regression test for Codex finding #5: walk-forward aggregate report
    used to filter out folds with PF <= 0, hiding strategy decay. New version
    must report the count of negative folds prominently and use median PF
    capped against the 999 'no losses' sentinel."""
    from scripts.backtest_v2 import (
        BacktestConfig, BacktestResult, WalkForwardFold, write_report,
    )
    from datetime import datetime, timezone
    import tempfile

    cfg = BacktestConfig()
    folds = [
        WalkForwardFold(0, datetime(2024,1,1,tzinfo=timezone.utc), datetime(2024,4,1,tzinfo=timezone.utc),
                        datetime(2024,4,1,tzinfo=timezone.utc), datetime(2024,7,1,tzinfo=timezone.utc),
                        10, 5, 2.0, 6.21, Decimal("0"), Decimal("236")),
        WalkForwardFold(1, datetime(2024,4,1,tzinfo=timezone.utc), datetime(2024,7,1,tzinfo=timezone.utc),
                        datetime(2024,7,1,tzinfo=timezone.utc), datetime(2024,10,1,tzinfo=timezone.utc),
                        10, 3, 2.0, 999.0, Decimal("0"), Decimal("839")),  # no losses sentinel
        WalkForwardFold(5, datetime(2025,10,1,tzinfo=timezone.utc), datetime(2026,1,1,tzinfo=timezone.utc),
                        datetime(2026,1,1,tzinfo=timezone.utc), datetime(2026,4,1,tzinfo=timezone.utc),
                        10, 5, 2.0, 0.0, Decimal("0"), Decimal("-921")),  # losing fold
    ]
    pair = "USD_CAD"
    fake_result = BacktestResult(
        pair=pair, label="baseline", trades=[],
        starting_balance=cfg.starting_balance, ending_balance=cfg.starting_balance,
        total_pnl=Decimal("0"), win_count=0, loss_count=0, breakeven_count=0,
        win_rate=0.0, profit_factor=0.0, expectancy_usd=Decimal("0"),
        expectancy_r=0.0, avg_win=Decimal("0"), avg_loss=Decimal("0"),
        win_loss_ratio=0.0, max_drawdown_usd=Decimal("0"), max_drawdown_pct=0.0,
        recovery_factor=0.0, sharpe_annualized=0.0, sortino_annualized=0.0,
        calmar=0.0, mar=0.0, wilson_ci_low=0.0, wilson_ci_high=0.0,
        expectancy_ci_low=0.0, expectancy_ci_high=0.0,
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        report_path = Path(f.name)

    write_report(report_path, {pair: fake_result}, {pair: folds}, {}, {}, cfg)
    body = report_path.read_text(encoding="utf-8")

    # Must include count of negative/zero folds (drag detector)
    assert "folds at PF≤1.0: **1**" in body, \
        f"Expected 'folds at PF≤1.0: **1**' in report — got:\n{body}"
    # Must NOT report a misleading mean that excludes the losing fold
    # (3.105 was the old positive-only mean which dropped the 0.0 fold)
    assert "median PF" in body
    assert "total OOS P&L" in body
    # Capped sentinel: 999 -> 99 in mean calc, but median = 6.21 (middle of [0, 6.21, 99])
    # We don't assert specific numbers (depends on capping semantics), just that the structure is right.
    report_path.unlink()
