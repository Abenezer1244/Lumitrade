# Track 3 — Dead Code Removal Audit

**Scope:** `backend/lumitrade/` + `frontend/src/`
**Date:** 2026-04-26 (eve of Monday 2026-04-27 LIVE cutover)
**Mode:** assessment-only, no edits, no deletions
**Tooling:** `knip` not installed (`npx knip` would require download); `vulture` not installed in current Python env. **Manual grep-based audit only.** Per CLAUDE.md rule 8, single greps may be incomplete; cross-checked with framework conventions and dynamic-import patterns.

---

## Executive Summary

| Category | Count | Notes |
|---|---:|---|
| **Confirmed dead** (manually verified, zero references) | **9** | 8 frontend components + 1 backend module |
| **Suspected dead, needs verification** | 4 | Mostly re-exported but never instantiated |
| **False-positive traps** (look dead, must NOT delete) | 6 categories | Subagent stubs, Phase-stubs, Next.js page conventions, etc. |
| **Out-of-scope but adjacent** | 5 zero-byte stray files | Already covered in track-7 |
| Total LOC removable, high-confidence | **~2,247 LOC frontend + ~330 LOC backend = ~2,577 LOC** | All optional, none on the LIVE-cutover critical path |

The codebase is unusually disciplined — almost every backend module has at least one inbound edge, and the subagent stub policy means many "looks-unused" Python classes are intentionally retained. Frontend has more genuine drift, mostly from a landing-page redesign (`ScrollSequence`, `FeatureCard`) and a dashboard layout that was iterated on faster than its component library was pruned (`MissionControl`, `MarketWatchlist`, `InsightCards`, `PerformanceSummaryCards`, `SystemStatusPanel`).

**Critical: do NOT touch any of this before Monday LIVE cutover.** Dead-code removal is zero-risk in theory and high-risk in practice (one wrong grep ⇒ broken import ⇒ engine fails to start). Defer to Tue 2026-04-29.

---

## CONFIRMED DEAD — high-confidence, safe to remove post-cutover

### Frontend (8 components, ~2,247 LOC)

For each: file, why static analysis flagged it, manual verification, recommendation.

#### 1. `frontend/src/components/landing/FeatureCard.tsx` (121 LOC)
- **Static signal:** exports `FeatureCard` default; zero `import .*FeatureCard` matches anywhere in `frontend/src`.
- **Manual verify:** grepped `FeatureCard` repo-wide — only matches are inside its own file. No dynamic `dynamic(() => import("@/components/landing/FeatureCard"))` either. Landing page (`app/page.tsx`) imports peer landing components but skips this one. Likely an early draft replaced by `FeatureBeams` + `StackedCards`.
- **Recommendation tier:** **POST-CUTOVER, low-risk.** Delete file. No tests, no DB, no runtime impact.

#### 2. `frontend/src/components/landing/ScrollSequence.tsx` (930 LOC)
- **Static signal:** exports `ScrollSequence` default; zero `import .*ScrollSequence` matches.
- **Manual verify:** the only reference repo-wide is the file itself (header comment + export line). Single largest component file in the frontend. Landing page (`app/page.tsx:20-30`) imports `LoadingScreen`, `KaraokeText`, `FeatureBeams`, `StackedCards`, `StatsCounter`, `Testimonials`, dynamic `ThreeScene` — but not `ScrollSequence`. Replaced by `ThreeScene` per session memory ("Three.js 3D scene, GSAP scroll animations").
- **Recommendation tier:** **POST-CUTOVER, low-risk.** Delete file. Largest single win.

#### 3. `frontend/src/components/dashboard/MissionControl.tsx` (343 LOC)
- **Static signal:** zero `import .*MissionControl` matches in `frontend/src`.
- **Manual verify:** `MissionControl.tsx` uses `useAgentEvents` and shows agent activity feed. The only mentions of "MissionControl" outside the file are in `docs/UI-REVIEW.md` (visual-audit notes). `app/(dashboard)/dashboard/page.tsx` imports `AccountPanel`, `TodayPanel`, `OpenPositionsTable`, `KillSwitchButton`, `NewsFeed`, `RiskUtilization` — but not `MissionControl`. Functionality overlaps with `ScanTimeline` (also uses `useAgentEvents`) which IS imported. Per session memory 2026-03-26 ("Mission Control built") this is a duplicate that was superseded by `ScanTimeline`.
- **Recommendation tier:** **POST-CUTOVER, low-risk.**

#### 4. `frontend/src/components/dashboard/MarketWatchlist.tsx` (171 LOC)
- **Static signal:** zero `import .*MarketWatchlist` matches.
- **Manual verify:** only mention outside the file is `tasks/cleanup/track-1-deduplication.md` (a sibling cleanup track flagging it as a candidate for shared price-fetching). Never rendered.
- **Recommendation tier:** **POST-CUTOVER, low-risk.**

#### 5. `frontend/src/components/dashboard/InsightCards.tsx` (122 LOC)
- **Static signal:** zero `import .*InsightCards` matches.
- **Manual verify:** confirmed by full-repo grep — only mention is its own export line. No tests reference it.
- **Recommendation tier:** **POST-CUTOVER, low-risk.**

#### 6. `frontend/src/components/dashboard/PerformanceSummaryCards.tsx` (147 LOC)
- **Static signal:** zero `import .*PerformanceSummaryCards` matches.
- **Manual verify:** the only references repo-wide are inside the file itself plus `tasks/cleanup/track-2-type-consolidation.md`, which calls out the `Tab` literal drift between this component and `TodayPanel.tsx` — a problem that **dissolves** if this component is removed (it's a stale duplicate of `TodayPanel`).
- **Recommendation tier:** **POST-CUTOVER, low-risk.** Removing this also closes a Track-2 finding.

#### 7. `frontend/src/components/dashboard/SystemStatusPanel.tsx` (308 LOC)
- **Static signal:** zero `import .*SystemStatusPanel` matches in current `frontend/src`.
- **Manual verify:** mentioned heavily in `docs/specs/Lumitrade_FDS_v2.0.md` (spec calls for it) and `docs/UI-REVIEW.md` (UI critique), but neither is an importer. Dashboard page now uses `RiskUtilization` (which itself calls `useSystemStatus`) instead. The Track-2 doc notes this file's `text-xs` styling drift — same dissolution-on-removal benefit as #6.
- **Recommendation tier:** **POST-CUTOVER, MEDIUM-risk.** Spec parity check first — the FDS spec still calls for this panel; confirm with PM whether the current `RiskUtilization`-only layout is the new design intent.

#### 8. `frontend/src/types/future.ts` (entire file)
- **Static signal:** zero `import .*future` matches anywhere in `frontend/src`.
- **Manual verify:** file is a "future feature" type bag (`MarketRegime`, `CurrencySentiment`, `AssetClass`, `RuinAnalysis`). Sister `types/system.ts` and `types/trading.ts` ARE used; this one isn't. Some types overlap with values now used inline elsewhere.
- **Recommendation tier:** **POST-CUTOVER, low-risk.** OR keep as documentation-only (small file). PM call.

### Backend (1 module, ~330 LOC)

#### 9. `backend/lumitrade/infrastructure/ig_client.py` (330 LOC)
- **Static signal:** zero `from .ig_client`, `import ig_client`, `IGClient`, `IGMarketsClient` matches anywhere in product code, tests, scripts, or supervisord.conf.
- **Manual verify:** the only matches repo-wide are inside the file itself. Originally written for IG Markets / tastyfx (US gold trading) per file docstring. Fully superseded by `infrastructure/capital_client.py` (Capital.com), which IS wired into `main.py:213` and `execution_engine/engine.py:868`. Per memory note "IBKR Pending — gold via Capital.com active", the IG path was abandoned.
- **Recommendation tier:** **POST-CUTOVER, low-risk.** Delete file. **Verify with founder first** — if there's any plan to revive IG (e.g., Capital.com outage backup), keep it. Otherwise it's a 330-LOC distraction every time someone greps for "gold" or "broker."

---

## SUSPECTED DEAD — needs human verification

### S1. `backend/lumitrade/risk_engine/state_machine.py` — class `RiskStateMachine`
- **Signal:** declared, re-exported in `risk_engine/__init__.py`, but **never instantiated** outside the file. No `RiskStateMachine(` calls anywhere.
- **Caveat:** `risk_engine/engine.py` performs the equivalent state-transition logic inline (CAUTIOUS, NORMAL, RECOVERY transitions). The state machine class may be a Phase-1 abstraction the engine outgrew. Could also be a **public API for external callers / tests yet to be written.** Risk monitor agent and risk_engine.engine both have their own state logic.
- **Recommendation tier:** **POST-CUTOVER, MEDIUM-risk.** Confirm with backend dev: is this referenced via `risk_engine.RiskStateMachine` from any subagent or future-feature path? If no, remove class + `__init__.py` re-export. If yes, add a doc-comment explaining the re-export is intentional.

### S2. `backend/lumitrade/analytics/performance_context_builder.py` — class `PerformanceContextBuilder`
- **Signal:** zero importers. Only matches are docs/specs and a `tasks/todo.md` checklist item.
- **Caveat — DO NOT DELETE.** Per `docs/specs/Lumitrade_BDS_v2.0.md §15.2`, this is an **explicit Phase-4 stub** with exactly the silent-no-op contract called out by CLAUDE.md rule 6. Removing it would violate the spec contract. See false-positive section #2 below.
- **Recommendation tier:** **DO NOT REMOVE.** Add a `# Phase-stub per BDS §15.2` comment at top of file so the next dead-code audit doesn't re-flag it.

### S3. `backend/lumitrade/api/__init__.py`, `fund/__init__.py`, `marketplace/__init__.py` (3 empty packages)
- **Signal:** all three packages are bare `__init__.py` with zero bytes; never `from lumitrade.api import …` etc.
- **Caveat:** package directories with empty `__init__.py` are commonly **placeholders for future feature work** and have near-zero cost. Removing them risks breaking a future import that was already being typed in someone's branch. Empty packages also act as namespace reservations.
- **Recommendation tier:** **POST-CUTOVER, very-low-risk to remove**, but reward is tiny. Recommend leaving alone unless a follow-up "directory hygiene" pass targets them explicitly.

### S4. `backend/lumitrade/main.py:622` — reference to `self.oanda_data` (NOT dead code, dead REFERENCE)
- **Signal:** `_risk_monitor_loop` calls `self.oanda_data.get_pricing(...)` but `OrchestratorService` only sets `self.oanda` and `self.oanda_trade` — `self.oanda_data` is never assigned.
- **Manual verify:** confirmed — single match in entire backend. This will raise `AttributeError` the first time `_risk_monitor_loop` actually has open trades to monitor. Currently masked by the broad `except Exception as e: logger.warning("risk_monitor_loop_error", ...)` two lines below.
- **NOT dead code — it's a runtime bug.** Out of Track-3 scope, but worth flagging to whoever owns runtime correctness (likely Track 6 — error handling).
- **Recommendation tier:** Forward to Track 6 or open a separate ticket. Not a Track-3 fix.

---

## FALSE-POSITIVE TRAPS — protect from future cleanup passes

These look unreferenced to a naive grep but are LIVE via framework conventions, dynamic imports, or spec contracts. Future audits MUST skip these.

### FP1. All seven Next.js `(dashboard)/<feature>/page.tsx` "Coming Soon" stubs
- `api-access/page.tsx`, `api-keys/page.tsx`, `backtest/page.tsx`, `coach/page.tsx`, `copy/page.tsx`, `intelligence/page.tsx`, `journal/page.tsx`, `marketplace/page.tsx`
- **Why they look dead:** Sidebar `NAV_ITEMS` only lists 5 routes (dashboard, signals, trades, analytics, settings); no static import of these 8 page files exists.
- **Why they ARE live:** Next.js App Router auto-discovers any `page.tsx`, `layout.tsx`, `route.ts`, `loading.tsx`, `error.tsx`, `not-found.tsx`, `middleware.ts` in `app/`. They're reachable via direct URL navigation (`/coach`, `/journal`, etc.) and link-sharing. Track 7 also calls these out as a UX decision, not dead code.
- **Protect rule:** Anything matching `app/**/<conventional-filename>.{tsx,ts}` is reached by Next.js router, full stop.

### FP2. `analytics/performance_context_builder.py` and the rest of the **Phase-stub family**
- Per BDS §15.2 and CLAUDE.md rule 6: "All stubs are silent no-ops — return safe defaults, never raise." Phase-stubs are the architectural contract; absence of importers is **expected** until the phase is implemented.
- Other likely Phase-stubs to NOT delete even if unreferenced: `data_engine/regime_classifier.py` (referenced — safe), `risk_engine/correlation_matrix.py` (referenced — safe), `ai_brain/consensus_engine.py` (referenced from main.py — safe), `ai_brain/sentiment_analyzer.py` (referenced from scanner — safe).

### FP3. **All of `subagents/`** even when an individual file looks unimported
- CLAUDE.md is explicit: subagent stubs may be "wired in via main.py orchestration or registered dynamically." Confirmed: `SubagentOrchestrator` in `subagents/subagent_orchestrator.py` imports all 5 subagents (`IntelligenceSubagent`, `MarketAnalystAgent`, `OnboardingAgent`, `PostTradeAnalystAgent`, `RiskMonitorAgent`). Plus `OnboardingAgent` is also dynamically imported inside `infrastructure/health_server.py:454`. **Do not remove** any file in `subagents/`.

### FP4. `backend/lumitrade/__main__.py`
- Looks like a 4-line nothing file. It IS the `python -m lumitrade` entry point and is referenced by `supervisord.conf` indirectly via the `lumitrade.main` module. Do not delete.

### FP5. Test fixtures and `conftest.py`
- `backend/tests/conftest.py` and the `__init__.py` files in `tests/`, `tests/unit/`, `tests/integration/`, `tests/chaos/`, `tests/security/`, `tests/performance/`, `tests/e2e/`, `tests/future/` are pytest-discovered (not statically imported). Do not delete.

### FP6. Performance / future-feature tests
- Tests under `tests/future/` are deliberately skipped via `addopts = ... -m "not future and not live"` in `pyproject.toml`. Empty/skipped does not mean dead.

---

## Recommendation tiering & sequencing

| Tier | Items | Trigger |
|---|---|---|
| **Tier 0 — DO NOT TOUCH before Monday LIVE cutover** | Everything in this report | LIVE goes 2026-04-27. Zero non-essential edits. |
| **Tier 1 — Tue 2026-04-29 morning, low-risk** | Confirmed-dead items 1, 2, 4, 5, 6, 8 (frontend components + `types/future.ts`) | One commit per file, run `next build` and Playwright e2e between each. |
| **Tier 2 — Tue 2026-04-29 PM, requires PM/founder confirmation** | Item 3 (`MissionControl`), 7 (`SystemStatusPanel`), 9 (`ig_client.py`) | Spec parity check + founder OK on IG retirement. |
| **Tier 3 — Wed+ 2026-04-30, requires backend dev review** | S1 (`RiskStateMachine`) | Confirm no future-feature use. |
| **Never** | S2 (`PerformanceContextBuilder`), all FP1–FP6 | Add comments to make their stub status visible. |

---

## Methodology disclosure

1. **No `knip`, no `vulture`** — both tools were unavailable in the environment. All findings are grep + manual cross-reference.
2. **Single-grep warning (per CLAUDE.md rule 10):** I checked each candidate with at least three search variants (snake_case, PascalCase, dot-import, dynamic-import, string literal). Findings labeled "Confirmed dead" had every variant return zero hits except inside the candidate file itself.
3. **Framework conventions honored:** Next.js App Router files explicitly excluded from dead-code candidates. pytest-discovered conftest/`__init__.py` excluded.
4. **Context-decay safeguard:** verified each candidate file actually exists on disk via `wc -l` before claiming it as removable.
5. **Spec cross-reference:** every backend candidate was greppped against `docs/specs/` to detect Phase-stub contracts (caught `PerformanceContextBuilder`).
