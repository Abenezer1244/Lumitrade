"""
BTC_USD volatility regime + RSI divergence sweep.

Run:
    python -m scripts._btc_regime_sweep
"""
from __future__ import annotations

import random
import sys
from bisect import bisect_right
from datetime import timedelta
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_v2 import (  # noqa: E402
    BacktestConfig,
    Candle,
    FilterToggles,
    Indicators,
    PIP_SIZE,
    Trade,
    _FRACTIONAL_UNIT_PAIRS,
    _close_trade,
    _do_partial_close,
    compute_metrics,
    confidence_tier_risk_pct,
    load_candles,
    monte_carlo,
    pip_value_per_unit,
    precompute_indicators,
    quant_evaluate,
    round_price,
)


PAIR = "BTC_USD"
SIGNAL_SCORE = 0.80
WARMUP = 200
ATR_AVG_PERIOD = 50
DIVERGENCE_MIN_BARS = 5
DIVERGENCE_MAX_BARS = 20
MC_SIMS = 3000


@dataclass(frozen=True)
class Variant:
    key: str
    label: str
    use_quant: bool = False
    use_atr_gate: bool = False
    use_rsi_divergence: bool = False
    use_trend_filter: bool = False
    divergence_min_bars: int = DIVERGENCE_MIN_BARS
    divergence_max_bars: int = DIVERGENCE_MAX_BARS
    use_macd_confirm: bool = False
    use_ema200_filter: bool = False
    use_h4_filter: bool = False


@dataclass(frozen=True)
class H4State:
    time: object
    bull: bool
    bear: bool


def make_config() -> BacktestConfig:
    cfg = BacktestConfig(
        sl_atr_multiplier=Decimal("1.5"),
        partial_close_pct=Decimal("0.67"),
        max_hold_hours=96,
    )
    cfg.spread_pips[PAIR] = Decimal("50")
    return cfg


def make_toggles() -> FilterToggles:
    return FilterToggles(
        use_confidence_band=False,
        use_session_window=False,
        use_global_cutoff_17_utc=False,
        use_daily_loss_limit=False,
        use_min_sl_pips=False,
        use_cooldown=False,
        use_partial_close=True,
        use_breakeven=False,
        use_trailing_stop=False,
    )


def rolling_atr_average(indicators: list[Indicators]) -> list[Decimal]:
    avgs = [Decimal("0")] * len(indicators)
    window_sum = Decimal("0")
    atrs = [ind.atr_14 for ind in indicators]
    for i, atr in enumerate(atrs):
        window_sum += atr
        if i >= ATR_AVG_PERIOD:
            window_sum -= atrs[i - ATR_AVG_PERIOD]
        if i >= ATR_AVG_PERIOD - 1:
            avgs[i] = window_sum / Decimal(ATR_AVG_PERIOD)
    return avgs


def atr_gate_passes(i: int, indicators: list[Indicators], atr_avgs: list[Decimal]) -> bool:
    atr = indicators[i].atr_14
    avg = atr_avgs[i]
    if atr <= 0 or avg <= 0:
        return False
    return Decimal("0.5") * avg <= atr <= Decimal("2.0") * avg


def is_price_trough(candles: list[Candle], i: int) -> bool:
    return candles[i].low < candles[i - 1].low and candles[i].low <= candles[i + 1].low


def is_price_peak(candles: list[Candle], i: int) -> bool:
    return candles[i].high > candles[i - 1].high and candles[i].high >= candles[i + 1].high


def is_rsi_trough(indicators: list[Indicators], i: int) -> bool:
    return indicators[i].rsi_14 < indicators[i - 1].rsi_14 and indicators[i].rsi_14 <= indicators[i + 1].rsi_14


def is_rsi_peak(indicators: list[Indicators], i: int) -> bool:
    return indicators[i].rsi_14 > indicators[i - 1].rsi_14 and indicators[i].rsi_14 >= indicators[i + 1].rsi_14


def rsi_divergence_signal(
    i: int,
    candles: list[Candle],
    indicators: list[Indicators],
    min_bars: int = DIVERGENCE_MIN_BARS,
    max_bars: int = DIVERGENCE_MAX_BARS,
) -> str | None:
    """Return BUY/SELL when two confirmed local pivots diverge within a bar window."""
    if i < max_bars + 2:
        return None

    start = max(1, i - max_bars)
    end = i - min_bars
    if end < start:
        return None

    troughs = [
        j for j in range(start, end + 1)
        if is_price_trough(candles, j) and is_rsi_trough(indicators, j)
    ]
    if len(troughs) >= 2:
        recent = troughs[-1]
        for earlier in reversed(troughs[:-1]):
            span = recent - earlier
            if min_bars <= span <= max_bars:
                if (
                    candles[recent].low < candles[earlier].low
                    and indicators[recent].rsi_14 > indicators[earlier].rsi_14
                ):
                    return "BUY"

    peaks = [
        j for j in range(start, end + 1)
        if is_price_peak(candles, j) and is_rsi_peak(indicators, j)
    ]
    if len(peaks) >= 2:
        recent = peaks[-1]
        for earlier in reversed(peaks[:-1]):
            span = recent - earlier
            if min_bars <= span <= max_bars:
                if (
                    candles[recent].high > candles[earlier].high
                    and indicators[recent].rsi_14 < indicators[earlier].rsi_14
                ):
                    return "SELL"

    return None


def build_h4_states(h4_candles: list[Candle]) -> list[H4State]:
    indicators = precompute_indicators(h4_candles)
    return [
        H4State(
            time=candle.time,
            bull=ind.ema_20 > ind.ema_50 and candle.close > ind.ema_200,
            bear=ind.ema_20 < ind.ema_50 and candle.close < ind.ema_200,
        )
        for candle, ind in zip(h4_candles, indicators)
    ]


def h4_filter_passes(
    action: str,
    candle: Candle,
    h4_states: list[H4State],
    h4_times: list[object],
) -> bool:
    # H4 candles store open timestamps; close time = open + 4h.
    # Only consider a candle completed once close_time <= h1_time,
    # i.e. open_time <= h1_time - 4h. Using candle.time directly
    # would include the in-progress H4 bar (lookahead bias).
    completed_cutoff = candle.time - timedelta(hours=4)
    idx = bisect_right(h4_times, completed_cutoff) - 1
    if idx < 0:
        return False
    state = h4_states[idx]
    return state.bull if action == "BUY" else state.bear


def position_units(
    balance: Decimal,
    entry_price: Decimal,
    sl_pips: Decimal,
    cfg: BacktestConfig,
    toggles: FilterToggles,
    score: float,
) -> Decimal:
    if sl_pips <= 0:
        return Decimal("0")
    risk_usd = balance * confidence_tier_risk_pct(score, cfg, toggles)
    pv = pip_value_per_unit(PAIR, entry_price)
    if pv == 0:
        return Decimal("0")
    raw_units = risk_usd / (sl_pips * pv)
    if PAIR in _FRACTIONAL_UNIT_PAIRS:
        units = max(Decimal("0"), raw_units.quantize(Decimal("0.01")))
        min_units = Decimal("0.01")
    else:
        units = Decimal(max(0, int(raw_units)))
        min_units = Decimal("1000")
    units = min(units, Decimal(str(cfg.max_units)))
    return units if units >= min_units else Decimal("0")


def close_if_needed(
    open_trade: Trade,
    candle: Candle,
    cfg: BacktestConfig,
    toggles: FilterToggles,
    spread_pips: Decimal,
    pip: Decimal,
) -> bool:
    if open_trade.direction == "BUY":
        if candle.low <= open_trade.stop_loss:
            _close_trade(open_trade, open_trade.stop_loss, candle.time, "SL_HIT", PAIR, cfg, toggles, spread_pips)
            return True
        partial_trigger = open_trade.entry_price + open_trade.initial_sl_distance * cfg.partial_close_rr
        if not open_trade.partial_closed and candle.high >= partial_trigger:
            _do_partial_close(open_trade, partial_trigger, "BUY", PAIR, cfg, toggles, spread_pips, pip)
    else:
        if candle.high >= open_trade.stop_loss:
            _close_trade(open_trade, open_trade.stop_loss, candle.time, "SL_HIT", PAIR, cfg, toggles, spread_pips)
            return True
        partial_trigger = open_trade.entry_price - open_trade.initial_sl_distance * cfg.partial_close_rr
        if not open_trade.partial_closed and candle.low <= partial_trigger:
            _do_partial_close(open_trade, partial_trigger, "SELL", PAIR, cfg, toggles, spread_pips, pip)

    held_hours = (candle.time - open_trade.entry_time).total_seconds() / 3600
    if held_hours >= cfg.max_hold_hours:
        _close_trade(open_trade, candle.close, candle.time, "MAX_HOLD", PAIR, cfg, toggles, spread_pips)
        return True
    return False


def run_variant(
    variant: Variant,
    candles: list[Candle],
    indicators: list[Indicators],
    atr_avgs: list[Decimal],
    cfg: BacktestConfig,
    toggles: FilterToggles,
    h4_states: list[H4State] | None = None,
) -> list[Trade]:
    signal_fn: Callable[[int], tuple[str, float, str, str] | None]
    h4_times = [state.time for state in h4_states] if h4_states is not None else []

    def signal_at(i: int) -> tuple[str, float, str, str] | None:
        if variant.use_atr_gate and not atr_gate_passes(i, indicators, atr_avgs):
            return None

        if variant.use_quant:
            action, score, strategies, regime = quant_evaluate(indicators[i], candles[i].close, toggles)
            if action not in ("BUY", "SELL"):
                return None
            return action, score, "+".join(strategies), regime

        if variant.use_rsi_divergence:
            action = rsi_divergence_signal(
                i,
                candles,
                indicators,
                variant.divergence_min_bars,
                variant.divergence_max_bars,
            )
            if action not in ("BUY", "SELL"):
                return None
            if variant.use_trend_filter:
                if action == "BUY" and indicators[i].ema_20 <= indicators[i].ema_50:
                    return None
                if action == "SELL" and indicators[i].ema_20 >= indicators[i].ema_50:
                    return None
            if variant.use_macd_confirm:
                if action == "BUY" and indicators[i].macd_histogram <= 0:
                    return None
                if action == "SELL" and indicators[i].macd_histogram >= 0:
                    return None
            if variant.use_ema200_filter:
                if action == "BUY" and candles[i].close <= indicators[i].ema_200:
                    return None
                if action == "SELL" and candles[i].close >= indicators[i].ema_200:
                    return None
            if variant.use_h4_filter:
                if h4_states is None or not h4_filter_passes(action, candles[i], h4_states, h4_times):
                    return None
            strategies = ["RSI_DIVERGENCE"]
            if variant.use_macd_confirm:
                strategies.append("MACD_HIST")
            if variant.use_ema200_filter:
                strategies.append("EMA200")
            if variant.use_h4_filter:
                strategies.append("H4_ALIGN")
            return action, SIGNAL_SCORE, "+".join(strategies), "DIVERGENCE"

        return None

    signal_fn = signal_at
    trades: list[Trade] = []
    open_trade: Trade | None = None
    balance = cfg.starting_balance
    spread_pips = cfg.spread_pips[PAIR]
    pip = PIP_SIZE[PAIR]

    for i in range(WARMUP, len(candles) - 1):
        candle = candles[i]
        if open_trade is not None:
            if close_if_needed(open_trade, candle, cfg, toggles, spread_pips, pip):
                trades.append(open_trade)
                balance += open_trade.pnl_usd
                open_trade = None
            continue

        signal = signal_fn(i)
        if signal is None:
            continue
        action, score, strategies, regime = signal

        atr = indicators[i].atr_14
        if atr <= 0:
            continue

        next_candle = candles[i + 1]
        entry_price = next_candle.open
        if toggles.use_friction:
            slip = cfg.slippage_pips * pip
            entry_price = entry_price + slip if action == "BUY" else entry_price - slip

        sl_distance = atr * cfg.sl_atr_multiplier
        sl_pips = sl_distance / pip
        units = position_units(balance, entry_price, sl_pips, cfg, toggles, score)
        if units <= 0:
            continue

        stop_loss = round_price(
            entry_price - sl_distance if action == "BUY" else entry_price + sl_distance,
            PAIR,
        )
        open_trade = Trade(
            pair=PAIR,
            direction=action,
            entry_price=entry_price,
            stop_loss=stop_loss,
            entry_time=next_candle.time,
            units=units,
            confidence_score=score,
            strategies_fired=f"{variant.key}:{strategies}",
            regime=regime,
            initial_sl_distance=sl_distance,
        )

    if open_trade is not None:
        last = candles[-1]
        _close_trade(open_trade, last.close, last.time, "BACKTEST_END", PAIR, cfg, toggles, spread_pips)
        trades.append(open_trade)
    return trades


def gate_count(result, mc: dict) -> int:
    return sum([
        result.profit_factor >= 1.50,
        result.sharpe_annualized >= 1.00,
        result.mar >= 0.50,
        mc["p_profit"] >= 0.85,
        result.max_drawdown_pct <= 10.0,
    ])


def main() -> None:
    random.seed(42)
    candles = load_candles(PAIR, "H1")
    indicators = precompute_indicators(candles)
    atr_avgs = rolling_atr_average(indicators)
    cfg = make_config()
    toggles = make_toggles()
    h4_states: list[H4State] | None = None
    h4_error: str | None = None
    try:
        h4_candles = load_candles(PAIR, "H4")
        h4_states = build_h4_states(h4_candles)
    except Exception as exc:
        h4_error = f"{type(exc).__name__}: {exc}"

    variants = [
        Variant("a", "ATR gate only", use_quant=True, use_atr_gate=True),
        Variant("b", "RSI divergence only", use_rsi_divergence=True),
        Variant("c", "ATR + RSI div", use_atr_gate=True, use_rsi_divergence=True),
        Variant("d", "ATR + RSI div + EMA", use_atr_gate=True, use_rsi_divergence=True, use_trend_filter=True),
        Variant(
            "e",
            "ATR + RSI 3-25 + MACD",
            use_atr_gate=True,
            use_rsi_divergence=True,
            divergence_min_bars=3,
            divergence_max_bars=25,
            use_macd_confirm=True,
        ),
        Variant(
            "f",
            "ATR + RSI 3-30 + EMA200",
            use_atr_gate=True,
            use_rsi_divergence=True,
            divergence_min_bars=3,
            divergence_max_bars=30,
            use_ema200_filter=True,
        ),
    ]
    if h4_states is not None:
        variants.append(
            Variant(
                "g",
                "ATR + RSI div + H4",
                use_atr_gate=True,
                use_rsi_divergence=True,
                use_h4_filter=True,
            )
        )
    else:
        print(f"Skipping variant g: unable to load H4 data ({h4_error})")

    print(f"BTC_USD Regime Sweep ({len(candles)} H1 candles)")
    print(
        f"{'Var':<3} {'Variant':<24} {'N':>5} {'WR':>7} {'PF':>7} "
        f"{'Sharpe':>8} {'MAR':>7} {'MaxDD':>8} {'MC P(profit)':>13} {'Gates':>7}"
    )
    print("-" * 98)

    for variant in variants:
        trades = run_variant(variant, candles, indicators, atr_avgs, cfg, toggles, h4_states)
        result = compute_metrics(PAIR, variant.label, trades, cfg.starting_balance)
        mc = monte_carlo(trades, cfg.starting_balance, n_sim=MC_SIMS)
        gates = gate_count(result, mc)
        print(
            f"{variant.key:<3} {variant.label:<24} {len(trades):>5} "
            f"{result.win_rate * 100:>6.1f}% {result.profit_factor:>7.2f} "
            f"{result.sharpe_annualized:>8.2f} {result.mar:>7.2f} "
            f"{result.max_drawdown_pct:>7.1f}% {mc['p_profit'] * 100:>12.1f}% "
            f"{gates}/5"
        )


if __name__ == "__main__":
    main()
