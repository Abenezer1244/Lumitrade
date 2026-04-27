# Backend Audit Scripts

Standalone, runnable diagnostic tools used by the Track 1-7 cleanup audits to inspect the `lumitrade` package without modifying it. Each script is a one-shot scanner that prints a report to stdout and exits.

Run periodically (or in CI as a regression guard) to catch architectural drift:

- `track4_cycle_scan.py` — builds the module-level import graph for `backend/lumitrade/` and runs Tarjan SCC to surface any new top-level circular imports. Should always print `RESULT: No top-level circular imports detected.` (`python backend/scripts/audits/track4_cycle_scan.py`).
- `track4_deferred_scan.py` — enumerates every in-function `import lumitrade.*` (the deferred-import pattern documented in `CLAUDE.md`). Use the diff in count between runs to detect newly-added lazy imports that should have been hoisted. (`python backend/scripts/audits/track4_deferred_scan.py`).
