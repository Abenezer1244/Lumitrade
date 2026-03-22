"""
Lumitrade Integration Tests — OANDA Client
=============================================
OC-001 to OC-005: OandaClient HTTP interaction tests.
Uses respx to mock httpx calls — no real OANDA API calls.
Verifies correct endpoints, headers, and error handling.
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock

import httpx
import pytest
import respx

from lumitrade.config import LumitradeConfig
from lumitrade.infrastructure.oanda_client import OandaClient


# ── Fixtures ──────────────────────────────────────────────────────


def _make_config() -> LumitradeConfig:
    """Create a LumitradeConfig with test defaults."""
    return LumitradeConfig(
        OANDA_API_KEY_DATA="test_key_data",
        OANDA_API_KEY_TRADING="test_key_trading",
        OANDA_ACCOUNT_ID="001-004-1234567-001",
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


BASE_URL = "https://api-fxpractice.oanda.com"
ACCOUNT_ID = "001-004-1234567-001"


@pytest.fixture
def config():
    return _make_config()


@pytest.fixture
def oanda_client(config):
    """
    Create an OandaClient with a plain httpx.AsyncClient (no SSL)
    so respx can intercept requests in the test environment.
    """
    client = OandaClient.__new__(OandaClient)
    client.config = config
    client._base_url = config.oanda_base_url
    client._stream_url = config.oanda_stream_url
    client._account_id = config.oanda_account_id
    # Use a plain httpx.AsyncClient that respx can intercept
    client._client = httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {config.oanda_api_key_data}",
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(10.0),
    )
    return client


# ── Test Class ────────────────────────────────────────────────────


@pytest.mark.integration
class TestOandaClient:
    """OC-001 to OC-005: OANDA Client HTTP tests."""

    # ── OC-001: get_candles() calls correct endpoint ─────────────

    @respx.mock
    async def test_oc001_get_candles_correct_endpoint(self, oanda_client):
        """OC-001: get_candles() calls /v3/instruments/{pair}/candles."""
        candle_data = {
            "candles": [
                {
                    "time": "2026-03-22T10:00:00Z",
                    "mid": {"o": "1.08500", "h": "1.08600", "l": "1.08400", "c": "1.08550"},
                    "volume": 1250,
                    "complete": True,
                },
                {
                    "time": "2026-03-22T10:15:00Z",
                    "mid": {"o": "1.08550", "h": "1.08700", "l": "1.08500", "c": "1.08650"},
                    "volume": 980,
                    "complete": True,
                },
            ]
        }

        route = respx.get(f"{BASE_URL}/v3/instruments/EUR_USD/candles").mock(
            return_value=httpx.Response(200, json=candle_data)
        )

        result = await oanda_client.get_candles("EUR_USD", "M15", count=2)

        assert route.called
        assert len(result) == 2
        assert result[0]["volume"] == 1250
        assert result[1]["mid"]["c"] == "1.08650"

    # ── OC-002: get_pricing() returns bid/ask data ───────────────

    @respx.mock
    async def test_oc002_get_pricing_returns_bid_ask(self, oanda_client):
        """OC-002: get_pricing() returns bid/ask data for requested pairs."""
        pricing_data = {
            "prices": [
                {
                    "instrument": "EUR_USD",
                    "asks": [{"price": "1.08520", "liquidity": 1000000}],
                    "bids": [{"price": "1.08500", "liquidity": 1000000}],
                    "time": "2026-03-22T10:30:00Z",
                },
                {
                    "instrument": "GBP_USD",
                    "asks": [{"price": "1.26820", "liquidity": 500000}],
                    "bids": [{"price": "1.26800", "liquidity": 500000}],
                    "time": "2026-03-22T10:30:00Z",
                },
            ]
        }

        route = respx.get(
            f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/pricing"
        ).mock(return_value=httpx.Response(200, json=pricing_data))

        result = await oanda_client.get_pricing(["EUR_USD", "GBP_USD"])

        assert route.called
        assert len(result["prices"]) == 2
        assert result["prices"][0]["instrument"] == "EUR_USD"
        assert result["prices"][0]["bids"][0]["price"] == "1.08500"

    # ── OC-003: get_account_summary() returns balance/equity ─────

    @respx.mock
    async def test_oc003_get_account_summary_returns_balance(self, oanda_client):
        """OC-003: get_account_summary() returns account balance and equity."""
        summary_data = {
            "account": {
                "id": ACCOUNT_ID,
                "balance": "10000.00",
                "unrealizedPL": "125.50",
                "pl": "500.00",
                "marginUsed": "200.00",
                "openTradeCount": 2,
                "currency": "USD",
            }
        }

        route = respx.get(
            f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/summary"
        ).mock(return_value=httpx.Response(200, json=summary_data))

        result = await oanda_client.get_account_summary()

        assert route.called
        assert result["balance"] == "10000.00"
        assert result["currency"] == "USD"
        assert result["openTradeCount"] == 2

    # ── OC-004: get_open_trades() returns trade list ─────────────

    @respx.mock
    async def test_oc004_get_open_trades_returns_trade_list(self, oanda_client):
        """OC-004: get_open_trades() returns list of open trades."""
        trades_data = {
            "trades": [
                {
                    "id": "12345",
                    "instrument": "EUR_USD",
                    "currentUnits": "5000",
                    "price": "1.08500",
                    "unrealizedPL": "15.00",
                    "stopLossOrder": {"price": "1.08300"},
                    "takeProfitOrder": {"price": "1.08900"},
                },
                {
                    "id": "12346",
                    "instrument": "GBP_USD",
                    "currentUnits": "-3000",
                    "price": "1.26800",
                    "unrealizedPL": "-8.50",
                    "stopLossOrder": {"price": "1.27000"},
                    "takeProfitOrder": {"price": "1.26400"},
                },
            ]
        }

        route = respx.get(
            f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/openTrades"
        ).mock(return_value=httpx.Response(200, json=trades_data))

        result = await oanda_client.get_open_trades()

        assert route.called
        assert len(result) == 2
        assert result[0]["instrument"] == "EUR_USD"
        assert result[1]["currentUnits"] == "-3000"

    # ── OC-005: HTTP error raises HTTPStatusError ────────────────

    @respx.mock
    async def test_oc005_http_error_raises_status_error(self, oanda_client):
        """OC-005: HTTP 401 raises httpx.HTTPStatusError."""
        respx.get(f"{BASE_URL}/v3/instruments/EUR_USD/candles").mock(
            return_value=httpx.Response(
                401,
                json={"errorMessage": "Insufficient authorization to perform request."},
            )
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await oanda_client.get_candles("EUR_USD", "M15")

        assert exc_info.value.response.status_code == 401

    # ── OC-005b: HTTP 500 on account summary raises error ────────

    @respx.mock
    async def test_oc005b_server_error_raises_status_error(self, oanda_client):
        """OC-005b: HTTP 500 raises httpx.HTTPStatusError."""
        respx.get(
            f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/summary"
        ).mock(return_value=httpx.Response(500, json={"errorMessage": "Internal server error"}))

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await oanda_client.get_account_summary()

        assert exc_info.value.response.status_code == 500
