"""
One-shot script: close all ghost OPEN trades across all accounts.
A ghost is a trade that is OPEN in Supabase but NOT open on OANDA.

Fixes (Codex adversarial review 2026-05-04):
- Checks ALL OANDA accounts (forex + crypto sub-account) so BTC/ETH
  trades on OANDA_SPOT_CRYPTO_ACCOUNT_ID are never falsely ghosted.
- Fetches real P&L, exit price, outcome, and close time from OANDA
  before patching DB rows — same logic as the runtime reconciler.
- Dry-run mode: pass --dry-run to print actions without patching.

Run via: railway run python scripts/close_ghost_trades.py [--dry-run]
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import httpx


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
OANDA_URL = os.environ.get("OANDA_BASE_URL", "https://api-fxtrade.oanda.com")
OANDA_KEY = os.environ.get("OANDA_API_KEY_DATA") or os.environ["OANDA_API_KEY"]

# Main forex account (required)
OANDA_ACCOUNT_FOREX = os.environ["OANDA_ACCOUNT_ID"]
# Crypto spot sub-account (optional — BTC/ETH trades live here)
OANDA_ACCOUNT_CRYPTO = os.environ.get("OANDA_SPOT_CRYPTO_ACCOUNT_ID", "")

_CRYPTO_PAIRS = {"BTC_USD", "ETH_USD"}

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
OANDA_HEADERS = {
    "Authorization": f"Bearer {OANDA_KEY}",
    "Content-Type": "application/json",
}

DRY_RUN = "--dry-run" in sys.argv


def _oanda_account_for(pair: str) -> str:
    """Return the OANDA account ID that holds trades for this pair."""
    if pair in _CRYPTO_PAIRS and OANDA_ACCOUNT_CRYPTO:
        return OANDA_ACCOUNT_CRYPTO
    return OANDA_ACCOUNT_FOREX


async def _fetch_all_oanda_open_ids(client: httpx.AsyncClient) -> set[str]:
    """
    Fetch open trade IDs from every relevant OANDA account.
    Returns a union set — a broker_trade_id not in this set is truly gone.
    """
    accounts: set[str] = {OANDA_ACCOUNT_FOREX}
    if OANDA_ACCOUNT_CRYPTO:
        accounts.add(OANDA_ACCOUNT_CRYPTO)

    all_ids: set[str] = set()
    for account_id in accounts:
        try:
            resp = await client.get(
                f"{OANDA_URL}/v3/accounts/{account_id}/trades",
                params={"state": "OPEN"},
                headers=OANDA_HEADERS,
            )
            resp.raise_for_status()
            trades = resp.json().get("trades", [])
            ids = {str(t["id"]) for t in trades}
            print(f"  [{account_id}] {len(ids)} open trades: {ids or 'none'}")
            all_ids |= ids
        except httpx.HTTPStatusError as e:
            print(
                f"  WARNING: failed to fetch open trades from {account_id}: "
                f"{e.response.status_code} {e.response.text[:200]}"
            )
    return all_ids


async def _fetch_broker_close_details(
    client: httpx.AsyncClient, broker_trade_id: str, pair: str
) -> dict:
    """
    Fetch a (possibly closed) trade's details from OANDA.
    Returns the trade dict, or {} if not found.
    """
    account_id = _oanda_account_for(pair)
    try:
        resp = await client.get(
            f"{OANDA_URL}/v3/accounts/{account_id}/trades/{broker_trade_id}",
            headers=OANDA_HEADERS,
        )
        resp.raise_for_status()
        return resp.json().get("trade", {})
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            print(
                f"  OANDA 404 for broker_trade_id={broker_trade_id} on {account_id}"
                f" — trade may never have been placed"
            )
        else:
            print(f"  OANDA {status} fetching {broker_trade_id}: {e.response.text[:200]}")
        return {}


def _classify_exit_reason(oanda_trade: dict, outcome: str) -> str:
    tx_reasons = [
        oanda_trade.get(k)
        for k in (
            "stopLossOrderFillReason",
            "takeProfitOrderFillReason",
            "trailingStopLossOrderFillReason",
        )
        if oanda_trade.get(k)
    ]
    close_reason = tx_reasons[0] if tx_reasons else None
    if close_reason:
        upper = close_reason.upper()
        if "TRAILING" in upper:
            return "TRAILING_STOP"
        if "STOP_LOSS" in upper:
            return "SL_HIT"
        if "TAKE_PROFIT" in upper:
            return "TP_HIT"
    if outcome == "LOSS":
        return "SL_HIT"
    if outcome == "WIN":
        return "TRAILING_STOP"
    return "UNKNOWN"


async def main() -> None:
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Ghost trade cleanup starting...")
    print(f"Forex account : {OANDA_ACCOUNT_FOREX}")
    print(f"Crypto account: {OANDA_ACCOUNT_CRYPTO or '(not configured)'}")

    async with httpx.AsyncClient(timeout=15) as client:
        # 1. Fetch all OPEN trades from Supabase (all accounts)
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/trades",
            params={"select": "*", "status": "eq.OPEN"},
            headers=SB_HEADERS,
        )
        resp.raise_for_status()
        db_open = resp.json()
        print(f"\nDB OPEN trades (all accounts): {len(db_open)}")
        if not db_open:
            print("No open trades in DB — nothing to do.")
            return

        for t in db_open:
            print(
                f"  id={t['id']} pair={t['pair']}"
                f" account_id={t['account_id']}"
                f" broker_trade_id={t.get('broker_trade_id')}"
            )

        # 2. Fetch open trade IDs from ALL OANDA accounts
        print("\nFetching OANDA open trades from all accounts...")
        oanda_ids = await _fetch_all_oanda_open_ids(client)
        print(f"Total OANDA open IDs (all accounts): {len(oanda_ids)}")

        # 3. Identify ghosts — broker_trade_id absent from every OANDA account
        ghosts = [
            t for t in db_open
            if t.get("broker_trade_id")
            and str(t["broker_trade_id"]) not in oanda_ids
        ]

        print(f"\nGhost trades found: {len(ghosts)}")
        if not ghosts:
            print("All open DB trades are confirmed open on OANDA — no action needed.")
            return

        # 4. Close each ghost with full broker details (mirrors reconciler logic)
        now = datetime.now(timezone.utc).isoformat()

        for ghost in ghosts:
            trade_id = ghost["id"]
            pair = ghost["pair"]
            broker_id = str(ghost.get("broker_trade_id") or "")
            entry_price = ghost.get("entry_price")
            opened_at = ghost.get("opened_at") or now

            print(f"\nGhost: id={trade_id} pair={pair} broker_trade_id={broker_id}")

            # Attempt to recover P&L from OANDA — mirrors reconciler._handle_ghost()
            oanda_trade = await _fetch_broker_close_details(client, broker_id, pair)

            pnl_usd: float = 0.0
            exit_price = entry_price
            close_time = now
            outcome = "BREAKEVEN"
            exit_reason = "UNKNOWN"

            if oanda_trade:
                real_pl = float(oanda_trade.get("realizedPL") or 0)
                if real_pl != 0:
                    pnl_usd = real_pl
                    outcome = "WIN" if real_pl > 0 else "LOSS"
                if oanda_trade.get("averageClosePrice"):
                    exit_price = oanda_trade["averageClosePrice"]
                if oanda_trade.get("closeTime"):
                    close_time = oanda_trade["closeTime"]
                exit_reason = _classify_exit_reason(oanda_trade, outcome)
                print(
                    f"  OANDA recovery: outcome={outcome} pnl=${pnl_usd:.2f}"
                    f" exit_price={exit_price} reason={exit_reason}"
                )
            else:
                print("  Could not recover from OANDA — using safe defaults (pnl=0, UNKNOWN)")

            duration_minutes = None
            try:
                opened_dt = datetime.fromisoformat(str(opened_at).replace("Z", "+00:00"))
                closed_dt = datetime.fromisoformat(str(close_time).replace("Z", "+00:00"))
                duration_minutes = int((closed_dt - opened_dt).total_seconds() // 60)
            except Exception:
                pass

            patch_payload: dict = {
                "status": "CLOSED",
                "closed_at": close_time,
                "exit_reason": exit_reason,
                "outcome": outcome,
                "pnl_usd": pnl_usd,
                "pnl_pips": "0",
                "exit_price": str(exit_price) if exit_price else None,
            }
            if duration_minutes is not None:
                patch_payload["duration_minutes"] = duration_minutes

            print(f"  Payload: {patch_payload}")

            if DRY_RUN:
                print(f"  [DRY RUN] Skipping patch for trade {trade_id}.")
                continue

            patch_resp = await client.patch(
                f"{SUPABASE_URL}/rest/v1/trades",
                params={"id": f"eq.{trade_id}"},
                headers=SB_HEADERS,
                json=patch_payload,
            )
            if patch_resp.status_code in (200, 204):
                print(f"  Closed trade {trade_id} successfully.")
            else:
                print(
                    f"  ERROR closing trade {trade_id}:"
                    f" {patch_resp.status_code} {patch_resp.text}"
                )

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
