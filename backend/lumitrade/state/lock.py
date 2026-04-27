"""
Lumitrade Distributed Lock
=============================
TTL-based distributed lock using the Supabase system_state table.
Ensures only one engine instance is PRIMARY at a time.
Per DOS Section 7.4.

Lock lifecycle:
  1. Instance tries to acquire lock (UPDATE singleton row).
  2. Primary instance renews lock every RENEW_INTERVAL seconds.
  3. If primary crashes, lock expires after LOCK_TTL_SECONDS.
  4. A standby instance can take over after lock_expires_at < now.
  5. On graceful shutdown, lock is explicitly released.

DB columns used (on the singleton row):
  is_primary_instance BOOLEAN
  instance_id TEXT
  lock_expires_at TIMESTAMPTZ
"""

import asyncio
from datetime import datetime, timedelta, timezone

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

LOCK_TTL_SECONDS = 120
RENEW_INTERVAL = 60
LOCK_ROW_ID = "singleton"
MAX_CONSECUTIVE_FAILURES = 2


class DistributedLock:
    """TTL-based distributed lock backed by Supabase system_state table."""

    def __init__(self, db: DatabaseClient) -> None:
        self._db = db
        self._renew_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

    async def acquire(self, instance_id: str) -> bool:
        """
        Try to become the primary instance.

        Checks the current lock state in system_state singleton row:
        - If no row or no holder: acquire it.
        - If lock is held by us: refresh it.
        - If lock_expires_at < now: lock is expired, take over.
        - Otherwise: return False (another instance is primary).

        Returns:
            True if this instance now holds the lock.
        """
        now = datetime.now(timezone.utc)

        try:
            row = await self._db.select_one(
                "system_state",
                {"id": LOCK_ROW_ID},
            )

            if row is None:
                # No singleton row — bootstrap. Two cold-starting instances
                # could race here, so after the upsert we must verify WE are
                # the recorded primary. Bootstrap path must not blindly
                # return True.
                await self._db.upsert(
                    "system_state",
                    {
                        "id": LOCK_ROW_ID,
                        "instance_id": instance_id,
                        "is_primary_instance": True,
                        "lock_expires_at": (
                            now + timedelta(seconds=LOCK_TTL_SECONDS)
                        ).isoformat(),
                        "updated_at": now.isoformat(),
                    },
                )
                # Verify with DELAYED double-readback. Codex round-4 finding #2:
                # an immediate readback can miss a competing writer that lands
                # microseconds later. Sleeping briefly then reading twice
                # materially shrinks the race window from microseconds to
                # 200ms+ collisions. NOT true CAS — proper fix requires DB-side
                # atomic primitive (Postgres advisory lock or version column +
                # update WHERE version = expected). Tracked as follow-up phase.
                # Single-instance Railway today doesn't trigger this race.
                await asyncio.sleep(0.2)
                check = await self._db.select_one("system_state", {"id": LOCK_ROW_ID})
                actual_holder = (check or {}).get("instance_id")
                if actual_holder != instance_id:
                    logger.warning(
                        "lock_bootstrap_lost_race",
                        instance_id=instance_id,
                        winner=actual_holder,
                    )
                    return False
                # Second confirmation read after another short delay
                await asyncio.sleep(0.2)
                check2 = await self._db.select_one("system_state", {"id": LOCK_ROW_ID})
                if (check2 or {}).get("instance_id") != instance_id:
                    logger.warning(
                        "lock_bootstrap_lost_race_late",
                        instance_id=instance_id,
                        winner=(check2 or {}).get("instance_id"),
                    )
                    return False
                logger.info(
                    "lock_acquired",
                    instance_id=instance_id,
                    method="initial_claim",
                )
                return True

            current_holder = row.get("instance_id")
            lock_expires_at_str = row.get("lock_expires_at")

            # We already hold the lock — refresh. Conditional update on our
            # own instance_id; if it fails, someone else stole the lock between
            # the read and the write.
            if current_holder == instance_id:
                ok = await self._update_lock(instance_id, now, expected_holder=instance_id)
                if not ok:
                    logger.warning("lock_reacquire_lost_race", instance_id=instance_id)
                    return False
                logger.info("lock_reacquired", instance_id=instance_id)
                return True

            # Check if no holder (vacant) or lock is no longer marked primary
            if current_holder is None or not row.get("is_primary_instance"):
                # Vacant-row case: cannot CAS on instance_id == NULL via our
                # current update primitive (filter does not support null
                # predicates). Use write-then-readback to detect race losers,
                # same pattern as the cold-start bootstrap path. Two concurrent
                # claimants both pass through the unconditional update, but
                # only the last writer's instance_id stays recorded — the
                # earlier writer reads back and discovers it lost.
                await self._db.update(
                    "system_state",
                    {"id": LOCK_ROW_ID},
                    {
                        "instance_id": instance_id,
                        "is_primary_instance": True,
                        "lock_expires_at": (now + timedelta(seconds=LOCK_TTL_SECONDS)).isoformat(),
                        "updated_at": now.isoformat(),
                    },
                )
                # Same delayed double-readback pattern as bootstrap.
                # See bootstrap branch comment for the limitation.
                await asyncio.sleep(0.2)
                check = await self._db.select_one("system_state", {"id": LOCK_ROW_ID})
                actual_holder = (check or {}).get("instance_id")
                if actual_holder != instance_id:
                    logger.warning(
                        "lock_claim_vacant_lost_race",
                        instance_id=instance_id,
                        previous_holder=current_holder,
                        winner=actual_holder,
                    )
                    return False
                # Second confirmation read
                await asyncio.sleep(0.2)
                check2 = await self._db.select_one("system_state", {"id": LOCK_ROW_ID})
                if (check2 or {}).get("instance_id") != instance_id:
                    logger.warning(
                        "lock_claim_vacant_lost_race_late",
                        instance_id=instance_id,
                        winner=(check2 or {}).get("instance_id"),
                    )
                    return False
                logger.info("lock_acquired", instance_id=instance_id, method="claim_vacant")
                return True

            if lock_expires_at_str:
                expires_at = datetime.fromisoformat(lock_expires_at_str)
                if now > expires_at:
                    # Lock holder is presumed dead — conditional takeover.
                    # Only succeeds if the holder hasn't changed since we read.
                    ok = await self._update_lock(instance_id, now, expected_holder=current_holder)
                    if not ok:
                        logger.warning(
                            "lock_takeover_lost_race",
                            instance_id=instance_id,
                            previous_holder=current_holder,
                        )
                        return False
                    logger.warning(
                        "lock_takeover",
                        instance_id=instance_id,
                        previous_holder=current_holder,
                        expired_at=lock_expires_at_str,
                    )
                    return True

                remaining = (expires_at - now).total_seconds()
                logger.info(
                    "lock_held_by_other",
                    current_holder=current_holder,
                    expires_in_seconds=remaining,
                )
                return False

            # No lock_expires_at — malformed, conditional takeover (still
            # require expected_holder to avoid clobbering a concurrent writer).
            ok = await self._update_lock(instance_id, now, expected_holder=current_holder)
            if not ok:
                logger.warning(
                    "lock_takeover_malformed_lost_race",
                    instance_id=instance_id,
                    previous_holder=current_holder,
                )
                return False
            logger.warning(
                "lock_takeover_malformed",
                instance_id=instance_id,
                previous_holder=current_holder,
            )
            return True

        except Exception:
            logger.exception(
                "lock_acquire_failed",
                instance_id=instance_id,
            )
            return False

    async def renew_loop(self, instance_id: str) -> None:
        """
        Background task that renews the lock every RENEW_INTERVAL seconds.

        If renewal fails MAX_CONSECUTIVE_FAILURES times in a row, triggers
        SystemExit to force a clean shutdown — another instance should take over.
        """
        consecutive_failures = 0
        self._shutdown_event.clear()

        logger.info(
            "lock_renew_loop_started",
            instance_id=instance_id,
            interval_seconds=RENEW_INTERVAL,
        )

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(RENEW_INTERVAL)
            except asyncio.CancelledError:
                logger.info(
                    "lock_renew_loop_cancelled",
                    instance_id=instance_id,
                )
                return

            if self._shutdown_event.is_set():
                break

            try:
                now = datetime.now(timezone.utc)
                # Renew with conditional update — only succeeds if WE still hold
                # the lock. If another instance has taken over (split-brain
                # avoidance), this returns False and we treat it as a failure
                # so the failure counter trips and we shut down cleanly.
                ok = await self._update_lock(instance_id, now, expected_holder=instance_id)
                if not ok:
                    raise RuntimeError(
                        f"Lock renewal CAS failed — another instance "
                        f"may have taken over while we were renewing"
                    )
                consecutive_failures = 0
                logger.debug(
                    "lock_renewed",
                    instance_id=instance_id,
                )
            except Exception:
                consecutive_failures += 1
                logger.error(
                    "lock_renewal_failed",
                    instance_id=instance_id,
                    consecutive_failures=consecutive_failures,
                    max_failures=MAX_CONSECUTIVE_FAILURES,
                )

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.critical(
                        "lock_renewal_fatal",
                        instance_id=instance_id,
                        msg="Exceeded max consecutive renewal failures, shutting down",
                    )
                    raise SystemExit(
                        f"Lock renewal failed "
                        f"{consecutive_failures} times. "
                        "Shutting down for failover."
                    )

    async def release(self, instance_id: str) -> None:
        """
        Release the lock on graceful shutdown.

        Only releases if we are the current holder — prevents accidental
        release of another instance's lock.
        """
        self._shutdown_event.set()

        if self._renew_task is not None and not self._renew_task.done():
            self._renew_task.cancel()
            try:
                await self._renew_task
            except (asyncio.CancelledError, SystemExit):
                pass
            self._renew_task = None

        try:
            row = await self._db.select_one(
                "system_state",
                {"id": LOCK_ROW_ID},
            )

            if row is None:
                logger.info(
                    "lock_release_noop",
                    instance_id=instance_id,
                    reason="no_lock_exists",
                )
                return

            current_holder = row.get("instance_id")

            if current_holder != instance_id:
                logger.warning(
                    "lock_release_skipped",
                    instance_id=instance_id,
                    current_holder=current_holder,
                    reason="not_lock_holder",
                )
                return

            now = datetime.now(timezone.utc)
            # CAS release: filter by both id AND instance_id so a takeover
            # that happened between the read above and this write doesn't
            # get clobbered by the previous holder.
            result = await self._db.update(
                "system_state",
                {"id": LOCK_ROW_ID, "instance_id": instance_id},
                {
                    "instance_id": None,
                    "is_primary_instance": False,
                    "lock_expires_at": None,
                    "updated_at": now.isoformat(),
                },
            )
            rows_updated = len(result) if isinstance(result, list) else 0
            if rows_updated != 1:
                logger.warning(
                    "lock_release_lost_race",
                    instance_id=instance_id,
                    rows_updated=rows_updated,
                    msg="Another instance took the lock between our read and release write — leaving them alone",
                )
                return
            logger.info(
                "lock_released",
                instance_id=instance_id,
            )

        except Exception:
            logger.exception(
                "lock_release_failed",
                instance_id=instance_id,
            )

    def start_renew_loop(self, instance_id: str) -> asyncio.Task:
        """Start the renewal background task and return the task handle."""
        self._renew_task = asyncio.create_task(
            self.renew_loop(instance_id),
            name=f"lock_renew_{instance_id}",
        )
        return self._renew_task

    async def _update_lock(
        self,
        instance_id: str,
        now: datetime,
        expected_holder: str | None = None,
    ) -> bool:
        """
        Write the lock renewal to system_state singleton row.
        Uses conditional update when expected_holder is set to prevent
        race conditions (only updates if the current holder matches).

        Returns True ONLY if the conditional update actually matched a row
        (compare-and-swap semantics). Returns False on zero-match — Codex
        review 2026-04-25 finding #1: previous version returned True
        unconditionally, allowing two instances to both believe they hold
        the lock after a failover race.
        """
        lock_data = {
            "instance_id": instance_id,
            "is_primary_instance": True,
            "lock_expires_at": (
                now + timedelta(seconds=LOCK_TTL_SECONDS)
            ).isoformat(),
            "updated_at": now.isoformat(),
        }

        if expected_holder is not None:
            # Conditional update: only if current holder matches expected
            filters = {"id": LOCK_ROW_ID, "instance_id": expected_holder}
        else:
            filters = {"id": LOCK_ROW_ID}

        result = await self._db.update("system_state", filters, lock_data)

        # CAS verification: db.update returns the list of rows that matched
        # the filters and were updated. Anything other than exactly 1 row
        # means the conditional update raced against another writer and
        # must be treated as a failed acquire/renew.
        rows_updated = len(result) if isinstance(result, list) else 0
        if rows_updated != 1:
            logger.warning(
                "lock_cas_failed",
                instance_id=instance_id,
                expected_holder=expected_holder,
                rows_updated=rows_updated,
            )
            return False
        return True
