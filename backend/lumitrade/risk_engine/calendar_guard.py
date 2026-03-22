"""
Lumitrade Calendar Guard
==========================
Enforces news-based trade blackout windows.
Per BDS Section 6.1 and config parameters.

Blackout rules:
  - HIGH impact: block 30 min before, 15 min after
  - MEDIUM impact: block 15 min before
  - LOW impact: no blackout
"""

from datetime import datetime, timezone

from ..core.enums import NewsImpact
from ..core.models import NewsEvent
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class CalendarGuard:
    """Check whether a currency pair is in a news blackout window."""

    async def is_blackout(
        self,
        pair: str,
        news_events: list[NewsEvent] | None = None,
    ) -> bool:
        """
        Determine if the given pair is currently in a news blackout.

        Args:
            pair: Currency pair in OANDA format (e.g. "EUR_USD").
            news_events: Pre-fetched list of upcoming/recent NewsEvent objects.
                         If None, no blackout is assumed (safe default).

        Returns:
            True if trading should be blocked for this pair.
        """
        if not news_events:
            return False

        now = datetime.now(timezone.utc)
        pair_currencies = set(pair.replace("_", "").upper()[i:i + 3] for i in (0, 3))

        for event in news_events:
            # Only check events that affect currencies in this pair
            event_currencies = {c.upper() for c in event.currencies_affected}
            if not pair_currencies & event_currencies:
                continue

            minutes_until = event.minutes_until
            # If the event model doesn't have a fresh minutes_until,
            # recompute from scheduled_at
            if event.scheduled_at.tzinfo is not None:
                delta = (event.scheduled_at - now).total_seconds() / 60.0
                minutes_until = int(delta)

            if event.impact == NewsImpact.HIGH:
                # Block 30 min before through 15 min after
                if -15 <= minutes_until <= 30:
                    logger.info(
                        "news_blackout_triggered",
                        pair=pair,
                        event=event.title,
                        impact=event.impact.value,
                        minutes_until=minutes_until,
                    )
                    return True

            elif event.impact == NewsImpact.MEDIUM:
                # Block 15 min before only
                if 0 <= minutes_until <= 15:
                    logger.info(
                        "news_blackout_triggered",
                        pair=pair,
                        event=event.title,
                        impact=event.impact.value,
                        minutes_until=minutes_until,
                    )
                    return True

            # LOW impact: no blackout

        return False
