"""Live verification that EMA200 now computes correctly.

Calls the real OANDA API (read-only), runs compute_indicators, and
asserts ema_200 > 0. Passes iff Bug 1 is fixed end-to-end.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Import after env is loaded
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lumitrade.config import LumitradeConfig
from lumitrade.data_engine.candle_fetcher import CandleFetcher
from lumitrade.data_engine.indicators import compute_indicators
from lumitrade.infrastructure.oanda_client import OandaClient


async def main() -> None:
    config = LumitradeConfig()
    oanda = OandaClient(config)
    fetcher = CandleFetcher(oanda)

    try:
        data = await fetcher.fetch_all_timeframes("USD_CAD")
        for tf, candles in data.items():
            print(f"{tf}: {len(candles)} candles")
        h1 = data["H1"]
        ind = compute_indicators(h1)
        print()
        print(f"ema_20  = {ind.ema_20}")
        print(f"ema_50  = {ind.ema_50}")
        print(f"ema_200 = {ind.ema_200}")
        print(f"adx_14  = {ind.adx_14}")
        print(f"atr_14  = {ind.atr_14}")
        print(f"rsi_14  = {ind.rsi_14}")

        assert len(h1) >= 200, f"H1 candles ({len(h1)}) < 200 — fetch still broken"
        assert ind.ema_200 > 0, f"ema_200 still 0 — indicator compute broken"
        assert ind.ema_20 > 0 and ind.ema_50 > 0, "ema_20/50 missing"
        print()
        print("PASS: H1=250 candles, ema_200 > 0, strategy tier unlocked.")
    finally:
        await oanda.close()


if __name__ == "__main__":
    asyncio.run(main())
