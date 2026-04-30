# Lumitrade Backtest v2 Report — 2026-04-29
**Live-parity**. SL 3.0×ATR, max hold 24h, conf band 0.7-0.8, ADX regime gate, tiered risk 0.5/1.0/2.0%, friction modeled.

## Per-pair baseline (full history, all live filters on)

### USD_CAD
```
  Trades:        35 (W:19/L:16/BE:0)
  Win rate:      54.3%   95% CI: [38.2, 69.5]
  P&L:           $+4,138.70  (+4.1%)
  Profit factor: 1.96
  Expectancy:    $+118.25 / trade  (+0.441R)
  Avg W / Avg L: $+444 / $-268  (ratio 1.65)
  Max DD:        $1,120.21  (1.1%)
  Sharpe (ann):  1.76
  Sortino:       3.45
  Calmar / MAR:  2.09
  Recovery:      3.69
```

### USD_JPY
```
  Trades:        85 (W:32/L:52/BE:1)
  Win rate:      37.6%   95% CI: [28.1, 48.3]
  P&L:           $+394.30  (+0.4%)
  Profit factor: 1.04
  Expectancy:    $+4.64 / trade  (+0.027R)
  Avg W / Avg L: $+292 / $-172  (ratio 1.70)
  Max DD:        $2,927.72  (2.8%)
  Sharpe (ann):  0.10
  Sortino:       0.15
  Calmar / MAR:  0.07
  Recovery:      0.13
```

### BTC_USD (added 2026-04-29 — 12,434 H1 candles, 2024-04-30 to 2026-04-30)
```
  Trades:        123 (W:82/L:41/BE:0)
  Win rate:      66.7%   95% CI: [57.9, 74.4]
  P&L:           $-1,270.04  (-1.3%)
  Profit factor: 0.91
  Expectancy:    $-10.33 / trade  (-0.030R)
  Avg W / Avg L: $+156 / $-343  (ratio 0.45)
  Max DD:        $4,010.74  (4.0%)
  Sharpe (ann):  -0.27
  Sortino:       -0.34
  Calmar / MAR:  -0.16
  Recovery:      -0.32
```

**VERDICT: FAILS all 5 live thresholds → paper-only until BTC-specific filter stack is tuned.**

Live threshold checklist (same as USD_CAD/JPY criteria):
| Metric | BTC_USD | Threshold | Pass? |
|---|---|---|---|
| Profit factor | 0.91 | ≥ 1.50 | FAIL |
| Sharpe (ann) | -0.27 | ≥ 1.00 | FAIL |
| MAR | -0.16 | ≥ 0.50 | FAIL |
| MC P(profit) | 35.7% | ≥ 85% | FAIL |
| Max DD | 4.0% | ≤ 10% | PASS |

Root cause: W/L ratio of 0.45 — the forex filter stack wins small and loses big on BTC.
The trailing stop closes BTC winners too early (avg win $156) while the 3x ATR SL
allows full losses ($343 avg). This is the inverse of the desired R:R.

Key ablation insight: removing friction (spread $50 + slippage) improves P&L by +$1,512
and pushes PF to 1.02 — nearly all the loss is friction cost. Suggests BTC is borderline
if a tighter spread window can be found (e.g. trade only when BTC spread < $30).

## Walk-forward (6mo train / 3mo test rolling)

### USD_CAD

| Fold | Train PF | Train trades | Test PF | Test trades | Test P&L |
|---|---|---|---|---|---|
| 0 | 4.09 | 6 | 6.21 | 4 | $+236 |
| 1 | 2.24 | 7 | 999.00 | 3 | $+839 |
| 2 | 24.80 | 7 | 1.06 | 6 | $+98 |
| 3 | 1.57 | 9 | 1.55 | 3 | $+295 |
| 4 | 1.50 | 10 | 2.03 | 5 | $+510 |
| 5 | 1.97 | 9 | 0.00 | 5 | $-921 |

**OOS aggregate:** 6 folds, avg test PF 201.97, total OOS P&L $+1,056

### USD_JPY

| Fold | Train PF | Train trades | Test PF | Test trades | Test P&L |
|---|---|---|---|---|---|
| 0 | 2.48 | 13 | 1.24 | 10 | $+157 |
| 1 | 3.33 | 19 | 0.40 | 7 | $-620 |
| 2 | 0.73 | 17 | 39.37 | 11 | $+1,707 |
| 3 | 2.09 | 21 | 1.75 | 9 | $+636 |
| 4 | 2.54 | 23 | 0.19 | 10 | $-2,090 |
| 5 | 0.56 | 20 | 1.02 | 14 | $+35 |

**OOS aggregate:** 6 folds, avg test PF 7.33, total OOS P&L $-175

### BTC_USD

| Fold | Train PF | Train trades | Test PF | Test trades | Test P&L |
|---|---|---|---|---|---|
| 0 | 0.54 | 28 | 0.70 | 19 | $-602 |
| 1 | 0.74 | 38 | 0.26 | 10 | $-1,169 |
| 2 | 0.54 | 30 | 1.05 | 14 | $+71 |
| 3 | 0.73 | 26 | 3.97 | 9 | $+1,563 |
| 4 | 1.77 | 24 | 0.87 | 14 | $-134 |
| 5 | 2.90 | 28 | 0.71 | 13 | $-510 |

**OOS aggregate:** 6 folds, total OOS P&L $-781. Highly inconsistent — no edge present.

## Ablation — marginal contribution of each filter

### USD_CAD

| Variant | Trades | WR | PF | PF Δ | P&L | P&L Δ vs baseline |
|---|---|---|---|---|---|---|
| baseline | 35 | 54.3% | 1.96 | +0.00 | $+4,139 | $+0 |
| no_adx | 82 | 37.8% | 1.28 | -0.69 | $+3,176 | $-963 |
| no_confidence_band | 499 | 31.7% | 0.73 | -1.23 | $-28,756 | $-32,895 |
| no_session | 73 | 47.9% | 1.43 | -0.54 | $+5,147 | $+1,009 |
| no_17utc_cutoff | 35 | 54.3% | 1.96 | +0.00 | $+4,139 | $+0 |
| no_daily_loss | 35 | 54.3% | 1.96 | +0.00 | $+4,139 | $+0 |
| no_max_hold | 29 | 37.9% | 3.78 | +1.82 | $+12,316 | $+8,177 |
| no_min_sl | 35 | 54.3% | 1.96 | +0.00 | $+4,139 | $+0 |
| no_tiered_risk | 35 | 54.3% | 2.08 | +0.12 | $+11,163 | $+7,024 |
| no_friction | 35 | 54.3% | 2.35 | +0.39 | $+5,227 | $+1,088 |
| no_trailing | 35 | 45.7% | 1.87 | -0.10 | $+3,767 | $-372 |
| no_breakeven | 33 | 63.6% | 2.09 | +0.12 | $+4,773 | $+635 |
| no_cooldown | 35 | 54.3% | 1.96 | +0.00 | $+4,139 | $+0 |

*Filters with positive `P&L Δ` when REMOVED are dead-weight or harmful.*

### USD_JPY

| Variant | Trades | WR | PF | PF Δ | P&L | P&L Δ vs baseline |
|---|---|---|---|---|---|---|
| baseline | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_adx | 130 | 37.7% | 1.06 | +0.01 | $+932 | $+538 |
| no_confidence_band | 694 | 35.2% | 0.89 | -0.15 | $-12,146 | $-12,541 |
| no_session | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_17utc_cutoff | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_daily_loss | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_max_hold | 83 | 37.3% | 0.91 | -0.14 | $-856 | $-1,250 |
| no_min_sl | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_tiered_risk | 85 | 37.6% | 1.03 | -0.01 | $+912 | $+518 |
| no_friction | 85 | 37.6% | 1.16 | +0.12 | $+1,350 | $+956 |
| no_trailing | 82 | 20.7% | 0.91 | -0.13 | $-727 | $-1,121 |
| no_breakeven | 82 | 47.6% | 1.05 | +0.01 | $+616 | $+222 |
| no_cooldown | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |

*Filters with positive `P&L Δ` when REMOVED are dead-weight or harmful.*

### BTC_USD

| Variant | Trades | WR | PF | PF Delta | P&L | P&L Delta |
|---|---|---|---|---|---|---|
| baseline | 123 | 66.7% | 0.91 | +0.00 | $-1,270 | $+0 |
| no_adx | 191 | 63.9% | 0.92 | +0.01 | $-1,670 | $-400 |
| no_confidence_band | 1085 | 65.3% | 0.99 | +0.08 | $-1,031 | $+239 |
| no_session | 123 | 66.7% | 0.91 | +0.00 | $-1,270 | $+0 |
| no_17utc_cutoff | 123 | 66.7% | 0.91 | +0.00 | $-1,270 | $+0 |
| no_daily_loss | 123 | 66.7% | 0.91 | +0.00 | $-1,270 | $+0 |
| no_max_hold | 123 | 65.9% | 0.84 | -0.07 | $-2,294 | $-1,024 |
| no_min_sl | 123 | 66.7% | 0.91 | +0.00 | $-1,270 | $+0 |
| no_tiered_risk | 123 | 66.7% | 0.90 | -0.01 | $-4,078 | $-2,808 |
| **no_friction** | **123** | **65.9%** | **1.02** | **+0.11** | **$+242** | **$+1,512** |
| no_trailing | 96 | 17.7% | 0.78 | -0.13 | $-2,400 | $-1,130 |
| no_breakeven | 92 | 55.4% | 0.93 | +0.02 | $-1,109 | $+161 |
| no_cooldown | 123 | 66.7% | 0.91 | +0.00 | $-1,270 | $+0 |

**Key insight**: `no_friction` pushes PF to 1.02 (+$1,512). The $50 BTC spread dominates losses.
Trading only during low-spread windows (<$30) or using a tighter spread gate could flip BTC profitable.
The `no_trailing` result (WR collapses from 67% to 18%) confirms the trailing stop is critical —
it is converting many potential losses to wins, but the friction cost erases those gains.

## Monte Carlo bootstrap (10k resamples)

| Pair | P(profit) | DD 5% | DD median | DD 95% |
|---|---|---|---|---|
| USD_CAD | 93.5% | 0.6% | 1.4% | 3.0% |
| USD_JPY | 55.0% | 1.3% | 2.8% | 5.9% |
| BTC_USD | 35.7% | 1.9% | 4.0% | 8.0% |

## Methodology notes
- Entries placed at **open[i+1]** (not close[i]) to avoid look-ahead bias.
- Indicators use only data through bar i (verified by parity tests).
- Lesson filter (BLOCK/BOOST) deliberately **not applied** — rules were learned from live trades inside this window (forward-looking bias).
- Friction: spread cost (1.5p USD_CAD / 1.0p USD_JPY) + 0.5p slippage entry & exit + daily swap on holds >24h.
- Methodology grounded in Pardo (2008), Aronson (2007), Bailey & López de Prado (2014), Carver (2015), Chan (2013).
