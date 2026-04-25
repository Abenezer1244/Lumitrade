# AMD Sweep-Reversal Backtest — 2026-04-25 — 🔴 REJECTED

> **DO NOT ADD TO PRODUCTION.** This satellite test failed every live threshold
> by a wide margin and was deliberately rejected. Kept as evidence of why the
> Inner Circle Trader (ICT) "Power of Three" / Asia-London-NY model does not
> hold up on the same 2-year USD_CAD data the main strategy was validated on.
>
> | Metric | Main strategy | AMD | Threshold |
> |---|---|---|---|
> | Profit factor | 1.96 | **0.75** | ≥ 1.5 |
> | Sharpe (ann) | 1.76 | **−1.68** | ≥ 1.0 |
> | MAR | 2.09 | **−0.43** | ≥ 0.5 |
> | MC P(profit) | 93.5% | **0.8%** | ≥ 85% |
> | Net P&L (2yr) | +$4,139 | **−$20,090** | > 0 |
>
> Per-trade R-expectancy: AMD = −0.16R, main strategy = +0.44R (4× better).
> Sweeps are roughly coin flips, not reliable reversal signals — momentum > mean
> reversion at session-boundary liquidity pools on this pair, this period.

**Strategy under test:** Asia (00-08 UTC) builds range. London/NY (08-17 UTC) sweeps Asia high/low. Enter against the sweep at next bar's open. SL = sweep wick + 5 pip buffer. TP = opposite Asia extreme. One trade per UTC day max. Force exit at 17:00 UTC.
**Friction:** ON (1.5p USD_CAD spread, 0.5p slippage)

## Live thresholds (PRD §3.4) for comparison
- Profit factor ≥ 1.5
- Sharpe (annualized) ≥ 1.0
- MAR ≥ 0.5
- Monte Carlo P(profit) ≥ 85%

## Per-pair results

### USD_CAD — 🔴 FAILS one or more live thresholds
```
  Trades:        308 (W:115/L:193/BE:0)
  Win rate:      37.3%   95% CI: [32.1, 42.9]
  P&L:           $-20,090.30  (-20.1%)
  Profit factor: 0.75
  Expectancy:    $-65.23 / trade  (-0.159R)
  Avg W / Avg L: $+516 / $-411  (ratio 1.25)
  Max DD:        $23,633.34  (23.6%)
  Sharpe (ann):  -1.68
  Sortino:       -2.42
  Calmar / MAR:  -0.43
  Recovery:      -0.85
```

**Monte Carlo:** P(profit)=0.8%, 5%-DD=11.2%, 95%-DD=35.3%

## Methodology notes
- Sweep = candle wick BEYOND Asia extreme + body close BACK INSIDE range.
- Entry at NEXT BAR'S OPEN to avoid look-ahead bias.
- Reuses `backtest_v2.py` data loading, metrics, friction model, Wilson CI.
- This is a SATELLITE TEST — not a replacement for the main strategy.
