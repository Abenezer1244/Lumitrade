# Track 2 — Type Consolidation Audit (Assessment-Only)

**Date:** 2026-04-26
**Author:** Track-2 cleanup agent
**Scope:** Assessment only. No code edits. Cutover is 2026-04-27.

---

## Executive Summary

Lumitrade has a **single canonical type source per side** of the stack — `backend/lumitrade/core/enums.py` + `backend/lumitrade/core/models.py` for Python, and `frontend/src/types/{trading,system,future}.ts` for TypeScript. They are well-curated. The duplication problem is concentrated in two zones:

1. **Cross-stack drift** (HIGH risk, ~3 confirmed). Frontend string-literal unions silently fall behind when the backend adds a new enum member or changes casing convention. The `circuit_breaker.status` casing mismatch and the missing `TRAILING_STOP` member of `ExitReason` are real, not hypothetical.
2. **Frontend inline duplication** (LOW–MEDIUM risk). `interface Trade { ... }` is redeclared four separate ways across components and Next.js API routes — none of them imports from `types/trading.ts`. Several reports/intelligence types (`PairStat`, `SessionStat`, `RiskAssessment`, `WeeklyReport`, `WeekSummary`, `PeriodStats`) are declared **verbatim** in both an API route and the page that consumes it.

**Tally:** 3 cross-stack drift findings · 8 pure-duplicate clusters · 0 backend duplicates worth touching pre-cutover.
**Recommendation:** **DO NOT** edit `core/enums.py` or `core/models.py` before Monday's live flip. Track-2 work should land Tue–Thu post-cutover.

---

## CROSS-STACK DRIFT FINDINGS (highest priority)

### D1. `circuit_breaker.status` casing mismatch — REAL BUG, MEDIUM SEVERITY
- **Backend source of truth:** `backend/lumitrade/core/enums.py:114-119` — `CircuitBreakerState` values are UPPERCASE: `"CLOSED" | "OPEN" | "HALF_OPEN"`.
- **Backend emitter:** `backend/lumitrade/infrastructure/health_server.py:224,278` — emits `{"status": "CLOSED"}` (uppercase).
- **Frontend consumer type:** `frontend/src/types/system.ts:16` — declares `circuit_breaker: { status: "closed" | "open" | "half_open" }` (lowercase).
- **Frontend API shim:** `frontend/src/app/(dashboard)/api/system/health/route.ts:104,150` — passes through uppercase `"CLOSED"`.
- **Drift evidence:** values do **not** match. Any TS narrowing on `status === "closed"` is dead code; the raw runtime value is `"CLOSED"`. Today this causes silent UI degradation (status badge falls into "unknown" branches), not a crash.
- **Confidence:** 10/10. **Risk if fixed wrong:** 4/10 (a one-line union edit).
- **Recommendation tier:** **POST-CUTOVER (Tue 2026-04-29).** Fix on the frontend side: change `system.ts:16` union to UPPERCASE, then align any narrowing in `SystemStatusPanel.tsx`. Do NOT lowercase the backend — that propagates a breaking change into health probes and persisted logs.
- **Single source of truth target:** `frontend/src/types/system.ts` mirroring `core/enums.py::CircuitBreakerState`.

### D2. Frontend `ExitReason` missing `TRAILING_STOP` — REAL BUG, MEDIUM SEVERITY
- **Backend:** `backend/lumitrade/core/enums.py:58-67` — `ExitReason` includes `TRAILING_STOP`.
- **Frontend:** `frontend/src/types/trading.ts:6` — `ExitReason = "SL_HIT" | "TP_HIT" | "AI_CLOSE" | "MANUAL" | "EMERGENCY" | "UNKNOWN"`. **`TRAILING_STOP` is absent.**
- **Frontend live use:** `frontend/src/components/ui/NotificationCenter.tsx:38` — `if (type === "TRAILING_STOP") return true;` — uses the value as a string literal, bypassing the typed enum. This works at runtime but is invisible to type-checking.
- **Drift evidence:** the production database absolutely contains `exit_reason = 'TRAILING_STOP'` rows (trailing stop is a configured exit per session notes). Any `Trade.exit_reason: ExitReason` assignment from API data is implicitly losing type safety. A future `switch (t.exit_reason)` exhaustiveness check would skip the trailing-stop branch.
- **Confidence:** 10/10. **Risk if fixed wrong:** 1/10 (additive union member).
- **Recommendation tier:** **POST-CUTOVER (Tue 2026-04-29).** Add `"TRAILING_STOP"` to the `ExitReason` union in `trading.ts`.
- **Single source of truth target:** `frontend/src/types/trading.ts` ExitReason.

### D3. `OrderStatus` enum has no frontend equivalent — DEFERRED
- **Backend:** `core/enums.py:70-80` — 8 states (`PENDING`, `SUBMITTED`, `ACKNOWLEDGED`, `FILLED`, `PARTIAL`, `REJECTED`, `TIMEOUT`, `CANCELLED`).
- **Frontend:** No corresponding type. Trade-level `Trade.status` (`trading.ts:72`) is a different concept — only `"OPEN" | "CLOSED" | "CANCELLED"` (the trade lifecycle, not the broker order lifecycle). They share the value `"CANCELLED"` and that's the only overlap.
- **Risk:** Today, none — frontend never surfaces broker order state. Future risk: if anyone adds an "Order History" panel, they will hand-write the union and drift again.
- **Confidence:** 8/10. **Recommendation tier:** **DEFER**. Not a current bug. Document the deliberate split in a code comment when Trade type is next touched.

---

## PURE DUPLICATES (no drift yet — same shape in multiple files)

### P1. `interface Trade` declared 4× in frontend, none import from `types/trading.ts`
- `frontend/src/types/trading.ts:56` — canonical, full Trade row (~21 fields, properly typed).
- `frontend/src/components/analytics/ConfidenceOutcome.tsx:8` — 3-field local subset (`confidence_score`, `outcome`, `pnl_usd`).
- `frontend/src/app/(dashboard)/api/analytics/route.ts:19` — 6-field server-side subset.
- `frontend/src/app/(dashboard)/api/analytics/periods/route.ts:5` — 3-field server-side subset.
- `frontend/src/app/(dashboard)/api/journal/route.ts:5` — 9-field server-side subset (note: every field typed as bare `string`, no `| null`).
- **Shape compatibility:** all are field-name compatible with the canonical Trade — they're row-projection subsets. None contradicts canonical.
- **Drift risk:** MEDIUM. The journal route's `pnl_usd: string` (no `| null`) drifts from canonical `string | null`; if the column is ever NULL the UI silently shows `"null"`.
- **Confidence:** 10/10. **Risk to consolidate:** 3/10.
- **Recommendation tier:** **POST-CUTOVER.** Replace each local interface with `Pick<Trade, ...fields>` from `@/types/trading`.
- **Target:** `frontend/src/types/trading.ts` (already canonical).

### P2. `interface PairStat` / `SessionStat` / `RiskAssessment` / `WeeklyReport` — VERBATIM duplicate API↔page
- **API route:** `frontend/src/app/(dashboard)/api/intelligence/route.ts:20-58` — defines all 4.
- **Page consumer:** `frontend/src/app/(dashboard)/intelligence/page.tsx:19-57` — defines all 4 with **byte-identical** field names and types.
- **Drift risk:** HIGH (latent). These are the response contract between the route and the page; they MUST stay in sync but nothing enforces it.
- **Confidence:** 10/10. **Risk to consolidate:** 2/10.
- **Recommendation tier:** **POST-CUTOVER, EARLY**. Lift to `frontend/src/types/intelligence.ts` and import from both files. This is the safest pure duplicate to fix first — any senior reviewer would mandate it.
- **Target:** new `frontend/src/types/intelligence.ts`.

### P3. `interface WeekSummary` — VERBATIM duplicate API↔page
- `frontend/src/app/(dashboard)/api/journal/route.ts:17-34` and `frontend/src/app/(dashboard)/journal/page.tsx:16-33`.
- 16 fields, identical declaration order. Same risk profile as P2.
- **Recommendation tier:** **POST-CUTOVER**. Move to `frontend/src/types/journal.ts`.

### P4. `interface PeriodStats` + `type Tab` — duplicate dashboard panels
- `frontend/src/components/dashboard/TodayPanel.tsx:84` — `PeriodStats { pnl, trades, wins, winRate }`, `TABS = ["Today","Week","Month","All"]`.
- `frontend/src/components/dashboard/PerformanceSummaryCards.tsx:7` — same `PeriodStats` shape, but `TABS = ["Today","This Week","This Month","All Time"]`.
- **Drift evidence:** the `Tab` literals diverge — TodayPanel uses short names, PerformanceSummaryCards uses long names that match the API's response keys (`/api/analytics/periods` returns `"Today" | "This Week" | "This Month" | "All Time"`). TodayPanel maps short→long via `PERIOD_MAP` to compensate; this is an accidentally-coupled invariant.
- **Confidence:** 10/10. **Risk to consolidate:** 5/10 (touches API contract — careful).
- **Recommendation tier:** **POST-CUTOVER, after P2/P3**. Lift `PeriodStats` to a shared type; pick ONE Tab convention and remove the mapping.

### P5. `type AuthState` duplicated in login + signup
- `frontend/src/app/auth/login/page.tsx:9` and `frontend/src/app/auth/signup/page.tsx:9`. Byte-identical: `"idle" | "loading" | "success" | "error"`.
- **Recommendation tier:** **POST-CUTOVER**. Move to `frontend/src/types/auth.ts` or co-locate in a `lib/auth.ts`.

### P6. `interface Candle` (frontend chart) — local definition
- `frontend/src/components/analytics/PriceChart.tsx:7` — `{ time: number; open/high/low/close: number }`.
- Backend canonical `Candle` (`core/models.py:34-45`) uses `Decimal` and `datetime`, plus `volume`, `complete`, `timeframe`. Pure shape mismatch — these are DIFFERENT objects (chart-input vs broker-row).
- **False positive watchlist member.** Do NOT consolidate.

### P7. `interface NewsEvent` lite/full split
- `frontend/src/types/trading.ts:48` — full version with `currencies_affected`, `impact`, etc.
- No second declaration found. Backend `core/models.py:90-99` adds `event_id`, `minutes_until` already present in TS as `minutes_until`. Reasonably aligned.
- **No action.**

### P8. `interface PnlCellProps` / `Props` / `AnimatedNumberProps` etc. — component-local UI props
- ~40 small `interface XyzProps` declarations in components (`PnlDisplay.tsx`, `Badge.tsx`, etc.).
- These are React component prop bags. They are intentionally local and SHOULD NOT be consolidated.
- **False positive watchlist members.**

---

## FALSE-POSITIVE WATCHLIST (look duplicate, are intentionally separate)

| Item | Why it looks duplicate | Why it should stay separate |
|---|---|---|
| Frontend `Candle` (PriceChart) vs backend `Candle` | Same name | Frontend is chart-rendering input (numbers, epoch ms); backend is broker row (Decimal, ISO datetime, volume, completeness). Wire format is JSON; chart converts. |
| `Trade.status: "OPEN"\|"CLOSED"\|"CANCELLED"` (frontend) vs `OrderStatus` (backend) | Both mention status of an order/trade | These model two different lifecycles: trade-lifecycle vs broker-order-lifecycle. They overlap on `"CANCELLED"` only. |
| `interface Props` declared in many UI primitives | Same identifier | Each is a local React prop bag scoped to one file. Consolidating would require a global `UIProps` namespace nobody wants. |
| `RiskState` in `system.ts` vs `RiskState` in `core/enums.py` | Both unions | Values match exactly (`NORMAL`, `CAUTIOUS`, `NEWS_BLOCK`, `DAILY_LIMIT`, `WEEKLY_LIMIT`, `CIRCUIT_OPEN`, `EMERGENCY_HALT`). This is the gold-standard mirror — leave alone. |
| `Direction` / `Action` / `TradingMode` / `Outcome` / `Session` / `GenerationMethod` / `MarketRegime` / `CurrencySentiment` / `AssetClass` | Cross-stack mirrors | All values match between Python enums and TS unions. These mirrors are deliberate and currently in sync. |
| `interface ClaudeMessage` / `ClaudeResponse` in `coach/route.ts` | Could be hoisted | These are wire shapes for Anthropic's API, only used in one route. Lifting them would be premature abstraction. |

---

## SUGGESTED TARGET FILES (when work resumes post-cutover)

| Cluster | Move into | Phase |
|---|---|---|
| D1 (circuit_breaker casing) | `frontend/src/types/system.ts` (edit existing union) | Tue 2026-04-29 |
| D2 (TRAILING_STOP) | `frontend/src/types/trading.ts` (add to ExitReason) | Tue 2026-04-29 |
| P1 (Trade subsets) | Reuse `Trade` from `frontend/src/types/trading.ts` via `Pick<>` | Wed 2026-04-30 |
| P2 (Intelligence) | new `frontend/src/types/intelligence.ts` | Wed 2026-04-30 |
| P3 (WeekSummary) | new `frontend/src/types/journal.ts` | Wed 2026-04-30 |
| P4 (PeriodStats / Tab) | new `frontend/src/types/dashboard.ts` | Thu 2026-05-01 |
| P5 (AuthState) | new `frontend/src/types/auth.ts` | Thu 2026-05-01 |

---

## OUT OF SCOPE — DO NOT TOUCH PRE-CUTOVER

- `backend/lumitrade/core/enums.py`
- `backend/lumitrade/core/models.py`
- `backend/lumitrade/ai_brain/quant_engine.py::QuantSignal` (only consumer is QuantEngine itself)
- `backend/lumitrade/ai_brain/validator.py::ValidationResult` (only consumer is the validator)
- Any backend Pydantic config models (`backend/lumitrade/config.py` only — no domain Pydantic models exist)
