"""
Lumitrade IG Markets / tastyfx Client
=======================================
Async REST client for IG Markets API (tastyfx in US).
Used for XAU/USD (gold) trading alongside OANDA for forex.

Same interface pattern as OandaTradingClient — plug-in replacement
for gold instruments.

Auth: API key + session tokens (CST + X-SECURITY-TOKEN).
Session tokens expire — auto-renewed on 401.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# IG API base URLs
IG_DEMO_URL = "https://demo-api.ig.com/gateway/deal"
IG_LIVE_URL = "https://api.ig.com/gateway/deal"

# XAU/USD epic on IG
GOLD_EPIC = "CS.D.USCGC.TODAY.IP"

# IG resolution mapping
RESOLUTION_MAP = {
    "M15": "MINUTE_15",
    "H1": "HOUR",
    "H4": "HOUR_4",
    "D": "DAY",
}


class IGClient:
    """Read-only IG client for candles and account info."""

    def __init__(self, api_key: str, username: str, password: str,
                 is_demo: bool = True):
        self._api_key = api_key
        self._username = username
        self._password = password
        self._base_url = IG_DEMO_URL if is_demo else IG_LIVE_URL
        self._cst = ""
        self._xst = ""
        self._account_id = ""
        self._client = httpx.AsyncClient(timeout=15.0)
        self._session_lock = asyncio.Lock()

    async def _ensure_session(self) -> None:
        """Login if no session tokens, or refresh if expired."""
        if self._cst and self._xst:
            return
        async with self._session_lock:
            if self._cst and self._xst:
                return
            await self._login()

    async def _login(self) -> None:
        """POST /session to get CST + X-SECURITY-TOKEN."""
        url = f"{self._base_url}/session"
        headers = {
            "X-IG-API-KEY": self._api_key,
            "Content-Type": "application/json",
            "VERSION": "2",
        }
        body = {
            "identifier": self._username,
            "password": self._password,
        }
        resp = await self._client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            logger.error("ig_login_failed", status=resp.status_code,
                         body=resp.text[:500])
            raise ConnectionError(f"IG login failed: {resp.status_code}")

        self._cst = resp.headers.get("CST", "")
        self._xst = resp.headers.get("X-SECURITY-TOKEN", "")
        data = resp.json()
        self._account_id = data.get("currentAccountId", "")

        logger.info("ig_session_created", account_id=self._account_id)

    def _headers(self, version: str = "2") -> dict:
        """Build request headers with session tokens."""
        return {
            "X-IG-API-KEY": self._api_key,
            "CST": self._cst,
            "X-SECURITY-TOKEN": self._xst,
            "Content-Type": "application/json",
            "VERSION": version,
        }

    async def _request(self, method: str, path: str, version: str = "2",
                       json_body: dict | None = None,
                       extra_headers: dict | None = None) -> dict:
        """Make an authenticated request, auto-renew session on 401."""
        await self._ensure_session()

        url = f"{self._base_url}{path}"
        headers = self._headers(version)
        if extra_headers:
            headers.update(extra_headers)

        resp = await self._client.request(method, url, headers=headers,
                                           json=json_body)

        # Session expired — re-login and retry once
        if resp.status_code == 401:
            logger.info("ig_session_expired_renewing")
            self._cst = ""
            self._xst = ""
            await self._login()
            headers = self._headers(version)
            if extra_headers:
                headers.update(extra_headers)
            resp = await self._client.request(method, url, headers=headers,
                                               json=json_body)

        resp.raise_for_status()
        return resp.json()

    # ── Candles ──────────────────────────────────────────────────

    async def get_candles(self, epic: str, granularity: str,
                          count: int = 50) -> list[dict]:
        """
        Fetch OHLCV candles from IG.
        Returns list of dicts matching OANDA candle format for compatibility.
        """
        resolution = RESOLUTION_MAP.get(granularity, granularity)
        path = f"/prices/{epic}/{resolution}/{count}"
        data = await self._request("GET", path, version="2")

        candles = []
        for p in data.get("prices", []):
            bid = p.get("closePrice", {})
            candles.append({
                "time": p.get("snapshotTimeUTC", ""),
                "mid": {
                    "o": str(bid.get("bid", p.get("openPrice", {}).get("bid", 0))),
                    "h": str(p.get("highPrice", {}).get("bid", 0)),
                    "l": str(p.get("lowPrice", {}).get("bid", 0)),
                    "c": str(bid.get("bid", 0)),
                },
                "volume": p.get("lastTradedVolume", 0),
                "complete": True,
            })

        logger.info("ig_candles_fetched", epic=epic, resolution=resolution,
                     count=len(candles))
        return candles

    # ── Account ──────────────────────────────────────────────────

    async def get_account_summary(self) -> dict:
        """Get account balance, equity, margin."""
        data = await self._request("GET", "/accounts", version="1")
        accounts = data.get("accounts", [])
        if not accounts:
            return {"balance": 0, "equity": 0, "margin_used": 0,
                    "available": 0}

        # Find the preferred/active account
        acct = accounts[0]
        for a in accounts:
            if a.get("preferred"):
                acct = a
                break

        bal = acct.get("balance", {})
        return {
            "balance": float(bal.get("balance", 0)),
            "equity": float(bal.get("balance", 0)) + float(bal.get("profitLoss", 0)),
            "margin_used": float(bal.get("deposit", 0)),
            "available": float(bal.get("available", 0)),
            "unrealized_pnl": float(bal.get("profitLoss", 0)),
        }

    # ── Open Positions ───────────────────────────────────────────

    async def get_open_positions(self) -> list[dict]:
        """Get all open positions."""
        data = await self._request("GET", "/positions", version="2")
        return data.get("positions", [])

    # ── Close ────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("ig_client_closed")


class IGTradingClient(IGClient):
    """Full trading client — extends IGClient with order management."""

    async def place_market_order(
        self,
        epic: str,
        direction: str,
        size: float,
        stop_level: float | None = None,
        stop_distance: float | None = None,
        limit_level: float | None = None,
        deal_reference: str = "",
    ) -> dict:
        """
        Place a market order on IG. Returns deal confirmation.

        For gold: size is in contracts (1.0 = 1 contract = ~1 oz).
        """
        body = {
            "epic": epic,
            "direction": direction.upper(),
            "size": size,
            "orderType": "MARKET",
            "timeInForce": "FILL_OR_KILL",
            "currencyCode": "USD",
            "expiry": "DFB",
            "forceOpen": True,
            "guaranteedStop": False,
        }

        if stop_level is not None:
            body["stopLevel"] = stop_level
        elif stop_distance is not None:
            body["stopDistance"] = stop_distance

        if limit_level is not None:
            body["limitLevel"] = limit_level

        if deal_reference:
            body["dealReference"] = deal_reference

        # Place order
        data = await self._request("POST", "/positions/otc", version="2",
                                    json_body=body)
        deal_ref = data.get("dealReference", "")

        if not deal_ref:
            logger.error("ig_order_no_deal_ref", response=data)
            return data

        # Poll for confirmation (IG is async — order not confirmed immediately)
        confirm = await self._poll_deal_confirm(deal_ref)

        logger.info(
            "ig_order_placed",
            epic=epic,
            direction=direction,
            size=size,
            deal_id=confirm.get("dealId", ""),
            deal_status=confirm.get("dealStatus", ""),
            level=confirm.get("level", ""),
        )

        return confirm

    async def modify_position(self, deal_id: str, stop_level: float | None = None,
                               limit_level: float | None = None) -> dict:
        """Update SL/TP on an open position."""
        body = {}
        if stop_level is not None:
            body["stopLevel"] = stop_level
        if limit_level is not None:
            body["limitLevel"] = limit_level
        body["trailingStop"] = False
        body["guaranteedStop"] = False

        data = await self._request("PUT", f"/positions/otc/{deal_id}",
                                    version="2", json_body=body)

        logger.info("ig_position_modified", deal_id=deal_id,
                     stop_level=stop_level, limit_level=limit_level)
        return data

    async def close_position(self, deal_id: str, direction: str,
                              size: float) -> dict:
        """
        Close a position. Direction must be OPPOSITE of open direction.
        IG uses POST with _method: DELETE header (quirk).
        """
        # Opposite direction
        close_dir = "SELL" if direction.upper() == "BUY" else "BUY"

        body = {
            "dealId": deal_id,
            "direction": close_dir,
            "size": size,
            "orderType": "MARKET",
            "timeInForce": "FILL_OR_KILL",
        }

        data = await self._request(
            "POST", "/positions/otc", version="1",
            json_body=body,
            extra_headers={"_method": "DELETE"},
        )

        deal_ref = data.get("dealReference", "")
        if deal_ref:
            confirm = await self._poll_deal_confirm(deal_ref)
            logger.info("ig_position_closed", deal_id=deal_id,
                         status=confirm.get("dealStatus", ""))
            return confirm

        return data

    async def _poll_deal_confirm(self, deal_reference: str,
                                  max_attempts: int = 5) -> dict:
        """Poll GET /confirms/{dealReference} until confirmed or timeout."""
        for attempt in range(max_attempts):
            try:
                data = await self._request(
                    "GET", f"/confirms/{deal_reference}", version="1",
                )
                if data.get("dealStatus") in ("ACCEPTED", "REJECTED"):
                    return data
            except Exception:
                pass
            await asyncio.sleep(0.5 * (attempt + 1))

        logger.warning("ig_deal_confirm_timeout", deal_ref=deal_reference)
        return {"dealReference": deal_reference, "dealStatus": "UNKNOWN"}
