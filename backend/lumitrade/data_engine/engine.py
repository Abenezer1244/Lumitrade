"""
Lumitrade Data Engine
=======================
Orchestrates all market data acquisition, validation, and indicator computation.
Assembles MarketSnapshot for each signal scan cycle.
Per BDS Section 4 and SAS Section 3.2.2.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from ..config import LumitradeConfig
from ..core.models import (
    AccountContext,
    DataQuality,
    MarketSnapshot,
    PriceTick,
    TradeSummary,
)
from ..infrastructure.db import DatabaseClient
from ..infrastructure.oanda_client import OandaClient
from ..infrastructure.secure_logger import get_logger
from ..utils.time_utils import get_current_session
from .calendar import CalendarFetcher
from .candle_fetcher import CandleFetcher
from .indicators import compute_indicators
from .price_stream import PriceStreamManager
from .regime_classifier import RegimeClassifier
from .validator import DataValidator

logger = get_logger(__name__)


class DataEngine:
    """
    Orchestrates market data acquisition and assembly.
    Produces MarketSnapshot consumed by SignalScanner.
    """

    def __init__(
        self, config: LumitradeConfig, oanda: OandaClient, db: DatabaseClient
    ):
        self.config = config
        self._oanda = oanda
        self._db = db
        self._validator = DataValidator()
        self._fetcher = CandleFetcher(oanda)
        self._stream = PriceStreamManager(oanda)
        self._calendar = CalendarFetcher(config)
        self._regime = RegimeClassifier()

    async def stream_task(self, pairs: list[str]) -> None:
        """
        Background task: stream prices for all pairs.
        Validates each tick and stores latest.
        Started by OrchestratorService.
        """
        logger.info("data_engine_stream_started", pairs=pairs)
        try:
            async for tick in self._stream.stream(pairs):
                self._validator.validate_tick(tick)
        except asyncio.CancelledError:
            logger.info("data_engine_stream_cancelled")
        except Exception as e:
            logger.error("data_engine_stream_error", error=str(e))
            raise

    async def get_snapshot(self, pair: str) -> MarketSnapshot | None:
        """
        Assemble a complete MarketSnapshot for a signal scan.
        Returns None if data quality is insufficient for trading.
        """
        try:
            return await self._build_snapshot(pair)
        except Exception as e:
            logger.error(
                "snapshot_assembly_failed", pair=pair, error=str(e)
            )
            return None

    async def _build_snapshot(self, pair: str) -> MarketSnapshot | None:
        """Build a MarketSnapshot from all data sources."""
        # 1. Get latest price tick
        latest_tick = self._stream.latest_tick.get(pair)
        if not latest_tick:
            # Fallback: fetch from REST
            try:
                pricing = await self._oanda.get_pricing([pair])
                prices = pricing.get("prices", [])
                if prices:
                    p = prices[0]
                    bids = p.get("bids", [])
                    asks = p.get("asks", [])
                    if bids and asks:
                        latest_tick = PriceTick(
                            pair=pair,
                            bid=Decimal(bids[0]["price"]),
                            ask=Decimal(asks[0]["price"]),
                            timestamp=datetime.now(timezone.utc),
                        )
            except Exception as e:
                logger.error("pricing_fetch_failed", pair=pair, error=str(e))
                return None

        if not latest_tick:
            logger.warning("no_price_data_available", pair=pair)
            return None

        # 2. Validate tick
        quality = self._validator.validate_tick(latest_tick)

        # 3. Fetch candles for all timeframes
        candle_data = await self._fetcher.fetch_all_timeframes(pair)
        candles_m15 = candle_data.get("M15", [])
        candles_h1 = candle_data.get("H1", [])
        candles_h4 = candle_data.get("H4", [])

        # 4. Validate candles
        for tf_candles in [candles_m15, candles_h1, candles_h4]:
            ohlc_ok, gaps_ok = self._validator.validate_candles(tf_candles)
            if not ohlc_ok or not gaps_ok:
                quality = DataQuality(
                    is_fresh=quality.is_fresh,
                    spike_detected=quality.spike_detected,
                    spread_acceptable=quality.spread_acceptable,
                    candles_complete=gaps_ok,
                    ohlc_valid=ohlc_ok,
                )

        # 5. Compute indicators from H1 candles (primary)
        indicators = compute_indicators(candles_h1)

        # 6. Get economic calendar events
        currencies = pair.split("_")
        news_events = await self._calendar.get_upcoming_events(currencies)

        # 7. Get account context
        account_ctx = await self._get_account_context()

        # 8. Get recent trades on this pair
        recent_trades = await self._get_recent_trades(pair)

        # 9. Classify market regime (STUB — returns UNKNOWN)
        regime = self._regime.classify(indicators, candles_h4)

        # 10. Get current session
        session = get_current_session()

        return MarketSnapshot(
            pair=pair,
            session=session,
            timestamp=datetime.now(timezone.utc),
            bid=latest_tick.bid,
            ask=latest_tick.ask,
            spread_pips=latest_tick.spread_pips,
            candles_m15=candles_m15,
            candles_h1=candles_h1,
            candles_h4=candles_h4,
            indicators=indicators,
            news_events=news_events,
            recent_trades=recent_trades,
            account_context=account_ctx,
            data_quality=quality,
            market_regime=regime,
        )

    async def _get_account_context(self) -> AccountContext:
        """Fetch current account summary from OANDA."""
        try:
            summary = await self._oanda.get_account_summary()
            return AccountContext(
                account_id=self.config.oanda_account_id,
                balance=Decimal(str(summary.get("balance", "0"))),
                equity=Decimal(str(summary.get("NAV", "0"))),
                margin_used=Decimal(str(summary.get("marginUsed", "0"))),
                open_trade_count=int(summary.get("openTradeCount", 0)),
                daily_pnl=Decimal(str(summary.get("pl", "0"))),
                fetched_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("account_context_failed", error=str(e))
            return AccountContext(
                account_id=self.config.oanda_account_id,
                balance=Decimal("0"),
                equity=Decimal("0"),
                margin_used=Decimal("0"),
                open_trade_count=0,
                daily_pnl=Decimal("0"),
                fetched_at=datetime.now(timezone.utc),
            )

    async def _get_recent_trades(
        self, pair: str, limit: int = 3
    ) -> list[TradeSummary]:
        """Get last N closed trades on this pair from DB."""
        try:
            trades = await self._db.select(
                "trades",
                {"pair": pair, "status": "CLOSED"},
                order="closed_at",
                limit=limit,
            )
            return [
                TradeSummary(
                    pair=t["pair"],
                    direction=t["direction"],
                    outcome=t.get("outcome"),
                    pnl_pips=Decimal(str(t["pnl_pips"])) if t.get("pnl_pips") else None,
                    opened_at=datetime.fromisoformat(t["opened_at"]),
                    closed_at=(
                        datetime.fromisoformat(t["closed_at"])
                        if t.get("closed_at")
                        else None
                    ),
                )
                for t in trades
            ]
        except Exception as e:
            logger.warning("recent_trades_fetch_failed", error=str(e))
            return []
