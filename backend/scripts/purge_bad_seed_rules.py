"""One-time cleanup: remove dangerous wildcard seed rules from trading_lessons.

Removes:
  - SELL:*:* (blocks ALL sells on all pairs — includes live USD_JPY, USD_CAD, BTC_USD)
  - *:GBP_USD:* (non-active pair)
  - *:EUR_USD:* (non-active pair)

Run once against the LIVE account after deploying the lesson_analyzer.py fix.
Safe to re-run — will report 0 deleted on a clean DB.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ACCOUNT_UUID = os.environ.get("ACCOUNT_UUID") or "7a281498-2f2e-5ecc-8583-70118edeff28"

BAD_PATTERN_KEYS = ["SELL:*:*", "*:GBP_USD:*", "*:EUR_USD:*"]

client = create_client(SUPABASE_URL, SUPABASE_KEY)

print(f"Auditing trading_lessons for account {ACCOUNT_UUID}")
print(f"Checking for dangerous pattern keys: {BAD_PATTERN_KEYS}\n")

total_deleted = 0
for pattern_key in BAD_PATTERN_KEYS:
    resp = (
        client.table("trading_lessons")
        .select("id, pattern_key, rule_type, evidence")
        .eq("account_id", ACCOUNT_UUID)
        .eq("pattern_key", pattern_key)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        print(f"  {pattern_key}: NOT FOUND (clean)")
        continue

    print(f"  {pattern_key}: FOUND {len(rows)} row(s) — DELETING")
    for row in rows:
        print(f"    id={row['id']} rule={row['rule_type']} evidence={row.get('evidence','')[:60]}")

    ids = [r["id"] for r in rows]
    client.table("trading_lessons").delete().in_("id", ids).execute()
    total_deleted += len(rows)

print(f"\nDone. Deleted {total_deleted} bad rule(s).")
if total_deleted == 0:
    print("DB was already clean — no action needed.")
else:
    print("WARNING: Re-run verify_lesson_filter_live.py to confirm filter is healthy.")
