"""
USD_JPY ADX Threshold Sensitivity Test
Sweeps H4 EMA5>EMA10 + ADX threshold from 15 to 30 in steps of 1.
Goal: confirm the ADX>=25 result is a stable plateau, not a single lucky cutoff.
Also runs a time-split walk-forward to check out-of-sample performance.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_v2 import (
    BacktestConfig, FilterToggles, Trade, PIP_SIZE,
    _close_trade, _do_partial_close, compute_metrics, monte_carlo,
    load_candles, precompute_indicators, quant_evaluate,
    BREAKEVEN_PIPS, TRAIL_ACTIVATION_PIPS, confidence_tier_risk_pct,
    pip_value_per_unit, round_price, compute_ema_series,
)


@dataclass
class H4StateExt:
    time: datetime
    ema5: Decimal
    ema10: Decimal
    ema20: Decimal
    ema50: Decimal
    ema200: Decimal
    adx: Decimal
    close: Decimal


def build_h4_states_ext(pair: str) -> list[H4StateExt]:
    candles = load_candles(pair, "H4")
    indicators = precompute_indicators(candles)
    closes = [c.close for c in candles]
    ema5_s  = compute_ema_series(closes, 5)
    ema10_s = compute_ema_series(closes, 10)
    return [
        H4StateExt(
            time=c.time, ema5=ema5_s[i], ema10=ema10_s[i],
            ema20=ind.ema_20, ema50=ind.ema_50, ema200=ind.ema_200,
            adx=ind.adx_14, close=c.close,
        )
        for i, (c, ind) in enumerate(zip(candles, indicators))
    ]


def h4_at(h4_states, h1_time):
    result = None
    for s in h4_states:
        if s.time + timedelta(hours=4) <= h1_time:  # only use closed H4 bars
            result = s
        else:
            break
    return result


def run_with_adx_thresh(pair, candles, indicators, h4_states, adx_thresh,
                        start_idx=None, end_idx=None):
    cfg = BacktestConfig(sl_atr_multiplier=Decimal("2.5"), partial_close_pct=Decimal("0.67"))
    toggles = FilterToggles(use_partial_close=True)
    n = len(candles)
    si = start_idx if start_idx is not None else 200
    ei = end_idx if end_idx is not None else n - 1

    balance = cfg.starting_balance
    trades = []
    open_trade = None
    cooldown_until = None
    sess_start, sess_end = cfg.session_hours.get(pair, (0, 24))
    spread_pips = cfg.spread_pips.get(pair, Decimal("1.5"))
    pip = PIP_SIZE[pair]
    daily_pnl = defaultdict(lambda: Decimal("0"))

    for i in range(max(si, 200), ei):
        candle = candles[i]
        next_candle = candles[i + 1]
        ind = indicators[i]
        hour = candle.time.hour
        date_key = candle.time.date().isoformat()

        if open_trade is not None:
            sl_hit = False
            exit_price = None
            exit_reason = ""

            if open_trade.direction == "BUY":
                if candle.low <= open_trade.stop_loss:
                    sl_hit = True; exit_price = open_trade.stop_loss
                    exit_reason = "TRAILING_STOP" if open_trade.trailing_active else "SL_HIT"
                else:
                    if (toggles.use_partial_close and not open_trade.partial_closed
                            and open_trade.initial_sl_distance > 0):
                        pt = open_trade.entry_price + open_trade.initial_sl_distance * cfg.partial_close_rr
                        if candle.high >= pt:
                            balance += _do_partial_close(open_trade, pt, "BUY", pair, cfg, toggles, spread_pips, pip)
                    pp = (candle.close - open_trade.entry_price) / pip
                    if toggles.use_breakeven and not open_trade.breakeven_set and pp >= BREAKEVEN_PIPS[pair]:
                        open_trade.stop_loss = open_trade.entry_price; open_trade.breakeven_set = True
                    if toggles.use_trailing_stop and pp >= TRAIL_ACTIVATION_PIPS[pair]:
                        open_trade.trailing_active = True
                        td = max((open_trade.entry_price - open_trade.stop_loss).copy_abs(),
                                 cfg.sl_atr_multiplier * pip * Decimal("15"))
                        ns = candle.close - td
                        if ns > open_trade.stop_loss: open_trade.stop_loss = ns
            else:
                if candle.high >= open_trade.stop_loss:
                    sl_hit = True; exit_price = open_trade.stop_loss
                    exit_reason = "TRAILING_STOP" if open_trade.trailing_active else "SL_HIT"
                else:
                    if (toggles.use_partial_close and not open_trade.partial_closed
                            and open_trade.initial_sl_distance > 0):
                        pt = open_trade.entry_price - open_trade.initial_sl_distance * cfg.partial_close_rr
                        if candle.low <= pt:
                            balance += _do_partial_close(open_trade, pt, "SELL", pair, cfg, toggles, spread_pips, pip)
                    pp = (open_trade.entry_price - candle.close) / pip
                    if toggles.use_breakeven and not open_trade.breakeven_set and pp >= BREAKEVEN_PIPS[pair]:
                        open_trade.stop_loss = open_trade.entry_price; open_trade.breakeven_set = True
                    if toggles.use_trailing_stop and pp >= TRAIL_ACTIVATION_PIPS[pair]:
                        open_trade.trailing_active = True
                        td = max((open_trade.stop_loss - open_trade.entry_price).copy_abs(),
                                 cfg.sl_atr_multiplier * pip * Decimal("15"))
                        ns = candle.close + td
                        if ns < open_trade.stop_loss: open_trade.stop_loss = ns

            hc = i - next((j for j in range(i, -1, -1) if candles[j].time <= open_trade.entry_time), i)
            if not sl_hit and hc >= cfg.max_hold_hours:
                sl_hit = True; exit_price = candle.close; exit_reason = "MAX_HOLD"

            if sl_hit and exit_price is not None:
                _close_trade(open_trade, exit_price, candle.time, exit_reason, pair, cfg, toggles, spread_pips)
                trades.append(open_trade)
                balance += open_trade.pnl_usd
                daily_pnl[date_key] += open_trade.pnl_usd
                cooldown_until = candle.time
                open_trade = None
            continue

        if cooldown_until and (candle.time - cooldown_until).total_seconds() < 300: continue
        if hour >= 17: continue
        if not (sess_start <= hour < sess_end): continue
        if daily_pnl[date_key] <= -cfg.daily_loss_limit_usd: continue

        action, score, strategies, regime = quant_evaluate(ind, candle.close, toggles)
        if action == "HOLD": continue

        h4 = h4_at(h4_states, candle.time)
        if h4 is not None:
            e5 = float(h4.ema5); e10 = float(h4.ema10); adx = float(h4.adx)
            if action == "BUY"  and not (e5 > e10 and adx >= adx_thresh): continue
            if action == "SELL" and not (e5 < e10 and adx >= adx_thresh): continue

        if not (cfg.confidence_floor <= score <= cfg.confidence_ceiling): continue
        atr = ind.atr_14
        if atr == 0: continue
        sl_dist = atr * cfg.sl_atr_multiplier
        sl_pips = sl_dist / pip
        if sl_pips < cfg.min_sl_pips: continue
        ep = next_candle.open + (cfg.slippage_pips * pip if action == "BUY" else -cfg.slippage_pips * pip)
        sl = round_price(ep - sl_dist if action == "BUY" else ep + sl_dist, pair)
        risk_pct = confidence_tier_risk_pct(score, cfg, toggles)
        risk_usd = balance * risk_pct
        pv = pip_value_per_unit(pair, ep)
        if pv == 0: continue
        units = Decimal(max(0, int(risk_usd / (sl_pips * pv))))
        if units < 1000: continue
        units = min(units, Decimal("500000"))
        open_trade = Trade(pair=pair, direction=action, entry_price=ep, stop_loss=sl,
                           entry_time=next_candle.time, units=units, confidence_score=score,
                           strategies_fired="+".join(strategies), regime=f"ADX{adx_thresh}",
                           initial_sl_distance=sl_dist)

    if open_trade is not None:
        _close_trade(open_trade, candles[-1].close, candles[-1].time, "END", pair, cfg, toggles, spread_pips)
        trades.append(open_trade)
    return trades


def main():
    pair = "USD_JPY"
    candles = load_candles(pair)
    indicators = precompute_indicators(candles)
    h4_states = build_h4_states_ext(pair)
    n = len(candles)

    print(f"USD_JPY ADX Threshold Sensitivity: H4 EMA5>EMA10 + ADX >= threshold")
    print(f"Total data: {n} H1 bars   ({candles[0].time.date()} to {candles[-1].time.date()})")
    print(f"\n{'ADX':>5} {'N':>4} {'WR':>6} {'PF':>5} {'Sharpe':>7} {'MAR':>5} {'MaxDD':>7} {'MC':>6} {'Gates':>6}")
    print("-" * 55)

    for thresh in range(15, 31):
        trades = run_with_adx_thresh(pair, candles, indicators, h4_states, thresh)
        if not trades:
            print(f"  {thresh:>3}   (no trades)")
            continue
        r = compute_metrics(pair, f"ADX{thresh}", trades, Decimal("100000"))
        mc = monte_carlo(trades, Decimal("100000"), n_sim=3000)
        mc_p = mc["p_profit"]
        n_t = r.win_count + r.loss_count + r.breakeven_count
        gates = sum([r.profit_factor >= 1.50, r.sharpe_annualized >= 1.00,
                     r.mar >= 0.50, mc_p >= 0.85, r.max_drawdown_pct <= 10.0])
        flag = " <<<" if gates >= 5 else (" <" if gates >= 4 else "")
        print(f"  {thresh:>3} {n_t:>4} {r.win_rate:>6.1%} {r.profit_factor:>5.2f} "
              f"{r.sharpe_annualized:>7.2f} {r.mar:>5.2f} {r.max_drawdown_pct:>6.2f}% "
              f"{mc_p:>6.1%} [{gates}/5]{flag}")

    # Walk-forward: first 70% in-sample, last 30% out-of-sample
    split = int(n * 0.70)
    print(f"\n--- Walk-Forward Validation (ADX>=25) ---")
    print(f"In-sample:  bars 0 to {split} ({candles[200].time.date()} to {candles[split].time.date()})")
    print(f"Out-of-sample: bars {split} to {n-1} ({candles[split].time.date()} to {candles[-1].time.date()})")

    is_trades = run_with_adx_thresh(pair, candles, indicators, h4_states, 25, end_idx=split)
    oos_trades = run_with_adx_thresh(pair, candles, indicators, h4_states, 25, start_idx=split)

    for label, trades in [("In-sample  (70%)", is_trades), ("Out-of-sample (30%)", oos_trades)]:
        if not trades:
            print(f"{label}: no trades")
            continue
        r = compute_metrics(pair, label, trades, Decimal("100000"))
        mc = monte_carlo(trades, Decimal("100000"), n_sim=3000)
        mc_p = mc["p_profit"]
        n_t = r.win_count + r.loss_count + r.breakeven_count
        gates = sum([r.profit_factor >= 1.50, r.sharpe_annualized >= 1.00,
                     r.mar >= 0.50, mc_p >= 0.85, r.max_drawdown_pct <= 10.0])
        print(f"{label}: N={n_t} WR={r.win_rate:.1%} PF={r.profit_factor:.2f} "
              f"Sharpe={r.sharpe_annualized:.2f} MAR={r.mar:.2f} "
              f"MaxDD={r.max_drawdown_pct:.2f}% MC={mc_p:.1%} [{gates}/5]")

    # Final high-sim verification of ADX>=25
    print(f"\n--- Final Verification: ADX>=25 with 10000 MC sims ---")
    all_trades = run_with_adx_thresh(pair, candles, indicators, h4_states, 25)
    r = compute_metrics(pair, "ADX25_final", all_trades, Decimal("100000"))
    mc_final = monte_carlo(all_trades, Decimal("100000"), n_sim=10000)
    mc_p = mc_final["p_profit"]
    n_t = r.win_count + r.loss_count + r.breakeven_count
    gates = sum([r.profit_factor >= 1.50, r.sharpe_annualized >= 1.00,
                 r.mar >= 0.50, mc_p >= 0.85, r.max_drawdown_pct <= 10.0])
    print(f"N={n_t} WR={r.win_rate:.1%} PF={r.profit_factor:.2f} "
          f"Sharpe={r.sharpe_annualized:.2f} MAR={r.mar:.2f} "
          f"MaxDD={r.max_drawdown_pct:.2f}% MC={mc_p:.1%} [{gates}/5]")

    # Trade date distribution
    if all_trades:
        months = defaultdict(int)
        for t in all_trades:
            months[t.entry_time.strftime("%Y-%m")] += 1
        print(f"\nTrade distribution by month:")
        for month in sorted(months):
            bar = "#" * months[month]
            print(f"  {month}: {months[month]:>2}  {bar}")


if __name__ == "__main__":
    main()
