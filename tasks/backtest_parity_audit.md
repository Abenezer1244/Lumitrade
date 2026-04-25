# Backtest Parity Audit (Phase 1 of forex re-backtest project)

**Live source files reviewed**
- `backend/lumitrade/main.py` (1–684)
- `backend/lumitrade/config.py` (1–197)
- `backend/lumitrade/risk_engine/engine.py` (1–672)
- `backend/lumitrade/risk_engine/position_sizer.py` (1–70)
- `backend/lumitrade/risk_engine/calendar_guard.py` (1–87)
- `backend/lumitrade/risk_engine/correlation_matrix.py` (1–190)
- `backend/lumitrade/ai_brain/quant_engine.py` (1–305)
- `backend/lumitrade/ai_brain/lesson_filter.py` (1–179)
- `backend/lumitrade/ai_brain/scanner.py` (1–641)
- `backend/lumitrade/ai_brain/confidence.py` (1–208)
- `backend/lumitrade/data_engine/indicators.py` (1–146)
- `backend/lumitrade/data_engine/regime_classifier.py` (1–130)
- `backend/lumitrade/execution_engine/engine.py` (1–737)

**Backtest under audit:** `backend/scripts/backtest.py` (1–665)

The backtest predates: ADX regime gate, the new SL multiplier (1.5x → 3.0x), the new max_hold_hours (6 → 24), the new max/min confidence band (0.70–0.80), the lesson filter, the confidence adjuster, the correlation multiplier, the per-pair session windows in `_pair_hours`, the 17–23 UTC dead-zone block, the daily loss circuit breaker, the H4 trend gate, the spread filter, the cooldown semantics, the breakeven stop, and the rebuilt pair list (USD_CAD + USD_JPY only).

---

## A. Filters present in LIVE but missing from backtest

### A1. ADX regime filter (regime-aware strategy voting)
- **Live source:** `ai_brain/quant_engine.py:54–80`
- **What it does:** ADX ≥ 25 → only EMA Trend + Momentum vote (Bollinger disabled); ADX < 25 → only Bollinger + Momentum vote (EMA Trend disabled). Backtest runs all three strategies in every regime, so it allows BB-revert against trend and EMA-trend in chop — exactly the trades production blocks.
- **Backtest impact:** Removes a class of low-quality trades. Adding it should raise win rate / profit factor and reduce trade count.
- **Implementation cost:** moderate (need to add ADX(14) computation; pandas-ta available, or hand-roll Wilder DI/DX).

### A2. Confidence ceiling at 0.80
- **Live source:** `risk_engine/engine.py:104–108, 400–414`; `config.py:82` (`max_confidence = 0.80`)
- **What it does:** Rejects signals with `confidence_adjusted > 0.80`. The 106-trade audit found 80%+ confidence had 27.3% WR / −$5,620.
- **Backtest impact:** Backtest has no Claude confidence number at all — but the quant `score` (line 332–343 of backtest) IS the analog. Live caps the equivalent of "score > 0.80" → backtest is letting the worst-performing band through.
- **Implementation cost:** trivial (add a single `if score > 0.80: continue`).

### A3. Confidence floor at 0.70
- **Live source:** `risk_engine/engine.py:98–102, 376–398`; `config.py:76` (`min_confidence = 0.70`)
- **What it does:** Rejects signals with confidence < 0.70 (or < 0.80 if risk_state == CAUTIOUS).
- **Backtest impact:** Backtest's effective floor is the quant Tier-2 threshold of 0.55 (line 343) — far below live. Adding it removes mediocre trades.
- **Implementation cost:** trivial.

### A4. Per-pair session windows ("`_pair_hours`")
- **Live source:** `main.py:357–362, 371–372`
  - USD_JPY: 0–17 UTC
  - USD_CAD: 8–17 UTC
  - AUD_USD: 0–8 UTC
  - NZD_USD: 0–8 UTC
- **What it does:** Outside that window, the pair is skipped. Note: the backtest's `SESSION_HOURS` (line 44–49) has USD_JPY at 0–8, NOT 0–17. This is a **divergent** value, so it also appears in section B.
- **Backtest impact:** USD_JPY in particular is being denied 9 hours of its live window (8–17 UTC = London + NY overlap). This will materially change the USD_JPY result.
- **Implementation cost:** trivial (one dict update).

### A5. 17–23 UTC dead-zone block (global)
- **Live source:** `main.py:351–354` (`if current_hour >= 17: continue`); `config.py:85` (`no_trade_hours_utc = [17,18,19,20,21,22,23]`); `risk_engine/engine.py:416–429` (re-enforced)
- **What it does:** After 17 UTC nothing scans — late NY + dead zone.
- **Backtest impact:** Some pairs in the backtest already cap at 17 via `SESSION_HOURS`, but USD_CAD's 8–17 already lines up. The redundancy doesn't add edge for those — but the rule needs to be present so that weekend candles, holidays, or post-17 prints don't slip in.
- **Implementation cost:** trivial.

### A6. Weekday blackout
- **Live source:** `main.py:308–316`; `config.py:86–92` (`blocked_weekdays_utc` — currently `[]`)
- **What it does:** Skip scanning on listed weekdays. Default empty, but the knob exists.
- **Backtest impact:** With current `[]` value, no impact on results. Should still be implemented for parity if/when the knob is flipped.
- **Implementation cost:** trivial.

### A7. Daily loss limit circuit breaker (−$2000)
- **Live source:** `main.py:329–343`
- **What it does:** If daily P&L < −$2000, all trading halts for the rest of the day.
- **Backtest impact:** Caps catastrophic days. Adding it will reduce max drawdown and may slightly reduce returns. Mar 31 −$11,081 day would have been clipped at −$2000.
- **Implementation cost:** trivial (track running daily P&L by candle date; reset at UTC midnight).

### A8. Confidence-tiered position sizing
- **Live source:** `risk_engine/engine.py:519–558`
  - `confidence ≥ 0.90` → 2.0% risk
  - `confidence ≥ 0.80` → 1.0% risk
  - else → 0.5% risk
- **What it does:** Tiered risk %. Backtest uses flat 1.5% (line 27 `RISK_PCT = 0.015`).
- **Backtest impact:** Most live trades land in the < 0.80 bucket → 0.5% risk, not 1.5%. Backtest is taking 3x the live position size. **This is the single biggest divergence by money exposed.**
- **Implementation cost:** trivial once you have a "confidence" proxy (use the quant score from line 332 of backtest).

### A9. Correlation-based size reduction
- **Live source:** `risk_engine/engine.py:162–184`; `risk_engine/correlation_matrix.py:145–189`
- **What it does:** When opening a new position correlated with an open one, multiplies size by `1.0 − (max_abs_corr × 0.5)`. AUD_USD/NZD_USD correlation is 0.90 → opening one halves the other's size. EUR_USD/USD_CHF at −0.90 same effect.
- **Backtest impact:** Backtest opens one position at a time (sequential, single-pair loop), so cross-pair correlation never fires. Multi-pair concurrency is not modeled at all. Adding it is only material if you also add concurrent positions across pairs.
- **Implementation cost:** moderate (requires multi-pair concurrent simulation loop, not the current per-pair sequential loop).

### A10. Lesson filter (BLOCK / BOOST rules)
- **Live source:** `ai_brain/scanner.py:169–207`; `ai_brain/lesson_filter.py:30–140`
- **What it does:** Pulls `trading_lessons` from Supabase keyed by (pair, direction, session). If a BLOCK rule matches, the pair direction is skipped entirely. Currently has rules like `BUY:USD_JPY` BOOST (84.6% WR) and active SELL:USD_JPY blocks when WR < 35%.
- **Backtest impact:** Lessons are derived from live trades, so applying them to a 2-year backtest is **circular reasoning**. Recommend (b) leave them off but document — see section D. If you want to recreate them, run an unbiased backtest first, then retro-apply rules, then re-run as a forward walk-forward.
- **Implementation cost:** significant if synthesized; trivial if ignored (see section D).

### A11. H4 trend alignment gate
- **Live source:** `ai_brain/scanner.py:479–519`
- **What it does:** SELL forbidden when H4 EMA20 > EMA50 > EMA200 (full bull). BUY forbidden when fully bearish. Note: this gate is **bypassed when a chart is present** (line 378–388), which it always is in production. So it only fires on chart-fallback paths.
- **Backtest impact:** In production this path is rarely hit. For backtest, since there is no chart, the rule WOULD apply on every trade — but most trades that pass quant Tier-1 (multi-strategy agreement) already align with H4 EMAs anyway, so the gate is mostly redundant with the quant `EMA_TREND` strategy. Low impact, but a true-parity backtest should add it.
- **Implementation cost:** moderate (need separate H4 candle ingestion; backtest currently reads only H1).

### A12. Indicator alignment confidence penalty
- **Live source:** `ai_brain/confidence.py:42–54, 95–128`
- **What it does:** Without chart, scores 5 indicators (RSI, MACD hist, EMA20 vs 50, EMA50 vs 200, price vs BB mid) for direction agreement. < 60% alignment shaves confidence by up to 25%.
- **Backtest impact:** Same as A11 — production usually has a chart so the penalty is bypassed. For backtest, this would replace some signals with "below-floor confidence" rejections.
- **Implementation cost:** moderate (and likely unnecessary if you simulate the chart-mode path that production actually takes).

### A13. Spread filter (Risk Engine + Scanner)
- **Live source:** `scanner.py:154–158` (early skip > 5 pips for forex, > 200 for XAU); `risk_engine/engine.py:436–448`
- **What it does:** Rejects signals when spread > 5 pips (forex) or > 200 (gold).
- **Backtest impact:** Backtest reads CSV close prices only — has no spread series. Cannot model. Recommend (c) assume neutral / always-pass — see section D.
- **Implementation cost:** untestable without spread data.

### A14. News blackout (CalendarGuard)
- **Live source:** `risk_engine/engine.py:450–462`; `risk_engine/calendar_guard.py:25–86`
- **What it does:** Blocks 30 min before / 15 min after HIGH-impact news, 15 min before MEDIUM.
- **Backtest impact:** Backtest has no news history. Recommend (a) stub with a downloaded ForexFactory or Investing.com calendar over the 2-year window. If unavailable, (c) ignore — assume neutral.
- **Implementation cost:** moderate (needs historical calendar CSV ingestion + parser).

### A15. Risk/Reward ratio gate
- **Live source:** `risk_engine/engine.py:464–502`; `config.py:102` (`min_rr_ratio = 1.5`)
- **What it does:** If TP ≠ 0, requires `(reward / risk) ≥ 1.5`. Skipped when TP = 0 (trailing-stop / Turtle mode — what live currently uses).
- **Backtest impact:** Live currently ALWAYS sets TP = 0 (`quant_engine.py:137`), so this gate is a no-op in production. Backtest already has no TP, so parity OK. **No action needed.**

### A16. Min SL pips (15) and min TP pips (15)
- **Live source:** `config.py:103–104` (`min_sl_pips = 15.0`, `min_tp_pips = 15.0`)
- **What it does:** Floor on stop distance. Note: the backtest already has a similar floor at line 490–491 (`if sl_pips < 10: continue`) but at **10**, not 15.
- **Backtest impact:** Need to lift floor to 15. Affects only trades where ATR(14) × 1.5 → between 10 and 15 pips. With the new live multiplier of 3.0× (not 1.5×) this rarely binds.
- **Implementation cost:** trivial.

### A17. Per-pair max positions (10) + global max positions (100)
- **Live source:** `risk_engine/engine.py:282–328`; `config.py:93–94`
- **Backtest impact:** Backtest is single-position by construction. No-op until multi-position simulation is added.
- **Implementation cost:** trivial once concurrency is added.

### A18. Cooldown 5 minutes per pair
- **Live source:** `risk_engine/engine.py:330–374`; `config.py:101` (`trade_cooldown_minutes = 5`)
- **What it does:** After a trade closes on a pair, no new trade on that pair for 5 minutes.
- **Backtest impact:** Backtest does have a cooldown (line 471: `(candle.time - cooldown_until).total_seconds() < 300`) — same 5-min, **already in parity**.

### A19. Already-in-position skip (FIFO)
- **Live source:** `scanner.py:160–167`
- **What it does:** Scanner skips a pair entirely if there's already an open trade on it.
- **Backtest impact:** Backtest already enforces this implicitly (single open trade per pair). **In parity.**

### A20. Breakeven stop at +15 pips (gold +300)
- **Live source:** `execution_engine/engine.py:419–450`
- **What it does:** When trade is +15 pips in profit, move SL to entry. Backtest already does this — line 408–411 with `BREAKEVEN_PIPS = 15` for all pairs. **In parity** for the threshold; not in parity for gold (`+300` live vs `15` per-pair table in backtest), but gold isn't backtested.

### A21. Trailing stop activation
- **Live source:** `execution_engine/engine.py:340–353, 452–495`
  - USD_JPY: 20 pips
  - USD_CAD: 18 pips (backtest: 18 — match)
  - AUD_USD: 15 (match)
  - NZD_USD: 15 (match)
  - **USD_JPY: 20 in live, 20 in backtest — match**
- **What it does:** Once profit ≥ activation pips, trail SL behind current price by the original SL distance.
- **Backtest impact:** Trail-distance logic in backtest (line 414 / 439) is subtly different: after first activation, the backtest hardcodes `PIP_SIZE × TRAIL_ACTIVATION_PIPS` as the trail distance, while live uses the **original** entry-to-SL distance every time. With 3.0× ATR live SL, the live trail is much wider than backtest's 18-pip cap → backtest is taking profit too quickly on big moves.
- **Implementation cost:** trivial.

### A22. Forced max-hold close (24 hours, not 6)
- **Live source:** `execution_engine/engine.py:224–263`; `config.py:108` (`max_hold_hours = 24`)
- **What it does:** Force-closes any trade older than 24 hours.
- **Backtest impact:** Backtest has `MAX_HOLD_CANDLES_H1 = 6` (line 33), only 6 hours. The 106-trade audit explicitly said: 0–6h bucket = 31% WR / −$11,692 (trades being severed too early). Forcing 6h in backtest will reproduce the bad result the live system was tuned away from.
- **Implementation cost:** trivial — change constant 6 → 24. **High-priority fix.**

### A23. Risk state machine (CAUTIOUS / DAILY_LIMIT / WEEKLY_LIMIT / EMERGENCY_HALT / CIRCUIT_OPEN)
- **Live source:** `risk_engine/engine.py:265–280, 376–398`; `config.py:96–97` (5%/10% limits)
- **What it does:** State transitions raise confidence floor (+0.10 in CAUTIOUS) or block trading entirely.
- **Backtest impact:** Backtest has no state machine. Daily/weekly limits never fire. Recommend modeling at least DAILY_LIMIT (5% drawdown halts day) — this is part of A7 above.
- **Implementation cost:** moderate.

### A24. Position size cap (500,000 units)
- **Live source:** `config.py:95` (`max_position_units = 500_000`); `risk_engine/engine.py:187–199`
- **What it does:** Hard cap on units regardless of risk %.
- **Backtest impact:** Backtest already has `MAX_UNITS = 500_000` (line 28) — **in parity**.

### A25. Quant Tier-2 single-strategy threshold (0.65)
- **Live source:** `quant_engine.py:111–126`
- **What it does:** Solo strategy with no opposition needs score ≥ 0.65 to fire (matches backtest line 342).
- **Backtest impact:** Backtest matches. **In parity.**

### A26. Quant strategy regime filter — Bollinger disabled in trend
- **Live source:** `quant_engine.py:65–69`
- This is the same as A1 but worth restating: with ADX ≥ 25, BB_REVERT can no longer cast a vote at all. Backtest's BB_REVERT will fire continuously even in strong trends → produces fade-the-trend trades that live no longer takes.

---

## B. Parameters that DIVERGE between live and backtest

| Parameter | Live value | Backtest value | Source live | Source backtest |
|---|---|---|---|---|
| Pairs scanned | `["USD_CAD","USD_JPY"]` (XAU added if Capital configured) | `["USD_JPY","USD_CAD","AUD_USD","NZD_USD"]` | `config.py:70` | `backtest.py:23` |
| Risk per trade | tiered 0.5 / 1.0 / 2.0% by confidence | flat 1.5% | `risk_engine/engine.py:546–551` | `backtest.py:27` |
| ATR SL multiplier | **3.0×** | **1.5×** | `quant_engine.py:289` | `backtest.py:488` |
| Max hold hours | **24** | **6** | `config.py:108` | `backtest.py:33` |
| Min confidence floor | 0.70 | none (effective 0.55 via quant Tier-2) | `config.py:76` | `backtest.py:343` |
| Max confidence ceiling | 0.80 | none | `config.py:82` | (absent) |
| USD_JPY session window (UTC) | **0–17** | **0–8** | `main.py:358` | `backtest.py:45` |
| USD_CAD session window | 8–17 | 8–17 | `main.py:359` | `backtest.py:46` (match) |
| AUD_USD session window | 0–8 | 0–8 | `main.py:360` | `backtest.py:47` (match) |
| NZD_USD session window | 0–8 | 0–8 | `main.py:361` | `backtest.py:48` (match) |
| Min SL pips | 15 | 10 | `config.py:103` | `backtest.py:490` |
| Trailing-stop trail distance after activation | original SL distance (entry→SL) | hardcoded `PIP_SIZE × TRAIL_ACTIVATION_PIPS` (18–20 pips) | `execution_engine/engine.py:457–462` | `backtest.py:414, 439` |
| Breakeven threshold | 15 pips (300 for XAU) | 15 pips (flat for all pairs) | `execution_engine/engine.py:422` | `backtest.py:31` |
| ADX regime filter | active (ADX ≥ 25 selects strategy set) | absent | `quant_engine.py:54–80` | (absent) |
| Daily loss limit | $2000 hard halt + 5% RiskState DAILY_LIMIT | none | `main.py:330`; `config.py:96` | (absent) |
| Spread max | 5 pips forex / 200 XAU | none (CSV has no spread) | `scanner.py:155`; `risk_engine/engine.py:432–448` | (absent) |
| Cooldown after close | 5 minutes | 5 minutes (`< 300` seconds) | `config.py:101` | `backtest.py:471` (match) |
| Starting balance | OANDA-real (queried each cycle) | $100,000 fixed | `main.py:319–325` | `backtest.py:26` |
| 17–23 UTC global block | yes (`if current_hour >= 17`) | partial — only via `SESSION_HOURS` upper bound | `main.py:351` | `backtest.py:467` |
| Quant takes-profit | TP=0 (trailing only) | TP unused (trailing only) | `quant_engine.py:137` | `backtest.py` (no TP set) — match |
| Indicator timeframe | H1 (`data_engine/engine.py:140` notes "primary") | H1 | both — match |
| EMA200 warmup | full series via pandas-ta | first 200 candles skipped (line 386) | `indicators.py:85` | `backtest.py:386` |

---

## C. Things the backtest does that LIVE does NOT

1. **Hardcoded $100,000 starting balance.** Live always queries OANDA. Should be a parameter, not a constant. Compounded results over 2 years diverge dramatically based on this.
2. **Session windows that contradict live.** Backtest USD_JPY = 0–8 UTC; live = 0–17 UTC. **Backtest is starving USD_JPY of London + NY hours**, which is exactly where the live BUY:USD_JPY:NY BOOST rule (71% WR, +$4,694) operates.
3. **5-minute cooldown after every trade close** — actually matches live, no divergence (kept for completeness).
4. **Trail distance hardcoded at 18–20 pips after activation** instead of using the original entry→SL distance. Once a 3.0×ATR SL is involved, this means the backtest gives back far less profit on winners than live, distorting the average win.
5. **Single-pair sequential loop.** Backtest runs USD_JPY end-to-end, then USD_CAD, etc. — equity is shared but trades never overlap. Live can hold 10 positions per pair / 100 globally, with correlation-aware sizing. This affects compounding behavior and drawdown shape.
6. **No trade journal / lesson generation.** Live closes a trade → triggers `LessonAnalyzer` → updates `trading_lessons`. Backtest has no feedback loop, which is correct for a strategy backtest, but it means the run cannot replicate a live system that *learns* over the same period.
7. **No reconciliation or ghost-trade checks.** Backtest assumes 100% fill at the candle close. Live has slippage, OANDA rejections, partial fills, circuit-breaker-induced rejections — none of these are simulated.
8. **`MAX_HOLD_CANDLES_H1 = 6`** — explicitly contradicts the live `max_hold_hours = 24` set after the 106-trade audit. This is the single largest "wrong direction" in the backtest. (Already in B, listed here because it's a behavior, not just a parameter.)
9. **Symmetric breakeven for all pairs.** Live has gold-specific 300-pip breakeven; backtest uses 15 across the board. Only matters if XAU is added to backtest.
10. **No real-balance dynamic risk %.** Live's risk_pct depends on confidence at signal time; backtest uses a fixed 1.5% off the running balance.

---

## D. Things that cannot be backtested deterministically

| Item | Live source | Recommendation |
|---|---|---|
| **Claude AI signal validation (entry-time second opinion)** | `scanner.py:316–423`, `ai_brain/claude_client.py` | (b) **Ignore and assume positive** — every quant signal that fires in backtest is treated as approved. Justification: Claude is currently a filter/approver, not the originator. Production data shows Claude rarely overrides quant on a live chart. Optionally also produce a (c) "Claude-rejects-30%" sensitivity run for a worst-case bound. |
| **Consensus engine (second Claude pass on the proposal)** | `main.py:394–410` | Same as above — (b) assume pass. |
| **Chart vision analysis (TradingView screenshot to Claude)** | `scanner.py:238–266` | (b) Assume pass. The H4 trend gate that depends on chart-mode (`scanner.py:378`) is also bypassed in production whenever chart is present, so the gate is effectively dormant. |
| **News blackout (CalendarGuard)** | `risk_engine/calendar_guard.py` | (a) **Stub with historical economic calendar.** Use ForexFactory CSV (free, available 2-year history) or Investing.com export. Map to currencies and apply 30-min before / 15-min after on HIGH impact. If calendar fetch is too costly, (c) ignore — but document the bias. |
| **Sentiment analyzer** | `ai_brain/sentiment_analyzer.py` (called from `scanner.py:283–292`) | (c) Ignore — its output only adjusts confidence by ±0.10, and a backtest without it gives a slightly more conservative confidence. |
| **Spread filter (5 pips forex / 200 XAU)** | `scanner.py:155`, `risk_engine/engine.py:436–448` | (c) **Assume neutral / always-pass.** OANDA H1 CSV doesn't carry spread. Optionally model a fixed spread cost (1.5 pips USD_CAD, 1.0 USD_JPY) deducted from each entry/exit for a more honest equity curve. |
| **Lesson filter (BLOCK / BOOST rules from prior live trades)** | `ai_brain/lesson_filter.py` | (b) **Ignore.** The rules were learned FROM live trades; applying them to a backtest that pre-dates those trades is forward-looking bias. Best to backtest *without* the lesson filter, then synthesize lessons from the backtest output, then forward-walk-test. |
| **Subagent analyst briefing** | `scanner.py:275–282` | (c) Ignore. |
| **Circuit breaker for OANDA API failures** | `execution_engine/engine.py:88–105`; `circuit_breaker.py` | (c) Ignore — assume 100% fills (already what backtest does). Adds slippage assumption only. |
| **Confidence adjuster (6 factors)** | `ai_brain/confidence.py` | (b) Approximate — apply only spread penalty (skip via D-spread row) and indicator alignment (which is largely captured by the quant score itself). Most factors require chart-mode bypass anyway. |
| **OANDA realized P&L vs computed P&L** | `execution_engine/engine.py:534–569` | Backtest must compute P&L itself (no broker round-trip). Document that backtest ignores swap, financing, and commissions. Add a per-trade $0.50–$1.00 cost assumption if conservative. |
| **Risk monitor subagent (every 30 min on open positions)** | `main.py:540–590` | (c) Ignore — it does not place trades, only emits warnings. |
| **Daily loss limit ($2000) circuit breaker** | `main.py:330` | (a) **Implement** — easy to track running daily P&L over the candle stream. Worth it because real live results will respect this and backtest should too. |

---

## E. Recommended order of attack for Phase 2

Numbered by **impact / effort** ratio. Each fix is one self-contained edit unless noted. Do them in this order so the largest distortions go away first.

1. **Lift `MAX_HOLD_CANDLES_H1 = 6` to 24** (backtest.py:33). Single biggest live↔backtest divergence; explicitly tuned away from in the 106-trade audit. 1-line change, massive directional impact.
2. **Change ATR SL multiplier 1.5 → 3.0** (backtest.py:488). The 1.5× was the *cause* of the −$3.4K → +$11K USD_CAD swing the live system was retuned around. 1-line change.
3. **Fix USD_JPY session window 0–8 → 0–17** (backtest.py:45) AND keep the 17 UTC global cap. Restores 9 hours/day of London + NY overlap that live uses for USD_JPY.
4. **Add confidence floor 0.70 + ceiling 0.80** on the quant `score`. Use the same `score` value the quant returns at line 332–343 — anything below 0.70 → skip; above 0.80 → skip. Two `if` statements.
5. **Switch from flat 1.5% risk to confidence-tiered risk** (0.5 / 1.0 / 2.0% by quant score band). Match live's `_determine_risk_pct` table.
6. **Implement ADX(14) regime gate** in the quant evaluation (mirror `quant_engine.py:54–80`). Disable BB in trend, EMA in range. Wilder DI/DX, ~30 lines of code, no extra data needed (already have H/L/C).
7. **Fix trailing-stop trail distance** to use original entry→SL distance (not hardcoded pips). One conditional change at backtest.py:414 and :439.
8. **Add daily $2000 loss limit circuit breaker.** Track running daily P&L; once <−$2000, skip all signals for that UTC day. Reset on date change.
9. **Lift `min_sl_pips` 10 → 15** (backtest.py:490). Trivial.
10. **Make starting balance configurable, not constant** — accept CLI arg or env var so backtest can match live OANDA balance per period.
11. **Walk-forward / out-of-sample split** — split the 2-year window into 6×4-month folds, optimize on each, test on the next. (Methodology, not a parity issue, but mandatory before trusting any result.)
12. **Add transaction-cost assumption** — flat 1.5 pips spread cost per round-trip (USD_CAD), 1.0 (USD_JPY). Conservative; matches OANDA practice account median.
13. **(Optional, expensive)** Historical news calendar ingestion for CalendarGuard parity. Defer until items 1–12 are done — at that point, decide whether news blackout meaningfully changes results.
14. **(Optional, requires multi-pair simulation rewrite)** Concurrent multi-pair loop with correlation-aware sizing. Defer — only worth it if items 1–12 still leave a result that the user wants to validate against the multi-pair production behavior.

Items 1–10 are all trivial (single-line or single-block edits) and together close ~90% of the parity gap. Items 11–14 are the methodology + remaining 10%.
