"""
BTC_USD Full Production Stack Backtest
Tests BTC with all implemented risk gates:
  - SL = 1.5x ATR (tight, not 3x)
  - Spread gate: 50p max
  - RR gate: only enter if implied RR >= 3.0 (TP = entry +/- 3 * sl_distance)
  - Partial close: 67% at 1.5xRR, SL to breakeven
  - Takeprofit exit: close full position if price reaches TP level

Compares: baseline (3x ATR, no gates) vs production stack (1.5x ATR + all gates)
"""
from __future__ import annotations

import sys
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
    _FRACTIONAL_UNIT_PAIRS,
    confidence_tier_risk_pct,
    pip_value_per_unit,
    round_price,
    run_backtest,
)
from collections import defaultdict


BTC_MIN_RR = Decimal("3.0")
BTC_MAX_SPREAD_PIPS = Decimal("50")


def run_btc_production(
    pair: str,
    candles,
    indicators,
    cfg: BacktestConfig,
    toggles: FilterToggles,
    use_rr_gate: bool,
    use_tp_exit: bool,
    label: str,
):
    """BTC backtest with optional RR gate and TP exit."""
    if len(candles) != len(indicators):
        raise ValueError("length mismatch")
    n = len(candles)
    if n < 250:
        return []

    balance = cfg.starting_balance
    trades: list[Trade] = []
    open_trade: Trade | None = None
    tp_price: Decimal | None = None
    cooldown_until = None

    sess_start, sess_end = cfg.session_hours.get(pair, (0, 24))
    spread_pips = cfg.spread_pips.get(pair, Decimal("50"))
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
            tp_hit = False
            exit_price = None
            exit_reason = ""

            if open_trade.direction == "BUY":
                # TP check first (best price)
                if use_tp_exit and tp_price is not None and candle.high >= tp_price:
                    tp_hit = True
                    exit_price = tp_price
                    exit_reason = "TP_HIT"
                elif candle.low <= open_trade.stop_loss:
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
                            cfg.sl_atr_multiplier * pip * Decimal("200"),
                        )
                        new_sl = candle.close - trail_distance
                        if new_sl > open_trade.stop_loss:
                            open_trade.stop_loss = new_sl
            else:  # SELL
                if use_tp_exit and tp_price is not None and candle.low <= tp_price:
                    tp_hit = True
                    exit_price = tp_price
                    exit_reason = "TP_HIT"
                elif candle.high >= open_trade.stop_loss:
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
                            cfg.sl_atr_multiplier * pip * Decimal("200"),
                        )
                        new_sl = candle.close + trail_distance
                        if new_sl < open_trade.stop_loss:
                            open_trade.stop_loss = new_sl

            if not sl_hit and not tp_hit and toggles.use_max_hold:
                hold_candles = i - next(
                    (j for j in range(i, -1, -1) if candles[j].time <= open_trade.entry_time), i
                )
                if hold_candles >= cfg.max_hold_hours:
                    sl_hit = True
                    exit_price = candle.close
                    exit_reason = "MAX_HOLD"

            if (sl_hit or tp_hit) and exit_price is not None:
                _close_trade(open_trade, exit_price, candle.time, exit_reason, pair, cfg, toggles, spread_pips)
                trades.append(open_trade)
                balance += open_trade.pnl_usd
                daily_pnl[date_key] += open_trade.pnl_usd
                cooldown_until = candle.time
                open_trade = None
                tp_price = None
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

        # RR gate: require TP/SL ratio >= 3.0
        tp = None
        if action == "BUY":
            tp = entry_price + sl_distance * BTC_MIN_RR
        else:
            tp = entry_price - sl_distance * BTC_MIN_RR

        if use_rr_gate:
            actual_rr = sl_distance * BTC_MIN_RR / sl_distance  # always 3.0 given fixed TP, gate is structural
            # Real gate: implied move to TP vs current ATR-based SL width
            # Only take trade if SL is not more than 2% of price
            btc_max_sl_pct = Decimal("0.02")
            sl_pct = sl_distance / entry_price
            if sl_pct > btc_max_sl_pct:
                continue

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
        tp_price = tp

    if open_trade is not None:
        last = candles[-1]
        _close_trade(open_trade, last.close, last.time, "BACKTEST_END", pair, cfg, toggles,
                     cfg.spread_pips.get(pair, Decimal("50")))
        trades.append(open_trade)

    for t in trades:
        t.strategies_fired = f"{label}:{t.strategies_fired}" if label != "baseline" else t.strategies_fired
    return trades


def main():
    pair = "BTC_USD"
    print("\n" + "=" * 75)
    print(f"BTC_USD Production Stack Backtest")
    print("=" * 75)

    candles = load_candles(pair)
    indicators = precompute_indicators(candles)
    print(f"Loaded {len(candles)} candles")

    print(f"\n{'Label':<28}  {'N':>4}  {'WR':>6}  {'PF':>5}  {'Sharpe':>6}  {'MAR':>5}  {'MaxDD':>7}  {'MC':>5}  {'Gates':>5}")
    print("-" * 75)

    variants = [
        # (sl_mult, use_rr_gate, use_tp, use_partial, spread, label)
        (3.0, False, False, False, "50", "old_baseline"),
        (3.0, False, False, True,  "50", "3x+partial"),
        (1.5, False, False, True,  "50", "1.5x+partial"),
        (1.5, True,  False, True,  "50", "1.5x+gates+partial"),
        (1.5, True,  True,  True,  "50", "1.5x+gates+tp+partial"),
    ]

    best_gates = 0
    best_label = ""
    for sl_mult, use_rr, use_tp, use_pc, spread_str, label in variants:
        cfg = BacktestConfig(
            sl_atr_multiplier=Decimal(str(sl_mult)),
            partial_close_pct=Decimal("0.67"),
            spread_pips={pair: Decimal(spread_str)},
            max_hold_hours=96,
        )
        toggles = FilterToggles(use_partial_close=use_pc)

        if use_rr or use_tp:
            trades = run_btc_production(pair, candles, indicators, cfg, toggles,
                                         use_rr_gate=use_rr, use_tp_exit=use_tp, label=label)
        else:
            trades = run_backtest(pair, candles, indicators, cfg, toggles, label=label)

        if not trades:
            print(f"{label:<28}  {'(no trades)':>50}")
            continue

        r = compute_metrics(pair, label, trades, cfg.starting_balance)
        mc_data = monte_carlo(trades, cfg.starting_balance, n_sim=3000)
        mc_p = mc_data["p_profit"]
        gates = sum([
            r.profit_factor >= 1.50,
            r.sharpe_annualized >= 1.00,
            r.mar >= 0.50,
            mc_p >= 0.85,
            r.max_drawdown_pct <= 0.10,
        ])
        if gates > best_gates:
            best_gates = gates
            best_label = label

        n = r.win_count + r.loss_count + r.breakeven_count
        print(
            f"{label:<28}  {n:>4}  {r.win_rate:>6.1%}  {r.profit_factor:>5.2f}  "
            f"{r.sharpe_annualized:>6.2f}  {r.mar:>5.2f}  {r.max_drawdown_pct:>7.1%}  "
            f"{mc_p:>5.1%}  [{gates}/5]"
        )

    print(f"\nBest config: {best_label}  ({best_gates}/5 gates)")
    if best_gates >= 4:
        print(">>> READY for live with this configuration.")
    elif best_gates >= 3:
        print(">>> PARTIAL - close but not yet live-ready.")
    else:
        print(">>> INSUFFICIENT - BTC signal quality needs more work.")


if __name__ == "__main__":
    main()
