"""Live verification: lesson_filter against the freshly rebuilt rules.

Confirms:
  - USD_CAD SELL LONDON → NOT blocked, boosted by SELL:USD_CAD:LONDON
  - USD_CAD BUY LONDON → NOT blocked, boosted by BUY:USD_CAD:LONDON
  - GBP_USD BUY NY → BLOCKED (specific BLOCK exists)
  - GBP_USD SELL LONDON → BLOCKED (*:GBP_USD:* wildcard BLOCK)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lumitrade.ai_brain.lesson_filter import LessonFilter
from lumitrade.config import LumitradeConfig
from lumitrade.infrastructure.db import DatabaseClient


async def main() -> None:
    config = LumitradeConfig()
    # Local .env has a test OANDA account; the rules we just rebuilt belong
    # to the production account. Override account_uuid on the config so the
    # live check hits the real rows.
    from unittest.mock import patch

    prod_account_uuid = "7a281498-2f2e-5ecc-8583-70118edeff28"
    # cached_property: override via __dict__ bypasses the lazy compute.
    object.__setattr__(config, "__dict__", {**config.__dict__, "account_uuid": prod_account_uuid})

    db = DatabaseClient(config)
    await db.connect()

    lf = LessonFilter(db, config)

    cases = [
        ("USD_CAD", "SELL", "LONDON", False, "SELL:USD_CAD:LONDON"),
        ("USD_CAD", "BUY", "LONDON", False, "BUY:USD_CAD:LONDON"),
        ("USD_CAD", "SELL", "NY", False, None),  # no specific rule, allowed
        ("GBP_USD", "BUY", "NY", True, None),
        ("GBP_USD", "SELL", "LONDON", True, None),
        ("EUR_USD", "BUY", "ASIAN", False, "BUY:EUR_USD:ASIAN"),  # BOOST > BLOCK
        ("EUR_USD", "SELL", "NY", True, None),  # only *:EUR_USD:* BLOCK matches
    ]

    all_pass = True
    for pair, direction, session, want_blocked, expect_boost in cases:
        blocked, boosts = await lf.check(pair, direction, session)
        ok = blocked == want_blocked
        boost_ok = expect_boost is None or any(expect_boost in b for b in boosts)
        status = "PASS" if ok and boost_ok else "FAIL"
        if not (ok and boost_ok):
            all_pass = False
        print(
            f"  [{status}] {pair:<8} {direction:<4} {session:<6}  "
            f"blocked={blocked}  boosts={len(boosts)}  "
            f"want_blocked={want_blocked}  expect_boost={expect_boost}"
        )

    print()
    if all_pass:
        print("PASS: lesson_filter wired correctly against rebuilt rules.")
    else:
        print("FAIL: lesson_filter behavior does not match expected.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
