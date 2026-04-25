# Lumitrade Progress

## Current Status
- **Phase**: 9 — Paper Trading + LIVE prep (Monday 2026-04-27 cutover planned)
- **Mode**: env=PAPER on Railway, dashboard armed=LIVE → effective=PAPER (dual-switch holding)
- **OANDA account**: switched from practice `101-001-37434000-001` to LIVE `001-001-19434175-002` (unfunded; user fund $100 over weekend)
- **Pairs trading**: USD_CAD only when env flips LIVE (USD_JPY auto-excluded by `live_pairs` filter); both in paper
- **Engine**: Running on Railway, dual-switch (env+dashboard) live mode, PaperExecutor activated, per-pair max_hold (USD_CAD=96h)
- **Strategy**: Turtle (trailing only) + ADX regime + Trading Memory + Visual Charts + TradingView consensus, 0.80 conf cap, 0.25% risk for live
- **Deploy Rule**: Only 13:00-23:59 UTC

## Session 2026-04-25 — 2-yr backtest, dual-switch live mode, OANDA cutover prep

### Part 1 — Live-parity 2-year backtest infrastructure
Discovery audit found old backtest predated **every** post-audit filter (3.0× ATR SL,
24h max hold, conf band 0.70-0.80, ADX gate, tiered risk, trailing-stop logic).
26 filter gaps + 17 divergent params identified. Built `backend/scripts/backtest_v2.py`
(~1300 lines) at live parity, with walk-forward (6mo/3mo, 8 folds), Monte Carlo
bootstrap (10k), per-filter ablation (13 variants), Sharpe/Sortino/Calmar/MAR/
expectancy/Wilson-CI/bootstrap-CI, friction model (1.5p USD_CAD spread / 1.0p
USD_JPY / 0.5p slippage / daily swap >24h), and a look-ahead bias self-test.
35 unit tests including ADX correctness, indicator non-leakage, full quant logic
parity, and walk-forward fold structure.

Methodology research subagent grounded gates in Pardo (2008), Aronson (2007),
Bailey & López de Prado (2014), Carver (2015), Chan (2013).

### Part 2 — 2-year backtest verdict (2024-04-24 → 2026-04-24)

| Pair | PF | Sharpe | MAR | MC P(profit) | Live status |
|---|---|---|---|---|---|
| USD_CAD | **1.96** | **1.76** | **2.09** | **93.5%** | ✅ Approved |
| USD_JPY | **1.04** | **0.10** | **0.07** | **55.0%** | 🔴 Paper-only |

USD_JPY's 2-year evidence under the current filter stack disagrees with its
24-trade live-paper streak (+$5,499). Backtest wins per PRD §3.4.

### Part 3 — Phase 5 production changes (commit `119b4e0`)
- `config.live_pairs = ["USD_CAD"]` — enforced at startup when TRADING_MODE=LIVE
- `config.max_hold_hours_for(pair)` — USD_CAD gets 96h, others stay 24h
  (ablation showed lifting CAD cap took PF 1.96 → 3.78, +$8.2K/2yr)
- Removed dead `>=0.90 → 2% risk` tier (couldn't fire under 0.80 confidence cap)
- PRD §3.4 Backtest Verification subsection added

### Part 4 — risk_engine test mock fixes (commit `7d075cd`)
18 pre-existing test_risk_engine.py failures fixed — `_make_config()` was
missing `max_positions_per_pair` and other numeric fields, causing
`int < MagicMock` TypeErrors. RE-019 updated for 0.80 cap, RE-020
rewritten for the removed dead 2% tier.

### Part 5 — CI workflows (commits `ecf98de` → `dc38198`)
- `.github/workflows/quarterly-backtest.yml` — auto-runs Jan/Apr/Jul/Oct 1
  at 14:00 UTC, opens PR with verdict, labels CRITICAL on threshold breach
- `.github/workflows/post-live-validation.yml` — fires once on 2026-05-16
  14:00 UTC (3 weeks post-go-live), compares live USD_CAD trades vs
  backtest predictions, opens PR with CONFIRMED/DRIFTING/DIVERGED verdict
- `backend/scripts/compare_live_to_backtest.py` — comparison helper
- 3 GitHub repo secrets set (OANDA_API_KEY_TRADING, SUPABASE_URL,
  SUPABASE_SERVICE_KEY) via stdin pipe
- 8 PR labels created
- Repo permission "Allow Actions to create PRs" enabled via API
- Smoke-test successful: PR #17 auto-created and merged the testing flow

### Part 6 — Dual-switch live mode + PaperExecutor activation (commit `e70ba7e`)
**Major bug found and fixed:** `PaperExecutor` was instantiated since Phase 5 but
never called — `execute_order()` always routed to `_oanda_executor` regardless
of TRADING_MODE. So all 112 paper trades were real OANDA API calls (just to
the practice account when OANDA_ENVIRONMENT=practice).

Fixed by adding `effective_trading_mode()` config method that returns LIVE
iff BOTH env_var AND dashboard ModeToggle agree on LIVE. `execute_order`
now branches on it. `risk_engine._load_user_settings` populates
`config.db_mode_override` from settings JSON, hot-reloaded on every signal
evaluation. ModeToggle.tsx shows "Engine env: X · Effective: Y" status
banner with a yellow warning when env=PAPER locks the LIVE button.

14 new routing tests covering all combinations of env+db modes.

### Part 7 — OANDA live cutover prep
- New live OANDA account: `001-001-19434175-002` (USD, unfunded)
- New live API token verified against api-fxtrade.oanda.com → HTTP 200
- Railway env updated: `OANDA_API_KEY_TRADING`, `OANDA_API_KEY_DATA`,
  `OANDA_ACCOUNT_ID=001-001-19434175-002`, `OANDA_ENVIRONMENT=live`
- TRADING_MODE kept PAPER on Railway
- Engine confirmed connected to new live account: `oanda_connected balance=0.0000`
- Dashboard ModeToggle armed via Supabase: `mode=LIVE, riskPct=0.25,
  maxPositions=1, maxPerPair=1, confidence=70`
- `scripts/go_live.sh` written with 5 preflight checks (deploy window,
  weekend guard, balance >= $50, dashboard mode=LIVE, current TRADING_MODE
  != LIVE) + typed-`GO` confirmation + log tailing

### Part 8 — Senior-trader review caveats
After explicit user request, ran a 4-decade-trader-voice analysis. Key concerns
flagged: 35-trade sample below Aronson 100-trade threshold, Wilson CI on win rate
[38.2, 69.5]% includes losing strategies, walk-forward fold 5 was PF 0.00
(strategy may be in regime decay), friction at $100 starter eats ~7% of
risk-per-trade per round trip, fontconfig errors in production logs may mean
chart-mode is broken, no catastrophic-event protection (volatility/news),
Friday outsized P&L is a fragile-edge signature. Recommended: 2-3 weeks of
paper-on-live observation before flip OR flip Monday at 0.25% risk and
accept first month is tuition. User chose Monday flip.

### Commits this session
```
119b4e0 feat(backtest): live-parity v2 backtest + USD_CAD-only live, per-pair max_hold
7d075cd test(risk): fix mock setup + update RE-019/RE-020 for 0.80 cap
ecf98de ci: quarterly backtest + post-live-validation workflows
081c2a9 ci(backtest): use absolute paths to fix cross-step path resolution
dc38198 ci(backtest): self-create labels, fault-tolerant PR creation
e70ba7e feat(execution): activate PaperExecutor + dual-switch mode (env AND db)
9aef895 chore: add scripts/go_live.sh for safe Monday cutover
```

### Monday 2026-04-27 — go-live plan
1. User funds OANDA $100 (must happen weekend)
2. Sunday 22:00 UTC: forex reopens, paper-on-live trades start firing on
   new account, broker_trade_id starts with `PAPER-`
3. Monday ~20:00 UTC (1 PM PT): user runs `bash scripts/go_live.sh`,
   typed-GO confirms after preflights, env flips to LIVE
4. Watch for `live_pair_filter_applied paper_only_pairs=['USD_JPY']
   live_pairs=['USD_CAD']` in Railway logs
5. First real OANDA fill (broker_trade_id NOT starting with `PAPER-`)

### Watch list for Monday + first week
- Live spread on $100 account vs 1.5p USD_CAD assumption — if 2-3x worse, halt
- Claude validator rejection rate (currently unknown — production-only data)
- Lesson filter blocking rate
- First 5 trades' P&L vs 22-pip-SL × 0.25% risk = $0.25 per loss expected
- The post-live validation workflow auto-fires 2026-05-16 14:00 UTC

## Session 2026-04-21/22 — Frontend critique refactor + 106-trade audit + engine tuning

### Part 1 — Frontend critique (2-round)
Ran `/critique` skill twice (impeccable). Score went from 21/40 → 33/40 on Nielsen
heuristics; impeccable detector 5 findings → 0.

**7-phase refactor landed in one commit `f2a5b04`:**
1. `/typeset` — 5 font families → 2 (Satoshi + JetBrains Mono). Purged 15 files of
   inline `fontFamily` overrides. Removed PT Serif, Nunito, Space Grotesk, DM Sans.
2. `/distill` — Sidebar 12 → 5 items (removed P2/P3 coming-soon placeholders).
   Pricing tier neon glow → restrained "Recommended" label.
3. `/layout` — Dashboard 10 → 6 panels with 4-tier hierarchy (hero Account+Today →
   focal OpenPositions → secondary Signals + rail Risk/News/Halt).
4. `/quieter` — Removed gradient "AI precision." clip-text; Three.js scroll spacer
   400vh → 150vh; bounce arrow → opacity pulse; FAQ `max-height` → `grid-template-rows`;
   LoadingScreen `width` → `scaleX`; pure-black modals → tinted navy.
5. `/clarify` — Every settings slider gained Recommended + concrete tradeoff copy.
6. `/harden` — Reduced-motion `useReducedMotion()` on Sidebar pulse. ModeToggle
   PAPER→LIVE now requires typed phrase `START LIVE TRADING` + risk-ack checkbox.
7. `/polish` + quick wins — Killed perpetual BUY/SELL badge bob, radar spin,
   opacity breathe (OpenPositionsTable). Glass hover-lift universal → opt-in
   `.glass-interactive`. Footer `#333` → tokenized. AccountPanel pipe → bullet.
   Login emerald glow → brand token. KillSwitch "Reset" → "Dismiss" with
   clarifying copy. Settings default `riskPct` 1.0 → 0.5 to match landing FAQ.
   TopBar purged 7 stale PAGE_TITLES entries. Go/No-Go got tooltip + aria.

Light-theme-default kept at user's explicit direction (flagged as downstream
semantic-color consequence — `#DC2626` loss on light ≠ `#FF4D6A` loss on dark).

Commit `f2a5b04` also included 14 previously-untracked components (ThemeToggle,
LoadingSpinner, ConfirmDialog, ModeToggle, auth/login, e2e tests, etc.) that
had never been on origin/main. Without them CI would have failed.

### Part 2 — 106-trade audit (replaces the 103-trade report)
Ran `backend/scripts/trade_audit.py`. Full data (Mar 26 – Apr 21):

| Metric | Value |
|---|---|
| Net P&L | +$904.11 |
| Win rate | 43.4% |
| Profit factor | **1.026** (barely edge-positive) |
| Max DD | −$15,065 (Apr 2) |
| Peak equity | $13,345 |
| Final cumulative | $904 (down $12,441 from peak) |

**Confidence model inverted above 0.80:**
- 0.70–0.80: **48.8% WR / +$6,455** (the sweet spot)
- 0.80–0.90: **27.3% WR / −$5,620**
- 0.90+: 0% WR / −$1,050

**Hold time is crucial:**
- 0–30min: 12.5% WR / −$2,802
- 6–24h: 55.6% WR / +$5,795
- 24h+: 85.7% WR / +$6,802

The engine was force-closing trades at 6h before they matured.

**Exit mix:** 81% of trades die on SL (86 SL_HIT vs 11 trailing-stop wins vs
7 TP_HIT). Trailing mechanic is 100% WR when it fires — don't touch what's
working.

**Tuesday drill-down:** 23 Tues trades / −$13,309, but 83% of that was one
week (W14 = −$11,081), and 12 of 23 were on pairs already excluded
(GBP/EUR/CHF/NZD). Post-restriction Tuesday sample = 6 trades — too small
to blanket-block. Added `blocked_weekdays_utc` config knob but default `[]`.

### Part 3 — Engine tuning (commit `6948951`)
Pushed **06:15 UTC inside trading hours** at user's explicit direction.
Expect engine restart to have missed any in-flight signal.

```python
# backend/lumitrade/config.py
max_confidence:     0.95 → 0.80   # rejects inverted-confidence bucket
max_hold_hours:     6   → 24     # lets profitable trades mature
blocked_weekdays_utc: []          # dormant knob, ready to flip to [1]
```

```python
# backend/lumitrade/main.py
# new weekday-blackout check in _signal_to_trade_loop (no-op while list is empty)
```

Wiring verified:
- `max_confidence` → `_check_confidence_ceiling` in risk_engine:400, invoked at
  risk_engine:105 with early-return rejection.
- `max_hold_hours` → force-close check in execution_engine:231.
- `blocked_weekdays_utc` → new check in main.py:308-316.

**Already in place, verified against audit:**
- GBP_USD already excluded via `pairs = [USD_CAD, USD_JPY]`.
- SL is ATR × 3.0 per-pair (`quant_engine._calculate_sl`) — audit's
  recommendation 8 was already implemented.
- Trailing stop tuned per-pair (`TRAIL_ACTIVATION_PIPS`), 100% WR —
  not touched.

**Deferred (separate decisions needed):**
- Restrict SELL to USD_CAD only (non-USD_CAD SELL = 0 wins / 12 trades).
- Blackout 13:00–17:00 UTC (only ≥17 currently blocked).

### Side cleanups
- Deleted 22 shell-quoting garbage files (`0`, `25`, `EMA200`, `{c}`,
  `backend/list[Trade]`, `../,`, `../clearInterval(interval)`, etc. — all
  0-byte shell-accident artifacts).

### Commits this session
```
f2a5b04 refactor(frontend): apply design critique — fonts, layout, motion calm, safety ceremony
6948951 perf(engine): tune from 106-trade audit — confidence cap, hold-time, weekday knob
```

### Watch list for next session
- Trade volume should drop from the 0.80 ceiling — don't over-interpret.
- Re-audit after ~30 more trades. If 0.80 cap proves too tight and 0.70–0.80
  samples well, consider raising back to 0.85.
- Watch whether 24h hold reveals TP-tier winners that used to be force-closed.
- If Tuesday drawdown recurs on USD_CAD/USD_JPY specifically, flip
  `blocked_weekdays_utc=[1]`.
- Re-run `/critique` on the frontend after some live user time to spot
  new polish opportunities.

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
