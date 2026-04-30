"""
EMA200 Trend-Alignment Filter Sweep - USD_JPY
Tests the hypothesis: only take signals aligned with the 200-period EMA macro trend.
  BUY  only when candle.close > ema_200
  SELL only when candle.close < ema_200

Reports baseline vs EMA200-filtered comparison.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_v2 import (
    BacktestConfig,
    BacktestResult,
    FilterToggles,
    PIP_SIZE,
    Trade,
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
)
from collections import defaultdict


def run_with_ema200_filter(
    pair: str,
    candles,
    indicators,
    cfg: BacktestConfig,
    toggles: FilterToggles,
    use_ema200: bool,
    label: str = "baseline",
):
    """run_backtest but with an optional EMA200 macro-trend gate injected."""
    if len(candles) != len(indicators):
        raise ValueError("length mismatch")
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

        # EMA200 macro-trend gate (the filter being tested)
        if use_ema200 and ind.ema_200 > 0:
            if action == "BUY" and candle.close < ind.ema_200:
                continue
            if action == "SELL" and candle.close > ind.ema_200:
                continue

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
            regime=regime,
            initial_sl_distance=sl_distance,
        )

    if open_trade is not None:
        last = candles[-1]
        _close_trade(open_trade, last.close, last.time, "BACKTEST_END", pair, cfg, toggles,
                     cfg.spread_pips.get(pair, Decimal("1.5")))
        trades.append(open_trade)

    for t in trades:
        t.strategies_fired = f"{label}:{t.strategies_fired}" if label != "baseline" else t.strategies_fired
    return trades


def fmt(r: BacktestResult) -> str:
    pf_pass = "PASS" if r.profit_factor >= 1.50 else "FAIL"
    sh_pass = "PASS" if r.sharpe_annualized >= 1.00 else "FAIL"
    mar_pass = "PASS" if r.mar >= 0.50 else "FAIL"
    return (
        f"  Trades : {r.win_count + r.loss_count + r.breakeven_count}  "
        f"W/L {r.win_count}/{r.loss_count}  WR {r.win_rate:.1%}\n"
        f"  PF     : {r.profit_factor:.2f} [{pf_pass}]  (need >=1.50)\n"
        f"  Sharpe : {r.sharpe_annualized:.2f} [{sh_pass}]  (need >=1.00)\n"
        f"  MAR    : {r.mar:.2f} [{mar_pass}]  (need >=0.50)\n"
        f"  MaxDD  : {r.max_drawdown_pct:.1%}\n"
        f"  Total  : ${r.total_pnl:,.0f}"
    )


def main():
    pair = "USD_JPY"
    print("\n" + "=" * 60)
    print(f"EMA200 Trend Filter Sweep - {pair}")
    print("=" * 60)

    candles = load_candles(pair)
    indicators = precompute_indicators(candles)
    print(f"Loaded {len(candles)} candles")

    cfg = BacktestConfig()
    toggles_base = FilterToggles(use_partial_close=True)

    # Baseline (no EMA200 filter)
    base_trades = run_with_ema200_filter(pair, candles, indicators, cfg, toggles_base,
                                         use_ema200=False, label="baseline")
    base_result = compute_metrics(pair, "baseline", base_trades, cfg.starting_balance)

    # EMA200 filtered
    ema_trades = run_with_ema200_filter(pair, candles, indicators, cfg, toggles_base,
                                        use_ema200=True, label="ema200")
    ema_result = compute_metrics(pair, "ema200", ema_trades, cfg.starting_balance)

    # Monte Carlo for EMA200 variant
    mc_data = monte_carlo(ema_trades, cfg.starting_balance, n_sim=5000)
    mc_p_profit = mc_data["p_profit"]

    print("\n--- BASELINE (partial close, no EMA200 filter) ---")
    print(fmt(base_result))

    print("\n--- WITH EMA200 MACRO TREND FILTER ---")
    print(fmt(ema_result))
    print(f"  MC P(profit) : {mc_p_profit:.1%}  (need >=85%)")

    thresholds = {
        "PF>=1.50": ema_result.profit_factor >= 1.50,
        "Sharpe>=1.00": ema_result.sharpe_annualized >= 1.00,
        "MAR>=0.50": ema_result.mar >= 0.50,
        "MC>=85%": mc_p_profit >= 0.85,
        "MaxDD<=10%": ema_result.max_drawdown_pct <= 0.10,
    }
    passed = sum(thresholds.values())
    print(f"\nLive Threshold Gates: {passed}/5")
    for name, ok in thresholds.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    if passed >= 4:
        print("\n>>> READY: Add use_ema200_trend_filter to backtest_v2 and live engine.")
    elif passed >= 3:
        print("\n>>> PARTIAL: Some gates pass. Combine with other layers before enabling live.")
    else:
        print("\n>>> INSUFFICIENT: EMA200 filter alone does not meet live thresholds.")

    # Direction breakdown
    buy_base = sum(1 for t in base_trades if t.direction == "BUY")
    sell_base = sum(1 for t in base_trades if t.direction == "SELL")
    buy_ema = sum(1 for t in ema_trades if t.direction == "BUY")
    sell_ema = sum(1 for t in ema_trades if t.direction == "SELL")
    print(f"\nDirection split - Baseline: {buy_base}B/{sell_base}S  ->  EMA200: {buy_ema}B/{sell_ema}S")
    print(f"Filtered out: {buy_base - buy_ema} BUY, {sell_base - sell_ema} SELL counter-trend trades")


if __name__ == "__main__":
    main()
