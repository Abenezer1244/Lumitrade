"""
Lumitrade Chaos Tests — Crash Recovery (CR-001 to CR-010)
===========================================================
Validates state persistence and lock acquisition survive crashes.
A crash that loses state = orphaned trades = uncontrolled risk.

Per QTS v2.0 Section 7.3.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumitrade.core.enums import RiskState
from lumitrade.state.lock import (
    LOCK_ROW_ID,
    LOCK_TTL_SECONDS,
    DistributedLock,
)
from lumitrade.state.manager import STATE_ROW_ID, StateManager


def _make_config_mock():
    """Create a mock LumitradeConfig with required attributes."""
    config = MagicMock()
    config.instance_id = "instance-A"
    config.trading_mode = "PAPER"
    config.pairs = ["EUR_USD", "GBP_USD"]
    return config


def _make_lock_row(instance_id: str, expires_at: datetime) -> dict:
    """Create a well-formed singleton row with lock fields."""
    return {
        "id": LOCK_ROW_ID,
        "instance_id": instance_id,
        "is_primary_instance": True,
        "lock_expires_at": expires_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.mark.chaos
class TestCrashRecovery:
    """CR-001 to CR-010: State persistence and lock recovery."""

    # ── CR-001: save() calls db.upsert with correct id ──────────

    @pytest.mark.asyncio
    async def test_cr001_save_calls_upsert(self):
        """CR-001: save() writes state to system_state with correct singleton id."""
        db = AsyncMock()
        config = _make_config_mock()
        oanda = AsyncMock()

        sm = StateManager(config, db, oanda)
        await sm.save()

        db.upsert.assert_called_once()
        call_args = db.upsert.call_args
        assert call_args[0][0] == "system_state"
        payload = call_args[0][1]
        assert payload["id"] == STATE_ROW_ID
        assert payload["risk_state"] == "NORMAL"
        assert "updated_at" in payload

    # ── CR-002: Lock acquired on empty system (no row) ────────────

    @pytest.mark.asyncio
    async def test_cr002_lock_acquired_empty_system(self):
        """CR-002: When no lock row exists, acquire succeeds via upsert."""
        db = AsyncMock()
        db.select_one.return_value = None  # No existing lock

        lock = DistributedLock(db)
        result = await lock.acquire("instance-A")

        assert result is True
        db.upsert.assert_called_once()
        upsert_payload = db.upsert.call_args[0][1]
        assert upsert_payload["instance_id"] == "instance-A"
        assert upsert_payload["is_primary_instance"] is True

    # ── CR-003: Lock not acquired when held by active other ───────

    @pytest.mark.asyncio
    async def test_cr003_lock_blocked_by_active_holder(self):
        """CR-003: Lock held by active instance-B blocks instance-A."""
        db = AsyncMock()
        # Lock expires in the future — holder is active
        future_expiry = datetime.now(timezone.utc) + timedelta(seconds=90)
        db.select_one.return_value = _make_lock_row("instance-B", future_expiry)

        lock = DistributedLock(db)
        result = await lock.acquire("instance-A")

        assert result is False
        db.upsert.assert_not_called()
        db.update.assert_not_called()

    # ── CR-004: Expired lock can be taken over ────────────────────

    @pytest.mark.asyncio
    async def test_cr004_expired_lock_takeover(self):
        """CR-004: Lock expired allows takeover."""
        db = AsyncMock()
        # Lock expired 10 seconds ago
        expired = datetime.now(timezone.utc) - timedelta(seconds=10)
        db.select_one.return_value = _make_lock_row("dead-instance", expired)

        lock = DistributedLock(db)
        result = await lock.acquire("instance-A")

        assert result is True
        db.update.assert_called_once()

    # ── CR-005: Lock released on shutdown ─────────────────────────

    @pytest.mark.asyncio
    async def test_cr005_lock_released_on_shutdown(self):
        """CR-005: release() clears the lock data for the holding instance."""
        db = AsyncMock()
        now = datetime.now(timezone.utc)
        future_expiry = now + timedelta(seconds=90)
        db.select_one.return_value = _make_lock_row("instance-A", future_expiry)

        lock = DistributedLock(db)
        await lock.release("instance-A")

        db.update.assert_called_once()
        update_payload = db.update.call_args[0][2]
        assert update_payload["instance_id"] is None
        assert update_payload["is_primary_instance"] is False
        assert update_payload["lock_expires_at"] is None

    # ── CR-006: State restored from DB ────────────────────────────

    @pytest.mark.asyncio
    async def test_cr006_state_restored_from_db(self):
        """CR-006: restore() merges persisted state and get() returns dict."""
        db = AsyncMock()
        config = _make_config_mock()
        oanda = AsyncMock()
        oanda.get_account_summary.return_value = {
            "balance": "500.00",
            "NAV": "500.00",
        }
        oanda.get_open_trades.return_value = []

        # DB returns persisted state as flat columns
        db.select_one.return_value = {
            "id": STATE_ROW_ID,
            "risk_state": "NORMAL",
            "open_trades": [],
            "daily_pnl_usd": "-15.00",
            "weekly_pnl_usd": "42.00",
            "consecutive_losses": 2,
            "last_signal_time": {"EUR_USD": "2025-01-06T12:00:00+00:00"},
            "confidence_threshold_override": None,
            "updated_at": "2025-01-06T12:30:00+00:00",
        }

        save_path = (
            "lumitrade.state.manager.StateManager.save"
        )
        reconciler_path = (
            "lumitrade.state.reconciler.PositionReconciler"
        )
        with patch(save_path, new_callable=AsyncMock):
            with patch(reconciler_path) as mock_reconciler_cls:
                mock_reconciler_instance = AsyncMock()
                mock_reconciler_instance.reconcile.return_value = {
                    "ghosts": [],
                    "phantoms": [],
                    "matched": [],
                    "reconciled_at": datetime.now(timezone.utc).isoformat(),
                }
                mock_reconciler_cls.return_value = mock_reconciler_instance

                with patch("lumitrade.infrastructure.alert_service.AlertService"):
                    sm = StateManager(config, db, oanda)
                    await sm.restore()

        state = await sm.get()
        assert isinstance(state, dict)
        assert state["daily_pnl"] == "-15.00"
        assert state["consecutive_losses"] == 2
        assert state["account_balance"] == "500.00"

    # ── CR-007: Missing DB state starts with defaults ─────────────

    @pytest.mark.asyncio
    async def test_cr007_missing_state_uses_defaults(self):
        """CR-007: When no persisted state exists, defaults to NORMAL risk state."""
        db = AsyncMock()
        config = _make_config_mock()
        oanda = AsyncMock()
        oanda.get_account_summary.return_value = {"balance": "0", "NAV": "0"}

        db.select_one.return_value = None  # No persisted state

        save_path = (
            "lumitrade.state.manager.StateManager.save"
        )
        reconciler_path = (
            "lumitrade.state.reconciler.PositionReconciler"
        )
        with patch(save_path, new_callable=AsyncMock):
            with patch(reconciler_path) as mock_reconciler_cls:
                mock_reconciler_instance = AsyncMock()
                mock_reconciler_instance.reconcile.return_value = {
                    "ghosts": [],
                    "phantoms": [],
                    "matched": [],
                    "reconciled_at": datetime.now(timezone.utc).isoformat(),
                }
                mock_reconciler_cls.return_value = mock_reconciler_instance

                with patch("lumitrade.infrastructure.alert_service.AlertService"):
                    sm = StateManager(config, db, oanda)
                    await sm.restore()

        assert sm.risk_state == RiskState.NORMAL
        state = await sm.get()
        assert state["consecutive_losses"] == 0

    # ── CR-008: Same instance can reacquire own lock ──────────────

    @pytest.mark.asyncio
    async def test_cr008_same_instance_reacquires(self):
        """CR-008: An instance that already holds the lock can refresh it."""
        db = AsyncMock()
        future_expiry = datetime.now(timezone.utc) + timedelta(seconds=60)
        db.select_one.return_value = _make_lock_row("instance-A", future_expiry)

        lock = DistributedLock(db)
        result = await lock.acquire("instance-A")

        assert result is True
        db.update.assert_called_once()  # _update_lock called

    # ── CR-009: DB write failure on save doesn't crash ────────────

    @pytest.mark.asyncio
    async def test_cr009_save_db_failure_no_crash(self):
        """CR-009: If DB upsert raises, save() catches it and doesn't propagate."""
        db = AsyncMock()
        db.upsert.side_effect = Exception("DB connection lost")
        config = _make_config_mock()
        oanda = AsyncMock()

        sm = StateManager(config, db, oanda)

        # This must NOT raise
        await sm.save()

        # Verify upsert was attempted
        db.upsert.assert_called_once()

    # ── CR-010: Lock acquire on empty table succeeds ──────────────

    @pytest.mark.asyncio
    async def test_cr010_lock_acquire_empty_table(self):
        """CR-010: Lock acquire when no row exists creates new lock and returns True."""
        db = AsyncMock()
        db.select_one.return_value = None

        lock = DistributedLock(db)
        result = await lock.acquire("fresh-instance")

        assert result is True
        db.upsert.assert_called_once()
        payload = db.upsert.call_args[0][1]
        assert payload["id"] == LOCK_ROW_ID
        assert payload["instance_id"] == "fresh-instance"
        assert payload["is_primary_instance"] is True
        assert "lock_expires_at" in payload
