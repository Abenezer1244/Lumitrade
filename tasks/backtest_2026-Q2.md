# Lumitrade Backtest v2 Report — 2026-04-25
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
  P&L:           $+393.88  (+0.4%)
  Profit factor: 1.04
  Expectancy:    $+4.63 / trade  (+0.027R)
  Avg W / Avg L: $+292 / $-172  (ratio 1.70)
  Max DD:        $2,928.08  (2.8%)
  Sharpe (ann):  0.10
  Sortino:       0.15
  Calmar / MAR:  0.07
  Recovery:      0.13
```

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
| 3 | 2.09 | 21 | 1.71 | 9 | $+602 |
| 4 | 2.52 | 23 | 0.19 | 11 | $-2,126 |
| 5 | 0.56 | 21 | 0.95 | 14 | $-99 |

**OOS aggregate:** 6 folds, avg test PF 7.31, total OOS P&L $-378

## Ablation — marginal contribution of each filter

### USD_CAD

| Variant | Trades | WR | PF | PF Δ | P&L | P&L Δ vs baseline |
|---|---|---|---|---|---|---|
| baseline | 35 | 54.3% | 1.96 | +0.00 | $+4,139 | $+0 |
| no_adx | 82 | 37.8% | 1.28 | -0.69 | $+3,176 | $-963 |
| no_confidence_band | 498 | 31.7% | 0.73 | -1.24 | $-28,869 | $-33,008 |
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
| no_adx | 130 | 37.7% | 1.02 | -0.03 | $+274 | $-120 |
| no_confidence_band | 694 | 35.2% | 0.89 | -0.15 | $-12,135 | $-12,528 |
| no_session | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_17utc_cutoff | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_daily_loss | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_max_hold | 83 | 37.3% | 0.91 | -0.14 | $-856 | $-1,250 |
| no_min_sl | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |
| no_tiered_risk | 85 | 37.6% | 1.03 | -0.01 | $+911 | $+517 |
| no_friction | 85 | 37.6% | 1.16 | +0.12 | $+1,350 | $+956 |
| no_trailing | 82 | 20.7% | 0.91 | -0.14 | $-756 | $-1,150 |
| no_breakeven | 82 | 47.6% | 1.05 | +0.01 | $+621 | $+227 |
| no_cooldown | 85 | 37.6% | 1.04 | +0.00 | $+394 | $+0 |

*Filters with positive `P&L Δ` when REMOVED are dead-weight or harmful.*

## Monte Carlo bootstrap (10k resamples)

| Pair | P(profit) | DD 5% | DD median | DD 95% |
|---|---|---|---|---|
| USD_CAD | 93.3% | 0.6% | 1.4% | 3.0% |
| USD_JPY | 55.0% | 1.3% | 2.8% | 5.8% |

## Methodology notes
- Entries placed at **open[i+1]** (not close[i]) to avoid look-ahead bias.
- Indicators use only data through bar i (verified by parity tests).
- Lesson filter (BLOCK/BOOST) deliberately **not applied** — rules were learned from live trades inside this window (forward-looking bias).
- Friction: spread cost (1.5p USD_CAD / 1.0p USD_JPY) + 0.5p slippage entry & exit + daily swap on holds >24h.
- Methodology grounded in Pardo (2008), Aronson (2007), Bailey & López de Prado (2014), Carver (2015), Chan (2013).
