# Lumitrade Go/No-Go Gates -- Live Trading Authorization

All 13 gates must be TRUE before switching `TRADING_MODE` to `LIVE` and depositing real capital.

Sources: QTS v2.0 Section 8.2, PRD v2.0 Section 18.2

---

## Gate Checklist

### G-001: All automated test suites pass with zero failures
- **Requirement:** CI pipeline shows 100% green across all test categories (unit, integration, chaos, security, e2e)
- **Verification:** Run `scripts/run_critical_tests.sh` -- all 191+ tests pass with zero failures
- **Evidence:** Screenshot of CI pipeline or terminal output showing all green
- [ ] **VERIFIED**

### G-002: Minimum 50 paper trades logged across all 3 currency pairs
- **Requirement:** At least 50 paper trades executed, covering EUR/USD, GBP/USD, and USD/JPY
- **Verification:** SQL query: `SELECT pair, COUNT(*) FROM trades WHERE mode='PAPER' GROUP BY pair;` -- total >= 50, all 3 pairs represented
- **Evidence:** Query result saved
- [ ] **VERIFIED**

### G-003: Paper trading win rate >= 40% over 50+ trade sample
- **Requirement:** Win rate must meet statistical minimum for live progression
- **Verification:** Analytics page win rate metric >= 40%, or SQL: `SELECT COUNT(*) FILTER (WHERE pnl > 0)::float / COUNT(*) FROM trades WHERE mode='PAPER';`
- **Evidence:** Analytics page screenshot or query result
- [ ] **VERIFIED**

### G-004: No system crashes in last 7 consecutive days of paper trading
- **Requirement:** System runs continuously for 7 days without requiring manual intervention
- **Verification:** SQL query: `SELECT COUNT(*) FROM system_events WHERE event_type='CRASH' AND created_at > NOW() - INTERVAL '7 days';` -- result must be 0
- **Evidence:** Query result showing zero CRASH entries
- [ ] **VERIFIED**

### G-005: Crash recovery tested successfully (manual)
- **Requirement:** Process killed externally, auto-restarts within 60 seconds, position reconciliation correct
- **Verification:** Manual test: `kill -9` the engine process, time the restart, verify positions reconciled against OANDA
- **Evidence:** Documented test with timestamps showing restart < 60s and reconciliation log
- [ ] **VERIFIED**

### G-006: Local backup failover tested successfully (manual)
- **Requirement:** Cloud process killed, local backup activates within 3 minutes automatically
- **Verification:** Stop Railway cloud service, observe local backup acquires primary lock and starts trading within 3 minutes
- **Evidence:** Documented test with timestamps, system_events log showing FAILOVER event
- [ ] **VERIFIED**

### G-007: Kill switch tested and confirmed functional (manual)
- **Requirement:** Kill switch activates in < 10 seconds, closes all paper positions, halts all signals
- **Verification:** Activate kill switch from Dashboard in paper mode -- time from click to full halt must be < 10 seconds
- **Evidence:** Timed test documented, confirmation that all positions closed and signals halted
- [ ] **VERIFIED**

### G-008: Daily loss limit tested (manual)
- **Requirement:** Simulate -5% daily P&L, confirm trading halts immediately
- **Verification:** Manually set daily P&L to -5% threshold, confirm system triggers DAILY_LIMIT halt and stops all trading
- **Evidence:** system_events log showing DAILY_LIMIT_HIT event, trading confirmed halted
- [ ] **VERIFIED**

### G-009: All 27 items on security audit checklist complete
- **Requirement:** Every item in the pre-launch security audit (docs/security-audit.md) is checked and verified
- **Verification:** Review security-audit.md -- all 27 checkboxes marked complete
- **Evidence:** Completed security-audit.md with all items checked
- [ ] **VERIFIED**

### G-010: Operator UAT score >= 7/10 satisfaction
- **Requirement:** Operator (Abenezer) completes the UAT checklist and rates overall satisfaction >= 7/10
- **Verification:** Complete UAT-001 through UAT-010 scenarios from QTS Section 8.1, rate each, overall score >= 7/10
- **Evidence:** Completed UAT scorecard documented
- [ ] **VERIFIED**

### G-011: Maximum initial live capital: $100
- **Requirement:** OANDA account funded with $100 only for first 2 weeks of live trading
- **Verification:** OANDA account balance screenshot showing exactly $100 deposited
- **Evidence:** OANDA portal screenshot
- [ ] **VERIFIED**

### G-012: Maximum risk per trade for first 2 weeks live: 0.5%
- **Requirement:** Conservative risk setting for initial live period (0.5% vs normal 2%)
- **Verification:** Settings panel shows risk slider at 0.5%, confirmed in config: `MAX_RISK_PER_TRADE=0.005`
- **Evidence:** Settings page screenshot and env var confirmation
- [ ] **VERIFIED**

### G-013: Emergency OANDA account closure procedure known and documented
- **Requirement:** Operator knows how to manually close all positions and withdraw funds via OANDA portal
- **Verification:** Operator confirms knowledge of: OANDA portal login, manual position closure, fund withdrawal procedure
- **Evidence:** Written confirmation that procedure is understood and practiced
- [ ] **VERIFIED**

---

## Summary

| Gate | Description | Status |
|------|-------------|--------|
| G-001 | All automated tests pass (191+ green) | [ ] |
| G-002 | 50+ paper trades across all 3 pairs | [ ] |
| G-003 | Win rate >= 40% over 50+ trades | [ ] |
| G-004 | 7 consecutive days without crash | [ ] |
| G-005 | Crash recovery tested (restart < 60s) | [ ] |
| G-006 | Local backup failover tested (< 3 min) | [ ] |
| G-007 | Kill switch tested (< 10s activation) | [ ] |
| G-008 | Daily loss limit tested (-5% halt) | [ ] |
| G-009 | 27-item security audit complete | [ ] |
| G-010 | Operator UAT score >= 7/10 | [ ] |
| G-011 | Initial capital $100 max | [ ] |
| G-012 | Risk per trade 0.5% max (first 2 weeks) | [ ] |
| G-013 | Emergency OANDA closure procedure known | [ ] |

**Go/No-Go Decision:** All 13 gates must show [x] before TRADING_MODE is switched to LIVE.
