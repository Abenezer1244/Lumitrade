"""
Tests for the StateManager pieces of the kill-switch wiring.

Per Codex round-2 review of audit finding [high] #4:
- The HTTP /kill-switch endpoint writes to system_state in DB.
- The engine main loop reads in-memory state, not DB.
- Without StateManager.refresh_kill_switch_from_db() and persistence in
  restore()/save(), the HTTP-to-engine bridge is broken: HTTP writes never
  reach the running engine, and a restart-with-flag-set never re-fires.

These tests cover the bridge.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _build_state_manager():
    """Construct a StateManager with mocked db + oanda for in-memory testing."""
    from lumitrade.state.manager import StateManager

    config = MagicMock()
    config.instance_id = "test-instance"
    config.trading_mode = "PAPER"
    config.pairs = ["EUR_USD"]
    config.account_uuid = "test-uuid"

    db = MagicMock()
    db.select_one = AsyncMock(return_value=None)
    db.upsert = AsyncMock(return_value=None)

    oanda = MagicMock()
    oanda.get_account_summary_for_pairs = AsyncMock(return_value={"balance": "1000", "NAV": "1000"})

    return StateManager(config=config, db=db, oanda=oanda), db


@pytest.mark.asyncio
async def test_refresh_kill_switch_pulls_from_db():
    """refresh_kill_switch_from_db hydrates in-memory flag from DB."""
    sm, db = _build_state_manager()

    # In-memory starts False
    assert sm.kill_switch_active is False

    # Simulate the HTTP endpoint having written kill_switch_active=True to DB
    db.select_one = AsyncMock(return_value={
        "id": "singleton",
        "kill_switch_active": True,
    })

    result = await sm.refresh_kill_switch_from_db()

    assert result is True
    assert sm.kill_switch_active is True


@pytest.mark.asyncio
async def test_refresh_kill_switch_db_failure_fails_closed():
    """FAIL CLOSED on DB error per PRD:579 (Codex round-3 review of finding #4):
    a kill switch is a SAFETY contract — when in doubt, halt trading. The cost
    of a false trigger from a transient DB blip is acceptable; the cost of a
    silent miss on operator emergency activation is not."""
    sm, db = _build_state_manager()
    sm._state["kill_switch_active"] = False

    db.select_one = AsyncMock(side_effect=RuntimeError("DB down"))

    result = await sm.refresh_kill_switch_from_db()

    # MUST flip to True so the engine treats kill as active on any DB blip
    assert result is True
    assert sm.kill_switch_active is True


@pytest.mark.asyncio
async def test_save_persists_kill_switch_active():
    """save() must include kill_switch_active so a restart can rehydrate it."""
    sm, db = _build_state_manager()

    sm.kill_switch_active = True
    await sm.save()

    db.upsert.assert_awaited_once()
    upsert_args = db.upsert.await_args.args
    upsert_payload = upsert_args[1]
    assert upsert_payload.get("kill_switch_active") is True


@pytest.mark.asyncio
async def test_restore_rehydrates_kill_switch_active():
    """restore() must pick up kill_switch_active from DB so a restart-with-flag-set
    re-triggers close-out on the engine's next loop tick."""
    sm, db = _build_state_manager()

    db.select_one = AsyncMock(return_value={
        "id": "singleton",
        "risk_state": "NORMAL",
        "kill_switch_active": True,
        "open_trades": [],
        "daily_pnl_usd": "0",
        "weekly_pnl_usd": "0",
        "consecutive_losses": 0,
        "last_signal_time": {},
        "updated_at": "2026-04-25T12:00:00+00:00",
    })

    await sm.restore()

    assert sm.kill_switch_active is True
