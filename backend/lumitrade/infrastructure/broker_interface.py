"""
Lumitrade Broker Interface
============================
Abstract base class for all broker integrations.
OandaClient implements this. Future brokers (Coinbase, Alpaca, Tastytrade)
will implement the same interface.
Per SAS v2.0 Section 14.6.
"""

from abc import ABC, abstractmethod
from decimal import Decimal


class BrokerInterface(ABC):
    """Abstract broker interface. All brokers must implement these methods."""

    @abstractmethod
    async def get_candles(
        self, pair: str, granularity: str, count: int = 50
    ) -> list[dict]:
        ...

    @abstractmethod
    async def get_pricing(self, pairs: list[str]) -> dict:
        ...

    @abstractmethod
    async def get_account_summary(self) -> dict:
        ...

    @abstractmethod
    async def get_open_trades(self) -> list[dict]:
        ...

    @abstractmethod
    async def place_market_order(
        self,
        pair: str,
        units: int,
        sl: Decimal,
        tp: Decimal,
        client_request_id: str,
    ) -> dict:
        ...

    @abstractmethod
    async def close_trade(self, broker_trade_id: str) -> dict:
        ...

    @abstractmethod
    async def stream_prices(self, pairs: list[str]):
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
