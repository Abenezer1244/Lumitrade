"""
BTC_USD D1 Trend Filter + Session Filter Sweep
================================================
Prior sweeps (7 variants by Codex) maxed at PF 1.14 / 1/5 gates.
This script tests two untried angles:

1. D1 synthetic trend filter -- aggregate H4 to daily bars, apply EMA5>EMA10 + ADX>=20
   (same logic that pushed USD_JPY from PF 1.04 -> 4.19 via H4, now one TF higher for BTC)

2. Session filters -- BTC has distinct US-session vs Asia behavior:
   - CME hours: 13:00-17:00 UTC (US open, most institutional flow)
   - Weekday-only: skip Saturday + Sunday (thinner liquidity)

3. Triple-screen: D1 trend + H4 ADX + H1 entry (Elder's triple screen for crypto)

Goal: push BTC from PF 1.14 (1/5) towards 3+/5 gates
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_v2 import (
    BacktestConfig, FilterToggles, Trade, PIP_SIZE,
    _FRACTIONAL_UNIT_PAIRS,
    _close_trade, _do_partial_close, compute_metrics, monte_carlo,
    load_candles, precompute_indicators, quant_evaluate,
    BREAKEVEN_PIPS, TRAIL_ACTIVATION_PIPS, confidence_tier_risk_pct,
    pip_value_per_unit, round_price, compute_ema_series,
    SPREAD_PIPS_DEFAULT,
)


# ── D1 synthetic bar builder ──────────────────────────────────────────────────

@dataclass
class D1State:
    date: date
    ema5: Decimal
    ema10: Decimal
    adx: Decimal
    close: Decimal


def build_d1_from_h4(pair: str) -> list[D1State]:
    """Aggregate H4 candles into daily bars, compute EMA5/EMA10/ADX."""
    h4 = load_candles(pair, "H4")

    daily: dict[date, list] = defaultdict(list)
    for c in h4:
        daily[c.time.date()].append(c)

    bars_list = []
    for d in sorted(daily.keys()):
        day_c = daily[d]
        bars_list.append((d, day_c[0].open, max(c.high for c in day_c),
                          min(c.low for c in day_c), day_c[-1].close))

    if len(bars_list) < 30:
        return []

    closes = [b[4] for b in bars_list]
    ema5_s  = compute_ema_series(closes, 5)
    ema10_s = compute_ema_series(closes, 10)

    def _adx_series(bars, length=14):
        n = len(bars)
        tr_list = pdm_list = ndm_list = [Decimal("0")] * n
        tr_list = [Decimal("0")] * n
        pdm_list = [Decimal("0")] * n
        ndm_list = [Decimal("0")] * n
        for i in range(1, n):
            h, lo, pc = bars[i][2], bars[i][3], bars[i - 1][4]
            tr_list[i] = max(h - lo, abs(h - pc), abs(lo - pc))
            up   = bars[i][2] - bars[i - 1][2]
            down = bars[i - 1][3] - bars[i][3]
            pdm_list[i] = up   if up > down and up > 0   else Decimal("0")
            ndm_list[i] = down if down > up and down > 0 else Decimal("0")
        k = Decimal(str(2 / (length + 1)))
        atr_val = pdi = ndi = Decimal("0")
        adx_val = Decimal("0")
        adx_acc = Decimal("0")
        adx_count = 0
        result = [Decimal("0")] * n
        for i in range(1, n):
            atr_val = atr_val * (1 - k) + tr_list[i] * k
            pdi = pdi * (1 - k) + pdm_list[i] * k
            ndi = ndi * (1 - k) + ndm_list[i] * k
            if atr_val == 0:
                result[i] = Decimal("0")
                continue
            pdi_n = pdi / atr_val * 100
            ndi_n = ndi / atr_val * 100
            denom = pdi_n + ndi_n
            dx = abs(pdi_n - ndi_n) / denom * 100 if denom != 0 else Decimal("0")
            adx_count += 1
            if adx_count < length:
                adx_acc += dx
                adx_val = adx_acc / adx_count
            else:
                adx_val = adx_val * (length - 1) / length + dx / length
            result[i] = adx_val
        return result

    adx_s = _adx_series(bars_list)
    return [
        D1State(date=bars_list[i][0], ema5=ema5_s[i], ema10=ema10_s[i],
                adx=adx_s[i], close=bars_list[i][4])
        for i in range(len(bars_list))
    ]


def d1_at(d1_states: list[D1State], h1_time: datetime) -> D1State | None:
    """Return the most recently COMPLETED D1 bar whose date is strictly before
    the date of *h1_time*.

    A D1 bar for day D is only finalised at the close of day D.  An H1 candle
    that opens at any point during day D must therefore use the D1 state from
    day D-1 — the last bar whose data is fully known.  Using ``<`` (strictly
    less than) prevents lookahead bias: we never let today's in-progress daily
    bar influence an entry decision that happens earlier the same day.
    """
    target = h1_time.date()
    result = None
    for s in d1_states:
        if s.date < target:   # strictly less than — same-day D1 excluded
            result = s
        else:
            break
    return result


# ── H4 state builder ──────────────────────────────────────────────────────────

@dataclass
class H4State:
    time: datetime
    ema5: Decimal
    ema10: Decimal
    adx: Decimal


def build_h4_states(pair: str) -> list[H4State]:
    import pandas as pd
    import pandas_ta as ta
    h4 = load_candles(pair, "H4")
    closes = pd.Series([float(c.close) for c in h4])
    highs  = pd.Series([float(c.high)  for c in h4])
    lows   = pd.Series([float(c.low)   for c in h4])
    ema5_s  = ta.ema(closes, length=5)
    ema10_s = ta.ema(closes, length=10)
    adx_df  = ta.adx(highs, lows, closes, length=14)
    adx_col = [c for c in adx_df.columns if "ADX" in c.upper() and "DM" not in c.upper()][0]
    return [
        H4State(
            time=h4[i].time,
            ema5=Decimal(str(round(float(ema5_s.iloc[i]), 4)))
                 if not pd.isna(ema5_s.iloc[i]) else Decimal("0"),
            ema10=Decimal(str(round(float(ema10_s.iloc[i]), 4)))
                  if not pd.isna(ema10_s.iloc[i]) else Decimal("0"),
            adx=Decimal(str(round(float(adx_df[adx_col].iloc[i]), 4)))
                if not pd.isna(adx_df[adx_col].iloc[i]) else Decimal("0"),
        )
        for i in range(len(h4))
    ]


def h4_at(h4_states: list[H4State], h1_time: datetime) -> H4State | None:
    result = None
    for s in h4_states:
        if s.time <= h1_time:
            result = s
        else:
            break
    return result


# ── Core sweep runner ─────────────────────────────────────────────────────────

def run_btc_sweep(
    candles, indicators, d1_states, h4_states,
    mode: str,
    d1_adx_thresh: float = 20.0,
    h4_adx_thresh: float = 25.0,
    session_start: int = 0,
    session_end: int = 24,
    skip_weekends: bool = False,
    sl_pct_cap: float = 0.0,    # 0 = no cap; 0.02 = 2% cap
) -> list[Trade]:
    pair = "BTC_USD"
    cfg = BacktestConfig(sl_atr_multiplier=Decimal("1.5"), partial_close_pct=Decimal("0.67"))
    toggles = FilterToggles(use_partial_close=True)
    spread_pips = cfg.spread_pips.get(pair, Decimal("50"))
    pip = PIP_SIZE[pair]
    n = len(candles)
    balance = cfg.starting_balance
    trades = []
    open_trade = None
    cooldown_until = None
    daily_pnl = defaultdict(lambda: Decimal("0"))
    min_units = Decimal("0.01")  # BTC fractional units

    for i in range(200, n - 1):
        candle = candles[i]
        next_candle = candles[i + 1]
        ind = indicators[i]
        hour = candle.time.hour
        dow = candle.time.weekday()   # 0=Mon ... 6=Sun
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
                            balance += _do_partial_close(open_trade, pt, "BUY", pair,
                                                         cfg, toggles, spread_pips, pip)
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
                            balance += _do_partial_close(open_trade, pt, "SELL", pair,
                                                         cfg, toggles, spread_pips, pip)
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

            hc = i - next((j for j in range(i, -1, -1)
                           if candles[j].time <= open_trade.entry_time), i)
            if not sl_hit and hc >= cfg.max_hold_hours:
                sl_hit = True
                exit_price = candle.close
                exit_reason = "MAX_HOLD"

            if sl_hit and exit_price is not None:
                _close_trade(open_trade, exit_price, candle.time, exit_reason,
                             pair, cfg, toggles, spread_pips)
                trades.append(open_trade)
                balance += open_trade.pnl_usd
                daily_pnl[date_key] += open_trade.pnl_usd
                cooldown_until = candle.time
                open_trade = None
            continue

        # ── Entry filters ────────────────────────────────────────────
        if cooldown_until and (candle.time - cooldown_until).total_seconds() < 300:
            continue
        if hour >= 17:
            continue
        if skip_weekends and dow >= 5:
            continue
        if session_start > 0 or session_end < 24:
            if not (session_start <= hour < session_end):
                continue
        if daily_pnl[date_key] <= -cfg.daily_loss_limit_usd:
            continue

        action, score, strategies, regime = quant_evaluate(ind, candle.close, toggles)
        if action == "HOLD":
            continue

        # ── Mode-specific multi-timeframe filters ────────────────────
        if mode == "d1_ema_only":
            d1 = d1_at(d1_states, candle.time)
            if d1 is not None and d1.ema5 > 0 and d1.ema10 > 0:
                if action == "BUY"  and d1.ema5 <= d1.ema10: continue
                if action == "SELL" and d1.ema5 >= d1.ema10: continue

        elif mode == "d1_ema_adx":
            d1 = d1_at(d1_states, candle.time)
            if d1 is not None and d1.ema5 > 0 and d1.ema10 > 0:
                if float(d1.adx) < d1_adx_thresh:              continue
                if action == "BUY"  and d1.ema5 <= d1.ema10:   continue
                if action == "SELL" and d1.ema5 >= d1.ema10:   continue

        elif mode == "h4_ema_adx":
            h4 = h4_at(h4_states, candle.time)
            if h4 is not None and h4.ema5 > 0 and h4.ema10 > 0:
                if float(h4.adx) < h4_adx_thresh:              continue
                if action == "BUY"  and h4.ema5 <= h4.ema10:   continue
                if action == "SELL" and h4.ema5 >= h4.ema10:   continue

        elif mode == "triple_screen":
            d1 = d1_at(d1_states, candle.time)
            if d1 is not None and d1.ema5 > 0 and d1.ema10 > 0:
                if action == "BUY"  and d1.ema5 <= d1.ema10:   continue
                if action == "SELL" and d1.ema5 >= d1.ema10:   continue
            h4 = h4_at(h4_states, candle.time)
            if h4 is not None and h4.adx > 0:
                if float(h4.adx) < h4_adx_thresh:              continue

        elif mode == "d1_session":
            # D1 EMA5>EMA10 trend filter combined with the session window
            # already applied above by session_start/session_end parameters.
            d1 = d1_at(d1_states, candle.time)
            if d1 is not None and d1.ema5 > 0 and d1.ema10 > 0:
                if action == "BUY"  and d1.ema5 <= d1.ema10: continue
                if action == "SELL" and d1.ema5 >= d1.ema10: continue

        # ── Standard sizing ──────────────────────────────────────────
        if not (cfg.confidence_floor <= score <= cfg.confidence_ceiling):
            continue
        atr = ind.atr_14
        if atr == 0:
            continue
        sl_dist = atr * cfg.sl_atr_multiplier
        sl_pips = sl_dist / pip
        if sl_pips < cfg.min_sl_pips:
            continue

        # Optional SL % cap (test variant only)
        if sl_pct_cap > 0:
            ep_check = next_candle.open
            if ep_check > 0 and float(sl_dist / ep_check) > sl_pct_cap:
                continue

        ep = next_candle.open + (cfg.slippage_pips * pip if action == "BUY"
                                  else -cfg.slippage_pips * pip)
        sl = round_price(ep - sl_dist if action == "BUY" else ep + sl_dist, pair)
        risk_pct = confidence_tier_risk_pct(score, cfg, toggles)
        risk_usd = balance * risk_pct
        pv = pip_value_per_unit(pair, ep)
        if pv == 0:
            continue
        units = Decimal(str(float(risk_usd) / (float(sl_pips) * float(pv))))
        units = units.quantize(Decimal("0.01"))
        if units < min_units:
            continue
        units = min(units, Decimal("500000"))
        open_trade = Trade(pair=pair, direction=action, entry_price=ep, stop_loss=sl,
                           entry_time=next_candle.time, units=units, confidence_score=score,
                           strategies_fired="+".join(strategies), regime=mode,
                           initial_sl_distance=sl_dist)

    if open_trade is not None:
        _close_trade(open_trade, candles[-1].close, candles[-1].time, "END",
                     pair, cfg, toggles, spread_pips)
        trades.append(open_trade)
    return trades


def main():
    pair = "BTC_USD"
    print("BTC_USD D1 Trend + Session Sweep")
    print("Prior best: 7 Codex variants, best PF 1.14 (1/5 gates) -- H4+ATR+divergence")
    print("Testing: D1 synthetic trend, triple-screen, session filters\n")

    candles = load_candles(pair, "H1")
    indicators = precompute_indicators(candles)
    print(f"H1: {len(candles)} bars  ({candles[0].time.date()} to {candles[-1].time.date()})")

    print("Building D1 synthetic bars from H4...")
    d1_states = build_d1_from_h4(pair)
    print(f"D1: {len(d1_states)} daily bars")

    print("Building H4 states...")
    h4_states = build_h4_states(pair)
    print(f"H4: {len(h4_states)} bars\n")

    # (label, mode, d1_adx_thresh, h4_adx_thresh, sess_start, sess_end, skip_wknd, sl_pct_cap)
    configs = [
        ("Baseline (no filter)",           "baseline",      20, 25,  0, 24, False, 0.0),
        ("D1 EMA5>10 only",                "d1_ema_only",   20, 25,  0, 24, False, 0.0),
        ("D1 EMA5>10 + ADX>=15",           "d1_ema_adx",    15, 25,  0, 24, False, 0.0),
        ("D1 EMA5>10 + ADX>=20",           "d1_ema_adx",    20, 25,  0, 24, False, 0.0),
        ("D1 EMA5>10 + ADX>=25",           "d1_ema_adx",    25, 25,  0, 24, False, 0.0),
        ("H4 EMA5>10 + ADX>=20",           "h4_ema_adx",    20, 20,  0, 24, False, 0.0),
        ("H4 EMA5>10 + ADX>=25",           "h4_ema_adx",    20, 25,  0, 24, False, 0.0),
        ("Triple: D1+H4ADX>=20",           "triple_screen", 20, 20,  0, 24, False, 0.0),
        ("Triple: D1+H4ADX>=25",           "triple_screen", 20, 25,  0, 24, False, 0.0),
        ("D1 + US session (13-17h)",        "d1_session",    20, 25, 13, 17, False, 0.0),
        ("D1 EMA only + weekday",           "d1_ema_only",   20, 25,  0, 24, True,  0.0),
        ("D1+ADX20 + weekday",              "d1_ema_adx",    20, 25,  0, 24, True,  0.0),
        ("Triple + weekday",                "triple_screen", 20, 25,  0, 24, True,  0.0),
        ("Triple + US session + weekday",   "triple_screen", 20, 25, 13, 17, True,  0.0),
        ("D1+ADX20 + SL<=2%",              "d1_ema_adx",    20, 25,  0, 24, False, 0.02),
        ("Triple+weekday + SL<=2%",         "triple_screen", 20, 25,  0, 24, True,  0.02),
    ]

    print(f"{'Mode':<42} {'N':>4} {'WR':>6} {'PF':>5} {'Sharpe':>7} {'MAR':>5} {'MaxDD':>7} {'MC':>6} {'Gates':>6}")
    print("-" * 96)

    best = {"gates": 0, "pf": 0, "label": "", "n": 0}
    for cfg_row in configs:
        label, mode, d1_adx, h4_adx, ss, se, wknd, sl_cap = cfg_row
        trades = run_btc_sweep(
            candles, indicators, d1_states, h4_states,
            mode=mode, d1_adx_thresh=d1_adx, h4_adx_thresh=h4_adx,
            session_start=ss, session_end=se, skip_weekends=wknd, sl_pct_cap=sl_cap,
        )
        if not trades:
            print(f"{label:<42}  (no trades)")
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
        flag = " <<<" if gates >= 5 else (" < " if gates >= 3 else "")
        if gates > best["gates"] or (gates == best["gates"] and r.profit_factor > best["pf"]):
            best = {"gates": gates, "pf": float(r.profit_factor), "label": label, "n": n}
        print(f"{label:<42} {n:>4} {r.win_rate:>6.1%} {r.profit_factor:>5.2f} "
              f"{r.sharpe_annualized:>7.2f} {r.mar:>5.2f} {r.max_drawdown_pct:>6.2f}% "
              f"{mc_p:>6.1%} [{gates}/5]{flag}")

    print(f"\nBest: {best['label']} -- {best['gates']}/5 gates  N={best['n']}  PF={best['pf']:.2f}")

    if best["gates"] >= 5:
        print("\n>>> 5/5 GATES -- BTC_USD configuration found!")
        print(">>> Run with 10k MC sims to confirm before live deployment.")
    elif best["gates"] >= 3:
        print(f"\n>>> {best['gates']}/5 gates -- improvement over prior best (1/5).")
        print(">>> May need walk-forward validation and 5k MC to confirm.")
    else:
        print("\n>>> BTC H1 signal quality ceiling may require a fundamentally different signal.")
        print(">>> Recommendation: keep BTC PAPER ONLY, revisit with D1/W1 signal approach.")


if __name__ == "__main__":
    main()
