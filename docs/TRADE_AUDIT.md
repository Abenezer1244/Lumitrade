# Lumitrade Trade Audit — 2026-04-20

**Dataset:** 103 closed trades, paper account `7a281498-2f2e-5ecc-8583-70118edeff28`
**Date range:** Mar 25 → Apr 20, 2026 (~26 days live)
**Source:** Supabase `trades` table (real OANDA fills)

---

## Headline Numbers

| Metric | Value | Verdict |
|---|---|---|
| Total P&L | **+$1,474.53** | Marginally profitable |
| Win rate | 43.7% (45W / 53L / 5BE) | Below target (50%+) |
| Profit factor | 1.045 | ⚠ Barely above breakeven (target 1.5+) |
| Expectancy | +$14.32 / trade | Thin edge |
| Avg win | $766.69 | Good |
| Avg loss | $623.14 | |
| Win/Loss ratio | 1.23 | Healthy |
| Max drawdown | **-$15,064.90** | 🔴 ~15% of $100K balance |
| Peak cumulative | +$13,344.76 | Gave back 89% of peak |
| Max win streak | 16 | |
| Max loss streak | 11 | 🔴 |

**Bottom line:** The system survived a near-catastrophe (-$15K drawdown from Mar 31–Apr 2) and has clawed back to +$1,474. Strategy changes over the last 2 weeks have produced 7 consecutive USD_CAD SELL wins. The edge is real but thin.

---

## ✅ WHAT'S WORKING

### 1. USD_CAD is the franchise pair — 66.7% WR, +$5,880
- **USD_CAD BUY:** 11W / 5L (68.8%), +$3,285
- **USD_CAD SELL:** 7W / 3L (63.6%), +$2,595
- Works in BOTH directions — rare. This is the only pair that passed 2-year backtest.
- Last 7 closed USD_CAD SELLs are all wins (Apr 15–20).

### 2. USD_JPY BUY is the other reliable setup — 60% WR, +$5,978
- 12W / 8L over 20 trades
- Already has a BOOST rule (`BUY:USD_JPY` — 84.6% WR on prior 13 trades)
- Asian session USD_JPY BUY is particularly strong

### 3. Session filters are directionally correct
| Session | Hours UTC | WR | P&L |
|---|---|---|---|
| **Asian** | 00–08 | **59.4%** | **+$7,868** |
| **London** | 08–13 | **53.8%** | **+$5,548** |
| NY overlap | 13–17 | 34.5% | -$5,304 |
| NY late | 17+ | **12.5%** | **-$6,637** |

The 17:00 UTC cut-off in `main.py:337` is doing work. Deleting the NY-late band would add ~$6.6K back.

### 4. Take profits, when hit, are 100% winners
- **TP_HIT:** 7/7 wins, +$8,281 (avg +$1,183 per TP)
- When the system sets a TP and it prints, the trade is pure green.
- Problem: only 7 of 103 trades hit TP. Turtle strategy (no fixed TP) dominates.

### 5. Long holds work; short holds don't
| Hold time | Trades | WR | P&L |
|---|---|---|---|
| < 30min | 8 | 12.5% | -$2,802 |
| 30min–2h | 21 | 19.0% | -$6,277 |
| 2h–6h | 33 | 45.5% | -$1,564 |
| 6h–24h | 34 | 55.9% | +$5,316 |
| **24h+** | 7 | **85.7%** | **+$6,802** |

Clear monotonic relationship: the longer we can keep a trade open, the more it wins. Trailing stops and no-fixed-TP Turtle behavior are earning their keep.

### 6. The 14 Trading Memory rules look accurate
All 3 BLOCK rules (GBP_USD, EUR_USD, SELL-wildcard) match the post-hoc data. The learning layer is doing its job.

### 7. Friday is magic — 90.9% WR, +$11,197
20W / 2L out of 22 trades. This is where most of the P&L lives.

---

## 🔴 WHAT NEEDS IMPROVEMENT

### 1. High-confidence signals are actively destructive
This is the #1 finding and is backwards from every assumption.

| Confidence | Trades | WR | P&L |
|---|---|---|---|
| 0.00–0.65 | 5 | 40.0% | +$278 |
| 0.65–0.70 | 35 | 48.6% | +$841 |
| **0.70–0.80** | **42** | **50.0%** | **+$6,731** ← sweet spot |
| **0.80–0.90** | **21** | **23.8%** | **-$6,375** 🔴 |

**Action:** Reject signals with confidence ≥ 0.80. Or better — require a second confirming signal above 0.80. This finding was noted in `main.py:423-425` ("Fixed 1x position size — no confidence scaling") but the signals themselves are still *entering* at 0.80+.

### 2. Tuesdays are a massacre — 10% WR, -$12,738
20 Tuesday trades, 2 wins, 18 losses. If we'd skipped every Tuesday we'd be up ~$14K instead of +$1.5K. Worth investigating:
- Is there a recurring Tuesday news/economic event?
- Is Tuesday overlap with NY-late hours driving this?
- **Quick action:** Add a Tuesday 17:00+ block; consider Tuesday 13:00+ block.

### 3. The best recent streak has data-quality bugs
Last 7 USD_CAD SELL winners all show:
- `pnl_pips: 0.0` (USD value is correct, but pip calc didn't run on close)
- `exit_reason: UNKNOWN` (reconciler isn't classifying exit)
- `session: ""` (empty — session field never populated)
- `take_profit: 0.0` (Turtle no-TP is fine, but confusing in UI)
- `duration_minutes: None` (never computed)

**Action:** Fix the close path to populate `pnl_pips`, `exit_reason`, `session`, `duration_minutes`. 23 of 103 trades have `exit_reason = UNKNOWN` — that's 22% of the audit trail broken.

### 4. Stop-loss distribution looks wrong for the edge
- SL median: **20.8 pips**, mean 20.9 (pretty tight)
- TP median: 33.2 pips, mean 40.9
- R:R median: **1.5** (target was 3x ATR per recent commit `29083f0`)

Short holds (<2h) have 19% WR. That's the signature of getting stopped out by noise. Tighten nothing; **widen SL to 25–30 pips minimum on majors, 35+ on JPY**, and verify the "3x ATR SL" commit actually landed.

### 5. Hour 07:00 UTC is the hidden loser inside London
| Hour | Trades | WR | P&L |
|---|---|---|---|
| 06:00 | 5 | 60% | +$1,450 |
| **07:00** | **6** | **16.7%** | **-$2,809** |
| 08:00 | 9 | 55.6% | +$1,610 |

07:00 UTC is right before London open — liquidity is thin, spreads widen. **Action:** block 07:00–07:59 UTC trades.

### 6. Currency-specific blocks need promoting to hard filters
| Pair | Trades | WR | P&L | Current status |
|---|---|---|---|---|
| GBP_USD | 14 | **7.1%** | **-$5,753** | BLOCK rule exists, pair removed |
| EUR_USD | 13 | 30.8% | -$2,398 | BLOCK rule exists, pair removed |
| NZD_USD | 7 | 28.6% | -$906 | Still active 🔴 |
| USD_CHF | 11 | 36.4% | -$1,219 | Pair removed per progress.md |
| AUD_USD | 7 | 42.9% | -$444 | Marginal |

**Action:** Drop NZD_USD from the scan list. AUD_USD is break-even — keep on short leash or widen the session filter to Asian-only (which is already in `main.py:347`).

### 7. SL_HIT rate is too high
- SL_HIT: 73 of 103 trades (70.9%), WR 38.4%, -$9,895
- This means most trades end in a loss via stop-out, and when they do, we lose more often than the coin flip.
- Combined with the "short hold = lose" finding, this confirms the SL is too tight.

### 8. SELL direction is still net losers
- 29.6% WR, -$5,705 over 27 trades
- Recent (Apr 15–20) flip has been all SELL wins for USD_CAD — 7 in a row
- But earlier data: SELL: USD_JPY 25%, AUD_USD 0%, NZD_USD 0%, GBP_USD 0%, EUR_USD 0%
- The SELL-wildcard BLOCK was the right call. Only USD_CAD SELL should be unblocked.

### 9. Drawdown risk is live
- $15K max drawdown on $100K = **15.0% peak-to-trough**
- Happened Mar 31 → Apr 2 (2 days). Daily loss circuit breaker at -$2,000 was added *after* this incident (`main.py:315–329`).
- **Action:** reduce to -$1,500 daily, or add weekly loss limit at -$3,500.

### 10. Position sizing is not adaptive
Still using fixed 1x size (comment at `main.py:423–425`). That's correct based on the confidence-inverse finding. But:
- No reduction after a loss streak (hit 11 in a row)
- No Kelly-fraction sizing by pair
- **Action:** cut size by 50% after 3 consecutive losses, restore on first win.

---

## 📊 Recent Strategy Pivot (working well)

Last 3 commits show the right direction:
- `ca64000` IG Markets / tastyfx for XAU_USD gold
- `21f9f10` ADX regime filter (trend vs range)
- `29083f0` Backtest-driven: USD_CAD only, 3x ATR SL

Since those landed (Apr 15+):
- 7 closed trades, all USD_CAD SELL, all wins (+$3,043 cumulative)
- No losses
- Hold times 4–7 hours (matches the "long hold wins" pattern)

**Keep this.** Don't re-broaden to other pairs until USD_CAD has 20+ more wins.

---

## 🎯 Prioritized Actions

### P0 — This week
1. **Fix exit-reason logging** — 22% of trades show `UNKNOWN`; can't optimize what we can't measure. Check `execution_engine/oanda_executor.py` and `state/reconciler.py` close paths.
2. **Reject confidence ≥ 0.80** — 23.8% WR at that level means the scanner is over-confident on bad setups.
3. **Verify the 3x ATR SL commit is live** — median SL is still 20.8 pips which looks tight. `risk_engine/filters.py` or position_sizer.
4. **Block 07:00 UTC and Tuesday 13:00+** — two of the clearest money pits in the data.

### P1 — Next 2 weeks
5. Drop NZD_USD; put AUD_USD on Asian-only.
6. Add post-loss size reduction (50% after 3 consecutive losses).
7. Tighten daily loss limit from -$2,000 to -$1,500.
8. Populate `session`, `duration_minutes`, and `pnl_pips` fields on every close.

### P2 — When USD_CAD has 20+ more wins
9. Re-enable USD_JPY BUY with full confidence (already BOOSTed).
10. Experiment with larger size on `BUY:USD_JPY:ASIAN` pattern (the 84.6% WR BOOST rule).
11. Add weekly loss limit.

---

## Go/No-Go Gate Status (QTS 8.2)

From 103-trade sample:
- ✅ Sample size ≥ 72 (gate 1)
- ✅ Profit factor ≥ 1.0 (gate 2, marginal at 1.045)
- ❌ Profit factor ≥ 1.5 (stretch gate)
- ✅ Win rate ≥ 40% (gate 3)
- ❌ Win rate ≥ 50% (stretch gate)
- ✅ Max drawdown < 20% (gate 4, at 15%)
- ❌ Max drawdown < 10% (stretch gate)
- ✅ No catastrophic single-day loss > 10% (gate 5, worst was -9% on Mar 31)
- ❌ Win/loss streak imbalance — 11-loss streak is at the pain threshold

**Verdict:** Paper-gate passed at minimum thresholds, **not ready for live** until P0 and P1 actions land. Target: 50+ USD_CAD-focused trades with the new regime filter, then re-audit.
