# Track 4 — Circular Dependency Mapping

**Date:** 2026-04-26 (T-1 day to live cutover)
**Mode:** Assessment-only. No code edits.
**Scope:** Backend `backend/lumitrade/` + Frontend `frontend/src/`.

---

## Executive Summary

| Category                                  | Count | Severity                                   |
| ----------------------------------------- | ----- | ------------------------------------------ |
| Backend module-import-time cycles         | **0** | none — engine imports cleanly              |
| Backend deferred (in-function) imports    | **64** across 14 files | mostly intentional; ~6 candidates for simple module-level promotion (post-cutover) |
| Frontend module-import-time cycles (madge ts/tsx) | **0** | none — `npx madge --circular` clean over 112 files |
| Frontend deferred / dynamic imports       | not enumerated (none flagged by madge) | n/a |

**Bottom line:** Track 4 finds **no real (import-time) circular dependencies** anywhere. The 64 backend deferred imports are documented in `CLAUDE.md` as a deliberate pattern. Several of them are mechanically removable post-cutover, but **none of them are bugs today** and none should be touched before Monday's live flip.

---

## Scanner outputs (verbatim)

### `backend/_track4_cycle_scan.py`

```
Total modules: 77
Total internal edges: 216
SCCs with size>1 (cycles): 0

RESULT: No top-level circular imports detected.
```

### `backend/_track4_deferred_scan.py`

```
Total deferred lumitrade imports: 64
```

Distribution by file:

| File | Count | Pattern |
| --- | ---: | --- |
| `infrastructure/health_server.py` | 27 | lazy import of `LumitradeConfig` + `OandaClient` per-handler |
| `main.py` | 12 | startup-deferred component wiring (documented in CLAUDE.md) |
| `execution_engine/engine.py` | 6 | enum + pip_math lazies in hot paths |
| `analytics/performance_analyzer.py` | 2 | `parse_iso_utc` per-call |
| `state/manager.py`, `state/reconciler.py` | 3 | reconciler/AlertService lazies |
| `ai_brain/validator.py` | 2 | pip_math + LumitradeConfig |
| `ai_brain/lesson_analyzer.py`, `ai_brain/quant_engine.py`, `data_engine/candle_fetcher.py`, `data_engine/price_stream.py`, `core/models.py`, `execution_engine/oanda_executor.py`, `execution_engine/capital_executor.py`, `infrastructure/oanda_client.py`, `risk_engine/engine.py` | 1–2 each | per-call utility imports (mostly `pip_math`, `time_utils`) |

### Frontend (`frontend && npx madge --circular --extensions ts,tsx src`)

```
Processed 112 files (17.3s)
✔ No circular dependency found!
```

---

## Real import-time cycles (backend)

**None.** Tarjan SCC over the full 77-module graph (216 internal edges) returned zero strongly-connected components of size > 1 and zero self-loops. Fresh imports of every module succeed.

No extraction proposals are needed.

---

## Deferred-import patterns (backend)

The CLAUDE.md project rules and the `main.py:188` comment ("import here to avoid circular deps") establish deferred imports as a documented architectural pattern. I classified all 64 occurrences into four buckets.

### Bucket A — Load-bearing wiring (DO-NOT-TOUCH)

These break a real latent cycle or are required by initialization order. Removing them would resurrect a cycle.

| Site | Why deferred | Recommendation |
| --- | --- | --- |
| `main.py:188-196` (9 imports of engines/scanners) | `EngineApp.startup()` constructs every subsystem; many of those subsystems transitively import config/state which `main.py` already initialized at module load. Promoting these imports re-creates a top-level cycle through `state.manager` → `infrastructure.alert_service` → `config`. | **DO-NOT** — keep as-is. Confirmed by the scanner: 0 cycles today *because* of this pattern. |
| `main.py:213` (`CapitalComClient`) | Conditional on `config.capital_api_key` — module is optional and not always installable. | **DO-NOT** — keep conditional + lazy. |
| `main.py:665-666` (reconciler in `_periodic_reconciliation`) | Same reasoning as 188; `state.reconciler` pulls config + db helpers that would close a cycle if hoisted. | **DO-NOT**. |
| `state/manager.py:167-168` (`AlertService`, `PositionReconciler`) | `state.manager` is imported by `main.py` at startup. Pulling `reconciler` to module top reintroduces `state.manager → state.reconciler → state.manager` (reconciler reads state). | **DO-NOT**. |
| `execution_engine/engine.py:67` (`CapitalExecutor`) | Conditional construction (`if capital_client`). Optional dependency. | **DO-NOT**. |

### Bucket B — Defensive lazies in HTTP handlers (POST-CUTOVER refactor)

`infrastructure/health_server.py` has **27** in-function `from ..config import LumitradeConfig` / `from ..infrastructure.oanda_client import OandaClient` calls, one per HTTP handler. These each instantiate a *fresh* `LumitradeConfig()` and a *fresh* `OandaClient`. The pattern is wasteful (re-parses env per request) but not cyclic — `health_server` is imported *by* `main.py`, not the other way around, so a top-level import here would be safe.

- **Confidence:** High (manually traced — health_server has no upstream importer in the package).
- **Risk:** Low to fix, but touching health_server before cutover is reckless.
- **Recommendation tier:** **POST-CUTOVER**. Refactor to inject one shared `LumitradeConfig` + `OandaClient` at server-construction time, then the 27 lazy imports collapse into 0. Estimated 1–2 hours, isolated to one file. **This is the single highest-leverage cleanup in the deferred list.**

### Bucket C — Per-call utility imports (POST-CUTOVER, low-priority)

These import small pure-function utilities (`pip_math`, `time_utils`, `core.enums`) inside hot loops. There is no cycle risk to hoisting them — the utility modules have zero internal deps.

| Site | Imported | Real reason for deferral |
| --- | --- | --- |
| `core/models.py:63` | `pip_math.pip_size` in `Quote.spread_pips` | `pip_math` does not import `core.models`, so this is **safe to hoist**. Likely a copy-paste habit. |
| `data_engine/candle_fetcher.py:63` | `time_utils.parse_iso_utc` | Safe to hoist. |
| `data_engine/price_stream.py:97,120` | `time_utils.parse_iso_utc` | Safe to hoist. |
| `ai_brain/quant_engine.py:296` | `pip_math.pip_size` | Safe to hoist. |
| `ai_brain/lesson_analyzer.py:165` | `time_utils.parse_iso_utc` | Safe to hoist. |
| `analytics/performance_analyzer.py:191,978` | `time_utils.parse_iso_utc` | Safe to hoist. |
| `execution_engine/engine.py:386,490,638,657` | `pip_math.{pip_size, pip_value_per_unit}` | Safe to hoist. |
| `execution_engine/{oanda,capital}_executor.py` | `pip_math.pips_between` | Safe to hoist. |
| `risk_engine/engine.py:195` | `pip_math` (two names) | Safe to hoist. |
| `infrastructure/oanda_client.py:201` | `secure_logger.get_logger` (in error-only branch) | Safe to hoist; logger is already used elsewhere in the file. |

- **Confidence:** High — `pip_math.py` has no `lumitrade.*` imports (verified), `time_utils` is similarly leaf-level.
- **Risk:** Low. Hoisting these saves microseconds per call and reduces noise. **None of them mask a real cycle.**
- **Recommendation tier:** **POST-CUTOVER batch cleanup** — group all of Bucket C into a single PR with a one-line scanner re-run as the verification. Estimated 30 min total.

### Bucket D — Latent design smell (DEFER, discuss first)

| Site | Issue |
| --- | --- |
| `state/reconciler.py:336` and `ai_brain/validator.py:158` | Both call `LumitradeConfig()` *inside* a function rather than receiving config via constructor. This is the same anti-pattern as Bucket B but in non-HTTP code. Hoisting the import is safe (no cycle), but the *real* fix is dependency-injecting config through the constructor. |

- **Confidence:** Medium (need to trace constructors across callers).
- **Risk:** Constructor-signature changes ripple to tests. Not a cycle, just bad coupling.
- **Recommendation tier:** **DEFER** — fold into a future "constructor injection" sweep, not a cycle-cleanup PR.

---

## Frontend cycles

`madge --circular --extensions ts,tsx src` over 112 files reported **zero circular dependencies**. 52 madge warnings exist (likely missing-extension or path-alias resolution noise — not cycle-related). No further action required for Track 4.

- **Confidence:** High (madge is the canonical tool for this).
- **Recommendation tier:** **n/a** — clean.

---

## Top recommendations (ranked)

| # | Action | Tier | Effort |
| --- | --- | --- | --- |
| 1 | Inject one shared `LumitradeConfig` + `OandaClient` into `health_server.py` constructor; delete the 27 per-handler lazy imports. | POST-CUTOVER | ~2 h |
| 2 | Batch-hoist Bucket C utility imports (10 sites, all `pip_math` / `time_utils` / `core.enums`). Re-run `_track4_cycle_scan.py` to confirm SCC count stays at 0. | POST-CUTOVER | ~30 min |
| 3 | Add `_track4_cycle_scan.py` and `_track4_deferred_scan.py` to CI as a regression guard so future deferred imports are flagged in PR review. | POST-CUTOVER | ~15 min |

## Do-not-touch list (load-bearing deferreds)

1. `main.py:188-196` — startup component wiring.
2. `main.py:213` — `CapitalComClient` (optional dependency).
3. `state/manager.py:167-168` — reconciler/alerts lazy.
4. `main.py:665-666` — periodic reconciliation lazy.
5. `execution_engine/engine.py:67` — `CapitalExecutor` (conditional).

These five sites collectively prevent the only real cycles the package would have if every import were hoisted to module top. Touching them before the live flip is forbidden.
