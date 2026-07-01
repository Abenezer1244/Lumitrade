"""
Lumitrade Alpaca Spot Crypto Client (read-only — Phase 1)
==========================================================
Read-only BTC/USD client for Alpaca: candles, pricing, account, positions.
PAPER-first. Mirrors the read-only surface of ``oanda_client.py`` and returns
data normalized to the SAME dict shapes the engine already consumes (OANDA
candle / pricing shapes), so the data engine, indicators, validator, and the
BTC D1 trend filter all work unchanged once BTC market data is routed here.

Phase 1 is DATA ONLY. ``place_market_order`` / ``close_trade`` /
``stream_prices`` raise ``NotImplementedError`` — trading lands in P2/P3 with
the synthetic-trade table + software OCO supervisor (see
``docs/ALPACA_CRYPTO_INTEGRATION.md``).

THE DECISIVE CONSTRAINT (why trading is deferred): Alpaca crypto holds the full
BTC quantity against the first open SELL order and supports no bracket/OCO
order class — so a full-size stop-loss and a full-size take-profit cannot both
rest at once. Protection therefore requires a software OCO supervisor, built in
P3. This module never places an order.

Security:
  * TLS verification is always enabled (never ``verify=False``). Per SS 5.1.
  * Auth uses TWO headers — ``APCA-API-KEY-ID`` / ``APCA-API-SECRET-KEY`` —
    NOT a Bearer token. Keys are read from config (env), never logged.
Per BDS Section 4.1 + SS Section 5.1.
"""

import json
import ssl
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

from ..config import LumitradeConfig
from .broker_interface import BrokerInterface
from .secure_logger import get_logger

logger = get_logger(__name__)

# Engine granularity code -> Alpaca timeframe string.
_GRANULARITY_MAP: dict[str, str] = {
    "M5": "5Min",
    "M15": "15Min",
    "H1": "1Hour",
    "H4": "4Hour",
    "D": "1Day",
}

# Period length of each engine granularity, used to decide whether the most
# recent bar has closed (OANDA marks the forming candle complete=False; we
# reproduce that semantic from the bar's start timestamp).
_GRANULARITY_DELTA: dict[str, timedelta] = {
    "M5": timedelta(minutes=5),
    "M15": timedelta(minutes=15),
    "H1": timedelta(hours=1),
    "H4": timedelta(hours=4),
    "D": timedelta(days=1),
}


def _to_alpaca_symbol(pair: str) -> str:
    """``BTC_USD`` (internal) -> ``BTC/USD`` (Alpaca data + trading symbol)."""
    return pair.upper().replace("_", "/")


def _to_internal_pair(symbol: str) -> str:
    """``BTC/USD`` or ``BTCUSD`` -> ``BTC_USD`` (internal)."""
    s = symbol.upper()
    if "/" in s:
        return s.replace("/", "_")
    # Slash-less trading form (e.g. BTCUSD) — split off the USD quote.
    if s.endswith("USD") and len(s) > 3:
        return f"{s[:-3]}_USD"
    return s


def _create_secure_client(
    key_id: str, secret_key: str, base_url: str, timeout: float = 10.0
) -> httpx.AsyncClient:
    """HTTPX client with TLS enforced and Alpaca's two-header auth.

    Per SS Section 5.1 — never set ``verify=False``.
    """
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    ssl_ctx.check_hostname = True

    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret_key,
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(connect=5.0, read=timeout, write=5.0, pool=2.0),
        verify=ssl_ctx,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )


class SpotCryptoClient(BrokerInterface):
    """Read-only Alpaca client for spot BTC/USD. Data + account/positions.

    Constructed only when ``config.alpaca_enabled`` is True (both keys present).
    Callers that may run without Alpaca credentials must guard on that flag —
    this class assumes the keys exist.
    """

    def __init__(self, config: LumitradeConfig):
        if not config.alpaca_enabled:
            raise ValueError(
                "SpotCryptoClient requires ALPACA_API_KEY_ID and "
                "ALPACA_API_SECRET_KEY; construct only when alpaca_enabled."
            )
        self.config = config
        self._data_base = config.alpaca_data_base_url.rstrip("/")
        self._trading_base = config.alpaca_trading_url.rstrip("/")
        # Two hosts: market data vs trading/account. Same auth headers.
        self._data = _create_secure_client(
            config.alpaca_api_key_id,  # type: ignore[arg-type]
            config.alpaca_api_secret_key,  # type: ignore[arg-type]
            self._data_base,
        )
        self._trading = _create_secure_client(
            config.alpaca_api_key_id,  # type: ignore[arg-type]
            config.alpaca_api_secret_key,  # type: ignore[arg-type]
            self._trading_base,
        )

    # ── Candles ────────────────────────────────────────────────
    async def get_candles(
        self, pair: str, granularity: str, count: int = 50
    ) -> list[dict]:
        """Fetch the most recent CLOSED ``count`` OHLCV bars, OANDA-shaped.

        Returns a list of dicts identical in shape to ``OandaClient.get_candles``
        so ``CandleFetcher._parse_candle`` consumes them unchanged::

            {"time": "<iso8601>", "mid": {"o","h","l","c"} (strings),
             "volume": int, "complete": bool}

        Ordering matches OANDA's ``count`` semantics: the ``count`` most recent
        bars in ASCENDING time order.

        Two correctness guards (Codex review 2026-06-30):
          * Alpaca crypto bars default ``start`` to the beginning of the
            current day, so an explicit ``start``/``end`` window is REQUIRED to
            return ``count`` historical bars — ``sort=desc`` + ``limit`` alone
            would only yield today's bars. We over-fetch by a margin and keep
            the newest ``count``.
          * The forming (incomplete) current-period bar is dropped so the BTC
            D1 EMA filter never computes EMA5/EMA10 over a partial candle
            (downstream does not itself filter on ``complete``).
        """
        timeframe = _GRANULARITY_MAP.get(granularity)
        if timeframe is None:
            raise ValueError(f"Unsupported granularity for Alpaca: {granularity!r}")
        delta = _GRANULARITY_DELTA[granularity]
        symbol = _to_alpaca_symbol(pair)
        now = datetime.now(timezone.utc)
        # Over-fetch: margin covers the dropped forming bar plus minor gaps.
        margin = max(5, count // 20)
        fetch_n = count + margin
        start = now - delta * fetch_n
        base_params = {
            "symbols": symbol,
            "timeframe": timeframe,
            "limit": int(fetch_n),
            "sort": "desc",
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": now.isoformat().replace("+00:00", "Z"),
        }
        raw_bars: list[dict] = []
        page_token: str | None = None
        for _ in range(6):  # bounded pagination guard
            params = dict(base_params)
            if page_token:
                params["page_token"] = page_token
            try:
                resp = await self._data.get(
                    "/v1beta3/crypto/us/bars", params=params
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "alpaca_candle_fetch_failed",
                    pair=pair,
                    granularity=granularity,
                    status=e.response.status_code,
                )
                raise
            body = self._decimal_json(resp)
            raw_bars.extend(body.get("bars", {}).get(symbol, []) or [])
            page_token = body.get("next_page_token")
            if not page_token or len(raw_bars) >= fetch_n:
                break
        # Bars are newest-first (sort=desc); build ascending, then drop the
        # forming bar so only closed candles reach the indicators.
        normalized = [
            self._normalize_bar(bar, granularity, now)
            for bar in reversed(raw_bars)
        ]
        closed = [c for c in normalized if c["complete"]]
        result = closed[-count:] if count else closed
        if len(result) < count:
            logger.warning(
                "alpaca_candles_thin",
                pair=pair,
                granularity=granularity,
                requested=count,
                returned=len(result),
            )
        return result

    @staticmethod
    def _decimal_json(resp: httpx.Response) -> dict:
        """Parse a JSON body preserving numeric precision as ``Decimal``.

        ``httpx.Response.json()`` coerces JSON numbers to float, losing the
        wire decimal before we can stringify it. Parsing the raw text with
        ``parse_float=Decimal`` keeps prices exact for ``Decimal()`` downstream.
        """
        return json.loads(resp.text, parse_float=Decimal)

    def _normalize_bar(
        self, bar: dict, granularity: str, now: datetime
    ) -> dict:
        """Alpaca bar ``{t,o,h,l,c,v,n,vw}`` -> OANDA candle dict.

        OHLC are emitted as STRINGS (from ``Decimal`` values parsed with
        ``parse_float=Decimal``) because ``CandleFetcher`` builds
        ``Decimal(mid["o"])`` — so prices stay wire-exact end to end.
        """
        start = self._parse_bar_time(bar["t"])
        delta = _GRANULARITY_DELTA.get(granularity)
        # A bar is complete once its period (keyed off the bar's open
        # timestamp) has fully elapsed. The forming current-period bar is
        # marked incomplete, matching OANDA's complete=False semantic.
        complete = True
        if delta is not None:
            complete = (start + delta) <= now
        return {
            "time": bar["t"],
            "mid": {
                "o": str(bar["o"]),
                "h": str(bar["h"]),
                "l": str(bar["l"]),
                "c": str(bar["c"]),
            },
            # Alpaca crypto volume is fractional base-asset units;
            # CandleFetcher coerces via int(). Volume is not used by the BTC
            # D1 EMA filter, so the truncation is harmless and documented.
            "volume": int(bar.get("v", 0) or 0),
            "complete": complete,
        }

    @staticmethod
    def _parse_bar_time(value: str) -> datetime:
        """Parse Alpaca's RFC-3339 bar timestamp to an aware UTC datetime."""
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # ── Pricing ────────────────────────────────────────────────
    async def get_pricing(self, pairs: list[str]) -> dict:
        """Latest bid/ask per pair, OANDA-shaped.

        Returns ``{"prices": [{"instrument", "bids":[{"price"}],
        "asks":[{"price"}], "time"}]}`` — the exact shape DataEngine reads
        (``prices[0]["bids"][0]["price"]`` / ``["asks"][0]["price"]``).

        Primary source is ``/latest/quotes`` (``bp``/``ap``). When a quote is
        absent or zero-priced, falls back to ``/latest/trades`` (``p``) using
        the trade price for both sides so the caller always gets a usable tick.
        """
        symbols = [_to_alpaca_symbol(p) for p in pairs]
        quotes = await self._fetch_latest_quotes(symbols)
        trades: dict | None = None
        prices: list[dict] = []
        for pair, symbol in zip(pairs, symbols):
            q = quotes.get(symbol) or {}
            bid = q.get("bp")
            ask = q.get("ap")
            ts = q.get("t")
            bid_bad = bid is None or Decimal(str(bid)) <= 0
            ask_bad = ask is None or Decimal(str(ask)) <= 0
            if bid_bad or ask_bad:
                # Quote missing/zero — fall back to last trade price (lazy fetch).
                if trades is None:
                    trades = await self._fetch_latest_trades(symbols)
                t = trades.get(symbol) or {}
                last = t.get("p")
                if last:
                    bid = ask = last
                    ts = t.get("t", ts)
            if not bid or not ask:
                logger.warning("alpaca_pricing_unavailable", pair=pair)
                continue
            prices.append(
                {
                    "instrument": pair,
                    "bids": [{"price": str(bid)}],
                    "asks": [{"price": str(ask)}],
                    "time": ts,
                }
            )
        return {"prices": prices}

    async def _fetch_latest_quotes(self, symbols: list[str]) -> dict:
        resp = await self._data.get(
            "/v1beta3/crypto/us/latest/quotes",
            params={"symbols": ",".join(symbols)},
        )
        resp.raise_for_status()
        return self._decimal_json(resp).get("quotes", {}) or {}

    async def _fetch_latest_trades(self, symbols: list[str]) -> dict:
        resp = await self._data.get(
            "/v1beta3/crypto/us/latest/trades",
            params={"symbols": ",".join(symbols)},
        )
        resp.raise_for_status()
        return self._decimal_json(resp).get("trades", {}) or {}

    # ── Account ────────────────────────────────────────────────
    async def get_account_summary(self) -> dict:
        """Fetch Alpaca account, normalized to OANDA-compatible summary keys.

        Crypto-spendable USD is ``non_marginable_buying_power`` (NOT
        ``buying_power``) — exposed both under that exact key and as a hint for
        the (future) crypto position sizer. ``equity`` is total account value.
        All numeric Alpaca fields are strings; we pass them through as strings.
        """
        resp = await self._trading.get("/v2/account")
        resp.raise_for_status()
        acct = resp.json()
        equity = acct.get("equity", "0") or "0"
        cash = acct.get("cash", "0") or "0"
        nmbp = acct.get("non_marginable_buying_power", "0") or "0"
        return {
            "id": acct.get("account_number", "alpaca"),
            "currency": acct.get("currency", "USD"),
            "balance": cash,
            "NAV": equity,
            "equity": equity,
            "non_marginable_buying_power": nmbp,
            "marginUsed": "0",
            "_broker": "alpaca",
        }

    # ── Positions ──────────────────────────────────────────────
    async def get_open_trades(self) -> list[dict]:
        """Not a valid reconciliation source in P1 — hard-fails by design.

        Spot crypto has no broker trade object carrying SL/TP, so there is no
        honest ``get_open_trades`` until the synthetic-trade table (P2) and the
        SEPARATE crypto reconciler (P3) exist. Returning raw ``/v2/positions``
        here under the broker-reconciler method name is exactly the footgun
        that caused the 2026-06-29 ghost incident (absence-as-closed). The
        crypto path must NEVER be reconciled by the OANDA trade-id reconciler.

        For a deliberate read-only inspection of live positions, call the
        explicitly-named :meth:`get_positions_diagnostic` instead.
        """
        raise NotImplementedError(
            "SpotCryptoClient.get_open_trades is unavailable until the "
            "synthetic-trade table (P2) + crypto reconciler (P3) exist. Use "
            "get_positions_diagnostic() for read-only inspection. See "
            "docs/ALPACA_CRYPTO_INTEGRATION.md §6."
        )

    async def get_positions_diagnostic(self) -> list[dict]:
        """Read-only/diagnostic snapshot of current Alpaca crypto positions.

        WARNING — NOT a reconciliation source. Never feed this to the OANDA
        reconciler or any absence-based close logic; a missing/empty snapshot
        is NOT proof a position closed (the 2026-06-29 ghost-bug class).

        Sizing reads ``qty_available`` (not ``qty``) so quantity held against a
        resting SELL order is not double-counted.
        """
        resp = await self._trading.get("/v2/positions")
        resp.raise_for_status()
        positions = resp.json() or []
        trades: list[dict] = []
        for pos in positions:
            symbol = pos.get("symbol", "")
            internal = _to_internal_pair(symbol)
            if internal not in self.config.ALPACA_CRYPTO_PAIRS:
                continue
            trades.append(
                {
                    "instrument": internal,
                    "symbol": symbol,
                    "side": pos.get("side", ""),
                    "qty": pos.get("qty", "0"),
                    "qty_available": pos.get("qty_available", pos.get("qty", "0")),
                    "avg_entry_price": pos.get("avg_entry_price", "0"),
                    "market_value": pos.get("market_value", "0"),
                    "unrealized_pl": pos.get("unrealized_pl", "0"),
                    "current_price": pos.get("current_price", "0"),
                    "_broker": "alpaca",
                }
            )
        return trades

    # ── Trading surface (deferred to P2/P3) ────────────────────
    async def place_market_order(
        self,
        pair: str,
        units: Decimal,
        sl: Decimal,
        tp: Decimal,
        client_request_id: str,
    ) -> dict:
        """Not available in P1. Entry txn + fill detection land in P2."""
        raise NotImplementedError(
            "SpotCryptoClient is read-only in Phase 1. Crypto order placement "
            "(stateful entry + software OCO) is built in P2/P3 — see "
            "docs/ALPACA_CRYPTO_INTEGRATION.md."
        )

    async def close_trade(self, broker_trade_id: str, pair: str = "") -> dict:
        """Not available in P1. Close/kill-switch lands in P3."""
        raise NotImplementedError(
            "SpotCryptoClient is read-only in Phase 1. Crypto close + "
            "kill-switch are built in P3 — see docs/ALPACA_CRYPTO_INTEGRATION.md."
        )

    async def stream_prices(self, pairs: list[str]):
        """Not available in P1. The data WS lands with the OCO supervisor (P3)."""
        raise NotImplementedError(
            "SpotCryptoClient price streaming (data WS) is built in P3 with the "
            "OCO supervisor — see docs/ALPACA_CRYPTO_INTEGRATION.md."
        )
        # Unreachable yield keeps this an async generator for interface parity.
        yield  # pragma: no cover

    async def close(self) -> None:
        """Close both HTTP clients."""
        await self._data.aclose()
        await self._trading.aclose()
