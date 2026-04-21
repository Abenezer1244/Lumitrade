"""Time utility tests.

Guards session_label_for_lesson boundaries so lesson_analyzer and
execution_engine stay in lockstep — a mismatch would silently route
trades to the wrong session bucket in trading_lessons.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumitrade.utils.time_utils import session_label_for_lesson


@pytest.mark.parametrize(
    "hour,want",
    [
        (0, "ASIAN"),
        (3, "ASIAN"),
        (7, "ASIAN"),
        (8, "LONDON"),
        (10, "LONDON"),
        (12, "LONDON"),
        (13, "NY"),
        (17, "NY"),
        (20, "NY"),
        (21, "OTHER"),
        (23, "OTHER"),
    ],
)
def test_session_label_boundaries(hour: int, want: str) -> None:
    dt = datetime(2026, 4, 15, hour, 30, tzinfo=timezone.utc)
    assert session_label_for_lesson(dt) == want


def test_session_label_matches_lesson_analyzer_ranges() -> None:
    """Contract: time_utils and lesson_analyzer must agree on boundaries.

    If these drift, trades open at hour X get bucketed into session A by
    the engine but session B by the lesson_analyzer — silently breaking
    the feedback loop.
    """
    from lumitrade.ai_brain.lesson_analyzer import SESSION_RANGES

    for name, (lo, hi) in SESSION_RANGES.items():
        for h in range(lo, hi):
            dt = datetime(2026, 4, 15, h, 30, tzinfo=timezone.utc)
            got = session_label_for_lesson(dt)
            assert got == name, (
                f"Hour {h} → {got}, but lesson_analyzer expects {name}"
            )
