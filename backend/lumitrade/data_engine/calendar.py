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
        self._cache: list[NewsEvent] | None = None
        self._cache_expiry: Optional[datetime] = None
        # Tracks whether the last fetch succeeded — None = never fetched
        self._last_fetch_ok: bool | None = None

    async def get_upcoming_events(
        self, currencies: list[str], hours_ahead: int = 4
    ) -> list[NewsEvent] | None:
        """
        Get upcoming high and medium impact events.
        Returns None when the calendar API is unavailable (vs [] for no events).
        CalendarGuard uses None to apply safety blocks during known risk windows.
        Returns cached results if available and fresh.
        """
        now = datetime.now(timezone.utc)

        # Return cache if still valid (preserves None if last fetch failed)
        if self._cache_expiry and now < self._cache_expiry:
            if self._cache is None:
                return None
            return self._filter_upcoming(self._cache, currencies, hours_ahead)

        # Fetch fresh events from OANDA Labs
        events = await self._fetch_events()
        self._last_fetch_ok = events is not None
        if events is None:
            # Keep stale cache entry for TTL so we don't hammer a down API
            self._cache_expiry = now + timedelta(seconds=CACHE_TTL_SECONDS)
            self._cache = None
            return None
        self._cache = events
        self._cache_expiry = now + timedelta(seconds=CACHE_TTL_SECONDS)

        return self._filter_upcoming(events, currencies, hours_ahead)

    async def _fetch_events(self) -> list[NewsEvent] | None:
        """
        Fetch economic calendar from ForexFactory free JSON feed.

        Returns None on any network/API failure (caller distinguishes from []).
        Returns [] when fetch succeeds but no events match.
        """
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning("calendar_fetch_failed", status=resp.status_code)
                    return None

                raw_events = resp.json()

        except Exception as e:
            logger.error("calendar_fetch_failed", error=str(e))
            return None

        # Map ForexFactory country codes to forex currencies
        country_to_currency = {
            "USD": "USD", "EUR": "EUR", "GBP": "GBP", "JPY": "JPY",
            "AUD": "AUD", "CAD": "CAD", "CHF": "CHF", "NZD": "NZD",
        }

        now = datetime.now(timezone.utc)
        lookahead = now + timedelta(hours=4)
        events: list[NewsEvent] = []

        for raw in raw_events:
            try:
                # Parse impact
                impact_str = (raw.get("impact") or "").strip()
                if impact_str == "High":
                    impact = NewsImpact.HIGH
                elif impact_str == "Medium":
                    impact = NewsImpact.MEDIUM
                else:
                    continue  # Skip low/holiday

                # Parse time
                date_str = raw.get("date", "")
                event_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)

                # Only include events in the next 4 hours
                if event_time < now - timedelta(minutes=15) or event_time > lookahead:
                    continue

                currency = country_to_currency.get(raw.get("country", ""), "")
                if not currency:
                    continue

                title = raw.get("title", "Unknown Event")
                minutes_until = int((event_time - now).total_seconds() / 60)

                event_id = hashlib.sha256(
                    f"{title}{date_str}".encode()
                ).hexdigest()[:16]

                events.append(NewsEvent(
                    event_id=event_id,
                    title=title,
                    impact=impact,
                    currencies_affected=[currency],
                    scheduled_at=event_time,
                    minutes_until=max(minutes_until, 0),
                ))

            except Exception:
                continue

        logger.info("calendar_fetched", event_count=len(events), source="forexfactory")
        return events

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
