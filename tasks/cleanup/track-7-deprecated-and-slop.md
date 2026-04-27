# Track 7 — Deprecated Code & AI Slop Audit

**Scope:** `backend/lumitrade/` + `frontend/src/`
**Date:** 2026-04-26 (eve of Monday 2026-04-27 LIVE cutover)
**Mode:** assessment-only, no edits

---

## Executive Summary

| Category | Count | Severity |
|---|---:|---|
| Stray zero-byte / shell-redirect debris files (repo root + backend) | 22 | Cleanup, harmless |
| One-shot helper scripts stranded in `backend/` root | 2 | Cleanup |
| AI-narration "Per Codex round-X finding #Y" comments | 83 across 19 files | High slop, see protect notes |
| Stale `Phase 2 TODO:` / `Phase 3 TODO:` headers on now-implemented modules | 3 files | Stale narration |
| `Coming Soon` dashboard pages still routable | 7 routes | UX decision (per Wave-3 task 14, was unchecked) |
| Deprecated API fallback still live | 1 (`api/system/health/route.ts`) | Verify usage |
| Commented-out code blocks in `.py`/`.ts` source | **0** | Clean |
| `_old` / `_v2` / `_new` source files in product code | **0** | `backtest_v2.py` is the live file (see protect-list) |
| `# TODO`, `# FIXME`, `# HACK` outside intentional Phase markers | **0** in product code (frontend), **3** in backend (all stale headers, not code) | Clean |
| `NotImplementedError` raised in product code | 2 (both intentional, see protect-list) | OK |
| Renamed-variable trails (`_old_x`, `x_v2`, `x_new` symbols) | 0 in product code | Clean |

The codebase is **structurally clean** — no commented-out blocks, no `_old.py` shadow files, no semantic duplicates. The dominant slop pattern is **review-history narration** ("Per Codex round-2 review of finding #4") which appears 83 times and reads like a changelog embedded in production code.

---

## Confirmed Legacy / Deprecated (safe to remove)

### 1. Zero-byte shell-redirect debris (22 files)

These are accidental output of broken PowerShell pipes (e.g. `... > 0` instead of `... > out.txt`), confirmed by 0-byte size and meaningless names. None are tracked by git's tracked set as content; all show up in `git status` as untracked. **Verification:** all files are 0 bytes; not referenced anywhere.

Repo root:
- `C:\...\Lumitrade\99` (0 bytes, 2026-04-25)
- `C:\...\Lumitrade\0.65)`
- `C:\...\Lumitrade\CheckResult`
- `C:\...\Lumitrade\Engine`
- `C:\...\Lumitrade\PriceTick`
- `C:\...\Lumitrade\dict`
- `C:\...\Lumitrade\expires_at`
- `C:\...\Lumitrade\list[str]`
- `C:\...\Lumitrade\state)`
- `C:\...\Lumitrade\web.Response`

Backend root:
- `C:\...\Lumitrade\backend\0` (0 bytes)
- `C:\...\Lumitrade\backend\2` (0 bytes)
- `C:\...\Lumitrade\backend\dashboard` (0 bytes — collision risk with concept "dashboard")
- `C:\...\Lumitrade\backend\engine` (0 bytes — collision risk with concept "engine")
- `C:\...\Lumitrade\backend\DROP`
- `C:\...\Lumitrade\backend\ExecutionError`
- `C:\...\Lumitrade\backend\TradingMode`
- `C:\...\Lumitrade\backend\True`
- `C:\...\Lumitrade\backend\web.Response`

**Recommendation:** delete all. None are imported, none are referenced, none have content. They pollute `git status`, IDE file trees, and grep results.

### 2. One-shot diagnostic scripts at the wrong path

- `C:\...\Lumitrade\backend\_track4_cycle_scan.py` (Tarjan SCC scanner for circular imports)
- `C:\...\Lumitrade\backend\_track4_deferred_scan.py` (find lazy in-function imports)

These are real, working tools written for the cleanup audit. The leading-underscore + `_track4_` prefix marks them as throwaway scripts. They should either move to `backend/scripts/audit/` (if kept) or be removed after Track 4's report is filed. **Verification:** not imported by `lumitrade.*`; runnable as standalone modules via `python backend/_track4_cycle_scan.py`.

### 3. Stale Phase-marker headers on completed modules

These docstring/comment headers describe the file as a stub, but the implementation is fully present:

| File | Line | Stale text | Reality |
|---|---:|---|---|
| `backend/lumitrade/subagents/intelligence_subagent.py` | 8-13 | `Phase 2 TODO: Integrate real news API … Add caching … Store reports in DB` | Caching via `intelligence_reports` table is implemented (lines 62-74, 96-108); calendar fetch implemented (lines 158-167) |
| `backend/lumitrade/subagents/onboarding_agent.py` | 7-12 | `Phase 2 TODO: Persist onboarding_state in DB … Add validation … interactive tour` | DB persistence implemented (lines 64-81, 119-137); only frontend tour is missing |
| `backend/lumitrade/analytics/performance_analyzer.py` | 7-8 | `Phase 3 TODO: _evolve_prompt_instructions, _update_session_filters, _update_confidence_thresholds remain as silent no-op stubs` | All three methods are fully implemented (lines 853-1176, ~325 lines of real analysis) |

**Recommendation:** delete the stale TODO blocks from the docstrings. Keeping them is misleading to anyone reading the file ("oh this is a stub, I'll go look elsewhere") when in fact it's done.

---

## AI Slop Comments (rewrite or DELETE)

### The "Per Codex round-X finding #Y" pattern (83 occurrences across 19 files)

This is the dominant slop pattern in the codebase. Recent commits (`fix: address all 4 Codex round-4 findings`, `…round-3…`, `…round-2…`, `…follow-up…`) left a fossil layer of comments tying production code to the review session that produced it. Examples:

| File | Line | Current comment | Useful rewrite |
|---|---:|---|---|
| `backend/lumitrade/execution_engine/engine.py` | 79 | `# kill check. Per Codex round-2 review of finding [high] #4.` | `# Refresh from DB so HTTP-endpoint kill-switch activations are visible without waiting for the next loop tick.` |
| `backend/lumitrade/execution_engine/engine.py` | 123 | `# for live orders. Per Codex round-2 review of finding #4.` | `# Final kill-switch readback before the broker call closes the gap between the top-of-method check and the I/O.` |
| `backend/lumitrade/execution_engine/engine.py` | 430 | `# Per Codex review 2026-04-25 finding #3.` | `# PAPER-* IDs are simulated fills; calling modify_trade against them would 404 OANDA and trip the circuit breaker.` |
| `backend/lumitrade/execution_engine/engine.py` | 527-533 | `# Trail distance = ORIGINAL SL distance from entry. Per Codex 2026-04-25 audit finding [high] #5, computing this from current_sl is broken: …` | Keep the WHY (the breakeven-collapses-to-zero explanation) — DELETE the "Per Codex…" attribution. |
| `backend/lumitrade/execution_engine/engine.py` | 814 | `# Account-scoped count per Codex round-4 finding #4 — without …` | `# Account-scoped: a global count would block account-A trading whenever account-B has positions open.` |
| `backend/lumitrade/state/lock.py` | 67-70, 81, 134, 339, 392-394 | Six instances of `Per Codex follow-up review #1`, `Codex round-4 finding #2`, `Codex round-3 review #1`, etc. | Each block has a real WHY underneath the attribution — keep the why, drop the attribution. |
| `backend/lumitrade/state/manager.py` | 124, 331-332 | `Per Codex audit round-2 review of finding #4`, `per Codex round-3 review of finding #4` | Same pattern. |
| `backend/lumitrade/state/reconciler.py` | 52, 76, 351-352 | `Per Codex round-3 review #3`, `per Codex round-1 review of finding #5` | Same. |
| `backend/lumitrade/risk_engine/engine.py` | 284, 577, 587, 673 | Four instances. The `Codex review 2026-04-25 finding #4 —` opener can be deleted; the explanation that follows is the real comment. | Keep the contract / fail-closed reasoning, drop the attribution. |
| `backend/lumitrade/ai_brain/scanner.py` | 74-75, 165 | `Codex round-4 finding #3`, `per Codex follow-up review #4` | Keep "filter on the same identifier" and "already hold this pair" rationale; drop attribution. |
| `backend/lumitrade/ai_brain/prompt_builder.py` | 362, 465 | `per Codex round-3` review attributions | Same. |
| `backend/lumitrade/infrastructure/oanda_client.py` | 229, 276-277 | `Per Codex 2026-04-25 audit finding [critical] #3 and QTS spec 765` and `Per Codex round-1 review of finding #3` | Keep `QTS spec 765` reference (a real spec). Drop "Per Codex…" attribution. |
| `backend/lumitrade/infrastructure/health_server.py` | 138, 554, 681, 767, 823 | Five instances of `Codex audit finding [high] #4`, `Per Codex round-3 review #4`, etc. | Same — keep the security/scoping rationale, drop attribution. |
| `backend/lumitrade/main.py` | 121, 333, 431, 709 | Four `Codex round-X finding #N` references. | Same. |
| `backend/lumitrade/execution_engine/oanda_executor.py` | 44 | `Codex 2026-04-25 audit finding [critical] #3: place_market_order` | Same. |
| `backend/lumitrade/execution_engine/engine.py` | 864-865 | `Sweep both brokers (OANDA forex + Capital.com metals). Per Codex round-2 review of finding #4: original sweep only hit OANDA, leaving …` | Keep "original sweep only hit OANDA, leaving the metals broker stuck" — that's useful WHY. Drop "Per Codex round-2 review of finding #4". |
| `frontend/src/app/(dashboard)/api/control/kill-switch/route.ts` | 18-19 | `// Per Codex post-fix audit: the engine's close-out path (PRD:579 + audit finding #4) watches kill_switch_active.` | Keep `PRD:579` (a spec reference). Drop "Per Codex post-fix audit" and "audit finding #4". |

**Pattern:** every one of these comments has a real explanation immediately after the attribution. The fix is mechanical — strip the `Per Codex round-X review of finding #Y[: ]` prefix, keep the rest.

**Why this matters:** when the next engineer reads `# Per Codex round-3 review #2 — analyzer writes`, they get noise about session history with no grounding (no PR link, no commit hash, no JIRA ticket). The real signal — "the analyzer writes per-account, so reads must filter per-account" — is buried after the noise. Git blame already encodes who/when/why-changed at the commit level.

### Test files referencing Codex are appropriate to keep

- `backend/tests/unit/test_codex_findings_fixes.py` — the filename and 24 internal references are intentional (regression coverage). **PROTECT.**
- Other test files (`test_calendar.py`, `test_kill_switch_*.py`, etc.) — references are usually in test-name docstrings ("ensures fix from Codex finding #4 stays in place"). Keep test docstrings; they're regression contracts.

### Spec / metadata references that ARE useful

Comments like `Per PRD:579`, `Per BDS Section 13.2`, `QTS spec 765` are valid — they ground code in a versioned spec doc. PROTECT these.

---

## Stubs and Placeholders — Classified

### DELIBERATE (PROTECT — do not remove)

Per `CLAUDE.md` non-negotiable rule #6 ("All stubs are silent no-ops — return safe defaults, never raise") and the `2026-03-26-fix-all-stubs-and-placeholders.md` audit doc which has marked these as fully implemented:

- `backend/lumitrade/subagents/base_agent.py` — base class
- `backend/lumitrade/subagents/market_analyst.py` — implemented (returns `{"briefing": ""}` on failure)
- `backend/lumitrade/subagents/post_trade_analyst.py` — implemented (returns `{}` on insufficient data; that's the silent-no-op contract)
- `backend/lumitrade/subagents/risk_monitor.py` — implemented (returns `{}` on no open trades)
- `backend/lumitrade/subagents/intelligence_subagent.py` — implemented (returns `{}` on Claude failure)
- `backend/lumitrade/subagents/onboarding_agent.py` — implemented
- `backend/lumitrade/subagents/subagent_orchestrator.py` — coordinator

### LEFTOVER from multi-phase build (cleanup candidates, none in product code)

- `backend/scripts/backtest_amd.py:284` — `confidence_score=0.65,  # placeholder — AMD has no scoring`. AMD = research backtest script in `scripts/`, not the product. Acceptable as-is, but flag the comment so a future reader doesn't propagate `0.65` into product code.

### Intentional `NotImplementedError` (PROTECT)

- `backend/lumitrade/infrastructure/oanda_client.py:120,126` — `place_market_order` and `close_trade` raise `NotImplementedError("OandaClient is read-only. Use OandaTradingClient for orders.")`. This **enforces** non-negotiable rule #9 ("OandaTradingClient only in ExecutionEngine"). Keep.
- `backend/lumitrade/main.py:731` — `except NotImplementedError: pass` for `loop.add_signal_handler` on Windows (Unix-only API). Legitimate cross-platform fallback. Keep.

---

## Renamed-Variable Trails / `_old` / `_v2` / `_new` Files

**None in product code.** The single hit is:
- `backend/scripts/backtest_v2.py` — this is the **current live-parity backtest** per `~/.claude/projects/.../project_session_20260425.md`: *"Live-parity backtest_v2 built (USD_CAD passes PF 1.96, USD_JPY fails 1.04)"*. **PROTECT** — do not rename, do not delete. There is no `backtest.py` shadow.

`graphify-out/obsidian/*_old*.md` files are graphify's auto-generated knowledge-graph artefacts (named after test functions like `test_old_failures_expire`); these are tooling output, not source.

---

## Dashboard Coming-Soon Pages (UX decision, not code rot)

Per the unchecked `Wave 3 Task 14` in `docs/superpowers/plans/2026-03-26-fix-all-stubs-and-placeholders.md`:

- `frontend/src/app/(dashboard)/copy/page.tsx` — "Copy Trading — Coming Soon"
- `frontend/src/app/(dashboard)/backtest/page.tsx` — "Coming Soon"
- `frontend/src/app/(dashboard)/marketplace/page.tsx` — "Coming Soon"
- Likely also: `coach/`, `intelligence/`, `journal/`, `api-keys/` (route folders exist; not all verified to be coming-soon stubs)

**These pages exist intentionally** as Phase 0 placeholders. The task hasn't decided whether to (a) hide from sidebar, (b) keep as marketing teasers, or (c) remove. **Not a rot issue — pending product decision.**

---

## Frontend health-route legacy fallback (verify before removing)

- `frontend/src/app/(dashboard)/api/system/health/route.ts:26` — `// Backend may return flat strings (old) or structured objects (new)`
- Same file `:161` — `// Old flat format fallback`

Both branches are still being parsed. If the backend always returns the structured-object format now (verify against `backend/lumitrade/infrastructure/health_server.py`), the flat-string branch is removable. **Recommend grep-verifying the backend response schema before removing.**

---

## Protect-List (looks like slop, is intentional)

1. **`backtest_v2.py`** — current production backtest, NOT a `_v2` shadow trail. The `_v1` does not exist; the `_v2` suffix marks it as the live-parity rewrite vs the original (now-deleted) backtest. Renaming to `backtest.py` would create a misleading commit history.
2. **All seven subagent files** in `backend/lumitrade/subagents/`. Even though some methods return `{}` or empty briefings, that is the silent-no-op contract from CLAUDE.md non-negotiable rule #6. Removing the "empty return" branches would violate the contract.
3. **`backend/tests/unit/test_codex_findings_fixes.py`** — explicitly named regression coverage for the four Codex review rounds. Filename is correct; 24 internal Codex references are correct. Don't sanitize.
4. **`oanda_client.py:120,126` `NotImplementedError`** — enforces architecture rule #9 (read-only client cannot place orders). Removing would silently allow the wrong client to take trade actions.
5. **All `database/migrations/*.sql`** — append-only history per project rules. Note migrations 015 (`015_revert_system_state_to_singleton.sql`) and 016 (`016_initial_stop_loss.sql`) in `git status` are new and should be committed, not deleted.
6. **`# Per BDS Section X.Y` / `# Per QTS spec NNN` / `# PRD:NNN`** — these are spec-doc references, not narration. Keep.
7. **`# Phase 0 defaults — populated when features activate`** in `core/models.py:189` — this is the documented Phase-marker pattern (intentional placeholder fields), not stale narration.

---

## Top-5 Highest-Value Cleanups (non-trading-path, low-risk)

Ordered by value/risk ratio. None of these touch trading logic — all are documentation, naming, or filesystem hygiene.

1. **Delete the 22 zero-byte shell-debris files** at repo root and `backend/`. (`99`, `0`, `2`, `dashboard`, `engine`, `DROP`, `ExecutionError`, `TradingMode`, `True`, `web.Response`, `CheckResult`, `Engine`, `PriceTick`, `dict`, `expires_at`, `list[str]`, `state)`, `0.65)`, etc.) Zero risk, big win for `git status` and IDE noise.
2. **Strip "Per Codex round-X review of finding #Y" prefixes** from the 83 occurrences across the 19 product files listed above. Keep the WHY that follows each prefix. Mechanical regex-friendly cleanup; massively improves comment signal-to-noise.
3. **Rewrite the three stale `Phase 2 TODO:` / `Phase 3 TODO:` docstring headers** in `intelligence_subagent.py`, `onboarding_agent.py`, and `performance_analyzer.py` — the modules are implemented; the headers tell a lie.
4. **Move or delete `backend/_track4_cycle_scan.py` and `_track4_deferred_scan.py`** — relocate to `backend/scripts/audit/` if reusable, or delete after the Track-4 report lands.
5. **Decide and act on the 7 `Coming Soon` dashboard routes** (`copy`, `backtest`, `marketplace`, `coach`, `intelligence`, `journal`, `api-keys`). Per the audit doc Wave-3 Task 14 (still unchecked), the plan was to hide from sidebar. Pre-LIVE-cutover is a good moment to make the call.

---

## Top-3 Protect-List Traps (do NOT clean these up)

1. **`backtest_v2.py`** — looks like a `_v2` rename trail; is actually the live production backtest. Renaming or removing breaks the go/no-go gate verification chain.
2. **Subagent files that "look like" stubs** (`market_analyst.py`, `post_trade_analyst.py`, `risk_monitor.py`, `intelligence_subagent.py`, `onboarding_agent.py`). They return empty dicts on no-data conditions because **CLAUDE.md rule #6 mandates silent no-op stubs**. The empty branches are the contract, not laziness.
3. **`OandaClient.place_market_order` raising `NotImplementedError`** — is architectural enforcement of rule #9 ("OandaTradingClient only in ExecutionEngine"). Looks like an unfinished method; is actually the guardrail.

---

## Files NOT touched / scope notes

- `database/migrations/*.sql` — append-only history; not in scope.
- `graphify-out/obsidian/*.md` — auto-generated knowledge-graph output; not source.
- `frontend/node_modules/` — third-party; ignored.
- `docs/superpowers/plans/` — planning artefacts, not product code.
- `tasks/lessons.md`, session memory files — user-owned context.
