"""
Lumitrade Economic Calendar
==============================
Fetches high and medium impact news events from the OANDA Labs calendar API.
Results cached for 30 minutes to minimize API calls.
Per BDS Section 4 and PRD Section 10.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from ..config import LumitradeConfig
from ..core.enums import NewsImpact
from ..core.models import NewsEvent
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 1800  # 30 minutes
CALENDAR_PERIOD_SECONDS = 86400  # Fetch 24 hours of events
REQUEST_TIMEOUT_SECONDS = 10


def _map_impact(impact_value: int) -> NewsImpact:
    """Map OANDA numeric impact to NewsImpact enum.

    OANDA uses: 3 = HIGH, 2 = MEDIUM, 1 = LOW.
    """
    if impact_value >= 3:
        return NewsImpact.HIGH
    if impact_value == 2:
        return NewsImpact.MEDIUM
    return NewsImpact.LOW


def _extract_currencies_from_pair(pair: str) -> list[str]:
    """Extract individual currencies from an OANDA instrument pair.

    E.g. 'EUR_USD' -> ['EUR', 'USD']
    """
    return pair.split("_")


def _build_event_id(event: dict[str, Any]) -> str:
    """Generate a deterministic event ID from title + timestamp."""
    raw = f"{event.get('title', '')}-{event.get('timestamp', 0)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class CalendarFetcher:
    """Fetches and caches economic calendar events from OANDA Labs API."""

    def __init__(self, config: LumitradeConfig):
        self._config = config
        self._cache: list[NewsEvent] = []
        self._cache_expiry: Optional[datetime] = None

    async def get_upcoming_events(
        self, currencies: list[str], hours_ahead: int = 4
    ) -> list[NewsEvent]:
        """
        Get upcoming high and medium impact events.
        Returns cached results if available and fresh.

        Fetches from OANDA Labs /labs/v1/calendar endpoint.
        Falls back to empty list on any error (non-critical data source).
        """
        now = datetime.now(timezone.utc)

        # Return cache if still valid
        if self._cache_expiry and now < self._cache_expiry:
            return self._filter_upcoming(self._cache, currencies, hours_ahead)

        # Fetch fresh events from OANDA Labs
        events = await self._fetch_events()
        self._cache = events
        self._cache_expiry = now + timedelta(seconds=CACHE_TTL_SECONDS)

        return self._filter_upcoming(events, currencies, hours_ahead)

    async def _fetch_events(self) -> list[NewsEvent]:
        """
        Fetch economic calendar events from OANDA Labs API.

        Endpoint: GET /labs/v1/calendar?instrument={pair}&period={seconds}
        Uses the data API key (read-only) — not the trading key.

        Returns empty list on any failure (graceful degradation).
        """
        all_events: dict[str, NewsEvent] = {}

        # Fetch calendar for each configured pair to get comprehensive coverage
        pairs_to_fetch = self._config.pairs

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                for pair in pairs_to_fetch:
                    try:
                        events = await self._fetch_pair_calendar(client, pair)
                        for event in events:
                            # Deduplicate by event_id
                            all_events[event.event_id] = event
                    except Exception as e:
                        logger.warning(
                            "calendar_pair_fetch_failed",
                            pair=pair,
                            error=str(e),
                        )
                        continue

        except Exception as e:
            logger.error("calendar_fetch_failed", error=str(e))
            return []

        result = list(all_events.values())
        logger.info(
            "calendar_fetched",
            event_count=len(result),
            pairs_queried=len(pairs_to_fetch),
        )
        return result

    async def _fetch_pair_calendar(
        self, client: httpx.AsyncClient, pair: str
    ) -> list[NewsEvent]:
        """Fetch calendar events for a single instrument pair from OANDA Labs."""
        url = f"{self._config.oanda_base_url}/labs/v1/calendar"
        headers = {
            "Authorization": f"Bearer {self._config.oanda_api_key_data}",
            "Content-Type": "application/json",
        }
        params = {
            "instrument": pair,
            "period": CALENDAR_PERIOD_SECONDS,
        }

        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()

        raw_events: list[dict[str, Any]] = response.json()
        now = datetime.now(timezone.utc)
        pair_currencies = _extract_currencies_from_pair(pair)
        events: list[NewsEvent] = []

        for raw in raw_events:
            try:
                impact_value = int(raw.get("impact", 0))
                impact = _map_impact(impact_value)

                # Only keep HIGH and MEDIUM impact events
                if impact == NewsImpact.LOW:
                    continue

                timestamp = int(raw.get("timestamp", 0))
                scheduled_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                minutes_until = int((scheduled_at - now).total_seconds() / 60)

                # Use the currency field from OANDA if available,
                # otherwise fall back to pair currencies
                currency = raw.get("currency", "")
                if currency:
                    currencies_affected = [currency.upper()]
                    # Add the counter currency from the pair if the event
                    # currency matches one side
                    for c in pair_currencies:
                        if c.upper() != currency.upper():
                            currencies_affected.append(c.upper())
                else:
                    currencies_affected = pair_currencies

                event = NewsEvent(
                    event_id=_build_event_id(raw),
                    title=str(raw.get("title", "Unknown Event")),
                    currencies_affected=currencies_affected,
                    impact=impact,
                    scheduled_at=scheduled_at,
                    minutes_until=minutes_until,
                )
                events.append(event)

            except (ValueError, TypeError, KeyError) as e:
                logger.debug(
                    "calendar_event_parse_skipped",
                    title=str(raw.get("title", "?")),
                    error=str(e),
                )
                continue

        logger.debug(
            "calendar_pair_fetched",
            pair=pair,
            raw_count=len(raw_events),
            filtered_count=len(events),
        )
        return events

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
