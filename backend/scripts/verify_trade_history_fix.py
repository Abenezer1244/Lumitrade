"""Verify Bug 3 fix: _get_trade_history shows both directions for USD_CAD,
with lifetime aggregates and no 'No history' on the BUY side.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lumitrade.config import LumitradeConfig
from lumitrade.infrastructure.db import DatabaseClient
from lumitrade.ai_brain.prompt_builder import PromptBuilder


async def main() -> None:
    config = LumitradeConfig()
    db = DatabaseClient(config)
    await db.connect()

    builder = PromptBuilder(db=db, account_id=config.account_uuid)
    history = await builder._get_trade_history("USD_CAD")
    print("=== _get_trade_history('USD_CAD') output ===")
    print(history)
    print()

    # Assertions
    assert "BUY" in history, "BUY section missing"
    assert "SELL" in history, "SELL section missing"
    assert "No history" not in history, (
        "Should never say 'No history' when data exists — Bug 3 regressed"
    )
    # USD_CAD has 16 BUY trades at 68.8% WR historically, so this should appear
    assert "BUY (lifetime)" in history, "BUY lifetime aggregate missing"
    assert "SELL (lifetime)" in history, "SELL lifetime aggregate missing"
    # USD_CAD BUY total P&L is +$3,284 per audit → should NOT trigger WARNING
    assert "WARNING: BUY on USD_CAD" not in history, (
        "False-negative WARNING on a profitable direction"
    )
    print("PASS: both directions shown with lifetime aggregates; no 'No history'; "
          "no false WARNING on profitable BUY.")


if __name__ == "__main__":
    asyncio.run(main())
