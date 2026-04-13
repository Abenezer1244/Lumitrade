"""
Fetch 2 years of historical candle data from OANDA for backtesting.
Saves CSV files to backend/data/historical/

Usage:
    cd backend
    python -m scripts.fetch_historical

Requires OANDA_API_KEY_DATA and OANDA_BASE_URL env vars.
"""

import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

# Config
PAIRS = ["USD_JPY", "USD_CAD", "AUD_USD", "NZD_USD"]
TIMEFRAMES = ["M15", "H1", "H4"]
YEARS_BACK = 2
MAX_CANDLES_PER_REQUEST = 5000
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "historical"

# OANDA API
BASE_URL = os.environ.get("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
API_KEY = os.environ.get("OANDA_API_KEY_DATA", "")


async def fetch_candles(
    client: httpx.AsyncClient,
    pair: str,
    granularity: str,
    from_dt: datetime,
    to_dt: datetime,
) -> list[dict]:
    """Fetch candles between two dates, paginating as needed."""
    all_candles = []
    current_from = from_dt

    while current_from < to_dt:
        url = f"{BASE_URL}/v3/instruments/{pair}/candles"
        # OANDA doesn't allow count + from/to together.
        # Use from + count (no to) — fetches up to 5000 candles forward from 'from'
        params = {
            "granularity": granularity,
            "from": current_from.isoformat(),
            "count": MAX_CANDLES_PER_REQUEST,
            "price": "M",
        }

        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            print(f"  ERROR: {resp.status_code} — {resp.text[:200]}")
            break

        data = resp.json()
        candles = data.get("candles", [])
        if not candles:
            break

        all_candles.extend(candles)

        # Move forward past the last candle
        last_time = candles[-1]["time"]
        if last_time.endswith("Z"):
            last_dt = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
        else:
            last_dt = datetime.fromisoformat(last_time)

        # If we didn't advance, break to avoid infinite loop
        if last_dt <= current_from:
            break
        current_from = last_dt + timedelta(seconds=1)

        print(f"    Fetched {len(candles)} candles up to {last_time[:19]}... (total: {len(all_candles)})")

        # Rate limit: OANDA allows ~20 req/sec but be polite
        await asyncio.sleep(0.2)

    return all_candles


def candles_to_csv(candles: list[dict], filepath: Path) -> int:
    """Write candles to CSV. Returns count written."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "open", "high", "low", "close", "volume", "complete"])

        count = 0
        for c in candles:
            if not c.get("complete", True):
                continue  # Skip incomplete candles
            mid = c.get("mid", {})
            writer.writerow([
                c["time"][:19],  # Trim to YYYY-MM-DDTHH:MM:SS
                mid.get("o", ""),
                mid.get("h", ""),
                mid.get("l", ""),
                mid.get("c", ""),
                c.get("volume", 0),
                c.get("complete", True),
            ])
            count += 1

    return count


async def main():
    if not API_KEY:
        print("ERROR: OANDA_API_KEY_DATA env var not set.")
        print("Set it from your OANDA practice account API token.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    to_dt = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(days=365 * YEARS_BACK)

    print(f"Fetching {YEARS_BACK} years of data: {from_dt.date()} to {to_dt.date()}")
    print(f"Pairs: {PAIRS}")
    print(f"Timeframes: {TIMEFRAMES}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        for pair in PAIRS:
            for tf in TIMEFRAMES:
                print(f"[{pair}] [{tf}] Fetching...")

                candles = await fetch_candles(client, pair, tf, from_dt, to_dt)

                if candles:
                    filepath = OUTPUT_DIR / f"{pair}_{tf}.csv"
                    count = candles_to_csv(candles, filepath)
                    size_kb = filepath.stat().st_size // 1024
                    print(f"  Saved {count} candles to {filepath.name} ({size_kb} KB)")
                else:
                    print(f"  No candles returned!")

                print()

    # Summary
    print("=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)
    total_files = 0
    total_size = 0
    for f in sorted(OUTPUT_DIR.glob("*.csv")):
        size = f.stat().st_size
        lines = sum(1 for _ in open(f)) - 1  # Subtract header
        print(f"  {f.name}: {lines:,} candles ({size // 1024} KB)")
        total_files += 1
        total_size += size
    print(f"\nTotal: {total_files} files, {total_size // 1024:,} KB")


if __name__ == "__main__":
    asyncio.run(main())
