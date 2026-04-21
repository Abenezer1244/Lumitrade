"""Backfill attribution fields on historical closed trades.

For trades with missing/UNKNOWN exit_reason, zero pnl_pips, empty session,
or null duration_minutes, compute the best-effort values using the same
rules the engine now applies on close:

  - exit_reason: OANDA fill reason if available, else TRAILING_STOP for
    wins / SL_HIT for losses / UNKNOWN for breakeven
  - pnl_pips   : from entry/exit/direction
  - session    : from opened_at hour (ASIAN/LONDON/NY/OTHER)
  - duration_minutes: from closed_at - opened_at

Read-only against OANDA (only fetches trade metadata), only UPDATEs DB rows.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import create_client

from lumitrade.utils.pip_math import pips_between
from lumitrade.utils.time_utils import session_label_for_lesson

SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ACCOUNT_ID = "7a281498-2f2e-5ecc-8583-70118edeff28"


def parse_dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None


def main() -> None:
    sb = create_client(SB_URL, SB_KEY)
    trades = (
        sb.table("trades")
        .select("*")
        .eq("account_id", ACCOUNT_ID)
        .eq("status", "CLOSED")
        .execute()
        .data
        or []
    )
    print(f"Scanning {len(trades)} closed trades for missing attribution...")

    updates_made = 0
    for t in trades:
        patch: dict = {}

        # session
        if not t.get("session"):
            opened_dt = parse_dt(t.get("opened_at"))
            if opened_dt:
                patch["session"] = session_label_for_lesson(opened_dt)

        # duration_minutes
        if t.get("duration_minutes") in (None, 0):
            o = parse_dt(t.get("opened_at"))
            c = parse_dt(t.get("closed_at"))
            if o and c:
                dm = int((c - o).total_seconds() // 60)
                if dm >= 0:
                    patch["duration_minutes"] = dm

        # pnl_pips (skip if already non-zero OR if entry/exit not present)
        try:
            pnl_pips_current = Decimal(str(t.get("pnl_pips") or 0))
        except Exception:
            pnl_pips_current = Decimal("0")
        if pnl_pips_current == 0:
            entry = t.get("entry_price")
            exit_p = t.get("exit_price")
            pair = t.get("pair") or ""
            direction = (t.get("direction") or "").upper()
            if entry and exit_p and pair and direction:
                try:
                    e = Decimal(str(entry))
                    x = Decimal(str(exit_p))
                    raw = pips_between(e, x, pair)
                    if direction == "BUY":
                        pips_val = raw if x >= e else -raw
                    elif direction == "SELL":
                        pips_val = raw if x <= e else -raw
                    else:
                        pips_val = raw
                    if pips_val != 0:
                        patch["pnl_pips"] = str(pips_val)
                except Exception:
                    pass

        # exit_reason — infer for UNKNOWN rows
        if (t.get("exit_reason") or "").upper() == "UNKNOWN":
            outcome = t.get("outcome")
            if outcome == "WIN":
                patch["exit_reason"] = "TRAILING_STOP"
            elif outcome == "LOSS":
                patch["exit_reason"] = "SL_HIT"

        if not patch:
            continue

        # Try the full patch first. If the exit_reason constraint hasn't
        # been migrated yet (014_trailing_stop_exit_reason.sql), retry
        # without exit_reason so the other fields still land.
        try:
            sb.table("trades").update(patch).eq("id", t["id"]).execute()
            updates_made += 1
        except Exception as e:
            msg = str(e)
            if "exit_reason_check" in msg or "check constraint" in msg.lower():
                fallback = {k: v for k, v in patch.items() if k != "exit_reason"}
                if fallback:
                    try:
                        sb.table("trades").update(fallback).eq("id", t["id"]).execute()
                        updates_made += 1
                    except Exception as e2:
                        print(f"  SKIP {t['id'][:8]}: {e2}")
            else:
                print(f"  SKIP {t['id'][:8]}: {msg[:150]}")

    print(f"Patched {updates_made} trades")

    # Summary verification
    after = (
        sb.table("trades")
        .select("exit_reason,session,pnl_pips,duration_minutes")
        .eq("account_id", ACCOUNT_ID)
        .eq("status", "CLOSED")
        .execute()
        .data
        or []
    )

    from collections import Counter

    exit_reasons = Counter(t.get("exit_reason") or "NONE" for t in after)
    sessions = Counter(t.get("session") or "NONE" for t in after)
    missing_pips = sum(1 for t in after if not t.get("pnl_pips") or float(t.get("pnl_pips") or 0) == 0)
    missing_dur = sum(1 for t in after if t.get("duration_minutes") in (None, 0))

    print()
    print(f"Exit reason distribution: {dict(exit_reasons)}")
    print(f"Session distribution:     {dict(sessions)}")
    print(f"Trades still missing pnl_pips:       {missing_pips}/{len(after)}")
    print(f"Trades still missing duration_minutes: {missing_dur}/{len(after)}")


if __name__ == "__main__":
    main()
