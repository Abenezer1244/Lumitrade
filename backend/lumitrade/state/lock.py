"""
Lumitrade Distributed Lock
=============================
TTL-based distributed lock using the Supabase system_state table.
Ensures only one engine instance is PRIMARY at a time.
Per DOS Section 7.4.

Lock lifecycle:
  1. Instance tries to acquire lock (INSERT or UPDATE if expired).
  2. Primary instance renews lock every RENEW_INTERVAL seconds.
  3. If primary crashes, lock expires after LOCK_TTL_SECONDS.
  4. A standby instance can take over after TAKEOVER_THRESHOLD seconds.
  5. On graceful shutdown, lock is explicitly released.
"""

import asyncio
from datetime import datetime, timezone

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

LOCK_TTL_SECONDS = 120
RENEW_INTERVAL = 60
TAKEOVER_THRESHOLD = 180
LOCK_ROW_KEY = "engine_lock"
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

        Checks the current lock state in system_state:
        - If no lock exists: acquire it.
        - If lock is held by us: refresh it.
        - If lock is expired beyond TAKEOVER_THRESHOLD: take over.
        - Otherwise: return False (another instance is primary).

        Returns:
            True if this instance now holds the lock.
        """
        now = datetime.now(timezone.utc)

        try:
            row = await self._db.select_one(
                "system_state",
                {"key": LOCK_ROW_KEY},
            )

            if row is None:
                # No lock exists — claim it
                await self._db.upsert(
                    "system_state",
                    {
                        "key": LOCK_ROW_KEY,
                        "value": {
                            "instance_id": instance_id,
                            "acquired_at": now.isoformat(),
                            "renewed_at": now.isoformat(),
                            "ttl_seconds": LOCK_TTL_SECONDS,
                        },
                        "updated_at": now.isoformat(),
                    },
                )
                logger.info(
                    "lock_acquired",
                    instance_id=instance_id,
                    method="initial_claim",
                )
                return True

            lock_data = row.get("value", {})
            current_holder = lock_data.get("instance_id")
            renewed_at_str = lock_data.get("renewed_at")

            # We already hold the lock — refresh
            if current_holder == instance_id:
                await self._update_lock(instance_id, now)
                logger.info(
                    "lock_reacquired",
                    instance_id=instance_id,
                )
                return True

            # Check if the current lock is expired
            if renewed_at_str:
                renewed_at = datetime.fromisoformat(renewed_at_str)
                elapsed = (now - renewed_at).total_seconds()

                if elapsed > TAKEOVER_THRESHOLD:
                    # Lock holder is presumed dead — take over
                    await self._update_lock(instance_id, now)
                    logger.warning(
                        "lock_takeover",
                        instance_id=instance_id,
                        previous_holder=current_holder,
                        elapsed_seconds=elapsed,
                    )
                    return True

                logger.info(
                    "lock_held_by_other",
                    current_holder=current_holder,
                    elapsed_seconds=elapsed,
                    takeover_in=TAKEOVER_THRESHOLD - elapsed,
                )
                return False

            # Malformed lock data — take over
            await self._update_lock(instance_id, now)
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
                await self._update_lock(instance_id, now)
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
                {"key": LOCK_ROW_KEY},
            )

            if row is None:
                logger.info(
                    "lock_release_noop",
                    instance_id=instance_id,
                    reason="no_lock_exists",
                )
                return

            lock_data = row.get("value", {})
            current_holder = lock_data.get("instance_id")

            if current_holder != instance_id:
                logger.warning(
                    "lock_release_skipped",
                    instance_id=instance_id,
                    current_holder=current_holder,
                    reason="not_lock_holder",
                )
                return

            now = datetime.now(timezone.utc)
            await self._db.update(
                "system_state",
                {"key": LOCK_ROW_KEY},
                {
                    "value": {
                        "instance_id": None,
                        "acquired_at": None,
                        "renewed_at": None,
                        "ttl_seconds": LOCK_TTL_SECONDS,
                        "released_at": now.isoformat(),
                        "released_by": instance_id,
                    },
                    "updated_at": now.isoformat(),
                },
            )
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

    async def _update_lock(self, instance_id: str, now: datetime) -> None:
        """Write the lock renewal to system_state."""
        await self._db.update(
            "system_state",
            {"key": LOCK_ROW_KEY},
            {
                "value": {
                    "instance_id": instance_id,
                    "acquired_at": now.isoformat(),
                    "renewed_at": now.isoformat(),
                    "ttl_seconds": LOCK_TTL_SECONDS,
                },
                "updated_at": now.isoformat(),
            },
        )
