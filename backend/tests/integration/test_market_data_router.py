"""
Lumitrade Integration Tests — MarketDataRouter (P1)
====================================================
MDR-001 to MDR-006: per-pair market-data dispatch. Uses lightweight fakes for
the OANDA and Alpaca clients (no HTTP) to assert routing, merge, stream
exclusion, and transparent forwarding.
"""

import pytest

from lumitrade.infrastructure.market_data_router import MarketDataRouter


class _FakeClient:
    """Records calls; returns venue-tagged data so routing is observable."""

    def __init__(self, tag: str):
        self.tag = tag
        self.candle_calls: list[tuple] = []
        self.pricing_calls: list[list] = []
        self.stream_calls: list[list] = []

    async def get_candles(self, pair, granularity, count=50):
        self.candle_calls.append((pair, granularity, count))
        return [{"venue": self.tag, "pair": pair}]

    async def get_pricing(self, pairs):
        self.pricing_calls.append(list(pairs))
        return {"prices": [{"instrument": p, "venue": self.tag} for p in pairs]}

    async def stream_prices(self, pairs):
        self.stream_calls.append(list(pairs))
        for p in pairs:
            yield f"{self.tag}:{p}"

    async def close(self):
        self.closed = True

    # A non-data method that must transparently forward through the router.
    async def get_account_summary_for(self, pair):
        return {"venue": self.tag, "pair": pair}


class _Cfg:
    ALPACA_CRYPTO_PAIRS = frozenset({"BTC_USD"})

    def uses_alpaca(self, pair: str) -> bool:
        return pair.upper() in self.ALPACA_CRYPTO_PAIRS


@pytest.fixture
def oanda():
    return _FakeClient("oanda")


@pytest.fixture
def crypto():
    return _FakeClient("alpaca")


@pytest.fixture
def router(oanda, crypto):
    return MarketDataRouter(_Cfg(), oanda, crypto)


@pytest.mark.integration
class TestMarketDataRouter:
    async def test_mdr001_candles_route_by_pair(self, router, oanda, crypto):
        forex = await router.get_candles("USD_CAD", "H1", 10)
        btc = await router.get_candles("BTC_USD", "D", 30)
        assert forex[0]["venue"] == "oanda"
        assert btc[0]["venue"] == "alpaca"
        assert oanda.candle_calls == [("USD_CAD", "H1", 10)]
        assert crypto.candle_calls == [("BTC_USD", "D", 30)]

    async def test_mdr002_pricing_splits_and_merges(self, router, oanda, crypto):
        result = await router.get_pricing(["USD_CAD", "BTC_USD", "USD_JPY"])
        venues = {p["instrument"]: p["venue"] for p in result["prices"]}
        assert venues == {
            "USD_CAD": "oanda", "USD_JPY": "oanda", "BTC_USD": "alpaca"
        }
        # OANDA only asked for its own pairs; Alpaca only for BTC.
        assert oanda.pricing_calls == [["USD_CAD", "USD_JPY"]]
        assert crypto.pricing_calls == [["BTC_USD"]]

    async def test_mdr003_stream_excludes_crypto(self, router, oanda, crypto):
        lines = [x async for x in router.stream_prices(["USD_CAD", "BTC_USD"])]
        assert lines == ["oanda:USD_CAD"]  # BTC never streamed in P1
        assert oanda.stream_calls == [["USD_CAD"]]
        assert crypto.stream_calls == []  # Alpaca stream untouched

    async def test_mdr004_forwards_non_data_methods(self, router):
        # get_account_summary_for is not overridden -> forwards to OANDA.
        summary = await router.get_account_summary_for("BTC_USD")
        assert summary["venue"] == "oanda"

    async def test_mdr005_no_crypto_client_all_oanda(self, oanda):
        router = MarketDataRouter(_Cfg(), oanda, None)
        btc = await router.get_candles("BTC_USD", "D", 30)
        assert btc[0]["venue"] == "oanda"  # falls back to OANDA when Alpaca off
        pricing = await router.get_pricing(["BTC_USD"])
        assert pricing["prices"][0]["venue"] == "oanda"
        lines = [x async for x in router.stream_prices(["BTC_USD"])]
        assert lines == ["oanda:BTC_USD"]

    async def test_mdr006_close_closes_both(self, router, oanda, crypto):
        await router.close()
        assert oanda.closed is True
        assert crypto.closed is True

    async def test_mdr007_crypto_only_stream_idles_not_empty_oanda(
        self, router, oanda
    ):
        """Crypto-only universe must NOT open an empty-instrument OANDA stream
        (which 400s and thrashes reconnect). The generator idles instead;
        crypto rides the REST pricing fallback."""
        import asyncio

        gen = router.stream_prices(["BTC_USD"])
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(gen.__anext__(), timeout=0.15)
        assert oanda.stream_calls == []  # OANDA stream never invoked
        await gen.aclose()
