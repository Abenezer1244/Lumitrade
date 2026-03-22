"""
Lumitrade Health Server
=========================
Lightweight aiohttp server on port 8000 for health checks.
Separate from the main trading engine — designed for external
monitoring, load balancers, and deployment platforms.

Per DOS Section 6.4.

Endpoints:
  GET /health  -> 200 (healthy) or 503 (degraded)
  GET /        -> Redirect to /health

Response JSON:
  {
    "status": "healthy" | "degraded",
    "instance_id": "...",
    "timestamp": "ISO8601",
    "uptime_seconds": N,
    "components": {
      "database": "ok" | "error",
      "oanda": "ok" | "error",
      "state": "ok" | "stale",
      "lock": "held" | "not_held"
    },
    "trading": {
      "mode": "PAPER" | "LIVE",
      "risk_state": "NORMAL",
      "open_trades": N,
      "last_signal_at": "ISO8601" | null
    }
  }
"""

import asyncio
from datetime import datetime, timezone

from aiohttp import web

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

HEALTH_PORT = 8000
STATE_STALENESS_THRESHOLD_SECONDS = 120


class HealthServer:
    """
    Lightweight HTTP health check server.
    Reads system_state from DB to report engine health.
    """

    def __init__(self, db: DatabaseClient, instance_id: str) -> None:
        self._db = db
        self._instance_id = instance_id
        self._started_at = datetime.now(timezone.utc)
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        """Start the health check HTTP server on HEALTH_PORT."""
        self._app = web.Application()
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/", self._handle_root)

        self._runner = web.AppRunner(self._app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", HEALTH_PORT)
        await self._site.start()

        logger.info(
            "health_server_started",
            port=HEALTH_PORT,
            instance_id=self._instance_id,
        )

    async def stop(self) -> None:
        """Gracefully stop the health check server."""
        if self._site is not None:
            await self._site.stop()
        if self._runner is not None:
            await self._runner.cleanup()

        logger.info("health_server_stopped")

    async def _handle_root(self, request: web.Request) -> web.Response:
        """Redirect root to /health."""
        raise web.HTTPFound("/health")

    async def _handle_health(self, request: web.Request) -> web.Response:
        """
        Main health check endpoint.
        Returns 200 if healthy, 503 if degraded.
        """
        now = datetime.now(timezone.utc)
        uptime = (now - self._started_at).total_seconds()

        # Gather component health
        components = await self._check_components(now)
        trading_info = await self._get_trading_info()

        # Determine overall status
        is_healthy = all(
            v in ("ok", "held")
            for v in components.values()
        )
        status = "healthy" if is_healthy else "degraded"
        http_status = 200 if is_healthy else 503

        body = {
            "status": status,
            "instance_id": self._instance_id,
            "timestamp": now.isoformat(),
            "uptime_seconds": round(uptime, 1),
            "components": components,
            "trading": trading_info,
        }

        return web.json_response(body, status=http_status)

    async def _check_components(self, now: datetime) -> dict:
        """Check health of individual components."""
        components = {
            "database": "error",
            "oanda": "error",
            "state": "stale",
            "lock": "not_held",
        }

        # Database check
        try:
            await self._db.select("system_state", {"key": "engine_state"}, limit=1)
            components["database"] = "ok"
        except Exception:
            logger.warning("health_check_db_failed")

        # State freshness check
        try:
            row = await self._db.select_one(
                "system_state",
                {"key": "engine_state"},
            )
            if row and row.get("value"):
                state_data = row["value"]
                last_persisted = state_data.get("last_persisted_at")
                if last_persisted:
                    persisted_at = datetime.fromisoformat(last_persisted)
                    elapsed = (now - persisted_at).total_seconds()
                    if elapsed <= STATE_STALENESS_THRESHOLD_SECONDS:
                        components["state"] = "ok"
                    else:
                        components["state"] = "stale"
        except Exception:
            logger.warning("health_check_state_failed")

        # Lock check
        try:
            lock_row = await self._db.select_one(
                "system_state",
                {"key": "engine_lock"},
            )
            if lock_row and lock_row.get("value"):
                lock_data = lock_row["value"]
                holder = lock_data.get("instance_id")
                if holder == self._instance_id:
                    components["lock"] = "held"
                elif holder:
                    components["lock"] = "held_by_other"
                else:
                    components["lock"] = "not_held"
        except Exception:
            logger.warning("health_check_lock_failed")

        # OANDA connectivity — derive from state freshness
        # (actual OANDA ping is done by watchdog, not health endpoint)
        if components["state"] == "ok":
            components["oanda"] = "ok"

        return components

    async def _get_trading_info(self) -> dict:
        """Extract trading info from persisted state."""
        default_info = {
            "mode": "UNKNOWN",
            "risk_state": "UNKNOWN",
            "open_trades": 0,
            "last_signal_at": None,
        }

        try:
            row = await self._db.select_one(
                "system_state",
                {"key": "engine_state"},
            )
            if row and row.get("value"):
                state_data = row["value"]
                return {
                    "mode": state_data.get("trading_mode", "UNKNOWN"),
                    "risk_state": state_data.get("risk_state", "UNKNOWN"),
                    "open_trades": len(state_data.get("open_trades", [])),
                    "last_signal_at": state_data.get("last_signal_at"),
                }
        except Exception:
            logger.warning("health_check_trading_info_failed")

        return default_info
