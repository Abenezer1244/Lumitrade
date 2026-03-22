"""
Lumitrade OANDA Client
========================
Read-only client (DATA key) + Trading client (TRADING key).
OandaTradingClient is ONLY instantiated by ExecutionEngine.
TLS verification always enabled. Circuit breaker wraps all calls.
Per BDS Section 4.1 + SS Section 5.1.
"""

import ssl
from decimal import Decimal

import httpx

from ..config import LumitradeConfig
from .broker_interface import BrokerInterface
from .secure_logger import get_logger

logger = get_logger(__name__)


def _create_secure_client(
    api_key: str, timeout: float = 10.0
) -> httpx.AsyncClient:
    """
    Create an HTTPX client with TLS verification enforced.
    Per SS Section 5.1. NEVER set verify=False.
    """
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    ssl_ctx.check_hostname = True

    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(
            connect=5.0,
            read=timeout,
            write=5.0,
            pool=2.0,
        ),
        verify=ssl_ctx,
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        ),
    )


class OandaClient(BrokerInterface):
    """Read-only OANDA client. Uses DATA key only."""

    def __init__(self, config: LumitradeConfig):
        self.config = config
        self._base_url = config.oanda_base_url
        self._stream_url = config.oanda_stream_url
        self._account_id = config.oanda_account_id
        self._client = _create_secure_client(config.oanda_api_key_data)

    async def get_candles(
        self, pair: str, granularity: str, count: int = 50
    ) -> list[dict]:
        """Fetch OHLCV candles from OANDA REST API."""
        url = f"{self._base_url}/v3/instruments/{pair}/candles"
        params = {"granularity": granularity, "count": count, "price": "M"}
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()["candles"]
        except httpx.HTTPStatusError as e:
            logger.error(
                "oanda_candle_fetch_failed",
                pair=pair,
                granularity=granularity,
                status=e.response.status_code,
            )
            raise

    async def get_pricing(self, pairs: list[str]) -> dict:
        """Get current bid/ask for one or more pairs."""
        url = f"{self._base_url}/v3/accounts/{self._account_id}/pricing"
        params = {"instruments": ",".join(pairs)}
        resp = await self._client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_account_summary(self) -> dict:
        """Fetch account balance, equity, margin."""
        url = f"{self._base_url}/v3/accounts/{self._account_id}/summary"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()["account"]

    async def get_open_trades(self) -> list[dict]:
        """Fetch all currently open trades."""
        url = f"{self._base_url}/v3/accounts/{self._account_id}/openTrades"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()["trades"]

    async def place_market_order(
        self,
        pair: str,
        units: int,
        sl: Decimal,
        tp: Decimal,
        client_request_id: str,
    ) -> dict:
        """Not available on read-only client."""
        raise NotImplementedError(
            "OandaClient is read-only. Use OandaTradingClient for orders."
        )

    async def close_trade(self, broker_trade_id: str) -> dict:
        """Not available on read-only client."""
        raise NotImplementedError(
            "OandaClient is read-only. Use OandaTradingClient for closing."
        )

    async def stream_prices(self, pairs: list[str]):
        """Async generator yielding real-time price ticks."""
        url = (
            f"{self._stream_url}/v3/accounts/{self._account_id}/pricing/stream"
        )
        params = {"instruments": ",".join(pairs)}
        async with httpx.AsyncClient(
            timeout=None,
            verify=True,
            headers={
                "Authorization": f"Bearer {self.config.oanda_api_key_data}",
                "Content-Type": "application/json",
            },
        ) as client:
            async with client.stream(
                "GET", url, params=params
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.strip():
                        yield line

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


class OandaTradingClient(OandaClient):
    """
    Trading-capable OANDA client. Uses TRADING key.
    ONLY instantiated by ExecutionEngine. Never import elsewhere.
    """

    def __init__(self, config: LumitradeConfig):
        super().__init__(config)
        self._trading_client = _create_secure_client(
            config.oanda_api_key_trading, timeout=15.0
        )

    async def place_market_order(
        self,
        pair: str,
        units: int,
        sl: Decimal,
        tp: Decimal,
        client_request_id: str,
    ) -> dict:
        """Place market order with attached SL and TP."""
        url = f"{self._base_url}/v3/accounts/{self._account_id}/orders"
        body = {
            "order": {
                "type": "MARKET",
                "instrument": pair,
                "units": str(units),
                "stopLossOnFill": {"price": str(sl)},
                "takeProfitOnFill": {"price": str(tp)},
                "clientExtensions": {"id": client_request_id},
            }
        }
        resp = await self._trading_client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()

    async def close_trade(self, broker_trade_id: str) -> dict:
        """Close a specific trade by OANDA trade ID."""
        url = (
            f"{self._base_url}/v3/accounts/{self._account_id}"
            f"/trades/{broker_trade_id}/close"
        )
        resp = await self._trading_client.put(url, json={"units": "ALL"})
        resp.raise_for_status()
        return resp.json()

    async def modify_trade(
        self, broker_trade_id: str, sl: Decimal, tp: Decimal
    ) -> dict:
        """Modify SL/TP on an existing open trade."""
        url = (
            f"{self._base_url}/v3/accounts/{self._account_id}"
            f"/trades/{broker_trade_id}/orders"
        )
        body = {
            "stopLoss": {"price": str(sl)},
            "takeProfit": {"price": str(tp)},
        }
        resp = await self._trading_client.put(url, json=body)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close both HTTP clients."""
        await self._client.aclose()
        await self._trading_client.aclose()
