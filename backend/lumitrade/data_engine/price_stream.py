"""
Lumitrade Price Stream Manager
=================================
Connects to OANDA streaming API. Yields PriceTick objects.
Auto-reconnects on disconnect. Falls back to REST polling if stream fails 3 times.
Per BDS Section 4 and SAS Section 3.2.2.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

from ..core.models import PriceTick
from ..infrastructure.oanda_client import OandaClient
from ..infrastructure.secure_logger import get_logger
from ..utils.time_utils import parse_iso_utc

logger = get_logger(__name__)

MAX_STREAM_FAILURES = 3
REST_POLL_INTERVAL_SECONDS = 5


class PriceStreamManager:
    """Manages real-time price feed with streaming and REST fallback."""

    def __init__(self, oanda: OandaClient):
        self._oanda = oanda
        self._stream_failures = 0
        self._using_rest_fallback = False
        self._latest_ticks: dict[str, PriceTick] = {}

    @property
    def latest_tick(self) -> dict[str, PriceTick]:
        """Most recent tick per pair."""
        return self._latest_ticks

    async def stream(self, pairs: list[str]):
        """
        Primary streaming loop. Yields PriceTick objects.
        Switches to REST polling after MAX_STREAM_FAILURES.
        """
        while True:
            if self._using_rest_fallback:
                async for tick in self._rest_poll_loop(pairs):
                    yield tick
            else:
                try:
                    async for tick in self._stream_loop(pairs):
                        yield tick
                except Exception as e:
                    self._stream_failures += 1
                    logger.error(
                        "price_stream_disconnected",
                        error=str(e),
                        failures=self._stream_failures,
                    )
                    if self._stream_failures >= MAX_STREAM_FAILURES:
                        self._using_rest_fallback = True
                        logger.warning(
                            "price_stream_switching_to_rest_fallback",
                            failures=self._stream_failures,
                        )
                    else:
                        await asyncio.sleep(2 ** self._stream_failures)

    async def _stream_loop(self, pairs: list[str]):
        """Connect to OANDA streaming API and yield ticks."""
        async for line in self._oanda.stream_prices(pairs):
            try:
                data = json.loads(line)
                if data.get("type") == "PRICE":
                    tick = self._parse_price(data)
                    if tick:
                        self._latest_ticks[tick.pair] = tick
                        self._stream_failures = 0  # Reset on success
                        yield tick
            except json.JSONDecodeError:
                continue

    async def _rest_poll_loop(self, pairs: list[str]):
        """Fallback: poll OANDA REST API every 5 seconds."""
        while self._using_rest_fallback:
            try:
                pricing = await self._oanda.get_pricing(pairs)
                for price in pricing.get("prices", []):
                    tick = self._parse_rest_price(price)
                    if tick:
                        self._latest_ticks[tick.pair] = tick
                        yield tick
            except Exception as e:
                logger.error("rest_poll_failed", error=str(e))
            await asyncio.sleep(REST_POLL_INTERVAL_SECONDS)

    def _parse_price(self, data: dict) -> PriceTick | None:
        """Parse streaming price data to PriceTick."""
        try:
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            if not bids or not asks:
                return None
            ts = parse_iso_utc(data["time"])
            if ts is None:
                # Preserve original ValueError surface for malformed timestamps.
                ts = datetime.fromisoformat(data["time"])
            return PriceTick(
                pair=data["instrument"],
                bid=Decimal(bids[0]["price"]),
                ask=Decimal(asks[0]["price"]),
                timestamp=ts,
            )
        except (KeyError, ValueError) as e:
            logger.warning("price_parse_failed", error=str(e))
            return None

    def _parse_rest_price(self, data: dict) -> PriceTick | None:
        """Parse REST pricing response to PriceTick."""
        try:
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            if not bids or not asks:
                return None
            ts = parse_iso_utc(data.get("time", "")) or datetime.now(timezone.utc)
            return PriceTick(
                pair=data["instrument"],
                bid=Decimal(bids[0]["price"]),
                ask=Decimal(asks[0]["price"]),
                timestamp=ts,
            )
        except (KeyError, ValueError) as e:
            logger.warning("rest_price_parse_failed", error=str(e))
            return None
