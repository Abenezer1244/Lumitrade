"""
Lumitrade Market-Data Router
==============================
Per-pair MARKET-DATA dispatch: crypto pairs (BTC_USD) read from Alpaca via the
read-only SpotCryptoClient; everything else reads from OANDA. Phase 1 of the
Alpaca integration (docs/ALPACA_CRYPTO_INTEGRATION.md).

SCOPE — data only. This router overrides exactly three methods:
    get_candles / get_pricing / stream_prices
Every other attribute is transparently forwarded to the OANDA client, so
account, trade-lookup, and execution semantics are byte-for-byte unchanged.

It is injected into the DataEngine (candles + REST pricing fallback + price
stream) and, as the ExecutionEngine's READ client, so BTC paper-exit pricing
(_check_paper_trade_exit / paper monitor) reroutes to Alpaca. That is still
data-only: the ExecutionEngine's trade-lookup and reconcile reads
(get_trade / get_all_open_trades_checked) are NOT overridden here, so they
forward to the real OANDA client via __getattr__ and stay OANDA-exact. LIVE
order placement uses self.oanda_trade (OANDA) directly and never this router;
StateManager and the standalone reconciler also receive the real OANDA clients.
Crypto has no order/reconcile path until P2/P3, and mixing OANDA trade-id
reconciliation with spot-crypto positions is the ghost-bug class we avoid.

Streaming: the crypto data WS lands in P3, so ``stream_prices`` streams only
OANDA pairs; BTC_USD prices ride the REST ``get_pricing`` fallback that the
DataEngine already performs when no live tick is present.
"""

import asyncio

from ..config import LumitradeConfig
from .broker_interface import BrokerInterface
from .oanda_client import OandaClient
from .secure_logger import get_logger

logger = get_logger(__name__)


class MarketDataRouter:
    """Transparent OANDA proxy that reroutes only market-data reads per pair."""

    def __init__(
        self,
        config: LumitradeConfig,
        oanda: OandaClient,
        crypto: BrokerInterface | None = None,
    ):
        self.config = config
        self._oanda = oanda
        self._crypto = crypto  # SpotCryptoClient, or None when Alpaca is off.

    def _routes_to_alpaca(self, pair: str) -> bool:
        return self._crypto is not None and self.config.uses_alpaca(pair)

    async def get_candles(
        self, pair: str, granularity: str, count: int = 50
    ) -> list[dict]:
        if self._routes_to_alpaca(pair):
            return await self._crypto.get_candles(pair, granularity, count)
        return await self._oanda.get_candles(pair, granularity, count)

    async def get_pricing(self, pairs: list[str]) -> dict:
        """Fetch pricing per venue and merge OANDA-shaped ``prices`` lists.

        Order is not significant to callers (each price carries its own
        ``instrument``), so we simply concatenate the two venues' results.
        """
        oanda_pairs = [p for p in pairs if not self._routes_to_alpaca(p)]
        crypto_pairs = [p for p in pairs if self._routes_to_alpaca(p)]
        prices: list[dict] = []
        if oanda_pairs:
            result = await self._oanda.get_pricing(oanda_pairs)
            prices.extend(result.get("prices", []))
        if crypto_pairs and self._crypto is not None:
            result = await self._crypto.get_pricing(crypto_pairs)
            prices.extend(result.get("prices", []))
        return {"prices": prices}

    async def stream_prices(self, pairs: list[str]):
        """Stream only OANDA pairs. Crypto rides REST pricing (no WS until P3)."""
        oanda_pairs = [p for p in pairs if not self._routes_to_alpaca(p)]
        if oanda_pairs:
            async for line in self._oanda.stream_prices(oanda_pairs):
                yield line
            return
        # No OANDA pairs to stream (e.g. a crypto-only universe): idle instead
        # of opening an empty-instrument OANDA stream (which 400s and would
        # thrash the reconnect/REST-fallback loop). Crypto prices are served by
        # the DataEngine's REST get_pricing fallback.
        while True:
            await asyncio.sleep(3600)
        yield  # pragma: no cover  (unreachable; keeps this an async generator)

    async def close(self) -> None:
        await self._oanda.close()
        if self._crypto is not None:
            await self._crypto.close()

    def __getattr__(self, name: str):
        """Forward any non-data attribute/method to the OANDA client.

        Guarded against recursion during ``__init__`` (before ``_oanda`` is set)
        by reading from ``__dict__`` directly.
        """
        oanda = self.__dict__.get("_oanda")
        if oanda is None:
            raise AttributeError(name)
        return getattr(oanda, name)
