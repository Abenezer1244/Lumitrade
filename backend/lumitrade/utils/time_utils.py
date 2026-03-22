"""
Lumitrade Time Utilities
==========================
Session detection and market hours checking.
All times in UTC. Per BDS Section 10.2.
"""

from datetime import datetime, time, timezone

from ..core.enums import Session

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
