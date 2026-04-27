# Lumitrade Security Audit Report

**Date**: 2026-03-22
**Auditor**: Security Engineer (Claude Opus 4.6)
**Scope**: `backend/lumitrade/` -- all 55 Python source files
**Severity levels**: CRITICAL (must fix before deploy), HIGH (fix before live trading), MEDIUM (fix before Phase 9 complete), LOW (track and fix), INFO (observation)

---

## Executive Summary

| Category | Verdict | Findings |
|---|---|---|
| 1. Secrets Scan | **PASS** | No hardcoded secrets in code |
| 2. SQL Injection | **PASS** | All queries parameterized via Supabase client |
| 3. TLS Verification | **PASS** | Never disabled; TLSv1.2 minimum enforced |
| 4. Input Validation | **PASS** | AI output validated, prompt injection sanitized |
| 5. Logging Safety | **PASS** (fixed) | SecureLogger scrubs all output, no print() |
| 6. Financial Math | **PASS** (with notes) | Decimal used for all financial values |
| 7. OANDA Client Isolation | **PASS** | OandaTradingClient only in execution_engine/ |
| 8. Error Handling | **PASS** | All external calls wrapped, subagents safe |
| 9. Dependencies | **WARNING** | Versions not pinned with hashes |
| 10. Dockerfile Security | **PASS** | Non-root user, no secrets in build |
| 11. Pre-Commit Hooks | **PASS** | Gitleaks + Bandit configured |
| 12. SecureLogger Patterns | **PASS** (fixed) | All 8 SS-spec patterns now implemented |

**Overall: PASS with 1 fix applied and 4 advisory items**

---

## 1. Secrets Scan -- PASS

### Method
- Searched all `.py` files for patterns: `sk-ant-`, `Bearer ` with literal values, `password=`, `api_key=` with string literals, `v1.sk-`, connection strings with embedded credentials.
- Verified `.env.example` contains only placeholder values.
- Verified `.gitignore` covers `.env`, `*.pem`, `*.key`, `secrets/`, `credentials/`.

### Findings
- **No hardcoded secrets found** in any source file.
- All secrets loaded via `pydantic-settings` from environment variables in `config.py`.
- `.env.example` uses safe placeholders like `your-read-only-api-key-here`, `sk-ant-your-key-here`.
- `.gitignore` comprehensively covers: `.env`, `*.env`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa`, `id_ed25519`, `secrets/`, `credentials/`, `*credentials*.json`, `*service-account*.json`.

### Verdict: PASS -- no issues.

---

## 2. SQL Injection Check -- PASS

### Method
- Searched for f-string SQL (`f"SELECT`, `f"INSERT`, `f"UPDATE`, `f"DELETE`), `.format()` SQL, and `%`-operator SQL.
- Reviewed `db.py` (DatabaseClient) for raw SQL.

### Findings
- **Zero raw SQL found anywhere** in the codebase.
- `DatabaseClient` wraps all Supabase operations (`insert`, `select`, `update`, `upsert`, `delete`, `count`) with parameterized filter dicts.
- All 17 modules that use the database go through `DatabaseClient` methods exclusively.
- The Supabase Python SDK handles parameterization internally.

### Verified files using DB (all use `self._db.<method>` pattern):
- `state/manager.py`, `state/lock.py`, `state/reconciler.py`
- `ai_brain/scanner.py`, `ai_brain/prompt_builder.py`
- `execution_engine/engine.py`
- `risk_engine/engine.py`
- `data_engine/engine.py`
- `infrastructure/alert_service.py`, `infrastructure/health_server.py`
- `analytics/performance_analyzer.py`

### Verdict: PASS -- no issues.

---

## 3. TLS Verification -- PASS

### Method
- Searched for `verify=False`, `ssl=False`, `verify_ssl=False`.

### Findings
- **Zero instances of disabled TLS verification.**
- `oanda_client.py:_create_secure_client()` explicitly creates an SSL context with:
  - `ssl.TLSVersion.TLSv1_2` minimum
  - `ssl.CERT_REQUIRED`
  - `check_hostname = True`
- The streaming client in `stream_prices()` explicitly sets `verify=True`.
- `alert_service.py` uses default `httpx.Client()` which defaults to `verify=True`.
- Comment on line 27: `Per SS Section 5.1. NEVER set verify=False.`

### Verdict: PASS -- no issues.

---

## 4. Input Validation -- PASS

### Method
- Reviewed AI output validator, data validator, prompt builder injection prevention.
- Searched for `eval()`, `exec()`, `pickle.loads()`, `subprocess`.

### Findings

**AI Output Validator** (`ai_brain/validator.py`):
- 8-step validation pipeline: JSON parse, required fields, action enum, numeric bounds, price logic, price sanity (0.5% deviation max), RR ratio (1.5:1 min), text quality.
- All numeric values converted to `Decimal` with `InvalidOperation` handling.
- `recommended_risk_pct` clamped to [0.25%, 2.0%].

**Prompt Injection Prevention** (`ai_brain/prompt_builder.py`):
- `_sanitize_news_title()` strips all non-alphanumeric characters except `.,-()/% `.
- Hard length limit of 100 characters on news titles.
- Regex: `r"[^a-zA-Z0-9 .,\-()%/]"` removes injection characters.

**Data Validator** (`data_engine/validator.py`):
- 5-check pipeline: freshness (5s), spike detection (3-sigma), spread ceiling, OHLC integrity, gap detection.

**Dangerous Functions**: Zero instances of `eval()`, `exec()`, `pickle.loads()`, or `subprocess` found.

### Verdict: PASS -- no issues.

---

## 5. Logging Safety -- PASS

### Method
- Searched for `print()` statements.
- Searched for f-string log messages that could leak secrets.
- Verified SecureLogger is the only logging path.

### Findings
- **Zero `print()` statements** in any source file.
- **Zero f-string log messages with secret interpolation.** All logging uses structured kwargs:
  ```python
  logger.info("event_name", key1=value1, key2=value2)
  ```
- `structlog` configured with `_scrub_processor` that runs before `JSONRenderer`.
- The scrub processor recursively processes all string values in the event dict.
- All 28 source modules import and use `get_logger(__name__)`.

### Verdict: PASS -- no issues.

---

## 6. Financial Math Safety -- PASS (with notes)

### Method
- Searched for `float()` calls across all source files.
- Reviewed `pip_math.py` and `position_sizer.py` for float usage.

### Findings

**Core financial math is Decimal-only:**
- `pip_math.py`: All calculations use `Decimal`. No `float()` anywhere.
- `position_sizer.py`: All calculations use `Decimal`. No `float()` anywhere.
- `risk_engine/engine.py`: All comparisons and calculations use `Decimal`.
- `ai_brain/validator.py`: All numeric validation uses `Decimal`.

**Acceptable `float()` usage found (2 locations, non-financial):**

1. **`data_engine/indicators.py:46-49`** -- `float(c.open)` etc. for pandas DataFrame construction.
   - **Why acceptable**: pandas-ta requires float arrays for indicator computation. Values are immediately converted back to `Decimal` via `_to_decimal(str(round(value, 10)))` before returning the `IndicatorSet`. No financial decisions are made with float values.

2. **`ai_brain/confidence.py:38-64`** -- `float(factor)` for adjustment log dict.
   - **Why acceptable**: These are logging/observability values stored in the `adjustments` dict for the adjustment log. All actual confidence math uses `Decimal`. The float values are never used in financial calculations.

### Verdict: PASS -- float usage is architecturally isolated and does not affect financial calculations.

---

## 7. OANDA Client Isolation -- PASS

### Method
- Searched for all references to `OandaTradingClient` across the codebase.

### Findings

`OandaTradingClient` is referenced in exactly 4 files:
1. **`infrastructure/oanda_client.py`** -- Class definition (line 150). Correct.
2. **`execution_engine/engine.py`** -- Imported and used as constructor parameter (lines 19, 35). Correct.
3. **`execution_engine/oanda_executor.py`** -- Imported and used (lines 13, 21). Correct.
4. **`main.py`** -- Imported and instantiated, then passed to `ExecutionEngine` (lines 19, 93, 152). Correct.

**No other module imports or uses `OandaTradingClient`.** The `DataEngine`, `AIBrain`, `RiskEngine`, and all subagents use `OandaClient` (read-only) exclusively.

The `paper_executor.py` explicitly documents: `NEVER calls OandaTradingClient. Per BDS Section 5.`

### Verdict: PASS -- isolation is correct.

---

## 8. Error Handling -- PASS

### Method
- Reviewed all external API call sites for try/except wrapping.
- Reviewed circuit breaker implementation.
- Reviewed all 5 subagent stubs.

### Findings

**External API calls -- all wrapped:**
- `oanda_client.py`: `get_candles()`, `get_pricing()`, `get_account_summary()`, `get_open_trades()` all have callers that wrap in try/except.
- `claude_client.py`: `call()` wraps in try/except, logs error, re-raises for scanner retry logic.
- `alert_service.py`: `_send_sms_sync()` and `_send_email()` both wrap in try/except, log errors, never crash.

**Circuit breaker** (`execution_engine/circuit_breaker.py`):
- Implements CLOSED -> OPEN (3 failures/60s) -> HALF_OPEN (30s) -> CLOSED pattern.
- Used by `ExecutionEngine.execute_order()` for all live OANDA order calls.

**Subagent error isolation** (`subagents/base_agent.py`):
- `_call_claude()` wraps in try/except, returns empty string on failure.
- All 5 subagents inherit from `BaseSubagent`.
- `SubagentOrchestrator` methods are called with try/except in `main.py` loops.

**Background task error handling:**
- `_risk_monitor_loop()`: catches `asyncio.CancelledError` (break) and `Exception` (log and continue).
- `_weekly_intelligence_loop()`: same pattern.
- `position_monitor()`: catches `asyncio.CancelledError`.
- `persist_loop()`: catches `asyncio.CancelledError`, performs final save.
- `renew_loop()`: escalates to `SystemExit` after 2 consecutive lock renewal failures.

### Verdict: PASS -- robust error handling throughout.

---

## 9. Dependencies -- WARNING

### Method
- Reviewed `requirements.txt` for pinning strategy.

### Findings

**Versions use range specifiers, not exact pins with hashes:**
```
httpx>=0.24,<0.28
anthropic>=0.25
supabase>=2.4
pandas>=2.2
```

**Risk**: A future `pip install` could pull a compromised or breaking version.

**Recommendation**: Use `pip-compile --generate-hashes` to produce a fully-pinned `requirements.txt` with integrity hashes. This prevents supply chain attacks where a PyPI package is replaced with a malicious version.

**Mitigating factor**: The Dockerfile builds from `requirements.txt` at image build time, so the running container has fixed versions. But the build itself is still vulnerable to supply chain attacks at build time.

### Verdict: WARNING -- not a blocking issue for paper trading, but MUST be resolved before live trading.

---

## 10. Dockerfile Security -- PASS

### Method
- Reviewed `backend/Dockerfile` for security best practices.

### Findings
- **Multi-stage build**: Builder stage compiles dependencies, runtime stage is minimal.
- **Non-root user**: `useradd --no-create-home --shell /bin/false lumitrade` + `USER lumitrade`.
- **Minimal base image**: `python:3.12-slim`.
- **No secrets in build args**: All secrets come from environment variables at runtime.
- **Health check**: `HEALTHCHECK` directive with `curl -f http://localhost:8000/health`.
- **No unnecessary packages**: Only `supervisor` and `curl` installed in runtime stage.

### Verdict: PASS -- no issues.

---

## 11. Pre-Commit Hooks -- PASS

### Method
- Reviewed `.pre-commit-config.yaml`.

### Findings
- **Gitleaks v8.18.2**: Scans for hardcoded secrets before every commit.
- **Bandit 1.7.8**: Python security scanner targeting `backend/lumitrade/` with `-ll` (medium+ severity).
- **detect-private-key**: Catches committed private keys.
- **check-added-large-files**: Prevents accidental large file commits (>500KB).

### Verdict: PASS -- comprehensive pre-commit security scanning.

---

## 12. SecureLogger Scrub Patterns -- PASS (FIXED)

### Method
- Compared implemented patterns against SS v2.0 specification requiring 8 patterns.

### Findings

**Before this audit**, SecureLogger was missing 2 of the 8 required scrub patterns:
1. **MISSING**: `v1.sk-` OANDA key pattern -- per SS spec Section 7.1.
2. **MISSING**: Credit card pattern `\b4[0-9]{12}(?:[0-9]{3})?\b` -- per SS spec.
3. **WEAK**: Phone pattern only matched `+1XXXXXXXXXX` (US only), not international `\+?1?\d{10,15}`.
4. **WEAK**: Bearer token regex did not match `~+/=` characters per SS spec.

### Fix Applied

**File**: `backend/lumitrade/infrastructure/secure_logger.py` (lines 16-44)

Changes made:
- Added `v1.sk-` OANDA key scrub pattern: `(r"v1\.sk-[A-Za-z0-9\-._]{10,}", "[REDACTED_OANDA_KEY]")`
- Added credit card scrub pattern: `(r"\b4[0-9]{12}(?:[0-9]{3})?\b", "[REDACTED_CARD]")`
- Updated phone pattern to international: `(r"\+?1?\d{10,15}", "[REDACTED_PHONE]")`
- Updated Bearer token regex to match full spec charset: `[A-Za-z0-9\-._~+/]+=*`

**All 8 SS-spec patterns are now implemented:**
1. Bearer tokens
2. Anthropic API keys (sk-ant-)
3. SendGrid keys (SG.)
4. Telnyx keys (KEY0)
5. OANDA keys (v1.sk-)
6. Password patterns
7. Credit card patterns
8. Email addresses
Plus: API key=value patterns, generic base64 tokens, phone numbers.

### Verdict: PASS after fix.

---

## Additional Security Observations

### A. Sentry Data Scrubbing -- GOOD
`main.py:scrub_sentry_event()` strips request headers, cookies, and local variables from all stack frames before transmission to Sentry. This prevents credential leakage to third-party error tracking.

### B. Alert Service Sync Calls -- ACCEPTABLE
`alert_service.py` uses `run_in_executor()` for synchronous SendGrid and Telnyx calls. This prevents blocking the async event loop. While async libraries would be preferable, the executor pattern is safe.

### C. Position Reconciliation -- GOOD
`reconciler.py` detects ghost trades (DB says open, broker says closed) and phantom trades (broker has trade, DB doesn't). Both trigger CRITICAL alerts and create audit records. This is essential for a live trading system.

### D. Kill Switch -- PRESENT
`state/manager.py` exposes `kill_switch_active` property. The risk engine checks `RiskState.EMERGENCY_HALT` to block all trading. Manual activation path exists.

### E. Order Expiry -- GOOD
`execution_engine/engine.py` checks `machine.check_expiry(order)` with 30-second TTL before execution. This prevents stale signals from executing.

### F. Webhook URL Validation -- NOT YET NEEDED
The SS spec requires webhook URL validation with SSRF protection. No webhook functionality exists yet in the codebase. When webhooks are added (marketplace, copy trading), the validation per SS Section 5.3 MUST be implemented.

### G. API Key Hashing -- NOT YET NEEDED
The SS spec requires bcrypt hashing for user API keys. No user API key functionality exists yet. When the marketplace API is built, bcrypt hashing per SS Section 6.2 MUST be implemented.

---

## Remediation Summary

| # | Severity | Issue | Status |
|---|---|---|---|
| 1 | CRITICAL | SecureLogger missing OANDA key scrub pattern | **FIXED** |
| 2 | CRITICAL | SecureLogger missing credit card scrub pattern | **FIXED** |
| 3 | MEDIUM | SecureLogger phone pattern US-only | **FIXED** |
| 4 | MEDIUM | SecureLogger Bearer regex too narrow | **FIXED** |
| 5 | MEDIUM | Requirements not pinned with hashes | Open -- fix before live trading |
| 6 | LOW | `float()` in indicators.py for pandas | Acceptable -- documented above |
| 7 | LOW | `float()` in confidence.py for log dict | Acceptable -- documented above |
| 8 | INFO | Webhook URL validation not yet implemented | Track for marketplace phase |
| 9 | INFO | API key bcrypt hashing not yet implemented | Track for marketplace phase |

---

## Conclusion

The Lumitrade backend codebase demonstrates strong security engineering. The architecture correctly separates read-only and trading OANDA clients, uses parameterized queries exclusively, enforces TLS everywhere, sanitizes external input in prompts, and wraps all external calls in error handling with circuit breakers.

**One critical fix was applied**: SecureLogger now implements all 8 required scrub patterns per SS v2.0.

**One advisory item remains**: Pin dependency versions with hashes before switching to live trading.

**The codebase is cleared for paper trading deployment.**
**Live trading requires**: pinned dependencies with hashes, and implementation of webhook URL validation and API key hashing when those features are built.
