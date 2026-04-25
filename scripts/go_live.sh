#!/usr/bin/env bash
# Lumitrade — Monday live flip with safety preflight.
#
# Usage (Monday during 13:00-23:59 UTC, recommended ~20:00 UTC = 1 PM PT):
#   bash scripts/go_live.sh
#
# Aborts if any safety check fails. No real money risk on abort.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "================================================================"
echo "  LUMITRADE — go-live cutover"
echo "  $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
echo "================================================================"

# ── Preflight check 1: deploy window ──────────────────────────────
HOUR_UTC=$(date -u +%H)
if [ "$HOUR_UTC" -lt 13 ] || [ "$HOUR_UTC" -ge 24 ]; then
  echo "ABORT: current hour ${HOUR_UTC}:00 UTC is outside the deploy window (13-23 UTC)."
  echo "Run during 13:00-23:59 UTC to avoid restarting the engine during trading hours."
  exit 1
fi
echo "[OK] Deploy window: ${HOUR_UTC}:00 UTC is inside 13-23 UTC."

# ── Preflight check 2: weekend? ───────────────────────────────────
DOW=$(date -u +%u)  # 1=Mon, 7=Sun
if [ "$DOW" -ge 6 ]; then
  echo "ABORT: It's weekend (DOW=$DOW). Forex markets are closed."
  exit 1
fi
if [ "$DOW" -eq 5 ] && [ "$HOUR_UTC" -ge 21 ]; then
  echo "ABORT: It's Friday after 21:00 UTC. Market closes 22:00 UTC; don't go live now."
  exit 1
fi
echo "[OK] Day of week: $DOW (1=Mon..5=Fri)"

# ── Preflight check 3: OANDA balance funded ──────────────────────
echo ""
echo "Checking OANDA live account balance…"
set -a; source backend/.env; set +a
BALANCE=$(python -c "
import os, httpx
r = httpx.get(
    f'https://api-fxtrade.oanda.com/v3/accounts/{os.environ[\"OANDA_ACCOUNT_ID\"]}/summary',
    headers={'Authorization': f'Bearer {os.environ[\"OANDA_API_KEY_TRADING\"]}'},
    timeout=10.0,
)
r.raise_for_status()
print(r.json()['account']['balance'])
" 2>&1)
echo "  OANDA account ${OANDA_ACCOUNT_ID} balance: \$${BALANCE}"

# Use Python for float comparison (POSIX shell can't do floats)
ENOUGH=$(python -c "print('yes' if float('${BALANCE}') >= 50.0 else 'no')")
if [ "$ENOUGH" != "yes" ]; then
  echo "ABORT: balance \$${BALANCE} is below \$50 — fund the account first."
  echo "Visit https://trade.oanda.com → Wallet → Deposit"
  exit 1
fi
echo "[OK] Account funded (\$${BALANCE} >= \$50 minimum)"

# ── Preflight check 4: dashboard mode is LIVE ─────────────────────
echo ""
echo "Checking dashboard mode in Supabase…"
DASHBOARD_MODE=$(python -c "
import os
from dotenv import load_dotenv
from supabase import create_client
load_dotenv('backend/.env')
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
row = sb.table('system_state').select('*').eq('id', 'settings').execute()
print(row.data[0].get('open_trades', {}).get('mode', 'PAPER') if row.data else 'PAPER')
" 2>&1)
echo "  Dashboard mode: ${DASHBOARD_MODE}"

if [ "$DASHBOARD_MODE" != "LIVE" ]; then
  echo "ABORT: dashboard mode is '${DASHBOARD_MODE}', expected 'LIVE'."
  echo "Open /settings in the dashboard, flip ModeToggle to LIVE, save, then re-run."
  exit 1
fi
echo "[OK] Dashboard mode = LIVE (dual-switch primed)"

# ── Preflight check 5: Railway TRADING_MODE currently PAPER ───────
echo ""
echo "Checking Railway env state…"
CURRENT_MODE=$(railway variables -s lumitrade-engine 2>&1 | grep "TRADING_MODE" | head -1 | awk -F'│' '{print $2}' | tr -d ' ')
echo "  Current TRADING_MODE on Railway: ${CURRENT_MODE}"

if [ "$CURRENT_MODE" = "LIVE" ]; then
  echo "ABORT: TRADING_MODE is already LIVE. Nothing to do."
  exit 0
fi
echo "[OK] Currently PAPER, ready to flip"

# ── Final confirmation ────────────────────────────────────────────
echo ""
echo "================================================================"
echo "  ALL PREFLIGHT CHECKS PASSED"
echo "================================================================"
echo "Account: ${OANDA_ACCOUNT_ID} balance \$${BALANCE}"
echo "Dashboard: LIVE"
echo "About to: railway variables --set TRADING_MODE=LIVE -s lumitrade-engine"
echo ""
read -p "Type GO to proceed (anything else to abort): " CONFIRM
if [ "$CONFIRM" != "GO" ]; then
  echo "ABORTED by user."
  exit 0
fi

# ── EXECUTE THE FLIP ──────────────────────────────────────────────
echo ""
echo "Flipping TRADING_MODE to LIVE…"
railway variables --set TRADING_MODE=LIVE -s lumitrade-engine
echo ""
echo "Waiting 60s for redeploy + first heartbeat…"
sleep 60

echo ""
echo "Recent logs (looking for live_pair_filter_applied + oanda_connected):"
railway logs -s lumitrade-engine 2>&1 | grep -iE "live_pair_filter_applied|oanda_connected|signal_to_trade_loop_started|trading_mode" | tail -20

echo ""
echo "================================================================"
echo "  CUTOVER COMPLETE"
echo "================================================================"
echo "  Watch: https://railway.app/project/<id>/service/lumitrade-engine"
echo "  Rollback: railway variables --set TRADING_MODE=PAPER -s lumitrade-engine"
echo "  Soft stop: dashboard /settings → ModeToggle → PAPER → save"
