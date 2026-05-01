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


# ─── Codex follow-up review #1: Lock CAS in bootstrap + release ─────────────


@pytest.mark.asyncio
async def test_lock_bootstrap_verifies_winner_after_upsert(env_keys):
    """Cold-start race: two instances see no row, both upsert. After upsert,
    the loser must read back and discover the winner's instance_id, returning
    False instead of declaring success."""
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.select_one = AsyncMock(side_effect=[
        None,  # initial select: no row exists yet
        {"id": "primary", "instance_id": "instance-WINNER"},  # readback after our upsert
    ])
    db.upsert = AsyncMock(return_value=[{"id": "primary"}])
    lock = DistributedLock(db)
    ok = await lock.acquire("instance-LOSER")
    assert ok is False, "Bootstrap loser must detect winner via readback and return False"


@pytest.mark.asyncio
async def test_lock_bootstrap_returns_true_when_we_win(env_keys):
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.select_one = AsyncMock(side_effect=[
        None,                                                        # initial read
        {"id": "primary", "instance_id": "instance-A"},              # 1st readback
        {"id": "primary", "instance_id": "instance-A"},              # 2nd confirmation read
    ])
    db.upsert = AsyncMock(return_value=[{"id": "primary"}])
    lock = DistributedLock(db)
    ok = await lock.acquire("instance-A")
    assert ok is True


@pytest.mark.asyncio
async def test_lock_release_uses_cas_filter(env_keys):
    """release() must filter by both id AND instance_id so a takeover
    between read and release write doesn't get wiped by previous holder.
    Codex follow-up review #1."""
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.select_one = AsyncMock(return_value={"id": "primary", "instance_id": "instance-A"})
    db.update = AsyncMock(return_value=[{"id": "primary"}])  # 1 row updated
    lock = DistributedLock(db)
    await lock.release("instance-A")
    call = db.update.call_args
    args, _ = call
    table, filters, data = args[0], args[1], args[2]
    assert table == "system_state"
    assert filters.get("instance_id") == "instance-A", \
        "release() must include instance_id in filter for CAS"
    assert "id" in filters  # LOCK_ROW_ID is the singleton key (actual value is internal)


@pytest.mark.asyncio
async def test_lock_release_aborts_if_cas_mismatch(env_keys):
    """If between our read and release write someone else took the lock,
    the conditional update returns 0 rows — release must abort cleanly
    without clobbering the new holder."""
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.select_one = AsyncMock(return_value={"id": "primary", "instance_id": "instance-A"})
    db.update = AsyncMock(return_value=[])  # 0 rows updated — race lost
    lock = DistributedLock(db)
    # Should not raise; just log and return
    await lock.release("instance-A")
    # No assertion on side effect — just that it didn't crash and didn't try harder


# ─── Codex follow-up review #2: Atomic settings parse ──────────────────────


@pytest.mark.asyncio
async def test_settings_load_corrupt_riskpct_falls_to_paper(env_keys):
    """A bad numeric field (e.g., riskPct: 'abc') must not leave a stale LIVE
    in memory just because the parse raised. Validate-then-commit pattern."""
    engine, cfg = _make_engine(env_keys, {
        "id": "settings",
        "open_trades": {"riskPct": "abc-not-a-number", "maxPositions": 1,
                        "maxPerPair": 1, "confidence": 70, "mode": "LIVE"},
    })
    cfg.db_mode_override = "LIVE"  # stale LIVE before the bad parse
    await engine._load_user_settings()
    assert cfg.db_mode_override == "PAPER", \
        "Numeric parse failure must still force PAPER (validate-then-commit)"


@pytest.mark.asyncio
async def test_settings_load_corrupt_maxpositions_falls_to_paper(env_keys):
    engine, cfg = _make_engine(env_keys, {
        "id": "settings",
        "open_trades": {"riskPct": 0.5, "maxPositions": "not-an-int",
                        "maxPerPair": 1, "confidence": 70, "mode": "LIVE"},
    })
    cfg.db_mode_override = "LIVE"
    await engine._load_user_settings()
    assert cfg.db_mode_override == "PAPER"


@pytest.mark.asyncio
async def test_settings_load_partial_commit_does_not_happen(env_keys):
    """If parsing fails midway, NO config field should be partially committed."""
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    cfg.max_risk_pct = Decimal("0.02")  # original value
    cfg.db_mode_override = "LIVE"
    db = MagicMock()
    db.select_one = AsyncMock(return_value={
        "id": "settings",
        "open_trades": {"riskPct": 0.001, "maxPositions": "garbage",  # 2nd field bad
                        "maxPerPair": 1, "confidence": 70, "mode": "LIVE"},
    })
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    engine._db = db
    await engine._load_user_settings()
    # max_risk_pct must NOT have been updated to 0.001 / 100 = 0.00001 since
    # the parse aborted on maxPositions
    assert cfg.max_risk_pct == Decimal("0.02"), \
        "Partial commit detected — first field updated even though second failed"
    assert cfg.db_mode_override == "PAPER"


# ─── Codex follow-up review #3: _get_open_pairs scoped to account_id ───────


@pytest.mark.asyncio
async def test_get_open_pairs_filters_by_account_id(env_keys):
    """Correlation sizing uses _get_open_pairs to detect open positions on
    correlated pairs. Without account_id filter, another account's open
    USD_CAD reduces THIS account's allowed size on a correlated pair."""
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    db = MagicMock()
    db.select = AsyncMock(return_value=[])
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    engine._db = db
    await engine._get_open_pairs()
    call = db.select.call_args
    args, _ = call
    filters = args[1]
    assert filters.get("account_id") == cfg.account_uuid


# ─── Codex follow-up review #4: Scanner already-in-position scoped ─────────


def test_scanner_already_in_position_query_includes_account_id(env_keys):
    """Static check: the scanner's already-in-position guard must filter by
    account_id. We grep the source rather than mocking the whole scanner
    pipeline because the query is a one-liner inside execute_scan."""
    scanner_path = ROOT / "lumitrade" / "ai_brain" / "scanner.py"
    src = scanner_path.read_text(encoding="utf-8")
    # Find the already-in-position block
    assert "already_at_max_positions_skip" in src
    # Confirm the query right above it includes account_id
    snippet = src.split("already_at_max_positions_skip")[0]
    last_select = snippet.rfind('self._db.select')
    assert last_select != -1, "scanner.py must call self._db.select before already_at_max_positions_skip"
    # Look forward from that select to find the closing paren
    select_block = snippet[last_select:last_select + 400]
    assert "account_id" in select_block, \
        f"Scanner already-in-position query missing account_id filter:\n{select_block}"


# ─── Codex round-3 review #1: Vacant-row lock CAS via readback ──────────────


@pytest.mark.asyncio
async def test_lock_vacant_row_uses_readback_cas(env_keys):
    """Two standbys racing into a vacant existing row (current_holder=None)
    must not both declare success. The loser's readback discovers the winner."""
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.select_one = AsyncMock(side_effect=[
        # First read: row exists but vacant
        {"id": "singleton", "instance_id": None, "is_primary_instance": False,
         "lock_expires_at": None},
        # Readback after our update: winner already wrote their id
        {"id": "singleton", "instance_id": "instance-WINNER",
         "is_primary_instance": True},
    ])
    db.update = AsyncMock(return_value=[{"id": "singleton"}])
    lock = DistributedLock(db)
    ok = await lock.acquire("instance-LOSER")
    assert ok is False, "Vacant-row loser must detect winner via readback"


@pytest.mark.asyncio
async def test_lock_vacant_row_we_win(env_keys):
    from lumitrade.state.lock import DistributedLock
    db = MagicMock()
    db.select_one = AsyncMock(side_effect=[
        # Initial read: row exists but vacant
        {"id": "singleton", "instance_id": None, "is_primary_instance": False,
         "lock_expires_at": None},
        # 1st readback: we won
        {"id": "singleton", "instance_id": "instance-A",
         "is_primary_instance": True},
        # 2nd confirmation read: still us
        {"id": "singleton", "instance_id": "instance-A",
         "is_primary_instance": True},
    ])
    db.update = AsyncMock(return_value=[{"id": "singleton"}])
    lock = DistributedLock(db)
    ok = await lock.acquire("instance-A")
    assert ok is True


# ─── Codex round-3 review #2: PromptBuilder account-scoped queries ──────────


@pytest.mark.asyncio
async def test_prompt_builder_trade_history_filters_by_account(env_keys):
    from lumitrade.ai_brain.prompt_builder import PromptBuilder
    db = MagicMock()
    db.select = AsyncMock(return_value=[])
    pb = PromptBuilder(db=db, account_id="acct-123")
    await pb._get_trade_history("USD_CAD")
    # All three select calls (buy_recent, sell_recent, all_trades) must include account_id
    for call in db.select.call_args_list:
        args, _ = call
        filters = args[1]
        assert filters.get("account_id") == "acct-123", \
            f"PromptBuilder query missing account_id: {filters}"


@pytest.mark.asyncio
async def test_prompt_builder_performance_insights_filters_by_account(env_keys):
    from lumitrade.ai_brain.prompt_builder import PromptBuilder
    db = MagicMock()
    db.select = AsyncMock(return_value=[])
    pb = PromptBuilder(db=db, account_id="acct-123")
    await pb._get_performance_insights("USD_CAD")
    for call in db.select.call_args_list:
        args, _ = call
        filters = args[1]
        assert filters.get("account_id") == "acct-123"


# ─── Codex round-3 review #3: Reconciler account-scoped ────────────────────


@pytest.mark.asyncio
async def test_reconciler_filters_by_account_uuid(env_keys):
    """Reconciler with account_uuid must only consider this account's open
    trades — without this, other tenants' open positions get classified as
    ghosts and force-closed."""
    from lumitrade.state.reconciler import PositionReconciler
    db = MagicMock()
    db.select = AsyncMock(return_value=[])
    oanda = MagicMock()
    oanda.get_open_trades = AsyncMock(return_value=[])
    alerts = MagicMock()
    alerts.send_critical = AsyncMock()
    reconciler = PositionReconciler(db, oanda, alerts, account_uuid="acct-123")
    await reconciler.reconcile()
    call = db.select.call_args
    args, _ = call
    filters = args[1]
    assert filters.get("account_id") == "acct-123"


@pytest.mark.asyncio
async def test_reconciler_legacy_no_account_unscoped(env_keys):
    """Reconciler called without account_uuid (legacy) must keep working
    (single-account dev/test) — falls back to unscoped query."""
    from lumitrade.state.reconciler import PositionReconciler
    db = MagicMock()
    db.select = AsyncMock(return_value=[])
    oanda = MagicMock()
    oanda.get_open_trades = AsyncMock(return_value=[])
    alerts = MagicMock()
    alerts.send_critical = AsyncMock()
    reconciler = PositionReconciler(db, oanda, alerts)  # no account_uuid
    await reconciler.reconcile()
    call = db.select.call_args
    args, _ = call
    filters = args[1]
    assert "account_id" not in filters  # unscoped, but doesn't crash


# ─── Codex round-3 review #4: Repair endpoints account-scoped ──────────────


def test_repair_endpoints_have_account_id_filters(env_keys):
    """Static check that the three repair endpoint handlers in health_server
    include account_id in their trade queries. They run hard-deletes and
    rewrites, so unscoped queries could destroy other tenants' history."""
    health_path = ROOT / "lumitrade" / "infrastructure" / "health_server.py"
    src = health_path.read_text(encoding="utf-8")
    for handler_name in ["_handle_fix_breakeven", "_handle_purge_ghosts",
                         "_handle_fix_timestamps"]:
        # Find the handler block
        start = src.find(f"async def {handler_name}")
        assert start != -1, f"Handler {handler_name} not found"
        # Look at the next 1500 chars (handler body)
        block = src[start:start + 1500]
        # It must include account_id somewhere in its DB query
        assert "account_id" in block, \
            f"{handler_name} missing account_id filter:\n{block[:400]}"


# ─── Codex round-4 review #1: Lock-first startup gates trading ──────────────


def test_main_startup_acquires_lock_before_state_restore(env_keys):
    """Static check: in main.py startup(), lock acquisition must precede
    state.restore() (which performs DB writes). Codex round-4 finding #1 —
    standby instances were corrupting DB state before knowing they lost."""
    main_path = ROOT / "lumitrade" / "main.py"
    src = main_path.read_text(encoding="utf-8")
    idx_lock = src.find("self.lock.acquire")
    idx_restore = src.find("self.state.restore()")
    assert idx_lock != -1, "Lock acquire call not found"
    assert idx_restore != -1, "state.restore() call not found"
    assert idx_lock < idx_restore, (
        f"Lock acquire (pos {idx_lock}) must come BEFORE state.restore() "
        f"(pos {idx_restore}) — currently restore happens first, which means "
        f"a standby corrupts DB before learning it lost the lock."
    )


def test_main_startup_exits_when_lock_not_acquired(env_keys):
    """Static check: when is_primary is False, startup must exit (raise
    SystemExit) — not just log and continue. Otherwise standbys still start
    trading loops."""
    main_path = ROOT / "lumitrade" / "main.py"
    src = main_path.read_text(encoding="utf-8")
    # The block right after the lock check should raise SystemExit
    lock_section_start = src.find("self.lock.acquire(self.config.instance_id)")
    section = src[lock_section_start:lock_section_start + 1500]
    assert "if not is_primary" in section
    assert "SystemExit" in section, \
        "Standby path must SystemExit, not just log and proceed"


# ─── Codex round-4 review #3: PromptBuilder uses account_uuid not oanda_account_id ──


def test_scanner_passes_account_uuid_to_prompt_builder(env_keys):
    """SignalScanner must wire PromptBuilder with config.account_uuid (the
    DB row identifier), not config.oanda_account_id (the broker identifier).
    Trade rows are written with account_uuid, so PromptBuilder filters
    would miss in production if wired with the wrong identifier."""
    scanner_path = ROOT / "lumitrade" / "ai_brain" / "scanner.py"
    src = scanner_path.read_text(encoding="utf-8")
    # Find the PromptBuilder construction
    idx = src.find("PromptBuilder(")
    assert idx != -1
    construction = src[idx:idx + 200]
    assert "account_uuid" in construction, \
        f"PromptBuilder must be constructed with account_uuid:\n{construction}"
    assert "oanda_account_id" not in construction, \
        f"PromptBuilder must NOT use oanda_account_id:\n{construction}"


def test_main_weekly_intelligence_passes_account_uuid(env_keys):
    """run_weekly_intelligence must use account_uuid, not oanda_account_id."""
    main_path = ROOT / "lumitrade" / "main.py"
    src = main_path.read_text(encoding="utf-8")
    # Find the run_weekly_intelligence call
    idx = src.find("run_weekly_intelligence(")
    assert idx != -1
    call = src[idx:idx + 200]
    assert "account_uuid" in call, \
        f"run_weekly_intelligence must use account_uuid:\n{call}"


# ─── Codex round-4 review #4: _trigger_insight_analysis account-scoped ─────


def test_trigger_insight_analysis_count_filters_by_account(env_keys):
    """Static check that _trigger_insight_analysis counts THIS account's
    closed trades only. Without scoping, another tenant's activity would
    spuriously trigger or suppress this account's insight cadence."""
    exec_path = ROOT / "lumitrade" / "execution_engine" / "engine.py"
    src = exec_path.read_text(encoding="utf-8")
    idx = src.find("async def _trigger_insight_analysis")
    assert idx != -1
    body = src[idx:idx + 800]
    assert "account_id" in body, \
        f"_trigger_insight_analysis must filter by account_id:\n{body[:400]}"
