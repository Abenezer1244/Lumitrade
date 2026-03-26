# Lumitrade Build Progress

## Overall Status
| Phase | Status | Tests |
|-------|--------|-------|
| Phase 1: Foundation | COMPLETE | 15/15 pass |
| Phase 2: Data Engine | COMPLETE | 8/8 pass |
| Phase 3: AI Brain | COMPLETE | 38/38 pass |
| Phase 4: Risk Engine | COMPLETE | 35/35 pass |
| Phase 5: Execution Engine | COMPLETE | 60/60 pass (40 new) |
| Phase 6: State & Orchestration | COMPLETE | 26/26 pass (10 new reconciler) |
| Phase 7: Dashboard Frontend | COMPLETE | 20/20 E2E written |
| Phase 8: Infrastructure | COMPLETE | 12 perf tests added |
| Phase 9: Paper Trading | **ACTIVE — REAL OANDA TRADES** | — |

---

## CURRENT STATE (as of 2026-03-26)

### Live Deployment
- **Backend**: https://lumitrade-engine-production.up.railway.app — HEALTHY, real OANDA trading
- **Frontend**: https://lumitrade-dashboard-production-0507.up.railway.app — LIVE, navy design
- **Railway project**: lumitrade (Pro plan, 2 services)
- **OANDA**: Practice account 101-001-37434000-001, $100,000 balance, REAL orders
- **Supabase**: Connected, signals + trades saving
- **Anthropic**: New API key active, Claude AI generating signals

### Trading Status
- **Engine is LIVE placing REAL orders on OANDA practice account**
- Claude AI scanning EUR/USD, GBP/USD, USD/JPY every 15 minutes
- Real OANDA orders with SL/TP (not simulated)
- 28 total trades placed (27 open, 1 closed at breakeven)
- Balance/equity updates every 5 seconds
- Dashboard polls every 2 seconds

### Critical Bug Fixes (2026-03-26 Session)
**Investigation revealed 5 critical trading engine bugs — all fixed:**

1. **Risk engine queried wrong table** (`open_positions` → `trades`)
   - Position count check always returned 0, allowing unlimited trades
   - `max_open_trades=3` was never enforced
   - Fixed: queries `trades` table, added per-pair limit (`max_positions_per_pair=1`), fail-closed on DB error

2. **OANDA response parsing — empty broker_trade_id**
   - Parser expected `tradeOpened.tradeID` but response nesting varied
   - All 28 trades had empty broker_trade_id, breaking position monitoring
   - Fixed: robust multi-fallback parser with logging (tradeOpened → tradeReduced → transaction ID)

3. **`get_pricing()` called with string instead of list**
   - `get_pricing(pair)` → `",".join("EUR_USD")` → `"E,U,R,_,U,S,D"` (invalid)
   - SL/TP checking silently failed on every position monitor cycle
   - Fixed: `get_pricing([pair])` + correct OANDA pricing response parsing

4. **Live P&L hardcoded to $0 in positions API**
   - Frontend positions route set `live_pnl_pips: 0`, `current_price: entry_price`
   - No current market prices were fetched
   - Fixed: added `/prices` endpoint to backend health server, positions API now calculates real unrealized P&L

5. **Position monitor skipped empty broker_trade_id trades**
   - Trades without broker_trade_id were neither "PAPER-" nor had valid IDs
   - They fell through all checks — never monitored, never closed
   - Fixed: empty broker_trade_id trades now checked via SL/TP price comparison

**Additional safeguards added:**
- `max_positions_per_pair: 1` — prevents stacking same pair
- `max_position_units: 500,000` — hard cap on position size
- Fail-closed on DB errors (was fail-open, defaulting to 0 positions)

### Files Changed
- `backend/lumitrade/config.py` — Added `max_positions_per_pair`, `max_position_units`
- `backend/lumitrade/risk_engine/engine.py` — Fixed table name, added per-pair check, max size cap, fail-closed
- `backend/lumitrade/execution_engine/oanda_executor.py` — Robust trade ID parsing with logging
- `backend/lumitrade/execution_engine/engine.py` — Fixed get_pricing() args, pricing response parsing, empty broker_id handling
- `backend/lumitrade/infrastructure/health_server.py` — Added `/prices` endpoint for live OANDA pricing
- `frontend/src/app/(dashboard)/api/positions/route.ts` — Real P&L calculation using backend pricing

---

### Previous Session Accomplishments (2026-03-24 to 2026-03-25)
- Full 8-agent audit (PM, UI/UX, Architect, Frontend, Backend, QA, DevOps, Security)
- Fixed 20+ critical bugs including RiskRejection type check, kill switch, auth
- Added 62 new tests (40 execution engine + 10 reconciler + 12 performance)
- Restored FDS navy design system, removed light mode
- Implemented SWR data fetching, toast notifications, signal filters
- Fixed Railway deployment (root directory + Dockerfile paths)
- Switched from simulated paper trades to REAL OANDA practice orders
- Added live unrealized P&L and daily P&L display
- Health server returns real latency/timing data
- Auth middleware with Supabase session validation

---

## Key URLs
| Resource | URL |
|----------|-----|
| Frontend | https://lumitrade-dashboard-production-0507.up.railway.app |
| Backend Health | https://lumitrade-engine-production.up.railway.app/health |
| Backend Prices | https://lumitrade-engine-production.up.railway.app/prices |
| Railway Project | https://railway.com/project/6a13a79e-54c8-48ef-9d7c-161ca4951b3c |
| Supabase | https://skrqpsubnenmreyjidyn.supabase.co |
| GitHub | https://github.com/Abenezer1244/Lumitrade |

## Key Credentials Location
- Backend env vars: Railway service vars (lumitrade-engine)
- Frontend env vars: Railway service vars (lumitrade-dashboard)
- OANDA Practice: account 101-001-37434000-001
- OANDA Live: account 001-001-19434175-002
- Anthropic API: New key set on Railway 2026-03-25

---

## What's Next
- [ ] Deploy fixes to Railway (backend + frontend)
- [ ] Close the 27 stale open positions on OANDA (manual or via script)
- [ ] Verify position monitor closes trades on SL/TP hit after deploy
- [ ] Verify live P&L displays correctly on dashboard
- [ ] Re-enable auth middleware (currently bypassed due to email rate limit)
- [ ] Set up custom SMTP for branded login emails (Lumitrade instead of Supabase Auth)
- [ ] Accumulate 50+ real trades for go/no-go gate
- [ ] Three.js background visibility on landing page sections
- [ ] Frontend design polish per user feedback
