"""Quick schema probe for trades + trading_lessons."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

print("=== TRADING LESSONS (first 5 full rows) ===")
lessons = sb.table("trading_lessons").select("*").execute().data or []
for le in lessons[:5]:
    print(le)

print()
print("=== 3 most recent CLOSED trades — full payload ===")
tr = (
    sb.table("trades")
    .select("*")
    .eq("status", "CLOSED")
    .order("closed_at", desc=True)
    .limit(3)
    .execute()
    .data
)
for t in tr:
    print("-" * 60)
    for k, v in t.items():
        print(f"  {k}: {v}")
