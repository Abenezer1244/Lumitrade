"""
USD_JPY H4 Combined Filter Sweep — Phase 2
Base: H4 EMA5>EMA10 gives 87 trades PF 1.32, MC 82.3% (2/5 gates).
Goal: Add quality filters on top to push PF from 1.32 → 1.50 while keeping N >= 20.

Quality filters to try:
  + H4 ADX>=20         : Only trade when H4 is trending (not choppy)
  + H4 ADX>=25         : Stricter trending condition
  + H4 close > EMA20   : Price already above medium H4 EMA
  + H4 close > EMA50   : Price above slow H4 EMA (stronger confirmation)
  + H4 EMA10>EMA20     : Dual fast-cross (EMA5>10 AND EMA10>20)
  + H4 EMA10>EMA20 +ADX20: Triple condition

Also tests H4 EMA5>10 with H1 RSI entry filter to avoid overbought/oversold entries.
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
    BacktestConfig,
    FilterToggles,
    Trade,
    PIP_SIZE,
    _close_trade,
    _do_partial_close,
    compute_metrics,
    monte_carlo,
    load_candles,
    precompute_indicators,
    quant_evaluate,
    BREAKEVEN_PIPS,
    TRAIL_ACTIVATION_PIPS,
    confidence_tier_risk_pct,
    pip_value_per_unit,
    round_price,
    compute_ema_series,
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


def h4_at(h4_states: list[H4StateExt], h1_time: datetime) -> H4StateExt | None:
    result = None
    for s in h4_states:
        if s.time + timedelta(hours=4) <= h1_time:  # only use closed H4 bars
            result = s
        else:
            break
    return result


def h4_allows(h4: H4StateExt, action: str, mode: str, ind=None) -> bool:
    e5  = float(h4.ema5)
    e10 = float(h4.ema10)
    e20 = float(h4.ema20)
    e50 = float(h4.ema50)
    adx = float(h4.adx)
    px  = float(h4.close)

    base_e5_gt_e10  = (e5 > e10 if action == "BUY" else e5 < e10)
    base_e10_gt_e20 = (e10 > e20 if action == "BUY" else e10 < e20)

    if mode == "e5_10_ADX20":
        return base_e5_gt_e10 and adx >= 20

    elif mode == "e5_10_ADX25":
        return base_e5_gt_e10 and adx >= 25

    elif mode == "e5_10_price_gt_e20":
        # Price above H4 EMA20 for BUY, below for SELL
        if action == "BUY":  return base_e5_gt_e10 and px > e20
        if action == "SELL": return base_e5_gt_e10 and px < e20

    elif mode == "e5_10_price_gt_e50":
        if action == "BUY":  return base_e5_gt_e10 and px > e50
        if action == "SELL": return base_e5_gt_e10 and px < e50

    elif mode == "e5_10_AND_e10_20":
        return base_e5_gt_e10 and base_e10_gt_e20

    elif mode == "e5_10_AND_e10_20_ADX20":
        return base_e5_gt_e10 and base_e10_gt_e20 and adx >= 20

    elif mode == "e5_10_AND_e10_20_ADX15":
        return base_e5_gt_e10 and base_e10_gt_e20 and adx >= 15

    elif mode == "e5_10_price_gt_e20_ADX15":
        if action == "BUY":  return base_e5_gt_e10 and px > e20 and adx >= 15
        if action == "SELL": return base_e5_gt_e10 and px < e20 and adx >= 15

    elif mode == "e5_10_only":
        return base_e5_gt_e10

    return True


def run_sweep(pair, candles, indicators, h4_states, mode, label, h1_rsi_filter=False):
    cfg = BacktestConfig(sl_atr_multiplier=Decimal("2.5"), partial_close_pct=Decimal("0.67"))
    toggles = FilterToggles(use_partial_close=True)
    n = len(candles)
    balance = cfg.starting_balance
    trades = []
    open_trade = None
    cooldown_until = None
    sess_start, sess_end = cfg.session_hours.get(pair, (0, 24))
    spread_pips = cfg.spread_pips.get(pair, Decimal("1.5"))
    pip = PIP_SIZE[pair]
    daily_pnl = defaultdict(lambda: Decimal("0"))

    for i in range(200, n - 1):
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
                    sl_hit = True
                    exit_price = open_trade.stop_loss
                    exit_reason = "TRAILING_STOP" if open_trade.trailing_active else "SL_HIT"
                else:
                    if (toggles.use_partial_close and not open_trade.partial_closed
                            and open_trade.initial_sl_distance > 0):
                        pt = open_trade.entry_price + open_trade.initial_sl_distance * cfg.partial_close_rr
                        if candle.high >= pt:
                            balance += _do_partial_close(open_trade, pt, "BUY", pair, cfg, toggles, spread_pips, pip)
                    pp = (candle.close - open_trade.entry_price) / pip
                    if toggles.use_breakeven and not open_trade.breakeven_set and pp >= BREAKEVEN_PIPS[pair]:
                        open_trade.stop_loss = open_trade.entry_price
                        open_trade.breakeven_set = True
                    if toggles.use_trailing_stop and pp >= TRAIL_ACTIVATION_PIPS[pair]:
                        open_trade.trailing_active = True
                        td = max((open_trade.entry_price - open_trade.stop_loss).copy_abs(),
                                 cfg.sl_atr_multiplier * pip * Decimal("15"))
                        ns = candle.close - td
                        if ns > open_trade.stop_loss:
                            open_trade.stop_loss = ns
            else:
                if candle.high >= open_trade.stop_loss:
                    sl_hit = True
                    exit_price = open_trade.stop_loss
                    exit_reason = "TRAILING_STOP" if open_trade.trailing_active else "SL_HIT"
                else:
                    if (toggles.use_partial_close and not open_trade.partial_closed
                            and open_trade.initial_sl_distance > 0):
                        pt = open_trade.entry_price - open_trade.initial_sl_distance * cfg.partial_close_rr
                        if candle.low <= pt:
                            balance += _do_partial_close(open_trade, pt, "SELL", pair, cfg, toggles, spread_pips, pip)
                    pp = (open_trade.entry_price - candle.close) / pip
                    if toggles.use_breakeven and not open_trade.breakeven_set and pp >= BREAKEVEN_PIPS[pair]:
                        open_trade.stop_loss = open_trade.entry_price
                        open_trade.breakeven_set = True
                    if toggles.use_trailing_stop and pp >= TRAIL_ACTIVATION_PIPS[pair]:
                        open_trade.trailing_active = True
                        td = max((open_trade.stop_loss - open_trade.entry_price).copy_abs(),
                                 cfg.sl_atr_multiplier * pip * Decimal("15"))
                        ns = candle.close + td
                        if ns < open_trade.stop_loss:
                            open_trade.stop_loss = ns

            hc = i - next((j for j in range(i, -1, -1) if candles[j].time <= open_trade.entry_time), i)
            if not sl_hit and hc >= cfg.max_hold_hours:
                sl_hit = True
                exit_price = candle.close
                exit_reason = "MAX_HOLD"

            if sl_hit and exit_price is not None:
                _close_trade(open_trade, exit_price, candle.time, exit_reason, pair, cfg, toggles, spread_pips)
                trades.append(open_trade)
                balance += open_trade.pnl_usd
                daily_pnl[date_key] += open_trade.pnl_usd
                cooldown_until = candle.time
                open_trade = None
            continue

        if cooldown_until and (candle.time - cooldown_until).total_seconds() < 300:
            continue
        if hour >= 17:
            continue
        if not (sess_start <= hour < sess_end):
            continue
        if daily_pnl[date_key] <= -cfg.daily_loss_limit_usd:
            continue

        action, score, strategies, regime = quant_evaluate(ind, candle.close, toggles)
        if action == "HOLD":
            continue

        # H4 filter
        h4 = h4_at(h4_states, candle.time)
        if h4 is not None:
            if not h4_allows(h4, action, mode, ind):
                continue

        # Optional H1 RSI entry filter (avoid entering when momentum already extended)
        if h1_rsi_filter:
            rsi = float(ind.rsi_14)
            if action == "BUY" and rsi > 65:
                continue
            if action == "SELL" and rsi < 35:
                continue

        if not (cfg.confidence_floor <= score <= cfg.confidence_ceiling):
            continue
        atr = ind.atr_14
        if atr == 0:
            continue
        sl_dist = atr * cfg.sl_atr_multiplier
        sl_pips = sl_dist / pip
        if sl_pips < cfg.min_sl_pips:
            continue
        ep = next_candle.open + (cfg.slippage_pips * pip if action == "BUY" else -cfg.slippage_pips * pip)
        sl = round_price(ep - sl_dist if action == "BUY" else ep + sl_dist, pair)
        risk_pct = confidence_tier_risk_pct(score, cfg, toggles)
        risk_usd = balance * risk_pct
        pv = pip_value_per_unit(pair, ep)
        if pv == 0:
            continue
        units = Decimal(max(0, int(risk_usd / (sl_pips * pv))))
        if units < 1000:
            continue
        units = min(units, Decimal("500000"))
        open_trade = Trade(pair=pair, direction=action, entry_price=ep, stop_loss=sl,
                           entry_time=next_candle.time, units=units, confidence_score=score,
                           strategies_fired="+".join(strategies), regime=label,
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

    print(f"USD_JPY H4 Combined Filter Sweep")
    print(f"Base: H4 EMA5>EMA10 = 87 trades, PF 1.32, MC 82.3% (2/5 gates)")
    print(f"Goal: Add quality gate to push PF to 1.50+ while keeping N >= 20")
    print(f"\n{'Mode':<35} {'N':>4} {'WR':>6} {'PF':>5} {'Sharpe':>7} {'MAR':>5} {'MaxDD':>7} {'MC':>6} {'Gates':>6}")
    print("-" * 85)

    configs = [
        ("e5_10_only",             "EMA5>10 (no filter)",        False),
        ("e5_10_price_gt_e20",     "EMA5>10 + price>H4_EMA20",   False),
        ("e5_10_price_gt_e50",     "EMA5>10 + price>H4_EMA50",   False),
        ("e5_10_ADX20",            "EMA5>10 + ADX>=20",          False),
        ("e5_10_ADX25",            "EMA5>10 + ADX>=25",          False),
        ("e5_10_AND_e10_20",       "EMA5>10 AND EMA10>20",       False),
        ("e5_10_AND_e10_20_ADX15", "EMA5>10+EMA10>20+ADX15",     False),
        ("e5_10_AND_e10_20_ADX20", "EMA5>10+EMA10>20+ADX20",     False),
        ("e5_10_price_gt_e20_ADX15", "EMA5>10+price>E20+ADX15",  False),
        # With H1 RSI entry filter
        ("e5_10_price_gt_e20",     "EMA5>10+price>E20+RSI<65",   True),
        ("e5_10_AND_e10_20",       "EMA5>10+E10>20+RSI<65",      True),
    ]

    best = {"gates": 0, "label": "", "r": None, "mc": 0, "n": 0}
    for mode, label, rsi_filter in configs:
        trades = run_sweep(pair, candles, indicators, h4_states, mode, label, h1_rsi_filter=rsi_filter)
        if not trades:
            print(f"{label:<35} (no trades)")
            continue
        r = compute_metrics(pair, label, trades, Decimal("100000"))
        mc = monte_carlo(trades, Decimal("100000"), n_sim=3000)
        mc_p = mc["p_profit"]
        n = r.win_count + r.loss_count + r.breakeven_count
        gates = sum([
            r.profit_factor >= 1.50,
            r.sharpe_annualized >= 1.00,
            r.mar >= 0.50,
            mc_p >= 0.85,
            r.max_drawdown_pct <= 10.0,
        ])
        if gates > best["gates"] or (gates == best["gates"] and n > best["n"]):
            best = {"gates": gates, "label": label, "r": r, "mc": mc_p, "n": n}
        print(f"{label:<35} {n:>4} {r.win_rate:>6.1%} {r.profit_factor:>5.2f} "
              f"{r.sharpe_annualized:>7.2f} {r.mar:>5.2f} {r.max_drawdown_pct:>6.2f}% "
              f"{mc_p:>6.1%} [{gates}/5]")

    print(f"\nBest: {best['label']} — {best['gates']}/5 gates  (N={best['n']})")
    if best["r"]:
        r = best["r"]
        print(f"  PF {r.profit_factor:.2f}  Sharpe {r.sharpe_annualized:.2f}  MAR {r.mar:.2f}"
              f"  MaxDD {r.max_drawdown_pct:.2f}%  MC {best['mc']:.1%}")

    if best["gates"] >= 5:
        print("\n>>> 5/5 GATES — USD_JPY LIVE READY")
    elif best["gates"] >= 4 and best["n"] >= 12:
        print("\n>>> 4/5 with N>=12 — MC very close. Consider 5000-sim final verification.")
    elif best["gates"] >= 4:
        print("\n>>> 4/5 gates — MC limited by sample size.")
    else:
        print("\n>>> Still insufficient. May need fundamentally different approach.")


if __name__ == "__main__":
    main()
