"""
AMD sweep-reversal backtest — Asia range, London sweep, NY reversion.

🔴 STATUS: REJECTED — DO NOT ADD TO PRODUCTION.

Tested 2026-04-25, failed every live threshold:
  PF 0.75 (need >= 1.5)
  Sharpe -1.68 (need >= 1.0)
  MAR -0.43 (need >= 0.5)
  Monte Carlo P(profit) 0.8% (need >= 85%)
  Net P&L over 2yr USD_CAD: -$20,090

Per-trade R-expectancy: -0.16R (vs main strategy's +0.44R, so 4x worse).

Kept as a satellite-test template. Future "what about strategy X?" questions
should use this same pattern: build the strategy, reuse backtest_v2's metrics
infrastructure, run on the same 2-yr data, compare against PRD §3.4 thresholds.

See tasks/backtest_amd_2026-04-25.md for the full report.

---

Tests the Inner Circle Trader (ICT) "Power of Three" hypothesis on the same
2-yr OANDA data the main strategy was validated on.

Strategy logic:
  1. Each UTC day, identify Asia session range (00:00-08:00 UTC):
       asia_high = max of high during that 8-hour window
       asia_low  = min of low during that 8-hour window
  2. During London + NY overlap (08:00-17:00 UTC), watch for a "sweep":
       SWEEP_HIGH: candle wicks ABOVE asia_high but body closes BACK INSIDE the range
       SWEEP_LOW:  candle wicks BELOW asia_low but body closes BACK INSIDE the range
  3. On confirmed sweep, enter at NEXT BAR'S OPEN (no look-ahead):
       SWEEP_HIGH -> SELL  (fade the sweep, expect reversion to range)
       SWEEP_LOW  -> BUY
  4. Stop loss: sweep wick extreme + 5 pip buffer
  5. Take profit: opposite Asia extreme (full reversion target)
  6. One trade per day max. Force close at 17:00 UTC if not hit.
  7. Same friction model as backtest_v2: spread + slippage.

Compares against the same 4 live thresholds (PF >= 1.5, Sharpe >= 1.0,
MAR >= 0.5, MC P(profit) >= 85%) used to approve USD_CAD for live.

Usage:
    cd backend
    python -m scripts.backtest_amd --pair USD_CAD --report ../tasks/backtest_amd.md
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Reuse infrastructure from backtest_v2
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backtest_v2 import (  # noqa: E402
    PIP_SIZE,
    SPREAD_PIPS_DEFAULT,
    SLIPPAGE_PIPS,
    Candle,
    BacktestConfig,
    Trade,
    BacktestResult,
    load_candles,
    pip_value_per_unit,
    round_price,
    compute_metrics,
    monte_carlo,
    wilson_ci,
    format_result,
    print_section,
)

# AMD-specific config
ASIA_START_UTC = 0
ASIA_END_UTC = 8       # exclusive
LONDON_START_UTC = 8
EXIT_BY_UTC = 17       # force close at 17:00 UTC if still open
SWEEP_BUFFER_PIPS = 5
MAX_TRADES_PER_DAY = 1
RISK_PCT = Decimal("0.005")  # 0.5% per trade (same as live config)
STARTING_BALANCE = Decimal("100000")
MAX_UNITS = 500_000
MIN_UNITS = 1000


@dataclass
class AsiaRange:
    date: str           # YYYY-MM-DD
    high: Decimal
    low: Decimal
    width_pips: Decimal


@dataclass
class SweepEvent:
    candle_index: int
    candle_time: datetime
    side: str           # "HIGH" or "LOW"
    sweep_extreme: Decimal
    body_close_inside: bool


def compute_asia_ranges(candles: list[Candle]) -> dict[str, AsiaRange]:
    """For each UTC date, compute the Asia session high/low."""
    by_date: dict[str, list[Candle]] = defaultdict(list)
    for c in candles:
        if ASIA_START_UTC <= c.time.hour < ASIA_END_UTC:
            by_date[c.time.date().isoformat()].append(c)

    ranges: dict[str, AsiaRange] = {}
    for date_key, day_candles in by_date.items():
        if not day_candles:
            continue
        high = max(c.high for c in day_candles)
        low = min(c.low for c in day_candles)
        # Need at least one candle to define a range
        ranges[date_key] = AsiaRange(date_key, high, low, Decimal("0"))
    return ranges


def detect_sweep(candle: Candle, asia: AsiaRange, pair: str) -> SweepEvent | None:
    """A sweep is: wick beyond Asia high/low + body close back inside the range.

    Both the open AND close must be inside the range — we want the wick to
    be a clear excursion that got rejected, not a breakout.
    """
    pip = PIP_SIZE[pair]
    body_lo = min(candle.open, candle.close)
    body_hi = max(candle.open, candle.close)

    # Sweep HIGH: wick above asia.high but body inside
    if candle.high > asia.high and body_hi <= asia.high:
        return SweepEvent(
            candle_index=-1,  # filled by caller
            candle_time=candle.time,
            side="HIGH",
            sweep_extreme=candle.high,
            body_close_inside=True,
        )
    # Sweep LOW: wick below asia.low but body inside
    if candle.low < asia.low and body_lo >= asia.low:
        return SweepEvent(
            candle_index=-1,
            candle_time=candle.time,
            side="LOW",
            sweep_extreme=candle.low,
            body_close_inside=True,
        )
    return None


def run_amd_backtest(
    pair: str,
    candles: list[Candle],
    starting_balance: Decimal = STARTING_BALANCE,
    use_friction: bool = True,
    label: str = "amd_baseline",
) -> list[Trade]:
    """Sweep-reversal strategy. One trade per day max, force exit by 17:00 UTC."""
    if len(candles) < 100:
        return []

    asia_ranges = compute_asia_ranges(candles)
    pip = PIP_SIZE[pair]
    spread_pips = SPREAD_PIPS_DEFAULT.get(pair, Decimal("1.5"))

    trades: list[Trade] = []
    balance = starting_balance
    open_trade: Trade | None = None
    trades_today: dict[str, int] = defaultdict(int)

    for i, candle in enumerate(candles):
        date_key = candle.time.date().isoformat()
        hour = candle.time.hour
        asia = asia_ranges.get(date_key)

        # ── Manage open trade ──
        if open_trade is not None:
            sl_hit = False
            tp_hit = False
            exit_price: Decimal | None = None
            exit_reason = ""

            if open_trade.direction == "BUY":
                if candle.low <= open_trade.stop_loss:
                    sl_hit = True
                    exit_price = open_trade.stop_loss
                    exit_reason = "SL_HIT"
                elif candle.high >= open_trade.take_profit:
                    tp_hit = True
                    exit_price = open_trade.take_profit
                    exit_reason = "TP_HIT"
            else:  # SELL
                if candle.high >= open_trade.stop_loss:
                    sl_hit = True
                    exit_price = open_trade.stop_loss
                    exit_reason = "SL_HIT"
                elif candle.low <= open_trade.take_profit:
                    tp_hit = True
                    exit_price = open_trade.take_profit
                    exit_reason = "TP_HIT"

            # Force close at end of trading window
            if not (sl_hit or tp_hit) and hour >= EXIT_BY_UTC:
                exit_price = candle.close
                exit_reason = "EOD_CLOSE"
                sl_hit = True  # treat as exit

            if exit_price is not None:
                _close_trade(open_trade, exit_price, candle.time, exit_reason,
                             pair, spread_pips, use_friction)
                trades.append(open_trade)
                balance += open_trade.pnl_usd
                open_trade = None
                continue
            continue  # already in trade, skip signal generation

        # ── Skip if outside London/NY window or no Asia range yet ──
        if not (LONDON_START_UTC <= hour < EXIT_BY_UTC):
            continue
        if asia is None:
            continue
        if trades_today[date_key] >= MAX_TRADES_PER_DAY:
            continue

        # ── Detect sweep on this candle ──
        sweep = detect_sweep(candle, asia, pair)
        if sweep is None:
            continue
        if i + 1 >= len(candles):
            continue  # no next bar to enter on

        # ── Enter at NEXT BAR'S OPEN (no look-ahead) ──
        next_candle = candles[i + 1]
        entry_price = next_candle.open

        if sweep.side == "HIGH":
            direction = "SELL"
            stop_loss = sweep.sweep_extreme + (Decimal(str(SWEEP_BUFFER_PIPS)) * pip)
            take_profit = asia.low
        else:
            direction = "BUY"
            stop_loss = sweep.sweep_extreme - (Decimal(str(SWEEP_BUFFER_PIPS)) * pip)
            take_profit = asia.high

        # Apply slippage on entry
        if use_friction:
            slip = SLIPPAGE_PIPS * pip
            entry_price = entry_price + slip if direction == "BUY" else entry_price - slip

        # Position sizing
        sl_distance = abs(entry_price - stop_loss)
        sl_pips = sl_distance / pip
        if sl_pips < 5:
            continue  # absurdly tight, skip
        risk_usd = balance * RISK_PCT
        pv = pip_value_per_unit(pair, entry_price)
        if pv == 0:
            continue
        units = int(risk_usd / (sl_pips * pv))
        units = min(units, MAX_UNITS)
        if units < MIN_UNITS:
            continue

        # Reject if R:R below 1.0 (sweep is too far from opposite extreme)
        reward = abs(take_profit - entry_price)
        if reward / sl_distance < Decimal("1.0"):
            continue

        open_trade = Trade(
            pair=pair,
            direction=direction,
            entry_price=round_price(entry_price, pair),
            stop_loss=round_price(stop_loss, pair),
            entry_time=next_candle.time,
            units=units,
            confidence_score=0.65,  # placeholder — AMD has no scoring
            strategies_fired=f"AMD_SWEEP_{sweep.side}",
            regime="AMD",
        )
        open_trade.take_profit = round_price(take_profit, pair)  # set TP explicitly
        trades_today[date_key] += 1

    # Close any still-open trade at last close
    if open_trade is not None:
        last = candles[-1]
        _close_trade(open_trade, last.close, last.time, "BACKTEST_END",
                     pair, spread_pips, use_friction)
        trades.append(open_trade)

    return trades


def _close_trade(
    t: Trade,
    exit_price: Decimal,
    exit_time: datetime,
    exit_reason: str,
    pair: str,
    spread_pips: Decimal,
    use_friction: bool,
) -> None:
    pip = PIP_SIZE[pair]
    if use_friction:
        slip = SLIPPAGE_PIPS * pip
        exit_price = exit_price - slip if t.direction == "BUY" else exit_price + slip

    if t.direction == "BUY":
        pnl_pips = (exit_price - t.entry_price) / pip
    else:
        pnl_pips = (t.entry_price - exit_price) / pip

    pv = pip_value_per_unit(pair, exit_price)
    pnl_usd = pnl_pips * t.units * pv

    spread_cost = Decimal("0")
    if use_friction:
        spread_cost = spread_pips * t.units * pv
        pnl_usd = pnl_usd - spread_cost

    t.exit_price = exit_price
    t.exit_time = exit_time
    t.exit_reason = exit_reason
    t.pnl_pips = pnl_pips
    t.pnl_usd = pnl_usd
    t.spread_cost_usd = spread_cost
    t.outcome = "WIN" if pnl_usd > 1 else ("LOSS" if pnl_usd < -1 else "BREAKEVEN")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AMD sweep-reversal backtest")
    p.add_argument("--pair", action="append",
                   help="Pair (repeatable). Default: USD_CAD")
    p.add_argument("--starting-balance", type=Decimal, default=STARTING_BALANCE)
    p.add_argument("--monte-carlo", type=int, default=10_000,
                   help="Monte Carlo bootstrap samples (0 to skip)")
    p.add_argument("--no-friction", action="store_true",
                   help="Disable spread + slippage modeling (cheating mode)")
    p.add_argument("--report", type=Path, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    pairs = args.pair if args.pair else ["USD_CAD"]
    use_friction = not args.no_friction

    print(f"AMD SWEEP-REVERSAL BACKTEST")
    print(f"  Pairs: {pairs}")
    print(f"  Starting balance: ${args.starting_balance:,}")
    print(f"  Friction: {'enabled' if use_friction else 'DISABLED (cheating)'}")
    print(f"  Asia: {ASIA_START_UTC:02d}-{ASIA_END_UTC:02d} UTC")
    print(f"  Trade window: {LONDON_START_UTC:02d}-{EXIT_BY_UTC:02d} UTC")
    print(f"  Risk per trade: {float(RISK_PCT)*100:.2f}%")
    print(f"  Sweep buffer: {SWEEP_BUFFER_PIPS} pips beyond extreme")
    print(f"  TP: opposite Asia extreme | SL: sweep wick + buffer")

    all_results: dict[str, BacktestResult] = {}
    mc_results: dict[str, dict] = {}

    for pair in pairs:
        print_section(f"BACKTESTING {pair} — AMD SWEEP-REVERSAL")
        candles = load_candles(pair, "H1")
        if len(candles) < 100:
            print(f"  Not enough data ({len(candles)} candles)")
            continue
        print(f"  Loaded {len(candles)} H1 candles "
              f"({candles[0].time.date()} to {candles[-1].time.date()})")

        trades = run_amd_backtest(pair, candles, args.starting_balance, use_friction)
        result = compute_metrics(pair, "amd_baseline", trades, args.starting_balance)
        all_results[pair] = result
        print(format_result(result))

        # Exit reason breakdown
        from collections import Counter
        exits = Counter(t.exit_reason for t in trades)
        print(f"  Exit reasons:")
        for reason, count in exits.most_common():
            wins = sum(1 for t in trades if t.exit_reason == reason and t.outcome == "WIN")
            pnl = sum(t.pnl_usd for t in trades if t.exit_reason == reason)
            print(f"    {reason}: {count} ({wins} W) P&L ${pnl:+,.2f}")

        # Sweep side breakdown
        side_high = [t for t in trades if "HIGH" in t.strategies_fired]
        side_low = [t for t in trades if "LOW" in t.strategies_fired]
        if side_high:
            wins = sum(1 for t in side_high if t.outcome == "WIN")
            pnl = sum(t.pnl_usd for t in side_high)
            print(f"  SWEEP_HIGH (SELL): {len(side_high)} ({wins} W, "
                  f"WR {wins/len(side_high)*100:.1f}%) P&L ${pnl:+,.2f}")
        if side_low:
            wins = sum(1 for t in side_low if t.outcome == "WIN")
            pnl = sum(t.pnl_usd for t in side_low)
            print(f"  SWEEP_LOW (BUY):   {len(side_low)} ({wins} W, "
                  f"WR {wins/len(side_low)*100:.1f}%) P&L ${pnl:+,.2f}")

        if args.monte_carlo > 0 and trades:
            mc = monte_carlo(trades, args.starting_balance, args.monte_carlo)
            mc_results[pair] = mc
            print(f"  Monte Carlo (n={args.monte_carlo}):")
            print(f"    P(profit) = {mc['p_profit']*100:.1f}%")
            print(f"    DD pcts: 5%={mc['p5_dd_pct']:.1f}%  "
                  f"50%={mc['median_dd_pct']:.1f}%  95%={mc['p95_dd_pct']:.1f}%")

    if args.report:
        write_report(args.report, all_results, mc_results, use_friction)
        print(f"\nReport written to {args.report}")

    return 0


def write_report(
    path: Path,
    results: dict[str, BacktestResult],
    mc: dict[str, dict],
    use_friction: bool,
) -> None:
    lines = [
        f"# AMD Sweep-Reversal Backtest — {datetime.now(timezone.utc).date()}\n",
        "**Strategy:** Asia (00-08 UTC) builds range. London/NY (08-17 UTC) sweeps Asia high/low. Enter against the sweep at next bar's open. SL = sweep wick + 5 pip buffer. TP = opposite Asia extreme. One trade per UTC day max. Force exit at 17:00 UTC.\n",
        f"**Friction:** {'ON (1.5p USD_CAD spread, 0.5p slippage)' if use_friction else 'OFF (cheating mode)'}\n",
        "\n## Live thresholds (PRD §3.4) for comparison\n",
        "- Profit factor ≥ 1.5\n- Sharpe (annualized) ≥ 1.0\n- MAR ≥ 0.5\n- Monte Carlo P(profit) ≥ 85%\n",
        "\n## Per-pair results\n",
    ]
    for pair, r in results.items():
        passes = (
            r.profit_factor >= 1.5 and r.sharpe_annualized >= 1.0
            and r.mar >= 0.5 and mc.get(pair, {}).get("p_profit", 0) >= 0.85
        )
        verdict = "✅ PASSES live thresholds" if passes else "🔴 FAILS one or more live thresholds"
        lines.append(f"\n### {pair} — {verdict}\n")
        lines.append("```\n" + format_result(r) + "```\n")
        if pair in mc:
            m = mc[pair]
            lines.append(f"\n**Monte Carlo:** P(profit)={m['p_profit']*100:.1f}%, "
                         f"5%-DD={m['p5_dd_pct']:.1f}%, 95%-DD={m['p95_dd_pct']:.1f}%\n")
    lines.append("\n## Methodology notes\n")
    lines.append("- Sweep = candle wick BEYOND Asia extreme + body close BACK INSIDE range.\n")
    lines.append("- Entry at NEXT BAR'S OPEN to avoid look-ahead bias.\n")
    lines.append("- Reuses `backtest_v2.py` data loading, metrics, friction model, Wilson CI.\n")
    lines.append("- This is a SATELLITE TEST — not a replacement for the main strategy.\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
