"""
Lumitrade Integration Tests — Alpaca SpotCryptoClient (read-only, P1)
=====================================================================
SC-001 to SC-009: SpotCryptoClient HTTP interaction + normalization tests.
Uses respx to mock httpx calls — no real Alpaca API calls.

Verifies the read-only client returns data in the SAME OANDA-shaped dicts the
data engine already consumes, so candle_fetcher / indicators / D1 filter work
unchanged. Also verifies the P1 trading surface is inert (raises).
"""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from lumitrade.config import LumitradeConfig
from lumitrade.infrastructure.spot_crypto_client import (
    SpotCryptoClient,
    _to_alpaca_symbol,
    _to_internal_pair,
)

DATA_BASE = "https://data.alpaca.markets"
TRADING_BASE = "https://paper-api.alpaca.markets"


def _make_config() -> LumitradeConfig:
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
        ALPACA_API_KEY_ID="test_alpaca_id",
        ALPACA_API_SECRET_KEY="test_alpaca_secret",
        ALPACA_PAPER=True,
    )


@pytest.fixture
def config():
    return _make_config()


@pytest.fixture
def crypto_client(config):
    """SpotCryptoClient with plain httpx clients so respx can intercept."""
    client = SpotCryptoClient.__new__(SpotCryptoClient)
    client.config = config
    client._data_base = DATA_BASE
    client._trading_base = TRADING_BASE
    headers = {
        "APCA-API-KEY-ID": config.alpaca_api_key_id,
        "APCA-API-SECRET-KEY": config.alpaca_api_secret_key,
        "Content-Type": "application/json",
    }
    client._data = httpx.AsyncClient(base_url=DATA_BASE, headers=headers)
    client._trading = httpx.AsyncClient(base_url=TRADING_BASE, headers=headers)
    return client


# ── Symbol normalization (pure) ──────────────────────────────────────


def test_symbol_normalization():
    assert _to_alpaca_symbol("BTC_USD") == "BTC/USD"
    assert _to_internal_pair("BTC/USD") == "BTC_USD"
    assert _to_internal_pair("BTCUSD") == "BTC_USD"
    # round-trip
    assert _to_internal_pair(_to_alpaca_symbol("BTC_USD")) == "BTC_USD"


# ── SC-001: get_candles normalizes + orders ascending ────────────────


@pytest.mark.integration
class TestSpotCryptoClient:
    @respx.mock
    async def test_sc001_get_candles_normalizes_and_orders_ascending(
        self, crypto_client
    ):
        """SC-001: Alpaca bars -> OANDA candle dict, newest-N reversed to asc."""
        # Alpaca returns sort=desc (newest first). Old timestamps so all bars
        # are complete regardless of wall-clock during the test run.
        bars = {
            "bars": {
                "BTC/USD": [
                    {"t": "2020-01-03T00:00:00Z", "o": 7300.1, "h": 7400.0,
                     "l": 7200.0, "c": 7350.5, "v": 1234.5, "n": 10, "vw": 7325.0},
                    {"t": "2020-01-02T00:00:00Z", "o": 7200.0, "h": 7320.0,
                     "l": 7150.0, "c": 7300.1, "v": 1000.0, "n": 8, "vw": 7250.0},
                    {"t": "2020-01-01T00:00:00Z", "o": 7150.0, "h": 7250.0,
                     "l": 7100.0, "c": 7200.0, "v": 900.0, "n": 6, "vw": 7180.0},
                ]
            },
            "next_page_token": None,
        }
        route = respx.get(f"{DATA_BASE}/v1beta3/crypto/us/bars").mock(
            return_value=httpx.Response(200, json=bars)
        )

        result = await crypto_client.get_candles("BTC_USD", "D", count=3)

        assert route.called
        # Correct timeframe + symbol + sort sent
        sent = route.calls.last.request.url
        assert "timeframe=1Day" in str(sent)
        assert "sort=desc" in str(sent)
        assert "BTC%2FUSD" in str(sent) or "BTC/USD" in str(sent)
        # Reversed to ascending
        assert len(result) == 3
        assert result[0]["time"] == "2020-01-01T00:00:00Z"
        assert result[2]["time"] == "2020-01-03T00:00:00Z"
        # OANDA shape: mid with STRING ohlc, int volume, complete bool
        assert result[2]["mid"] == {
            "o": "7300.1", "h": "7400.0", "l": "7200.0", "c": "7350.5"
        }
        assert result[2]["volume"] == 1234
        assert result[2]["complete"] is True
        # All ohlc are strings (so Decimal() is exact downstream)
        for key in ("o", "h", "l", "c"):
            assert isinstance(result[0]["mid"][key], str)

    @respx.mock
    async def test_sc001b_candles_parse_to_candle_dataclass(self, crypto_client):
        """SC-001b: normalized dicts feed CandleFetcher._parse_candle cleanly."""
        from decimal import Decimal

        from lumitrade.data_engine.candle_fetcher import CandleFetcher

        bars = {
            "bars": {
                "BTC/USD": [
                    {"t": "2020-01-02T00:00:00Z", "o": 7200.0, "h": 7320.0,
                     "l": 7150.0, "c": 7300.1, "v": 1000.0, "n": 8, "vw": 7250.0},
                    {"t": "2020-01-01T00:00:00Z", "o": 7150.0, "h": 7250.0,
                     "l": 7100.0, "c": 7200.0, "v": 900.0, "n": 6, "vw": 7180.0},
                ]
            }
        }
        respx.get(f"{DATA_BASE}/v1beta3/crypto/us/bars").mock(
            return_value=httpx.Response(200, json=bars)
        )
        raw = await crypto_client.get_candles("BTC_USD", "D", count=2)
        fetcher = CandleFetcher.__new__(CandleFetcher)
        parsed = [fetcher._parse_candle(c, "D") for c in raw]
        assert parsed[0].close == Decimal("7200.0")
        assert parsed[1].close == Decimal("7300.1")
        assert parsed[0].volume == 900
        assert parsed[0].timeframe == "D"

    def test_sc002_completeness_boundary(self, crypto_client):
        """SC-002: forming current-period bar marked complete=False."""
        now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
        # A 1Day bar opened today has NOT closed at noon -> incomplete.
        forming = {"t": "2026-06-30T00:00:00Z", "o": 60000, "h": 61000,
                   "l": 59000, "c": 60500, "v": 10.0}
        closed = {"t": "2026-06-29T00:00:00Z", "o": 59000, "h": 60000,
                  "l": 58000, "c": 60000, "v": 12.0}
        assert crypto_client._normalize_bar(forming, "D", now)["complete"] is False
        assert crypto_client._normalize_bar(closed, "D", now)["complete"] is True

    @respx.mock
    async def test_sc003_get_pricing_from_quotes(self, crypto_client):
        """SC-003: latest quotes -> OANDA pricing shape (bp/ap -> bids/asks)."""
        quotes = {"quotes": {"BTC/USD": {
            "t": "2026-06-30T12:00:00Z", "bp": 60010.5, "ap": 60020.0,
            "bs": 1.0, "as": 0.5}}}
        route = respx.get(f"{DATA_BASE}/v1beta3/crypto/us/latest/quotes").mock(
            return_value=httpx.Response(200, json=quotes)
        )
        result = await crypto_client.get_pricing(["BTC_USD"])
        assert route.called
        p = result["prices"][0]
        assert p["instrument"] == "BTC_USD"
        assert p["bids"][0]["price"] == "60010.5"
        assert p["asks"][0]["price"] == "60020.0"

    @respx.mock
    async def test_sc004_get_pricing_falls_back_to_trades(self, crypto_client):
        """SC-004: zero/missing quote falls back to last trade price."""
        quotes = {"quotes": {"BTC/USD": {
            "t": "2026-06-30T12:00:00Z", "bp": 0, "ap": 0, "bs": 0, "as": 0}}}
        trades = {"trades": {"BTC/USD": {
            "t": "2026-06-30T12:00:01Z", "p": 60015.25, "s": 0.1}}}
        respx.get(f"{DATA_BASE}/v1beta3/crypto/us/latest/quotes").mock(
            return_value=httpx.Response(200, json=quotes)
        )
        trade_route = respx.get(
            f"{DATA_BASE}/v1beta3/crypto/us/latest/trades"
        ).mock(return_value=httpx.Response(200, json=trades))
        result = await crypto_client.get_pricing(["BTC_USD"])
        assert trade_route.called
        p = result["prices"][0]
        assert p["bids"][0]["price"] == "60015.25"
        assert p["asks"][0]["price"] == "60015.25"

    @respx.mock
    async def test_sc005_get_account_summary(self, crypto_client):
        """SC-005: /v2/account -> normalized summary; nmbp is crypto-spendable."""
        account = {
            "account_number": "PA123", "currency": "USD",
            "equity": "150.25", "cash": "150.25",
            "buying_power": "300.50", "non_marginable_buying_power": "150.25",
        }
        route = respx.get(f"{TRADING_BASE}/v2/account").mock(
            return_value=httpx.Response(200, json=account)
        )
        result = await crypto_client.get_account_summary()
        assert route.called
        assert result["balance"] == "150.25"
        assert result["equity"] == "150.25"
        assert result["NAV"] == "150.25"
        assert result["non_marginable_buying_power"] == "150.25"
        assert result["_broker"] == "alpaca"

    @respx.mock
    async def test_sc006_positions_diagnostic_filters_crypto(self, crypto_client):
        """SC-006: get_positions_diagnostic -> crypto-only view, qty_available."""
        positions = [
            {"symbol": "BTC/USD", "side": "long", "qty": "0.0050",
             "qty_available": "0.0030", "avg_entry_price": "60000",
             "market_value": "300", "unrealized_pl": "5",
             "current_price": "60100"},
            {"symbol": "AAPL", "side": "long", "qty": "10",
             "qty_available": "10", "avg_entry_price": "190"},
        ]
        route = respx.get(f"{TRADING_BASE}/v2/positions").mock(
            return_value=httpx.Response(200, json=positions)
        )
        result = await crypto_client.get_positions_diagnostic()
        assert route.called
        assert len(result) == 1  # AAPL filtered out
        assert result[0]["instrument"] == "BTC_USD"
        assert result[0]["qty_available"] == "0.0030"

    async def test_sc006b_get_open_trades_raises(self, crypto_client):
        """SC-006b: get_open_trades hard-fails (ghost-bug guard) until P2/P3."""
        with pytest.raises(NotImplementedError):
            await crypto_client.get_open_trades()

    @respx.mock
    async def test_sc007_http_error_raises(self, crypto_client):
        """SC-007: HTTP 401 on bars raises HTTPStatusError (no silent default)."""
        respx.get(f"{DATA_BASE}/v1beta3/crypto/us/bars").mock(
            return_value=httpx.Response(401, json={"message": "forbidden"})
        )
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await crypto_client.get_candles("BTC_USD", "D", count=5)
        assert exc.value.response.status_code == 401

    async def test_sc008_trading_surface_inert(self, crypto_client):
        """SC-008: P1 order/close/stream surface raises — never silently trades."""
        from decimal import Decimal

        with pytest.raises(NotImplementedError):
            await crypto_client.place_market_order(
                "BTC_USD", Decimal("0.001"), Decimal("59000"),
                Decimal("62000"), "cid-1"
            )
        with pytest.raises(NotImplementedError):
            await crypto_client.close_trade("x", "BTC_USD")
        with pytest.raises(NotImplementedError):
            async for _ in crypto_client.stream_prices(["BTC_USD"]):
                break

    def test_sc009_requires_credentials(self, config):
        """SC-009: constructing without keys is a hard error (guarded feature)."""
        config.alpaca_api_key_id = None
        with pytest.raises(ValueError):
            SpotCryptoClient(config)


@pytest.mark.integration
async def test_alpaca_unsupported_granularity_raises(crypto_client):
    """Unknown granularity (e.g. M1) is rejected, not silently mismapped."""
    with pytest.raises(ValueError):
        await crypto_client.get_candles("BTC_USD", "M1", count=5)
