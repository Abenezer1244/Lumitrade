"""
Audit 2026-06-25 (a3): reconciler-closed P&L must reach the daily/weekly
loss-limit counters.

The position monitor books its own closes, but a trade closed SOLELY by
reconciliation was invisible to the limits — the engine could trade past its
daily loss limit. StateManager._book_reconciled_pnl closes that gap,
period-aware and excluding shadow trades.
"""

from datetime import datetime, timedelta, timezone

import pytest

from lumitrade.state.manager import StateManager


def _sm() -> StateManager:
    sm = StateManager.__new__(StateManager)
    sm._state = {"daily_pnl": "0", "weekly_pnl": "0"}
    return sm


def test_books_current_period_live_ghosts_excludes_shadow():
    sm = _sm()
    now = datetime.now(timezone.utc).isoformat()
    sm._book_reconciled_pnl([
        {"pnl_usd": "-10.00", "closed_at": now, "mode": "LIVE"},
        {"pnl_usd": "5.00", "closed_at": now, "mode": "LIVE"},
        {"pnl_usd": "-100.00", "closed_at": now, "mode": "PAPER_SHADOW"},  # excluded
    ])
    assert sm._state["daily_pnl"] == "-5.00"   # -10 + 5
    assert sm._state["weekly_pnl"] == "-5.00"


def test_ignores_prior_period_close():
    sm = _sm()
    old = "2020-01-01T00:00:00+00:00"
    sm._book_reconciled_pnl([{"pnl_usd": "-50.00", "closed_at": old, "mode": "LIVE"}])
    # A close from a prior day/week must not be attributed to the current period.
    assert sm._state["daily_pnl"] == "0"
    assert sm._state["weekly_pnl"] == "0"


def test_unknown_close_time_counts_conservatively():
    sm = _sm()
    # No/blank closed_at -> count in current period (a loss escaping the limit
    # is worse than a conservative limit).
    sm._book_reconciled_pnl([{"pnl_usd": "-7.00", "closed_at": "", "mode": "LIVE"}])
    assert sm._state["daily_pnl"] == "-7.00"
    assert sm._state["weekly_pnl"] == "-7.00"


def test_zero_and_empty_are_noops():
    sm = _sm()
    sm._book_reconciled_pnl([])
    sm._book_reconciled_pnl([{"pnl_usd": "0", "closed_at": "", "mode": "LIVE"}])
    assert sm._state["daily_pnl"] == "0"
    assert sm._state["weekly_pnl"] == "0"


def test_daily_only_when_same_day_but_weekly_same_week():
    sm = _sm()
    # A close earlier THIS week but on a prior day: not in daily, but in weekly.
    now = datetime.now(timezone.utc)
    # Pick a day earlier in the same ISO week if possible; else skip the daily side.
    if now.weekday() == 0:
        pytest.skip("Monday: no earlier same-week day to test")
    earlier_same_week = (now - timedelta(days=1)).isoformat()
    sm._book_reconciled_pnl([{"pnl_usd": "-12.00", "closed_at": earlier_same_week, "mode": "LIVE"}])
    assert sm._state["daily_pnl"] == "0"        # not today
    assert sm._state["weekly_pnl"] == "-12.00"  # same week
