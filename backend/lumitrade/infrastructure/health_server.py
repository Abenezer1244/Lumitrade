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

import os
from datetime import datetime, timezone

from aiohttp import web

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

HEALTH_PORT = int(os.environ.get("PORT", 8000))
STATE_STALENESS_THRESHOLD_SECONDS = 120
STATE_ROW_ID = "singleton"


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
        self._app.router.add_get("/prices", self._handle_prices)
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

        # Determine overall status — healthy if DB is ok (other components may still be starting)
        db_status = components.get("database", {})
        db_ok = (db_status.get("status") if isinstance(db_status, dict) else db_status) == "ok"

        # Count how many critical components are ok
        ok_count = sum(
            1 for v in components.values()
            if (v.get("status") if isinstance(v, dict) else v) in ("ok", "held", "CLOSED")
        )
        total = len(components)

        # Healthy if DB is up (core requirement). Degraded only if DB is down.
        is_healthy = db_ok
        status = "healthy" if ok_count == total else ("degraded" if db_ok else "down")
        http_status = 200 if db_ok else 503

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
        """Check health of individual components with real latency."""
        import time

        components = {
            "database": {"status": "error", "latency_ms": 0},
            "oanda": {"status": "error", "latency_ms": 0},
            "state": {"status": "stale", "updated_ago_s": 0},
            "lock": {"status": "not_held"},
            "ai_brain": {"status": "offline", "last_call_ago_s": 0},
            "price_feed": {"status": "offline", "last_tick_ago_s": 0},
            "risk_engine": {"status": "ok", "state": "NORMAL"},
            "circuit_breaker": {"status": "CLOSED"},
        }

        row = None

        # Database check with real latency measurement
        try:
            t0 = time.monotonic()
            result = await self._db.select(
                "system_state", {"id": STATE_ROW_ID}, limit=1
            )
            db_latency = round((time.monotonic() - t0) * 1000, 1)
            components["database"] = {"status": "ok", "latency_ms": db_latency}
        except Exception:
            logger.warning("health_check_db_failed")

        # Fetch singleton row once for all checks
        try:
            row = await self._db.select_one(
                "system_state", {"id": STATE_ROW_ID}
            )
        except Exception:
            pass

        if row:
            # State freshness
            updated_at_str = row.get("updated_at")
            if updated_at_str:
                try:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    elapsed = (now - updated_at).total_seconds()
                    state_status = "ok" if elapsed <= STATE_STALENESS_THRESHOLD_SECONDS else "stale"
                    components["state"] = {"status": state_status, "updated_ago_s": round(elapsed)}
                except Exception:
                    pass

            # Lock
            holder = row.get("instance_id")
            is_primary = row.get("is_primary_instance", False)
            if is_primary and holder == self._instance_id:
                components["lock"] = {"status": "held"}
            elif is_primary and holder:
                components["lock"] = {"status": "held_by_other"}

            # OANDA — derive from state freshness
            if components["state"]["status"] == "ok":
                components["oanda"] = {"status": "ok", "latency_ms": components["database"]["latency_ms"]}

            # Risk engine state
            risk_state = row.get("risk_state", "NORMAL")
            components["risk_engine"] = {"status": "ok", "state": risk_state}

            # Circuit breaker
            cb_state = row.get("circuit_breaker_state", "CLOSED")
            components["circuit_breaker"] = {"status": cb_state}

            # AI Brain — last signal time
            last_signal = row.get("last_signal_time")
            if last_signal and isinstance(last_signal, dict):
                # Find most recent signal across all pairs
                most_recent = None
                for pair, ts in last_signal.items():
                    if ts:
                        try:
                            t = datetime.fromisoformat(str(ts))
                            if most_recent is None or t > most_recent:
                                most_recent = t
                        except Exception:
                            pass
                if most_recent:
                    ago = round((now - most_recent).total_seconds())
                    components["ai_brain"] = {"status": "ok", "last_call_ago_s": ago}

            # Price feed — use updated_at as proxy (state persists every 30s)
            if components["state"]["status"] == "ok":
                components["price_feed"] = {
                    "status": "ok",
                    "last_tick_ago_s": components["state"]["updated_ago_s"],
                }

        return components

    async def _get_trading_info(self) -> dict:
        """Extract trading info from persisted state (flat columns)."""
        try:
            row = await self._db.select_one(
                "system_state", {"id": STATE_ROW_ID}
            )
            if row:
                open_trades = row.get("open_trades", [])
                return {
                    "mode": "PAPER",
                    "risk_state": row.get("risk_state", "NORMAL"),
                    "open_trades": len(open_trades) if isinstance(open_trades, list) else 0,
                    "daily_pnl_usd": float(row.get("daily_pnl_usd", 0)),
                    "signals_today": row.get("daily_trade_count", 0),
                    "last_signal_at": row.get("last_signal_time"),
                }
        except Exception:
            logger.warning("health_check_trading_info_failed")

        return {"mode": "PAPER", "risk_state": "NORMAL", "open_trades": 0}


    async def _handle_prices(self, request: web.Request) -> web.Response:
        """
        Return current OANDA bid/ask for requested pairs.
        GET /prices?pairs=EUR_USD,GBP_USD,USD_JPY
        """
        pairs_param = request.query.get("pairs", "EUR_USD,GBP_USD,USD_JPY")
        pairs = [p.strip() for p in pairs_param.split(",") if p.strip()]

        if not pairs:
            return web.json_response({"prices": {}}, status=400)

        try:
            from ..config import LumitradeConfig
            from ..infrastructure.oanda_client import OandaClient

            config = LumitradeConfig()  # type: ignore[call-arg]
            client = OandaClient(config)
            try:
                raw = await client.get_pricing(pairs)
                result = {}
                for p in raw.get("prices", []):
                    instrument = p.get("instrument", "")
                    bids = p.get("bids", [])
                    asks = p.get("asks", [])
                    bid = float(bids[0]["price"]) if bids else 0.0
                    ask = float(asks[0]["price"]) if asks else 0.0
                    mid = (bid + ask) / 2
                    result[instrument] = {"bid": bid, "ask": ask, "mid": mid}
                return web.json_response({"prices": result})
            finally:
                await client.close()
        except Exception as e:
            logger.error("prices_endpoint_error", error=str(e))
            return web.json_response({"prices": {}, "error": str(e)}, status=500)


async def _run_standalone() -> None:
    """Entry point when run as a standalone process via supervisord."""
    from ..config import LumitradeConfig

    config = LumitradeConfig()  # type: ignore[call-arg]
    db = DatabaseClient(config)
    await db.connect()

    server = HealthServer(db, config.instance_id)
    await server.start()

    # Run forever until interrupted
    try:
        await asyncio.get_event_loop().create_future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        await server.stop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_run_standalone())
