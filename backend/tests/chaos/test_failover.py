"""
Lumitrade Chaos Tests — Failover (FO-001 to FO-008)
======================================================
Validates distributed lock failover: standby takes over dead primary.
If failover breaks, the system stays down when the primary crashes.

Per QTS v2.0 Section 7.4.

NOTE (audit 2026-06-25): the lock now stores a PER-PROCESS owner token
(`INSTANCE_ID#<lease>`), not the bare INSTANCE_ID, so two processes sharing an
INSTANCE_ID (rolling-deploy overlap) cannot both hold the lock. Tests build
mock rows from `lock._owner(...)` to reflect what the process actually persists.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from lumitrade.state.lock import (
    LOCK_ROW_ID,
    LOCK_TTL_SECONDS,
    MAX_CONSECUTIVE_FAILURES,
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
    """FO-001 to FO-008: Distributed lock failover scenarios."""

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
        lock = DistributedLock(db)
        expired = datetime.now(timezone.utc) - timedelta(seconds=60)
        db.select_one.return_value = _make_lock_row(lock._owner("primary-01"), expired)
        # CAS update must return 1 row to signal success
        db.update.return_value = [{"id": LOCK_ROW_ID}]

        result = await lock.acquire("standby-01")

        assert result is True
        db.update.assert_called_once()
        update_payload = db.update.call_args[0][2]
        # The persisted owner is this process's composite token, not the bare id.
        assert update_payload["instance_id"] == lock._owner("standby-01")
        assert update_payload["is_primary_instance"] is True

    # ── FO-003: Primary reclaims after standby releases ───────────

    @pytest.mark.asyncio
    async def test_fo003_primary_reclaims_after_release(self):
        """FO-003: Primary reclaims after standby releases (claims vacant row)."""
        db = AsyncMock()
        lock = DistributedLock(db)
        released = _make_released_lock_row()
        acquired = _make_acquired_row(lock._owner("primary-01"))
        # Initial read returns released row; double-readback returns acquired row
        db.select_one.side_effect = [released, acquired, acquired]
        db.update.return_value = [{"id": LOCK_ROW_ID}]

        result = await lock.acquire("primary-01")

        assert result is True

    # ── FO-004: Release clears lock data ──────────────────────────

    @pytest.mark.asyncio
    async def test_fo004_release_clears_lock(self):
        """FO-004: release() sets is_primary_instance=False, instance_id=None."""
        db = AsyncMock()
        lock = DistributedLock(db)
        now = datetime.now(timezone.utc)
        future_expiry = now + timedelta(seconds=90)
        # The holder recorded in the row must be OUR owner token for release to fire.
        db.select_one.return_value = _make_lock_row(lock._owner("primary-01"), future_expiry)
        # Return 1 row so the CAS release succeeds (not lost-race branch)
        db.update.return_value = [{"id": LOCK_ROW_ID}]

        await lock.release("primary-01")

        db.update.assert_called_once()
        update_args = db.update.call_args[0]
        assert update_args[0] == "system_state"
        # CAS release filters on both id and our owner token
        assert update_args[1] == {"id": LOCK_ROW_ID, "instance_id": lock._owner("primary-01")}
        cleared = update_args[2]
        assert cleared["instance_id"] is None
        assert cleared["is_primary_instance"] is False
        assert cleared["lock_expires_at"] is None

    # ── FO-005: Acquire on empty table creates lock ───────────────

    @pytest.mark.asyncio
    async def test_fo005_acquire_empty_table(self):
        """FO-005: When no lock row exists at all, acquire creates one via upsert."""
        db = AsyncMock()
        lock = DistributedLock(db)
        acquired = _make_acquired_row(lock._owner("new-instance"))
        # First select_one returns None (empty table); readbacks return acquired row
        db.select_one.side_effect = [None, acquired, acquired]

        result = await lock.acquire("new-instance")

        assert result is True
        db.upsert.assert_called_once()
        payload = db.upsert.call_args[0][1]
        assert payload["id"] == LOCK_ROW_ID
        assert payload["instance_id"] == lock._owner("new-instance")
        assert payload["is_primary_instance"] is True

    # ── FO-006: Same instance re-acquires (renew) ─────────────────

    @pytest.mark.asyncio
    async def test_fo006_same_instance_reacquires(self):
        """FO-006: A process that already holds the lock (same owner token) can
        refresh/renew it."""
        db = AsyncMock()
        lock = DistributedLock(db)
        future_expiry = datetime.now(timezone.utc) + timedelta(seconds=60)
        db.select_one.return_value = _make_lock_row(lock._owner("instance-A"), future_expiry)
        # CAS renewal must return 1 row to signal success
        db.update.return_value = [{"id": LOCK_ROW_ID}]

        result = await lock.acquire("instance-A")

        assert result is True
        db.update.assert_called_once()  # _update_lock refreshes the lock

    # ── FO-007: Same INSTANCE_ID, different process → split-brain blocked ──

    @pytest.mark.asyncio
    async def test_fo007_same_instance_id_different_process_cannot_steal(self):
        """FO-007 (audit fix, Codex CRITICAL #3): two processes that share the
        SAME configured INSTANCE_ID (e.g. overlapping containers during a
        Railway rolling deploy) get DIFFERENT owner tokens. The newcomer must
        NOT be able to 'refresh' the active holder's lock — otherwise both run
        as primary and place duplicate live orders."""
        db = AsyncMock()
        held_by = DistributedLock(db)    # process 1 (we only need its owner token)
        newcomer = DistributedLock(db)   # process 2, same db + same INSTANCE_ID
        # Same human INSTANCE_ID, different per-process lease tokens.
        assert held_by._owner("ENGINE") != newcomer._owner("ENGINE")

        future_expiry = datetime.now(timezone.utc) + timedelta(seconds=90)
        # Row is held (not expired) by the FIRST process's owner token.
        db.select_one.return_value = _make_lock_row(held_by._owner("ENGINE"), future_expiry)

        # Newcomer shares INSTANCE_ID "ENGINE" but is a different process.
        result = await newcomer.acquire("ENGINE")

        assert result is False  # cannot refresh someone else's lease
        db.update.assert_not_called()  # no CAS write attempted — active lock respected

    # ── FO-008: Fatal renewal failure invokes failover callback, not SystemExit ──

    @pytest.mark.asyncio
    async def test_fo008_renewal_failure_invokes_on_lock_lost(self):
        """FO-008 (audit fix, Codex CRITICAL #2): when lock renewal fails fatally,
        the renew loop must invoke the on_lock_lost callback (which hard-halts
        execution and shuts down) rather than raising a bare SystemExit inside an
        unsupervised task that leaves the engine trading without a lease."""
        db = AsyncMock()
        # Every CAS renewal matches 0 rows → _update_lock returns False → failure.
        db.update.return_value = []

        called = {"n": 0}

        async def on_lost():
            called["n"] += 1

        lock = DistributedLock(db, on_lock_lost=on_lost)

        # Drive _trigger_lock_lost directly (renew_loop's fatal branch calls it):
        # callback path must fire and NOT raise SystemExit.
        await lock._trigger_lock_lost()
        assert called["n"] == 1
        assert lock._shutdown_event.is_set()

        # And with no callback wired, it must fail safe via SystemExit.
        bare = DistributedLock(db)
        with pytest.raises(SystemExit):
            await bare._trigger_lock_lost()

        # Sanity: MAX_CONSECUTIVE_FAILURES is the documented fatal threshold.
        assert MAX_CONSECUTIVE_FAILURES >= 1
