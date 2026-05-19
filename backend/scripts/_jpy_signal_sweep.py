"""
USD_JPY New Signal Stack Sweep
The current EMA+BB+Momentum stack fails because USD_JPY is a counter-trend/ranging pair.
Tests 3 alternative signal approaches suited to JPY's character:

1. RSI_REVERSION: mean-reversion on RSI extremes (oversold/overbought)
2. BB_RSI_REVERSION: Bollinger Band touch + RSI confirmation (classic range trade)
3. MACD_ZERO_CROSS: MACD line crosses zero — catches momentum shifts without trend bias

All variants use partial close 67% at 1.5xRR, 2.5x ATR SL (best from SL sweep).
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_v2 import (
    BacktestConfig,
    FilterToggles,
    Indicators,
    Trade,
    PIP_SIZE,
    _close_trade,
    _do_partial_close,
    compute_metrics,
    monte_carlo,
    load_candles,
    precompute_indicators,
    BREAKEVEN_PIPS,
    TRAIL_ACTIVATION_PIPS,
    _FRACTIONAL_UNIT_PAIRS,
    confidence_tier_risk_pct,
    pip_value_per_unit,
    round_price,
)
from collections import defaultdict


# ─── Signal Functions ─────────────────────────────���────────────────────────────

def rsi_reversion_signal(ind: Indicators) -> tuple[str, float]:
    """Mean reversion on RSI extremes. BUY oversold, SELL overbought."""
    rsi = float(ind.rsi_14)
    if rsi < 25:
        return "BUY", 0.78
    if rsi < 30:
        return "BUY", 0.72
    if rsi > 75:
        return "SELL", 0.78
    if rsi > 70:
        return "SELL", 0.72
    return "HOLD", 0.0


def bb_rsi_reversion_signal(ind: Indicators, price: Decimal) -> tuple[str, float]:
    """Price at/below BB lower + RSI < 40 → BUY. Price at/above BB upper + RSI > 60 → SELL."""
    rsi = float(ind.rsi_14)
    px = float(price)
    bb_u = float(ind.bb_upper)
    bb_l = float(ind.bb_lower)
    bb_m = float(ind.bb_mid)
    if bb_u == 0 or bb_l == 0:
        return "HOLD", 0.0
    width = bb_u - bb_l
    if width == 0:
        return "HOLD", 0.0
    dist_from_mid = (px - bb_m) / (width / 2)

    if dist_from_mid <= -0.90 and rsi < 40:
        score = 0.78 if rsi < 30 else 0.72
        return "BUY", score
    if dist_from_mid >= 0.90 and rsi > 60:
        score = 0.78 if rsi > 70 else 0.72
        return "SELL", score
    return "HOLD", 0.0


def macd_zero_cross_signal(ind: Indicators) -> tuple[str, float]:
    """MACD line crosses zero line — momentum shift without trend bias."""
    macd = float(ind.macd_line)
    signal = float(ind.macd_signal)
    hist = float(ind.macd_histogram)
    rsi = float(ind.rsi_14)

    # BUY: MACD just crossed above zero and histogram expanding
    if macd > 0 and hist > 0 and abs(macd) < abs(signal) * 0.5 and rsi < 65:
        return "BUY", 0.72
    # SELL: MACD just crossed below zero and histogram expanding negative
    if macd < 0 and hist < 0 and abs(macd) < abs(signal) * 0.5 and rsi > 35:
        return "SELL", 0.72
    return "HOLD", 0.0


def ema_cross_signal(ind: Indicators) -> tuple[str, float]:
    """EMA 20/50 crossover only (no EMA200 requirement). Catches short-term momentum."""
    ema20 = float(ind.ema_20)
    ema50 = float(ind.ema_50)
    if ema20 == 0 or ema50 == 0:
        return "HOLD", 0.0
    macd_hist = float(ind.macd_histogram)
    rsi = float(ind.rsi_14)

    if ema20 > ema50 and macd_hist > 0 and 45 < rsi < 70:
        return "BUY", 0.74
    if ema20 < ema50 and macd_hist < 0 and 30 < rsi < 55:
        return "SELL", 0.74
    return "HOLD", 0.0


SIGNAL_VARIANTS = {
    "rsi_reversion":    lambda ind, px: rsi_reversion_signal(ind),
    "bb_rsi_reversion": lambda ind, px: bb_rsi_reversion_signal(ind, px),
    "macd_zero_cross":  lambda ind, px: macd_zero_cross_signal(ind),
    "ema_cross":        lambda ind, px: ema_cross_signal(ind),
    "rsi+bb_combined":  lambda ind, px: _combined(ind, px),
}


def _combined(ind: Indicators, px: Decimal) -> tuple[str, float]:
    """RSI reversion AND BB_RSI must agree."""
    a1, s1 = rsi_reversion_signal(ind)
    a2, s2 = bb_rsi_reversion_signal(ind, px)
    if a1 == a2 and a1 != "HOLD":
        return a1, max(s1, s2)
    return "HOLD", 0.0


# ─── Backtest Runner ──────────────────────────────────────────────────────────

def run_with_signal(pair, candles, indicators, cfg, toggles, signal_fn, label):
    """Run backtest using a custom signal function instead of quant_evaluate."""
    n = len(candles)
    if n < 250:
        return []

    balance = cfg.starting_balance
    trades = []
    open_trade = None
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
                            # Don't book pc_pnl here — _close_trade sets
                            # pnl_usd = remaining_leg + partial_close_pnl_usd,
                            # so the balance update at final close covers it.
                            # Booking here AND there double-counts partial PnL.
                            _do_partial_close(open_trade, pt, "BUY", pair, cfg, toggles, spread_pips, pip)
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
                            _do_partial_close(open_trade, pt, "SELL", pair, cfg, toggles, spread_pips, pip)
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

        # No open position
        if toggles.use_cooldown and cooldown_until is not None:
            if (candle.time - cooldown_until).total_seconds() < cfg.cooldown_seconds:
                continue
        if toggles.use_global_cutoff_17_utc and hour >= 17:
            continue
        if toggles.use_session_window and not (sess_start <= hour < sess_end):
            continue
        if toggles.use_daily_loss_limit and daily_pnl[date_key] <= -cfg.daily_loss_limit_usd:
            continue

        action, score = signal_fn(ind, candle.close)
        if action == "HOLD":
            continue

        # Confidence band
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
            strategies_fired=label,
            regime="custom",
            initial_sl_distance=sl_distance,
        )

    if open_trade is not None:
        last = candles[-1]
        _close_trade(open_trade, last.close, last.time, "BACKTEST_END", pair, cfg, toggles, spread_pips)
        trades.append(open_trade)
    return trades


def main():
    pair = "USD_JPY"
    candles = load_candles(pair)
    indicators = precompute_indicators(candles)
    print(f"\nLoaded {len(candles)} {pair} candles")
    print(f"\n{'Signal':<20} {'N':>4} {'WR':>6} {'PF':>5} {'Sharpe':>7} {'MAR':>5} {'MaxDD':>6} {'MC':>6} {'Gates':>6}")
    print("-" * 73)

    cfg = BacktestConfig(
        sl_atr_multiplier=Decimal("2.5"),
        partial_close_pct=Decimal("0.67"),
    )
    toggles = FilterToggles(use_partial_close=True)

    best = {"gates": 0, "label": "", "r": None, "mc": 0}

    for sig_name, sig_fn in SIGNAL_VARIANTS.items():
        trades = run_with_signal(pair, candles, indicators, cfg, toggles, sig_fn, sig_name)
        if not trades:
            print(f"{sig_name:<20} {'(no trades)':>50}")
            continue
        r = compute_metrics(pair, sig_name, trades, cfg.starting_balance)
        mc_data = monte_carlo(trades, cfg.starting_balance, n_sim=3000)
        mc_p = mc_data["p_profit"]
        gates = sum([
            r.profit_factor >= 1.50,
            r.sharpe_annualized >= 1.00,
            r.mar >= 0.50,
            mc_p >= 0.85,
            r.max_drawdown_pct <= 10.0,
        ])
        if gates > best["gates"]:
            best = {"gates": gates, "label": sig_name, "r": r, "mc": mc_p}
        n = r.win_count + r.loss_count + r.breakeven_count
        print(
            f"{sig_name:<20} {n:>4} {r.win_rate:>6.1%} {r.profit_factor:>5.2f} "
            f"{r.sharpe_annualized:>7.2f} {r.mar:>5.2f} {r.max_drawdown_pct:>6.2f}% "
            f"{mc_p:>6.1%} [{gates}/5]"
        )

    print(f"\nBest: {best['label']} — {best['gates']}/5 gates")
    if best["r"]:
        r = best["r"]
        print(f"  PF {r.profit_factor:.2f}  Sharpe {r.sharpe_annualized:.2f}  MAR {r.mar:.2f}  MaxDD {r.max_drawdown_pct:.2f}%  MC {best['mc']:.1%}")

    if best["gates"] >= 4:
        print("\n>>> LIVE READY with this signal stack.")
    elif best["gates"] >= 3:
        print("\n>>> CLOSE - 3/5 gates. Try combining with existing quant signals or tweaking confidence band.")
    else:
        print("\n>>> STILL INSUFFICIENT. May need fundamentally different data (news sentiment, COT reports).")


if __name__ == "__main__":
    main()
