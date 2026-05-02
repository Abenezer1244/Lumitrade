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

import hmac
import os
from datetime import datetime, timezone
from typing import Any, TypedDict

from aiohttp import web

from ..config import LumitradeConfig
from ..infrastructure.db import DatabaseClient
from ..infrastructure.oanda_client import OandaClient, OandaTradingClient
from ..infrastructure.secure_logger import get_logger


class ComponentHealth(TypedDict, total=False):
    """Per-component health entry returned by `_check_components()`.

    `status` is required (e.g. "ok", "error", "stale", "held",
    "not_held", "offline", "CLOSED"). The remaining metric fields are
    populated only when the corresponding measurement succeeded.
    """

    status: str
    latency_ms: float
    updated_ago_s: int
    last_call_ago_s: int
    last_tick_ago_s: int
    state: str


class TradingInfo(TypedDict, total=False):
    """Trading-state snapshot embedded in the /health response."""

    mode: str
    risk_state: str
    open_trades: int
    daily_pnl_usd: float
    signals_today: int


class HealthResponse(TypedDict):
    """JSON contract returned by `GET /health`.

    The dashboard `/api/system/health` proxy depends on this shape.
    `system_state_read_error=True` flips `status` to "degraded" so the
    endpoint never claims "ok" while blind to the singleton state row.
    """

    status: str
    instance_id: str
    timestamp: str
    uptime_seconds: float
    system_state_read_error: bool
    components: dict[str, Any]
    trading: dict[str, Any]

logger = get_logger(__name__)

HEALTH_PORT = int(os.environ.get("PORT", 8000))
STATE_STALENESS_THRESHOLD_SECONDS = 120
STATE_ROW_ID = "singleton"

# Read at module load — empty string means ALL requests are rejected (fail closed)
INTERNAL_API_SECRET = os.environ.get("INTERNAL_API_SECRET", "")

# Endpoints that do NOT require authentication (read-only monitoring)
_PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("GET", "/"),
    ("GET", "/prices"),
    ("GET", "/candles"),
    ("GET", "/calendar"),
    ("GET", "/ws/prices"),
}


@web.middleware
async def _auth_middleware(request: web.Request, handler):
    """
    Bearer-token auth middleware.
    Public read-only monitoring routes are allowed without credentials.
    All other routes require:  Authorization: Bearer <INTERNAL_API_SECRET>
    Fail closed: if INTERNAL_API_SECRET is not set, every request is rejected.
    """
    # request.path strips query strings, so /ws/prices?pair=X matches correctly
    path_only = request.path

    is_public = (request.method, path_only) in _PUBLIC_ROUTES

    if not is_public:
        if not INTERNAL_API_SECRET:
            logger.warning(
                "auth_rejected_no_secret_configured",
                method=request.method,
                path=path_only,
                remote=request.remote,
            )
            return web.json_response(
                {"error": "Unauthorized"},
                status=401,
            )

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()

        if not hmac.compare_digest(token, INTERNAL_API_SECRET):
            logger.warning(
                "auth_rejected_invalid_token",
                method=request.method,
                path=path_only,
                remote=request.remote,
            )
            return web.json_response(
                {"error": "Unauthorized"},
                status=401,
            )

    return await handler(request)


class HealthServer:
    """
    Lightweight HTTP health check server.
    Reads system_state from DB to report engine health.
    """

    def __init__(
        self,
        db: DatabaseClient,
        instance_id: str,
        config: LumitradeConfig | None = None,
    ) -> None:
        self._db = db
        self._instance_id = instance_id
        self._started_at = datetime.now(timezone.utc)
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        # Cached LumitradeConfig — injected if provided, else created lazily
        # on first use. Construction reads env vars (cheap), but caching
        # avoids re-parsing on every request.
        self._config: LumitradeConfig | None = config

    def _get_config(self) -> LumitradeConfig:
        """Return cached LumitradeConfig, instantiating on first use.

        Replaces the previous per-handler `from ..config import LumitradeConfig;
        config = LumitradeConfig()` pattern (27 sites). Safe to memoize because
        env vars do not change at runtime.
        """
        if self._config is None:
            self._config = LumitradeConfig()  # type: ignore[call-arg]
        return self._config

    async def start(self) -> None:
        """Start the health check HTTP server on HEALTH_PORT."""
        self._app = web.Application(middlewares=[_auth_middleware])
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/prices", self._handle_prices)
        self._app.router.add_get("/settings", self._handle_get_settings)
        self._app.router.add_post("/settings", self._handle_post_settings)
        self._app.router.add_post("/onboarding", self._handle_onboarding)
        self._app.router.add_post("/reconcile", self._handle_reconcile)
        self._app.router.add_get("/account", self._handle_account)
        self._app.router.add_post("/fix-breakeven", self._handle_fix_breakeven)
        self._app.router.add_post("/fix-timestamps", self._handle_fix_timestamps)
        self._app.router.add_post("/purge-ghosts", self._handle_purge_ghosts)
        self._app.router.add_get("/trade/{trade_id}", self._handle_get_trade)
        self._app.router.add_get("/oanda-trades", self._handle_oanda_trades)
        self._app.router.add_post("/trade/{trade_id}/close", self._handle_close_trade)
        # Kill switch (per PRD:579). Authenticated; the engine main loop
        # detects the False->True transition in system_state and closes
        # all open OANDA positions on its next tick.
        self._app.router.add_post("/kill-switch", self._handle_kill_switch_activate)
        self._app.router.add_delete("/kill-switch", self._handle_kill_switch_deactivate)
        self._app.router.add_get("/kill-switch", self._handle_kill_switch_status)
        self._app.router.add_get("/candles", self._handle_candles)
        self._app.router.add_get("/ws/prices", self._handle_ws_prices)
        self._app.router.add_get("/calendar", self._handle_calendar)
        self._app.router.add_get("/preflight", self._handle_preflight)
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

    async def _handle_preflight(self, request: web.Request) -> web.Response:
        """Pre-market demo-readiness check. Aggregates the 5 operational
        risks identified in the 2026-04-27 audit so an operator can
        confirm \"will the engine actually trade today\" with one HTTP call.

        Auth: required (admin-private). Returns 200 with `ready=true|false`
        plus per-check booleans and the actual values for debugging.
        """
        config = self._get_config()

        # 1. env TRADING_MODE
        env_mode = config.trading_mode
        env_mode_live = env_mode == "LIVE"

        # 2. dashboard mode toggle (db_mode_override source of truth)
        db_dashboard_mode: str = "unknown"
        settings_row_present = False
        try:
            row = await self._db.select_one(
                "system_state", {"id": self.SETTINGS_ROW_ID}
            )
            if row and isinstance(row.get("open_trades"), dict):
                settings_row_present = True
                db_dashboard_mode = row["open_trades"].get("mode", "PAPER")
            else:
                db_dashboard_mode = "missing_or_malformed"
        except Exception as e:
            db_dashboard_mode = f"fetch_failed: {type(e).__name__}"

        db_mode_live = db_dashboard_mode == "LIVE"

        # 3. effective mode (the gate the execution engine actually uses).
        # Demo-week hard lock wins over both switches.
        force_paper_mode = bool(getattr(config, "force_paper_mode", False))
        if force_paper_mode:
            effective_mode = "PAPER"
        else:
            effective_mode = "LIVE" if (env_mode_live and db_mode_live) else "PAPER"

        # 4. OANDA reachability + balance
        oanda_reachable = False
        oanda_balance: float | None = None
        oanda_error: str | None = None
        try:
            oanda = OandaClient(config)
            try:
                acct = await oanda.get_account_summary_for_pairs(config.pairs)
                oanda_reachable = True
                try:
                    oanda_balance = float(acct.get("balance", 0))
                except (TypeError, ValueError):
                    oanda_balance = None
            finally:
                await oanda.close()
        except Exception as e:
            oanda_error = f"{type(e).__name__}: {str(e)[:120]}"

        balance_sufficient = (
            oanda_balance is not None and oanda_balance >= 1200.0
        )

        # 5. kill switch
        kill_switch_off = True
        try:
            kr = await self._db.select_one(
                "system_state", {"id": STATE_ROW_ID}
            )
            if kr and bool(kr.get("kill_switch_active", False)):
                kill_switch_off = False
        except Exception:
            kill_switch_off = False

        # Composite: ready when every box is checked. Demo can run in
        # PAPER mode (PaperExecutor) too — `ready_for_live_demo` only
        # gates the LIVE-on-practice path. When `force_paper_mode` is on,
        # live can never be ready by design — that is the lockdown's job.
        ready_for_live_demo = (
            not force_paper_mode
            and env_mode_live
            and db_mode_live
            and settings_row_present
            and oanda_reachable
            and balance_sufficient
            and kill_switch_off
        )
        ready_for_paper_demo = (
            oanda_reachable and balance_sufficient and kill_switch_off
        )

        body = {
            "ready_for_live_demo": ready_for_live_demo,
            "ready_for_paper_demo": ready_for_paper_demo,
            "effective_mode": effective_mode,
            "force_paper_mode": force_paper_mode,
            "checks": {
                "force_paper_mode_lockdown": force_paper_mode,
                "env_mode_is_LIVE": env_mode_live,
                "dashboard_mode_is_LIVE": db_mode_live,
                "settings_row_present": settings_row_present,
                "oanda_reachable": oanda_reachable,
                "balance_sufficient_for_forex_min": balance_sufficient,
                "kill_switch_off": kill_switch_off,
            },
            "values": {
                "env_trading_mode": env_mode,
                "db_dashboard_mode": db_dashboard_mode,
                "force_paper_mode": force_paper_mode,
                "oanda_environment": config.oanda_environment,
                "oanda_account_id": config.oanda_account_id,
                "oanda_balance": oanda_balance,
                "oanda_error": oanda_error,
                "pairs": config.pairs,
                "live_pairs": config.live_pairs,
                "min_forex_units": 1000,
                "max_confidence_ceiling": float(config.max_confidence),
                "min_confidence_floor": float(config.min_confidence),
                "session_window_utc": "08-17 USD_CAD, 00-17 USD_JPY",
            },
        }
        # Always 200 — preflight is informational, not a liveness probe.
        return web.json_response(body)

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

        # Pull the system_state read flag out of components so it does
        # not skew the per-component "is this status ok?" tally below.
        system_state_read_error = bool(components.pop("system_state_read_error", False))

        # Determine overall status — healthy if DB is ok (other components may still be starting)
        db_status = components.get("database", {})
        db_ok = (db_status.get("status") if isinstance(db_status, dict) else db_status) == "ok"

        # Count how many critical components are ok
        ok_count = sum(
            1 for v in components.values()
            if (v.get("status") if isinstance(v, dict) else v) in ("ok", "held", "CLOSED")
        )
        total = len(components)

        # Healthy if DB is up AND the singleton system_state row was readable.
        # Without that row, every other component below DB defaults to "ok"
        # despite the server being blind, so a successful DB ping alone is
        # not enough to claim health.
        is_healthy = db_ok and not system_state_read_error
        if not db_ok:
            status = "down"
        elif system_state_read_error or ok_count != total:
            status = "degraded"
        else:
            status = "healthy"
        http_status = 200 if is_healthy else 503

        body: HealthResponse = {
            "status": status,
            "instance_id": self._instance_id,
            "timestamp": now.isoformat(),
            "uptime_seconds": round(uptime, 1),
            "system_state_read_error": system_state_read_error,
            "components": components,
            "trading": trading_info,
        }

        return web.json_response(body, status=http_status)

    async def _check_components(self, now: datetime) -> dict[str, Any]:
        """Check health of individual components with real latency.

        Each entry in the returned dict matches `ComponentHealth` (status
        plus optional metric fields). The reserved
        `system_state_read_error` key is a bool, not a `ComponentHealth`,
        and is popped by the caller before iteration.
        """
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
        # Tracks whether the singleton system_state read succeeded. When
        # it fails, every downstream component below stays at its default
        # (often "ok"/"NORMAL") despite the server being blind to real
        # state. Surfaced on the response so /health does not silently
        # claim "ok" while the state row is unreadable.
        system_state_read_error = False

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
            system_state_read_error = True
            logger.warning(
                "health_server_system_state_read_failed",
                exc_info=True,
            )

        components["system_state_read_error"] = system_state_read_error

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

    async def _get_trading_info(self) -> dict[str, Any]:
        """Extract trading info from persisted state (flat columns).

        Returned dict matches `TradingInfo`.
        """
        try:
            row = await self._db.select_one(
                "system_state", {"id": STATE_ROW_ID}
            )
            if row:
                open_trades = row.get("open_trades", [])

                # Compute effective mode: LIVE only when env AND dashboard
                # both LIVE — UNLESS force_paper_mode lockdown is active,
                # in which case we always report PAPER so dashboards can't
                # render a misleading LIVE badge during demo week
                # (Codex review finding #3).
                effective_mode = "PAPER"
                try:
                    config = self._get_config()
                    if bool(getattr(config, "force_paper_mode", False)):
                        effective_mode = "PAPER"
                    else:
                        env_mode = config.trading_mode
                        settings_row = await self._db.select_one(
                            "system_state", {"id": self.SETTINGS_ROW_ID}
                        )
                        db_mode = "PAPER"
                        stored_settings = (
                            settings_row.get("open_trades")
                            if settings_row else None
                        )
                        if isinstance(stored_settings, dict):
                            db_mode = stored_settings.get("mode", "PAPER")
                        effective_mode = (
                            "LIVE"
                            if (env_mode == "LIVE" and db_mode == "LIVE")
                            else "PAPER"
                        )
                except Exception:
                    pass

                return {
                    "mode": effective_mode,
                    "risk_state": row.get("risk_state", "NORMAL"),
                    "open_trades": len(open_trades) if isinstance(open_trades, list) else 0,
                    "daily_pnl_usd": float(row.get("daily_pnl_usd", 0)),
                    "signals_today": row.get("daily_trade_count", 0),
                    "last_signal_at": row.get("last_signal_time"),
                }
        except Exception:
            logger.warning("health_check_trading_info_failed")

        return {"mode": "PAPER", "risk_state": "NORMAL", "open_trades": 0}


    # ── Settings Endpoints ──────────────────────────────────────

    # User-adjustable settings (stored in Supabase system_state id='settings')
    SETTINGS_ROW_ID = "settings"

    def _get_settings_defaults(self) -> dict:
        """Derive defaults from config — always in sync, never hardcoded."""
        try:
            config = self._get_config()
            return {
                "riskPct": float(config.max_risk_pct) * 100,
                "maxPositions": config.max_open_trades,
                "maxPerPair": config.max_positions_per_pair,
                "confidence": int(config.min_confidence * 100),
                "scanInterval": config.signal_interval_minutes,
                "mode": config.trading_mode,
            }
        except Exception:
            return {
                "riskPct": 0.5, "maxPositions": 5, "maxPerPair": 5,
                "confidence": 70, "scanInterval": 15, "mode": "PAPER",
            }

    @property
    def SETTINGS_DEFAULTS(self) -> dict:
        return self._get_settings_defaults()
    # Guardrails — read-only, set via env vars only
    GUARDRAILS = {
        "maxPositionUnits": 500_000,
        "dailyLossLimitPct": 5.0,
        "weeklyLossLimitPct": 10.0,
    }

    async def _handle_get_settings(self, request: web.Request) -> web.Response:
        """GET /settings — return user settings + guardrails + effective mode.

        Includes:
          - mode: what the dashboard last saved (PAPER / LIVE)
          - env_mode: TRADING_MODE env var (Railway-controlled)
          - effective_mode: what the engine ACTUALLY uses for execution
                            (LIVE iff env_mode==LIVE AND mode==LIVE)
        """
        try:
            row = await self._db.select_one(
                "system_state", {"id": self.SETTINGS_ROW_ID}
            )
            if row and row.get("open_trades"):
                stored = row["open_trades"]
                user_settings = stored if isinstance(stored, dict) else dict(self.SETTINGS_DEFAULTS)
            else:
                user_settings = dict(self.SETTINGS_DEFAULTS)
        except Exception:
            user_settings = dict(self.SETTINGS_DEFAULTS)

        # Merge guardrails + dual-switch mode visibility from config
        try:
            config = self._get_config()
            guardrails = {
                "maxPositionUnits": config.max_position_units,
                "dailyLossLimitPct": float(config.daily_loss_limit_pct) * 100,
                "weeklyLossLimitPct": float(config.weekly_loss_limit_pct) * 100,
            }
            env_mode = config.trading_mode
            db_mode = user_settings.get("mode", "PAPER")
            force_paper_mode = bool(getattr(config, "force_paper_mode", False))
            if force_paper_mode:
                effective_mode = "PAPER"
            else:
                effective_mode = (
                    "LIVE" if (env_mode == "LIVE" and db_mode == "LIVE") else "PAPER"
                )
        except Exception:
            guardrails = dict(self.GUARDRAILS)
            env_mode = "PAPER"
            effective_mode = "PAPER"
            force_paper_mode = False

        return web.json_response({
            **user_settings,
            "guardrails": guardrails,
            "env_mode": env_mode,
            "effective_mode": effective_mode,
            "force_paper_mode": force_paper_mode,
        })

    async def _handle_post_settings(self, request: web.Request) -> web.Response:
        """POST /settings — save user-adjustable settings."""
        import json
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # Demo-week lockdown: reject any attempt to persist mode=LIVE
        # while FORCE_PAPER_MODE is on. Without this, a stale LIVE could
        # be written into the settings row and reactivate the moment the
        # lockdown is lifted (Codex review finding #2).
        force_paper_mode_active = False
        try:
            force_paper_mode_active = bool(self._get_config().force_paper_mode)
        except Exception:
            pass

        requested_mode = body.get("mode")
        if force_paper_mode_active:
            persisted_mode = "PAPER"
        elif requested_mode in ("PAPER", "LIVE"):
            persisted_mode = requested_mode
        else:
            persisted_mode = "PAPER"

        # Validate and clamp values
        clamped = {
            "riskPct": max(0.25, min(2.0, float(body.get("riskPct", 0.5)))),
            "maxPositions": max(1, min(100, int(body.get("maxPositions", 5)))),
            "maxPerPair": max(1, min(10, int(body.get("maxPerPair", 5)))),
            "confidence": max(50, min(90, int(body.get("confidence", 70)))),
            "scanInterval": max(5, min(60, int(body.get("scanInterval", 15)))),
            "mode": persisted_mode,
        }

        try:
            await self._db.upsert("system_state", {
                "id": self.SETTINGS_ROW_ID,
                "open_trades": clamped,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info("settings_saved", settings=clamped)
        except Exception as e:
            logger.error("settings_save_failed", error=str(e))
            return web.json_response({"error": "Failed to save"}, status=500)

        return web.json_response(clamped)

    async def _handle_onboarding(self, request: web.Request) -> web.Response:
        """POST /onboarding — conversational onboarding via SA-05."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = body.get("message", "")
        account_id = body.get("account_id", "default")

        if not message:
            return web.json_response({"error": "Missing 'message'"}, status=400)

        try:
            from ..subagents.onboarding_agent import OnboardingAgent

            config = self._get_config()
            agent = OnboardingAgent(config, self._db)
            result = await agent.run({
                "user_message": message,
                "account_id": account_id,
            })
            return web.json_response(result)
        except Exception as e:
            logger.error("onboarding_endpoint_error", error=str(e))
            return web.json_response(
                {"response": "Onboarding service encountered an error.", "completed": False},
                status=500,
            )

    async def _handle_account(self, request: web.Request) -> web.Response:
        """
        GET /account — return real OANDA account summary.
        Returns aggregate balance/equity/margin/unrealizedPL plus a per-account
        breakdown (forex primary + spot crypto sub-account).
        """
        try:
            config = self._get_config()
            oanda = OandaClient(config)
            try:
                # Aggregate across all accounts
                acct = await oanda.get_account_summary_for_pairs(config.pairs)
                balance = float(acct.get("balance", 0))
                equity = float(acct.get("NAV", acct.get("equity", balance)))
                margin_used = float(acct.get("marginUsed", 0))
                unrealized_pnl = float(acct.get("unrealizedPL", 0))
                open_trade_count = int(acct.get("openTradeCount", 0))

                # Forex (primary) account
                forex_acct = await oanda.get_account_summary()
                forex_balance = float(forex_acct.get("balance", 0))
                forex_equity = float(forex_acct.get("NAV", forex_acct.get("equity", forex_balance)))
                forex_unrealized = float(forex_acct.get("unrealizedPL", 0))
                forex_open = int(forex_acct.get("openTradeCount", 0))

                # Spot crypto sub-account (PAXOS — V20 may return 400; show zeros if unavailable)
                crypto_balance = 0.0
                crypto_equity = 0.0
                crypto_unrealized = 0.0
                crypto_open = 0
                spot_id = getattr(config, "oanda_spot_crypto_account_id", None)
                if spot_id and spot_id != config.oanda_account_id:
                    try:
                        crypto_acct = await oanda.get_account_summary_for("BTC_USD")
                        crypto_balance = float(crypto_acct.get("balance", 0))
                        crypto_equity = float(crypto_acct.get("NAV", crypto_acct.get("equity", crypto_balance)))
                        crypto_unrealized = float(crypto_acct.get("unrealizedPL", 0))
                        crypto_open = int(crypto_acct.get("openTradeCount", 0))
                    except Exception:
                        pass  # PAXOS account not accessible via V20; zeros are correct

                return web.json_response({
                    "balance": round(balance, 2),
                    "equity": round(equity, 2),
                    "margin_used": round(margin_used, 2),
                    "margin_available": round(balance - margin_used, 2),
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "open_trade_count": open_trade_count,
                    "accounts": {
                        "forex": {
                            "balance": round(forex_balance, 2),
                            "equity": round(forex_equity, 2),
                            "unrealized_pnl": round(forex_unrealized, 2),
                            "open_trade_count": forex_open,
                        },
                        "crypto": {
                            "balance": round(crypto_balance, 2),
                            "equity": round(crypto_equity, 2),
                            "unrealized_pnl": round(crypto_unrealized, 2),
                            "open_trade_count": crypto_open,
                        },
                    },
                })
            finally:
                await oanda.close()
        except Exception as e:
            logger.error("account_endpoint_error", error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_get_trade(self, request: web.Request) -> web.Response:
        """GET /trade/{trade_id} — fetch a specific trade from OANDA."""
        trade_id = request.match_info.get("trade_id", "")
        if not trade_id:
            return web.json_response({"error": "Missing trade_id"}, status=400)
        try:
            config = self._get_config()
            oanda = OandaClient(config)
            try:
                pair = request.query.get("pair", "")
                if not pair:
                    try:
                        trade_row = await self._db.select_one(
                            "trades", {"broker_trade_id": trade_id}
                        )
                        if trade_row:
                            pair = trade_row.get("pair", "") or ""
                    except Exception as _db_err:
                        logger.warning(
                            "trade_lookup_pair_lookup_failed",
                            trade_id=trade_id,
                            error=str(_db_err),
                        )
                trade = await oanda.get_trade(trade_id, pair=pair)
                return web.json_response(trade)
            finally:
                await oanda.close()
        except Exception as e:
            logger.error("trade_lookup_error", trade_id=trade_id, error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_oanda_trades(self, request: web.Request) -> web.Response:
        """GET /oanda-trades — return all open trades from OANDA with per-trade P&L."""
        try:
            config = self._get_config()
            oanda = OandaClient(config)
            try:
                trades = await oanda.get_all_open_trades()
                return web.json_response({"trades": trades})
            finally:
                await oanda.close()
        except Exception as e:
            logger.error("oanda_trades_error", error=str(e))
            return web.json_response({"trades": []})

    async def _handle_kill_switch_status(self, request: web.Request) -> web.Response:
        """GET /kill-switch — return current kill-switch flag state."""
        try:
            row = await self._db.select_one("system_state", {"id": STATE_ROW_ID})
            active = bool((row or {}).get("kill_switch_active", False))
            return web.json_response({"active": active})
        except Exception as e:
            logger.error("kill_switch_status_error", error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_kill_switch_activate(self, request: web.Request) -> web.Response:
        """
        POST /kill-switch — activate kill switch.

        Per PRD:579. Sets kill_switch_active=True on the singleton state
        row. The engine main loop detects the False->True transition on
        its next tick and closes every open OANDA position via
        ExecutionEngine.close_all_positions().

        Authenticated route (private). Operator-initiated only.
        """
        try:
            body: dict = {}
            try:
                body = await request.json()
            except Exception:
                body = {}
            reason = (body.get("reason") or "").strip() or "operator_invoked"

            await self._db.upsert("system_state", {
                "id": STATE_ROW_ID,
                "kill_switch_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.critical(
                "kill_switch_activated_via_api",
                reason=reason,
                remote=request.remote,
            )
            return web.json_response({
                "active": True,
                "reason": reason,
                "note": "Engine will close all open positions on next signal-loop tick.",
            })
        except Exception as e:
            logger.error("kill_switch_activate_error", error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_kill_switch_deactivate(self, request: web.Request) -> web.Response:
        """
        DELETE /kill-switch — clear the kill switch flag (operator-initiated).

        Does NOT reopen any closed positions; just allows the engine to resume
        scanning. Authenticated route.
        """
        try:
            await self._db.upsert("system_state", {
                "id": STATE_ROW_ID,
                "kill_switch_active": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.warning(
                "kill_switch_deactivated_via_api",
                remote=request.remote,
            )
            return web.json_response({"active": False})
        except Exception as e:
            logger.error("kill_switch_deactivate_error", error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_close_trade(self, request: web.Request) -> web.Response:
        """POST /trade/{trade_id}/close — close a specific trade on OANDA."""
        trade_id = request.match_info.get("trade_id", "")
        if not trade_id:
            return web.json_response({"error": "Missing trade_id"}, status=400)
        try:
            config = self._get_config()

            # Resolve the pair from DB so we route to the correct OANDA account.
            # BTC_USD trades live on the spot crypto sub-account; without the pair
            # close_trade() defaults to the main forex account and fails silently.
            pair = ""
            try:
                trade_row = await self._db.select_one(
                    "trades", {"broker_trade_id": trade_id}
                )
                if trade_row:
                    pair = trade_row.get("pair", "") or ""
            except Exception as _db_err:
                logger.warning(
                    "close_trade_pair_lookup_failed",
                    trade_id=trade_id,
                    error=str(_db_err),
                )

            client = OandaTradingClient(config)
            try:
                result = await client.close_trade(trade_id, pair=pair)
                return web.json_response(result)
            finally:
                await client.close()
        except Exception as e:
            logger.error("trade_close_error", trade_id=trade_id, error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_reconcile(self, request: web.Request) -> web.Response:
        """POST /reconcile — trigger position reconciliation on demand."""
        try:
            from ..infrastructure.alert_service import AlertService
            from ..state.reconciler import PositionReconciler

            config = self._get_config()
            oanda = OandaClient(config)
            try:
                alerts = AlertService(config, self._db)
                reconciler = PositionReconciler(
                    self._db, oanda, alerts,
                    account_uuid=config.account_uuid,
                )
                result = await reconciler.reconcile()

                # Sync system_state.open_trades with reconciliation result
                matched_ids = [
                    m.get("broker_trade_id") for m in result.get("matched", [])
                ]
                await self._db.upsert("system_state", {
                    "id": STATE_ROW_ID,
                    "open_trades": matched_ids,
                })

                logger.info(
                    "manual_reconciliation_complete",
                    ghosts=len(result.get("ghosts", [])),
                    phantoms=len(result.get("phantoms", [])),
                    matched=len(result.get("matched", [])),
                )
                return web.json_response(result)
            finally:
                await oanda.close()
        except Exception as e:
            logger.error("reconcile_endpoint_error", error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_fix_breakeven(self, request: web.Request) -> web.Response:
        """POST /fix-breakeven — retroactively fix BREAKEVEN trades with real OANDA P&L."""
        try:
            from ..utils.pip_math import pips_between, pip_size as get_pip_size

            config = self._get_config()
            oanda = OandaClient(config)

            # Find all CLOSED trades with BREAKEVEN outcome FOR THIS ACCOUNT.
            # Account-scoped: without this filter, the endpoint would
            # rewrite another tenant's closed trade history.
            breakeven_trades = await self._db.select(
                "trades",
                {"status": "CLOSED", "outcome": "BREAKEVEN",
                 "account_id": config.account_uuid},
            )

            fixed = []
            errors = []
            try:
                for trade in breakeven_trades:
                    broker_id = trade.get("broker_trade_id", "")
                    if not broker_id:
                        continue
                    try:
                        pair = trade.get("pair", "")
                        oanda_trade = await oanda.get_trade(broker_id, pair=pair)
                        close_price = oanda_trade.get("averageClosePrice")
                        real_pl = oanda_trade.get("realizedPL")
                        if not close_price or not real_pl:
                            continue

                        from decimal import Decimal
                        exit_price = Decimal(str(close_price))
                        realized_pnl = Decimal(str(real_pl))
                        entry = Decimal(str(trade.get("entry_price", "0")))
                        pair = trade.get("pair", "")
                        direction = trade.get("direction", "BUY")

                        pnl_pips = pips_between(entry, exit_price, pair)
                        if direction == "BUY":
                            pnl_pips = pnl_pips if exit_price > entry else -pnl_pips
                        else:
                            pnl_pips = pnl_pips if exit_price < entry else -pnl_pips

                        outcome = "WIN" if realized_pnl > 0 else ("LOSS" if realized_pnl < 0 else "BREAKEVEN")

                        sl = Decimal(str(trade.get("stop_loss", "0")))
                        tp = Decimal(str(trade.get("take_profit", "0")))
                        ps = get_pip_size(pair)
                        sl_dist = abs(exit_price - sl)
                        tp_dist = abs(exit_price - tp)
                        exit_reason = "SL_HIT" if sl_dist < tp_dist else "TP_HIT"

                        update_fields: dict = {
                                "exit_price": str(exit_price),
                                "pnl_pips": str(pnl_pips),
                                "pnl_usd": str(realized_pnl),
                                "outcome": outcome,
                                "exit_reason": exit_reason,
                        }
                        # Also fix closed_at from OANDA if available
                        close_time = oanda_trade.get("closeTime")
                        if close_time:
                            update_fields["closed_at"] = close_time

                        await self._db.update(
                            "trades",
                            {"id": trade["id"]},
                            update_fields,
                        )
                        fixed.append({
                            "trade_id": trade["id"],
                            "pair": pair,
                            "outcome": outcome,
                            "pnl_usd": str(realized_pnl),
                        })
                    except Exception as e:
                        logger.error("fix_breakeven_trade_error", broker_id=broker_id, error=str(e))
                        errors.append({"broker_id": broker_id, "error": "Processing failed"})
            finally:
                await oanda.close()

            return web.json_response({
                "total_breakeven": len(breakeven_trades),
                "fixed": len(fixed),
                "errors": len(errors),
                "details": fixed,
                "error_details": errors,
            })
        except Exception as e:
            logger.error("fix_breakeven_error", error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_purge_ghosts(self, request: web.Request) -> web.Response:
        """POST /purge-ghosts — remove BREAKEVEN trades with no broker_trade_id (never executed).
        Account-scoped because this endpoint hard-deletes rows by id;
        an unscoped query could destroy another tenant's history."""
        try:
            config = self._get_config()
            # Find all CLOSED BREAKEVEN trades FOR THIS ACCOUNT
            breakeven_trades = await self._db.select(
                "trades",
                {"status": "CLOSED", "outcome": "BREAKEVEN",
                 "account_id": config.account_uuid},
            )

            # Filter to those with no broker_trade_id or empty broker_trade_id
            ghosts = [
                t for t in breakeven_trades
                if not t.get("broker_trade_id") or t["broker_trade_id"].strip() == ""
            ]

            deleted = []
            for ghost in ghosts:
                try:
                    await self._db.delete("trades", {"id": ghost["id"]})
                    deleted.append({
                        "trade_id": ghost["id"],
                        "pair": ghost.get("pair"),
                        "opened_at": ghost.get("opened_at"),
                    })
                except Exception as e:
                    logger.error("purge_ghost_failed", trade_id=ghost["id"], error=str(e))

            logger.info(
                "ghost_purge_complete",
                total_breakeven=len(breakeven_trades),
                ghosts_found=len(ghosts),
                deleted=len(deleted),
            )

            return web.json_response({
                "total_breakeven": len(breakeven_trades),
                "ghosts_without_broker_id": len(ghosts),
                "deleted": len(deleted),
                "details": deleted,
            })
        except Exception as e:
            logger.error("purge_ghosts_error", error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_fix_timestamps(self, request: web.Request) -> web.Response:
        """POST /fix-timestamps — correct closed_at on all closed trades using OANDA closeTime."""
        try:
            config = self._get_config()
            oanda = OandaClient(config)

            # Account-scoped because this endpoint rewrites closed_at on
            # every row it touches.
            closed_trades = await self._db.select(
                "trades",
                {"status": "CLOSED", "account_id": config.account_uuid},
            )
            fixed = []
            errors = []
            try:
                for trade in closed_trades:
                    broker_id = trade.get("broker_trade_id", "")
                    if not broker_id:
                        continue
                    try:
                        pair = trade.get("pair", "")
                        oanda_trade = await oanda.get_trade(broker_id, pair=pair)
                        close_time = oanda_trade.get("closeTime")
                        if close_time and close_time != trade.get("closed_at"):
                            await self._db.update(
                                "trades",
                                {"id": trade["id"]},
                                {"closed_at": close_time},
                            )
                            fixed.append({
                                "trade_id": trade["id"],
                                "pair": trade.get("pair"),
                                "old_closed_at": trade.get("closed_at"),
                                "new_closed_at": close_time,
                            })
                    except Exception as e:
                        logger.error("fix_timestamps_trade_error", broker_id=broker_id, error=str(e))
                        errors.append({"broker_id": broker_id, "error": "Processing failed"})
            finally:
                await oanda.close()

            return web.json_response({
                "total_closed": len(closed_trades),
                "fixed": len(fixed),
                "errors": len(errors),
                "details": fixed,
            })
        except Exception as e:
            logger.error("fix_timestamps_error", error=str(e))
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _handle_ws_prices(self, request: web.Request) -> web.WebSocketResponse:
        """
        WebSocket /ws/prices?pair=EUR_USD — stream live OANDA ticks.
        Sends JSON: {"time": epoch, "bid": float, "ask": float, "mid": float}
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        pair = request.query.get("pair", "EUR_USD")

        try:
            import httpx

            config = self._get_config()
            stream_env = "fxpractice" if config.oanda_environment != "live" else "fxtrade"
            stream_base = f"https://stream-{stream_env}.oanda.com"
            account_id = config.account_id_for(pair)
            url = f"{stream_base}/v3/accounts/{account_id}/pricing/stream?instruments={pair}"

            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "GET", url,
                    headers={"Authorization": f"Bearer {config.oanda_api_key_data}"},
                ) as response:
                    async for line in response.aiter_lines():
                        if ws.closed:
                            break
                        if not line.strip():
                            continue
                        try:
                            import json as _json
                            tick = _json.loads(line)
                            if tick.get("type") == "PRICE":
                                bids = tick.get("bids", [])
                                asks = tick.get("asks", [])
                                if bids and asks:
                                    bid = float(bids[0]["price"])
                                    ask = float(asks[0]["price"])
                                    mid = round((bid + ask) / 2, 6)
                                    ts = tick.get("time", "")
                                    # Convert ISO to epoch
                                    from datetime import datetime as _dt
                                    epoch = int(_dt.fromisoformat(
                                        ts.replace("Z", "+00:00").split(".")[0] + "+00:00"
                                    ).timestamp())
                                    await ws.send_json({
                                        "time": epoch,
                                        "bid": bid,
                                        "ask": ask,
                                        "mid": mid,
                                    })
                        except Exception:
                            continue
        except Exception as e:
            logger.error("ws_prices_error", error=str(e))
        finally:
            await ws.close()

        return ws

    async def _handle_calendar(self, request: web.Request) -> web.Response:
        """GET /calendar — fetch economic calendar from Nager.Date + Trading Economics free data."""
        import httpx
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        events = []

        try:
            # Use TradingEconomics free calendar API
            start = now.strftime("%Y-%m-%d")
            end = (now + timedelta(days=7)).strftime("%Y-%m-%d")

            async with httpx.AsyncClient(timeout=10) as client:
                # Try free economic calendar sources
                # 1. Nager.Date for public holidays (affects forex liquidity)
                try:
                    holiday_resp = await client.get(
                        f"https://date.nager.at/api/v3/NextPublicHolidays/US"
                    )
                    if holiday_resp.status_code == 200:
                        holidays = holiday_resp.json()
                        for h in holidays[:5]:
                            ts = int(datetime.strptime(h["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
                            events.append({
                                "title": h.get("localName", h.get("name", "")),
                                "currency": "USD",
                                "impact": 2,
                                "forecast": None,
                                "actual": None,
                                "previous": None,
                                "market": None,
                                "timestamp": ts,
                                "region": "americas",
                                "unit": "holiday",
                            })
                except Exception:
                    pass

                # 2. Generate known recurring high-impact events
                # These are the major forex-moving events with fixed schedules
                major_events = [
                    {"title": "FOMC Interest Rate Decision", "currency": "USD", "impact": 3, "day": 2, "hour": 18},
                    {"title": "Non-Farm Payrolls", "currency": "USD", "impact": 3, "day": 4, "hour": 12},
                    {"title": "US CPI (YoY)", "currency": "USD", "impact": 3, "day": 2, "hour": 12},
                    {"title": "ECB Interest Rate Decision", "currency": "EUR", "impact": 3, "day": 3, "hour": 12},
                    {"title": "BOE Interest Rate Decision", "currency": "GBP", "impact": 3, "day": 3, "hour": 11},
                    {"title": "BOJ Interest Rate Decision", "currency": "JPY", "impact": 3, "day": 4, "hour": 3},
                    {"title": "US Retail Sales (MoM)", "currency": "USD", "impact": 2, "day": 1, "hour": 12},
                    {"title": "US ISM Manufacturing PMI", "currency": "USD", "impact": 2, "day": 0, "hour": 14},
                    {"title": "US Jobless Claims", "currency": "USD", "impact": 2, "day": 3, "hour": 12},
                    {"title": "UK GDP (QoQ)", "currency": "GBP", "impact": 2, "day": 4, "hour": 6},
                    {"title": "Eurozone CPI (YoY)", "currency": "EUR", "impact": 2, "day": 0, "hour": 9},
                    {"title": "Australia Employment Change", "currency": "AUD", "impact": 2, "day": 3, "hour": 0},
                    {"title": "Canada Employment Change", "currency": "CAD", "impact": 2, "day": 4, "hour": 12},
                    {"title": "NZ Official Cash Rate", "currency": "NZD", "impact": 3, "day": 2, "hour": 1},
                    {"title": "Swiss CPI (MoM)", "currency": "CHF", "impact": 2, "day": 1, "hour": 6},
                ]

                # Place events in this week based on their weekday
                week_start = now - timedelta(days=now.weekday())
                for evt in major_events:
                    event_dt = week_start.replace(hour=evt["hour"], minute=30, second=0, microsecond=0) + timedelta(days=evt["day"])
                    # Only include future events or events from today
                    if event_dt > now - timedelta(hours=12):
                        events.append({
                            "title": evt["title"],
                            "currency": evt["currency"],
                            "impact": evt["impact"],
                            "forecast": None,
                            "actual": None,
                            "previous": None,
                            "market": None,
                            "timestamp": int(event_dt.timestamp()),
                            "region": "global",
                            "unit": "report",
                        })

            # Sort by timestamp ascending (soonest first)
            events.sort(key=lambda e: e.get("timestamp", 0))
            return web.json_response({"events": events[:30]})

        except Exception as e:
            logger.error("calendar_endpoint_error", error=str(e))
            return web.json_response({"events": [], "error": "Internal server error"})

    async def _handle_candles(self, request: web.Request) -> web.Response:
        """GET /candles?pair=EUR_USD&granularity=H1&count=100 — fetch OANDA candles."""
        pair = request.query.get("pair", "EUR_USD")
        granularity = request.query.get("granularity", "H1")
        count = request.query.get("count", "100")

        try:
            config = self._get_config()
            oanda = OandaClient(config)
            try:
                candles = await oanda.get_candles(pair, granularity, int(count))
                formatted = []
                for c in candles:
                    mid = c.get("mid", {})
                    formatted.append({
                        "time": int(
                            __import__("datetime").datetime.fromisoformat(
                                c["time"].replace("Z", "+00:00").split(".")[0] + "+00:00"
                            ).timestamp()
                        ),
                        "open": float(mid.get("o", 0)),
                        "high": float(mid.get("h", 0)),
                        "low": float(mid.get("l", 0)),
                        "close": float(mid.get("c", 0)),
                        "volume": c.get("volume", 0),
                    })
                return web.json_response({"candles": formatted})
            finally:
                await oanda.close()
        except Exception as e:
            logger.error("candles_endpoint_error", error=str(e))
            return web.json_response({"candles": []})

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
            config = self._get_config()
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
            return web.json_response({"prices": {}, "error": "Internal server error"}, status=500)


async def _run_standalone() -> None:
    """Entry point when run as a standalone process via supervisord."""
    config = LumitradeConfig()  # type: ignore[call-arg]
    db = DatabaseClient(config)
    await db.connect()

    server = HealthServer(db, config.instance_id, config=config)
    await server.start()

    # Run forever until interrupted
    try:
        await asyncio.get_event_loop().create_future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        await server.stop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_run_standalone())
