"""
BTC parameter sweep: SL multiplier + fixed take-profit variants.
Run: python -m scripts._btc_sweep
"""
from __future__ import annotations
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from collections import defaultdict
from decimal import Decimal
import scripts.backtest_v2 as bv


def run_with_tp(pair, candles, indicators, cfg, toggles, tp_rr=0.0):
    """Backtest loop that adds a fixed TP at tp_rr * SL_distance. tp_rr=0 = trailing-only."""
    n = len(candles)
    if n < 250:
        return []
    balance = cfg.starting_balance
    trades = []
    open_trade = None
    cooldown_until = None
    sess_start, sess_end = cfg.session_hours.get(pair, (0, 24))
    spread_pips = cfg.spread_pips.get(pair, Decimal("1.5"))
    pip = bv.PIP_SIZE[pair]
    daily_pnl = defaultdict(lambda: Decimal("0"))
    warmup = max(200, 28)
    take_profit = None

    for i in range(warmup, n - 1):
        candle = candles[i]
        next_candle = candles[i + 1]
        ind = indicators[i]
        hour = candle.time.hour
        date_key = candle.time.date().isoformat()

        if open_trade is not None:
            sl_hit = tp_hit = False
            exit_price = None
            exit_reason = ""

            if open_trade.direction == "BUY":
                if candle.low <= open_trade.stop_loss:
                    sl_hit = True
                    exit_price = open_trade.stop_loss
                    exit_reason = "TRAILING_STOP" if open_trade.trailing_active else "SL_HIT"
                elif take_profit and candle.high >= take_profit:
                    tp_hit = True
                    exit_price = take_profit
                    exit_reason = "TP_HIT"
                else:
                    pp = (candle.close - open_trade.entry_price) / pip
                    if not open_trade.breakeven_set and pp >= bv.BREAKEVEN_PIPS.get(pair, 15):
                        open_trade.stop_loss = open_trade.entry_price
                        open_trade.breakeven_set = True
                    if pp >= bv.TRAIL_ACTIVATION_PIPS.get(pair, 20):
                        if not open_trade.trailing_active:
                            open_trade.trailing_active = True
                        td = max(
                            (open_trade.entry_price - open_trade.stop_loss).copy_abs(),
                            cfg.sl_atr_multiplier * pip * Decimal("15"),
                        )
                        ns = candle.close - td
                        if ns > open_trade.stop_loss:
                            open_trade.stop_loss = ns
            else:
                if candle.high >= open_trade.stop_loss:
                    sl_hit = True
                    exit_price = open_trade.stop_loss
                    exit_reason = "TRAILING_STOP" if open_trade.trailing_active else "SL_HIT"
                elif take_profit and candle.low <= take_profit:
                    tp_hit = True
                    exit_price = take_profit
                    exit_reason = "TP_HIT"
                else:
                    pp = (open_trade.entry_price - candle.close) / pip
                    if not open_trade.breakeven_set and pp >= bv.BREAKEVEN_PIPS.get(pair, 15):
                        open_trade.stop_loss = open_trade.entry_price
                        open_trade.breakeven_set = True
                    if pp >= bv.TRAIL_ACTIVATION_PIPS.get(pair, 20):
                        if not open_trade.trailing_active:
                            open_trade.trailing_active = True
                        td = max(
                            (open_trade.stop_loss - open_trade.entry_price).copy_abs(),
                            cfg.sl_atr_multiplier * pip * Decimal("15"),
                        )
                        ns = candle.close + td
                        if ns < open_trade.stop_loss:
                            open_trade.stop_loss = ns

            if toggles.use_max_hold:
                hold = i - next(
                    (j for j in range(i, -1, -1) if candles[j].time <= open_trade.entry_time), i
                )
                if hold >= cfg.max_hold_hours:
                    sl_hit = True
                    exit_price = candle.close
                    exit_reason = "MAX_HOLD"

            if (sl_hit or tp_hit) and exit_price is not None:
                bv._close_trade(open_trade, exit_price, candle.time, exit_reason,
                                pair, cfg, toggles, spread_pips)
                trades.append(open_trade)
                balance += open_trade.pnl_usd
                daily_pnl[date_key] += open_trade.pnl_usd
                cooldown_until = candle.time
                open_trade = None
                take_profit = None
            continue

        if (toggles.use_cooldown and cooldown_until
                and (candle.time - cooldown_until).total_seconds() < cfg.cooldown_seconds):
            continue
        if toggles.use_global_cutoff_17_utc and hour >= 17:
            continue
        if toggles.use_session_window and not (sess_start <= hour < sess_end):
            continue
        if toggles.use_daily_loss_limit and daily_pnl[date_key] <= -cfg.daily_loss_limit_usd:
            continue

        action, score, strategies, regime = bv.quant_evaluate(ind, candle.close, toggles)
        if action == "HOLD":
            continue
        if toggles.use_confidence_band:
            if score < cfg.confidence_floor or score > cfg.confidence_ceiling:
                continue

        atr = ind.atr_14
        if atr == 0:
            continue
        sl_dist = atr * cfg.sl_atr_multiplier
        sl_pips_val = sl_dist / pip
        if toggles.use_min_sl_pips and sl_pips_val < cfg.min_sl_pips:
            continue

        entry_price = next_candle.open
        if toggles.use_friction:
            slip = cfg.slippage_pips * pip
            entry_price = entry_price + slip if action == "BUY" else entry_price - slip

        sl = bv.round_price(
            entry_price - sl_dist if action == "BUY" else entry_price + sl_dist, pair
        )
        risk_pct = bv.confidence_tier_risk_pct(score, cfg, toggles)
        risk_usd = balance * risk_pct
        pv = bv.pip_value_per_unit(pair, entry_price)
        if pv == 0:
            continue

        raw_units = risk_usd / (sl_pips_val * pv)
        if pair in bv._FRACTIONAL_UNIT_PAIRS:
            units = max(Decimal("0"), raw_units.quantize(Decimal("0.01")))
            min_u = Decimal("0.01")
        else:
            units = Decimal(max(0, int(raw_units)))
            min_u = Decimal("1000")
        units = min(units, Decimal(str(cfg.max_units)))
        if units < min_u:
            continue

        take_profit = (
            bv.round_price(
                entry_price + sl_dist * Decimal(str(tp_rr)) if action == "BUY"
                else entry_price - sl_dist * Decimal(str(tp_rr)),
                pair,
            )
            if tp_rr > 0
            else None
        )

        open_trade = bv.Trade(
            pair=pair,
            direction=action,
            entry_price=entry_price,
            stop_loss=sl,
            entry_time=next_candle.time,
            units=units,
            confidence_score=score,
            strategies_fired="+".join(strategies),
            regime=regime,
        )

    if open_trade is not None:
        last = candles[-1]
        bv._close_trade(open_trade, last.close, last.time, "BACKTEST_END",
                        pair, cfg, toggles, cfg.spread_pips.get(pair, Decimal("1.5")))
        trades.append(open_trade)
    return trades


def main():
    pair = "BTC_USD"
    candles = bv.load_candles(pair, "H1")
    indicators = bv.precompute_indicators(candles)
    print(f"Loaded {len(candles)} H1 candles ({candles[0].time.date()} -> {candles[-1].time.date()})")
    print()

    hdr = f"{'Config':<52} {'Trades':>7} {'WR':>6} {'PF':>6} {'Sharpe':>7} {'MAR':>6} {'AvgW':>7} {'AvgL':>7} {'MC%':>6}"
    print(hdr)
    print("-" * len(hdr))

    variants = [
        ("3.0xATR / no TP [baseline]",    3.0, 0.0),
        ("1.5xATR / no TP",               1.5, 0.0),
        ("1.5xATR / TP 1.5x RR",          1.5, 1.5),
        ("1.5xATR / TP 2.0x RR",          1.5, 2.0),
        ("1.5xATR / TP 2.5x RR",          1.5, 2.5),
        ("1.5xATR / TP 3.0x RR",          1.5, 3.0),
        ("2.0xATR / TP 2.0x RR",          2.0, 2.0),
        ("2.0xATR / TP 2.5x RR",          2.0, 2.5),
        ("2.0xATR / TP 3.0x RR",          2.0, 3.0),
        ("3.0xATR / TP 2.0x RR",          3.0, 2.0),
        ("3.0xATR / TP 2.5x RR",          3.0, 2.5),
        ("3.0xATR / TP 3.0x RR",          3.0, 3.0),
    ]

    best = None
    for label, sl_mult, tp_rr in variants:
        cfg = bv.BacktestConfig(sl_atr_multiplier=Decimal(str(sl_mult)))
        t = run_with_tp(pair, candles, indicators, cfg, bv.FilterToggles(), tp_rr=tp_rr)
        r = bv.compute_metrics(pair, label, t, cfg.starting_balance)
        mc = bv.monte_carlo(t, cfg.starting_balance, n_sim=2000)
        avg_w = float(r.avg_win)
        avg_l = float(r.avg_loss)
        print(
            f"{label:<52} {len(t):>7} {r.win_rate*100:>5.1f}% {r.profit_factor:>6.2f}"
            f" {r.sharpe_annualized:>7.2f} {r.mar:>6.2f}"
            f" ${avg_w:>+6.0f} ${avg_l:>+6.0f} {mc['p_profit']*100:>5.1f}%"
        )
        if r.profit_factor > 1.0 and (best is None or r.profit_factor > best[0]):
            best = (r.profit_factor, label, sl_mult, tp_rr, r.sharpe_annualized, r.mar, mc["p_profit"])

    print()
    if best:
        print(f"Best PF>1.0: '{best[1]}' — PF={best[0]:.2f} Sharpe={best[4]:.2f} MAR={best[5]:.2f} MC={best[6]*100:.1f}%")
    else:
        print("No variant achieved PF > 1.0 with friction modeled.")

    # Also run USD_CAD and USD_JPY baselines to confirm they are unaffected
    print()
    print("=== Regression check: USD_CAD + USD_JPY baselines unchanged ===")
    for p in ["USD_CAD", "USD_JPY"]:
        c = bv.load_candles(p, "H1")
        ind = bv.precompute_indicators(c)
        cfg = bv.BacktestConfig()
        t = bv.run_backtest(p, c, ind, cfg, bv.FilterToggles(), label="baseline")
        r = bv.compute_metrics(p, "baseline", t, cfg.starting_balance)
        print(f"  {p}: PF={r.profit_factor:.2f}  Sharpe={r.sharpe_annualized:.2f}  Trades={len(t)}")


if __name__ == "__main__":
    main()
