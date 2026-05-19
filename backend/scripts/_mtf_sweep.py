"""
Multi-Timeframe Confluence (MTF) Backtest — USD_JPY and BTC_USD
Architecture:
  H4 candles → compute trend state (bull/bear/neutral)
  H1 candles → existing quant signals for entry timing
  Filter: only enter H1 signal if it aligns with H4 trend bias

H4 trend state determination:
  BULL:    EMA20_H4 > EMA50_H4 > EMA200_H4  AND  close > EMA200_H4
  BEAR:    EMA20_H4 < EMA50_H4 < EMA200_H4  AND  close < EMA200_H4
  NEUTRAL: neither (choppy / unclear)

Signal filtering modes:
  A) strict:   only enter when H4 is clearly BULL (for BUY) or BEAR (for SELL)
  B) weak:     enter when H4 EMA20 > EMA50 (BUY) or EMA20 < EMA50 (SELL) [just 2-EMA cross]
  C) no_neutral: reject entries when H4 is NEUTRAL; allow BULL or BEAR both directions
  D) h4_adx:  only enter when H4 ADX >= 20 (trending on H4) in the right direction

Alignment: for H1 bar at time T, use the most recently COMPLETED H4 bar at time <= T.
This is strictly no-lookahead — we never use the in-progress H4 candle.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_v2 import (
    BacktestConfig,
    FilterToggles,
    Indicators,
    Trade,
    PIP_SIZE,
    SESSION_HOURS_LIVE,
    _close_trade,
    _do_partial_close,
    compute_metrics,
    monte_carlo,
    load_candles,
    precompute_indicators,
    quant_evaluate,
    BREAKEVEN_PIPS,
    TRAIL_ACTIVATION_PIPS,
    _FRACTIONAL_UNIT_PAIRS,
    confidence_tier_risk_pct,
    pip_value_per_unit,
    round_price,
    compute_adx_series,
)
from collections import defaultdict
from datetime import datetime, timedelta


# ─── H4 Trend State ───────────────────────────────────────────────────────────

@dataclass
class H4State:
    time: datetime
    ema20: Decimal
    ema50: Decimal
    ema200: Decimal
    adx: Decimal
    close: Decimal

    @property
    def trend(self) -> str:
        if self.ema20 == 0 or self.ema50 == 0 or self.ema200 == 0:
            return "NEUTRAL"
        if self.ema20 > self.ema50 > self.ema200 and self.close > self.ema200:
            return "BULL"
        if self.ema20 < self.ema50 < self.ema200 and self.close < self.ema200:
            return "BEAR"
        return "NEUTRAL"

    @property
    def weak_bull(self) -> bool:
        return self.ema20 > self.ema50

    @property
    def weak_bear(self) -> bool:
        return self.ema20 < self.ema50

    @property
    def adx_trending(self) -> bool:
        return float(self.adx) >= 20.0


def build_h4_states(pair: str) -> list[H4State]:
    from scripts.backtest_v2 import compute_ema_series, Candle
    candles = load_candles(pair, "H4")
    indicators = precompute_indicators(candles)
    states = []
    for i, (c, ind) in enumerate(zip(candles, indicators)):
        states.append(H4State(
            time=c.time,
            ema20=ind.ema_20,
            ema50=ind.ema_50,
            ema200=ind.ema_200,
            adx=ind.adx_14,
            close=c.close,
        ))
    return states


def h4_state_at(h4_states: list[H4State], h1_time: datetime) -> H4State | None:
    """Return the most recently COMPLETED H4 state whose close is at or before h1_time.

    H4 candles are stored with open timestamps. A candle that opens at T closes
    at T+4h, so it must not be used by any H1 bar earlier than T+4h.
    """
    result = None
    for state in h4_states:
        if state.time + timedelta(hours=4) <= h1_time:
            result = state
        else:
            break
    return result


# ─── MTF Backtest Engine ──────────────────────────────────────────────────────

def run_mtf(
    pair: str,
    candles,
    indicators,
    h4_states: list[H4State],
    cfg: BacktestConfig,
    toggles: FilterToggles,
    mode: str,  # "strict" | "weak" | "no_neutral" | "h4_adx"
    label: str,
) -> list[Trade]:
    n = len(candles)
    if n < 250:
        return []

    balance = cfg.starting_balance
    trades: list[Trade] = []
    open_trade: Trade | None = None
    cooldown_until = None

    sess_start, sess_end = cfg.session_hours.get(pair, (0, 24))
    spread_pips = cfg.spread_pips.get(pair, Decimal("1.5"))
    pip = PIP_SIZE[pair]
    daily_pnl = defaultdict(lambda: Decimal("0"))
    warmup = max(200, 28)

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
                            pc_pnl = _do_partial_close(open_trade, pt, "BUY", pair, cfg, toggles, spread_pips, pip)
                            balance += pc_pnl
                            daily_pnl[date_key] += pc_pnl
                    profit_pips = (candle.close - open_trade.entry_price) / pip
                    if toggles.use_breakeven and not open_trade.breakeven_set and profit_pips >= BREAKEVEN_PIPS[pair]:
                        open_trade.stop_loss = open_trade.entry_price
                        open_trade.breakeven_set = True
                    if toggles.use_trailing_stop and profit_pips >= TRAIL_ACTIVATION_PIPS[pair]:
                        if not open_trade.trailing_active:
                            open_trade.trailing_active = True
                        trail_distance = max(
                            (open_trade.entry_price - open_trade.stop_loss).copy_abs(),
                            cfg.sl_atr_multiplier * pip * Decimal("15"),
                        )
                        new_sl = candle.close - trail_distance
                        if new_sl > open_trade.stop_loss:
                            open_trade.stop_loss = new_sl
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
                            pc_pnl = _do_partial_close(open_trade, pt, "SELL", pair, cfg, toggles, spread_pips, pip)
                            balance += pc_pnl
                            daily_pnl[date_key] += pc_pnl
                    profit_pips = (open_trade.entry_price - candle.close) / pip
                    if toggles.use_breakeven and not open_trade.breakeven_set and profit_pips >= BREAKEVEN_PIPS[pair]:
                        open_trade.stop_loss = open_trade.entry_price
                        open_trade.breakeven_set = True
                    if toggles.use_trailing_stop and profit_pips >= TRAIL_ACTIVATION_PIPS[pair]:
                        if not open_trade.trailing_active:
                            open_trade.trailing_active = True
                        trail_distance = max(
                            (open_trade.stop_loss - open_trade.entry_price).copy_abs(),
                            cfg.sl_atr_multiplier * pip * Decimal("15"),
                        )
                        new_sl = candle.close + trail_distance
                        if new_sl < open_trade.stop_loss:
                            open_trade.stop_loss = new_sl

            if not sl_hit and toggles.use_max_hold:
                hold_candles = i - next(
                    (j for j in range(i, -1, -1) if candles[j].time <= open_trade.entry_time), i
                )
                if hold_candles >= cfg.max_hold_hours:
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

        # No open position - evaluate signal
        if toggles.use_cooldown and cooldown_until is not None:
            if (candle.time - cooldown_until).total_seconds() < cfg.cooldown_seconds:
                continue
        if toggles.use_global_cutoff_17_utc and hour >= 17:
            continue
        if toggles.use_session_window and not (sess_start <= hour < sess_end):
            continue
        if toggles.use_daily_loss_limit and daily_pnl[date_key] <= -cfg.daily_loss_limit_usd:
            continue

        action, score, strategies, regime = quant_evaluate(ind, candle.close, toggles)
        if action == "HOLD":
            continue

        # ── H4 Multi-Timeframe Filter ─────────────────────────────────────────
        h4 = h4_state_at(h4_states, candle.time)
        if h4 is not None:
            if mode == "strict":
                if action == "BUY" and h4.trend != "BULL":
                    continue
                if action == "SELL" and h4.trend != "BEAR":
                    continue
            elif mode == "weak":
                if action == "BUY" and not h4.weak_bull:
                    continue
                if action == "SELL" and not h4.weak_bear:
                    continue
            elif mode == "no_neutral":
                if h4.trend == "NEUTRAL":
                    continue
                # Allow BULL or BEAR regardless of direction — still need H1 agreement
                if action == "BUY" and h4.trend == "BEAR":
                    continue
                if action == "SELL" and h4.trend == "BULL":
                    continue
            elif mode == "h4_adx":
                if not h4.adx_trending:
                    continue
                if action == "BUY" and not h4.weak_bull:
                    continue
                if action == "SELL" and not h4.weak_bear:
                    continue
        # ─────────────────────────────────────────────────────────────────────

        if toggles.use_confidence_band:
            if score < cfg.confidence_floor or score > cfg.confidence_ceiling:
                continue

        atr = ind.atr_14
        if atr == 0:
            continue
        sl_distance = atr * cfg.sl_atr_multiplier
        sl_pips = sl_distance / pip
        if toggles.use_min_sl_pips and sl_pips < cfg.min_sl_pips:
            continue

        entry_price = next_candle.open
        if toggles.use_friction:
            slip_amt = cfg.slippage_pips * pip
            entry_price = entry_price + slip_amt if action == "BUY" else entry_price - slip_amt

        sl = entry_price - sl_distance if action == "BUY" else entry_price + sl_distance
        sl = round_price(sl, pair)

        risk_pct = confidence_tier_risk_pct(score, cfg, toggles)
        risk_usd = balance * risk_pct
        pv = pip_value_per_unit(pair, entry_price)
        if pv == 0:
            continue
        raw_units = risk_usd / (sl_pips * pv)
        if pair in _FRACTIONAL_UNIT_PAIRS:
            units = max(Decimal("0"), raw_units.quantize(Decimal("0.01")))
            min_units = Decimal("0.01")
        else:
            units = Decimal(max(0, int(raw_units)))
            min_units = Decimal("1000")
        units = min(units, Decimal(str(cfg.max_units)))
        if units < min_units:
            continue

        open_trade = Trade(
            pair=pair,
            direction=action,
            entry_price=entry_price,
            stop_loss=sl,
            entry_time=next_candle.time,
            units=units,
            confidence_score=score,
            strategies_fired="+".join(strategies),
            regime=f"H4:{h4.trend if h4 else 'UNK'}",
            initial_sl_distance=sl_distance,
        )

    if open_trade is not None:
        last = candles[-1]
        _close_trade(open_trade, last.close, last.time, "BACKTEST_END", pair, cfg, toggles,
                     cfg.spread_pips.get(pair, Decimal("1.5")))
        trades.append(open_trade)

    return trades


def run_pair(pair: str, sl_mult: float, max_hold: int) -> None:
    print(f"\n{'=' * 70}")
    print(f"MTF Sweep — {pair}  (SL={sl_mult}x ATR, max_hold={max_hold}h, partial_close 67%)")
    print(f"{'=' * 70}")

    candles = load_candles(pair)
    indicators = precompute_indicators(candles)
    h4_states = build_h4_states(pair)
    print(f"H1: {len(candles)} candles  H4: {len(h4_states)} candles")

    cfg = BacktestConfig(
        sl_atr_multiplier=Decimal(str(sl_mult)),
        partial_close_pct=Decimal("0.67"),
        max_hold_hours=max_hold,
    )
    toggles = FilterToggles(use_partial_close=True)

    print(f"\n{'Mode':<14} {'N':>4} {'WR':>6} {'PF':>5} {'Sharpe':>7} {'MAR':>5} {'MaxDD':>6} {'MC':>6} {'Dir B/S':>8} {'Gates':>6}")
    print("-" * 73)

    best = {"gates": 0, "label": "", "r": None, "mc": 0}

    # Baseline (no H4 filter) for comparison
    from scripts.backtest_v2 import run_backtest
    base_trades = run_backtest(pair, candles, indicators, cfg, toggles, label="baseline")
    r = compute_metrics(pair, "baseline", base_trades, cfg.starting_balance)
    mc_data = monte_carlo(base_trades, cfg.starting_balance, n_sim=3000)
    mc_p = mc_data["p_profit"]
    gates = sum([r.profit_factor >= 1.50, r.sharpe_annualized >= 1.00, r.mar >= 0.50, mc_p >= 0.85, r.max_drawdown_pct <= 10.0])
    nb = sum(1 for t in base_trades if t.direction == "BUY")
    ns = sum(1 for t in base_trades if t.direction == "SELL")
    n = r.win_count + r.loss_count + r.breakeven_count
    print(f"{'[no_h4_filter]':<14} {n:>4} {r.win_rate:>6.1%} {r.profit_factor:>5.2f} {r.sharpe_annualized:>7.2f} {r.mar:>5.2f} {r.max_drawdown_pct:>6.2f}% {mc_p:>6.1%} {nb:>3}B/{ns:<3}S [{gates}/5]")
    if gates > best["gates"]:
        best = {"gates": gates, "label": "no_h4_filter", "r": r, "mc": mc_p}

    for mode in ["weak", "no_neutral", "strict", "h4_adx"]:
        trades = run_mtf(pair, candles, indicators, h4_states, cfg, toggles, mode, f"mtf_{mode}")
        if not trades:
            print(f"{mode:<14} {'(no trades)':>50}")
            continue
        r = compute_metrics(pair, mode, trades, cfg.starting_balance)
        mc_data = monte_carlo(trades, cfg.starting_balance, n_sim=3000)
        mc_p = mc_data["p_profit"]
        gates = sum([r.profit_factor >= 1.50, r.sharpe_annualized >= 1.00, r.mar >= 0.50, mc_p >= 0.85, r.max_drawdown_pct <= 10.0])
        nb = sum(1 for t in trades if t.direction == "BUY")
        ns = sum(1 for t in trades if t.direction == "SELL")
        n = r.win_count + r.loss_count + r.breakeven_count
        print(
            f"{mode:<14} {n:>4} {r.win_rate:>6.1%} {r.profit_factor:>5.2f} "
            f"{r.sharpe_annualized:>7.2f} {r.mar:>5.2f} {r.max_drawdown_pct:>6.2f}% "
            f"{mc_p:>6.1%} {nb:>3}B/{ns:<3}S [{gates}/5]"
        )
        if gates > best["gates"]:
            best = {"gates": gates, "label": mode, "r": r, "mc": mc_p}

    # Best result detail
    r = best["r"]
    if r:
        print(f"\nBest: {best['label']} — {best['gates']}/5 gates")
        pf_ok  = "PASS" if r.profit_factor >= 1.50 else "FAIL"
        sh_ok  = "PASS" if r.sharpe_annualized >= 1.00 else "FAIL"
        mar_ok = "PASS" if r.mar >= 0.50 else "FAIL"
        mc_ok  = "PASS" if best["mc"] >= 0.85 else "FAIL"
        dd_ok  = "PASS" if r.max_drawdown_pct <= 10.0 else "FAIL"
        print(f"  PF {r.profit_factor:.2f} [{pf_ok}]  Sharpe {r.sharpe_annualized:.2f} [{sh_ok}]  MAR {r.mar:.2f} [{mar_ok}]  MaxDD {r.max_drawdown_pct:.2f}% [{dd_ok}]  MC {best['mc']:.1%} [{mc_ok}]")


def main():
    print("Multi-Timeframe Confluence Backtest")
    print("H4 trend bias filter applied to H1 entry signals\n")

    run_pair("USD_JPY", sl_mult=2.5, max_hold=24)
    run_pair("BTC_USD", sl_mult=1.5, max_hold=96)


if __name__ == "__main__":
    main()
