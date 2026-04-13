"""
Lumitrade Backtester
=====================
Runs the QuantEngine strategies against 2 years of historical OANDA data.
Simulates entries, stop losses, trailing stops, and position sizing.

Usage:
    cd backend
    python -m scripts.backtest

Reads CSV files from backend/data/historical/
"""

import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"

PAIRS = ["USD_JPY", "USD_CAD", "AUD_USD", "NZD_USD"]

# Position sizing
STARTING_BALANCE = Decimal("100000")
RISK_PCT = Decimal("0.015")  # 1.5% risk per trade
MAX_UNITS = 500000

# Trailing stop config (matches production)
BREAKEVEN_PIPS = {"USD_JPY": 15, "USD_CAD": 15, "AUD_USD": 15, "NZD_USD": 15}
TRAIL_ACTIVATION_PIPS = {"USD_JPY": 20, "USD_CAD": 18, "AUD_USD": 15, "NZD_USD": 15}
MAX_HOLD_CANDLES_H1 = 6  # 6 hours max hold

# Pip sizes
PIP_SIZE = {
    "USD_JPY": Decimal("0.01"),
    "USD_CAD": Decimal("0.0001"),
    "AUD_USD": Decimal("0.0001"),
    "NZD_USD": Decimal("0.0001"),
}

# Session hours (UTC) -- only trade during these hours
SESSION_HOURS = {
    "USD_JPY": (0, 8),
    "USD_CAD": (8, 17),
    "AUD_USD": (0, 8),
    "NZD_USD": (0, 8),
}


@dataclass
class Candle:
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass
class Indicators:
    ema_20: Decimal = Decimal("0")
    ema_50: Decimal = Decimal("0")
    ema_200: Decimal = Decimal("0")
    rsi_14: Decimal = Decimal("0")
    bb_upper: Decimal = Decimal("0")
    bb_mid: Decimal = Decimal("0")
    bb_lower: Decimal = Decimal("0")
    macd_line: Decimal = Decimal("0")
    macd_signal: Decimal = Decimal("0")
    macd_histogram: Decimal = Decimal("0")
    atr_14: Decimal = Decimal("0")


@dataclass
class Trade:
    pair: str
    direction: str  # BUY or SELL
    entry_price: Decimal
    stop_loss: Decimal
    entry_time: datetime
    units: int
    strategy: str
    # Filled on close
    exit_price: Decimal = Decimal("0")
    exit_time: datetime | None = None
    pnl_pips: Decimal = Decimal("0")
    pnl_usd: Decimal = Decimal("0")
    outcome: str = ""
    exit_reason: str = ""
    breakeven_set: bool = False
    trailing_active: bool = False


def load_candles(pair: str, timeframe: str) -> list[Candle]:
    """Load candles from CSV."""
    filepath = DATA_DIR / f"{pair}_{timeframe}.csv"
    if not filepath.exists():
        print(f"  WARNING: {filepath} not found")
        return []

    candles = []
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append(Candle(
                time=datetime.fromisoformat(row["time"]),
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
                volume=int(row["volume"]),
            ))
    return candles


def compute_ema(closes: list[Decimal], period: int) -> list[Decimal]:
    """Compute EMA for a list of close prices."""
    if not closes:
        return []
    emas = [closes[0]]
    mult = Decimal(str(2 / (period + 1)))
    for i in range(1, len(closes)):
        emas.append(closes[i] * mult + emas[-1] * (1 - mult))
    return emas


def compute_rsi(closes: list[Decimal], period: int = 14) -> list[Decimal]:
    """Compute RSI."""
    rsis = [Decimal("50")] * min(period, len(closes))
    if len(closes) <= period:
        return rsis

    gains = []
    losses = []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, Decimal("0")))
        losses.append(abs(min(change, Decimal("0"))))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, Decimal("0"))
        loss = abs(min(change, Decimal("0")))

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsis.append(Decimal("100"))
        else:
            rs = avg_gain / avg_loss
            rsis.append(Decimal("100") - Decimal("100") / (1 + rs))

    return rsis


def compute_atr(candles: list[Candle], period: int = 14) -> list[Decimal]:
    """Compute ATR."""
    if len(candles) < 2:
        return [Decimal("0")] * len(candles)

    trs = [candles[0].high - candles[0].low]
    for i in range(1, len(candles)):
        tr = max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - candles[i - 1].close),
            abs(candles[i].low - candles[i - 1].close),
        )
        trs.append(tr)

    atrs = [Decimal("0")] * min(period, len(trs))
    if len(trs) >= period:
        atrs.append(sum(trs[:period]) / period)
        for i in range(period + 1, len(trs)):
            atrs.append((atrs[-1] * (period - 1) + trs[i]) / period)

    # Pad to match length
    while len(atrs) < len(candles):
        atrs.append(atrs[-1] if atrs else Decimal("0"))

    return atrs


def compute_macd(closes: list[Decimal]) -> tuple[list[Decimal], list[Decimal], list[Decimal]]:
    """Compute MACD line, signal, histogram."""
    ema12 = compute_ema(closes, 12)
    ema26 = compute_ema(closes, 26)

    macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    macd_signal = compute_ema(macd_line, 9)
    macd_hist = [ml - ms for ml, ms in zip(macd_line, macd_signal)]

    return macd_line, macd_signal, macd_hist


def compute_bollinger(closes: list[Decimal], period: int = 20) -> tuple[list[Decimal], list[Decimal], list[Decimal]]:
    """Compute Bollinger Bands (mid, upper, lower). Uses float for sqrt speed."""
    import math
    mids = []
    uppers = []
    lowers = []

    for i in range(len(closes)):
        if i < period - 1:
            mids.append(closes[i])
            uppers.append(closes[i])
            lowers.append(closes[i])
        else:
            window = closes[i - period + 1:i + 1]
            mid = sum(window) / period
            variance = float(sum((x - mid) ** 2 for x in window) / period)
            std = Decimal(str(math.sqrt(variance)))
            mids.append(mid)
            uppers.append(mid + 2 * std)
            lowers.append(mid - 2 * std)

    return mids, uppers, lowers


def compute_indicators(candles: list[Candle], idx: int) -> Indicators:
    """Compute all indicators up to index idx."""
    closes = [c.close for c in candles[:idx + 1]]

    ema20 = compute_ema(closes, 20)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    rsi = compute_rsi(closes, 14)
    atr = compute_atr(candles[:idx + 1], 14)
    macd_line, macd_signal, macd_hist = compute_macd(closes)
    bb_mid, bb_upper, bb_lower = compute_bollinger(closes, 20)

    return Indicators(
        ema_20=ema20[-1] if ema20 else Decimal("0"),
        ema_50=ema50[-1] if ema50 else Decimal("0"),
        ema_200=ema200[-1] if ema200 else Decimal("0"),
        rsi_14=rsi[-1] if rsi else Decimal("50"),
        bb_upper=bb_upper[-1] if bb_upper else Decimal("0"),
        bb_mid=bb_mid[-1] if bb_mid else Decimal("0"),
        bb_lower=bb_lower[-1] if bb_lower else Decimal("0"),
        macd_line=macd_line[-1] if macd_line else Decimal("0"),
        macd_signal=macd_signal[-1] if macd_signal else Decimal("0"),
        macd_histogram=macd_hist[-1] if macd_hist else Decimal("0"),
        atr_14=atr[-1] if atr else Decimal("0"),
    )


# -- Quant Strategies (mirrors production quant_engine.py) ------

def ema_trend_signal(ind: Indicators, price: Decimal) -> dict:
    ema20 = float(ind.ema_20)
    ema50 = float(ind.ema_50)
    ema200 = float(ind.ema_200)
    px = float(price)
    if ema20 == 0 or ema50 == 0 or ema200 == 0:
        return {"action": "HOLD", "score": 0.0, "name": "EMA_TREND"}

    full_bull = ema20 > ema50 > ema200
    full_bear = ema20 < ema50 < ema200

    if full_bull and px > ema200:
        score = 0.85 if px > ema20 else 0.65
        return {"action": "BUY", "score": score, "name": "EMA_TREND"}
    elif full_bear and px < ema200:
        score = 0.85 if px < ema20 else 0.65
        return {"action": "SELL", "score": score, "name": "EMA_TREND"}
    elif ema20 > ema50 and px > ema50:
        return {"action": "BUY", "score": 0.45, "name": "EMA_TREND"}
    elif ema20 < ema50 and px < ema50:
        return {"action": "SELL", "score": 0.45, "name": "EMA_TREND"}
    return {"action": "HOLD", "score": 0.0, "name": "EMA_TREND"}


def bollinger_signal(ind: Indicators, price: Decimal) -> dict:
    px = float(price)
    bb_upper = float(ind.bb_upper)
    bb_lower = float(ind.bb_lower)
    bb_mid = float(ind.bb_mid)
    rsi = float(ind.rsi_14)
    if bb_upper == 0 or bb_lower == 0 or bb_mid == 0:
        return {"action": "HOLD", "score": 0.0, "name": "BB_REVERT"}

    bb_width = bb_upper - bb_lower
    if bb_width == 0:
        return {"action": "HOLD", "score": 0.0, "name": "BB_REVERT"}

    dist_from_mid = (px - bb_mid) / (bb_width / 2)

    if dist_from_mid <= -0.85 and rsi < 35:
        score = 0.75 if rsi < 25 else 0.55
        return {"action": "BUY", "score": score, "name": "BB_REVERT"}
    if dist_from_mid >= 0.85 and rsi > 65:
        score = 0.75 if rsi > 75 else 0.55
        return {"action": "SELL", "score": score, "name": "BB_REVERT"}
    return {"action": "HOLD", "score": 0.0, "name": "BB_REVERT"}


def momentum_signal(ind: Indicators) -> dict:
    macd_hist = float(ind.macd_histogram)
    macd_line = float(ind.macd_line)
    macd_signal = float(ind.macd_signal)
    rsi = float(ind.rsi_14)

    macd_bull = macd_hist > 0 and macd_line > macd_signal
    macd_bear = macd_hist < 0 and macd_line < macd_signal

    if macd_bull and 45 < rsi < 72:
        score = 0.70 if abs(macd_hist) > abs(macd_signal) * 0.3 else 0.45
        return {"action": "BUY", "score": score, "name": "MOMENTUM"}
    if macd_bear and 28 < rsi < 55:
        score = 0.70 if abs(macd_hist) > abs(macd_signal) * 0.3 else 0.45
        return {"action": "SELL", "score": score, "name": "MOMENTUM"}
    return {"action": "HOLD", "score": 0.0, "name": "MOMENTUM"}


def quant_evaluate(ind: Indicators, price: Decimal) -> tuple[str, float, list[str]]:
    """Run quant engine. Returns (action, score, strategies)."""
    ema = ema_trend_signal(ind, price)
    bb = bollinger_signal(ind, price)
    mom = momentum_signal(ind)

    signals = [ema, bb, mom]
    buy_votes = [s for s in signals if s["action"] == "BUY"]
    sell_votes = [s for s in signals if s["action"] == "SELL"]

    # Tier 1: Multi-strategy agreement
    if len(buy_votes) >= 2:
        score = min(0.70 + sum(s["score"] for s in buy_votes) / 3 * 0.30, 1.0)
        return "BUY", score, [s["name"] for s in buy_votes]
    if len(sell_votes) >= 2:
        score = min(0.70 + sum(s["score"] for s in sell_votes) / 3 * 0.30, 1.0)
        return "SELL", score, [s["name"] for s in sell_votes]

    # Tier 2: Solo strong strategy, no opposition
    if buy_votes and not sell_votes:
        best = max(buy_votes, key=lambda s: s["score"])
        if best["score"] >= 0.65:
            return "BUY", 0.55 + (best["score"] - 0.65) * 0.5, [best["name"]]
    if sell_votes and not buy_votes:
        best = max(sell_votes, key=lambda s: s["score"])
        if best["score"] >= 0.65:
            return "SELL", 0.55 + (best["score"] - 0.65) * 0.5, [best["name"]]

    return "HOLD", 0.0, []


def pips_between(p1: Decimal, p2: Decimal, pair: str) -> Decimal:
    return abs(p1 - p2) / PIP_SIZE[pair]


def pip_value(pair: str, price: Decimal) -> Decimal:
    """Approximate pip value in USD per unit."""
    ps = PIP_SIZE[pair]
    if pair.startswith("USD"):
        return ps / price
    return ps


# -- Backtest Engine --------------------------------------------

def backtest_pair(pair: str) -> list[Trade]:
    """Run backtest for one pair using H1 candles for signals, M15 for entries."""
    print(f"\n{'='*60}")
    print(f"BACKTESTING {pair}")
    print(f"{'='*60}")

    h1_candles = load_candles(pair, "H1")
    if len(h1_candles) < 250:
        print(f"  Not enough H1 data ({len(h1_candles)} candles)")
        return []

    print(f"  H1 candles: {len(h1_candles)} ({h1_candles[0].time.date()} to {h1_candles[-1].time.date()})")

    trades: list[Trade] = []
    balance = STARTING_BALANCE
    open_trade: Trade | None = None
    session_start, session_end = SESSION_HOURS[pair]
    cooldown_until: datetime | None = None

    # Start after 200 candles (need EMA200 warmup)
    for i in range(200, len(h1_candles)):
        candle = h1_candles[i]
        hour = candle.time.hour

        # -- Check open trade --
        if open_trade:
            # Check SL hit
            if open_trade.direction == "BUY":
                if candle.low <= open_trade.stop_loss:
                    open_trade.exit_price = open_trade.stop_loss
                    open_trade.exit_time = candle.time
                    open_trade.exit_reason = "SL_HIT"
                    pips = (open_trade.exit_price - open_trade.entry_price) / PIP_SIZE[pair]
                    open_trade.pnl_pips = pips
                    open_trade.pnl_usd = pips * open_trade.units * pip_value(pair, open_trade.exit_price)
                    open_trade.outcome = "WIN" if open_trade.pnl_usd > 0 else "LOSS"
                    balance += open_trade.pnl_usd
                    trades.append(open_trade)
                    cooldown_until = candle.time
                    open_trade = None
                    continue
                # Breakeven check
                profit_pips = (candle.close - open_trade.entry_price) / PIP_SIZE[pair]
                if not open_trade.breakeven_set and profit_pips >= BREAKEVEN_PIPS[pair]:
                    open_trade.stop_loss = open_trade.entry_price
                    open_trade.breakeven_set = True
                # Trailing stop check
                if profit_pips >= TRAIL_ACTIVATION_PIPS[pair]:
                    sl_distance = abs(open_trade.entry_price - open_trade.stop_loss) if not open_trade.trailing_active else PIP_SIZE[pair] * TRAIL_ACTIVATION_PIPS[pair]
                    new_sl = candle.close - sl_distance
                    if new_sl > open_trade.stop_loss:
                        open_trade.stop_loss = new_sl
                        open_trade.trailing_active = True

            else:  # SELL
                if candle.high >= open_trade.stop_loss:
                    open_trade.exit_price = open_trade.stop_loss
                    open_trade.exit_time = candle.time
                    open_trade.exit_reason = "SL_HIT"
                    pips = (open_trade.entry_price - open_trade.exit_price) / PIP_SIZE[pair]
                    open_trade.pnl_pips = pips
                    open_trade.pnl_usd = pips * open_trade.units * pip_value(pair, open_trade.exit_price)
                    open_trade.outcome = "WIN" if open_trade.pnl_usd > 0 else "LOSS"
                    balance += open_trade.pnl_usd
                    trades.append(open_trade)
                    cooldown_until = candle.time
                    open_trade = None
                    continue
                profit_pips = (open_trade.entry_price - candle.close) / PIP_SIZE[pair]
                if not open_trade.breakeven_set and profit_pips >= BREAKEVEN_PIPS[pair]:
                    open_trade.stop_loss = open_trade.entry_price
                    open_trade.breakeven_set = True
                if profit_pips >= TRAIL_ACTIVATION_PIPS[pair]:
                    sl_distance = abs(open_trade.stop_loss - open_trade.entry_price) if not open_trade.trailing_active else PIP_SIZE[pair] * TRAIL_ACTIVATION_PIPS[pair]
                    new_sl = candle.close + sl_distance
                    if new_sl < open_trade.stop_loss:
                        open_trade.stop_loss = new_sl
                        open_trade.trailing_active = True

            # Max hold: close after 6 candles (6 hours)
            candle_idx_entry = next((j for j in range(len(h1_candles)) if h1_candles[j].time >= open_trade.entry_time), i)
            if i - candle_idx_entry >= MAX_HOLD_CANDLES_H1:
                open_trade.exit_price = candle.close
                open_trade.exit_time = candle.time
                open_trade.exit_reason = "MAX_HOLD"
                if open_trade.direction == "BUY":
                    pips = (candle.close - open_trade.entry_price) / PIP_SIZE[pair]
                else:
                    pips = (open_trade.entry_price - candle.close) / PIP_SIZE[pair]
                open_trade.pnl_pips = pips
                open_trade.pnl_usd = pips * open_trade.units * pip_value(pair, candle.close)
                open_trade.outcome = "WIN" if open_trade.pnl_usd > 0 else "LOSS"
                balance += open_trade.pnl_usd
                trades.append(open_trade)
                cooldown_until = candle.time
                open_trade = None
                continue

            continue  # Already in a trade, skip signal generation

        # -- Session filter --
        if not (session_start <= hour < session_end):
            continue

        # -- Cooldown --
        if cooldown_until and (candle.time - cooldown_until).total_seconds() < 300:
            continue

        # -- Compute indicators --
        ind = compute_indicators(h1_candles, i)

        # -- Run quant engine --
        action, score, strategies = quant_evaluate(ind, candle.close)

        if action == "HOLD":
            continue

        # -- Position sizing --
        atr = ind.atr_14
        if atr == 0:
            continue

        sl_distance = atr * Decimal("1.5")
        sl_pips = sl_distance / PIP_SIZE[pair]
        if sl_pips < 10:
            continue

        risk_usd = balance * RISK_PCT
        pv = pip_value(pair, candle.close)
        if pv == 0:
            continue
        units = int(risk_usd / (sl_pips * pv))
        units = min(units, MAX_UNITS)
        if units < 1000:
            continue

        # -- Set SL --
        if action == "BUY":
            sl = candle.close - sl_distance
        else:
            sl = candle.close + sl_distance

        # -- Open trade --
        open_trade = Trade(
            pair=pair,
            direction=action,
            entry_price=candle.close,
            stop_loss=sl,
            entry_time=candle.time,
            units=units,
            strategy="+".join(strategies),
        )

    # Close any remaining open trade at last price
    if open_trade:
        last = h1_candles[-1]
        open_trade.exit_price = last.close
        open_trade.exit_time = last.time
        open_trade.exit_reason = "BACKTEST_END"
        if open_trade.direction == "BUY":
            pips = (last.close - open_trade.entry_price) / PIP_SIZE[pair]
        else:
            pips = (open_trade.entry_price - last.close) / PIP_SIZE[pair]
        open_trade.pnl_pips = pips
        open_trade.pnl_usd = pips * open_trade.units * pip_value(pair, last.close)
        open_trade.outcome = "WIN" if open_trade.pnl_usd > 0 else "LOSS"
        trades.append(open_trade)

    return trades


def print_results(all_trades: list[Trade]):
    """Print backtest summary."""
    if not all_trades:
        print("\nNo trades generated!")
        return

    wins = [t for t in all_trades if t.outcome == "WIN"]
    losses = [t for t in all_trades if t.outcome == "LOSS"]

    total_pnl = sum(t.pnl_usd for t in all_trades)
    win_pnl = sum(t.pnl_usd for t in wins)
    loss_pnl = sum(t.pnl_usd for t in losses)

    avg_win = win_pnl / len(wins) if wins else Decimal("0")
    avg_loss = loss_pnl / len(losses) if losses else Decimal("0")

    wr = len(wins) / len(all_trades) * 100 if all_trades else 0
    profit_factor = abs(win_pnl / loss_pnl) if loss_pnl != 0 else Decimal("999")

    # Max drawdown
    equity = STARTING_BALANCE
    peak = equity
    max_dd = Decimal("0")
    for t in sorted(all_trades, key=lambda x: x.entry_time):
        equity += t.pnl_usd
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    final_balance = STARTING_BALANCE + total_pnl

    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS -- 2 YEARS")
    print(f"{'='*60}")
    print(f"Starting Balance:  ${STARTING_BALANCE:,.2f}")
    print(f"Final Balance:     ${final_balance:,.2f}")
    print(f"Total P&L:         ${total_pnl:+,.2f}")
    print(f"Return:            {(total_pnl / STARTING_BALANCE * 100):+.1f}%")
    print()
    print(f"Total Trades:      {len(all_trades)}")
    print(f"Wins:              {len(wins)} ({wr:.1f}%)")
    print(f"Losses:            {len(losses)} ({100 - wr:.1f}%)")
    print(f"Avg Win:           ${avg_win:+,.2f}")
    print(f"Avg Loss:          ${avg_loss:+,.2f}")
    print(f"Win/Loss Ratio:    {abs(avg_win / avg_loss) if avg_loss != 0 else 999:.2f}x")
    print(f"Profit Factor:     {profit_factor:.2f}")
    print(f"Max Drawdown:      ${max_dd:,.2f} ({(max_dd / STARTING_BALANCE * 100):.1f}%)")

    # Per-pair breakdown
    print(f"\n{'-'*60}")
    print(f"PER-PAIR BREAKDOWN")
    print(f"{'-'*60}")
    for pair in PAIRS:
        pt = [t for t in all_trades if t.pair == pair]
        if not pt:
            print(f"  {pair}: No trades")
            continue
        pw = [t for t in pt if t.outcome == "WIN"]
        pwr = len(pw) / len(pt) * 100
        ppnl = sum(t.pnl_usd for t in pt)
        print(f"  {pair}: {len(pt)} trades | WR: {pwr:.0f}% | P&L: ${ppnl:+,.2f}")

        # By direction
        for d in ["BUY", "SELL"]:
            dt = [t for t in pt if t.direction == d]
            if dt:
                dw = [t for t in dt if t.outcome == "WIN"]
                dwr = len(dw) / len(dt) * 100
                dpnl = sum(t.pnl_usd for t in dt)
                print(f"    {d}: {len(dt)} trades | WR: {dwr:.0f}% | P&L: ${dpnl:+,.2f}")

    # Per-strategy breakdown
    print(f"\n{'-'*60}")
    print(f"PER-STRATEGY BREAKDOWN")
    print(f"{'-'*60}")
    strategies = set()
    for t in all_trades:
        strategies.add(t.strategy)
    for strat in sorted(strategies):
        st = [t for t in all_trades if t.strategy == strat]
        sw = [t for t in st if t.outcome == "WIN"]
        swr = len(sw) / len(st) * 100
        spnl = sum(t.pnl_usd for t in st)
        print(f"  {strat}: {len(st)} trades | WR: {swr:.0f}% | P&L: ${spnl:+,.2f}")

    # By exit reason
    print(f"\n{'-'*60}")
    print(f"EXIT REASONS")
    print(f"{'-'*60}")
    for reason in ["SL_HIT", "MAX_HOLD", "BACKTEST_END"]:
        rt = [t for t in all_trades if t.exit_reason == reason]
        if rt:
            rw = [t for t in rt if t.outcome == "WIN"]
            rpnl = sum(t.pnl_usd for t in rt)
            print(f"  {reason}: {len(rt)} trades | Wins: {len(rw)} | P&L: ${rpnl:+,.2f}")

    # Monthly breakdown
    print(f"\n{'-'*60}")
    print(f"MONTHLY P&L")
    print(f"{'-'*60}")
    monthly: dict[str, Decimal] = {}
    for t in all_trades:
        month = t.entry_time.strftime("%Y-%m")
        monthly[month] = monthly.get(month, Decimal("0")) + t.pnl_usd
    for month in sorted(monthly):
        bar = "+" * max(0, int(float(monthly[month]) / 200)) if monthly[month] > 0 else "-" * max(0, int(abs(float(monthly[month])) / 200))
        print(f"  {month}: ${monthly[month]:+8,.0f} {bar}")


def main():
    print("LUMITRADE BACKTESTER")
    print(f"Period: 2 years | Pairs: {PAIRS}")
    print(f"Strategies: EMA Trend + Bollinger Reversion + Momentum Breakout")
    print(f"Risk: {RISK_PCT*100}% per trade | Max hold: {MAX_HOLD_CANDLES_H1}h")

    all_trades: list[Trade] = []
    for pair in PAIRS:
        trades = backtest_pair(pair)
        all_trades.extend(trades)
        print(f"  -> {pair}: {len(trades)} trades")

    print_results(all_trades)


if __name__ == "__main__":
    main()
