"""
Lumitrade Chaos Tests — Failover (FO-001 to FO-006)
======================================================
Validates distributed lock failover: standby takes over dead primary.
If failover breaks, the system stays down when the primary crashes.

Per QTS v2.0 Section 7.4.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from lumitrade.state.lock import (
    LOCK_ROW_ID,
    LOCK_TTL_SECONDS,
    DistributedLock,
)


def _make_lock_row(instance_id: str, expires_at: datetime) -> dict:
    """Create a well-formed singleton row with lock fields as returned by select_one."""
    return {
        "id": LOCK_ROW_ID,
        "instance_id": instance_id,
        "is_primary_instance": True,
        "lock_expires_at": expires_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _make_released_lock_row() -> dict:
    """Singleton row after release — instance_id is None, is_primary_instance is False."""
    now = datetime.now(timezone.utc)
    return {
        "id": LOCK_ROW_ID,
        "instance_id": None,
        "is_primary_instance": False,
        "lock_expires_at": None,
        "updated_at": now.isoformat(),
    }


def _make_acquired_row(instance_id: str) -> dict:
    """Singleton row showing a successful acquisition for double-readback mocks."""
    future = datetime.now(timezone.utc) + timedelta(seconds=LOCK_TTL_SECONDS)
    return {
        "id": LOCK_ROW_ID,
        "instance_id": instance_id,
        "is_primary_instance": True,
        "lock_expires_at": future.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.mark.chaos
class TestFailover:
    """FO-001 to FO-006: Distributed lock failover scenarios."""

    # ── FO-001: Standby blocked while primary is active ───────────

    @pytest.mark.asyncio
    async def test_fo001_standby_blocked_by_active_primary(self):
        """FO-001: Standby cannot acquire while primary lock is not expired."""
        db = AsyncMock()
        # Lock expires in the future — primary is active
        future_expiry = datetime.now(timezone.utc) + timedelta(seconds=90)
        db.select_one.return_value = _make_lock_row("primary-01", future_expiry)

        lock = DistributedLock(db)
        result = await lock.acquire("standby-01")

        assert result is False
        db.upsert.assert_not_called()
        db.update.assert_not_called()

    # ── FO-002: Standby takes over expired lock ───────────────────

    @pytest.mark.asyncio
    async def test_fo002_standby_takes_over_expired_lock(self):
        """FO-002: Expired primary lock allows standby takeover."""
        db = AsyncMock()
        expired = datetime.now(timezone.utc) - timedelta(seconds=60)
        db.select_one.return_value = _make_lock_row("primary-01", expired)
        # CAS update must return 1 row to signal success
        db.update.return_value = [{"id": LOCK_ROW_ID}]

        lock = DistributedLock(db)
        result = await lock.acquire("standby-01")

        assert result is True
        db.update.assert_called_once()
        update_payload = db.update.call_args[0][2]
        assert update_payload["instance_id"] == "standby-01"
        assert update_payload["is_primary_instance"] is True

    # ── FO-003: Primary reclaims after standby releases ───────────

    @pytest.mark.asyncio
    async def test_fo003_primary_reclaims_after_release(self):
        """FO-003: Primary reclaims after standby releases."""
        db = AsyncMock()
        released = _make_released_lock_row()
        acquired = _make_acquired_row("primary-01")
        # Initial read returns released row; double-readback returns acquired row
        db.select_one.side_effect = [released, acquired, acquired]
        db.update.return_value = [{"id": LOCK_ROW_ID}]

        lock = DistributedLock(db)
        result = await lock.acquire("primary-01")

        assert result is True

    # ── FO-004: Release clears lock data ──────────────────────────

    @pytest.mark.asyncio
    async def test_fo004_release_clears_lock(self):
        """FO-004: release() sets is_primary_instance=False, instance_id=None."""
        db = AsyncMock()
        now = datetime.now(timezone.utc)
        future_expiry = now + timedelta(seconds=90)
        db.select_one.return_value = _make_lock_row("primary-01", future_expiry)
        # Return 1 row so the CAS release succeeds (not lost-race branch)
        db.update.return_value = [{"id": LOCK_ROW_ID}]

        lock = DistributedLock(db)
        await lock.release("primary-01")

        db.update.assert_called_once()
        update_args = db.update.call_args[0]
        assert update_args[0] == "system_state"
        # CAS release filters on both id and instance_id
        assert update_args[1] == {"id": LOCK_ROW_ID, "instance_id": "primary-01"}
        cleared = update_args[2]
        assert cleared["instance_id"] is None
        assert cleared["is_primary_instance"] is False
        assert cleared["lock_expires_at"] is None

    # ── FO-005: Acquire on empty table creates lock ───────────────

    @pytest.mark.asyncio
    async def test_fo005_acquire_empty_table(self):
        """FO-005: When no lock row exists at all, acquire creates one via upsert."""
        db = AsyncMock()
        acquired = _make_acquired_row("new-instance")
        # First select_one returns None (empty table); readbacks return acquired row
        db.select_one.side_effect = [None, acquired, acquired]

        lock = DistributedLock(db)
        result = await lock.acquire("new-instance")

        assert result is True
        db.upsert.assert_called_once()
        payload = db.upsert.call_args[0][1]
        assert payload["id"] == LOCK_ROW_ID
        assert payload["instance_id"] == "new-instance"
        assert payload["is_primary_instance"] is True

    # ── FO-006: Same instance re-acquires (renew) ─────────────────

    @pytest.mark.asyncio
    async def test_fo006_same_instance_reacquires(self):
        """FO-006: Instance that already holds the lock can refresh/renew it."""
        db = AsyncMock()
        future_expiry = datetime.now(timezone.utc) + timedelta(seconds=60)
        db.select_one.return_value = _make_lock_row("instance-A", future_expiry)
        # CAS renewal must return 1 row to signal success
        db.update.return_value = [{"id": LOCK_ROW_ID}]

        lock = DistributedLock(db)
        result = await lock.acquire("instance-A")

        assert result is True
        db.update.assert_called_once()  # _update_lock refreshes the lock
