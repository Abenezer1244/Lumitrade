"""
Lumitrade OANDA Client
========================
Read-only client (DATA key) + Trading client (TRADING key).
OandaTradingClient is ONLY instantiated by ExecutionEngine.
TLS verification always enabled. Circuit breaker wraps all calls.
Per BDS Section 4.1 + SS Section 5.1.
"""

import ssl
from decimal import Decimal

import httpx

from ..config import LumitradeConfig
from .broker_interface import BrokerInterface
from .secure_logger import get_logger

logger = get_logger(__name__)


def _create_secure_client(
    api_key: str, timeout: float = 10.0
) -> httpx.AsyncClient:
    """
    Create an HTTPX client with TLS verification enforced.
    Per SS Section 5.1. NEVER set verify=False.
    """
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    ssl_ctx.check_hostname = True

    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(
            connect=5.0,
            read=timeout,
            write=5.0,
            pool=2.0,
        ),
        verify=ssl_ctx,
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        ),
    )


class OandaClient(BrokerInterface):
    """Read-only OANDA client. Uses DATA key only."""

    def __init__(self, config: LumitradeConfig):
        self.config = config
        self._base_url = config.oanda_base_url
        self._stream_url = config.oanda_stream_url
        self._account_id = config.oanda_account_id
        self._client = _create_secure_client(config.oanda_api_key_data)

    async def get_candles(
        self, pair: str, granularity: str, count: int = 50
    ) -> list[dict]:
        """Fetch OHLCV candles from OANDA REST API."""
        url = f"{self._base_url}/v3/instruments/{pair}/candles"
        params = {"granularity": granularity, "count": count, "price": "M"}
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()["candles"]
        except httpx.HTTPStatusError as e:
            logger.error(
                "oanda_candle_fetch_failed",
                pair=pair,
                granularity=granularity,
                status=e.response.status_code,
            )
            raise

    async def get_pricing(self, pairs: list[str]) -> dict:
        """Get current bid/ask for one or more pairs.

        Routes spot crypto pairs (BTC_USD, ETH_USD) to the sub-account when
        configured — those instruments are not listed on the main forex account.
        Merges results into a single {"prices": [...]} dict.
        """
        spot_id = getattr(self.config, "oanda_spot_crypto_account_id", None)
        spot_set = getattr(self.config, "SPOT_CRYPTO_PAIRS", frozenset())
        spot_pairs = [p for p in pairs if p in spot_set and spot_id and spot_id != self._account_id]
        main_pairs = [p for p in pairs if p not in spot_pairs]

        all_prices: list = []
        if main_pairs:
            url = f"{self._base_url}/v3/accounts/{self._account_id}/pricing"
            resp = await self._client.get(url, params={"instruments": ",".join(main_pairs)})
            resp.raise_for_status()
            all_prices.extend(resp.json().get("prices", []))

        if spot_pairs:
            url = f"{self._base_url}/v3/accounts/{spot_id}/pricing"
            try:
                resp = await self._client.get(url, params={"instruments": ",".join(spot_pairs)})
                resp.raise_for_status()
                all_prices.extend(resp.json().get("prices", []))
            except Exception as e:
                logger.warning("spot_crypto_pricing_fetch_failed", pairs=spot_pairs, error=str(e))

        return {"prices": all_prices}

    async def get_account_summary(self) -> dict:
        """Fetch account balance, equity, margin from the main account."""
        url = f"{self._base_url}/v3/accounts/{self._account_id}/summary"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()["account"]

    async def get_account_summary_for(self, pair: str = "") -> dict:
        """Fetch account balance/equity/margin, routing spot crypto pairs to their sub-account.

        BTC_USD and ETH_USD positions live on the spot crypto sub-account;
        fetching balance from the main forex account would give the wrong
        equity base for BTC risk sizing.
        """
        account_id = self.config.account_id_for(pair) if pair else self._account_id
        url = f"{self._base_url}/v3/accounts/{account_id}/summary"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()["account"]

    async def get_account_summary_for_pairs(self, pairs: list[str]) -> dict:
        """Fetch aggregate summary across the unique OANDA accounts for pairs."""
        representatives: dict[str, str] = {}
        for pair in pairs:
            account_id = self.config.account_id_for(pair)
            representatives.setdefault(account_id, pair)
        if not representatives:
            representatives[self._account_id] = ""

        summaries = [
            await self.get_account_summary_for(pair)
            for pair in representatives.values()
        ]
        if len(summaries) == 1:
            return summaries[0]

        def _sum_decimal(key: str) -> str:
            total = sum(Decimal(str(summary.get(key, "0") or "0")) for summary in summaries)
            return str(total)

        nav_total = sum(
            Decimal(str(summary.get("NAV", summary.get("equity", "0")) or "0"))
            for summary in summaries
        )
        return {
            **summaries[0],
            "balance": _sum_decimal("balance"),
            "NAV": str(nav_total),
            "equity": str(nav_total),
            "marginUsed": _sum_decimal("marginUsed"),
            "unrealizedPL": _sum_decimal("unrealizedPL"),
            "openTradeCount": str(
                sum(int(summary.get("openTradeCount", 0) or 0) for summary in summaries)
            ),
        }

    async def get_open_trades(self) -> list[dict]:
        """Fetch all currently open trades from the main account."""
        url = f"{self._base_url}/v3/accounts/{self._account_id}/openTrades"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()["trades"]

    async def get_all_open_trades(self) -> list[dict]:
        """Fetch open trades from main account AND spot crypto sub-account (if configured).

        Merges results so the position monitor sees BTC/ETH trades placed on
        the separate spot crypto account alongside standard forex trades.
        """
        trades = await self.get_open_trades()
        spot_id = self.config.oanda_spot_crypto_account_id
        if spot_id and spot_id != self._account_id:
            try:
                url = f"{self._base_url}/v3/accounts/{spot_id}/openTrades"
                resp = await self._client.get(url)
                resp.raise_for_status()
                spot_trades = resp.json().get("trades", [])
                trades = trades + spot_trades
            except Exception as e:
                logger.warning("spot_crypto_open_trades_fetch_failed", error=str(e))
        return trades

    async def get_trade(self, trade_id: str, pair: str = "") -> dict:
        """Fetch a specific trade by ID (open or closed).

        Routes to the spot crypto sub-account when pair is a spot crypto instrument
        and the sub-account is configured.
        """
        account_id = self.config.account_id_for(pair) if pair else self._account_id
        url = f"{self._base_url}/v3/accounts/{account_id}/trades/{trade_id}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()["trade"]

    async def place_market_order(
        self,
        pair: str,
        units: Decimal,
        sl: Decimal,
        tp: Decimal,
        client_request_id: str,
    ) -> dict:
        """Not available on read-only client."""
        raise NotImplementedError(
            "OandaClient is read-only. Use OandaTradingClient for orders."
        )

    async def close_trade(self, broker_trade_id: str, pair: str = "") -> dict:
        """Not available on read-only client."""
        raise NotImplementedError(
            "OandaClient is read-only. Use OandaTradingClient for closing."
        )

    async def stream_prices(self, pairs: list[str]):
        """Async generator yielding real-time price ticks."""
        pairs_by_account: dict[str, list[str]] = {}
        for pair in pairs:
            pairs_by_account.setdefault(self.config.account_id_for(pair), []).append(pair)

        if len(pairs_by_account) == 1:
            account_id, account_pairs = next(iter(pairs_by_account.items()))
            async for line in self._stream_prices_for_account(account_id, account_pairs):
                yield line
            return

        import asyncio

        queue: asyncio.Queue[str] = asyncio.Queue()

        async def _pump(account_id: str, account_pairs: list[str]) -> None:
            async for line in self._stream_prices_for_account(account_id, account_pairs):
                await queue.put(line)

        tasks = [
            asyncio.create_task(_pump(account_id, account_pairs))
            for account_id, account_pairs in pairs_by_account.items()
        ]
        try:
            while True:
                yield await queue.get()
        finally:
            for task in tasks:
                task.cancel()

    async def _stream_prices_for_account(self, account_id: str, pairs: list[str]):
        """Async generator yielding price ticks for pairs on one OANDA account."""
        url = (
            f"{self._stream_url}/v3/accounts/{account_id}/pricing/stream"
        )
        params = {"instruments": ",".join(pairs)}
        async with httpx.AsyncClient(
            timeout=None,
            verify=True,
            headers={
                "Authorization": f"Bearer {self.config.oanda_api_key_data}",
                "Content-Type": "application/json",
            },
        ) as client:
            async with client.stream(
                "GET", url, params=params
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.strip():
                        yield line

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


class OandaTradingClient(OandaClient):
    """
    Trading-capable OANDA client. Uses TRADING key.
    ONLY instantiated by ExecutionEngine. Never import elsewhere.
    """

    def __init__(self, config: LumitradeConfig):
        super().__init__(config)
        self._trading_client = _create_secure_client(
            config.oanda_api_key_trading, timeout=15.0
        )

    async def place_market_order(
        self,
        pair: str,
        units: Decimal,
        sl: Decimal,
        tp: Decimal,
        client_request_id: str,
    ) -> dict:
        """Place market order with attached SL and TP."""
        account_id = self.config.account_id_for(pair)
        url = f"{self._base_url}/v3/accounts/{account_id}/orders"
        # OANDA requires specific price precision per instrument
        # JPY pairs: 3 decimals, XAU/BTC: 2 decimals, others: 5 decimals
        if "JPY" in pair:
            fmt_sl, fmt_tp = f"{sl:.3f}", f"{tp:.3f}"
        elif "XAU" in pair or "BTC" in pair:
            fmt_sl, fmt_tp = f"{sl:.2f}", f"{tp:.2f}"
        else:
            fmt_sl, fmt_tp = f"{sl:.5f}", f"{tp:.5f}"
        order = {
            "type": "MARKET",
            "instrument": pair,
            "units": str(units),
            "stopLossOnFill": {"price": fmt_sl},
            "clientExtensions": {"id": client_request_id},
        }
        # Only attach TP if provided — no TP lets trailing stop manage exit
        if tp and tp > 0:
            order["takeProfitOnFill"] = {"price": fmt_tp}
        body = {"order": order}
        resp = await self._trading_client.post(url, json=body)
        if resp.status_code >= 400:
            error_body = resp.text
            from ..infrastructure.secure_logger import get_logger
            get_logger(__name__).error(
                "oanda_order_error_detail",
                status=resp.status_code,
                body=error_body[:500],
                pair=pair,
                units=units,
                sl=fmt_sl,
                tp=fmt_tp,
            )
        resp.raise_for_status()
        return resp.json()

    async def close_trade(self, broker_trade_id: str, pair: str = "") -> dict:
        """Close a specific trade by OANDA trade ID."""
        account_id = self.config.account_id_for(pair) if pair else self._account_id
        url = (
            f"{self._base_url}/v3/accounts/{account_id}"
            f"/trades/{broker_trade_id}/close"
        )
        resp = await self._trading_client.put(url, json={"units": "ALL"})
        resp.raise_for_status()
        return resp.json()

    async def lookup_order_status(self, client_request_id: str, pair: str = "") -> dict | None:
        """
        Idempotent order lookup by client_request_id, used by OandaExecutor
        to recover from network timeouts during order placement.

        Per QTS spec 765: if place_market_order raises, the broker may have
        accepted the order anyway. Without this lookup, a restart later
        double-fills the position.

        Behavior:
          - Returns a response-shaped dict mimicking place_market_order's output
            (with orderCreateTransaction / orderFillTransaction or
            orderCancelTransaction) when the order is found in a terminal state.
          - Returns None when the order never reached OANDA (404), is still
            pending (caller must NOT proceed — let reconciler handle it later),
            or when the lookup itself fails. The caller treats None as
            'cannot confirm success — fail closed'.
        """
        account_id = self.config.account_id_for(pair) if pair else self._account_id
        url = (
            f"{self._base_url}/v3/accounts/{account_id}"
            f"/orders/@{client_request_id}"
        )
        try:
            resp = await self._trading_client.get(url)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
            return None

        if resp.status_code == 404:
            return None
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            return None

        order = resp.json().get("order") or {}
        state = (order.get("state") or "").upper()

        if state == "CANCELLED":
            # Clean rejection — surface it through _parse_response's cancel path.
            return {
                "orderCreateTransaction": {"id": order.get("id", "")},
                "orderCancelTransaction": {
                    "reason": order.get("cancelledReason", "CANCELLED"),
                    "rejectReason": order.get("rejectReason", ""),
                },
            }

        if state == "FILLED":
            # An OANDA order can resolve into one of three trade outcomes:
            # tradeOpenedID (new position), tradeReducedID (reduced existing),
            # or tradeClosedIDs (fully closed an existing). _parse_response
            # already handles all three; lookup must synthesize them too so
            # recovery isn't restricted to fresh-position fills.
            trade_opened_id = order.get("tradeOpenedID", "") or ""
            trade_reduced_id = order.get("tradeReducedID", "") or ""
            trade_closed_ids = order.get("tradeClosedIDs", []) or []
            trade_id = (
                trade_opened_id
                or trade_reduced_id
                or (trade_closed_ids[0] if trade_closed_ids else "")
            )
            if not trade_id:
                return None
            try:
                trade = await self.get_trade(trade_id, pair=pair)
            except Exception:
                return None

            fill_tx: dict = {
                "id": order.get("fillingTransactionID", trade_id),
                "price": trade.get("price", "0"),
                "units": trade.get("currentUnits", trade.get("initialUnits", "0")),
            }
            if trade_opened_id:
                fill_tx["tradeOpened"] = {"tradeID": trade_opened_id}
            if trade_reduced_id:
                fill_tx["tradeReduced"] = {"tradeID": trade_reduced_id}
            return {
                "orderCreateTransaction": {"id": order.get("id", "")},
                "orderFillTransaction": fill_tx,
            }

        # PENDING / TRIGGERED / unknown — order still in-flight or weird state.
        # Return None so the caller fails closed; reconciler will pick it up.
        return None

    async def modify_trade(
        self, broker_trade_id: str, sl: Decimal, tp: Decimal, pair: str = ""
    ) -> dict:
        """Modify SL/TP on an existing open trade.

        Uses same price precision as place_market_order (JPY=3dp, XAU=2dp,
        others=5dp) and omits takeProfit when tp is zero so OANDA never
        receives an invalid price. Logs the response body on 4xx so the
        exact OANDA errorCode is visible in structured logs.
        """
        account_id = self.config.account_id_for(pair) if pair else self._account_id
        url = (
            f"{self._base_url}/v3/accounts/{account_id}"
            f"/trades/{broker_trade_id}/orders"
        )
        # Match precision formatting from place_market_order
        if pair and "JPY" in pair:
            fmt_sl = f"{sl:.3f}"
            fmt_tp = f"{tp:.3f}" if tp and tp > 0 else None
        elif pair and ("XAU" in pair or "BTC" in pair):
            fmt_sl = f"{sl:.2f}"
            fmt_tp = f"{tp:.2f}" if tp and tp > 0 else None
        else:
            fmt_sl = f"{sl:.5f}"
            fmt_tp = f"{tp:.5f}" if tp and tp > 0 else None

        body: dict = {"stopLoss": {"price": fmt_sl}}
        if fmt_tp is not None:
            body["takeProfit"] = {"price": fmt_tp}

        resp = await self._trading_client.put(url, json=body)
        if resp.status_code >= 400:
            from ..infrastructure.secure_logger import get_logger
            get_logger(__name__).error(
                "oanda_modify_trade_error_detail",
                status=resp.status_code,
                body=resp.text[:500],
                broker_trade_id=broker_trade_id,
                pair=pair,
                sl=fmt_sl,
                tp=fmt_tp,
            )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close both HTTP clients."""
        await self._client.aclose()
        await self._trading_client.aclose()
