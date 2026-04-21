"""Rebuild trading_lessons from the ground up.

Deletes all existing lessons for the account, then recomputes BLOCK/BOOST/
NEUTRAL rules from the full closed-trades table at multiple granularities:

  - {DIRECTION}:{PAIR}              (e.g. SELL:USD_CAD)
  - {DIRECTION}:{PAIR}:{SESSION}    (e.g. SELL:USD_CAD:LONDON)
  - *:{PAIR}:*                      (wildcard, pair-level)
  - {DIRECTION}:*:*                 (wildcard, direction-level)

Thresholds mirror lesson_analyzer.py:
  BLOCK if win_rate < 0.35 and sample_size >= 5
  BOOST if win_rate > 0.65 and sample_size >= 5
  NEUTRAL otherwise (but only written if sample_size >= 2 to cut noise)

Use when the live extractor is stale (e.g., after a strategy pivot) so the
lesson filter and prompt injection reflect actual recent performance.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import create_client

BLOCK_WIN_RATE = Decimal("0.35")
BOOST_WIN_RATE = Decimal("0.65")
MIN_SAMPLE_SIZE = 5

SESSION_RANGES = {"ASIAN": (0, 8), "LONDON": (8, 13), "NY": (13, 21)}


def session_from_hour(hour: int) -> str:
    for name, (lo, hi) in SESSION_RANGES.items():
        if lo <= hour < hi:
            return name
    return "OTHER"


def session_for_trade(t: dict) -> str:
    opened = t.get("opened_at")
    if not opened:
        return "OTHER"
    if isinstance(opened, str):
        try:
            dt = datetime.fromisoformat(opened.replace("Z", "+00:00"))
        except Exception:
            return "OTHER"
    else:
        dt = opened
    return session_from_hour(dt.hour)


def classify(wins: int, total: int) -> str:
    if total < MIN_SAMPLE_SIZE:
        return "NEUTRAL"
    wr = Decimal(wins) / Decimal(total)
    if wr < BLOCK_WIN_RATE:
        return "BLOCK"
    if wr > BOOST_WIN_RATE:
        return "BOOST"
    return "NEUTRAL"


def main() -> None:
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    account_id = os.environ.get("ACCOUNT_UUID") or "7a281498-2f2e-5ecc-8583-70118edeff28"

    # Fetch closed trades
    trades = (
        sb.table("trades")
        .select("*")
        .eq("status", "CLOSED")
        .eq("account_id", account_id)
        .execute()
        .data
        or []
    )
    print(f"Loaded {len(trades)} closed trades for {account_id}")

    # Delete existing lessons
    sb.table("trading_lessons").delete().eq("account_id", account_id).execute()
    print("Cleared existing lessons")

    # Build buckets at multiple granularities
    buckets: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for t in trades:
        pair = t.get("pair") or ""
        direction = t.get("direction") or ""
        if not pair or not direction:
            continue
        session = session_for_trade(t)
        # Granularities (pattern_key, pair, direction, session)
        # Direction-only wildcards (e.g., "SELL:*:*") are intentionally
        # omitted — they're too broad and would suppress pair-specific
        # BOOST rules on the same direction due to BLOCK-first matching
        # in lesson_filter.
        buckets[(f"{direction}:{pair}", pair, direction, "*")].append(t)
        buckets[(f"{direction}:{pair}:{session}", pair, direction, session)].append(t)
        buckets[(f"*:{pair}:*", pair, "*", "*")].append(t)

    now_iso = datetime.now(timezone.utc).isoformat()
    rows_to_insert: list[dict] = []
    for (pattern_key, pair, direction, session), trade_list in buckets.items():
        total = len(trade_list)
        if total < 2:  # cut micro-patterns to reduce noise
            continue
        wins = sum(1 for t in trade_list if t.get("outcome") == "WIN")
        losses = sum(
            1
            for t in trade_list
            if t.get("outcome") in ("LOSS", "BREAKEVEN")
        )
        pnl = Decimal("0")
        for t in trade_list:
            try:
                pnl += Decimal(str(t.get("pnl_usd") or 0))
            except Exception:
                pass

        rule_type = classify(wins, total)
        win_rate = (Decimal(wins) / Decimal(total)).quantize(Decimal("0.0001"))
        evidence = (
            f"{wins}W/{losses}L out of {total} trades, "
            f"WR={win_rate:.1%}, P&L=${pnl:.2f}"
        )
        rows_to_insert.append(
            {
                "id": str(uuid4()),
                "account_id": account_id,
                "pattern_key": pattern_key,
                "pair": pair,
                "direction": direction,
                "session": session,
                "indicator_conditions": {},
                "rule_type": rule_type,
                "win_count": wins,
                "loss_count": losses,
                "sample_size": total,
                "win_rate": str(win_rate),
                "total_pnl": str(pnl.quantize(Decimal("0.01"))),
                "evidence": evidence,
                "created_from_trade_id": None,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    if rows_to_insert:
        sb.table("trading_lessons").insert(rows_to_insert).execute()
    print(f"Inserted {len(rows_to_insert)} fresh lessons")

    # Verify: dump top BLOCK/BOOST rules
    fresh = (
        sb.table("trading_lessons")
        .select("*")
        .eq("account_id", account_id)
        .execute()
        .data
        or []
    )
    print()
    print("=== ACTIVE BLOCK/BOOST RULES ===")
    for rule in sorted(fresh, key=lambda r: r["rule_type"]):
        if rule["rule_type"] in ("BLOCK", "BOOST"):
            print(
                f"  [{rule['rule_type']}] {rule['pattern_key']:<28} "
                f"{rule['win_count']}W/{rule['loss_count']}L "
                f"WR={rule['win_rate']}  P&L=${rule['total_pnl']}"
            )


if __name__ == "__main__":
    main()
