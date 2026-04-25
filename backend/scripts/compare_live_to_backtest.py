"""
Compare live trade performance against backtest predictions.

Used by .github/workflows/post-live-validation.yml. Reads trades from Supabase
since a given cutover date, computes live profit factor / Sharpe / expectancy
on a single pair, and writes a Markdown report comparing to the backtest
predictions passed as CLI args.

Verdict heuristics:
  CONFIRMED — live PF / expectancy within 30% of backtest
  DRIFTING  — within 30-50%
  DIVERGED  — live PF < 0.7x backtest PF (or expectancy negative)

Usage:
    python -m scripts.compare_live_to_backtest \\
        --since 2026-04-25 --pair USD_CAD \\
        --bt-pf 1.96 --bt-sharpe 1.76 --bt-expectancy 118.25 --bt-wr 0.543 \\
        --bt-source tasks/backtest_2026Q2_results.md \\
        --report tasks/live_vs_backtest_2026-05-16.md

Prints `VERDICT: <CONFIRMED|DRIFTING|DIVERGED|INSUFFICIENT_SAMPLE>` as the
last line of stdout for the CI workflow to grep.
"""
from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv  # type: ignore
from supabase import create_client  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def D(v) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def fetch_trades_since(since_date: str, pair: str) -> list[dict]:
    """Pull all trades for `pair` opened on or after `since_date` (ISO YYYY-MM-DD)."""
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    trades: list[dict] = []
    page_size = 1000
    start = 0
    while True:
        resp = (
            sb.table("trades")
            .select("*")
            .eq("pair", pair)
            .gte("opened_at", f"{since_date}T00:00:00+00:00")
            .order("opened_at", desc=False)
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        trades.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return trades


def compute_live_metrics(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    if not closed:
        return {
            "trade_count": len(trades),
            "closed_count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": Decimal("0"),
            "total_pnl": Decimal("0"),
            "avg_win": Decimal("0"),
            "avg_loss": Decimal("0"),
            "sharpe": 0.0,
        }

    wins = [t for t in closed if D(t.get("pnl_usd")) > Decimal("1")]
    losses = [t for t in closed if D(t.get("pnl_usd")) < Decimal("-1")]
    win_pnl = sum(D(t.get("pnl_usd")) for t in wins) or Decimal("0")
    loss_pnl = sum(D(t.get("pnl_usd")) for t in losses) or Decimal("0")
    total_pnl = sum(D(t.get("pnl_usd")) for t in closed) or Decimal("0")
    win_rate = len(wins) / len(closed) if closed else 0.0
    pf = float(abs(win_pnl / loss_pnl)) if loss_pnl != 0 else (999.0 if win_pnl > 0 else 0.0)
    expectancy = total_pnl / len(closed) if closed else Decimal("0")
    avg_win = win_pnl / len(wins) if wins else Decimal("0")
    avg_loss = loss_pnl / len(losses) if losses else Decimal("0")

    # Per-trade Sharpe-like (annualized assuming ~252 trades/yr is meaningless on small samples)
    pnls = [float(D(t.get("pnl_usd"))) for t in closed]
    sharpe = 0.0
    if len(pnls) >= 2:
        mean_p = statistics.mean(pnls)
        std_p = statistics.stdev(pnls)
        if std_p > 0:
            sharpe = mean_p / std_p * math.sqrt(252)

    return {
        "trade_count": len(trades),
        "closed_count": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "profit_factor": pf,
        "expectancy": expectancy,
        "total_pnl": total_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "sharpe": sharpe,
    }


def render_report(
    pair: str,
    since: str,
    live: dict,
    bt: dict,
    verdict: str,
    bt_source: str,
) -> str:
    pf_ratio = (live["profit_factor"] / bt["pf"]) if bt["pf"] > 0 else 0.0
    expectancy_ratio = (
        float(live["expectancy"] / Decimal(str(bt["expectancy"])))
        if bt["expectancy"] != 0 else 0.0
    )

    lines = [
        f"# Post-Live Validation — {pair} since {since}\n",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}\n",
        f"**Backtest source:** `{bt_source}`\n",
        "\n## Sample\n",
        f"- Total trades opened: **{live['trade_count']}**\n",
        f"- Trades closed: **{live['closed_count']}**\n",
        f"- Wins / Losses: {live['wins']} / {live['losses']}\n",
        "\n## Live vs Backtest\n",
        "| Metric | Backtest | Live | Δ | Ratio |\n",
        "|---|---|---|---|---|\n",
        f"| Profit factor | {bt['pf']:.2f} | {live['profit_factor']:.2f} | "
        f"{live['profit_factor'] - bt['pf']:+.2f} | {pf_ratio:.2f}× |\n",
        f"| Win rate | {bt['wr']*100:.1f}% | {live['win_rate']*100:.1f}% | "
        f"{(live['win_rate'] - bt['wr'])*100:+.1f}pp | — |\n",
        f"| Expectancy / trade | ${bt['expectancy']:+.2f} | ${live['expectancy']:+.2f} | "
        f"${float(live['expectancy']) - bt['expectancy']:+.2f} | {expectancy_ratio:.2f}× |\n",
        f"| Sharpe (annualized) | {bt['sharpe']:.2f} | {live['sharpe']:.2f} | "
        f"{live['sharpe'] - bt['sharpe']:+.2f} | — |\n",
        f"| Total P&L | — | ${live['total_pnl']:+,.2f} | — | — |\n",
        "\n## Verdict\n",
        f"### `{verdict}`\n\n",
    ]

    if verdict == "INSUFFICIENT_SAMPLE":
        lines.append("Fewer than 5 closed trades since cutover. Wait for more data before drawing conclusions.\n")
    elif verdict == "CONFIRMED":
        lines.append("Live performance is within 30% of backtest predictions on profit factor and expectancy. The 2-yr backtest is a fair predictor of live behavior so far.\n")
    elif verdict == "DRIFTING":
        lines.append("Live performance is between 30%-50% below backtest. Not yet a regime change but worth watching. Review:\n")
        lines.append("- Is the live filter stack identical to what was backtested?\n")
        lines.append("- Has spread / slippage materially exceeded the friction model assumptions (1.5p USD_CAD spread, 0.5p slippage)?\n")
        lines.append("- Is the regime distribution since cutover unusual (e.g. a single high-ATR event)?\n")
    elif verdict == "DIVERGED":
        lines.append("🔴 **Live profit factor is below 0.7× backtest predictions.** Consider:\n")
        lines.append("- Pause LIVE mode and revert to PAPER until cause is identified\n")
        lines.append("- Re-run the backtest on the latest 2-year window to check for regime drift\n")
        lines.append("- Verify production filter stack against `backend/scripts/backtest_v2.py` defaults\n")
        lines.append("- Audit any production changes since the cutover\n")

    lines.append("\n---\n")
    lines.append("Generated by `backend/scripts/compare_live_to_backtest.py`.\n")
    return "".join(lines)


def decide_verdict(live: dict, bt: dict) -> str:
    if live["closed_count"] < 5:
        return "INSUFFICIENT_SAMPLE"
    if live["profit_factor"] < bt["pf"] * 0.7:
        return "DIVERGED"
    if live["expectancy"] < 0:
        return "DIVERGED"
    pf_ratio = live["profit_factor"] / bt["pf"] if bt["pf"] > 0 else 0
    expectancy_ratio = (
        float(live["expectancy"]) / bt["expectancy"] if bt["expectancy"] != 0 else 0
    )
    if pf_ratio >= 0.7 and expectancy_ratio >= 0.7:
        return "CONFIRMED"
    if pf_ratio >= 0.5 and expectancy_ratio >= 0.5:
        return "DRIFTING"
    return "DIVERGED"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--since", required=True, help="ISO date (YYYY-MM-DD)")
    p.add_argument("--pair", required=True)
    p.add_argument("--bt-pf", type=float, required=True)
    p.add_argument("--bt-sharpe", type=float, required=True)
    p.add_argument("--bt-expectancy", type=float, required=True)
    p.add_argument("--bt-wr", type=float, required=True, help="Backtest win rate as 0.0-1.0")
    p.add_argument("--bt-source", default="(unknown)")
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()

    print(f"Fetching trades since {args.since} for {args.pair}…")
    trades = fetch_trades_since(args.since, args.pair)
    print(f"Fetched {len(trades)} trades")

    live = compute_live_metrics(trades)
    bt = {
        "pf": args.bt_pf,
        "sharpe": args.bt_sharpe,
        "expectancy": args.bt_expectancy,
        "wr": args.bt_wr,
    }

    print(f"Live PF: {live['profit_factor']:.2f}, Sharpe: {live['sharpe']:.2f}, "
          f"Expectancy: ${live['expectancy']:+.2f}, WR: {live['win_rate']*100:.1f}%")
    print(f"Backtest PF: {bt['pf']:.2f}, Sharpe: {bt['sharpe']:.2f}, "
          f"Expectancy: ${bt['expectancy']:+.2f}, WR: {bt['wr']*100:.1f}%")

    verdict = decide_verdict(live, bt)
    report = render_report(args.pair, args.since, live, bt, verdict, args.bt_source)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"Report written to {args.report}")
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
