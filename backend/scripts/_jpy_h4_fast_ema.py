"""
USD_JPY H4 Fast-EMA Sweep
Goal: increase qualifying trade count from 7 to 12+ while keeping PF >= 1.50
      so that MC bootstrap can reach 85% P(profit).

Current best: H4 EMA20>EMA50 weak mode → 7 trades, PF 2.63, MC 80.5% (4/5 gates)
Problem:      7-trade bootstrap can't reliably reach 85% MC threshold

Strategy:
  Test faster H4 EMA crossovers (EMA5/EMA10) and quality-boosted medium-term configs.
  Faster H4 EMAs → more qualifying periods → more H1 entries pass the filter.

Modes tested:
  h4_ema10_gt_ema20   : H4 EMA10 > EMA20 (40h vs 80h) — faster than EMA20>EMA50
  h4_ema5_gt_ema10    : H4 EMA5 > EMA10 (20h vs 40h) — very fast H4 cross
  h4_ema10_20_adx15   : H4 EMA10>EMA20 AND ADX>=15 (quality gate on faster cross)
  h4_ema10_20_adx20   : H4 EMA10>EMA20 AND ADX>=20 (stricter ADX)
  h4_ema50_200_adx15  : H4 EMA50>EMA200 AND ADX>=15 (23-trade variant + quality)
  h4_ema50_200_adx20  : H4 EMA50>EMA200 AND ADX>=20
  h4_ema20_50_adx15   : Current best (EMA20>EMA50) AND ADX>=15
  h4_ema20_50_any     : Current best no ADX (baseline for comparison)
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


# ─── Extended H4 State ────────────────────────────────────────────────────────

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
    ema5_series  = compute_ema_series(closes, 5)
    ema10_series = compute_ema_series(closes, 10)
    states = []
    for i, (c, ind) in enumerate(zip(candles, indicators)):
        states.append(H4StateExt(
            time=c.time,
            ema5=ema5_series[i],
            ema10=ema10_series[i],
            ema20=ind.ema_20,
            ema50=ind.ema_50,
            ema200=ind.ema_200,
            adx=ind.adx_14,
            close=c.close,
        ))
    return states


def h4_ext_at(h4_states: list[H4StateExt], h1_time: datetime) -> H4StateExt | None:
    result = None
    for state in h4_states:
        if state.time + timedelta(hours=4) <= h1_time:  # only use closed H4 bars
            result = state
        else:
            break
    return result


# ─── MTF Filter Logic ─────────────────────────────────────────────────────────

def h4_allows(h4: H4StateExt, action: str, mode: str) -> bool:
    e5   = float(h4.ema5)
    e10  = float(h4.ema10)
    e20  = float(h4.ema20)
    e50  = float(h4.ema50)
    e200 = float(h4.ema200) if h4.ema200 > 0 else None
    adx  = float(h4.adx)

    if mode == "h4_ema10_gt_ema20":
        if action == "BUY":  return e10 > e20
        if action == "SELL": return e10 < e20

    elif mode == "h4_ema5_gt_ema10":
        if action == "BUY":  return e5 > e10
        if action == "SELL": return e5 < e10

    elif mode == "h4_ema10_20_adx15":
        if action == "BUY":  return e10 > e20 and adx >= 15
        if action == "SELL": return e10 < e20 and adx >= 15

    elif mode == "h4_ema10_20_adx20":
        if action == "BUY":  return e10 > e20 and adx >= 20
        if action == "SELL": return e10 < e20 and adx >= 20

    elif mode == "h4_ema50_200_adx15":
        if e200 is None: return False
        if action == "BUY":  return e50 > e200 and adx >= 15
        if action == "SELL": return e50 < e200 and adx >= 15

    elif mode == "h4_ema50_200_adx20":
        if e200 is None: return False
        if action == "BUY":  return e50 > e200 and adx >= 20
        if action == "SELL": return e50 < e200 and adx >= 20

    elif mode == "h4_ema20_50_adx15":
        if action == "BUY":  return e20 > e50 and adx >= 15
        if action == "SELL": return e20 < e50 and adx >= 15

    elif mode == "h4_ema20_50_any":
        if action == "BUY":  return e20 > e50
        if action == "SELL": return e20 < e50

    return True  # no filter


# ─── Backtest Engine ──────────────────────────────────────────────────────────

def run_fast_ema(pair, candles, indicators, h4_states, mode, label):
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
    warmup = 200

    for i in range(warmup, n - 1):
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

        h4 = h4_ext_at(h4_states, candle.time)
        if h4 is not None:
            if not h4_allows(h4, action, mode):
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    pair = "USD_JPY"
    candles = load_candles(pair)
    indicators = precompute_indicators(candles)
    h4_states = build_h4_states_ext(pair)

    print(f"USD_JPY H4 Fast-EMA Sweep — targeting MC>=85% via more qualifying trades")
    print(f"H1: {len(candles)} bars   H4: {len(h4_states)} bars")
    print(f"\nTarget: 12+ trades with PF>=1.50, Sharpe>=1.00, MAR>=0.50, MaxDD<=10%, MC>=85%\n")
    print(f"{'Mode':<26} {'N':>4} {'WR':>6} {'PF':>5} {'Sharpe':>7} {'MAR':>5} {'MaxDD':>7} {'MC':>6} {'Gates':>6}")
    print("-" * 78)

    modes = [
        ("h4_ema20_50_any",     "EMA20>50 (baseline 4/5)"),
        ("h4_ema10_gt_ema20",   "EMA10>20 H4 (faster)"),
        ("h4_ema5_gt_ema10",    "EMA5>10 H4 (fastest)"),
        ("h4_ema10_20_adx15",   "EMA10>20 + ADX>=15"),
        ("h4_ema10_20_adx20",   "EMA10>20 + ADX>=20"),
        ("h4_ema50_200_adx15",  "EMA50>200 + ADX>=15"),
        ("h4_ema50_200_adx20",  "EMA50>200 + ADX>=20"),
        ("h4_ema20_50_adx15",   "EMA20>50 + ADX>=15"),
    ]

    best = {"gates": 0, "label": "", "r": None, "mc": 0, "n": 0}
    for mode, label in modes:
        trades = run_fast_ema(pair, candles, indicators, h4_states, mode, label)
        if not trades:
            print(f"{label:<26} (no trades)")
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
        print(f"{label:<26} {n:>4} {r.win_rate:>6.1%} {r.profit_factor:>5.2f} "
              f"{r.sharpe_annualized:>7.2f} {r.mar:>5.2f} {r.max_drawdown_pct:>6.2f}% "
              f"{mc_p:>6.1%} [{gates}/5]")

    print(f"\nBest: {best['label']} — {best['gates']}/5 gates  (N={best['n']})")
    if best["r"]:
        r = best["r"]
        print(f"  PF {r.profit_factor:.2f}  Sharpe {r.sharpe_annualized:.2f}  MAR {r.mar:.2f}"
              f"  MaxDD {r.max_drawdown_pct:.2f}%  MC {best['mc']:.1%}")
    if best["gates"] >= 5:
        print("\n>>> 5/5 GATES — LIVE READY")
    elif best["gates"] >= 4:
        if best["n"] >= 12:
            print("\n>>> 4/5 gates with sufficient sample size — MC likely close to threshold.")
        else:
            print("\n>>> 4/5 gates — sample size still limiting MC. Try multi-year data or looser filter.")
    else:
        print("\n>>> Not sufficient. Different approach needed.")


if __name__ == "__main__":
    main()
