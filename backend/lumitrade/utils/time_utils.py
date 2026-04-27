"""
Lumitrade Time Utilities
==========================
Session detection and market hours checking.
All times in UTC. Per BDS Section 10.2.
"""

from datetime import datetime, time, timezone
from typing import Union

from ..core.enums import Session


def parse_iso_utc(value: Union[str, datetime, None]) -> datetime | None:
    """Parse an ISO-8601 timestamp into a timezone-aware datetime.

    Accepts the OANDA / Supabase variants we see in practice:
      - ``"2026-04-25T12:34:56Z"``        (trailing Z)
      - ``"2026-04-25T12:34:56+00:00"``   (explicit offset)
      - ``"2026-04-25T12:34:56"``         (naive, treated as UTC)
      - an existing ``datetime`` instance (returned as-is, naive promoted to UTC)
      - ``None`` / empty string -> ``None``

    Centralises the ``s.replace("Z", "+00:00")`` idiom that was duplicated
    across analytics, ai_brain, data_engine, and execution paths. Returns
    ``None`` instead of raising on malformed input so callers can keep
    their existing "skip on parse failure" semantics.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if not isinstance(value, str) or not value:
        return None
    s = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

# All times in UTC
LONDON_OPEN = time(7, 0)  # 08:00 BST = 07:00 UTC
LONDON_CLOSE = time(16, 0)  # 17:00 BST = 16:00 UTC
NY_OPEN = time(13, 0)  # 09:00 EST = 13:00 UTC (summer)
NY_CLOSE = time(21, 0)  # 17:00 EST = 21:00 UTC
TOKYO_OPEN = time(0, 0)
TOKYO_CLOSE = time(6, 0)


def get_current_session(dt: datetime | None = None) -> Session:
    """Determine which forex trading session is currently active."""
    now = (dt or datetime.now(timezone.utc)).time()

    in_london = LONDON_OPEN <= now < LONDON_CLOSE
    in_ny = NY_OPEN <= now < NY_CLOSE
    in_tokyo = TOKYO_OPEN <= now < TOKYO_CLOSE

    if in_london and in_ny:
        return Session.OVERLAP
    elif in_london:
        return Session.LONDON
    elif in_ny:
        return Session.NEW_YORK
    elif in_tokyo:
        return Session.TOKYO
    return Session.OTHER


def session_label_for_lesson(dt: datetime | None = None) -> str:
    """Return the session label used by lesson_filter and lesson_analyzer.

    Simple UTC-hour buckets, independent of DST:
      ASIAN  : 00-08 UTC
      LONDON : 08-13 UTC
      NY     : 13-21 UTC
      OTHER  : 21-24 UTC

    Matches lesson_analyzer.SESSION_RANGES so round-trip extraction works.
    """
    hour = (dt or datetime.now(timezone.utc)).hour
    if 0 <= hour < 8:
        return "ASIAN"
    if 8 <= hour < 13:
        return "LONDON"
    if 13 <= hour < 21:
        return "NY"
    return "OTHER"


def is_market_open(dt: datetime | None = None) -> bool:
    """Forex market is closed Saturday + most of Sunday."""
    now = dt or datetime.now(timezone.utc)
    weekday = now.weekday()  # 0=Monday, 5=Saturday, 6=Sunday

    if weekday == 5:  # Saturday always closed
        return False
    if weekday == 6 and now.time() < time(21, 0):  # Sunday before NY open
        return False
    if weekday == 4 and now.time() >= time(21, 0):  # Friday after NY close
        return False
    return True
