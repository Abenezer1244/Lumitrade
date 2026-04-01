"""
Lumitrade Capital.com Client
===============================
Trading client for Capital.com REST API. Used for instruments not
available on OANDA (e.g., XAU/USD gold on forex-only accounts).
Implements BrokerInterface for seamless integration.

Session tokens auto-refresh every 9 minutes (expire at 10).
"""

import asyncio
import ssl
import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from ..config import LumitradeConfig
from .broker_interface import BrokerInterface
from .secure_logger import get_logger

logger = get_logger(__name__)

# Capital.com base URLs
DEMO_BASE = "https://demo-api-capital.backend-capital.com/api/v1"
LIVE_BASE = "https://api-capital.backend-capital.com/api/v1"

# Map OANDA instrument names to Capital.com epics
INSTRUMENT_MAP = {
    "XAU_USD": "GOLD",
}

# Reverse map
EPIC_TO_PAIR = {v: k for k, v in INSTRUMENT_MAP.items()}

SESSION_REFRESH_SECONDS = 540  # Refresh every 9 min (tokens expire at 10)


class CapitalComClient(BrokerInterface):
    """Capital.com REST API client for gold/metals trading."""

    def __init__(self, config: LumitradeConfig):
        self._config = config
        self._api_key = config.capital_api_key
        self._identifier = config.capital_identifier
        self._password = config.capital_password
        self._base_url = DEMO_BASE if config.trading_mode == "PAPER" else LIVE_BASE
        self._cst: str = ""
        self._security_token: str = ""
        self._session_created_at: float = 0
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=2.0),
            verify=True,
        )

    async def _ensure_session(self) -> None:
        """Create or refresh session if needed."""
        now = time.time()
        if self._cst and (now - self._session_created_at) < SESSION_REFRESH_SECONDS:
            return
        await self._create_session()

    async def _create_session(self) -> None:
        """Authenticate and get session tokens."""
        url = f"{self._base_url}/session"
        resp = await self._client.post(
            url,
            headers={"X-CAP-API-KEY": self._api_key},
            json={
                "identifier": self._identifier,
                "password": self._password,
                "encryptedPassword": False,
            },
        )
        resp.raise_for_status()
        self._cst = resp.headers.get("CST", "")
        self._security_token = resp.headers.get("X-SECURITY-TOKEN", "")
        self._session_created_at = time.time()
        logger.info("capital_session_created")

    def _auth_headers(self) -> dict:
        """Return authentication headers for API calls."""
        return {
            "CST": self._cst,
            "X-SECURITY-TOKEN": self._security_token,
            "Content-Type": "application/json",
        }

    def _to_epic(self, pair: str) -> str:
        """Convert OANDA pair name to Capital.com epic."""
        return INSTRUMENT_MAP.get(pair, pair)

    async def get_candles(
        self, pair: str, granularity: str, count: int = 50
    ) -> list[dict]:
        """Fetch historical candles from Capital.com."""
        await self._ensure_session()
        epic = self._to_epic(pair)

        # Map OANDA granularity to Capital.com resolution
        resolution_map = {
            "M5": "MINUTE_5",
            "M15": "MINUTE_15",
            "H1": "HOUR",
            "H4": "HOUR_4",
            "D": "DAY",
        }
        resolution = resolution_map.get(granularity, "HOUR")

        resp = await self._client.get(
            f"{self._base_url}/prices/{epic}",
            headers=self._auth_headers(),
            params={"resolution": resolution, "max": count},
        )
        resp.raise_for_status()
        data = resp.json()

        # Convert Capital.com format to OANDA-compatible format
        candles = []
        for price in data.get("prices", []):
            bid = price.get("closePrice", {})
            ask = price.get("closePrice", {})
            candles.append({
                "time": price.get("snapshotTime", ""),
                "mid": {
                    "o": str(bid.get("open", 0)),
                    "h": str(bid.get("high", 0)),
                    "l": str(bid.get("low", 0)),
                    "c": str(bid.get("close", 0)),
                },
                "volume": price.get("lastTradedVolume", 0),
                "complete": True,
            })
        return candles

    async def get_pricing(self, pairs: list[str]) -> dict:
        """Get current bid/ask prices."""
        await self._ensure_session()
        prices = []
        for pair in pairs:
            epic = self._to_epic(pair)
            try:
                resp = await self._client.get(
                    f"{self._base_url}/markets/{epic}",
                    headers=self._auth_headers(),
                )
                resp.raise_for_status()
                market = resp.json()
                snapshot = market.get("snapshot", {})
                prices.append({
                    "instrument": pair,
                    "bids": [{"price": str(snapshot.get("bid", 0))}],
                    "asks": [{"price": str(snapshot.get("offer", 0))}],
                })
            except Exception as e:
                logger.warning("capital_pricing_failed", pair=pair, error=str(e))
        return {"prices": prices}

    async def get_account_summary(self) -> dict:
        """Fetch account balance and equity."""
        await self._ensure_session()
        resp = await self._client.get(
            f"{self._base_url}/accounts",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        accounts = resp.json().get("accounts", [])
        if accounts:
            acc = accounts[0]
            balance = acc.get("balance", {})
            return {
                "balance": str(balance.get("balance", 0)),
                "unrealizedPL": str(balance.get("profitLoss", 0)),
                "NAV": str(balance.get("balance", 0)),
            }
        return {"balance": "0", "unrealizedPL": "0", "NAV": "0"}

    async def get_open_trades(self) -> list[dict]:
        """Fetch all open positions."""
        await self._ensure_session()
        resp = await self._client.get(
            f"{self._base_url}/positions",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        positions = resp.json().get("positions", [])

        # Convert to OANDA-compatible format
        trades = []
        for pos in positions:
            position = pos.get("position", {})
            market = pos.get("market", {})
            epic = market.get("epic", "")
            pair = EPIC_TO_PAIR.get(epic, epic)
            trades.append({
                "id": position.get("dealId", ""),
                "instrument": pair,
                "currentUnits": str(position.get("size", 0)),
                "price": str(position.get("level", 0)),
                "unrealizedPL": str(position.get("upl", 0)),
                "direction": position.get("direction", "BUY"),
            })
        return trades

    async def place_market_order(
        self,
        pair: str,
        units: int,
        sl: Decimal,
        tp: Decimal,
        client_request_id: str,
    ) -> dict:
        """Place a market order on Capital.com."""
        await self._ensure_session()
        epic = self._to_epic(pair)
        direction = "SELL" if units < 0 else "BUY"
        size = abs(units)

        # Capital.com uses fractional sizes for gold (1 unit = 1 oz)
        body = {
            "epic": epic,
            "direction": direction,
            "size": size,
            "orderType": "MARKET",
            "stopLoss": {"level": float(sl)},
            "takeProfit": {"level": float(tp)},
        }

        logger.info(
            "capital_placing_order",
            epic=epic, pair=pair, direction=direction,
            size=size, sl=str(sl), tp=str(tp),
        )

        resp = await self._client.post(
            f"{self._base_url}/positions",
            headers=self._auth_headers(),
            json=body,
        )

        if resp.status_code >= 400:
            logger.error(
                "capital_order_error",
                status=resp.status_code,
                body=resp.text[:500],
                pair=pair,
            )
        resp.raise_for_status()
        result = resp.json()

        # Confirm the deal
        deal_ref = result.get("dealReference", "")
        if deal_ref:
            await asyncio.sleep(0.5)  # Brief wait for confirmation
            confirm = await self._confirm_deal(deal_ref)
            result["confirmation"] = confirm

        return self._to_oanda_format(result, pair, direction, size, sl, tp)

    async def _confirm_deal(self, deal_reference: str) -> dict:
        """Confirm deal execution."""
        try:
            resp = await self._client.get(
                f"{self._base_url}/confirms/{deal_reference}",
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("capital_confirm_failed", deal_ref=deal_reference, error=str(e))
            return {}

    def _to_oanda_format(
        self, result: dict, pair: str, direction: str, size: int,
        sl: Decimal, tp: Decimal,
    ) -> dict:
        """Convert Capital.com response to OANDA-compatible format."""
        confirm = result.get("confirmation", {})
        deal_id = confirm.get("dealId", result.get("dealReference", ""))
        level = confirm.get("level", 0)
        status = confirm.get("dealStatus", "")

        if status == "REJECTED":
            reason = confirm.get("reason", "UNKNOWN")
            return {
                "orderCancelTransaction": {
                    "reason": reason,
                    "rejectReason": reason,
                },
            }

        return {
            "orderCreateTransaction": {
                "id": deal_id,
                "instrument": pair,
                "units": str(size if direction == "BUY" else -size),
            },
            "orderFillTransaction": {
                "id": deal_id,
                "instrument": pair,
                "units": str(size if direction == "BUY" else -size),
                "price": str(level),
                "tradeOpened": {
                    "tradeID": deal_id,
                    "units": str(size if direction == "BUY" else -size),
                },
            },
        }

    async def close_trade(self, broker_trade_id: str) -> dict:
        """Close a position by deal ID."""
        await self._ensure_session()
        resp = await self._client.delete(
            f"{self._base_url}/positions/{broker_trade_id}",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def modify_trade(
        self, broker_trade_id: str, sl: Decimal, tp: Decimal
    ) -> dict:
        """Modify SL/TP on an existing position."""
        await self._ensure_session()
        body = {
            "stopLoss": {"level": float(sl)},
            "takeProfit": {"level": float(tp)},
        }
        resp = await self._client.put(
            f"{self._base_url}/positions/{broker_trade_id}",
            headers=self._auth_headers(),
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_trade(self, trade_id: str) -> dict:
        """Get a specific position by deal ID."""
        await self._ensure_session()
        resp = await self._client.get(
            f"{self._base_url}/positions/{trade_id}",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        position = data.get("position", {})
        return {
            "id": position.get("dealId", trade_id),
            "state": "OPEN",
            "currentUnits": str(position.get("size", 0)),
            "averageClosePrice": "0",
            "realizedPL": "0",
        }

    async def stream_prices(self, pairs: list[str]):
        """Price streaming not implemented — uses REST polling instead."""
        # Capital.com uses WebSocket for streaming which requires
        # a different connection model. For now, the REST fallback
        # in data_engine handles pricing via get_pricing().
        while True:
            await asyncio.sleep(3600)
            yield ""

    async def search_markets(self, term: str) -> list[dict]:
        """Search for market instruments by name."""
        await self._ensure_session()
        resp = await self._client.get(
            f"{self._base_url}/markets",
            headers=self._auth_headers(),
            params={"searchTerm": term},
        )
        resp.raise_for_status()
        return resp.json().get("markets", [])

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
