# Track 1 — Deduplication Assessment

**Owner:** assessment-only (no edits performed)
**Date:** 2026-04-26
**Cutover:** 2026-04-27 — recommendations are tiered to keep the trading path frozen until live-parity is verified.

---

## Executive Summary

- **15 duplication candidates identified** across backend Python and frontend Next.js. Backend has been disciplined (DB ops, logging, time parsing, pip math are already centralized). The remaining hot spots are (a) inline `replace("Z", "+00:00")` patterns that bypass the existing `parse_iso_utc` helper, (b) JPY/XAU price-precision branches re-derived in 4 files, and (c) frontend API route boilerplate that is copy-pasted across 22 routes.
- **Top systemic offender:** the *price-precision-by-instrument* rule (`JPY → 3dp, XAU → 2dp, others → 5dp`) appears in 4 separate files including two within `execution_engine/engine.py`. This is a trading-path business rule and a single source of truth (e.g., `utils/pip_math.precision_for(pair)`) is the highest-leverage backend dedup, but it must wait until POST-CUTOVER because every callsite is on the hot path.
- **Lowest-risk wins available immediately:** finishing the `parse_iso_utc` migration in 5 files (utility was added but legacy callsites remain), and extracting a `lib/api/supabase-fetch.ts` helper for the 22 frontend route handlers. Both are non-trading-path and have unit tests already.
- **Frontend has a `PIP_SIZE` table re-implemented in TypeScript** (`api/positions/route.ts`) — a copy of `backend/lumitrade/utils/pip_math.py`. This is duplicated *across the language boundary*, so consolidation requires a shared schema (e.g., generated JSON), not a function extraction. Defer to a separate cross-cutting initiative.
- **Backtest scripts intentionally mirror production quant code** (`backend/scripts/backtest.py`, `backtest_v2.py`) — these LOOK like duplicates of `quant_engine.py` but are explicitly labeled "live-mirror" snapshots. Do NOT consolidate; they exist precisely to detect production drift.

---

## Findings Table

| ID  | Files | What | Confidence | Risk | Recommendation | Rationale |
|-----|-------|------|-----------:|-----:|----------------|-----------|
| D-01 | `execution_engine/engine.py:291`, `execution_engine/engine.py:704`, `data_engine/calendar.py:130`, `state/manager.py:144`, `state/reconciler.py:258,263`, `infrastructure/health_server.py:911,1034` | Inline `s.replace("Z", "+00:00")` then `datetime.fromisoformat(...)` — duplicates the existing `utils/time_utils.parse_iso_utc()` helper which was created exactly to eliminate this idiom. | 10 | 7 (trading path) | POST-CUTOVER | Helper exists, contract documented, used by 4 modules already. Trading-path files (engine.py, state/*) need a careful swap because `parse_iso_utc` returns `None` on parse failure where some callsites currently raise. Verify each callsite's failure semantics before swapping. health_server.py instances are non-trading-path and could go IMPLEMENT NOW *if* not on the freeze. |
| D-02 | `execution_engine/engine.py:497-500`, `engine.py:561-564`, `ai_brain/quant_engine.py:308-313`, `infrastructure/oanda_client.py:181-186` | Price-precision branch by pair: `JPY → 3dp / XAU → 2dp / else → 5dp`. Same business rule, four hand-rolled implementations using slightly different idioms (`quantize` vs f-string `:.3f`). | 10 | 8 (trading path) | POST-CUTOVER | Add `utils/pip_math.price_precision(pair) -> int` and `quantize_price(value, pair) -> Decimal`. Risk is that `oanda_client.py` formats *strings sent to the broker* — a precision regression here gets orders rejected. Move only after one full live week without alerts. |
| D-03 | `frontend/src/app/(dashboard)/api/*/route.ts` (22 files) | Identical boilerplate: `dynamic = "force-dynamic"`, env-var presence check, `headers = { apikey, Authorization: Bearer }`, REST call to `${SUPABASE_URL}/rest/v1/<table>?...`, try/catch returning fallback. | 10 | 2 | IMPLEMENT NOW | Extract `frontend/src/lib/api/supabase-rest.ts` exposing `supabaseFetch(path, opts)` and a `withFallback(handler, fallback)` wrapper. Read-only routes; no trading impact; no tests broken because routes are thin. ~600 LOC removable. |
| D-04 | `frontend/src/app/(dashboard)/api/positions/route.ts:6-24` vs `backend/lumitrade/utils/pip_math.py:11-49` | `PIP_SIZE` dict and `pipValue` function re-implemented in TypeScript. Same pip sizes, same conditional structure (`endsWith('_USD')`, `startsWith('USD_')`). | 9 | 4 | DEFER | Same intent, but cross-language. Real fix is a generated `pairs.json` consumed by both runtimes — a separate workstream. Until then, add a comment in both files cross-linking each other so future edits stay in sync. |
| D-05 | `frontend/src/components/dashboard/MarketWatchlist.tsx:22-24`, `components/dashboard/PriceTicker.tsx:79`, `analytics/PriceChart.tsx:343`, `lib/formatters.ts:4` | Frontend price-precision branch: `JPY → 3dp / XAU → 2dp / else → 5dp` (mirror of D-02). `formatters.ts.formatPrice` already exists with this logic but four other components reimplement it inline. | 10 | 1 | IMPLEMENT NOW | `formatPrice(price, pair)` exists in `lib/formatters.ts`. Replace inline branches with the helper. `formatters.ts:formatPrice` is missing the XAU branch — fix that as part of consolidation (currently `pair?.includes("JPY") ? 3 : 5`, no XAU). |
| D-06 | `frontend/src/components/analytics/SessionAnalysis.tsx:38`, `analytics/PnlCalendar.tsx:21`, `analytics/PairBreakdown.tsx:25`, `dashboard/PerformanceSummaryCards.tsx:19`, `dashboard/InsightCards.tsx:59,69`, `dashboard/TodayPanel.tsx:13,17`, `app/(dashboard)/intelligence/page.tsx:88`, `app/(dashboard)/trades/page.tsx:73,76`, `app/(dashboard)/journal/page.tsx:83` | "Signed-dollar" formatter: `${value >= 0 ? "+" : ""}${value < 0 ? "-" : ""}$${Math.abs(value).toFixed(2)}` re-implemented inline ~10 times. `formatters.ts:formatPnl` exists but only returns `{ formatted, colorClass }` — components that don't need the color class re-roll. | 9 | 1 | IMPLEMENT NOW | Add `formatSignedUsd(value, opts?)` to `lib/formatters.ts` and replace inline expressions. Tiny diff per file; non-trading; visual regression risk near zero. |
| D-07 | `execution_engine/oanda_executor.py:89-168` vs `execution_engine/capital_executor.py:44-91` | `_parse_response()` shape: extract `orderFillTransaction`, check `orderCancelTransaction.reason`, build `OrderResult` with `pips_between` slippage, same fallback chain. ~70% structural overlap. | 7 | 9 (live-trading path) | POST-CUTOVER | The shapes match because both adopted the OANDA response schema, but Capital.com's API is currently *not* live (only OANDA is). Forcing a shared base class now would couple two brokers right before cutover with no test coverage on the Capital path. After live-parity proves stable, factor a `BaseExecutor._parse_oanda_style_fill()` helper. |
| D-08 | `analytics/performance_analyzer.py:103` vs `data_engine/indicators.py:22` | Both define a private `_to_decimal()` helper. **Different intents:** analyzer returns `Decimal \| None` for missing data; indicators returns `Decimal` with a `default` for NaN floats. | 5 | 4 | DO-NOT (different intents) | Same name, different semantics. Consolidating would force every caller to pick a default-vs-None contract; this is exactly the kind of "false-positive" the review brief warns about. Leave both. |
| D-09 | `data_engine/calendar.py:50,145`, `ai_brain/fallback.py:111`, `ai_brain/scanner.py:324` | `hashlib.sha256(s.encode()).hexdigest()[:N]` for ID generation. 4 callsites, same one-liner. | 6 | 2 | DEFER | Each callsite uses different slice lengths (`[:16]` vs full hex) and different inputs. The shared abstraction would be a 2-line wrapper that adds no clarity. Skip. |
| D-10 | `infrastructure/oanda_client.py:181-186` (string-format precision) vs everywhere else (`Decimal.quantize`) | Same business rule (D-02) but `oanda_client.py` formats as string for the wire protocol while engine.py uses `quantize` for DB persistence. Functionally equivalent precision, two implementations. | 9 | 8 (broker contract) | POST-CUTOVER | Bundle with D-02. The new helper should expose both `price_precision_dp(pair) -> int` (for f-string) and `quantize_price(value, pair) -> Decimal` (for DB). |
| D-11 | `execution_engine/oanda_executor.py:32`, `execution_engine/capital_executor.py:25` | `direction_str = order.direction.value if hasattr(order.direction, "value") else str(order.direction)` — the pattern from `lessons.md` "Enum Values from DB". Repeated in two executors and 3 ai_brain files (scanner.py:299, prompt_builder.py:156, prompt_builder.py:585). | 10 | 3 | IMPLEMENT NOW (utils/) | Add `core/enums.py:enum_value(x) -> str` (one-liner). Centralizes a known repeated bug pattern. Trading-path files use it but the helper itself is non-mutating — extract first, then swap callers in a follow-up batch. |
| D-12 | `infrastructure/oanda_client.py:24-34` returns `httpx.AsyncClient`; `infrastructure/capital_client.py:53` and `infrastructure/ig_client.py:52` instantiate their own. `data_engine/calendar.py:95` and `infrastructure/health_server.py:887,941` use ad-hoc `async with httpx.AsyncClient(timeout=...)`. | Inconsistent httpx client construction — some have factory, others inline. | 7 | 5 | POST-CUTOVER | Centralize as `infrastructure/http_client.py:make_async_client(timeout, verify=True)`. Risk: the OANDA client has carefully tuned timeouts/keepalive for streaming — don't pull it into a generic factory without preserving those. |
| D-13 | `infrastructure/oanda_client.py` `OandaClient` and `OandaTradingClient` (lines 53, 157) | Two classes, second extends the first. Each has its own `close()`. Looked at; not a duplicate — `OandaTradingClient` adds order-placement methods. | n/a | n/a | DO-NOT (false positive) | Inheritance is correct; Trading client adds methods. Not a dedup target. |
| D-14 | `backend/scripts/backtest.py:255-329` and `backend/scripts/backtest_v2.py:422-500` | Both define `ema_trend_signal`, `bollinger_signal`/`bb_revert_signal`, `momentum_signal`, `quant_evaluate` — near-identical to `ai_brain/quant_engine.py`. | 8 | 9 (test integrity) | DO-NOT (intentional) | These are explicit "live-mirror" snapshots used to regression-test the live engine. Consolidating into the production module breaks the very purpose: detecting drift. Add a docstring tag to make this intent louder, but do not merge. |
| D-15 | `ai_brain/chart_generator.py:163-166` | `float(c.open) if isinstance(c.open, Decimal) else float(c.open)` — both branches identical. Not duplication across files but a no-op ternary that survived a refactor. | 10 | 1 | IMPLEMENT NOW | Trivial: collapse to `float(c.open)` ×4. Non-trading. While here, the line itself is in a `if isinstance` chain that's pointless because `float(Decimal)` and `float(float)` both work. |

Confidence rubric: 10 = bit-identical or contract-identical. 7-9 = same intent, syntactic divergence. ≤6 = looks like a duplicate but inspection shows divergent semantics.

Risk rubric: trading-path files (`execution_engine/`, `risk_engine/`, `ai_brain/`, `state/`, `main.py`, `data_engine/`) auto-floor at 7. Frontend dashboard non-trading: 1-3.

---

## Top 5 High-Confidence Safe Consolidations (Diff Sketches)

### 1. D-15 — Collapse no-op ternary in `chart_generator.py` (5 min)

```diff
-                "Open": float(c.open) if isinstance(c.open, Decimal) else float(c.open),
-                "High": float(c.high) if isinstance(c.high, Decimal) else float(c.high),
-                "Low": float(c.low) if isinstance(c.low, Decimal) else float(c.low),
-                "Close": float(c.close) if isinstance(c.close, Decimal) else float(c.close),
+                "Open": float(c.open),
+                "High": float(c.high),
+                "Low": float(c.low),
+                "Close": float(c.close),
```
Risk: 1. Conf: 10. Both branches return the same value today. Bot-found dead code.

### 2. D-06 — Add `formatSignedUsd` to `lib/formatters.ts` and inline-replace (~30 min)

```diff
// lib/formatters.ts
+export function formatSignedUsd(value: number | string | null, opts?: { decimals?: number; abs?: boolean }): string {
+  if (value === null || value === undefined) return "—";
+  const n = typeof value === "string" ? parseFloat(value) : value;
+  if (isNaN(n)) return "—";
+  const decimals = opts?.decimals ?? 2;
+  const sign = n >= 0 ? "+" : "-";
+  return `${sign}$${Math.abs(n).toFixed(decimals)}`;
+}
```
Then in 8 components / 3 pages:
```diff
-{`${value >= 0 ? "+" : ""}$${Math.abs(value).toFixed(2)}`}
+{formatSignedUsd(value)}
```
Risk: 1. Conf: 9. Pure presentation; no trading-path impact; visual diff is zero.

### 3. D-05 — Use existing `formatPrice` everywhere + add XAU branch (~20 min)

```diff
// lib/formatters.ts
 export function formatPrice(price: string | number, pair?: string): string {
   const n = typeof price === "string" ? parseFloat(price) : price;
   if (isNaN(n)) return "—";
-  const decimals = pair?.includes("JPY") ? 3 : 5;
+  const decimals = pair?.includes("JPY") ? 3 : pair?.includes("XAU") ? 2 : 5;
   return n.toFixed(decimals);
 }
```
Then in `MarketWatchlist.tsx`, `PriceTicker.tsx`, `PriceChart.tsx`:
```diff
-if (pair.includes("JPY")) return price.toFixed(3);
-if (pair.includes("XAU")) return price.toFixed(2);
-return price.toFixed(5);
+return formatPrice(price, pair);
```
Risk: 1. Conf: 10. **Bonus:** fixes a latent bug where `formatPrice` itself misses the XAU branch and renders gold to 5 decimals.

### 4. D-03 — Extract `lib/api/supabase-rest.ts` (~2 hr)

```ts
// lib/api/supabase-rest.ts
import { NextResponse } from "next/server";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY = process.env.SUPABASE_SERVICE_KEY;

export function envReady(): boolean { return !!(URL && KEY); }

export async function supabaseFetch<T>(
  path: string,
  opts: { extraHeaders?: Record<string, string> } = {}
): Promise<T | null> {
  if (!envReady()) return null;
  const res = await fetch(`${URL}${path}`, {
    headers: { apikey: KEY!, Authorization: `Bearer ${KEY}`, ...opts.extraHeaders },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json() as Promise<T>;
}

export function withFallback<T>(handler: () => Promise<T>, fallback: T) {
  return async () => {
    try {
      const result = await handler();
      return NextResponse.json(result ?? fallback);
    } catch {
      return NextResponse.json(fallback);
    }
  };
}
```
Each route shrinks from ~40 LOC to ~10. Read-only API routes only — leave trade-mutating routes (`api/control/kill-switch/route.ts`) alone in this pass. Risk: 2. Conf: 10. Removes ~600 LOC.

### 5. D-11 — Extract `enum_value()` helper (~10 min) — backend, but on cold paths

```diff
# core/enums.py (append)
+def enum_value(x) -> str:
+    """Supabase round-trips enums as raw strings; production code reads
+    both cases. Centralises the `hasattr(x, 'value')` check noted in
+    lessons.md (Enum Values from DB)."""
+    return x.value if hasattr(x, "value") else str(x)
```
Then in `oanda_executor.py:32`, `capital_executor.py:25`, `ai_brain/scanner.py:299`, `ai_brain/prompt_builder.py:156,585`:
```diff
-direction_str = order.direction.value if hasattr(order.direction, "value") else str(order.direction)
+direction_str = enum_value(order.direction)
```
Risk: 3 (touches trading path *callsites*, but the helper is purely additive). Conf: 10.
**IMPORTANT:** Add the helper IMPLEMENT NOW; defer the trading-path callsite swaps to POST-CUTOVER.

---

## False-Positive Watchlist (Do NOT consolidate these in future passes)

These look like duplicates but are NOT — leaving them as-is is the correct call.

| Pattern | Files | Why it's not a true duplicate |
|---------|-------|-------------------------------|
| `_to_decimal()` private helpers (D-08) | `analytics/performance_analyzer.py`, `data_engine/indicators.py` | Different return contracts: `Decimal \| None` (analyzer) vs `Decimal` with default (indicators). Merging forces a contract decision on every caller. |
| Quant strategy functions in `backtest.py`, `backtest_v2.py` (D-14) | `backend/scripts/backtest*.py` and `ai_brain/quant_engine.py` | Backtests are *intentional snapshots* of production code — the whole point is detecting drift. Merging defeats the test. |
| `OandaClient` vs `OandaTradingClient` (D-13) | `infrastructure/oanda_client.py` | Inheritance chain (read-only client + trading subclass). Their `close()` overrides exist because the trading client owns extra resources. |
| `_parse_response()` in OANDA vs Capital executors (D-07) | `execution_engine/oanda_executor.py`, `capital_executor.py` | Looks structural-identical because Capital.com adopted OANDA's response schema. Capital path is currently *unproven in production*. Forcing a shared base class before the Capital path has live test coverage couples two brokers under risk. Revisit after Capital is verified. |
| `hashlib.sha256(...)[:N]` (D-09) | `data_engine/calendar.py`, `ai_brain/fallback.py`, `ai_brain/scanner.py` | Each callsite uses different slice lengths and inputs. Extracting a 2-line wrapper adds no clarity. |
| Multiple `async def close(self)` methods (8 files) | `infrastructure/*`, `ai_brain/*` | Each owns a *different* resource (httpx client, browser context, websocket). Same name, different intent. |
| Multiple `logger = get_logger(__name__)` declarations (40+ files) | All modules | Module-scope structlog binding is the documented pattern. This is correct, not duplication. |
| `db.client.table(...)` callsite searches return zero hits | All modules | Verified: ALL DB ops route through `infrastructure/db.py`'s `DatabaseClient` wrapper. The codebase is already disciplined here — no consolidation needed. |
| `datetime.now(timezone.utc)` (60+ callsites) | Everywhere | Calling `datetime.now(timezone.utc)` is the correct idiom; the centralisation `parse_iso_utc` covers parsing only, not "now". Do not be tempted to wrap `now()`. |

---

## Notes for Track-2 through Track-7

- The codebase already has 3 well-designed centralization helpers (`utils/pip_math.py`, `utils/time_utils.py`, `infrastructure/db.py`, `infrastructure/secure_logger.py`). Future cleanup tracks should *finish migrations* into these helpers before introducing new ones.
- Backend has very low duplication relative to size (≈75 .py files, ≈15 candidates, ~5 are real). Cleanup ROI is much higher on the frontend.
- Track 4 (architecture) should look at whether `ai_brain/quant_engine.py` and the two backtest mirrors should share a `Strategy` ABC instead of being three free-function families that drift.
