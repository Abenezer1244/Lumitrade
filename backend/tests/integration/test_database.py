"""
Lumitrade Integration Tests — Database Client
================================================
DB-001 to DB-007: DatabaseClient operation tests.
Supabase client is mocked — no real DB calls.
Verifies correct method chaining and return values.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumitrade.config import LumitradeConfig
from lumitrade.infrastructure.db import DatabaseClient


# ── Fixtures ──────────────────────────────────────────────────────


def _make_config() -> LumitradeConfig:
    """Create a LumitradeConfig with test defaults."""
    return LumitradeConfig(
        OANDA_API_KEY_DATA="test_key_data",
        OANDA_API_KEY_TRADING="test_key_trading",
        OANDA_ACCOUNT_ID="test_account",
        OANDA_ENVIRONMENT="practice",
        ANTHROPIC_API_KEY="test_key",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_SERVICE_KEY="test_service_key",
        TELNYX_API_KEY="test_telnyx_key",
        TELNYX_FROM_NUMBER="+10000000000",
        ALERT_SMS_TO="+10000000001",
        SENDGRID_API_KEY="test_sg_key",
        ALERT_EMAIL_TO="test@test.com",
        INSTANCE_ID="ci-test",
        TRADING_MODE="PAPER",
    )


def _build_mock_supabase():
    """
    Build a mock Supabase async client that supports the chained
    query builder pattern: client.table("x").insert(data).execute()
    """
    mock_client = MagicMock()

    # The query builder supports chaining: each method returns the builder itself
    mock_query = MagicMock()

    # Make every chained method return the query builder
    mock_query.insert.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.upsert.return_value = mock_query
    mock_query.delete.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query

    # execute() returns an awaitable response
    mock_response = MagicMock()
    mock_response.data = [{"id": "abc-123", "pair": "EUR_USD", "status": "OPEN"}]
    mock_response.count = 1
    mock_query.execute = AsyncMock(return_value=mock_response)

    # table() returns the query builder
    mock_client.table.return_value = mock_query

    return mock_client, mock_query, mock_response


@pytest.fixture
def db_client():
    """Create a DatabaseClient with a pre-injected mock Supabase client."""
    config = _make_config()
    client = DatabaseClient(config)
    mock_supabase, mock_query, mock_response = _build_mock_supabase()
    client._client = mock_supabase
    return client, mock_supabase, mock_query, mock_response


# ── Test Class ────────────────────────────────────────────────────


@pytest.mark.integration
class TestDatabaseClient:
    """DB-001 to DB-007: DatabaseClient operation tests."""

    # ── DB-001: insert() calls table().insert().execute() ────────

    async def test_db001_insert_calls_correct_chain(self, db_client):
        """DB-001: insert() calls table().insert().execute() with correct data."""
        client, mock_supabase, mock_query, mock_response = db_client
        mock_response.data = {"id": "new-123", "pair": "GBP_USD"}

        data = {"pair": "GBP_USD", "action": "BUY", "confidence": "0.85"}
        result = await client.insert("signals", data)

        mock_supabase.table.assert_called_once_with("signals")
        mock_query.insert.assert_called_once_with(data)
        mock_query.execute.assert_awaited_once()
        assert result == {"id": "new-123", "pair": "GBP_USD"}

    # ── DB-002: select() applies filters via eq() ────────────────

    async def test_db002_select_applies_filters(self, db_client):
        """DB-002: select() applies each filter key via eq() and returns list."""
        client, mock_supabase, mock_query, mock_response = db_client
        mock_response.data = [
            {"id": "1", "pair": "EUR_USD", "status": "OPEN"},
            {"id": "2", "pair": "EUR_USD", "status": "OPEN"},
        ]

        result = await client.select(
            "open_positions",
            {"pair": "EUR_USD", "status": "OPEN"},
            order="created_at",
            limit=10,
        )

        mock_supabase.table.assert_called_with("open_positions")
        mock_query.select.assert_called_with("*")
        # eq() should be called once per filter key
        assert mock_query.eq.call_count == 2
        mock_query.order.assert_called_once_with("created_at", desc=True)
        mock_query.limit.assert_called_once_with(10)
        assert len(result) == 2

    # ── DB-003: select_one() returns first row or None ───────────

    async def test_db003_select_one_returns_first_row(self, db_client):
        """DB-003: select_one() returns first row when data exists."""
        client, mock_supabase, mock_query, mock_response = db_client
        mock_response.data = [{"id": "abc", "pair": "USD_JPY"}]

        result = await client.select_one("trades", {"id": "abc"})

        assert result == {"id": "abc", "pair": "USD_JPY"}

    async def test_db003_select_one_returns_none_when_empty(self, db_client):
        """DB-003b: select_one() returns None when no rows match."""
        client, mock_supabase, mock_query, mock_response = db_client
        mock_response.data = []

        result = await client.select_one("trades", {"id": "nonexistent"})

        assert result is None

    # ── DB-004: update() calls table().update() with filters ─────

    async def test_db004_update_calls_correct_chain(self, db_client):
        """DB-004: update() calls table().update() and applies filters."""
        client, mock_supabase, mock_query, mock_response = db_client
        mock_response.data = {"id": "abc", "status": "CLOSED"}

        result = await client.update(
            "trades",
            {"id": "abc"},
            {"status": "CLOSED", "closed_at": "2026-03-22T12:00:00Z"},
        )

        mock_supabase.table.assert_called_with("trades")
        mock_query.update.assert_called_once_with(
            {"status": "CLOSED", "closed_at": "2026-03-22T12:00:00Z"}
        )
        mock_query.eq.assert_called()
        mock_query.execute.assert_awaited()

    # ── DB-005: upsert() calls table().upsert().execute() ────────

    async def test_db005_upsert_calls_correct_chain(self, db_client):
        """DB-005: upsert() calls table().upsert().execute()."""
        client, mock_supabase, mock_query, mock_response = db_client
        mock_response.data = {"id": "abc", "risk_state": "NORMAL"}

        data = {"id": "abc", "risk_state": "NORMAL", "updated_at": "2026-03-22T12:00:00Z"}
        result = await client.upsert("system_state", data)

        mock_supabase.table.assert_called_with("system_state")
        mock_query.upsert.assert_called_once_with(data)
        mock_query.execute.assert_awaited()

    # ── DB-006: count() returns integer ──────────────────────────

    async def test_db006_count_returns_integer(self, db_client):
        """DB-006: count() returns integer count of matching rows."""
        client, mock_supabase, mock_query, mock_response = db_client
        mock_response.count = 5

        result = await client.count("open_positions", {"status": "OPEN"})

        mock_supabase.table.assert_called_with("open_positions")
        mock_query.select.assert_called_with("*", count="exact")
        assert result == 5
        assert isinstance(result, int)

    async def test_db006_count_returns_zero_when_none(self, db_client):
        """DB-006b: count() returns 0 when response.count is None."""
        client, mock_supabase, mock_query, mock_response = db_client
        mock_response.count = None

        result = await client.count("open_positions", {"status": "OPEN"})

        assert result == 0

    # ── DB-007: Access before connect() raises RuntimeError ──────

    async def test_db007_access_before_connect_raises_runtime_error(self):
        """DB-007: Accessing client before connect() raises RuntimeError."""
        config = _make_config()
        client = DatabaseClient(config)

        # client property should raise because _client is None
        with pytest.raises(RuntimeError, match="not connected"):
            _ = client.client
