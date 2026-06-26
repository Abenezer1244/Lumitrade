# Audit Branch — Deploy Checklist (2026-06-25)

Branch: `audit/saas-trading-review` (worktree `C:/Users/Windows/lumitrade-audit`)
Base: `main` @ `7a19164`
Scope: **backend only** (`lumitrade-engine`). No frontend, no DB schema/migrations.
Account type: **HEDGING** (confirmed by operator).

> **Do not deploy outside 13:00–23:59 UTC.** Trading hours are 00:00–13:00 UTC;
> deploying then restarts the engine and misses trades.

---

## 1. What's in this branch (12 commits)

| Commit | Severity | Summary |
|---|---|---|
| `f56c1d1` | 🔴 CRITICAL | Reconciliation fails closed on a partial broker snapshot — stops force-closing live BTC/ETH positions when the spot-crypto fetch fails. |
| `c8c5f5b` | 🔴 CRITICAL | Lock split-brain fix: per-process lease token (no two same-`INSTANCE_ID` containers hold the lock) + supervised failover that halts new orders **without** liquidating. |
| `17214a7` `ef1dec9` `76bb207` | 🟠 HIGH | SL/TP "confirmed" now read back from the live broker trade (was echoing requested values). Emergency-close only on positively-confirmed-missing protection; never on readback/parse uncertainty. |
| `de6ec00` `8977a15` | 🟠 HIGH | Idempotency guard before live placement (skip a signal that already has a live trade row); **fails closed**. |
| `8d30ff1` `8977a15` `38eddba` | 🟠 HIGH | Reconciler-closed P&L now books into daily/weekly loss limits; atomic CAS close on both monitor and reconciler so a trade is booked exactly once. |
| `b031646` `5c84942` `ade7d1a` | test | Un-rotted lock/risk/btc/live-pair/crash-recovery test suites (were giving false-green on the money paths). |

All money-path fixes were cross-verified by an independent Codex review (several
reached SHIP only after Codex caught a follow-on defect that was then fixed).

## 2. Test status

- **All functional/correctness tests pass** locally (`pytest tests/unit tests/chaos`).
- Remaining local failures: `tests/performance/test_latency.py` wall-clock
  benchmarks (e.g. indicator computation 0.9s vs 0.5s budget). These are
  **hardware/load-sensitive**, not correctness failures, and unrelated to the
  audit. CI runs them on consistent GitHub hardware where the budgets pass.
- CI gates: gitleaks, bandit `-ll`, pytest. ruff/mypy are **advisory**
  (`--exit-zero` / `|| true`) — the repo carries a pre-existing E501 baseline.
- Changes are security-neutral: no new secrets, no raw SQL (parameterized db
  client), no new external-input parsing beyond broker JSON already handled.

## 3. Migrations / config

- **None required.** All fixes use existing columns (`signal_id`, `status`,
  `instance_id`). No Supabase migration to apply.
- No new env vars.

## 4. ⚠️ Operator-awareness items (surfaced by the audit, NOT changed here)

1. **Position sizing is 2%/3%, not 0.5%/1%.** Commit `95ec9e9` (already on main)
   raised the confidence-based risk schedule to target ~$10/trade: sub-0.80 →
   2.0%, at-0.80 → 3.0% (capped by `max_risk_pct`=3%). The rotted tests had hidden
   this 3–6× change. **Confirm this is intended for the live account size.**
2. **Garbage files in repo root + `backend/`** (zero-byte `'`, `str`, `EMA10`,
   `{max_conf}`, …) from shell-redirect accidents. Untracked; `git clean -n` to
   preview, `git clean -f` to remove. Not in the repo, just disk litter.

## 5. Deferred follow-ups (documented, non-blocking)

- Durable pre-placement claim (orders table + unique constraint) for true
  idempotency — closes the TOCTOU + broker-accept-then-DB-save-fail windows the
  current best-effort guard cannot.
- Recompute-from-closed-trades P&L ledger (needs a DB range-query primitive) —
  also fixes the restart-resets-counter fragility and the CAS-then-counter
  non-atomic crash gap.
- True atomic bootstrap/vacant lock CAS (Postgres advisory lock / version CAS).
- `run()` await `lock.release()` on signal shutdown; done-callbacks for
  non-heartbeat critical tasks.
- Netting/`tradesClosed` defensive hardening (latent on a hedging account).

## 6. Deploy steps (operator runs — agent will NOT deploy without explicit go)

```bash
# 0. Confirm UTC time is within 13:00–23:59.
# 1. Merge the audit branch to main (from the main checkout):
git checkout main && git pull
git merge --no-ff audit/saas-trading-review
git push origin main

# 2. Verify CI is green on main (gitleaks + bandit + pytest).

# 3. Deploy backend (per feedback_railway_deploy):
railway up --service lumitrade-engine --detach --ci
#    (cache-bust if Railway reuses a stale build layer)

# 4. Confirm Railway actually rebuilt (feedback_railway_autodeploy_check) and
#    watch startup_diagnostics for: effective_mode, oanda_environment,
#    hedging, lock_acquired, kill_switch=off.

# 5. Post-deploy smoke: tail logs for one scan cycle; confirm
#    reconciliation_complete shows snapshot_complete=true and no
#    reconciliation_snapshot_incomplete_ghosts_deferred alerts.
```

Rollback: `git revert` the merge commit and redeploy, or redeploy the prior
`main` SHA `7a19164`.
