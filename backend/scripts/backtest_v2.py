"""
Lumitrade Backtester v2 — live-parity, walk-forward, ablation, Monte Carlo.

Replaces backend/scripts/backtest.py. Mirrors the production filter stack as of
2026-04-24 (post 106-trade audit + engine tune commit 6948951):

  - 3.0x ATR stop loss (was 1.5x in v1)
  - 24-hour max hold (was 6h in v1)
  - Confidence band 0.70-0.80 (v1 had no band)
  - ADX(14) regime gate: trend → EMA+Momentum, range → BB+Momentum
  - Tiered risk: 0.5/1.0/2.0% by confidence (v1: flat 1.5%)
  - Per-pair session windows (USD_JPY 0-17, USD_CAD 8-17)
  - 17:00 UTC global cutoff
  - Daily $2000 loss circuit breaker
  - Trailing stop trail = original entry→SL distance (v1 hardcoded 18-20p)
  - Min SL pips = 15 (v1 had 10)
  - Friction: flat spread cost (1.5p USD_CAD, 1.0p USD_JPY) + 0.5p slippage entry+exit
  - Daily swap on holds >24h (positive long carry on USD_CAD/JPY at current rates)

Adds methodology missing from v1:
  - Walk-forward (6mo train / 3mo test, rolling)
  - Sharpe / Sortino / Calmar / MAR / Expectancy / Recovery Factor / Wilson 95% CI
  - Monte Carlo bootstrap (10,000 resamples) for worst-case DD
  - Per-filter ablation (toggle each gate to measure marginal contribution)
  - Look-ahead bias self-test (entry at open[i+1], not close[i])

Usage:
    cd backend
    python -m scripts.backtest_v2                          # full run, default pairs
    python -m scripts.backtest_v2 --pair USD_CAD           # single pair
    python -m scripts.backtest_v2 --walk-forward           # rolling WFA
    python -m scripts.backtest_v2 --ablate                 # run filter ablation
    python -m scripts.backtest_v2 --monte-carlo 10000      # bootstrap DD
    python -m scripts.backtest_v2 --report tasks/bt.md     # write markdown report

Lessons (Trading Memory) are deliberately NOT applied — they were learned from
live trades inside the backtest window and would be forward-looking bias. See
tasks/backtest_parity_audit.md section D.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"

# ─── Pair Configuration ───────────────────────────────────────────────────────

PAIRS_DEFAULT = ["USD_CAD", "USD_JPY"]

PIP_SIZE: dict[str, Decimal] = {
    "USD_JPY": Decimal("0.01"),
    "USD_CAD": Decimal("0.0001"),
    "AUD_USD": Decimal("0.0001"),
    "NZD_USD": Decimal("0.0001"),
    "BTC_USD": Decimal("1.00"),   # 1 pip = $1 move in BTC price
}

# Crypto pairs use fractional (Decimal) units; all others use integer units
_FRACTIONAL_UNIT_PAIRS = {"BTC_USD", "ETH_USD", "LTC_USD"}

# Live source: backend/lumitrade/main.py:357-362 (_pair_hours)
SESSION_HOURS_LIVE: dict[str, tuple[int, int]] = {
    "USD_JPY": (0, 17),
    "USD_CAD": (8, 17),
    "AUD_USD": (0, 8),
    "NZD_USD": (0, 8),
    "BTC_USD": (0, 17),   # 24/7 asset; apply global 17 UTC cutoff
}

# Live source: backend/lumitrade/execution_engine/engine.py
BREAKEVEN_PIPS = {"USD_JPY": 15, "USD_CAD": 15, "AUD_USD": 15, "NZD_USD": 15,
                  "BTC_USD": 200}   # $200 move before breakeven
TRAIL_ACTIVATION_PIPS = {"USD_JPY": 20, "USD_CAD": 18, "AUD_USD": 15, "NZD_USD": 15,
                          "BTC_USD": 300}  # $300 move before trailing activates

# Friction defaults (Phase 1 research recommendation)
SPREAD_PIPS_DEFAULT: dict[str, Decimal] = {
    "USD_CAD": Decimal("1.5"),
    "USD_JPY": Decimal("1.0"),
    "AUD_USD": Decimal("1.5"),
    "NZD_USD": Decimal("1.5"),
    "BTC_USD": Decimal("50"),     # ~$50 typical BTC/USD spread on OANDA practice
}
SLIPPAGE_PIPS = Decimal("0.5")  # per side (entry and exit)

# Annualized swap rates approximated from current rate differentials
# Source: OANDA financing rates median 2024-2026, expressed as pips/day for long
SWAP_PIPS_PER_DAY: dict[str, dict[str, Decimal]] = {
    "USD_CAD": {"BUY": Decimal("0.3"), "SELL": Decimal("-0.3")},
    "USD_JPY": {"BUY": Decimal("0.8"), "SELL": Decimal("-0.8")},
    "AUD_USD": {"BUY": Decimal("-0.2"), "SELL": Decimal("0.2")},
    "NZD_USD": {"BUY": Decimal("-0.2"), "SELL": Decimal("0.2")},
    "BTC_USD": {"BUY": Decimal("0"), "SELL": Decimal("0")},  # no swap for crypto CFDs
}


# ─── Data Types ───────────────────────────────────────────────────────────────


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
    rsi_14: Decimal = Decimal("50")
    bb_upper: Decimal = Decimal("0")
    bb_mid: Decimal = Decimal("0")
    bb_lower: Decimal = Decimal("0")
    macd_line: Decimal = Decimal("0")
    macd_signal: Decimal = Decimal("0")
    macd_histogram: Decimal = Decimal("0")
    atr_14: Decimal = Decimal("0")
    adx_14: Decimal = Decimal("0")


@dataclass
class FilterToggles:
    """Each filter can be toggled off for ablation runs."""
    use_adx_regime: bool = True
    use_confidence_band: bool = True       # 0.70 floor + 0.80 ceiling
    use_session_window: bool = True
    use_global_cutoff_17_utc: bool = True
    use_daily_loss_limit: bool = True
    use_max_hold: bool = True              # 24h force-close
    use_min_sl_pips: bool = True           # 15 pip floor
    use_tiered_risk: bool = True           # 0.5/1.0/2.0% tiered vs flat
    use_friction: bool = True              # spread + slippage + swap
    use_trailing_stop: bool = True
    use_breakeven: bool = True
    use_cooldown: bool = True              # 5 min between trades on same pair


@dataclass
class BacktestConfig:
    starting_balance: Decimal = Decimal("100000")
    sl_atr_multiplier: Decimal = Decimal("3.0")
    min_sl_pips: int = 15
    max_units: int = 500_000
    max_hold_hours: int = 24
    daily_loss_limit_usd: Decimal = Decimal("2000")
    cooldown_seconds: int = 300                   # 5 min
    confidence_floor: float = 0.70
    confidence_ceiling: float = 0.80
    session_hours: dict[str, tuple[int, int]] = field(
        default_factory=lambda: dict(SESSION_HOURS_LIVE)
    )
    spread_pips: dict[str, Decimal] = field(
        default_factory=lambda: dict(SPREAD_PIPS_DEFAULT)
    )
    slippage_pips: Decimal = SLIPPAGE_PIPS
    risk_pct_low_conf: Decimal = Decimal("0.005")    # < 0.80
    risk_pct_mid_conf: Decimal = Decimal("0.01")     # >= 0.80 (effectively the only tier given 0.80 cap)
    risk_pct_high_conf: Decimal = Decimal("0.02")    # >= 0.90 (dead branch under 0.80 cap)


@dataclass
class Trade:
    pair: str
    direction: str
    entry_price: Decimal
    stop_loss: Decimal
    entry_time: datetime
    units: Decimal
    confidence_score: float
    strategies_fired: str
    regime: str
    # Filled on close
    exit_price: Decimal = Decimal("0")
    exit_time: datetime | None = None
    pnl_pips: Decimal = Decimal("0")
    pnl_usd: Decimal = Decimal("0")
    outcome: str = ""
    exit_reason: str = ""
    breakeven_set: bool = False
    trailing_active: bool = False
    spread_cost_usd: Decimal = Decimal("0")
    slippage_cost_usd: Decimal = Decimal("0")
    swap_pnl_usd: Decimal = Decimal("0")


@dataclass
class BacktestResult:
    pair: str
    label: str                      # "baseline", "no_adx", "no_session", etc.
    trades: list[Trade]
    starting_balance: Decimal
    ending_balance: Decimal
    total_pnl: Decimal
    win_count: int
    loss_count: int
    breakeven_count: int
    win_rate: float
    profit_factor: float
    expectancy_usd: Decimal
    expectancy_r: float            # in R-multiples
    avg_win: Decimal
    avg_loss: Decimal
    win_loss_ratio: float
    max_drawdown_usd: Decimal
    max_drawdown_pct: float
    recovery_factor: float
    sharpe_annualized: float
    sortino_annualized: float
    calmar: float
    mar: float
    wilson_ci_low: float
    wilson_ci_high: float
    expectancy_ci_low: float
    expectancy_ci_high: float


# ─── CSV Loader ───────────────────────────────────────────────────────────────


def load_candles(pair: str, timeframe: str = "H1") -> list[Candle]:
    filepath = DATA_DIR / f"{pair}_{timeframe}.csv"
    if not filepath.exists():
        raise FileNotFoundError(f"{filepath} not found — run fetch_historical.py first")
    candles: list[Candle] = []
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = datetime.fromisoformat(row["time"])
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            candles.append(Candle(
                time=t,
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
                volume=int(row["volume"]),
            ))
    return candles


# ─── Indicators (full-series, no look-ahead) ──────────────────────────────────


def compute_ema_series(closes: list[Decimal], period: int) -> list[Decimal]:
    if not closes:
        return []
    emas = [closes[0]]
    mult = Decimal(str(2 / (period + 1)))
    for i in range(1, len(closes)):
        emas.append(closes[i] * mult + emas[-1] * (1 - mult))
    return emas


def compute_rsi_series(closes: list[Decimal], period: int = 14) -> list[Decimal]:
    n = len(closes)
    rsis = [Decimal("50")] * n
    if n <= period:
        return rsis
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, Decimal("0")))
        losses.append(abs(min(change, Decimal("0"))))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period, n):
        change = closes[i] - closes[i - 1]
        gain = max(change, Decimal("0"))
        loss = abs(min(change, Decimal("0")))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsis[i] = Decimal("100")
        else:
            rs = avg_gain / avg_loss
            rsis[i] = Decimal("100") - Decimal("100") / (1 + rs)
    return rsis


def compute_atr_series(candles: list[Candle], period: int = 14) -> list[Decimal]:
    n = len(candles)
    if n < 2:
        return [Decimal("0")] * n
    trs = [candles[0].high - candles[0].low]
    for i in range(1, n):
        tr = max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - candles[i - 1].close),
            abs(candles[i].low - candles[i - 1].close),
        )
        trs.append(tr)
    atrs = [Decimal("0")] * n
    if n >= period:
        atrs[period - 1] = sum(trs[:period]) / period
        for i in range(period, n):
            atrs[i] = (atrs[i - 1] * (period - 1) + trs[i]) / period
    return atrs


def compute_macd_series(closes: list[Decimal]) -> tuple[list[Decimal], list[Decimal], list[Decimal]]:
    ema12 = compute_ema_series(closes, 12)
    ema26 = compute_ema_series(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    macd_signal = compute_ema_series(macd_line, 9)
    macd_hist = [m - s for m, s in zip(macd_line, macd_signal)]
    return macd_line, macd_signal, macd_hist


def compute_bb_series(closes: list[Decimal], period: int = 20) -> tuple[list[Decimal], list[Decimal], list[Decimal]]:
    n = len(closes)
    mids = [closes[i] if i < period - 1 else Decimal("0") for i in range(n)]
    uppers = list(mids)
    lowers = list(mids)
    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        mid = sum(window) / period
        variance = float(sum((x - mid) ** 2 for x in window) / period)
        std = Decimal(str(math.sqrt(variance)))
        mids[i] = mid
        uppers[i] = mid + 2 * std
        lowers[i] = mid - 2 * std
    return mids, uppers, lowers


def compute_adx_series(candles: list[Candle], period: int = 14) -> list[Decimal]:
    """Wilder's ADX(14). Returns list[Decimal] aligned to candles, 0 during warmup."""
    n = len(candles)
    if n < 2 * period:
        return [Decimal("0")] * n

    plus_dm: list[Decimal] = [Decimal("0")]
    minus_dm: list[Decimal] = [Decimal("0")]
    trs: list[Decimal] = [candles[0].high - candles[0].low]

    for i in range(1, n):
        up_move = candles[i].high - candles[i - 1].high
        down_move = candles[i - 1].low - candles[i].low
        pdm = up_move if (up_move > down_move and up_move > 0) else Decimal("0")
        mdm = down_move if (down_move > up_move and down_move > 0) else Decimal("0")
        plus_dm.append(pdm)
        minus_dm.append(mdm)
        tr = max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - candles[i - 1].close),
            abs(candles[i].low - candles[i - 1].close),
        )
        trs.append(tr)

    # Wilder smoothing (similar to EMA but with alpha = 1/period)
    smoothed_pdm = [Decimal("0")] * n
    smoothed_mdm = [Decimal("0")] * n
    smoothed_tr = [Decimal("0")] * n
    smoothed_pdm[period] = sum(plus_dm[1:period + 1])
    smoothed_mdm[period] = sum(minus_dm[1:period + 1])
    smoothed_tr[period] = sum(trs[1:period + 1])
    for i in range(period + 1, n):
        smoothed_pdm[i] = smoothed_pdm[i - 1] - smoothed_pdm[i - 1] / period + plus_dm[i]
        smoothed_mdm[i] = smoothed_mdm[i - 1] - smoothed_mdm[i - 1] / period + minus_dm[i]
        smoothed_tr[i] = smoothed_tr[i - 1] - smoothed_tr[i - 1] / period + trs[i]

    plus_di: list[Decimal] = [Decimal("0")] * n
    minus_di: list[Decimal] = [Decimal("0")] * n
    dx: list[Decimal] = [Decimal("0")] * n
    for i in range(period, n):
        if smoothed_tr[i] != 0:
            plus_di[i] = Decimal("100") * smoothed_pdm[i] / smoothed_tr[i]
            minus_di[i] = Decimal("100") * smoothed_mdm[i] / smoothed_tr[i]
            di_sum = plus_di[i] + minus_di[i]
            if di_sum != 0:
                dx[i] = Decimal("100") * abs(plus_di[i] - minus_di[i]) / di_sum

    adx: list[Decimal] = [Decimal("0")] * n
    if n >= 2 * period:
        adx[2 * period - 1] = sum(dx[period:2 * period]) / period
        for i in range(2 * period, n):
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return adx


def precompute_indicators(candles: list[Candle]) -> list[Indicators]:
    closes = [c.close for c in candles]
    ema20 = compute_ema_series(closes, 20)
    ema50 = compute_ema_series(closes, 50)
    ema200 = compute_ema_series(closes, 200)
    rsi = compute_rsi_series(closes, 14)
    atr = compute_atr_series(candles, 14)
    macd_l, macd_s, macd_h = compute_macd_series(closes)
    bb_m, bb_u, bb_l = compute_bb_series(closes, 20)
    adx = compute_adx_series(candles, 14)
    out = []
    for i in range(len(candles)):
        out.append(Indicators(
            ema_20=ema20[i] if i < len(ema20) else Decimal("0"),
            ema_50=ema50[i] if i < len(ema50) else Decimal("0"),
            ema_200=ema200[i] if i < len(ema200) else Decimal("0"),
            rsi_14=rsi[i],
            bb_upper=bb_u[i],
            bb_mid=bb_m[i],
            bb_lower=bb_l[i],
            macd_line=macd_l[i],
            macd_signal=macd_s[i],
            macd_histogram=macd_h[i],
            atr_14=atr[i],
            adx_14=adx[i],
        ))
    return out


# ─── Live-mirror Quant Strategy ───────────────────────────────────────────────


def ema_trend_signal(ind: Indicators, price: Decimal) -> dict:
    ema20 = float(ind.ema_20); ema50 = float(ind.ema_50); ema200 = float(ind.ema_200)
    px = float(price)
    if ema20 == 0 or ema50 == 0 or ema200 == 0:
        return {"name": "EMA_TREND", "action": "HOLD", "score": 0.0}
    full_bull = ema20 > ema50 > ema200
    full_bear = ema20 < ema50 < ema200
    if full_bull and px > ema200:
        return {"name": "EMA_TREND", "action": "BUY", "score": 0.85 if px > ema20 else 0.65}
    if full_bear and px < ema200:
        return {"name": "EMA_TREND", "action": "SELL", "score": 0.85 if px < ema20 else 0.65}
    if ema20 > ema50 and px > ema50:
        return {"name": "EMA_TREND", "action": "BUY", "score": 0.45}
    if ema20 < ema50 and px < ema50:
        return {"name": "EMA_TREND", "action": "SELL", "score": 0.45}
    return {"name": "EMA_TREND", "action": "HOLD", "score": 0.0}


def bb_revert_signal(ind: Indicators, price: Decimal) -> dict:
    px = float(price)
    bb_u = float(ind.bb_upper); bb_l = float(ind.bb_lower); bb_m = float(ind.bb_mid)
    rsi = float(ind.rsi_14)
    if bb_u == 0 or bb_l == 0 or bb_m == 0:
        return {"name": "BB_REVERT", "action": "HOLD", "score": 0.0}
    width = bb_u - bb_l
    if width == 0:
        return {"name": "BB_REVERT", "action": "HOLD", "score": 0.0}
    dist = (px - bb_m) / (width / 2)
    if dist <= -0.85 and rsi < 35:
        return {"name": "BB_REVERT", "action": "BUY", "score": 0.75 if rsi < 25 else 0.55}
    if dist >= 0.85 and rsi > 65:
        return {"name": "BB_REVERT", "action": "SELL", "score": 0.75 if rsi > 75 else 0.55}
    return {"name": "BB_REVERT", "action": "HOLD", "score": 0.0}


def momentum_signal(ind: Indicators) -> dict:
    h = float(ind.macd_histogram); ml = float(ind.macd_line); ms = float(ind.macd_signal)
    rsi = float(ind.rsi_14)
    bull = h > 0 and ml > ms
    bear = h < 0 and ml < ms
    if bull and 45 < rsi < 72:
        return {"name": "MOMENTUM", "action": "BUY", "score": 0.70 if abs(h) > abs(ms) * 0.3 else 0.45}
    if bear and 28 < rsi < 55:
        return {"name": "MOMENTUM", "action": "SELL", "score": 0.70 if abs(h) > abs(ms) * 0.3 else 0.45}
    return {"name": "MOMENTUM", "action": "HOLD", "score": 0.0}


def quant_evaluate(
    ind: Indicators,
    price: Decimal,
    toggles: FilterToggles,
) -> tuple[str, float, list[str], str]:
    """Live-mirror of QuantEngine.evaluate. Returns (action, score, strategies, regime)."""
    adx = float(ind.adx_14)
    is_trending = adx >= 25 and toggles.use_adx_regime
    is_ranging = 0 < adx < 25 and toggles.use_adx_regime

    if is_trending:
        ema = ema_trend_signal(ind, price)
        bb = {"name": "BB_REVERT", "action": "HOLD", "score": 0.0}
        mom = momentum_signal(ind)
        regime = "TRENDING"
    elif is_ranging:
        ema = {"name": "EMA_TREND", "action": "HOLD", "score": 0.0}
        bb = bb_revert_signal(ind, price)
        mom = momentum_signal(ind)
        regime = "RANGING"
    else:
        ema = ema_trend_signal(ind, price)
        bb = bb_revert_signal(ind, price)
        mom = momentum_signal(ind)
        regime = "UNKNOWN"

    signals = [ema, bb, mom]
    buy_votes = [s for s in signals if s["action"] == "BUY"]
    sell_votes = [s for s in signals if s["action"] == "SELL"]
    buy_score = sum(s["score"] for s in buy_votes)
    sell_score = sum(s["score"] for s in sell_votes)

    # Tier 1: 2+ agreement
    if len(buy_votes) >= 2 and buy_score > sell_score:
        score = min(0.70 + (buy_score / 3) * 0.30, 1.0)
        return "BUY", score, [s["name"] for s in buy_votes], regime
    if len(sell_votes) >= 2 and sell_score > buy_score:
        score = min(0.70 + (sell_score / 3) * 0.30, 1.0)
        return "SELL", score, [s["name"] for s in sell_votes], regime
    # Tier 2: solo strong, no opposition
    if buy_votes and len(sell_votes) == 0:
        best = max(buy_votes, key=lambda s: s["score"])
        if best["score"] >= 0.65:
            return "BUY", 0.55 + (best["score"] - 0.65) * 0.5, [best["name"]], regime
    if sell_votes and len(buy_votes) == 0:
        best = max(sell_votes, key=lambda s: s["score"])
        if best["score"] >= 0.65:
            return "SELL", 0.55 + (best["score"] - 0.65) * 0.5, [best["name"]], regime
    return "HOLD", 0.0, [], regime


# ─── Position Sizing & Friction ───────────────────────────────────────────────


def confidence_tier_risk_pct(score: float, cfg: BacktestConfig, toggles: FilterToggles) -> Decimal:
    if not toggles.use_tiered_risk:
        return Decimal("0.015")  # legacy v1 behavior for ablation
    if score >= 0.90:
        return cfg.risk_pct_high_conf
    if score >= 0.80:
        return cfg.risk_pct_mid_conf
    return cfg.risk_pct_low_conf


def pip_value_per_unit(pair: str, price: Decimal) -> Decimal:
    """Approximate USD pip value per 1 unit of base currency."""
    ps = PIP_SIZE[pair]
    if pair.startswith("USD"):
        return ps / price
    return ps  # quote currency is USD → pip value = pip_size USD


def round_price(price: Decimal, pair: str) -> Decimal:
    if "JPY" in pair:
        return price.quantize(Decimal("0.001"))
    if "BTC" in pair or "ETH" in pair:
        return price.quantize(Decimal("0.01"))
    return price.quantize(Decimal("0.00001"))


# ─── Backtest Engine ──────────────────────────────────────────────────────────


def run_backtest(
    pair: str,
    candles: list[Candle],
    indicators: list[Indicators],
    cfg: BacktestConfig,
    toggles: FilterToggles,
    starting_balance: Decimal | None = None,
    label: str = "baseline",
) -> list[Trade]:
    """
    Single-pair sequential simulation. Mirrors live filter stack.

    Critical timing rule: signal evaluated on bar i (using CLOSED data through i),
    entry at open[i+1], not close[i]. This avoids look-ahead bias.
    """
    if len(candles) != len(indicators):
        raise ValueError("candles and indicators length mismatch")
    n = len(candles)
    if n < 250:
        return []

    balance = starting_balance if starting_balance is not None else cfg.starting_balance
    trades: list[Trade] = []
    open_trade: Trade | None = None
    cooldown_until: datetime | None = None

    sess_start, sess_end = cfg.session_hours.get(pair, (0, 24))
    spread_pips = cfg.spread_pips.get(pair, Decimal("1.5"))
    pip = PIP_SIZE[pair]

    # Daily P&L tracking for circuit breaker
    daily_pnl: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    # Start AFTER warmup (200 candles for EMA200, 28 for ADX)
    warmup = max(200, 28)

    for i in range(warmup, n - 1):  # n-1 because entry is at i+1
        candle = candles[i]
        next_candle = candles[i + 1]
        ind = indicators[i]
        hour = candle.time.hour
        date_key = candle.time.date().isoformat()

        # ─── Manage open position (use bar i's H/L for SL/trail/maxhold checks) ─
        if open_trade is not None:
            tr_pip = pip
            sl_hit = False
            exit_price: Decimal | None = None
            exit_reason = ""

            if open_trade.direction == "BUY":
                if candle.low <= open_trade.stop_loss:
                    sl_hit = True
                    exit_price = open_trade.stop_loss
                    exit_reason = "TRAILING_STOP" if open_trade.trailing_active else "SL_HIT"
                else:
                    profit_pips = (candle.close - open_trade.entry_price) / tr_pip
                    if toggles.use_breakeven and not open_trade.breakeven_set and profit_pips >= BREAKEVEN_PIPS[pair]:
                        open_trade.stop_loss = open_trade.entry_price
                        open_trade.breakeven_set = True
                    if toggles.use_trailing_stop and profit_pips >= TRAIL_ACTIVATION_PIPS[pair]:
                        # Live: trail by ORIGINAL entry→SL distance, not hardcoded pips
                        if not open_trade.trailing_active:
                            initial_sl_distance = abs(open_trade.entry_price - (
                                open_trade.entry_price - cfg.sl_atr_multiplier * indicators[
                                    next((j for j in range(len(candles)) if candles[j].time >= open_trade.entry_time), i)
                                ].atr_14
                            ))
                            # Simpler: use the actual entry-to-SL distance at OPEN time
                            initial_sl_distance = open_trade.entry_price - open_trade.stop_loss
                            if open_trade.breakeven_set:
                                # After breakeven was set, restore the original distance
                                initial_sl_distance = open_trade.entry_price * Decimal("0") + cfg.sl_atr_multiplier * tr_pip * Decimal("20")
                            open_trade.trailing_active = True
                        # Trail by initial_sl_distance behind current close
                        trail_distance = max(
                            (open_trade.entry_price - open_trade.stop_loss).copy_abs(),
                            cfg.sl_atr_multiplier * tr_pip * Decimal("15"),  # safety floor
                        )
                        new_sl = candle.close - trail_distance
                        if new_sl > open_trade.stop_loss:
                            open_trade.stop_loss = new_sl
            else:  # SELL
                if candle.high >= open_trade.stop_loss:
                    sl_hit = True
                    exit_price = open_trade.stop_loss
                    exit_reason = "TRAILING_STOP" if open_trade.trailing_active else "SL_HIT"
                else:
                    profit_pips = (open_trade.entry_price - candle.close) / tr_pip
                    if toggles.use_breakeven and not open_trade.breakeven_set and profit_pips >= BREAKEVEN_PIPS[pair]:
                        open_trade.stop_loss = open_trade.entry_price
                        open_trade.breakeven_set = True
                    if toggles.use_trailing_stop and profit_pips >= TRAIL_ACTIVATION_PIPS[pair]:
                        if not open_trade.trailing_active:
                            open_trade.trailing_active = True
                        trail_distance = max(
                            (open_trade.stop_loss - open_trade.entry_price).copy_abs(),
                            cfg.sl_atr_multiplier * tr_pip * Decimal("15"),
                        )
                        new_sl = candle.close + trail_distance
                        if new_sl < open_trade.stop_loss:
                            open_trade.stop_loss = new_sl

            # Max hold check (24h = 24 H1 candles)
            if not sl_hit and toggles.use_max_hold:
                # Find the candle index of entry_time
                hold_candles = i - next(
                    (j for j in range(i, -1, -1) if candles[j].time <= open_trade.entry_time),
                    i,
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

            continue  # already in trade

        # ─── No open position — evaluate signal ─
        # Cooldown
        if toggles.use_cooldown and cooldown_until is not None:
            if (candle.time - cooldown_until).total_seconds() < cfg.cooldown_seconds:
                continue

        # 17:00 UTC global cutoff (live: main.py:351)
        if toggles.use_global_cutoff_17_utc and hour >= 17:
            continue

        # Per-pair session window
        if toggles.use_session_window and not (sess_start <= hour < sess_end):
            continue

        # Daily loss circuit breaker
        if toggles.use_daily_loss_limit and daily_pnl[date_key] <= -cfg.daily_loss_limit_usd:
            continue

        # Quant evaluation (uses indicators at bar i — closed data only)
        action, score, strategies, regime = quant_evaluate(ind, candle.close, toggles)
        if action == "HOLD":
            continue

        # Confidence band (live: 0.70-0.80)
        if toggles.use_confidence_band:
            if score < cfg.confidence_floor or score > cfg.confidence_ceiling:
                continue

        # Position sizing
        atr = ind.atr_14
        if atr == 0:
            continue
        sl_distance = atr * cfg.sl_atr_multiplier
        sl_pips = sl_distance / pip
        if toggles.use_min_sl_pips and sl_pips < cfg.min_sl_pips:
            continue

        # Entry at NEXT BAR'S OPEN (no look-ahead)
        entry_price = next_candle.open
        # Apply slippage
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
            # Crypto: keep 2dp fractional (e.g. 0.17 BTC); minimum 0.01
            units = max(Decimal("0"), raw_units.quantize(Decimal("0.01")))
            min_units: Decimal = Decimal("0.01")
        else:
            units = Decimal(max(0, int(raw_units)))
            min_units = Decimal("1000")
        units = min(units, Decimal(str(cfg.max_units)))
        if units < min_units:
            continue

        # Open
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
        )

    # Close any still-open trade at last close
    if open_trade is not None:
        last = candles[-1]
        _close_trade(open_trade, last.close, last.time, "BACKTEST_END", pair, cfg, toggles,
                     cfg.spread_pips.get(pair, Decimal("1.5")))
        trades.append(open_trade)

    # Tag trades with label for ablation tracking
    for t in trades:
        t.strategies_fired = f"{label}:{t.strategies_fired}" if label != "baseline" else t.strategies_fired
    return trades


def _close_trade(
    t: Trade,
    exit_price: Decimal,
    exit_time: datetime,
    exit_reason: str,
    pair: str,
    cfg: BacktestConfig,
    toggles: FilterToggles,
    spread_pips: Decimal,
) -> None:
    pip = PIP_SIZE[pair]
    # Apply exit slippage
    if toggles.use_friction:
        slip_amt = cfg.slippage_pips * pip
        exit_price = exit_price - slip_amt if t.direction == "BUY" else exit_price + slip_amt

    if t.direction == "BUY":
        pnl_pips = (exit_price - t.entry_price) / pip
    else:
        pnl_pips = (t.entry_price - exit_price) / pip

    pv = pip_value_per_unit(pair, exit_price)
    pnl_usd = pnl_pips * t.units * pv

    # Spread cost (1 round trip)
    spread_cost = Decimal("0")
    swap_pnl = Decimal("0")
    if toggles.use_friction:
        spread_cost = spread_pips * t.units * pv
        # Swap on holds > 24h
        days_held = (exit_time - t.entry_time).total_seconds() / 86400
        if days_held > 1:
            swap_per_day = SWAP_PIPS_PER_DAY.get(pair, {}).get(t.direction, Decimal("0"))
            swap_pnl = swap_per_day * t.units * pv * Decimal(str(days_held - 1))
        pnl_usd = pnl_usd - spread_cost + swap_pnl

    t.exit_price = exit_price
    t.exit_time = exit_time
    t.exit_reason = exit_reason
    t.pnl_pips = pnl_pips
    t.pnl_usd = pnl_usd
    t.spread_cost_usd = spread_cost
    t.swap_pnl_usd = swap_pnl
    t.outcome = "WIN" if pnl_usd > 1 else ("LOSS" if pnl_usd < -1 else "BREAKEVEN")


# ─── Metrics ──────────────────────────────────────────────────────────────────


def wilson_ci(wins: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score 95% CI for a proportion. Robust for small N."""
    if n == 0:
        return 0.0, 0.0
    z = 1.96  # 95%
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def bootstrap_ci(values: list[float], n_resamples: int = 5000, alpha: float = 0.05) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    means = []
    for _ in range(n_resamples):
        sample = [random.choice(values) for _ in range(len(values))]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo = means[int(n_resamples * alpha / 2)]
    hi = means[int(n_resamples * (1 - alpha / 2))]
    return lo, hi


def max_drawdown(equity_curve: list[Decimal]) -> tuple[Decimal, float]:
    if not equity_curve:
        return Decimal("0"), 0.0
    peak = equity_curve[0]
    max_dd = Decimal("0")
    max_dd_pct = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = peak - v
            dd_pct = float(dd / peak * 100)
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
    return max_dd, max_dd_pct


def annualized_sharpe(returns: list[float], periods_per_year: int = 252) -> float:
    if len(returns) < 2:
        return 0.0
    mean = statistics.mean(returns)
    std = statistics.stdev(returns)
    if std == 0:
        return 0.0
    return mean / std * math.sqrt(periods_per_year)


def annualized_sortino(returns: list[float], periods_per_year: int = 252) -> float:
    if len(returns) < 2:
        return 0.0
    mean = statistics.mean(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return 0.0
    downside_std = math.sqrt(sum(r * r for r in downside) / len(returns))
    if downside_std == 0:
        return 0.0
    return mean / downside_std * math.sqrt(periods_per_year)


def compute_metrics(
    pair: str,
    label: str,
    trades: list[Trade],
    starting_balance: Decimal,
) -> BacktestResult:
    if not trades:
        return BacktestResult(
            pair=pair, label=label, trades=[], starting_balance=starting_balance,
            ending_balance=starting_balance, total_pnl=Decimal("0"),
            win_count=0, loss_count=0, breakeven_count=0,
            win_rate=0.0, profit_factor=0.0,
            expectancy_usd=Decimal("0"), expectancy_r=0.0,
            avg_win=Decimal("0"), avg_loss=Decimal("0"), win_loss_ratio=0.0,
            max_drawdown_usd=Decimal("0"), max_drawdown_pct=0.0,
            recovery_factor=0.0, sharpe_annualized=0.0, sortino_annualized=0.0,
            calmar=0.0, mar=0.0, wilson_ci_low=0.0, wilson_ci_high=0.0,
            expectancy_ci_low=0.0, expectancy_ci_high=0.0,
        )

    wins = [t for t in trades if t.outcome == "WIN"]
    losses = [t for t in trades if t.outcome == "LOSS"]
    breakevens = [t for t in trades if t.outcome == "BREAKEVEN"]

    total_pnl = sum(t.pnl_usd for t in trades)
    ending_balance = starting_balance + total_pnl
    win_pnl = sum(t.pnl_usd for t in wins) or Decimal("0")
    loss_pnl = sum(t.pnl_usd for t in losses) or Decimal("0")

    win_rate = len(wins) / len(trades)
    profit_factor = float(abs(win_pnl / loss_pnl)) if loss_pnl != 0 else (999.0 if win_pnl > 0 else 0.0)
    avg_win = win_pnl / len(wins) if wins else Decimal("0")
    avg_loss = loss_pnl / len(losses) if losses else Decimal("0")
    wl_ratio = float(abs(avg_win / avg_loss)) if avg_loss != 0 else 0.0

    expectancy_usd = total_pnl / len(trades)
    # R-multiple expectancy: avg_win in R units (where R = avg_loss)
    expectancy_r = float(expectancy_usd / abs(avg_loss)) if avg_loss != 0 else 0.0

    # Equity curve in chronological order
    eq_curve: list[Decimal] = [starting_balance]
    for t in sorted(trades, key=lambda x: x.entry_time):
        eq_curve.append(eq_curve[-1] + t.pnl_usd)
    max_dd_usd, max_dd_pct = max_drawdown(eq_curve)
    recovery = float(total_pnl / max_dd_usd) if max_dd_usd > 0 else 0.0

    # Returns per trade as fraction of starting balance for Sharpe/Sortino
    returns = [float(t.pnl_usd / starting_balance) for t in sorted(trades, key=lambda x: x.entry_time)]

    # Trades per year approximation
    if len(trades) >= 2:
        first = min(t.entry_time for t in trades)
        last = max(t.entry_time for t in trades)
        years = max(0.5, (last - first).days / 365.25)
    else:
        years = 1.0
    trades_per_year = len(trades) / years
    annualized_return_pct = float(total_pnl / starting_balance / Decimal(str(years)) * 100)

    sharpe = annualized_sharpe(returns, periods_per_year=int(max(50, trades_per_year)))
    sortino = annualized_sortino(returns, periods_per_year=int(max(50, trades_per_year)))
    calmar = annualized_return_pct / max_dd_pct if max_dd_pct > 0 else 0.0
    mar = annualized_return_pct / max_dd_pct if max_dd_pct > 0 else 0.0  # for one period MAR ≈ Calmar

    wci_low, wci_high = wilson_ci(len(wins), len(trades))
    eci_low, eci_high = bootstrap_ci([float(t.pnl_usd) for t in trades], n_resamples=2000)

    return BacktestResult(
        pair=pair, label=label, trades=trades, starting_balance=starting_balance,
        ending_balance=ending_balance, total_pnl=total_pnl,
        win_count=len(wins), loss_count=len(losses), breakeven_count=len(breakevens),
        win_rate=win_rate, profit_factor=profit_factor,
        expectancy_usd=expectancy_usd, expectancy_r=expectancy_r,
        avg_win=avg_win, avg_loss=avg_loss, win_loss_ratio=wl_ratio,
        max_drawdown_usd=max_dd_usd, max_drawdown_pct=max_dd_pct,
        recovery_factor=recovery, sharpe_annualized=sharpe, sortino_annualized=sortino,
        calmar=calmar, mar=mar,
        wilson_ci_low=wci_low, wilson_ci_high=wci_high,
        expectancy_ci_low=eci_low, expectancy_ci_high=eci_high,
    )


# ─── Walk-Forward ─────────────────────────────────────────────────────────────


@dataclass
class WalkForwardFold:
    fold_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    trades_in_train: int
    trades_in_test: int
    train_pf: float
    test_pf: float
    train_pnl: Decimal
    test_pnl: Decimal


def walk_forward(
    pair: str,
    candles: list[Candle],
    indicators: list[Indicators],
    cfg: BacktestConfig,
    toggles: FilterToggles,
    train_months: int = 6,
    test_months: int = 3,
) -> list[WalkForwardFold]:
    """
    Rolling 6mo-train / 3mo-test walk-forward over the full data window.
    Strategy parameters are NOT optimized per fold (we don't tune); this is
    a pure OOS test to measure stability across regimes.

    Returns one fold per test window. Test trades are concatenated for the
    final OOS equity curve.
    """
    if not candles:
        return []
    folds: list[WalkForwardFold] = []
    first = candles[0].time
    last = candles[-1].time
    train_delta = timedelta(days=train_months * 30)
    test_delta = timedelta(days=test_months * 30)

    cursor = first + train_delta
    fold_id = 0
    while cursor + test_delta <= last:
        train_start = cursor - train_delta
        train_end = cursor
        test_start = cursor
        test_end = min(cursor + test_delta, last)

        # Slice candles + indicators
        train_candles = [c for c in candles if train_start <= c.time < train_end]
        test_candles = [c for c in candles if test_start <= c.time < test_end]
        train_inds = indicators[len(candles) - len(test_candles) - len(train_candles):
                                len(candles) - len(test_candles)]
        test_inds = indicators[len(candles) - len(test_candles):]
        # The above slicing assumes training+test align with end; safer: index by time
        train_inds = [indicators[i] for i, c in enumerate(candles) if train_start <= c.time < train_end]
        test_inds = [indicators[i] for i, c in enumerate(candles) if test_start <= c.time < test_end]

        train_trades = run_backtest(pair, train_candles, train_inds, cfg, toggles,
                                     cfg.starting_balance, label=f"wf_train_{fold_id}")
        test_trades = run_backtest(pair, test_candles, test_inds, cfg, toggles,
                                    cfg.starting_balance, label=f"wf_test_{fold_id}")

        train_metrics = compute_metrics(pair, f"wf_train_{fold_id}", train_trades, cfg.starting_balance)
        test_metrics = compute_metrics(pair, f"wf_test_{fold_id}", test_trades, cfg.starting_balance)

        folds.append(WalkForwardFold(
            fold_id=fold_id,
            train_start=train_start, train_end=train_end,
            test_start=test_start, test_end=test_end,
            trades_in_train=len(train_trades),
            trades_in_test=len(test_trades),
            train_pf=train_metrics.profit_factor,
            test_pf=test_metrics.profit_factor,
            train_pnl=train_metrics.total_pnl,
            test_pnl=test_metrics.total_pnl,
        ))

        cursor += test_delta
        fold_id += 1

    return folds


# ─── Monte Carlo ──────────────────────────────────────────────────────────────


def monte_carlo(trades: list[Trade], starting_balance: Decimal, n_sim: int = 10_000) -> dict:
    """
    Bootstrap resample of trade return sequence. Reports 5th-percentile DD
    and probability of profit.
    """
    if not trades:
        return {"p_profit": 0.0, "p5_dd_pct": 0.0, "median_dd_pct": 0.0, "p95_dd_pct": 0.0,
                "p_profit_count": 0, "n_sim": 0}
    pnls = [t.pnl_usd for t in trades]
    profits = 0
    dds: list[float] = []
    for _ in range(n_sim):
        sample = random.choices(pnls, k=len(pnls))
        eq = [starting_balance]
        for p in sample:
            eq.append(eq[-1] + p)
        if eq[-1] > starting_balance:
            profits += 1
        _, dd_pct = max_drawdown(eq)
        dds.append(dd_pct)
    dds.sort()
    return {
        "p_profit": profits / n_sim,
        "p_profit_count": profits,
        "n_sim": n_sim,
        "p5_dd_pct": dds[int(n_sim * 0.05)],
        "median_dd_pct": dds[int(n_sim * 0.50)],
        "p95_dd_pct": dds[int(n_sim * 0.95)],
    }


# ─── Ablation ─────────────────────────────────────────────────────────────────


ABLATION_VARIANTS: dict[str, dict[str, bool]] = {
    "baseline": {},
    "no_adx": {"use_adx_regime": False},
    "no_confidence_band": {"use_confidence_band": False},
    "no_session": {"use_session_window": False},
    "no_17utc_cutoff": {"use_global_cutoff_17_utc": False},
    "no_daily_loss": {"use_daily_loss_limit": False},
    "no_max_hold": {"use_max_hold": False},
    "no_min_sl": {"use_min_sl_pips": False},
    "no_tiered_risk": {"use_tiered_risk": False},
    "no_friction": {"use_friction": False},
    "no_trailing": {"use_trailing_stop": False},
    "no_breakeven": {"use_breakeven": False},
    "no_cooldown": {"use_cooldown": False},
}


def run_ablation(
    pair: str,
    candles: list[Candle],
    indicators: list[Indicators],
    cfg: BacktestConfig,
) -> dict[str, BacktestResult]:
    results: dict[str, BacktestResult] = {}
    for label, overrides in ABLATION_VARIANTS.items():
        toggles = FilterToggles()
        for k, v in overrides.items():
            setattr(toggles, k, v)
        trades = run_backtest(pair, candles, indicators, cfg, toggles,
                              cfg.starting_balance, label=label)
        results[label] = compute_metrics(pair, label, trades, cfg.starting_balance)
    return results


# ─── Reporting ────────────────────────────────────────────────────────────────


def format_result(r: BacktestResult) -> str:
    return (
        f"  Trades:        {len(r.trades)} (W:{r.win_count}/L:{r.loss_count}/BE:{r.breakeven_count})\n"
        f"  Win rate:      {r.win_rate*100:.1f}%   95% CI: [{r.wilson_ci_low*100:.1f}, {r.wilson_ci_high*100:.1f}]\n"
        f"  P&L:           ${r.total_pnl:+,.2f}  ({float(r.total_pnl/r.starting_balance)*100:+.1f}%)\n"
        f"  Profit factor: {r.profit_factor:.2f}\n"
        f"  Expectancy:    ${r.expectancy_usd:+.2f} / trade  ({r.expectancy_r:+.3f}R)\n"
        f"  Avg W / Avg L: ${r.avg_win:+,.0f} / ${r.avg_loss:+,.0f}  (ratio {r.win_loss_ratio:.2f})\n"
        f"  Max DD:        ${r.max_drawdown_usd:,.2f}  ({r.max_drawdown_pct:.1f}%)\n"
        f"  Sharpe (ann):  {r.sharpe_annualized:.2f}\n"
        f"  Sortino:       {r.sortino_annualized:.2f}\n"
        f"  Calmar / MAR:  {r.calmar:.2f}\n"
        f"  Recovery:      {r.recovery_factor:.2f}\n"
    )


def print_section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ─── CLI ──────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Lumitrade Backtester v2 (live-parity)")
    p.add_argument("--pair", action="append",
                   help="Pair to backtest (repeatable). Default: USD_CAD, USD_JPY")
    p.add_argument("--walk-forward", action="store_true", help="Run walk-forward analysis")
    p.add_argument("--ablate", action="store_true", help="Run ablation (toggle each filter)")
    p.add_argument("--monte-carlo", type=int, metavar="N", default=0,
                   help="Run N-sample Monte Carlo bootstrap (suggest 10000)")
    p.add_argument("--report", type=Path, metavar="PATH",
                   help="Write Markdown report to PATH")
    p.add_argument("--starting-balance", type=Decimal, default=Decimal("100000"),
                   help="Starting balance (default 100000)")
    p.add_argument("--quiet", action="store_true", help="Suppress per-pair detail output")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    pairs = args.pair if args.pair else PAIRS_DEFAULT
    cfg = BacktestConfig(starting_balance=args.starting_balance)

    print(f"LUMITRADE BACKTESTER v2 — live-parity")
    print(f"Pairs: {pairs}")
    print(f"Starting balance: ${cfg.starting_balance:,}")
    print(f"SL: {cfg.sl_atr_multiplier}x ATR | Max hold: {cfg.max_hold_hours}h | "
          f"Conf band: {cfg.confidence_floor:.2f}-{cfg.confidence_ceiling:.2f}")

    all_results: dict[str, BacktestResult] = {}
    walk_forward_results: dict[str, list[WalkForwardFold]] = {}
    ablation_results: dict[str, dict[str, BacktestResult]] = {}
    mc_results: dict[str, dict] = {}

    for pair in pairs:
        print_section(f"BACKTESTING {pair}")
        candles = load_candles(pair, "H1")
        if len(candles) < 250:
            print(f"  Not enough data ({len(candles)} candles)")
            continue
        print(f"  Loaded {len(candles)} H1 candles "
              f"({candles[0].time.date()} -> {candles[-1].time.date()})")

        indicators = precompute_indicators(candles)
        toggles = FilterToggles()  # all on (live parity)

        trades = run_backtest(pair, candles, indicators, cfg, toggles,
                              cfg.starting_balance, label="baseline")
        result = compute_metrics(pair, "baseline", trades, cfg.starting_balance)
        all_results[pair] = result

        if not args.quiet:
            print(format_result(result))

        if args.walk_forward:
            print(f"  Running walk-forward (6mo train / 3mo test)…")
            folds = walk_forward(pair, candles, indicators, cfg, toggles)
            walk_forward_results[pair] = folds
            if not args.quiet:
                for f in folds:
                    print(f"    Fold {f.fold_id}: train PF {f.train_pf:.2f} "
                          f"({f.trades_in_train}t) -> test PF {f.test_pf:.2f} ({f.trades_in_test}t) "
                          f"OOS P&L ${f.test_pnl:+,.0f}")

        if args.ablate:
            print(f"  Running ablation (13 variants)…")
            ablation = run_ablation(pair, candles, indicators, cfg)
            ablation_results[pair] = ablation
            if not args.quiet:
                base_pf = ablation["baseline"].profit_factor
                base_pnl = ablation["baseline"].total_pnl
                print(f"    {'variant':<24} {'trades':>7} {'WR':>6} {'PF':>6} "
                      f"{'PF Δ':>7} {'P&L':>12} {'P&L Δ':>12}")
                for label, r in ablation.items():
                    pf_d = r.profit_factor - base_pf
                    pnl_d = r.total_pnl - base_pnl
                    print(f"    {label:<24} {len(r.trades):>7} {r.win_rate*100:>5.1f}% "
                          f"{r.profit_factor:>6.2f} {pf_d:>+7.2f} ${r.total_pnl:>+10,.0f} "
                          f"${pnl_d:>+10,.0f}")

        if args.monte_carlo > 0:
            print(f"  Running Monte Carlo (n={args.monte_carlo})…")
            mc = monte_carlo(trades, cfg.starting_balance, args.monte_carlo)
            mc_results[pair] = mc
            if not args.quiet:
                print(f"    P(profit) = {mc['p_profit']*100:.1f}%  "
                      f"DD pcts: 5%={mc['p5_dd_pct']:.1f}%  "
                      f"50%={mc['median_dd_pct']:.1f}%  95%={mc['p95_dd_pct']:.1f}%")

    if args.report:
        write_report(args.report, all_results, walk_forward_results, ablation_results, mc_results, cfg)
        print(f"\nReport written to {args.report}")

    return 0


def write_report(
    path: Path,
    results: dict[str, BacktestResult],
    wf: dict[str, list[WalkForwardFold]],
    abl: dict[str, dict[str, BacktestResult]],
    mc: dict[str, dict],
    cfg: BacktestConfig,
) -> None:
    lines: list[str] = []
    lines.append(f"# Lumitrade Backtest v2 Report — {datetime.now(timezone.utc).date()}\n")
    lines.append(f"**Live-parity**. SL {cfg.sl_atr_multiplier}×ATR, max hold {cfg.max_hold_hours}h, "
                 f"conf band {cfg.confidence_floor}-{cfg.confidence_ceiling}, ADX regime gate, "
                 f"tiered risk 0.5/1.0/2.0%, friction modeled.\n")
    lines.append("\n## Per-pair baseline (full history, all live filters on)\n")
    for pair, r in results.items():
        lines.append(f"\n### {pair}\n")
        lines.append("```\n" + format_result(r) + "```\n")

    if wf:
        lines.append("\n## Walk-forward (6mo train / 3mo test rolling)\n")
        for pair, folds in wf.items():
            lines.append(f"\n### {pair}\n\n")
            lines.append("| Fold | Train PF | Train trades | Test PF | Test trades | Test P&L |\n")
            lines.append("|---|---|---|---|---|---|\n")
            for f in folds:
                lines.append(f"| {f.fold_id} | {f.train_pf:.2f} | {f.trades_in_train} "
                             f"| {f.test_pf:.2f} | {f.trades_in_test} | ${f.test_pnl:+,.0f} |\n")
            if folds:
                # Robust aggregate per Codex review 2026-04-25 finding #5.
                # Old code computed mean PF over only positive folds, which
                # silently dropped losing/zero quarters and inflated the
                # apparent OOS quality. New aggregate is honest:
                #   - count of negative/zero folds (drag detector)
                #   - median PF (robust to the 999 sentinel for no-loss folds)
                #   - mean PF over ALL folds (capped to ignore the sentinel)
                #   - total OOS P&L summed over all folds
                # Never use positive-only averaging in any go/no-go decision.
                neg_count = sum(1 for f in folds if f.test_pf <= 1.0)
                # Cap at 99 to neutralize the 999 "no losses" sentinel; PF > 99
                # is statistically meaningless on small fold samples anyway.
                capped_pfs = [min(f.test_pf, 99.0) for f in folds]
                pf_median = statistics.median(capped_pfs)
                pf_mean = statistics.mean(capped_pfs)
                test_pnl_total = sum(f.test_pnl for f in folds)
                drag_warn = " 🔴 some folds were losers" if neg_count > 0 else ""
                lines.append(
                    f"\n**OOS aggregate (all {len(folds)} folds):** "
                    f"median PF {pf_median:.2f}, mean PF {pf_mean:.2f}, "
                    f"total OOS P&L ${test_pnl_total:+,.0f}, "
                    f"folds at PF≤1.0: **{neg_count}**.{drag_warn}\n"
                )

    if abl:
        lines.append("\n## Ablation — marginal contribution of each filter\n")
        for pair, variants in abl.items():
            lines.append(f"\n### {pair}\n\n")
            base = variants["baseline"]
            lines.append("| Variant | Trades | WR | PF | PF Δ | P&L | P&L Δ vs baseline |\n")
            lines.append("|---|---|---|---|---|---|---|\n")
            for label, r in variants.items():
                pf_d = r.profit_factor - base.profit_factor
                pnl_d = r.total_pnl - base.total_pnl
                lines.append(f"| {label} | {len(r.trades)} | {r.win_rate*100:.1f}% "
                             f"| {r.profit_factor:.2f} | {pf_d:+.2f} | ${r.total_pnl:+,.0f} "
                             f"| ${pnl_d:+,.0f} |\n")
            lines.append("\n*Filters with positive `P&L Δ` when REMOVED are dead-weight or harmful.*\n")

    if mc:
        lines.append("\n## Monte Carlo bootstrap (10k resamples)\n\n")
        lines.append("| Pair | P(profit) | DD 5% | DD median | DD 95% |\n")
        lines.append("|---|---|---|---|---|\n")
        for pair, m in mc.items():
            lines.append(f"| {pair} | {m['p_profit']*100:.1f}% | {m['p5_dd_pct']:.1f}% "
                         f"| {m['median_dd_pct']:.1f}% | {m['p95_dd_pct']:.1f}% |\n")

    lines.append("\n## Methodology notes\n")
    lines.append("- Entries placed at **open[i+1]** (not close[i]) to avoid look-ahead bias.\n")
    lines.append("- Indicators use only data through bar i (verified by parity tests).\n")
    lines.append("- Lesson filter (BLOCK/BOOST) deliberately **not applied** — rules were "
                 "learned from live trades inside this window (forward-looking bias).\n")
    lines.append("- Friction: spread cost (1.5p USD_CAD / 1.0p USD_JPY) + 0.5p slippage "
                 "entry & exit + daily swap on holds >24h.\n")
    lines.append("- Methodology grounded in Pardo (2008), Aronson (2007), "
                 "Bailey & López de Prado (2014), Carver (2015), Chan (2013).\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
