"""Time utility tests.

Guards session_label_for_lesson boundaries so lesson_analyzer and
execution_engine stay in lockstep — a mismatch would silently route
trades to the wrong session bucket in trading_lessons.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumitrade.utils.time_utils import parse_iso_utc, session_label_for_lesson


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


class TestParseIsoUtc:
    """parse_iso_utc consolidates the s.replace('Z','+00:00') idiom that
    was duplicated across analytics, ai_brain, and data_engine paths."""

    def test_z_suffix_is_treated_as_utc(self) -> None:
        dt = parse_iso_utc("2026-04-25T12:34:56Z")
        assert dt is not None
        assert dt.tzinfo is timezone.utc
        assert (dt.year, dt.month, dt.day, dt.hour) == (2026, 4, 25, 12)

    def test_explicit_offset_preserved(self) -> None:
        dt = parse_iso_utc("2026-04-25T12:34:56+00:00")
        assert dt is not None
        assert dt.utcoffset().total_seconds() == 0

    def test_naive_string_promoted_to_utc(self) -> None:
        dt = parse_iso_utc("2026-04-25T12:34:56")
        assert dt is not None
        assert dt.tzinfo is timezone.utc

    def test_passthrough_aware_datetime(self) -> None:
        original = datetime(2026, 4, 25, 12, tzinfo=timezone.utc)
        assert parse_iso_utc(original) is original

    def test_naive_datetime_promoted(self) -> None:
        naive = datetime(2026, 4, 25, 12)
        out = parse_iso_utc(naive)
        assert out is not None and out.tzinfo is timezone.utc

    def test_none_and_empty(self) -> None:
        assert parse_iso_utc(None) is None
        assert parse_iso_utc("") is None

    def test_malformed_returns_none(self) -> None:
        # Callers in analytics/lesson_analyzer rely on None to skip the row.
        assert parse_iso_utc("not-a-timestamp") is None


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
