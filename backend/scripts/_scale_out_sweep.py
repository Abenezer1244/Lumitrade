"""
Partial scale-out parameter sweep across all 3 pairs.
Tests: baseline vs various partial-close RR triggers and percentages.

Run: python -m scripts._scale_out_sweep
"""
from __future__ import annotations
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from decimal import Decimal
import scripts.backtest_v2 as bv


def run_pair(pair: str, candles, indicators, cfg: bv.BacktestConfig, toggles: bv.FilterToggles) -> dict:
    t = bv.run_backtest(pair, candles, indicators, cfg, toggles, label="sweep")
    r = bv.compute_metrics(pair, "sweep", t, cfg.starting_balance)
    mc = bv.monte_carlo(t, cfg.starting_balance, n_sim=2000)
    return {"trades": len(t), "wr": r.win_rate, "pf": r.profit_factor,
            "sharpe": r.sharpe_annualized, "mar": r.mar,
            "avg_w": float(r.avg_win), "avg_l": float(r.avg_loss),
            "mc": mc["p_profit"], "pnl": float(r.total_pnl)}


def main():
    pairs = ["USD_CAD", "USD_JPY", "BTC_USD"]
    data = {}
    for pair in pairs:
        candles = bv.load_candles(pair, "H1")
        indicators = bv.precompute_indicators(candles)
        data[pair] = (candles, indicators)
        print(f"{pair}: {len(candles)} candles ({candles[0].time.date()} -> {candles[-1].time.date()})")
    print()

    variants = [
        # (label,              partial_on, rr,   pct)
        ("baseline (no partial)", False,   0.0,  0.00),
        ("partial 1.0RR 50%",     True,    1.0,  0.50),
        ("partial 1.5RR 33%",     True,    1.5,  0.33),
        ("partial 1.5RR 50%",     True,    1.5,  0.50),
        ("partial 1.5RR 67%",     True,    1.5,  0.67),
        ("partial 2.0RR 33%",     True,    2.0,  0.33),
        ("partial 2.0RR 50%",     True,    2.0,  0.50),
        ("partial 2.0RR 67%",     True,    2.0,  0.67),
        ("partial 2.5RR 50%",     True,    2.5,  0.50),
    ]

    for pair in pairs:
        candles, indicators = data[pair]
        print(f"{'='*72}")
        print(f"  {pair}")
        print(f"{'='*72}")
        hdr = f"{'Variant':<28} {'T':>5} {'WR':>6} {'PF':>6} {'Sharpe':>7} {'MAR':>6} {'AvgW':>7} {'AvgL':>7} {'MC':>6} {'P&L':>9}"
        print(hdr)
        print("-" * len(hdr))

        best = None
        for label, partial_on, rr, pct in variants:
            cfg = bv.BacktestConfig(
                partial_close_rr=Decimal(str(rr)) if partial_on else Decimal("1.5"),
                partial_close_pct=Decimal(str(pct)) if partial_on else Decimal("0.50"),
            )
            toggles = bv.FilterToggles(use_partial_close=partial_on)
            m = run_pair(pair, candles, indicators, cfg, toggles)
            print(
                f"{label:<28} {m['trades']:>5} {m['wr']*100:>5.1f}% {m['pf']:>6.2f}"
                f" {m['sharpe']:>7.2f} {m['mar']:>6.2f}"
                f" ${m['avg_w']:>+6.0f} ${m['avg_l']:>+6.0f} {m['mc']*100:>5.1f}%"
                f" ${m['pnl']:>+8.0f}"
            )
            if m["pf"] > 1.0 and (best is None or m["pf"] > best[0]):
                best = (m["pf"], label, rr, pct, m["sharpe"], m["mar"], m["mc"])

        print()
        if best:
            print(f"  Best PF>1: '{best[1]}' PF={best[0]:.2f} Sharpe={best[4]:.2f} MAR={best[5]:.2f} MC={best[6]*100:.1f}%")
        else:
            print(f"  No variant achieved PF > 1.0 for {pair}")
        print()


if __name__ == "__main__":
    main()
