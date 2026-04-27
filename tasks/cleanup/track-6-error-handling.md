# Track 6 — Error Handling Audit

**Scope:** Backend Python (`backend/lumitrade/`) and Frontend TypeScript (`frontend/src/`).
**Mode:** Assessment-only. **No code edited.** Pre-LIVE-cutover (2026-04-27) — trading-path findings are **flag-only**, recommend deferring all trading-path edits until after the first profitable LIVE week.

---

## Executive Summary

| Metric | Count |
|---|---|
| Python `try:` blocks (non-test backend) | 237 |
| Python `except` clauses (non-test backend) | 220 |
| Python `except Exception` (non-test backend) | 172 |
| Python bare `except:` | **0** (clean — no bare excepts in production) |
| TypeScript `catch (` clauses (frontend) | 8 |
| TypeScript `catch {` (param-less) clauses (frontend) | 50 |
| **Genuine smells** | **17** |
| **Load-bearing keeps** | **~118** (counted by category, not enumerated 1-by-1) |
| **Unclear / needs author judgment** | **6** |

**Headline:** Codebase is largely disciplined — `logger.exception(...)` / `logger.warning(...)` patterns dominate, and there are zero bare `except:` clauses. The trading loop's wide catches are explicitly load-bearing per CLAUDE.md non-negotiable rule #6 ("All stubs are silent no-ops"). The genuine smells cluster around **(a)** silent `pass` on default-mask fallbacks that hide DB outages, **(b)** one fail-OPEN/fail-CLOSED inconsistency on kill-switch reads, and **(c)** frontend `catch {}` swallowers in user-facing flows (auth, API keys).

---

## Genuine Smells (proposed fixes — DO NOT apply pre-cutover for trading-path entries)

### S-1 — Kill-switch read fails OPEN in risk_engine but fails CLOSED in state_manager
- **File:** `backend/lumitrade/risk_engine/state_machine.py:120-127`
- **Counterpart:** `backend/lumitrade/state/manager.py:346-348` — explicitly `failing_closed`
- **Smell:** Same logical operation, opposite safety semantics. `state_machine._is_emergency_halt()` returns `False` (no halt) on exception; `state_manager.refresh_kill_switch_from_db()` defaults to `True` (halted).
- **Risk:** HIGH. A transient Supabase blip during a live session could let a trade through past the risk-engine layer even when the operator pressed kill.
- **Confidence:** HIGH (verified both files).
- **Tier:** **DEFER (post-cutover)** — trading-path. Track it but do not touch this week. After cutover, harmonize: state_machine should fail-CLOSED to match state_manager.
- **Fix:** Change line 127 `return False` to `return True` (halt on read failure) and rename comment from "fail-open" to "fail-closed".

### S-2 — `prompt_builder.py` returns "No trade history available." on DB error
- **File:** `backend/lumitrade/ai_brain/prompt_builder.py:391-392` and `:489-490`
- **Smell:** Default-mask fallback. A Supabase outage causes Claude to be told there's no trade history and no performance insights — model then advises with no learned context, silently degrading signal quality. No log emitted.
- **Risk:** MEDIUM. Would not corrupt accounting, but invalidates the entire learning loop without any operator visibility.
- **Confidence:** HIGH.
- **Tier:** **DEFER (post-cutover)** — trading-path adjacent (prompt is sent to AI, AI signal goes to risk → execution).
- **Fix:** Add `logger.warning("trade_history_fetch_failed_using_empty_context", error=str(e))` before each `return`. Consider a circuit-breaker that *abstains* from the scan rather than calling Claude with empty context.

### S-3 — `lesson_filter.py` silently degrades to empty BLOCK rules on DB error
- **File:** `backend/lumitrade/ai_brain/lesson_filter.py:61-63` and `:70-72`
- **Smell:** It DOES log (warning), but then sets `block_rules = []` / `boost_rules = []`. If the trading_lessons table is unreachable, every previously-blocked bad pattern is now allowed through.
- **Risk:** MEDIUM-HIGH. The whole point of BLOCK rules is to prevent recurring losses; failing-open negates that protection. Violates "fail-CLOSED" pattern used everywhere else.
- **Confidence:** HIGH.
- **Tier:** **DEFER (post-cutover)** — trading-path.
- **Fix:** On exception, raise / return a sentinel that causes the scanner to skip the pair this cycle (consistent with risk_engine fail-closed pattern at `risk_engine/engine.py:292-293`).

### S-4 — `health_server.py:245` swallows DB read for the `system_state` row
- **File:** `backend/lumitrade/infrastructure/health_server.py:241-246`
- **Smell:** `except Exception: pass` with no log. Subsequent code reads `row` which is `None` and silently skips state/lock/oanda/risk_engine/circuit_breaker/ai_brain/price_feed component reporting. Health endpoint then claims "ok" for what it could measure (DB latency) but is blind to whether the singleton row exists.
- **Risk:** MEDIUM. Operator-facing dashboard could green-light a partially-broken system.
- **Confidence:** HIGH.
- **Tier:** **SAFE-NOW** (health server is not on the trading path; failure is observability-only).
- **Fix:** Add `logger.warning("health_check_state_row_fetch_failed")` before the `pass`.

### S-5 — `health_server.py:564` swallows JSON parse on kill-switch ACTIVATE POST
- **File:** `backend/lumitrade/infrastructure/health_server.py:562-566`
- **Smell:** `body = {}` on parse failure with no log. The kill-switch endpoint then proceeds with `reason = "operator_invoked"` even though the operator may have intended a specific reason. Audit trail is incomplete.
- **Risk:** LOW (kill activates either way), but the audit log loses the operator's intended reason.
- **Confidence:** HIGH.
- **Tier:** **SAFE-NOW** (route layer, not trading loop).
- **Fix:** Log a warning with `request.remote` so missing reasons are traceable.

### S-6 — `health_server.py:919` silent `continue` inside WS price loop
- **File:** `backend/lumitrade/infrastructure/health_server.py:919-920`
- **Smell:** Inside an `async for msg in ws` loop with a sub-`try` that swallows any per-message exception via `continue`. No log. If pricing payloads change shape, the WS silently sends nothing without a single log line.
- **Risk:** LOW-MEDIUM. UI looks dead with no diagnostic trail.
- **Confidence:** HIGH.
- **Tier:** **SAFE-NOW** (WS to dashboard, not trading-path).
- **Fix:** `logger.debug("ws_price_msg_dropped", error=str(e))` to throttle-log without spam.

### S-7 — `health_server.py:964` silent `pass` on calendar holiday parsing
- **File:** `backend/lumitrade/infrastructure/health_server.py:961-965`
- **Smell:** Per-event catch with no log. If the upstream calendar API changes shape, every event is dropped and the dashboard shows a working-but-empty calendar.
- **Risk:** LOW.
- **Tier:** **SAFE-NOW**.

### S-8 — `execution_engine/engine.py:943` audit-log swallow inside `close_all_positions`
- **File:** `backend/lumitrade/execution_engine/engine.py:943-944`
- **Smell:** Right after kill-switch close-all, the audit-log `db.insert(...)` is wrapped in `except Exception: pass`. If audit insert fails, we have no record we ever ran a kill-switch close. Combined with how rare this path is, a silent failure means we can't reconstruct what happened.
- **Risk:** MEDIUM (compliance + post-mortem trail).
- **Confidence:** HIGH.
- **Tier:** **DEFER (post-cutover)** — trading-path.
- **Fix:** `logger.exception("kill_switch_audit_log_failed", attempted=attempted, closed=closed, failed=failed)` so at least the structured log retains the data even if DB insert fails.

### S-9 — `ai_brain/scanner.py:176` silent pass after open-trades pre-check
- **File:** `backend/lumitrade/ai_brain/scanner.py:172-177`
- **Smell:** Comment says "Non-critical — risk engine will catch it later" but the open-trades pre-check is meant to short-circuit *before* spending a Claude API call. If it silently fails, every cycle wastes Claude tokens AND emits no log.
- **Risk:** LOW (cost only — no trade safety impact).
- **Tier:** **DEFER (post-cutover)** — trading-path.
- **Fix:** `logger.debug("scanner_open_trade_pre_check_failed_continuing", pair=pair, error=str(e))`.

### S-10 — `ai_brain/scanner.py:633` silent pass on hold-signal save
- **File:** `backend/lumitrade/ai_brain/scanner.py:629-634`
- **Smell:** `_save_hold_signal` failures are silenced. Hold signals are observability data — losing them silently breaks the scan-history trace in the dashboard.
- **Risk:** LOW.
- **Tier:** **DEFER (post-cutover)**.

### S-11 — `state/manager.py:282` silent pass on account-balance refresh
- **File:** `backend/lumitrade/state/manager.py:278-283` (inside `persist_loop`)
- **Smell:** Mirror of `main.py:389`. Comment says "Non-critical — balance stays at last known value" but **no log**. If OANDA account auth has rotated and we never refresh balance, position_sizer will compute risk against stale equity for hours/days without a single warning. (Note: similar one in `main.py:389-390` already noted in commits as intentional.)
- **Risk:** MEDIUM-HIGH (position sizing on stale balance).
- **Confidence:** HIGH.
- **Tier:** **DEFER (post-cutover)** — trading-path.
- **Fix:** Throttled `logger.warning` (once per N minutes) on consecutive failures, and emit a metric so the watchdog can fire at N=5 consecutive failures.

### S-12 — `infrastructure/ig_client.py:325` silent pass in deal-confirm polling loop
- **File:** `backend/lumitrade/infrastructure/ig_client.py:319-330`
- **Smell:** Polling `/confirms/{deal_reference}` 5 times. Inner `except Exception: pass` swallows every retry attempt's error — only emits one final "ig_deal_confirm_timeout" log without indicating WHY (network? auth? 500?).
- **Risk:** LOW-MEDIUM. (IG path is not currently active per session notes — IBKR/Capital used instead.) Becomes important when IG goes live.
- **Tier:** **SAFE-NOW** (currently inactive broker).
- **Fix:** `logger.debug("ig_deal_confirm_attempt_failed", attempt=attempt, error=str(e))`.

### S-13 — `execution_engine/capital_executor.py:322-326` (same pattern as S-12)
- **File:** `backend/lumitrade/execution_engine/capital_executor.py` (poll loop near 322)
- **Note:** File is only 92 lines (reread confirmed); the 322 reference was actually from the IG client. Re-grep showed the only `except Exception` in capital_executor is at line 36 (logged + raised). **Withdraw — not a smell.**

### S-14 — Frontend `app/auth/login/page.tsx:39` and `signup/page.tsx:39` swallow auth errors
- **Files:** `frontend/src/app/auth/login/page.tsx:39`, `frontend/src/app/auth/signup/page.tsx:39`
- **Smell:** `catch { setErrorMessage("An unexpected error occurred. Please try again."); }` — no telemetry call, no `console.error`. Real auth bugs (expired Supabase keys, network failure, RLS misconfig) appear identically to user input errors.
- **Risk:** MEDIUM (operator visibility into auth failures = zero).
- **Tier:** **SAFE-NOW** — frontend, not trading-path.
- **Fix:** `catch (err) { console.error("auth_signup_error", err); ... }` plus a Sentry/PostHog hook.

### S-15 — Frontend `app/(dashboard)/journal/page.tsx:184` `.catch(() => {})`
- **File:** `frontend/src/app/(dashboard)/journal/page.tsx:184`
- **Smell:** Silent swallow on `/api/journal` fetch. User sees blank journal with no error indication.
- **Risk:** LOW.
- **Tier:** **SAFE-NOW**.
- **Fix:** Set an error state to render "Couldn't load journal — retry" UI.

### S-16 — Frontend `app/(dashboard)/api/api-keys/route.ts:46-48`, `103-105`, `120-122`, `147-149`
- **File:** `frontend/src/app/(dashboard)/api/api-keys/route.ts`
- **Smell:** Four `catch {}` clauses on a security-sensitive route (API key issuance + revocation). Empty arrays / 500 responses without server-side logs. If revocation silently fails, the key remains valid.
- **Risk:** HIGH (security, compliance, key-revocation correctness).
- **Tier:** **SAFE-NOW** — frontend route. **Highest-priority frontend smell.**
- **Fix:** `catch (err) { console.error("api_keys_revoke_failed", err); return NextResponse.json({ error: "Failed to revoke key" }, { status: 500 }); }` and add an alerting hook on key-revocation failures specifically.

### S-17 — Frontend `app/(dashboard)/api/account/route.ts:56,73,86,126` `catch { /* continue */ }`
- **File:** `frontend/src/app/(dashboard)/api/account/route.ts`
- **Smell:** Three nested fallback layers, each silently failing through. End user sees the FALLBACK constant — they don't know the real account number was unreachable.
- **Risk:** MEDIUM (user shown stale/fake account data thinking it's live).
- **Tier:** **SAFE-NOW**.
- **Fix:** Log each fallback transition; include a `data_source: "live" | "cache" | "fallback"` field in the JSON so the UI can display a "stale data" badge.

---

## Load-Bearing Keep-List (do NOT remove in any future cleanup)

These follow the CLAUDE.md non-negotiable rules. Tagging the categories rather than every line:

1. **`main.py:281-715` — orchestrator loops.** Every `except asyncio.CancelledError: break` then `except Exception as e: logger.warning(...)` pattern in `_periodic_reconciliation`, `_weekly_intelligence_loop`, `_risk_monitor_loop`, signal-loop. **Rationale:** trading loop must not crash (CLAUDE.md non-negotiable).
2. **`execution_engine/engine.py:93-159` — circuit-breaker wrap.** `except Exception: await record_failure(); raise` is the textbook circuit-breaker pattern. **Rationale:** required by CLAUDE.md non-negotiable rule #5.
3. **`execution_engine/oanda_executor.py:43-96` — order-recovery lookup.** Catches post-broker-commit exceptions and runs an idempotent status lookup to avoid duplicate orders. Codex-audited. **Rationale:** prevents duplicate fills on partial-failure.
4. **`state/lock.py:222-368` — distributed lock acquisition/release.** Uses `logger.exception` at every catch. **Rationale:** lock failure must be visible but cannot crash the engine.
5. **`state/reconciler.py:139-365` — position reconciliation.** Uses `logger.exception` + `_alerts.send_critical(...)`. **Rationale:** alerts the operator while keeping the loop alive.
6. **`infrastructure/watchdog.py:86-87` — top-level watchdog tick.** `logger.exception("watchdog_check_failed")` then continues. **Rationale:** watchdog itself cannot die.
7. **`infrastructure/alert_service.py:76, 91, 107` — alert delivery.** Catches Twilio/SendGrid/DB failures so a broken pager doesn't break trading. Each logs. **Rationale:** explicit comment "Alert logging should never crash the engine".
8. **`infrastructure/event_publisher.py:78-80` — Mission Control event publish.** Explicit comment "Mission Control is observability, not critical path". **Rationale:** correct.
9. **`infrastructure/oanda_client.py:290-291` — `get_trade` lookup inside fill parsing.** Returns None on missing trade — order parser then degrades gracefully to using the order envelope only. Acceptable.
10. **`risk_engine/engine.py:292-318` — fail-CLOSED on DB read.** Comment says "Fail-CLOSED: if DB unavailable, block trading". **Rationale:** correct fail-closed pattern. This is the gold standard the smells above should match.
11. **`subagents/base_agent.py:49-`, all `subagents/*.py` log+return-empty patterns.** Subagents are explicitly stubs/auxiliaries; CLAUDE.md non-negotiable rule #6 says stubs are silent no-ops returning safe defaults. **Rationale:** intentional design.
12. **All Python `claude_client.py:44-46, 99-101` — log + re-raise.** Textbook good pattern.
13. **All frontend Next.js API routes that catch and return `NextResponse.json({error: ...}, {status: 500})`** — these ARE the user-facing error boundary; load-bearing.
14. **All frontend `await res.json().catch(() => fallback)`** — defensive parse fallback when an upstream returns non-JSON 5xx. Idiomatic, load-bearing.

---

## Unclear Cases (need author input — do not auto-fix)

### U-1 — `main.py:599-600` settings-row JSON parse swallow
- **File:** `backend/lumitrade/main.py:596-600`
- **Question:** When `settings_row.open_trades.scanInterval` parse fails, we silently keep the prior `scan_minutes`. Is this intentional (operator changed settings, parse failed, keep last good) or should this fire an alert (operator's settings dashboard is now broken and they don't know)?

### U-2 — `state/manager.py:282-283` balance refresh swallow inside persist_loop
- **File:** `backend/lumitrade/state/manager.py:278-283`
- **Question:** Same as S-11 but specifically: should this trigger the watchdog after N consecutive failures, or is "stay on last balance forever" acceptable when OANDA is down?

### U-3 — `risk_engine/state_machine.py:120-127` fail-OPEN on kill-switch
- **File:** see S-1
- **Question:** Was the fail-open semantic deliberate (e.g., "if state manager is down, the *primary* kill switch via env var is still authoritative")? Or is this a bug? Comment says "fail-open on kill switch read only" — needs explicit confirmation that the env-var dual-switch covers this case.

### U-4 — `execution_engine/engine.py:709-710` duration parse swallow
- **File:** `backend/lumitrade/execution_engine/engine.py:706-710`
- **Question:** `duration_minutes = None` on parse failure. Downstream lesson_analyzer treats `None` differently from 0. Confirm this is intentional and not a missed log.

### U-5 — `data_engine/calendar.py:158-159` per-event silent continue
- **File:** `backend/lumitrade/data_engine/calendar.py:155-160`
- **Question:** Is dropping a malformed calendar event silently acceptable, or do we want a counter so we can detect ForexFactory schema drift?

### U-6 — Subagent return-empty-dict patterns (`market_analyst.py:99`, `post_trade_analyst.py:134`, `intelligence_subagent.py:124`)
- **Question:** These conform to "stubs are no-ops" but several are now real (intelligence is wired into the weekly loop). For real subagents, should errors propagate to the orchestrator with a flag rather than degrading to `{}` which the orchestrator can't distinguish from "no analysis yet"?

---

## Per-File Counts (informational, top 12 by `except Exception` density)

| File | `except Exception` | Trading-path? | Smell count |
|---|---|---|---|
| `infrastructure/health_server.py` | 33 | No | 4 (S-4, S-5, S-6, S-7) |
| `execution_engine/engine.py` | 20 | YES | 1 (S-8) |
| `analytics/performance_analyzer.py` | 12 | No | 0 |
| `main.py` | 13 | YES | 0 (S-11 mirror is in state/manager) |
| `ai_brain/scanner.py` | 10 | YES | 2 (S-9, S-10) |
| `risk_engine/engine.py` | 7 | YES | 0 (gold standard) |
| `state/manager.py` | 6 | YES | 1 (S-11) |
| `state/reconciler.py` | 6 | YES | 0 |
| `ai_brain/tv_chart_screenshotter.py` | 6 | No | 0 |
| `ai_brain/lesson_analyzer.py` | 3 | No | 0 |
| `subagents/onboarding_agent.py` | 3 | No | 0 |
| `infrastructure/alert_service.py` | 3 | No | 0 |

---

## Recommended Sequencing (post-cutover)

1. **Week 1 LIVE:** No changes. Observe.
2. **Week 2:** Fix S-4, S-5, S-6, S-7, S-14, S-15, S-16, S-17 (all SAFE-NOW frontend + health-server).
3. **Week 3:** Resolve U-3 with author, then fix S-1 (kill-switch consistency) — highest-priority trading-path fix.
4. **Week 4:** S-2, S-3, S-8, S-11 (one PR each, with chaos-test that simulates Supabase outage during signal/exec).
5. **Week 5+:** S-9, S-10, S-12 as cleanup.
