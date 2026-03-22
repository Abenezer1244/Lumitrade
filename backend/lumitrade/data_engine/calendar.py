"""
Lumitrade Economic Calendar
==============================
Fetches high and medium impact news events for the next 4 hours.
Results cached for 30 minutes to minimize API calls.
Per BDS Section 4 and PRD Section 10.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..core.enums import NewsImpact
from ..core.models import NewsEvent
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 1800  # 30 minutes


class CalendarFetcher:
    """Fetches and caches economic calendar events."""

    def __init__(self):
        self._cache: list[NewsEvent] = []
        self._cache_expiry: Optional[datetime] = None

    async def get_upcoming_events(
        self, currencies: list[str], hours_ahead: int = 4
    ) -> list[NewsEvent]:
        """
        Get upcoming high and medium impact events.
        Returns cached results if available and fresh.

        Phase 0: Returns empty list (no news API configured).
        Phase 2: Will integrate with NewsAPI or ForexFactory.
        """
        now = datetime.now(timezone.utc)

        # Return cache if still valid
        if self._cache_expiry and now < self._cache_expiry:
            return self._filter_upcoming(self._cache, currencies, hours_ahead)

        # Phase 0: No external calendar API configured
        # Return empty list — news blackout checks will pass (no events = no block)
        events = await self._fetch_events()
        self._cache = events
        self._cache_expiry = now + timedelta(seconds=CACHE_TTL_SECONDS)

        return self._filter_upcoming(events, currencies, hours_ahead)

    async def _fetch_events(self) -> list[NewsEvent]:
        """
        Fetch events from calendar API.

        Phase 0: Returns empty list.
        Phase 2 TODO: Integrate with ForexFactory scraper or newsapi.org
        """
        logger.debug("calendar_fetch_phase_0_stub")
        return []

    def _filter_upcoming(
        self,
        events: list[NewsEvent],
        currencies: list[str],
        hours_ahead: int,
    ) -> list[NewsEvent]:
        """Filter events by currency and time window."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)

        return [
            e
            for e in events
            if e.scheduled_at <= cutoff
            and any(c in e.currencies_affected for c in currencies)
            and e.impact in (NewsImpact.HIGH, NewsImpact.MEDIUM)
        ]
