# Alpaca Crypto (Spot BTC/USD) Integration Spec

Status: PLAN (not built). Researched 2026-06-30 against current `docs.alpaca.markets/us/`,
Codex-reviewed for live-money safety. Build is **PAPER-first**. Effort: **Large**.

## 0. Why Alpaca (decision recap)
Across 7 researched venues (Alpaca, Coinbase Adv, Kraken, Gemini, tastytrade, IBKR, CCXT),
**no US crypto-spot venue offers a reliable atomic entry+SL+TP bracket** — so the engine must
build its own OCO/protection supervisor regardless of venue. Given that, Alpaca wins on the
remaining axes: cheapest fees (2–25 bps vs 1.2% Coinbase/Gemini), simplest auth (2 headers),
best data (native 15m/1h/4h/1d, free, real-time), a true paper endpoint, and $100-friendly
minimums. Coinbase's `trigger_bracket` is the only thing that could remove the supervisor —
unverified for US spot; kept as a future option (see §9).

## 1. THE decisive constraint — no two-legged OCO on Alpaca crypto
Alpaca **holds the full BTC position quantity against the first open SELL order**, and
**bracket/OCO order classes are NOT supported for crypto** (crypto = `market`/`limit`/`stop_limit`,
TIF `gtc`/`ioc` only). Therefore a full-size SL stop-limit **and** a full-size TP limit **cannot
both rest** at once — the second is rejected for insufficient `qty_available`.

**Design (risk-first):** rest the **SELL `stop_limit` (stop-loss) as the live broker order**
(survives a process/host crash) and **synthesize the take-profit in software** (supervisor watches
price; on TP hit → cancel resting SL → fire marketable IOC/market sell). The capital-protection
leg is always a real broker order; only the upside TP depends on the bot being alive.

## 2. BrokerInterface mapping (new SpotCryptoClient, async httpx — mirrors oanda_client.py)
| Method | Alpaca |
|---|---|
| `get_candles(pair, gran, count)` | `GET data.alpaca.markets/v1beta3/crypto/us/bars?symbols=BTC/USD&timeframe=15Min|1Hour|4Hour|1Day&limit=N` |
| `get_pricing(pairs)` | `GET .../v1beta3/crypto/us/latest/quotes` (bid `bp`/ask `ap`; fallback `/latest/trades` `p`) |
| `get_account_summary()` | `GET /v2/account` → `equity`, `cash`, **`non_marginable_buying_power`** (crypto-spendable USD; NOT `buying_power`) |
| `get_open_trades()` | `GET /v2/positions` → synthetic trade; size off **`qty_available`** (not `qty`) |
| `place_market_order(pair,units,sl,tp,cid)` | stateful txn — see §3 |
| `close_trade(id)` | cancel symbol's open orders → `DELETE /v2/positions/{symbol}`; kill-switch = `DELETE /v2/positions?cancel_orders=true` |
| `stream_prices(pairs)` | `wss://stream.data.alpaca.markets/v1beta3/crypto/us` (auth → subscribe quotes/bars) |

Note: data/WS use slash `BTC/USD`; trading paths historically slash-less `BTCUSD` (both accepted) — normalize both ways.

## 3. place_market_order as a stateful transaction (per Codex)
1. Write synthetic-trade row state=`OPENING`, keyed by `client_order_id` (≤128, account-unique → idempotent retries).
2. Preflight: `non_marginable_buying_power` ≥ cost; round qty to `min_trade_increment` 0.0001 (min 0.0001 BTC, ≤$200k/order); no existing unmanaged BTC / open synthetic trade.
3. `POST /v2/orders` market buy (`notional` USD or `qty`), `tif:gtc`, with `client_order_id`.
4. Await the `fill`/`partial_fill` event on the **trade_updates** account WS (don't trust the immediate `new` response). Read true `filled_qty` + `filled_avg_price`; for partials size exits off position `qty_available`.
5. Place the **SELL `stop_limit`** SL (limit_price ≤ stop_price, w/ slippage room). State=`OPEN_PROTECTED`.
6. If SL placement fails → **immediately market-close** the filled BTC, state=`FAILED_PROTECTION_CLOSED`.
7. If price already ≤ SL before protection is live → skip stale SL, **market-close** now.

## 4. OCO / protection supervisor (the core new component)
- Feed: **trade_updates account WS** (`wss://{paper-}api.alpaca.markets/stream` → `{"action":"auth",key,secret}` → `{"action":"listen","data":{"streams":["trade_updates"]}}`; events new/fill/partial_fill/canceled with `order/price/qty/position_qty`) + market-data WS for price (the TP trigger).
- Loop faster than the existing 60s monitor (TP is software-triggered; target ~1–5s price checks / event-driven).
- On TP hit → `DELETE` resting SL → fire marketable IOC/market SELL → await its fill.
- On SL `fill` event → tear down TP watcher, book close.
- Reconnect recovery: reconcile via `GET /v2/positions` + `GET /v2/orders` (resting SL is source of truth); re-place protection for any `OPENING/UNPROTECTED` row or market-close it.
- Treat the software-triggered TP leg as higher-risk: redundant price feed + heartbeat watchdog.

## 5. Synthetic-trade persistence (new table / migration)
Columns: client_order_id, broker entry order id, SL order id, side, intended qty, filled qty, avg price, sl, tp, state (`OPENING|OPEN_PROTECTED|FAILED_PROTECTION_CLOSED|CLOSED`), protection_status, last_broker_sync, signal_id, broker='alpaca'. This is the "open trade" the engine reconciles — spot has no broker position-with-SL/TP object.

## 6. Crypto reconciler (separate path — ghost-bug avoidance)
Do NOT reuse the OANDA trade-id reconciler. Reconcile synthetic bundles against balances + open orders + closed orders. **Never treat a missing/empty/errored snapshot as "closed"** (that absence-as-truth bug caused the 2026-06-29 ghost incident). `get_open_trades()` returns only internally-reconstructed protected synthetic trades with a completeness flag. Book P&L from FILL + CFEE activities, not a position realizedPL. Don't auto-classify stray BTC balance as a Lumitrade trade without a matching client_order_id.

## 7. 24/7 concerns
BTC already bypasses the forex session filter / risk-monitor / periodic-reconcile (code present). Still fix: daily-P&L midnight-UTC reset must attribute by close time (BTC trades span midnight); add the fast order-state loop (§4); kill-switch must cancel exits + flatten BTC.

## 8. Fees, env, limits, eligibility
- Fees: 2–25 bps on credited asset; posted as `CFEE` activity (`net_amount`) **end-of-day** → estimate at fill, reconcile later.
- Env: `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, `ALPACA_TRADING_BASE_URL` (paper↔live switch), `ALPACA_DATA_BASE_URL=https://data.alpaca.markets`, `ALPACA_DATA_WS_URL`, `ALPACA_PAPER`. Auth = headers `APCA-API-KEY-ID`/`APCA-API-SECRET-KEY`. Data host same for paper+live; only trading base URL + key pair change.
- Limits: trading 200/min; data REST 200/min free (1000 on $9 plan) — stream prices via WS to avoid throttling.
- US eligibility: **paper crypto works in ALL regions** (build/test freely). LIVE is state-gated — ~28 supported states; **NY, TX, FL, PA excluded** (verify operator's state at live signup). Paper-first is unaffected.
- Paper quirks to tolerate: random ~10% partial fills, no liquidity check, occasional transient "position does not exist" — reconciler must be tolerant.

## 9. Future option — Coinbase native bracket
If a paper-test confirms Coinbase `trigger_bracket` attaches atomic SL+TP to a US BTC-USD spot
market entry, it removes the §4 supervisor (the riskiest component). Keep the client behind the
same SpotCryptoClient interface so swapping is a config change. (CCXT covers both venues if
multi-venue is later desired.)

## 10. Phased build (all PAPER-gated)
- **P0** Operator creates Alpaca paper keys; verify crypto actually fills in paper.
- **P1** Read-only client (candles/pricing/account/positions) + wire BTC into scanner data path (D1 filter exists). No orders.
- **P2** Synthetic-trade table + entry txn (§3) + fill detection via trade_updates WS. Paper.
- **P3** OCO supervisor (§4) + crypto reconciler (§6) + kill-switch. Paper.
- **P4** Chaos tests: partial fill, SL-place failure, crash recovery, WS reconnect, paper position-not-found, duplicate client_order_id. Paper soak (≥ weeks / ≥ N trades).
- **P5** Tiny LIVE canary at 0.5% risk cap → then enable in live_pairs.

## Open items for operator
1. Your **US state** (decides live eligibility; paper unaffected).
2. Create **Alpaca paper API keys** to start P0/P1.
