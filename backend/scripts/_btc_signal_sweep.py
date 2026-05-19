from __future__ import annotations
import sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.backtest_v2 import (load_candles, precompute_indicators, BacktestConfig, FilterToggles,
    compute_metrics, monte_carlo, Trade, _close_trade, _do_partial_close, PIP_SIZE,
    _FRACTIONAL_UNIT_PAIRS, BREAKEVEN_PIPS, TRAIL_ACTIVATION_PIPS, pip_value_per_unit, round_price,
    confidence_tier_risk_pct)
from collections import defaultdict


PAIR = "BTC_USD"
SIGNAL_SCORE = 0.80
TP_RR = Decimal("3.0")
SL_CAP_PCT = Decimal("0.02")


def btc_trend_rsi(i, arrays):
    candles, indicators = arrays
    if i <= 0:
        return None
    ind = indicators[i]
    prev = indicators[i - 1]
    if ind.ema_20 > ind.ema_50 > ind.ema_200 and prev.rsi_14 < 50 and ind.rsi_14 >= 50:
        return "BUY"
    if ind.ema_20 < ind.ema_50 < ind.ema_200 and prev.rsi_14 > 50 and ind.rsi_14 <= 50:
        return "SELL"
    return None


def btc_breakout(i, arrays):
    candles, indicators = arrays
    if i < 20:
        return None
    close = candles[i].close
    lookback = candles[i - 20:i]
    high_20 = max(c.high for c in lookback)
    low_20 = min(c.low for c in lookback)
    rsi = indicators[i].rsi_14
    if close > high_20 and rsi > 55:
        return "BUY"
    if close < low_20 and rsi < 45:
        return "SELL"
    return None


def btc_combined(i, arrays):
    trend = btc_trend_rsi(i, arrays)
    breakout = btc_breakout(i, arrays)
    if trend is not None and trend == breakout:
        return trend
    return None


def make_btc_union(toggles):
    try:
        from scripts.backtest_v2 import quant_evaluate
    except ImportError:
        return None

    def btc_union(i, arrays):
        candles, indicators = arrays
        combined = btc_combined(i, arrays)
        if combined is not None:
            return combined
        action, _score, _strategies, _regime = quant_evaluate(indicators[i], candles[i].close, toggles)
        return action if action in ("BUY", "SELL") else None

    return btc_union


def make_config():
    cfg = BacktestConfig(
        sl_atr_multiplier=Decimal("1.5"),
        partial_close_pct=Decimal("0.67"),
        max_hold_hours=96,
    )
    cfg.spread_pips[PAIR] = Decimal("50")
    return cfg


# Gates disabled here vs. the live engine. LIVE-READY verdict is suppressed
# when any of these are off — this sweep is ablation, not a deployment signal.
_ABLATION_DISABLED = [
    "use_min_sl_pips", "use_session_window", "use_global_cutoff_17_utc",
    "use_daily_loss_limit", "use_cooldown", "use_confidence_band",
    "use_trailing_stop", "use_breakeven",
]


def make_toggles():
    toggles = FilterToggles()
    toggles.use_partial_close = True
    toggles.use_min_sl_pips = False
    toggles.use_session_window = False
    toggles.use_global_cutoff_17_utc = False
    toggles.use_daily_loss_limit = False
    toggles.use_cooldown = False
    toggles.use_confidence_band = False
    toggles.use_trailing_stop = False
    toggles.use_breakeven = False
    return toggles


def _is_production_equivalent(toggles) -> bool:
    """True only if every live-engine risk gate is enabled."""
    return all(getattr(toggles, gate, False) for gate in _ABLATION_DISABLED)


def position_units(balance, entry_price, sl_pips, cfg, toggles):
    risk_pct = confidence_tier_risk_pct(SIGNAL_SCORE, cfg, toggles)
    risk_usd = balance * risk_pct
    pv = pip_value_per_unit(PAIR, entry_price)
    if pv == 0 or sl_pips <= 0:
        return Decimal("0")
    raw_units = risk_usd / (sl_pips * pv)
    if PAIR in _FRACTIONAL_UNIT_PAIRS:
        units = raw_units.quantize(Decimal("0.01"))
        min_units = Decimal("0.01")
    else:
        units = Decimal(max(0, int(raw_units)))
        min_units = Decimal("1000")
    units = min(units, Decimal(str(cfg.max_units)))
    return units if units >= min_units else Decimal("0")


def run_btc_backtest(signal_fn, candles, indicators, config):
    if len(candles) != len(indicators):
        raise ValueError("candles and indicators length mismatch")

    toggles = make_toggles()
    data = (candles, indicators)
    pip = PIP_SIZE[PAIR]
    spread_pips = Decimal("50")
    trades = []
    open_trade = None
    take_profit = None
    balance = config.starting_balance
    exit_counts = defaultdict(int)

    for i in range(210, len(candles) - 1):
        candle = candles[i]

        if open_trade is not None:
            exit_price = None
            exit_reason = None

            if open_trade.direction == "BUY":
                partial_trigger = open_trade.entry_price + (open_trade.initial_sl_distance * config.partial_close_rr)
                if candle.low <= open_trade.stop_loss:
                    exit_price = open_trade.stop_loss
                    exit_reason = "SL_HIT"
                elif take_profit is not None and candle.high >= take_profit:
                    exit_price = take_profit
                    exit_reason = "TP_HIT"
                elif not open_trade.partial_closed and candle.high >= partial_trigger:
                    _do_partial_close(open_trade, partial_trigger, open_trade.direction, PAIR, config, toggles, spread_pips, pip)
            else:
                partial_trigger = open_trade.entry_price - (open_trade.initial_sl_distance * config.partial_close_rr)
                if candle.high >= open_trade.stop_loss:
                    exit_price = open_trade.stop_loss
                    exit_reason = "SL_HIT"
                elif take_profit is not None and candle.low <= take_profit:
                    exit_price = take_profit
                    exit_reason = "TP_HIT"
                elif not open_trade.partial_closed and candle.low <= partial_trigger:
                    _do_partial_close(open_trade, partial_trigger, open_trade.direction, PAIR, config, toggles, spread_pips, pip)

            if exit_price is None:
                held_hours = Decimal(str((candle.time - open_trade.entry_time).total_seconds())) / Decimal("3600")
                if held_hours >= config.max_hold_hours:
                    exit_price = candle.close
                    exit_reason = "MAX_HOLD"

            if exit_price is not None:
                _close_trade(open_trade, exit_price, candle.time, exit_reason, PAIR, config, toggles, spread_pips)
                trades.append(open_trade)
                balance += open_trade.pnl_usd
                exit_counts[exit_reason] += 1
                open_trade = None
                take_profit = None
            continue

        direction = signal_fn(i, data)
        if direction not in ("BUY", "SELL"):
            continue

        ind = indicators[i]
        if ind.atr_14 <= 0:
            continue

        next_candle = candles[i + 1]
        entry_price = next_candle.open
        if toggles.use_friction:
            slip = config.slippage_pips * pip
            entry_price = entry_price + slip if direction == "BUY" else entry_price - slip

        sl_distance = ind.atr_14 * config.sl_atr_multiplier
        if sl_distance > SL_CAP_PCT * entry_price:
            continue

        sl_pips = sl_distance / pip
        units = position_units(balance, entry_price, sl_pips, config, toggles)
        if units <= 0:
            continue

        stop_loss = round_price(entry_price - sl_distance if direction == "BUY" else entry_price + sl_distance, PAIR)
        take_profit = round_price(entry_price + (sl_distance * TP_RR) if direction == "BUY" else entry_price - (sl_distance * TP_RR), PAIR)

        open_trade = Trade(
            pair=PAIR,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            entry_time=next_candle.time,
            units=units,
            confidence_score=SIGNAL_SCORE,
            strategies_fired=signal_fn.__name__,
            regime="BTC_CUSTOM",
            initial_sl_distance=sl_distance,
        )

    if open_trade is not None:
        last = candles[-1]
        _close_trade(open_trade, last.close, last.time, "BACKTEST_END", PAIR, config, toggles, spread_pips)
        trades.append(open_trade)

    return trades


def gate_status(result, mc):
    gates = [
        ("PF>=1.50", result.profit_factor >= 1.50),
        ("Sharpe>=1.00", result.sharpe_annualized >= 1.00),
        ("MAR>=0.50", result.mar >= 0.50),
        ("MC>=85%", mc["p_profit"] >= 0.85),
        ("MaxDD<=10.0%", result.max_drawdown_pct <= 10.0),
    ]
    return gates


def evaluate_variant(name, signal_fn, candles, indicators):
    cfg = make_config()
    trades = run_btc_backtest(signal_fn, candles, indicators, cfg)
    result = compute_metrics(PAIR, name, trades, cfg.starting_balance)
    mc = monte_carlo(trades, cfg.starting_balance)
    gates = gate_status(result, mc)
    return {
        "name": name,
        "trades": trades,
        "result": result,
        "mc": mc,
        "gates": gates,
        "gate_count": sum(1 for _name, passed in gates if passed),
    }


def print_row(item):
    r = item["result"]
    mc = item["mc"]
    print(
        f"{item['name']:<15} | {len(item['trades']):>8} | {r.win_rate * 100:>5.1f} | "
        f"{r.profit_factor:>5.2f} | {r.sharpe_annualized:>6.2f} | {r.mar:>5.2f} | "
        f"{r.max_drawdown_pct:>6.2f} | {mc['p_profit'] * 100:>5.1f} | {item['gate_count']}/5"
    )


def main():
    candles = load_candles(PAIR, "H1")
    indicators = precompute_indicators(candles)

    variants = [
        ("btc_trend_rsi", btc_trend_rsi),
        ("btc_breakout", btc_breakout),
        ("btc_combined", btc_combined),
    ]
    results = [evaluate_variant(name, fn, candles, indicators) for name, fn in variants]
    best = max(results, key=lambda x: (x["gate_count"], x["result"].profit_factor, x["result"].sharpe_annualized))

    if best["gate_count"] >= 3:
        toggles = make_toggles()
        union_fn = make_btc_union(toggles)
        if union_fn is not None:
            results.append(evaluate_variant("btc_union", union_fn, candles, indicators))
            best = max(results, key=lambda x: (x["gate_count"], x["result"].profit_factor, x["result"].sharpe_annualized))

    print("BTC_USD Signal Sweep Results")
    print("Variant         | N_Trades |   WR% |    PF | Sharpe |   MAR | MaxDD% | MC_P% | Gates/5")
    print("-" * 86)
    for item in results:
        print_row(item)

    r = best["result"]
    mc = best["mc"]
    print()
    print(f"Best variant: {best['name']}")
    print(f"Trades: {len(best['trades'])}")
    print(f"Ending balance: {r.ending_balance:.2f}")
    print(f"Total PnL: {r.total_pnl:.2f}")
    print(f"Win rate: {r.win_rate * 100:.2f}%")
    print(f"Profit factor: {r.profit_factor:.2f}")
    print(f"Sharpe: {r.sharpe_annualized:.2f}")
    print(f"MAR: {r.mar:.2f}")
    print(f"MaxDD: {r.max_drawdown_pct:.2f}%")
    print(f"MC probability of profit: {mc['p_profit'] * 100:.2f}%")

    print()
    print("Gate status:")
    for name, passed in best["gates"]:
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    missing = 5 - best["gate_count"]
    toggles_used = make_toggles()
    if missing == 0 and _is_production_equivalent(toggles_used):
        print("LIVE-READY: YES")
    elif missing == 0:
        print(
            "LIVE-READY: NO (ablation mode — production risk gates disabled: "
            + ", ".join(_ABLATION_DISABLED)
            + "). Re-run with all gates enabled before using as a deployment signal."
        )
    else:
        print(f"LIVE-READY: NO (needs {missing} more gates)")


if __name__ == "__main__":
    main()
