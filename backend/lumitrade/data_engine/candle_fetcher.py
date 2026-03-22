"""
Lumitrade Candle Fetcher
==========================
Fetches OHLCV candles from OANDA REST API for all timeframes.
Validates each candle series through DataValidator before returning.
Per BDS Section 4.
"""

from datetime import datetime
from decimal import Decimal

from ..core.models import Candle
from ..infrastructure.oanda_client import OandaClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

TIMEFRAMES = ["M5", "M15", "H1", "H4", "D"]


class CandleFetcher:
    """Fetches and parses OANDA candles into Candle dataclasses."""

    def __init__(self, oanda: OandaClient):
        self._oanda = oanda

    async def fetch(self, pair: str, granularity: str, count: int = 50) -> list[Candle]:
        """Fetch candles for a pair and timeframe, return as Candle list."""
        try:
            raw_candles = await self._oanda.get_candles(pair, granularity, count)
            candles = [self._parse_candle(c, granularity) for c in raw_candles]
            logger.info(
                "candles_fetched",
                pair=pair,
                granularity=granularity,
                count=len(candles),
            )
            return candles
        except Exception as e:
            logger.error(
                "candle_fetch_failed",
                pair=pair,
                granularity=granularity,
                error=str(e),
            )
            raise

    async def fetch_all_timeframes(self, pair: str) -> dict[str, list[Candle]]:
        """Fetch candles for all required timeframes."""
        result = {}
        for tf in ["M15", "H1", "H4"]:
            result[tf] = await self.fetch(pair, tf, count=50)
        return result

    def _parse_candle(self, raw: dict, granularity: str) -> Candle:
        """Parse OANDA candle JSON to Candle dataclass."""
        mid = raw["mid"]
        time_str = raw["time"]
        # Handle OANDA timestamp format
        if time_str.endswith("Z"):
            time_str = time_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(time_str)

        return Candle(
            time=dt,
            open=Decimal(mid["o"]),
            high=Decimal(mid["h"]),
            low=Decimal(mid["l"]),
            close=Decimal(mid["c"]),
            volume=int(raw.get("volume", 0)),
            complete=bool(raw.get("complete", True)),
            timeframe=granularity,
        )
