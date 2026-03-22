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
    LOCK_ROW_KEY,
    LOCK_TTL_SECONDS,
    TAKEOVER_THRESHOLD,
    DistributedLock,
)


def _make_lock_row(instance_id: str, renewed_at: datetime) -> dict:
    """Create a well-formed lock row as returned by select_one."""
    return {
        "key": LOCK_ROW_KEY,
        "value": {
            "instance_id": instance_id,
            "acquired_at": renewed_at.isoformat(),
            "renewed_at": renewed_at.isoformat(),
            "ttl_seconds": LOCK_TTL_SECONDS,
        },
        "updated_at": renewed_at.isoformat(),
    }


def _make_released_lock_row() -> dict:
    """Lock row after release — instance_id is None."""
    now = datetime.now(timezone.utc)
    return {
        "key": LOCK_ROW_KEY,
        "value": {
            "instance_id": None,
            "acquired_at": None,
            "renewed_at": None,
            "ttl_seconds": LOCK_TTL_SECONDS,
            "released_at": now.isoformat(),
            "released_by": "primary-01",
        },
        "updated_at": now.isoformat(),
    }


@pytest.mark.chaos
class TestFailover:
    """FO-001 to FO-006: Distributed lock failover scenarios."""

    # ── FO-001: Standby blocked while primary is active ───────────

    @pytest.mark.asyncio
    async def test_fo001_standby_blocked_by_active_primary(self):
        """FO-001: Standby cannot acquire while primary renewed recently."""
        db = AsyncMock()
        recent = datetime.now(timezone.utc) - timedelta(seconds=30)
        db.select_one.return_value = _make_lock_row("primary-01", recent)

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
        expired = datetime.now(timezone.utc) - timedelta(
            seconds=TAKEOVER_THRESHOLD + 60
        )
        db.select_one.return_value = _make_lock_row("primary-01", expired)

        lock = DistributedLock(db)
        result = await lock.acquire("standby-01")

        assert result is True
        db.update.assert_called_once()
        update_payload = db.update.call_args[0][2]
        assert update_payload["value"]["instance_id"] == "standby-01"

    # ── FO-003: Primary reclaims after standby releases ───────────

    @pytest.mark.asyncio
    async def test_fo003_primary_reclaims_after_release(self):
        """FO-003: Primary reclaims after standby releases."""
        db = AsyncMock()
        # First call: standby releases (lock row has instance_id=None)
        # The released lock row has instance_id=None, which != "primary-01"
        # and renewed_at=None, so it falls through to the malformed branch
        # which does _update_lock and returns True.
        db.select_one.return_value = _make_released_lock_row()

        lock = DistributedLock(db)
        result = await lock.acquire("primary-01")

        assert result is True

    # ── FO-004: Release clears lock data ──────────────────────────

    @pytest.mark.asyncio
    async def test_fo004_release_clears_lock(self):
        """FO-004: release() sets instance_id to None and records released_by."""
        db = AsyncMock()
        now = datetime.now(timezone.utc)
        db.select_one.return_value = _make_lock_row("primary-01", now)

        lock = DistributedLock(db)
        await lock.release("primary-01")

        db.update.assert_called_once()
        update_args = db.update.call_args[0]
        assert update_args[0] == "system_state"
        assert update_args[1] == {"key": LOCK_ROW_KEY}
        cleared = update_args[2]["value"]
        assert cleared["instance_id"] is None
        assert cleared["acquired_at"] is None
        assert cleared["renewed_at"] is None
        assert cleared["released_by"] == "primary-01"

    # ── FO-005: Acquire on empty table creates lock ───────────────

    @pytest.mark.asyncio
    async def test_fo005_acquire_empty_table(self):
        """FO-005: When no lock row exists at all, acquire creates one via upsert."""
        db = AsyncMock()
        db.select_one.return_value = None

        lock = DistributedLock(db)
        result = await lock.acquire("new-instance")

        assert result is True
        db.upsert.assert_called_once()
        payload = db.upsert.call_args[0][1]
        assert payload["key"] == LOCK_ROW_KEY
        assert payload["value"]["instance_id"] == "new-instance"

    # ── FO-006: Same instance re-acquires (renew) ─────────────────

    @pytest.mark.asyncio
    async def test_fo006_same_instance_reacquires(self):
        """FO-006: Instance that already holds the lock can refresh/renew it."""
        db = AsyncMock()
        now = datetime.now(timezone.utc) - timedelta(seconds=50)
        db.select_one.return_value = _make_lock_row("instance-A", now)

        lock = DistributedLock(db)
        result = await lock.acquire("instance-A")

        assert result is True
        db.update.assert_called_once()  # _update_lock refreshes the lock
