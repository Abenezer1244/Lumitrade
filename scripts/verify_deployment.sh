#!/bin/bash
# Lumitrade Deployment Verification
# Run after deployment to verify everything is working
#
# Usage:
#   ./scripts/verify_deployment.sh                              # Uses localhost:8000
#   HEALTH_URL=https://your-app.railway.app/health ./scripts/verify_deployment.sh

set -euo pipefail

echo "=== Lumitrade Deployment Verification ==="
echo ""

PASS=0
FAIL=0

check_pass() {
  echo "  OK:   $1"
  PASS=$((PASS + 1))
}

check_fail() {
  echo "  FAIL: $1"
  FAIL=$((FAIL + 1))
}

# ── Step 1: Check required environment variables ─────────────────

echo "[1/3] Checking required environment variables..."
echo ""

REQUIRED_VARS=(
  "OANDA_API_KEY_DATA"
  "OANDA_API_KEY_TRADING"
  "OANDA_ACCOUNT_ID"
  "OANDA_ENVIRONMENT"
  "ANTHROPIC_API_KEY"
  "SUPABASE_URL"
  "SUPABASE_SERVICE_KEY"
  "INSTANCE_ID"
  "TRADING_MODE"
)

for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    check_fail "$var is not set"
  else
    check_pass "$var is set"
  fi
done

# Check alert vars separately (warn but don't fail)
echo ""
echo "  Alert variables (recommended):"
ALERT_VARS=("TELNYX_API_KEY" "TELNYX_FROM_NUMBER" "ALERT_SMS_TO" "SENDGRID_API_KEY" "ALERT_EMAIL_TO")
for var in "${ALERT_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "  WARN: $var is not set (alerts will not work)"
  else
    check_pass "$var is set"
  fi
done

# ── Step 2: Check health endpoint ────────────────────────────────

echo ""
echo "[2/3] Checking health endpoint..."
echo ""

HEALTH_URL="${HEALTH_URL:-http://localhost:8000/health}"
echo "  Target: $HEALTH_URL"

# Pick a working python — Windows often only has `python`, not `python3`.
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else PY=""
fi

# Use mktemp so the path is valid for both bash and Python on every platform
# (Git Bash on Windows maps /tmp differently for bash vs Python, breaking
# `python -c "open('/tmp/...')` if we hardcode the unix path).
if [ -n "$PY" ]; then
  HEALTH_FILE=$("$PY" -c "import tempfile; print(tempfile.mkstemp(suffix='.json', prefix='lumitrade_health_')[1])")
else
  HEALTH_FILE="$(mktemp -t lumitrade_health.XXXXXX.json 2>/dev/null || echo /tmp/lumitrade_health.json)"
fi

HTTP_CODE=$(curl -s -o "$HEALTH_FILE" -w "%{http_code}" --connect-timeout 10 --max-time 15 "$HEALTH_URL" 2>/dev/null || echo "000")

# Helper: extract a field from the health JSON.
# Usage: get_field <dotted-path> e.g. "status" or "components.database.status"
# Path + file are passed via env vars so Windows backslash paths don't get
# misinterpreted as Python unicode escape sequences.
get_field() {
  local path="$1"
  if [ -z "$PY" ]; then echo "unknown"; return; fi
  HEALTH_FILE_ENV="$HEALTH_FILE" FIELD_PATH="$path" "$PY" -c "
import json, os
try:
    d = json.load(open(os.environ['HEALTH_FILE_ENV']))
    cur = d
    for key in os.environ['FIELD_PATH'].split('.'):
        if isinstance(cur, dict):
            cur = cur.get(key, 'MISSING')
        else:
            cur = 'MISSING'; break
    print(cur if cur is not None else 'null')
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown"
}

if [ "$HTTP_CODE" = "200" ]; then
  echo ""
  echo "  Health response:"
  if [ -n "$PY" ]; then
    "$PY" -m json.tool $HEALTH_FILE 2>/dev/null | sed 's/^/    /' || cat $HEALTH_FILE | sed 's/^/    /'
  else
    cat $HEALTH_FILE | sed 's/^/    /'
  fi
  echo ""

  # Overall status: server returns HTTP 200 even on "degraded" (DB up, other
  # components struggling). A post-deploy verifier must fail unless overall
  # status == "healthy" — degraded means something's wrong.
  OVERALL=$(get_field "status")
  case "$OVERALL" in
    healthy)  check_pass "Overall status: healthy" ;;
    degraded) check_fail "Overall status: degraded — one or more components are not OK (HTTP 200 alone is not enough)" ;;
    down)     check_fail "Overall status: down" ;;
    *)        check_fail "Overall status: $OVERALL (expected 'healthy')" ;;
  esac

  # Per-component checks — all live under components.* and report status: "ok" / "error" / "stale" / etc.
  DB_STATUS=$(get_field "components.database.status")
  case "$DB_STATUS" in
    ok)      check_pass "Database: ok" ;;
    MISSING) check_fail "components.database.status missing from health response" ;;
    *)       check_fail "Database status: $DB_STATUS (expected 'ok')" ;;
  esac

  OANDA_STATUS=$(get_field "components.oanda.status")
  case "$OANDA_STATUS" in
    ok)      check_pass "OANDA broker: ok" ;;
    MISSING) check_fail "components.oanda.status missing from health response" ;;
    *)       check_fail "OANDA broker status: $OANDA_STATUS (expected 'ok')" ;;
  esac

  STATE_STATUS=$(get_field "components.state.status")
  case "$STATE_STATUS" in
    ok)      check_pass "Engine state: fresh" ;;
    stale)   check_fail "Engine state is STALE — engine may not be writing heartbeats" ;;
    MISSING) echo "  WARN: components.state.status missing (older engine build?)" ;;
    *)       check_fail "Engine state status: $STATE_STATUS" ;;
  esac

  LOCK_STATUS=$(get_field "components.lock.status")
  case "$LOCK_STATUS" in
    held)            check_pass "Distributed lock: held by this instance" ;;
    held_by_other)   echo "  WARN: lock held by another instance (this is a standby)" ;;
    not_held)        check_fail "No instance holds the distributed lock — engine is not running primary" ;;
    MISSING)         echo "  WARN: components.lock.status missing" ;;
    *)               check_fail "Lock status: $LOCK_STATUS" ;;
  esac

  CB_STATUS=$(get_field "components.circuit_breaker.status")
  case "$CB_STATUS" in
    CLOSED)  check_pass "Circuit breaker: CLOSED (healthy)" ;;
    OPEN)    check_fail "Circuit breaker is OPEN — broker calls are being rejected" ;;
    HALF_OPEN) echo "  WARN: circuit breaker is HALF_OPEN — recovering from a fault" ;;
    MISSING) echo "  WARN: components.circuit_breaker.status missing" ;;
    *)       echo "  WARN: circuit breaker status: $CB_STATUS" ;;
  esac

  # Trading info from the response (cross-check with TRADING_MODE env in step 3)
  REPORTED_MODE=$(get_field "trading.mode")
  if [ "$REPORTED_MODE" != "MISSING" ] && [ "$REPORTED_MODE" != "unknown" ]; then
    if [ -n "${TRADING_MODE:-}" ] && [ "$REPORTED_MODE" != "${TRADING_MODE:-}" ]; then
      check_fail "Engine reports trading.mode=$REPORTED_MODE but TRADING_MODE env=$TRADING_MODE — env/runtime mismatch"
    else
      check_pass "Engine trading.mode = $REPORTED_MODE"
    fi
  fi
else
  check_fail "Health endpoint returned HTTP $HTTP_CODE"
  if [ "$HTTP_CODE" = "000" ]; then
    echo "  (Could not connect -- is the service running?)"
  elif [ "$HTTP_CODE" = "503" ]; then
    echo "  (Service is reporting unhealthy — check logs for component failures)"
    if [ -n "$PY" ]; then
      "$PY" -m json.tool $HEALTH_FILE 2>/dev/null | sed 's/^/    /' || true
    fi
  fi
fi

# ── Step 3: Check trading mode ───────────────────────────────────

echo ""
echo "[3/3] Checking trading mode..."
echo ""

if [ "${TRADING_MODE:-}" = "PAPER" ]; then
  check_pass "TRADING_MODE is PAPER"
elif [ "${TRADING_MODE:-}" = "LIVE" ]; then
  echo "  WARN: TRADING_MODE is LIVE -- ensure all 13 go/no-go gates have passed"
  PASS=$((PASS + 1))
else
  check_fail "TRADING_MODE is '${TRADING_MODE:-unset}' (expected PAPER or LIVE)"
fi

# ── Summary ──────────────────────────────────────────────────────

echo ""
echo "=== Verification Summary ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo ""

# Clean up
rm -f $HEALTH_FILE

if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: FAIL -- $FAIL check(s) did not pass. Fix issues before proceeding."
  exit 1
else
  echo "RESULT: ALL CHECKS PASSED"
  exit 0
fi
