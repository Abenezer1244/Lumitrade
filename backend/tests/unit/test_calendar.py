"""
Regression test for Codex 2026-04-25 audit finding [critical] #2:
CalendarFetcher constructed NewsEvent with the wrong field name (event_time=)
while the dataclass requires scheduled_at. The TypeError was swallowed by
the bare except in _fetch_events, silently dropping every high-impact event
and letting the engine trade into NFP/FOMC blackouts.

This test exercises the forexfactory ingestion path with a mocked HTTP
response and asserts that the returned NewsEvent has scheduled_at set
correctly. A regression of the original bug would either:
  - raise TypeError during construction (caught by the bare except, returning
    an empty list — assertion on len fails), or
  - produce a NewsEvent missing scheduled_at (assertion on the field fails).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumitrade.core.enums import NewsImpact
from lumitrade.core.models import NewsEvent
from lumitrade.data_engine.calendar import CalendarFetcher


def _build_config() -> MagicMock:
    cfg = MagicMock()
    cfg.oanda_base_url = "https://api-fxpractice.oanda.com"
    return cfg


def _build_response(payload: list[dict], status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=payload)
    return resp


@pytest.mark.asyncio
async def test_news_event_constructor_requires_scheduled_at():
    """Direct dataclass test: event_time= must fail, scheduled_at= must succeed."""
    now = datetime.now(timezone.utc)

    # Positive: correct field name builds successfully.
    ev = NewsEvent(
        event_id="abc123",
        title="NFP",
        currencies_affected=["USD"],
        impact=NewsImpact.HIGH,
        scheduled_at=now,
        minutes_until=30,
    )
    assert ev.scheduled_at == now

    # Negative: wrong field name (the original bug) must raise.
    with pytest.raises(TypeError):
        NewsEvent(
            event_id="abc123",
            title="NFP",
            currencies_affected=["USD"],
            impact=NewsImpact.HIGH,
            event_time=now,  # type: ignore[call-arg]
            minutes_until=30,
        )


@pytest.mark.asyncio
async def test_fetch_events_populates_scheduled_at_from_forexfactory():
    """Full ingestion path: httpx mock -> _fetch_events -> NewsEvent.scheduled_at."""
    fetcher = CalendarFetcher(_build_config())

    # ForexFactory returns ISO-8601 timestamps; build one ~30 min in the future
    # so it falls inside the 4-hour lookahead window.
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    payload = [
        {
            "title": "Non-Farm Employment Change",
            "country": "USD",
            "date": future.isoformat().replace("+00:00", "Z"),
            "impact": "High",
        },
        {
            "title": "Holiday — should be skipped",
            "country": "USD",
            "date": future.isoformat().replace("+00:00", "Z"),
            "impact": "Low",
        },
    ]

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(return_value=_build_response(payload))

    with patch("lumitrade.data_engine.calendar.httpx.AsyncClient", return_value=mock_client):
        events = await fetcher._fetch_events()

    # The high-impact event MUST be returned — if the constructor still used
    # event_time=, the bare-except in _fetch_events would catch the TypeError
    # and return an empty list, hiding the bug. Assert non-empty + correct shape.
    assert len(events) == 1, f"expected 1 high-impact event, got {len(events)}"
    ev = events[0]
    assert isinstance(ev, NewsEvent)
    assert ev.impact == NewsImpact.HIGH
    assert ev.title == "Non-Farm Employment Change"
    assert ev.currencies_affected == ["USD"]
    # Critical assertion: scheduled_at is the field that downstream consumers
    # (calendar_guard, _filter_upcoming) actually read.
    assert isinstance(ev.scheduled_at, datetime)
    # Within 1 second of the future timestamp we sent in (allow for parsing drift).
    assert abs((ev.scheduled_at - future).total_seconds()) < 1.0


@pytest.mark.asyncio
async def test_fetch_events_returns_none_on_http_failure():
    """HTTP non-200 returns None (distinguishable from 'no events') without crashing."""
    fetcher = CalendarFetcher(_build_config())

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(return_value=_build_response([], status_code=500))

    with patch("lumitrade.data_engine.calendar.httpx.AsyncClient", return_value=mock_client):
        events = await fetcher._fetch_events()

    assert events is None
