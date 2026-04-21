# Lumitrade Progress

## Current Status
- **Phase**: 9 — Paper Trading (ACTIVE)
- **Mode**: PAPER on OANDA practice account
- **Balance**: ~$101,474 (103 closed trades, +$1,474 cumulative)
- **Pairs trading**: USD_CAD + USD_JPY (re-enabled 2026-04-21)
- **Engine**: Running on Railway, per-pair session windows
- **Strategy**: Turtle (no fixed TP) + ADX regime filter + Trading Memory + Visual Charts + TradingView consensus
- **Deploy Rule**: Only deploy 13:00-23:59 UTC (never during trading hours)

## Session 2026-04-21 (cont.) — Deploy + verify + Railway webhook fix

### Critical infra bug discovered and fixed
Railway's GitHub auto-deploy was **broken since 2026-04-13**. Every
commit pushed between Apr 13 and Apr 21 was silently ignored by Railway
(no rebuilds triggered). Discovery path:

1. Audit + 5 bug fixes pushed 05:37–06:05 UTC — NO deploys
2. After restart, logs showed `pairs: ["USD_CAD"]` and `count: 50`
   (OLD code) — meaning none of the fixes were live.
3. `railway deployment list` confirmed zero successful builds between
   2026-04-13 and 2026-04-21.
4. `railway up --service lumitrade-engine --detach --ci` forced a
   fresh build from local source, unblocking deploy.
5. Root cause via Railway GraphQL: `serviceInstances.source.repo` was
   `null`. Both `lumitrade-engine` and `lumitrade-dashboard` had been
   disconnected from GitHub at some point.
6. Fixed via `serviceConnect` mutation on `lumitrade-engine`, setting
   `repo: "Abenezer1244/Lumitrade"`. (Dashboard is on Vercel, left as-is.)
7. Verified with test commit `0e9cf5a` — auto-deployed in ~3 min.

### All 5 bug fixes now LIVE in production (confirmed by logs)
- `"pairs": ["USD_CAD", "USD_JPY"]` — USD_JPY wired
- `"count": 250` on H1, `120` on M15/H4 — Bug 1 candle fix
- First MULTI-tier signal ever: `SELL 0.83, strategies: [EMA_TREND, MOMENTUM]`
  (pre-fix, EMA_TREND was ALWAYS HOLD because ema_200=0 gate)
- New trades have `session: "LONDON"` populated — Bug 5 close-path fix
- `lesson_filter_boost_matched` firing for new specificity-aware rules

### First new-code trades opened 2026-04-21 08:16-08:17 UTC
| Pair | Dir | Entry | SL | Conf | Session |
|---|---|---|---|---|---|
| USD_CAD | SELL | 1.366 | 1.36878 | 0.83 | LONDON |
| **USD_JPY** | **BUY** | **159.197** | **158.73** | **0.77** | **LONDON** |

First USD_JPY trade in ~2 weeks. SL distance 46.7 pips (was ~20 pip
median pre-fix — the 3x ATR math is now working because ema_200
no longer forces HOLD).

### Auto-deploy now verified working
- Test commit `0e9cf5a` pushed → Railway auto-built → deployed in ~3 min
- Future `git push origin main` will auto-deploy (no more `railway up` needed)

### Tools / side installs
- Impeccable skill pack installed (`npx skills add pbakaus/impeccable -y -g`)
  — 17 frontend design skills symlinked to Claude Code via `~/.agents/skills/`.
  Notable: `audit`, `polish`, `typeset`, `colorize`, `layout`.

### Commits this session (in order)
```
48d1792 fix: fetch 250 H1 candles so EMA(200) actually computes
1abe5a0 fix: show both trade directions in Claude prompt
25d2f2e fix: lesson_filter honors specificity
877bff1 fix: populate session, duration, pips, and exit_reason on close
c38f793 docs: 103-trade audit report
0f7df9d chore: track migration 014 in supabase/migrations/ format
60fac64 feat: re-enable USD_JPY trading alongside USD_CAD
4eb58d3 docs: update progress.md
68a922c chore: cache bust for Railway redeploy
0e9cf5a chore: test github-railway auto-deploy after reconnecting source repo
```

## Session 2026-04-20 → 2026-04-21 — Audit + 5 Bug Fixes + USD_JPY re-enable

### 103-trade audit findings (docs/TRADE_AUDIT.md)
- Win rate 43.7%, PF 1.045, expectancy +$14/trade
- USD_CAD is the franchise pair: 66.7% WR, +$5,880 (both directions)
- Confidence 0.80+ paradox: 23.8% WR (worse than 0.70-0.80 at 50%)
- Max DD -$15,065 (Mar 31 - Apr 2)
- 22% of trades had `UNKNOWN` exit_reason (attribution debt)

### 5 Bugs Fixed + Pushed
1. **EMA200 silently 0 on every signal** — candle_fetcher was pulling 50 candles; EMA(200) needs 200. Fixed to 250 H1. Unlocks MULTI-strategy tier in quant engine.
2. **Trade history prompt bias** — `_get_trade_history` pulled last 10 trades regardless of direction, causing Claude to hallucinate pessimistic records. Fixed to query each direction independently.
3. **lesson_filter specificity** — broad wildcard BLOCK could suppress pair-specific BOOST. Fixed to honor specificity.
4. **Stale trading_lessons** — rebuilt from 103 trades. New `SELL:USD_CAD:LONDON` BOOST (5W/1L, 83%) now live.
5. **Exit attribution** — added `TRAILING_STOP` ExitReason, populate session/duration/pips on every close. Backfilled 53 historical trades. Migration 014 applied via Supabase CLI.

### USD_JPY re-enabled
- Commit `60fac64` — added to `config.pairs`
- Rationale: `BUY:USD_JPY:NY` is 71% WR / +$4,694 (BOOST live)
- `SELL:USD_JPY` at 25% WR / 4 trades — watch; auto-BLOCKs on next loss (hits 5-sample threshold)

### Deploy log
- 5 fix commits pushed 2026-04-21 05:37 UTC (during trading hours, user accepted trade-off)
- Migration 014 applied via `supabase db push --linked` 2026-04-21 05:58 UTC
- USD_JPY commit pushed ~06:05 UTC (before USD_CAD window at 08:00 UTC — safe)
- All commits: `48d1792` `1abe5a0` `25d2f2e` `877bff1` `c38f793` `0f7df9d` `60fac64`

### New tests added (21 passing, zero regressions)
- `tests/unit/test_indicators.py` — 4 tests guarding EMA200 + candle count contract
- `tests/unit/test_time_utils.py` — 12 tests incl. cross-module session boundary contract
- `tests/unit/test_lesson_filter.py` — 5 specificity precedence cases

### New scripts (reusable)
- `backend/scripts/trade_audit.py` — full audit against any account
- `backend/scripts/rebuild_trading_lessons.py` — wipe + rebuild lessons from trades
- `backend/scripts/backfill_trade_attribution.py` — fix historical UNKNOWNs
- `backend/scripts/verify_ema200_fix.py` — live OANDA smoke test
- `backend/scripts/verify_trade_history_fix.py` — prompt output check
- `backend/scripts/verify_lesson_filter_live.py` — 7-case filter validation

## Gold Trading Plan — PAUSED until 2026-05-20

### IBKR account approved
- Account number: **U25411010** (IBKR Pro, Live)
- Regulator: SEC + FINRA + CFTC + NFA (US entity)
- SIPC protection: $500K + $30M excess Lloyd's

### Current permissions (2026-04-21)
- ✅ Stocks, Forex, Event Contracts — Enabled
- 🟡 Bonds, Mutual Funds, Crypto — can Request
- 🔴 Futures, Futures Options, Options, Metals, Warrants, SSF — **30-day cooldown** (auto-declined on initial application)
- ❌ Complex/Leveraged ETPs — Unavailable (Incompatible Objectives)

### Why cooldown — initial financial profile too weak
Need to update in IBKR → Settings → Account Settings → Financial Information:
- Investment Objective: add **Speculation** and **Active Trading**
- Risk Tolerance: **High**
- Futures experience: 1-2 years (if any backtesting/simulation done)
- Accurate liquid net worth + annual income

### Next steps (in order)
1. **2026-04-21 (today):** User updates financial profile (5 min). No deposit needed.
2. **2026-04-21:** User enables Paper Trading Account (free, instant). Gets `DU…` paper account number.
3. **2026-04-21+:** Claude builds `backend/lumitrade/infrastructure/ibkr_client.py` against paper account, wires GLD as a test. Has MGC-ready code waiting.
4. **2026-05-20 (Day 30):** Re-request Futures permission in IBKR. Profile should now qualify.
5. **2026-05-20+:** Fund account ($2,000-5,000 recommended for MGC margin + buffer). Swap GLD → MGC in config.
6. **2026-05-21+:** Paper-trade `/MGC` micro gold for 1 week minimum before any live allocation.

### Rejected alternatives (documented for future)
- **Capital.com** — not available to US retail
- **tastyfx** — forex-only, no metals; US citizenship required for tastytrade futures
- **Plus500 US** — only .NET/FIX APIs (no Python); 2-week integration cost
- **Eightcap** — US retail via SCB offshore = KYC/FATCA risk; no retail REST API

### Gold instrument plan (when unlocked)
- **Primary:** `/MGC` (Micro Gold Futures, COMEX) — 10 oz, $1/tick = $10/contract, 23h trading
- **Margin:** ~$300-400 per MGC contract
- **Stop-loss:** 3x ATR ($/oz) — same logic as USD_CAD
- **API:** TWS socket via `ib-async` Python library
- **Deployment:** IB Gateway (headless Docker sidecar) on Railway, ~$5/mo extra

## Previous Sessions

## Session 2026-04-03 — New Strategy: Adaptive Trading Memory + Visual Charts

### Major Strategy Overhaul
Two AI learning systems deployed:

**System 1: Trading Memory** — learns from every trade
- `trading_lessons` table stores hard rules (BLOCK/BOOST)
- After every trade close: extracts pattern, queries history, creates rules
- BLOCK (< 35% WR over 5+ trades): hard filter BEFORE AI sees the setup
- BOOST (> 65% WR over 5+ trades): injected into AI prompt as preferred setups
- 9 rules active (5 seed + 4 auto-learned):
  - BLOCK: All SELL (0% WR), GBP_USD (7% WR), EUR_USD (31% WR)
  - BOOST: BUY USD_JPY (85% WR, 13 trades), BUY USD_CAD (70% WR, 10 trades)
  - NEUTRAL: BUY USD_JPY:LONDON (50% WR, 4 trades), BUY USD_CAD:ASIAN (1 trade)

**System 2: Visual Chart Analysis** — Claude sees charts like a trader
- Generates 3-panel candlestick PNG (H4/H1/M15) with EMAs, Bollinger, S/R, RSI
- Sent to Claude as base64 image alongside text data (multimodal)
- Dark theme matching Lumitrade design (confirmed 80-88KB charts generating)
- Falls back to text-only if chart fails

### Other Fixes (Apr 1-3)
- FIFO violation fix: single order with scaled size instead of multiple orders
- Daily P&L reset at midnight UTC (was blocking trading with stale -$10K)
- Session time filter: only trade 00-13 UTC (Asian + London)
- Removed GBP_USD, EUR_USD, USD_CHF from pairs (data-driven)
- Removed confidence size multiplier (80%+ conf had worst WR at 16.7%)
- Daily loss circuit breaker at -$2,000
- Tighter TP guidance (1x-1.5x ATR instead of 3x)
- OANDA per-trade unrealizedPL for accurate dashboard P&L
- `/trade/{id}/close` and `/oanda-trades` endpoints added

### New Features Built (Apr 2-3)
- **Trade Journal** — weekly AI summaries with pair analysis (real data)
- **AI Coach** — chat with Claude about your trades (real Claude API)
- **Intel Report** — weekly intelligence with session heatmaps (real data)
- **API Access** — real API key generation, /v1/signals and /v1/trades endpoints
- **Marketplace** — rich preview UI (Phase 3)
- **Copy Trading** — rich preview UI (Phase 3)
- **Backtesting** — rich preview UI (Phase 3)

### 72-Trade Deep Analysis (basis for strategy changes)
| Direction | Trades | WR | P&L |
|-----------|--------|-----|-----|
| BUY | 57 | 49.1% | +$6,483 |
| SELL | 13 | 0% | -$8,203 |

| Session | WR | P&L |
|---------|-----|-----|
| Asian (00-08) | 73.9% | +$9,592 |
| London (08-13) | 50.0% | +$2,342 |
| NY (13-17) | 34.8% | -$3,279 |
| NY Late (17-21) | 12.5% | -$6,637 |

| Pair | WR | P&L |
|------|-----|-----|
| USD_JPY | 73.3% | +$7,604 |
| USD_CAD | 71.4% | +$3,398 |
| AUD_USD | 50.0% | +$409 |
| NZD_USD | 40.0% | -$23 |
| USD_CHF | 36.4% | -$1,219 |
| EUR_USD | 30.8% | -$2,398 |
| GBP_USD | 7.1% | -$5,753 |

### New System Early Results (2 trades — need 20+ for conclusions)
| Metric | Old System | New System |
|--------|-----------|-----------|
| Win Rate | 44.9% | 50.0% |
| Avg Win | +$817 | +$446 |
| Avg Loss | -$665 | -$315 |
| Win/Loss Ratio | 1.23 | 1.42 |
| Losses smaller | | Yes |

### Concerns to Monitor (revisit after 20 trades)
1. SL too tight on loss (10p for JPY — should be 15-20p minimum)
2. Only London session tested — need Asian session data
3. USD_JPY:LONDON at 50% WR could auto-BLOCK if it drops — would block best pair during London
4. TP hit rate still 0% — both exits via trailing stop
5. Need to verify chart analysis is actually improving signal quality vs text-only

## Previous Sessions

### Session 2026-03-30
- Light theme overhaul, brand audit, 20+ icon swaps
- Reconciler P&L fix, trade counter fix

### Session 2026-03-27
- Ghost trade elimination, real OANDA P&L
- 8 pairs + gold, trailing stops, confidence multiplier

### Session 2026-03-26
- 20+ commits, 5 bug fixes, all 14 stubs eliminated, Mission Control

### Session 2026-03-25
- Full 8-agent audit, 30+ fixes, 50 tests, real OANDA trading live

## What's Next
- [ ] Let new system run 20+ trades, then re-analyze
- [ ] Monitor Trading Memory for false BLOCK rules on good pairs
- [ ] Consider raising minimum SL to 15p (forex) / 20p (JPY)
- [ ] Re-enable auth middleware (bypassed due to email rate limit)
- [ ] Set up custom SMTP for branded login emails
- [ ] Three.js background on all landing sections
- [ ] Create proper logo graphic
- [ ] When ready: switch to LIVE with $100, max_risk_pct=0.5%
