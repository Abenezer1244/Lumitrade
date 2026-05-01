#!/usr/bin/env bash
# go_live.sh — Monday 2026-05-04 real-money flip procedure
#
# DEPLOY WINDOW: 13:00–23:59 UTC only. Never run during trading hours (00:00–13:00 UTC).
#
# Prerequisites:
#   railway CLI installed and logged in
#   RAILWAY_PROJECT_ID and RAILWAY_SERVICE_ID set (or use --service flag)
#
# Usage:
#   bash scripts/go_live.sh            # dry-run (shows what would happen)
#   bash scripts/go_live.sh --confirm  # actually flip to live

set -euo pipefail

DRY_RUN=true
[[ "${1:-}" == "--confirm" ]] && DRY_RUN=false

BACKEND_SERVICE="lumitrade-engine"
REQUIRED_PAIRS="USD_CAD,USD_JPY,BTC_USD"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${GREEN}[GO-LIVE]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}   $*"; }
die()  { echo -e "${RED}[ABORT]${NC}  $*"; exit 1; }

# ── Step 0: sanity checks ──────────────────────────────────────────────────────

UTC_HOUR=$(date -u +%H)
if (( 10#$UTC_HOUR < 13 )); then
  die "Current UTC hour is $UTC_HOUR:xx — inside trading window (00:00–13:00 UTC). Deploy only 13:00–23:59 UTC."
fi
log "UTC hour $UTC_HOUR — deploy window OK"

if ! command -v railway &>/dev/null; then
  die "railway CLI not found. Install: npm i -g @railway/cli"
fi
log "railway CLI found"

# ── Step 1: git preflight — fetch, exact-match, clean tree ────────────────────

log "Fetching from origin..."
git fetch origin 2>/dev/null || die "git fetch failed — check network/auth"

LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(git rev-parse origin/main)

log "  Local  HEAD : $LOCAL_SHA"
log "  Remote main : $REMOTE_SHA"

if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
  AHEAD=$(git rev-list --count origin/main..HEAD)
  BEHIND=$(git rev-list --count HEAD..origin/main)
  die "HEAD ($LOCAL_SHA) does not match origin/main ($REMOTE_SHA). " \
      "Local is $AHEAD ahead, $BEHIND behind. Sync first: git pull --ff-only && git push origin main"
fi
log "HEAD exactly matches origin/main ✓"

# Require a clean tracked tree (staged or unstaged changes are a bug risk)
DIRTY=$(git status --porcelain --untracked-files=no 2>/dev/null)
if [[ -n "$DIRTY" ]]; then
  echo "$DIRTY"
  die "Working tree has uncommitted tracked changes. Commit or stash before going live."
fi
log "Working tree is clean (tracked files) ✓"

# Warn about untracked files (non-blocking — scripts/artifacts are expected)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null)
if [[ -n "$UNTRACKED" ]]; then
  warn "Untracked files present (non-blocking — verify none are required for the deploy):"
  echo "$UNTRACKED" | head -10 | sed 's/^/    /'
fi

# ── Step 2: set TRADING_MODE=LIVE on Railway ──────────────────────────────────

log "Current TRADING_MODE on Railway..."
CURRENT_MODE=$(railway variables --service "$BACKEND_SERVICE" 2>/dev/null | grep TRADING_MODE | awk '{print $NF}' || echo "UNKNOWN")
log "  Current: TRADING_MODE=$CURRENT_MODE"

if [[ "$CURRENT_MODE" == "LIVE" ]]; then
  log "  Already LIVE — no change needed"
else
  if $DRY_RUN; then
    warn "[DRY RUN] Would set TRADING_MODE=LIVE on service $BACKEND_SERVICE"
  else
    log "Setting TRADING_MODE=LIVE..."
    railway variables --service "$BACKEND_SERVICE" set TRADING_MODE=LIVE
    log "TRADING_MODE=LIVE set"
  fi
fi

# ── Step 3: verify Railway deployment matches HEAD ────────────────────────────

log "Checking Railway deployment commit..."
if $DRY_RUN; then
  warn "[DRY RUN] Would verify Railway deployment commit matches $LOCAL_SHA"
else
  # Poll railway status for deployed commit hash (Railway CLI exposes --json on some versions)
  RAILWAY_COMMIT=""
  if railway status --service "$BACKEND_SERVICE" --json &>/dev/null; then
    RAILWAY_COMMIT=$(railway status --service "$BACKEND_SERVICE" --json 2>/dev/null \
      | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('commitHash','') or d.get('commit',''))" 2>/dev/null || echo "")
  fi

  if [[ -n "$RAILWAY_COMMIT" ]]; then
    if [[ "$RAILWAY_COMMIT" == "$LOCAL_SHA"* || "$LOCAL_SHA" == "$RAILWAY_COMMIT"* ]]; then
      log "Railway deployment commit matches HEAD ✓ ($RAILWAY_COMMIT)"
    else
      warn "Railway deployed commit ($RAILWAY_COMMIT) does NOT match HEAD ($LOCAL_SHA)."
      warn "GitHub source connection may have silently dropped (known issue 2026-04-13 to 04-21)."
      warn "Triggering manual redeploy: railway up --service $BACKEND_SERVICE --detach"
      if ! $DRY_RUN; then
        railway up --service "$BACKEND_SERVICE" --detach || warn "railway up failed — check Railway dashboard"
      fi
    fi
  else
    log "Latest local commit:"
    git log --oneline -1
    warn "Could not read Railway deploy commit via CLI (version may not support --json)."
    warn "Manually verify Railway dashboard shows commit $LOCAL_SHA"
    warn "If deploy didn't trigger: railway up --service $BACKEND_SERVICE --detach"
  fi
fi

# ── Step 4: dual-switch reminder ──────────────────────────────────────────────

echo ""
echo -e "${YELLOW}══════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  MANUAL STEP REQUIRED: Dashboard Kill-Switch${NC}"
echo -e "${YELLOW}══════════════════════════════════════════════════════${NC}"
echo ""
echo "  Engine is LIVE only when BOTH switches are ON:"
echo "  1. Env var TRADING_MODE=LIVE  (done above)"
echo "  2. Dashboard kill-switch → LIVE  (YOU must flip this)"
echo ""
echo "  Navigate to dashboard → Mission Control → flip trading mode to LIVE"
echo "  The engine checks both; either OFF = PAPER mode."
echo ""

# ── Step 5: BTC risk cap reminder ─────────────────────────────────────────────

echo -e "${YELLOW}══════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  BTC_USD RISK CAP REMINDER${NC}"
echo -e "${YELLOW}══════════════════════════════════════════════════════${NC}"
echo ""
echo "  BTC_USD N=16 backtest (below 20-trade confidence threshold)"
echo "  Risk cap: 0.5% per trade UNTIL 20 live BTC trades are logged"
echo "  After 20 live BTC trades: review and optionally raise to standard risk"
echo "  BTC fires ~8 quality setups/year — track in dashboard"
echo ""

# ── Step 6: live pairs confirmation ──────────────────────────────────────────

log "Required live_pairs: $REQUIRED_PAIRS"
log "Verify in config.py that live_pairs matches the above"

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
if $DRY_RUN; then
  echo -e "${YELLOW}[DRY RUN COMPLETE]${NC} No changes made. Run with --confirm to execute."
else
  echo -e "${GREEN}[GO-LIVE COMPLETE]${NC}"
  echo "  - Commits pushed"
  echo "  - TRADING_MODE=LIVE set on Railway"
  echo "  - Flip dashboard kill-switch to activate"
  echo ""
  echo "  Monitor: watch Railway logs for first LIVE trades"
  echo "  Emergency stop: dashboard kill-switch OFF (immediate) or set TRADING_MODE=PAPER (Railway)"
fi
