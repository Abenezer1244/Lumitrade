# Track 5 — Type Strengthening Assessment (Lumitrade)

**Date:** 2026-04-26 (T-1 day from LIVE cutover)
**Assessor:** Code Quality Analyzer
**Mode:** Assessment-only — no code edits performed
**Live cutover:** 2026-04-27 — all trading-path findings are DEFER tier

---

## Executive Summary

| Surface | Files w/ weak types | Total instances | Verdict |
|---|---:|---:|---|
| Backend (Python) | 48 | 257 | Material weakness — `dict`/`list` without parameters dominates |
| Frontend (TypeScript) | 2 | 3 | Effectively clean |
| Boundary `unknown` (legitimate) | 1 file | 3 sites | Protect from cleanup |

**Key finding:** Backend has 257 weak type sites concentrated in three patterns:
1. **Bare `dict`/`list`** (no type parameters) on internal functions — dominant smell, ~180 instances
2. **`dict[str, Any]` on Supabase row dicts** — semi-legitimate but most rows have a known schema (DB migrations 001–016)
3. **`# type: ignore[call-arg]` on `LumitradeConfig()`** — 19 instances, all stem from one Pydantic v2 init pattern; root cause is Pydantic settings, not a code defect

**Frontend is in excellent shape.** Only 3 weak sites total, two of which are at the Supabase Realtime boundary (legitimate `payload: any` since postgres_changes is dynamically typed).

**Critical-path observation:** `core/models.py` defines `SignalProposal`, `OrderResult`, and `IndicatorSet` with `dict` fields (no parameters) for `confidence_adjustment_log`, `timeframe_scores`, `indicators_snapshot`, `raw_response`. These are the contracts that flow through the entire pipeline (AIBrain → RiskEngine → ExecutionEngine). **Strengthening these would cascade into every consumer** — DEFER until post-cutover.

---

## High-Confidence Safe Replacements (non-trading-path, post-cutover)

These are safe to fix in a follow-up PR after Monday's cutover. None touch the active hot path.

### S-1. `infrastructure/db.py` — Supabase wrapper (entire file)
- **Lines:** 38, 46, 50, 62, 67, 75, 80, 88
- **Current:** `data: dict`, `filters: dict`, `-> dict`, `-> list`
- **Should be:** `data: Mapping[str, JsonValue]`, `filters: Mapping[str, str | int | bool | None]`, `-> list[dict[str, JsonValue]]` where `JsonValue = str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]`
- **Confidence:** 8/10 — Supabase rows are JSON-typed; the schema is known per migration files
- **Risk:** 4/10 — wrapper is used by every component, but the runtime contract is unchanged; only the static surface tightens
- **Why weak:** Original author treated Supabase as opaque; in practice rows match migration columns
- **Tier:** SAFE (post-cutover)

### S-2. `analytics/performance_analyzer.py` — analytics module (10 sites)
- **Lines:** 117, 152, 155, 178, 216, 308, 317, 346, 453, 495, 868, 1085
- **Current:** `trades: list[dict]`, `dict[str, Any]` for accumulators
- **Should be:** Define a `TradeRow = TypedDict("TradeRow", {"id": str, "pair": str, "direction": str, "entry_price": str, "exit_price": str, "pnl_usd": str, "pnl_pips": str, "outcome": str, "opened_at": str, "closed_at": str, ...})` matching `trades` table schema in migration 005. Accumulator dicts can use named TypedDicts (`HourBucket`, `PairStats`, `BucketDetail`).
- **Confidence:** 9/10 — schema is fully knowable from migrations
- **Risk:** 1/10 — analytics module is read-only and runs out-of-band of trading
- **Why weak:** Author was iterating on dashboard analytics quickly
- **Tier:** SAFE (post-cutover, highest ROI for type safety)

### S-3. `subagents/*.py` — agent context dicts (8 sites across files)
- **Files:** `base_agent.py:32`, `intelligence_subagent.py:48,128–130`, `market_analyst.py:49,63,64,102,113`, `post_trade_analyst.py:62,75,136,165`, `risk_monitor.py:61,74,80`, `onboarding_agent.py:51`
- **Current:** `async def run(self, context: dict) -> dict:` and helper params `indicators: dict`, `candles: list`, `trades: list`
- **Should be:** Define `AgentContext = TypedDict(...)` per agent. Common keys: `pair: str`, `indicators: IndicatorSet | dict[str, Decimal]`, `candles: list[Candle]`, `recent_trades: list[TradeRow]`, `account_summary: AccountContext`. Return type per agent is also stable (`{"summary": str, "concerns": list[str], ...}`).
- **Confidence:** 7/10 — the Phase-0-stub `BaseAgent` was meant to be polymorphic, but each concrete agent has a fixed schema
- **Risk:** 3/10 — subagents run periodically off the hot path
- **Why weak:** `BaseAgent` was written first as a plug-in interface; concrete agents inherited the loose signature
- **Tier:** SAFE (post-cutover)

### S-4. `infrastructure/health_server.py` — `_check_components` and friends
- **Lines:** 212, 306, 334, 354, 562, 725
- **Current:** `-> dict`, `body: dict = {}`, `update_fields: dict = {}`
- **Should be:** `ComponentHealth = TypedDict("ComponentHealth", {"status": str, "latency_ms": float}, total=False)`; `HealthResponse = TypedDict(...)` matching the JSON contract the frontend `/api/health` consumer expects
- **Confidence:** 9/10 — frontend health page already encodes this shape in TS
- **Risk:** 2/10 — health server is read-only HTTP endpoint
- **Why weak:** Quick iteration on observability surface
- **Tier:** SAFE (post-cutover) — bonus: keeps frontend types in sync via shared schema

### S-5. `infrastructure/secure_logger.py:62-67` — structlog processor
- **Current:** `def _scrub_processor(logger: Any, method: str, event_dict: dict) -> dict` and `scrub_recursive(obj: Any) -> Any`
- **Should be:** `logger: structlog.stdlib.BoundLogger`, `event_dict: structlog.types.EventDict`, recursive helper as `scrub_recursive(obj: object) -> object` with proper isinstance narrowing
- **Confidence:** 8/10 — structlog publishes these types
- **Risk:** 1/10 — formatter is library glue
- **Why weak:** structlog `Any` was the path of least resistance
- **Tier:** SAFE (post-cutover)

---

## Trading-Path Weak Types (assessment-only, DEFER until post-cutover)

**Rule:** No edits to these files before 2026-04-27 cutover per project deploy policy.

### T-1. `core/models.py` — pipeline contracts (CRITICAL)
- **Lines:** 86 (`to_dict() -> dict`), 213 (`confidence_adjustment_log: dict`), 219 (`timeframe_scores: dict`), 220 (`indicators_snapshot: dict`), 279 (`raw_response: dict`)
- **Current:** Bare `dict` on `SignalProposal` and `OrderResult` fields
- **Should be:**
  - `confidence_adjustment_log: dict[str, float]` (only floats stored — see `confidence.py:35`)
  - `timeframe_scores: dict[str, Decimal]` (M15/H1/H4 → score)
  - `indicators_snapshot: dict[str, str]` (already `to_dict()` produces `{k: str(v)}` at line 87)
  - `raw_response: Mapping[str, JsonValue]` (OANDA REST response — actually JSON)
  - `to_dict(self) -> dict[str, str]` (returns string values per impl at line 87)
- **Confidence:** 10/10 — implementations directly reveal the type
- **Risk:** 9/10 — `SignalProposal` is the contract between AIBrain and RiskEngine; tightening it transitively forces type updates in `validator.py`, `prompt_builder.py`, `risk_engine/engine.py`, `oanda_executor.py`. Every consumer touched.
- **Why weak:** Domain model was authored before downstream consumers were finalized; `dict` was a placeholder
- **Tier:** DEFER (post-cutover; coordinate with Track 1 if it touches models)

### T-2. `infrastructure/oanda_client.py` — broker REST wrapper
- **Lines:** 65, 82, 90, 97, 104, 118, 124, 130, 176, 214, 224, 293, 313
- **Current:** `-> list[dict]`, `-> dict`, `fill_tx: dict = {...}`
- **Should be:** Define `OandaCandle`, `OandaPriceTick`, `OandaAccount`, `OandaTrade`, `OandaOrderResponse`, `OandaTransaction` TypedDicts mirroring OANDA v3 REST schema (publicly documented). Boundary justification is weak — OANDA's schema is stable and versioned.
- **Confidence:** 9/10 — OANDA publishes the REST schema
- **Risk:** 9/10 — every order placement and reconciliation path consumes these dicts
- **Why weak:** Original author treated broker JSON as opaque to avoid coupling to OANDA-specific shapes; reasonable for v1 but the abstraction has leaked anyway (every consumer uses `.get("price")` etc.)
- **Tier:** DEFER (post-cutover; consider creating a `broker_types.py` module)

### T-3. `infrastructure/broker_interface.py` — abstract base
- **Lines:** 20, 24, 28, 32, 43, 47
- **Current:** Abstract methods declared with bare `dict` / `list[dict]`
- **Should be:** Same TypedDicts as T-2, made broker-agnostic (reuse for IG, Capital.com)
- **Confidence:** 8/10 — already implementing for 3 brokers (`oanda_client.py`, `ig_client.py`, `capital_client.py`); a unified TypedDict would be valuable
- **Risk:** 8/10 — touches all broker implementations
- **Tier:** DEFER (post-cutover)

### T-4. `state/manager.py:65,291` and `state/reconciler.py` — state dicts
- **Lines:** `manager.py:65` (`self._state: dict = {...}`), `manager.py:291` (`get(self) -> dict`), `reconciler.py:70-72,87,94,152,310`
- **Current:** Bare `dict`, `dict[str, dict]`, `list[dict]`
- **Should be:** `SystemState = TypedDict(...)` matching the 17 `_state` keys initialized at lines 65–83 (instance_id, trading_mode, risk_state, kill_switch_active, pairs, open_trades, daily_pnl, weekly_pnl, ...). For `reconciler.py`: `Ghost`, `Phantom`, `Match` TypedDicts.
- **Confidence:** 10/10 — `_state` schema is self-documenting at the init site
- **Risk:** 8/10 — state manager is the single source of truth for the engine
- **Tier:** DEFER (post-cutover)

### T-5. `execution_engine/engine.py` — `trade: dict` parameters
- **Lines:** 339, 470, 599, 686, 779, 810
- **Current:** `async def _check_paper_trade_exit(self, trade: dict)`, `_check_and_trail(self, trade: dict, price_map: dict[str, Decimal])`, `_mark_trade_closed(trade: dict)`, etc.
- **Should be:** Reuse `TradeRow` TypedDict from S-2 (the same Supabase `trades` row)
- **Confidence:** 9/10 — every `.get("pair")`, `.get("entry_price")`, etc. confirms the schema
- **Risk:** 10/10 — execution engine = trading-critical-path
- **Tier:** DEFER (post-cutover)

### T-6. `execution_engine/engine.py:873,897` — `# type: ignore[attr-defined]`
- **Current:** `await broker_client.get_open_trades()  # type: ignore[attr-defined]` and `.close_trade()  # type: ignore[attr-defined]`
- **Should be:** Remove ignore by typing `broker_clients: list[tuple[str, BrokerInterface]]` instead of `list[tuple[str, object]]` at line 867
- **Confidence:** 10/10 — `BrokerInterface` already declares both methods
- **Risk:** 8/10 — touches close_all_positions, the kill-switch path
- **Why weak:** Author typed as `object` instead of using the existing ABC
- **Tier:** DEFER (post-cutover; trivial fix, just not worth pre-cutover risk)

### T-7. `infrastructure/health_server.py` — 16x `# type: ignore[call-arg]`
- **Lines:** 338, 387, 456, 479, 512, 529, 619, 638, 677, 771, 820, 882, 1024, 1065, 1090 (also `validator.py:159`, `reconciler.py:337`)
- **Current:** `config = LumitradeConfig()  # type: ignore[call-arg]`
- **Root cause:** `LumitradeConfig` extends Pydantic v2 `BaseSettings` which infers required fields from env vars; mypy can't see env-var defaults
- **Should be:** Add a classmethod `LumitradeConfig.from_env() -> "LumitradeConfig"` that wraps the construction, keep the `# type: ignore` confined to that single line. 19 ignores → 1.
- **Confidence:** 9/10 — standard Pydantic settings idiom
- **Risk:** 2/10 — only changes a constructor pattern, no runtime change
- **Why weak:** Pydantic v2's mypy story for `BaseSettings` is incomplete
- **Tier:** SAFE (post-cutover) — cosmetic but high signal-to-noise improvement

---

## Boundary `unknown` Keep-List (PROTECT)

These three frontend sites use `unknown` correctly at runtime boundaries. Future cleanup passes must NOT replace them with concrete types.

### K-1. `frontend/src/app/(dashboard)/api/positions/route.ts:77`
- **Code:** `const openCount = (data as unknown[]).length;`
- **Why legit:** `data` came from `await supabase.from("trades")...` and the API surface deliberately doesn't enforce a row schema at this point — only the count is used
- **Action:** Keep as-is. (Optional: `data as Pick<TradeRow, "id">[]` if S-2 lands)

### K-2. `frontend/src/components/analytics/PriceChart.tsx:311,319`
- **Code:** `(ws as unknown as Record<string, unknown>).__pollTimer = timer;` and the symmetric read
- **Why legit:** Stashing an out-of-band poll-fallback timer on a WebSocket instance — there is no public WS API for this and adding a wrapper class is overkill for a 1-property bag
- **Action:** Keep as-is. The `unknown as` double-cast is the idiomatic TS way to monkey-patch a host object

### K-3. `frontend/src/hooks/useRealtime.ts:10,23` (`payload: any`)
- **Code:** `onData: (payload: any) => void;` and `(payload: any) => onDataRef.current(payload)`
- **Why legit:** Supabase Realtime `postgres_changes` payload shape depends on the runtime table being subscribed to; this hook is generic across tables. The contract is "the consumer knows what table they subscribed to and casts."
- **Action:** Soft-tighten possible but not required — `payload: RealtimePostgresChangesPayload<Record<string, unknown>>` from `@supabase/supabase-js` would be a slight win. Confidence 6/10. Tier: SAFE (post-cutover).

### Backend `Any` boundary protections
- `main.py:37` — `scrub_sentry_event(event: dict[str, Any], hint: dict[str, Any])` — Sentry SDK callback signature is `Any`; PROTECT
- `secure_logger.py:63,67` — structlog processor receives arbitrary `event_dict`; the `Any` on `scrub_recursive(obj: Any)` is correct because it does isinstance dispatch at runtime; PROTECT (cosmetic improvement possible: `obj: object`)
- `analytics/performance_analyzer.py:103` — `_to_decimal(value: Any) -> Decimal | None` — accepts `str | int | float | Decimal | None` from arbitrary DB columns; could be tightened to that union, but `Any` is defensible

---

## Findings Index (compact)

| ID | File:line | Current | Proposed | Conf | Risk | Tier |
|----|-----------|---------|----------|------|------|------|
| S-1 | infrastructure/db.py:38–88 | `dict`/`list` | `Mapping[str, JsonValue]` / `list[dict[str, JsonValue]]` | 8 | 4 | SAFE |
| S-2 | analytics/performance_analyzer.py (12 sites) | `list[dict]`, `dict[str, Any]` | `list[TradeRow]`, named TypedDicts | 9 | 1 | SAFE |
| S-3 | subagents/*.py (8 sites) | `context: dict -> dict` | per-agent `TypedDict` | 7 | 3 | SAFE |
| S-4 | infrastructure/health_server.py (6 sites) | `dict` | `ComponentHealth`, `HealthResponse` TypedDicts | 9 | 2 | SAFE |
| S-5 | infrastructure/secure_logger.py:62-67 | `Any`, `dict` | `EventDict`, `BoundLogger`, `object` | 8 | 1 | SAFE |
| T-1 | core/models.py:86,213,219,220,279 | bare `dict` on dataclass fields | typed dicts per inspection | 10 | 9 | DEFER |
| T-2 | infrastructure/oanda_client.py (13 sites) | `dict`/`list[dict]` | OANDA-schema TypedDicts | 9 | 9 | DEFER |
| T-3 | infrastructure/broker_interface.py (6 sites) | `dict`/`list[dict]` | shared broker TypedDicts | 8 | 8 | DEFER |
| T-4 | state/manager.py:65,291 + reconciler.py (8 sites) | `dict`, `list[dict]` | `SystemState`, `Ghost`, `Phantom`, `Match` | 10 | 8 | DEFER |
| T-5 | execution_engine/engine.py (6 sites) | `trade: dict` | `trade: TradeRow` | 9 | 10 | DEFER |
| T-6 | execution_engine/engine.py:867,873,897 | `list[tuple[str, object]]` + 2 ignores | `list[tuple[str, BrokerInterface]]` | 10 | 8 | DEFER |
| T-7 | health_server.py + 3 others (19 ignores) | `# type: ignore[call-arg]` | `LumitradeConfig.from_env()` factory | 9 | 2 | SAFE |
| K-1 | api/positions/route.ts:77 | `data as unknown[]` | KEEP | n/a | n/a | PROTECT |
| K-2 | components/analytics/PriceChart.tsx:311,319 | `unknown as Record` | KEEP | n/a | n/a | PROTECT |
| K-3 | hooks/useRealtime.ts:10,23 | `payload: any` | optional soft-tighten | 6 | 1 | PROTECT-ish |

---

## Recommendations

1. **Pre-cutover (today):** No changes. All findings are read-only assessment.
2. **Week of 2026-04-28 (post-cutover):** Land S-7 (config factory, 19→1 ignores), then S-1 → S-5 in any order. ~1 day of work.
3. **Sprint after stabilization:** Tackle T-1 → T-6 as a coordinated PR. Order: T-3 (broker interface) → T-2 (OANDA impl) → T-1 (models) → T-4 (state) → T-5 (engine) → T-6 (kill-switch ignores). ~2–3 days of work, blast radius confined to backend.
4. **Frontend:** Keep K-1, K-2, K-3 as-is. Optionally soft-tighten K-3 to `RealtimePostgresChangesPayload<Record<string, unknown>>`.

**Top hidden hazard:** `state/manager.py:65` `self._state: dict = {...}` is the live source of truth for the engine. Every consumer that does `state.get("kill_switch_active")` is one typo away from a silent bug. Tightening to `SystemState` TypedDict is the single highest-leverage backend type fix.
