#!/usr/bin/env bash
# ============================================================
# Lumitrade Go/No-Go Gate Validator
# ============================================================
# Validates the 13 go/no-go gates from QTS v2.0 Section 8.2.
# Gates that require manual testing are flagged for human review.
#
# Usage: bash scripts/validate_gates.sh
#
# Requires:
#   - Backend .env loaded (SUPABASE_URL, SUPABASE_SERVICE_KEY)
#   - Backend health endpoint reachable (BACKEND_URL)
#   - pytest available in PATH
# ============================================================

set -euo pipefail

PASS=0
FAIL=0
MANUAL=0
TOTAL=13

# Load env if available
if [ -f backend/.env ]; then
  set -a; source backend/.env; set +a
fi

BACKEND_URL="${BACKEND_URL:-https://lumitrade-engine-production.up.railway.app}"
SUPABASE_URL="${SUPABASE_URL:-}"
SUPABASE_KEY="${SUPABASE_SERVICE_KEY:-}"

echo "============================================"
echo "  LUMITRADE GO/NO-GO GATE VALIDATION"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"
echo ""

# ── G-001: All automated tests pass ──────────────────────────
echo "G-001: All automated test suites pass"
if cd backend && python -m pytest tests/unit/ tests/chaos/ tests/integration/ tests/security/ tests/performance/ -q --tb=no 2>/dev/null; then
  echo "  [PASS] All tests green"
  PASS=$((PASS + 1))
else
  echo "  [FAIL] Some tests failed"
  FAIL=$((FAIL + 1))
fi
cd ..
echo ""

# ── G-002: 50+ paper trades across all 3 pairs ──────────────
echo "G-002: Minimum 50 paper trades across 3 pairs"
if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_KEY" ]; then
  TRADE_COUNT=$(curl -s "${SUPABASE_URL}/rest/v1/trades?select=id&mode=eq.PAPER" \
    -H "apikey: ${SUPABASE_KEY}" -H "Authorization: Bearer ${SUPABASE_KEY}" \
    | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [ "$TRADE_COUNT" -ge 50 ] 2>/dev/null; then
    echo "  [PASS] $TRADE_COUNT paper trades found (>= 50)"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] Only $TRADE_COUNT paper trades (need >= 50)"
    FAIL=$((FAIL + 1))
  fi
else
  echo "  [SKIP] No Supabase credentials — cannot check"
  MANUAL=$((MANUAL + 1))
fi
echo ""

# ── G-003: Win rate >= 40% ──────────────────────────────────
echo "G-003: Paper trading win rate >= 40%"
if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_KEY" ]; then
  WINS=$(curl -s "${SUPABASE_URL}/rest/v1/trades?select=id&mode=eq.PAPER&outcome=eq.WIN" \
    -H "apikey: ${SUPABASE_KEY}" -H "Authorization: Bearer ${SUPABASE_KEY}" \
    | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  TOTAL_TRADES=$(curl -s "${SUPABASE_URL}/rest/v1/trades?select=id&mode=eq.PAPER&outcome=neq.null" \
    -H "apikey: ${SUPABASE_KEY}" -H "Authorization: Bearer ${SUPABASE_KEY}" \
    | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [ "$TOTAL_TRADES" -gt 0 ] 2>/dev/null; then
    WIN_RATE=$(python3 -c "print(round($WINS / $TOTAL_TRADES * 100, 1))")
    if python3 -c "exit(0 if $WINS / $TOTAL_TRADES >= 0.4 else 1)" 2>/dev/null; then
      echo "  [PASS] Win rate: ${WIN_RATE}% ($WINS/$TOTAL_TRADES)"
      PASS=$((PASS + 1))
    else
      echo "  [FAIL] Win rate: ${WIN_RATE}% (need >= 40%)"
      FAIL=$((FAIL + 1))
    fi
  else
    echo "  [FAIL] No completed trades yet"
    FAIL=$((FAIL + 1))
  fi
else
  echo "  [SKIP] No Supabase credentials"
  MANUAL=$((MANUAL + 1))
fi
echo ""

# ── G-004: No crashes in 7 days ─────────────────────────────
echo "G-004: No system crashes in last 7 days"
if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_KEY" ]; then
  CRASHES=$(curl -s "${SUPABASE_URL}/rest/v1/system_events?select=id&event_type=eq.CRASH&created_at=gte.$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo '2026-03-16T00:00:00Z')" \
    -H "apikey: ${SUPABASE_KEY}" -H "Authorization: Bearer ${SUPABASE_KEY}" \
    | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [ "$CRASHES" -eq 0 ] 2>/dev/null; then
    echo "  [PASS] Zero crashes in last 7 days"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $CRASHES crash events found"
    FAIL=$((FAIL + 1))
  fi
else
  echo "  [SKIP] No Supabase credentials"
  MANUAL=$((MANUAL + 1))
fi
echo ""

# ── G-005: Crash recovery (manual) ──────────────────────────
echo "G-005: Crash recovery tested (restart < 60s)"
echo "  [MANUAL] Requires manual test: kill engine, time restart, verify reconciliation"
MANUAL=$((MANUAL + 1))
echo ""

# ── G-006: Failover (manual) ────────────────────────────────
echo "G-006: Local backup failover tested (< 3 min)"
echo "  [MANUAL] Requires manual test: stop cloud, verify local takes over"
MANUAL=$((MANUAL + 1))
echo ""

# ── G-007: Kill switch (manual) ─────────────────────────────
echo "G-007: Kill switch tested (< 10s activation)"
echo "  [MANUAL] Requires manual test: activate kill switch, time response"
MANUAL=$((MANUAL + 1))
echo ""

# ── G-008: Daily loss limit (manual) ────────────────────────
echo "G-008: Daily loss limit tested (-5% halt)"
echo "  [MANUAL] Requires manual test: simulate -5% PnL, verify halt"
MANUAL=$((MANUAL + 1))
echo ""

# ── G-009: Security audit complete ──────────────────────────
echo "G-009: Security audit checklist complete"
if [ -f docs/SECURITY_AUDIT.md ]; then
  CHECKED=$(grep -c '\[x\]' docs/SECURITY_AUDIT.md 2>/dev/null || echo "0")
  UNCHECKED=$(grep -c '\[ \]' docs/SECURITY_AUDIT.md 2>/dev/null || echo "0")
  if [ "$UNCHECKED" -eq 0 ] && [ "$CHECKED" -gt 0 ]; then
    echo "  [PASS] All $CHECKED items checked in SECURITY_AUDIT.md"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $UNCHECKED unchecked items remain (of $((CHECKED + UNCHECKED)) total)"
    FAIL=$((FAIL + 1))
  fi
else
  echo "  [FAIL] docs/SECURITY_AUDIT.md not found"
  FAIL=$((FAIL + 1))
fi
echo ""

# ── G-010: Operator UAT (manual) ────────────────────────────
echo "G-010: Operator UAT score >= 7/10"
echo "  [MANUAL] Requires operator (Abenezer) to complete UAT checklist"
MANUAL=$((MANUAL + 1))
echo ""

# ── G-011: Initial capital $100 (manual) ────────────────────
echo "G-011: Initial live capital $100 max"
echo "  [MANUAL] Verify OANDA live account balance = $100"
MANUAL=$((MANUAL + 1))
echo ""

# ── G-012: Risk 0.5% (automated check) ─────────────────────
echo "G-012: Risk per trade 0.5% for first 2 weeks"
echo "  [MANUAL] Verify settings: MAX_RISK_PER_TRADE=0.005 before going live"
MANUAL=$((MANUAL + 1))
echo ""

# ── G-013: Emergency procedure (manual) ─────────────────────
echo "G-013: Emergency OANDA closure procedure known"
echo "  [MANUAL] Operator confirms knowledge of manual position close + withdrawal"
MANUAL=$((MANUAL + 1))
echo ""

# ── Summary ──────────────────────────────────────────────────
echo "============================================"
echo "  GATE VALIDATION SUMMARY"
echo "============================================"
echo "  PASS:   $PASS / $TOTAL"
echo "  FAIL:   $FAIL / $TOTAL"
echo "  MANUAL: $MANUAL / $TOTAL (require human verification)"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo "  All automated gates PASS."
  echo "  Complete manual gates before switching to LIVE."
else
  echo "  WARNING: $FAIL automated gate(s) FAILED."
  echo "  DO NOT switch to LIVE until all gates pass."
fi
echo "============================================"

exit $FAIL
