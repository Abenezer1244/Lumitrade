"""Trade audit script - pulls real trade data from Supabase and produces
a comprehensive performance audit covering what is working vs what needs
improvement.

Run: python backend/scripts/trade_audit.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def D(v) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def fetch_all_trades() -> list[dict]:
    trades: list[dict] = []
    page_size = 1000
    start = 0
    while True:
        resp = (
            sb.table("trades")
            .select("*")
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


def parse_dt(v) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None


def classify_session(hour: int) -> str:
    if 0 <= hour < 8:
        return "ASIAN"
    if 8 <= hour < 13:
        return "LONDON"
    if 13 <= hour < 17:
        return "NY_OVERLAP"
    return "NY_LATE"


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def summarize(group: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for key, tr in group.items():
        wins = sum(1 for t in tr if t.get("outcome") == "WIN")
        losses = sum(1 for t in tr if t.get("outcome") == "LOSS")
        total = len(tr)
        pnl = sum((D(t.get("pnl_usd")) for t in tr), Decimal("0"))
        pips = sum((D(t.get("pnl_pips")) for t in tr), Decimal("0"))
        wr = (Decimal(wins) / Decimal(total) * 100) if total else Decimal("0")
        rows.append(
            {
                "key": key,
                "wins": wins,
                "losses": losses,
                "total": total,
                "wr": float(wr),
                "pnl_usd": float(pnl),
                "pnl_pips": float(pips),
            }
        )
    rows.sort(key=lambda r: r["pnl_usd"], reverse=True)
    return rows


def print_table(rows: list[dict], key_label: str) -> None:
    header = f"{key_label:<22} {'Trades':>7} {'Wins':>5} {'Loss':>5} {'WR%':>6} {'P&L $':>11} {'Pips':>8}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['key']:<22} {r['total']:>7} {r['wins']:>5} {r['losses']:>5} "
            f"{r['wr']:>6.1f} {r['pnl_usd']:>11.2f} {r['pnl_pips']:>8.1f}"
        )


def main() -> None:
    trades = fetch_all_trades()
    print(f"Fetched {len(trades)} trades from Supabase")
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    opened = [t for t in trades if t.get("status") == "OPEN"]

    # Overall
    section("OVERALL PERFORMANCE")
    wins = [t for t in closed if t.get("outcome") == "WIN"]
    losses = [t for t in closed if t.get("outcome") == "LOSS"]
    breakeven = [t for t in closed if t.get("outcome") not in ("WIN", "LOSS")]
    total_pnl = sum((D(t.get("pnl_usd")) for t in closed), Decimal("0"))
    total_pips = sum((D(t.get("pnl_pips")) for t in closed), Decimal("0"))
    gross_win = sum((D(t.get("pnl_usd")) for t in wins), Decimal("0"))
    gross_loss = abs(sum((D(t.get("pnl_usd")) for t in losses), Decimal("0")))
    wr = (Decimal(len(wins)) / Decimal(len(closed)) * 100) if closed else Decimal("0")
    pf = (gross_win / gross_loss) if gross_loss > 0 else Decimal("0")
    expectancy = (total_pnl / Decimal(len(closed))) if closed else Decimal("0")
    avg_win = (gross_win / Decimal(len(wins))) if wins else Decimal("0")
    avg_loss = (gross_loss / Decimal(len(losses))) if losses else Decimal("0")

    print(f"Open trades:      {len(opened)}")
    print(f"Closed trades:    {len(closed)}")
    print(f"  Wins:           {len(wins)}")
    print(f"  Losses:         {len(losses)}")
    print(f"  Breakeven:      {len(breakeven)}")
    print(f"Win rate:         {wr:.2f}%")
    print(f"Total P&L:        ${total_pnl:,.2f}")
    print(f"Total pips:       {total_pips:,.1f}")
    print(f"Profit factor:    {pf:.3f}")
    print(f"Expectancy:       ${expectancy:,.2f} per trade")
    print(f"Avg win:          ${avg_win:,.2f}")
    print(f"Avg loss:         ${avg_loss:,.2f}")
    if avg_loss > 0:
        print(f"Win/Loss ratio:   {avg_win / avg_loss:.2f}")

    # Direction
    section("BY DIRECTION")
    by_dir = defaultdict(list)
    for t in closed:
        by_dir[t.get("direction", "?")].append(t)
    print_table(summarize(by_dir), "Direction")

    # Pair
    section("BY PAIR")
    by_pair = defaultdict(list)
    for t in closed:
        by_pair[t.get("pair", "?")].append(t)
    print_table(summarize(by_pair), "Pair")

    # Pair + direction
    section("BY PAIR + DIRECTION")
    by_pd = defaultdict(list)
    for t in closed:
        by_pd[f"{t.get('pair','?')} {t.get('direction','?')}"].append(t)
    print_table(summarize(by_pd), "Pair Dir")

    # Session
    section("BY SESSION (opened_at UTC)")
    by_sess = defaultdict(list)
    for t in closed:
        dt = parse_dt(t.get("opened_at"))
        if dt:
            by_sess[classify_session(dt.hour)].append(t)
    print_table(summarize(by_sess), "Session")

    # Hour-by-hour
    section("BY HOUR OF DAY (UTC)")
    by_hour = defaultdict(list)
    for t in closed:
        dt = parse_dt(t.get("opened_at"))
        if dt:
            by_hour[f"{dt.hour:02d}:00"].append(t)
    rows = []
    for k in sorted(by_hour.keys()):
        rows.append(summarize({k: by_hour[k]})[0])
    print_table(rows, "Hour")

    # Weekday
    section("BY WEEKDAY")
    wd_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    by_wd = defaultdict(list)
    for t in closed:
        dt = parse_dt(t.get("opened_at"))
        if dt:
            by_wd[wd_names[dt.weekday()]].append(t)
    rows = []
    for k in wd_names:
        if k in by_wd:
            rows.append(summarize({k: by_wd[k]})[0])
    print_table(rows, "Weekday")

    # Confidence buckets
    section("BY CONFIDENCE BUCKET")
    buckets = [
        ("0.00-0.65", Decimal("0"), Decimal("0.65")),
        ("0.65-0.70", Decimal("0.65"), Decimal("0.70")),
        ("0.70-0.80", Decimal("0.70"), Decimal("0.80")),
        ("0.80-0.90", Decimal("0.80"), Decimal("0.90")),
        ("0.90-1.00", Decimal("0.90"), Decimal("1.01")),
    ]
    by_conf = defaultdict(list)
    for t in closed:
        c = D(t.get("confidence_score") or t.get("confidence"))
        if c > Decimal("1"):
            c = c / Decimal("100")
        for label, lo, hi in buckets:
            if lo <= c < hi:
                by_conf[label].append(t)
                break
    rows = []
    for label, _, _ in buckets:
        if label in by_conf:
            rows.append(summarize({label: by_conf[label]})[0])
    print_table(rows, "Confidence")

    # Exit reason
    section("BY EXIT REASON")
    by_exit = defaultdict(list)
    for t in closed:
        key = t.get("exit_reason") or t.get("close_reason") or "UNKNOWN"
        by_exit[key].append(t)
    print_table(summarize(by_exit), "Exit")

    # Hold time
    section("HOLD TIME ANALYSIS")
    hold_buckets = defaultdict(list)
    for t in closed:
        o = parse_dt(t.get("opened_at"))
        c = parse_dt(t.get("closed_at"))
        if o and c:
            minutes = (c - o).total_seconds() / 60.0
            if minutes < 30:
                k = "0-30min"
            elif minutes < 120:
                k = "30min-2h"
            elif minutes < 360:
                k = "2h-6h"
            elif minutes < 1440:
                k = "6h-24h"
            else:
                k = "24h+"
            hold_buckets[k].append(t)
    order = ["0-30min", "30min-2h", "2h-6h", "6h-24h", "24h+"]
    rows = []
    for k in order:
        if k in hold_buckets:
            rows.append(summarize({k: hold_buckets[k]})[0])
    print_table(rows, "Hold time")

    # SL/TP distances
    section("STOP LOSS & TAKE PROFIT DISTANCES (in pips)")
    sl_dists = []
    tp_dists = []
    rr_ratios = []
    for t in closed:
        entry = D(t.get("entry_price"))
        sl = D(t.get("stop_loss") or t.get("sl"))
        tp = D(t.get("take_profit") or t.get("tp"))
        pair = t.get("pair", "")
        if entry == 0 or sl == 0:
            continue
        pip_mult = Decimal("100") if "JPY" in pair else Decimal("10000")
        if pair == "XAU_USD":
            pip_mult = Decimal("10")
        sl_pips = abs((entry - sl) * pip_mult)
        sl_dists.append(sl_pips)
        if tp > 0:
            tp_pips = abs((tp - entry) * pip_mult)
            tp_dists.append(tp_pips)
            if sl_pips > 0:
                rr_ratios.append(tp_pips / sl_pips)

    def stats(xs: list[Decimal]) -> str:
        if not xs:
            return "n/a"
        xs = sorted(xs)
        n = len(xs)
        avg = sum(xs) / n
        med = xs[n // 2]
        return f"n={n}  min={xs[0]:.1f}  med={med:.1f}  mean={avg:.1f}  max={xs[-1]:.1f}"

    print(f"SL distance pips: {stats(sl_dists)}")
    print(f"TP distance pips: {stats(tp_dists)}")
    print(f"R:R ratio:        {stats(rr_ratios)}")

    # Most recent 20 trades
    section("LAST 20 CLOSED TRADES")
    recent = sorted(
        closed, key=lambda t: parse_dt(t.get("closed_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True
    )[:20]
    print(f"{'When':<20} {'Pair':<9} {'Dir':<5} {'Conf':<6} {'Outcome':<9} {'P&L $':>10} {'Pips':>8} {'Exit':<12}")
    print("-" * 90)
    for t in recent:
        dt = parse_dt(t.get("closed_at"))
        when = dt.strftime("%Y-%m-%d %H:%M") if dt else "?"
        conf = D(t.get("confidence_score") or t.get("confidence"))
        if conf > Decimal("1"):
            conf = conf / Decimal("100")
        print(
            f"{when:<20} {t.get('pair','?'):<9} {t.get('direction','?'):<5} "
            f"{float(conf):<6.2f} {t.get('outcome','?'):<9} "
            f"{float(D(t.get('pnl_usd'))):>10.2f} {float(D(t.get('pnl_pips'))):>8.1f} "
            f"{(t.get('exit_reason') or '')[:12]:<12}"
        )

    # Open trades
    if opened:
        section(f"CURRENTLY OPEN TRADES ({len(opened)})")
        print(f"{'Opened':<20} {'Pair':<9} {'Dir':<5} {'Conf':<6} {'Entry':>10} {'SL':>10} {'TP':>10}")
        for t in opened:
            dt = parse_dt(t.get("opened_at"))
            when = dt.strftime("%Y-%m-%d %H:%M") if dt else "?"
            conf = D(t.get("confidence_score") or t.get("confidence"))
            if conf > Decimal("1"):
                conf = conf / Decimal("100")
            print(
                f"{when:<20} {t.get('pair','?'):<9} {t.get('direction','?'):<5} "
                f"{float(conf):<6.2f} {float(D(t.get('entry_price'))):>10.5f} "
                f"{float(D(t.get('stop_loss'))):>10.5f} {float(D(t.get('take_profit'))):>10.5f}"
            )

    # Equity curve / drawdown
    section("EQUITY CURVE & DRAWDOWN")
    sorted_closed = sorted(closed, key=lambda t: parse_dt(t.get("closed_at")) or datetime.min.replace(tzinfo=timezone.utc))
    running = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")
    max_dd_dt = None
    curr_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    last_outcome = None
    best_day = defaultdict(lambda: Decimal("0"))
    for t in sorted_closed:
        pnl = D(t.get("pnl_usd"))
        running += pnl
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd
            max_dd_dt = parse_dt(t.get("closed_at"))
        oc = t.get("outcome")
        if oc == last_outcome:
            curr_streak += 1
        else:
            curr_streak = 1
            last_outcome = oc
        if oc == "WIN":
            max_win_streak = max(max_win_streak, curr_streak)
        elif oc == "LOSS":
            max_loss_streak = max(max_loss_streak, curr_streak)
        dt = parse_dt(t.get("closed_at"))
        if dt:
            best_day[dt.date().isoformat()] += pnl

    print(f"Max drawdown:     ${max_dd:,.2f}  ({max_dd_dt})")
    print(f"Max win streak:   {max_win_streak}")
    print(f"Max loss streak:  {max_loss_streak}")
    print(f"Final cumulative: ${running:,.2f}")
    print(f"Peak cumulative:  ${peak:,.2f}")

    # Best / worst days
    sorted_days = sorted(best_day.items(), key=lambda x: x[1], reverse=True)
    print("\nTop 5 best days:")
    for d, p in sorted_days[:5]:
        print(f"  {d}: ${float(p):,.2f}")
    print("\nTop 5 worst days:")
    for d, p in sorted_days[-5:]:
        print(f"  {d}: ${float(p):,.2f}")

    # Trading lessons
    section("TRADING LESSONS / MEMORY RULES")
    try:
        lessons = sb.table("trading_lessons").select("*").execute().data or []
        print(f"Total lessons: {len(lessons)}")
        for le in sorted(lessons, key=lambda x: x.get("rule_type", ""), reverse=False):
            print(
                f"  [{le.get('rule_type','?'):<7}] {le.get('pattern','?')}: "
                f"{le.get('sample_size','?')} trades, "
                f"WR {le.get('win_rate','?')}"
            )
    except Exception as e:
        print(f"  (trading_lessons table not accessible: {e})")

    # Dump raw summary for agent consumption
    out = {
        "total_closed": len(closed),
        "total_open": len(opened),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": float(wr),
        "total_pnl_usd": float(total_pnl),
        "profit_factor": float(pf),
        "avg_win_usd": float(avg_win),
        "avg_loss_usd": float(avg_loss),
        "max_drawdown_usd": float(max_dd),
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "by_pair": {k: summarize({k: v})[0] for k, v in by_pair.items()},
        "by_direction": {k: summarize({k: v})[0] for k, v in by_dir.items()},
        "by_session": {k: summarize({k: v})[0] for k, v in by_sess.items()},
        "by_pair_dir": {k: summarize({k: v})[0] for k, v in by_pd.items()},
    }
    Path("tasks/trade_audit_summary.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nSummary dumped to tasks/trade_audit_summary.json")


if __name__ == "__main__":
    main()
