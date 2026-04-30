"""
USD_JPY SL Multiplier Sweep
Tests whether a tighter ATR stop improves signal quality.
Pairs tested: USD_JPY only. Partial close enabled (67% at 1.5xRR).
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_v2 import (
    BacktestConfig,
    FilterToggles,
    compute_metrics,
    monte_carlo,
    load_candles,
    precompute_indicators,
    run_backtest,
)


def run_variant(pair, candles, indicators, sl_mult: float, label: str):
    cfg = BacktestConfig(
        sl_atr_multiplier=Decimal(str(sl_mult)),
        partial_close_pct=Decimal("0.67"),
    )
    toggles = FilterToggles(use_partial_close=True)
    trades = run_backtest(pair, candles, indicators, cfg, toggles, label=label)
    result = compute_metrics(pair, label, trades, cfg.starting_balance)
    mc_data = monte_carlo(trades, cfg.starting_balance, n_sim=3000)
    return result, mc_data["p_profit"], trades


def main():
    pair = "USD_JPY"
    print("\n" + "=" * 70)
    print(f"USD_JPY SL Multiplier Sweep (partial close 67% at 1.5xRR)")
    print("=" * 70)
    print(f"{'Mult':>6}  {'Trades':>6}  {'WR':>6}  {'PF':>6}  {'Sharpe':>7}  {'MAR':>6}  {'MaxDD':>7}  {'MC':>6}  {'Total':>9}")
    print("-" * 70)

    candles = load_candles(pair)
    indicators = precompute_indicators(candles)

    thresholds_met = {}
    for sl_mult in [1.5, 2.0, 2.5, 3.0]:
        label = f"sl_{sl_mult}x"
        r, mc_p, trades = run_variant(pair, candles, indicators, sl_mult, label)
        n = r.win_count + r.loss_count + r.breakeven_count
        gates = sum([
            r.profit_factor >= 1.50,
            r.sharpe_annualized >= 1.00,
            r.mar >= 0.50,
            mc_p >= 0.85,
            r.max_drawdown_pct <= 0.10,
        ])
        thresholds_met[sl_mult] = gates
        print(
            f"{sl_mult:>6.1f}  {n:>6}  {r.win_rate:>6.1%}  {r.profit_factor:>6.2f}  "
            f"{r.sharpe_annualized:>7.2f}  {r.mar:>6.2f}  {r.max_drawdown_pct:>7.1%}  "
            f"{mc_p:>6.1%}  ${r.total_pnl:>8,.0f}  [{gates}/5]"
        )

    best = max(thresholds_met, key=thresholds_met.get)
    print(f"\nBest SL multiplier: {best}x  ({thresholds_met[best]}/5 gates)")
    if thresholds_met[best] >= 4:
        print(">>> READY: Use this multiplier for USD_JPY in production.")
    elif thresholds_met[best] >= 3:
        print(">>> PARTIAL: Improving but not live-ready. Try combining layers.")
    else:
        print(">>> INSUFFICIENT: SL tuning alone cannot fix USD_JPY signal quality.")


if __name__ == "__main__":
    main()
