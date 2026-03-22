# LUMITRADE — CLAUDE CODE MASTER BUILD PROMPT
## Paste this entire prompt into Claude Code to begin building

---

## WHO YOU ARE

You are a **senior full-stack engineer** building **Lumitrade** — a production-grade, enterprise-level AI-powered forex trading SaaS. This is NOT a prototype, demo, tutorial project, or throwaway script. Every line of code you write is production code that will run against a live OANDA brokerage account with real capital.

You have been given 8 specification documents produced by a full engineering team:
- **PRD** — Product Requirements Document
- **SAS** — System Architecture Specification
- **BDS** — Backend Developer Specification
- **FDS** — Frontend Developer Specification
- **DOS** — DevOps Specification
- **SS** — Security Specification
- **UDS** — UI/UX Design Specification
- **QTS** — QA Testing Specification

You will follow these documents precisely. When a spec says something must be done a certain way, you do it that way — no shortcuts, no simplifications, no "we'll add that later."

---

## WHAT YOU ARE BUILDING

**Lumitrade** is an AI-powered forex trading system with:
- A **Python 3.11 async backend** that trades forex on OANDA using Claude AI for signal generation
- A **Next.js 14 dashboard** for real-time monitoring and control
- A **Supabase PostgreSQL** database for all state, trades, and logs
- **Cloud deployment on Railway** with a local backup failover
- **Enterprise-grade reliability**: crash recovery, circuit breakers, data validation, distributed lock failover
- **Financial-grade security**: separate API keys, IP whitelisting, log scrubbing, no secrets in code

**Phase 0 scope**: Single user (the founder), OANDA forex only (EUR/USD, GBP/USD, USD/JPY), paper trading first, live trading after 50+ successful paper trades.

---

## YOUR OPERATING RULES

### Rule 1: Always check the spec before writing code
Before implementing any module, re-read the relevant section of the specification documents. The specs are your ground truth. Do not invent architecture or patterns not specified.

### Rule 2: Never compromise on the money path
The signal → risk → execution pipeline has zero tolerance for shortcuts. Every validation check must be implemented. Every error must be caught and handled. The position sizing formula uses `Decimal`, not `float`. No exceptions.

### Rule 3: Security is non-negotiable
- API keys live ONLY in environment variables. Never in code, comments, logs, or the database.
- The `SecureLogger` scrubs ALL log output before it is written.
- `OandaTradingClient` is ONLY instantiated by `ExecutionEngine`. No other module touches it.
- `verify=False` on any HTTPS client is STRICTLY FORBIDDEN.
- Use `--require-hashes` in requirements.txt.

### Rule 4: Write tests as you build
Every module gets unit tests immediately after implementation. Do not proceed to the next module until the current module's tests pass. Critical modules (AI validator, risk engine, pip math) require 100% coverage.

### Rule 5: Follow the exact file structure
Use the exact folder and file names from the SAS specification. No renaming, no restructuring, no "cleaner" alternatives. Consistency with the spec enables the documentation to remain accurate.

### Rule 6: All financial values use Decimal
```python
from decimal import Decimal
# CORRECT
entry_price = Decimal("1.08432")
risk_pct = Decimal("0.01")

# WRONG — never do this
entry_price = 1.08432
risk_pct = 0.01
```

### Rule 7: All async, always
Every I/O operation is async. Never use `requests`, `time.sleep()`, or any blocking call inside an async context. Use `httpx.AsyncClient`, `asyncio.sleep()`, and `run_in_executor()` for blocking operations.

### Rule 8: Log everything structured
Every significant event uses the structured logger:
```python
logger.info("event_name", pair="EUR_USD", signal_id=str(signal_id), confidence=str(confidence))
```
Never use `print()`. Never use f-string log messages without keyword args.

---

## BUILD ORDER — FOLLOW THIS EXACTLY

Work through these phases in sequence. Complete all steps in a phase before moving to the next.

---

### PHASE 1: PROJECT FOUNDATION (Week 1)

**Step 1.1 — Create repository structure**
Create the complete folder/file tree from SAS Section 4 exactly as specified:
```
lumitrade/
├── backend/
│   ├── lumitrade/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── enums.py
│   │   │   └── exceptions.py
│   │   ├── data_engine/
│   │   ├── ai_brain/
│   │   ├── risk_engine/
│   │   ├── execution_engine/
│   │   ├── state/
│   │   ├── infrastructure/
│   │   └── utils/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── chaos/
│   │   └── security/
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── supervisord.conf
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── types/
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.ts
├── database/
│   └── migrations/
│       ├── 001_initial_schema.sql
│       ├── 002_add_indexes.sql
│       └── 003_add_rls_policies.sql
├── .github/
│   └── workflows/
│       ├── test.yml
│       └── deploy.yml
├── .gitignore
├── .pre-commit-config.yaml
├── .env.example
├── docker-compose.yml
└── README.md
```

**Step 1.2 — Create core files**
Implement these files exactly as specified in BDS Section 2 and 3:
- `backend/lumitrade/core/enums.py` — all 12 enums exactly as written in BDS
- `backend/lumitrade/core/models.py` — all 14 dataclasses exactly as written in BDS
- `backend/lumitrade/core/exceptions.py` — custom exception hierarchy
- `backend/lumitrade/config.py` — Pydantic Settings exactly as written in BDS Section 3

**Step 1.3 — Create infrastructure clients**
- `backend/lumitrade/infrastructure/secure_logger.py` — from BDS Section 8.1 and SS Section 7
- `backend/lumitrade/infrastructure/db.py` — from SS Section 4.1
- `backend/lumitrade/infrastructure/oanda_client.py` — from BDS Section 4.1
- `backend/lumitrade/infrastructure/alert_service.py` — from BDS Section 8.2 BUT use Telnyx instead of Twilio (see Pattern 6 below)

**Step 1.4 — Create utilities**
- `backend/lumitrade/utils/pip_math.py` — from BDS Section 10.1 (EXACT formulas — verified against test cases in QTS)
- `backend/lumitrade/utils/time_utils.py` — from BDS Section 10.2

**Step 1.5 — Create database migrations**
Create all 3 SQL migration files exactly as written in BDS Section 9.

**Step 1.6 — Create security files**
- `.gitignore` — from SS Section 3.2 (all entries required)
- `.env.example` — from SS Section 3.3 (all 17 variables)
- `.pre-commit-config.yaml` — from SS Section 3.1

**Step 1.7 — Write Phase 1 tests**
Before moving to Phase 2, all these must pass:
```bash
pytest tests/unit/test_pip_math.py -v  # All 15 tests green
pytest tests/unit/test_secure_logger.py -v  # All 6 tests green
```

---

### PHASE 2: DATA ENGINE (Week 2–3)

**Step 2.1 — Data validator**
Implement `backend/lumitrade/data_engine/validator.py` from BDS Section 4.2.
All validation logic: freshness check, spike detection (3σ), spread check, OHLC integrity, gap detection.

**Step 2.2 — Indicator computer**
Implement `backend/lumitrade/data_engine/indicators.py`.
Use pandas-ta to compute: RSI(14), MACD(12,26,9), EMA(20,50,200), ATR(14), Bollinger Bands(20,2).
Return as `IndicatorSet` dataclass. All values as `Decimal`.

**Step 2.3 — Candle fetcher**
Implement `backend/lumitrade/data_engine/candle_fetcher.py`.
Fetch OHLCV candles from OANDA REST API for M5, M15, H1, H4, D timeframes.
Validate each candle series through `DataValidator` before returning.

**Step 2.4 — Price stream manager**
Implement `backend/lumitrade/data_engine/price_stream.py`.
Connect to OANDA streaming API. Yield `PriceTick` objects. Auto-reconnect on disconnect.
Fallback: switch to REST polling every 5 seconds if stream fails 3 times.

**Step 2.5 — Economic calendar**
Implement `backend/lumitrade/data_engine/calendar.py`.
Fetch high and medium impact news events for the next 4 hours.
Return as `List[NewsEvent]`. Cache results for 30 minutes.

**Step 2.6 — Data engine orchestrator**
Implement `backend/lumitrade/data_engine/engine.py`.
Assemble `MarketSnapshot` from all data sources.
Expose `stream_task()` async method for the orchestrator.

**Step 2.7 — Write Phase 2 tests**
```bash
pytest tests/unit/test_data_validator.py -v
pytest tests/unit/test_indicators.py -v
pytest tests/chaos/test_data_failures.py -v  # All 8 chaos tests
```

---

### PHASE 3: AI BRAIN (Week 3–4)

**Step 3.1 — Prompt builder**
Implement `backend/lumitrade/ai_brain/prompt_builder.py` from BDS Section 5.1.
Implement the SYSTEM_PROMPT exactly as written. The `build_prompt()` function assembles all 7 sections.
Include `_sanitize_news_title()` from SS Section 4.2 for injection prevention.

**Step 3.2 — AI output validator**
Implement `backend/lumitrade/ai_brain/validator.py` from BDS Section 5.2.
All 8 validation steps exactly as written. This is a 100% coverage module.

**Step 3.3 — Confidence adjustment pipeline**
Implement `backend/lumitrade/ai_brain/confidence.py`.
Apply all 6 adjustment factors from PRD Section 10.3:
- Indicator alignment (×0.5 to ×1.0 multiplier)
- News proximity (−0.15 or −0.25)
- Session quality (+0.05 or −0.10)
- Spread penalty (−0.05 or reject)
- Consecutive losses (threshold shift)
- Recent pair performance (−0.10)

**Step 3.4 — Claude API client**
Implement `backend/lumitrade/ai_brain/claude_client.py`.
Use `anthropic` Python SDK. Model: `claude-sonnet-4-20250514`.
Retry protocol: 3 attempts with simplified prompt on retry 2, rule-based fallback on attempt 4.
Log every prompt hash and response to `ai_interaction_log` table.

**Step 3.5 — Rule-based fallback**
Implement `backend/lumitrade/ai_brain/fallback.py`.
When Claude API is unavailable: generate signal using indicator thresholds only.
EMA 50 > EMA 200 + RSI < 30 → BUY. EMA 50 < EMA 200 + RSI > 70 → SELL. Otherwise → HOLD.
Label output with `generation_method=RULE_BASED`.

**Step 3.6 — Signal scanner**
Implement `backend/lumitrade/ai_brain/scanner.py`.
Scan each pair on staggered 15-minute intervals (EUR/USD :00, GBP/USD :05, USD/JPY :10).
Acquire per-pair lock before scanning. Release on completion.
Write signal record to DB regardless of outcome (executed or not).

**Step 3.7 — Write Phase 3 tests**
```bash
pytest tests/unit/test_ai_validator.py -v  # All 30 tests (AIV-001 to AIV-030) — 100% required
pytest tests/unit/test_confidence.py -v
pytest tests/unit/test_prompt_builder.py -v
pytest tests/security/test_prompt_injection.py -v
```

---

### PHASE 4: RISK ENGINE (Week 4–5)

**Step 4.1 — Risk state machine**
Implement `backend/lumitrade/risk_engine/state_machine.py`.
All 7 states from SAS Section 3.2.5: NORMAL, CAUTIOUS, NEWS_BLOCK, DAILY_LIMIT, WEEKLY_LIMIT, CIRCUIT_OPEN, EMERGENCY_HALT.
State transitions triggered by: daily P&L, weekly P&L, consecutive losses, circuit breaker, kill switch.

**Step 4.2 — Position sizer**
Implement `backend/lumitrade/risk_engine/position_sizer.py`.
Use the exact formula from BDS Section 6.1:
```python
units = (balance * risk_pct) / (sl_pips * pip_value_per_unit)
units = int(units / 1000) * 1000  # Floor to micro lot
```
Always use Decimal arithmetic. Return `(units: int, risk_amount_usd: Decimal)`.

**Step 4.3 — Calendar guard**
Implement `backend/lumitrade/risk_engine/calendar_guard.py`.
Block trades 30 minutes before HIGH impact events. 15 minutes before MEDIUM impact events.
Block 15 minutes AFTER any high impact event concludes.

**Step 4.4 — Risk filters**
Implement `backend/lumitrade/risk_engine/filters.py`.
Individual filter functions for each check:
`check_risk_state`, `check_position_count`, `check_cooldown`, `check_confidence`,
`check_spread`, `check_rr_ratio`, `check_action`.
Each returns a tuple: `(rule_name, passed, reason, current_value, threshold)`.

**Step 4.5 — Risk engine orchestrator**
Implement `backend/lumitrade/risk_engine/engine.py` from BDS Section 6.1.
Run all 8 checks in sequence. First failure → `RiskRejection`. All pass → `ApprovedOrder`.
Log every rejection to `risk_events` table. Log the full check chain.

**Step 4.6 — Write Phase 4 tests**
```bash
pytest tests/unit/test_risk_engine.py -v  # All 25 tests (RE-001 to RE-025) — 100% required
pytest tests/unit/test_position_sizer.py -v
pytest tests/unit/test_calendar_guard.py -v
```

---

### PHASE 5: EXECUTION ENGINE (Week 5–6)

**Step 5.1 — Circuit breaker**
Implement `backend/lumitrade/execution_engine/circuit_breaker.py` from BDS Section 7.1.
CLOSED → OPEN (3 failures in 60s) → HALF_OPEN (after 30s) → CLOSED (on success).
Thread-safe via `asyncio.Lock`.

**Step 5.2 — Order state machine**
Implement `backend/lumitrade/execution_engine/order_machine.py`.
States: PENDING → SUBMITTED → ACKNOWLEDGED → FILLED → MANAGED → CLOSED.
Error paths: TIMEOUT → QUERY_STATUS → (FILLED or FAILED). REJECTED → log → done.
Enforce expiry: `ApprovedOrder.is_expired` → reject before submission.

**Step 5.3 — OANDA executor**
Implement `backend/lumitrade/execution_engine/oanda_executor.py`.
Place market orders with attached SL and TP via `OandaTradingClient`.
Generate `order_ref` UUID as `clientExtensions.id` for idempotency.
Before any retry: query OANDA by `order_ref` to confirm no previous fill.

**Step 5.4 — Paper executor**
Implement `backend/lumitrade/execution_engine/paper_executor.py`.
Identical interface to OANDA executor. Uses real bid/ask prices from live feed.
Simulates fill at current mid price. Stores result in DB as mode=PAPER.
NEVER calls `OandaTradingClient`.

**Step 5.5 — Fill verifier**
Implement `backend/lumitrade/execution_engine/fill_verifier.py` from BDS Section 7.2.
Check: fill price vs intended (slippage), actual units vs requested, SL/TP attached.
Alert if slippage > 3 pips. Alert CRITICAL if SL/TP missing.

**Step 5.6 — Execution engine orchestrator**
Implement `backend/lumitrade/execution_engine/engine.py`.
Route to paper or OANDA executor based on `TradingMode`.
Run fill verification on every fill. Log all outcomes to `trades` table.
Run `position_monitor()` async task every 60 seconds.

**Step 5.7 — Write Phase 5 tests**
```bash
pytest tests/unit/test_circuit_breaker.py -v
pytest tests/unit/test_order_machine.py -v
pytest tests/chaos/test_broker_failures.py -v  # All 10 chaos tests
pytest tests/chaos/test_crash_recovery.py -v   # All 10 chaos tests
```

---

### PHASE 6: STATE & ORCHESTRATION (Week 6–7)

**Step 6.1 — Distributed lock**
Implement `backend/lumitrade/state/lock.py` from DOS Section 7.4.
TTL-based lock in Supabase `system_state` table.
`acquire()`, `renew_loop()`, `release()` methods.
`renew_loop()`: renew every 60s, shutdown after 2 consecutive failures.

**Step 6.2 — Position reconciler**
Implement `backend/lumitrade/state/reconciler.py`.
Compare `open_trades` in DB against actual open trades from OANDA API.
Ghost trade (in DB, not on OANDA): mark CLOSED, UNKNOWN exit reason, CRITICAL alert.
Phantom trade (on OANDA, not in DB): create emergency record, CRITICAL alert.

**Step 6.3 — State manager**
Implement `backend/lumitrade/state/manager.py`.
`restore()`: read DB state → reconcile with OANDA → return merged state.
`save()`: write full `SystemState` to `system_state` singleton row.
`persist_loop()`: call `save()` every 30 seconds.
`get()`: return current in-memory state (refreshed from DB on startup and every 60s).

**Step 6.4 — Health server**
Implement `backend/lumitrade/infrastructure/health_server.py` from DOS Section 6.4.
Separate aiohttp process. Reads system state from DB. Returns full JSON health payload.
Returns 200 if healthy, 503 if degraded. Runs on port 8000.

**Step 6.5 — Watchdog**
Implement `backend/lumitrade/infrastructure/watchdog.py`.
Monitor: main engine heartbeat (every 30s), primary lock age, state persist freshness.
Alert on anomalies. Log all watchdog events.

**Step 6.6 — Main orchestrator**
Implement `backend/lumitrade/main.py` from BDS Section 11.1 exactly.
Startup sequence: load config → connect DB → restore state → acquire lock → validate OANDA → start all 6 tasks.
Shutdown sequence: stop scans → wait for in-flight → persist state → release lock → close connections.
Handle SIGTERM and SIGINT gracefully.

**Step 6.7 — Write Phase 6 tests**
```bash
pytest tests/chaos/test_failover.py -v  # All 6 failover tests
pytest tests/integration/test_signal_pipeline.py -v  # All 10 pipeline tests
pytest tests/integration/test_database.py -v  # All 10 DB tests
```

---

### PHASE 7: DASHBOARD FRONTEND (Week 7–9)

**Step 7.1 — Project setup**
Initialize Next.js 14 with TypeScript strict mode.
Install all dependencies from FDS Section 11.1 (`package.json`).
Configure Tailwind from FDS Section 8.1 exactly (all CSS variables, all custom colors, DM Sans + JetBrains Mono + Space Grotesk fonts).
Create `globals.css` from FDS Section 8.2 exactly.

**Step 7.2 — Types and utilities**
- `src/types/trading.ts` — from FDS Section 3.1 exactly
- `src/types/system.ts` — from FDS Section 3.2 exactly
- `src/lib/formatters.ts` — from FDS Section 10.1 exactly
- `src/lib/supabase.ts` — Supabase browser and server clients

**Step 7.3 — Follow the build order from FDS Section 12.1**
Build components in the exact sequence specified (items 1–36).
DO NOT skip ahead. Dependencies must be in place before dependents.
Key sequence: types → formatters → hooks → UI primitives → layout → signal components → dashboard components → API routes → analytics → trades → settings.

**Step 7.4 — Critical components**
These require special care — implement exactly as specified:
- `SignalDetailPanel.tsx` — the full AI reasoning view is Lumitrade's key differentiator
- `KillSwitchButton.tsx` — two-step typed confirmation, no exceptions
- `SystemStatusPanel.tsx` — all 6 components with correct status dot colors
- `ConfidenceBar.tsx` — color changes at exactly 65% (amber) and 80% (green) thresholds

**Step 7.5 — API routes**
Implement all 10 API routes from FDS Section 9 and as specified in the PRD.
Every route calls `requireAuth()` first. No unauthenticated data access.
Kill switch route writes EMERGENCY_HALT to `system_state` and logs to `system_events`.

**Step 7.6 — Middleware**
Implement `src/middleware.ts` from SS Section 6.1.
Protect all dashboard routes. Redirect unauthenticated users to `/auth/login`.

**Step 7.7 — Security headers**
Add all 6 security headers to `next.config.ts` from SS Section 5.2.
Content-Security-Policy must restrict to Supabase domains only.

**Step 7.8 — Write Phase 7 tests**
```bash
# E2E tests require running frontend + backend
pytest tests/e2e/ -v  # Target: all 20 E2E tests passing
```

---

### PHASE 8: INFRASTRUCTURE & HARDENING (Week 9–10)

**Step 8.1 — Dockerfile**
Implement `backend/Dockerfile` from DOS Section 2.1 exactly.
Multi-stage build. Non-root user. Health check endpoint.

**Step 8.2 — Supervisord config**
Implement `backend/supervisord.conf` from DOS Section 2.2 exactly.
Two programs: `lumitrade-engine` and `lumitrade-health`. Both autostart and autorestart.

**Step 8.3 — GitHub Actions**
Implement `.github/workflows/test.yml` from DOS Section 3.1 exactly.
Implement `.github/workflows/deploy.yml` from DOS Section 3.2 exactly.
The test workflow must include the gitleaks secrets scan step.

**Step 8.4 — Railway configuration**
Create `railway.toml` from DOS Section 4.1.
Set health check path to `/health`. Restart policy: on_failure, max 5 retries.

**Step 8.5 — Pre-commit hooks**
Install `.pre-commit-config.yaml` from SS Section 3.1.
Run: `pre-commit install && pre-commit run --all-files` — must pass clean.

**Step 8.6 — Full test suite**
```bash
pytest tests/ -v --cov=lumitrade --cov-report=term-missing
# Target: 75%+ overall coverage, 100% on critical modules
```

**Step 8.7 — Security audit**
Run through all 27 items in SS Section 9.1.
Run: `gitleaks detect --source . --log-opts="--all"` — must return zero findings.
Run: `npm audit` in frontend — must return zero high/critical vulnerabilities.

---

### PHASE 9: PAPER TRADING (Week 10–12)

**Step 9.1 — Deploy to Railway**
Push to main branch. Confirm CI passes. Confirm Railway deploys. Confirm `/health` returns 200.

**Step 9.2 — Configure monitoring**
Set up UptimeRobot to ping `/health` every 5 minutes.
Confirm SMS alert fires when service is manually taken down.
Confirm Sentry receives a test error event.

**Step 9.3 — Run paper trading for minimum 2 weeks**
System runs in PAPER mode. Do not switch to LIVE until:
- 50+ paper trades logged
- Win rate ≥ 40%
- 7 consecutive days without crash
- All 13 go/no-go gates in QTS Section 8.2 pass

**Step 9.4 — Pre-live checklist**
Complete all 25 items in DOS Section 9.1.
Complete all 27 items in SS Section 9.1.
Complete all 13 Go/No-Go gates in QTS Section 8.2.

---

## KEY TECHNICAL DECISIONS (DO NOT DEVIATE)

| Decision | Value | Reason |
|---|---|---|
| Language | Python 3.11 | pandas-ta, best async, finance ecosystem |
| Async | asyncio throughout | I/O-bound workloads, no GIL issues |
| Financial arithmetic | `Decimal` always | Exact arithmetic, no float rounding errors |
| AI model | `claude-sonnet-4-20250514` | Best structured JSON reasoning |
| Database | Supabase (PostgreSQL) | Realtime subscriptions, managed, RLS |
| Frontend | Next.js 14 App Router | SSR, Supabase native, TypeScript |
| Styling | Tailwind + CSS variables | Dark terminal theme, maintainable |
| Charts | Recharts | React-native, good TypeScript support |
| Hosting | Railway | Simplest persistent process hosting |
| Secrets | Environment variables only | Never in code, ever |
| HTTP client | httpx.AsyncClient | Async-native, TLS 1.3 |
| Logging | structlog (JSON) | Structured, queryable, scrubbable |
| Process mgmt | Supervisord | Auto-restart, log rotation |
| Testing | pytest + playwright | Best Python async test support |

---

## CRITICAL PATTERNS — COPY THESE EXACTLY

### Pattern 1: Every async function that calls an external API
```python
async def call_oanda_api(self) -> dict:
    state = await self.circuit_breaker.check_and_transition()
    if state == CircuitBreakerState.OPEN:
        raise CircuitBreakerOpenError("OANDA API circuit breaker is open")
    try:
        result = await self._client.get(url)
        result.raise_for_status()
        await self.circuit_breaker.record_success()
        return result.json()
    except httpx.HTTPStatusError as e:
        await self.circuit_breaker.record_failure()
        logger.error("oanda_api_error", status=e.response.status_code, url=str(url))
        raise
    except Exception as e:
        await self.circuit_breaker.record_failure()
        logger.error("oanda_api_unexpected_error", error=str(e))
        raise
```

### Pattern 2: Every DB operation
```python
# CORRECT — parameterized via Supabase client
result = await self.db.select("trades", {"account_id": account_id, "status": "OPEN"})

# WRONG — never do this
result = await self.db.raw_sql(f"SELECT * FROM trades WHERE account_id = '{account_id}'")
```

### Pattern 3: Every log entry
```python
# CORRECT — structured with keyword args
logger.info("trade_opened", pair="EUR_USD", direction="BUY",
            entry=str(entry_price), units=units, signal_id=str(signal_id))

# WRONG — never do this
logger.info(f"Trade opened: {pair} {direction} at {entry_price}")
print(f"Trade: {pair}")  # NEVER use print()
```

### Pattern 4: Every financial calculation
```python
# CORRECT
from decimal import Decimal
risk_amount = Decimal(str(balance)) * Decimal("0.01")
sl_pips = abs(entry_price - stop_loss) / pip_size(pair)

# WRONG
risk_amount = float(balance) * 0.01
sl_pips = abs(float(entry_price) - float(stop_loss)) / 0.0001
```

### Pattern 5: Every component that displays P&L
```tsx
// CORRECT — color is semantic, never decorative
const { formatted, colorClass } = formatPnl(trade.pnl_usd);
return <span className={`font-mono ${colorClass}`}>{formatted}</span>;

// WRONG — hardcoding colors
return <span className="text-green-500">{trade.pnl_usd}</span>;
```

### Pattern 6: Alert service — use Telnyx via raw httpx (NO Twilio, NO telnyx SDK)
The BDS Section 8.2 shows a Twilio implementation. **Ignore it. Use this instead.**
No new dependency needed — httpx is already in the stack.

```python
# infrastructure/alert_service.py — Telnyx implementation
import asyncio
import httpx
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from ..config import config
from .secure_logger import get_logger
from ..infrastructure.db import DatabaseClient

logger = get_logger(__name__)

TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"

class AlertService:
    """Delivers SMS via Telnyx and email via SendGrid. All sends logged."""

    def __init__(self, db: DatabaseClient):
        self.db = db

    async def send_info(self, message: str):
        """Low-priority: queue for daily digest. No immediate SMS."""
        await self._log_alert("INFO", message, channel="email_queue")

    async def send_warning(self, message: str):
        """Medium-priority: send immediate email."""
        await asyncio.get_event_loop().run_in_executor(
            None, self._send_email, "WARNING", message
        )
        await self._log_alert("WARNING", message, channel="email")

    async def send_error(self, message: str):
        """High-priority: send SMS immediately."""
        await asyncio.get_event_loop().run_in_executor(
            None, self._send_sms_sync, message
        )
        await self._log_alert("ERROR", message, channel="sms")

    async def send_critical(self, message: str):
        """Critical: SMS + email simultaneously."""
        await asyncio.gather(
            asyncio.get_event_loop().run_in_executor(
                None, self._send_sms_sync, f"CRITICAL: {message}"
            ),
            asyncio.get_event_loop().run_in_executor(
                None, self._send_email, "CRITICAL", message
            ),
        )
        await self._log_alert("CRITICAL", message, channel="sms+email")

    def _send_sms_sync(self, body: str):
        """Synchronous Telnyx SMS via httpx (run in executor)."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    TELNYX_MESSAGES_URL,
                    headers={
                        "Authorization": f"Bearer {config.telnyx_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": config.telnyx_from_number,
                        "to": config.alert_sms_to,
                        "text": f"[LUMITRADE] {body}",
                    },
                )
                response.raise_for_status()
                logger.info("sms_sent",
                           message_id=response.json().get("data", {}).get("id"))
        except Exception as e:
            logger.error("sms_send_failed", error=str(e))

    def _send_email(self, level: str, body: str):
        """Send email via SendGrid."""
        try:
            sg = SendGridAPIClient(config.sendgrid_api_key)
            mail = Mail(
                from_email="alerts@lumitrade.app",
                to_emails=config.alert_email_to,
                subject=f"[Lumitrade {level}] {body[:80]}",
                plain_text_content=body,
            )
            sg.send(mail)
            logger.info("email_sent", level=level)
        except Exception as e:
            logger.error("email_send_failed", error=str(e))

    async def _log_alert(self, level: str, message: str, channel: str):
        from datetime import datetime, timezone
        await self.db.insert("alerts_log", {
            "level": level,
            "message": message,
            "channel": channel,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
```

**Also add to config.py** (in the `LumitradeConfig` class, replacing the Twilio fields):
```python
# Telnyx — telnyx.com portal → API Keys
telnyx_api_key: str     = Field(alias="TELNYX_API_KEY")
telnyx_from_number: str = Field(alias="TELNYX_FROM_NUMBER")
alert_sms_to: str       = Field(alias="ALERT_SMS_TO")

# SendGrid
sendgrid_api_key: str   = Field(alias="SENDGRID_API_KEY")
alert_email_to: str     = Field(alias="ALERT_EMAIL_TO")
```

**Also update requirements.txt** — remove `twilio==8.13.0`. No replacement needed. httpx already handles Telnyx calls.

---

## ENVIRONMENT VARIABLES YOU NEED

Before starting, ensure these are available in your `.env` file:
```
OANDA_API_KEY_DATA=        # Read-only key from OANDA developer portal
OANDA_API_KEY_TRADING=     # Trading key from OANDA developer portal
OANDA_ACCOUNT_ID=          # Your OANDA account ID (not the key)
OANDA_ENVIRONMENT=practice # Start with practice always
ANTHROPIC_API_KEY=         # From console.anthropic.com
SUPABASE_URL=              # From Supabase project settings
SUPABASE_SERVICE_KEY=      # From Supabase project settings (server only)
NEXT_PUBLIC_SUPABASE_ANON_KEY= # From Supabase project settings (browser)
TELNYX_API_KEY=            # From Telnyx portal → API Keys → Create key
TELNYX_FROM_NUMBER=        # Your Telnyx number (e.g. +12065550100)
ALERT_SMS_TO=              # Your personal phone number
SENDGRID_API_KEY=          # From SendGrid dashboard
ALERT_EMAIL_TO=            # Your email address
INSTANCE_ID=cloud-primary  # This instance identifier
TRADING_MODE=PAPER         # ALWAYS start with PAPER
LOG_LEVEL=INFO
```

---

## HOW TO START RIGHT NOW

**Tell me which phase to start and I will begin immediately.**

Recommended starting command:
```
Start Phase 1. Create the complete repository structure and implement all core files as specified.
```

Or if you want to start a specific component:
```
Start Phase 1, Step 1.2. Implement core/enums.py and core/models.py exactly as specified in the BDS.
```

Or to resume work:
```
I am resuming work on Lumitrade. We completed [Phase X, Step Y]. Continue from [Phase X, Step Z].
Here is the current state of the codebase: [paste relevant files or describe what exists]
```

---

## WHAT SUCCESS LOOKS LIKE

At the end of Phase 9, Lumitrade will be:
- Running 24/7 on Railway, scanning EUR/USD, GBP/USD, USD/JPY every 15 minutes
- Generating AI-powered trading signals using Claude Sonnet
- Paper trading with 50+ completed trades and documented performance
- Accessible via a real-time web dashboard showing account, positions, signals, and analytics
- Monitored by UptimeRobot with SMS alerts for any downtime
- Protected by enterprise-grade security: IP whitelisting, separate API keys, encrypted secrets, log scrubbing
- Ready to switch to LIVE trading once all 13 go/no-go gates are confirmed

**This is Lumitrade. Let's build it.**

---

# ADDITION SET A: SELF-IMPROVEMENT + ADAPTIVE SIZING FOUNDATIONS
## Paste this alongside the master prompt — these additions are from earlier sessions

# LUMITRADE — ADDITIONS PROMPT
## Paste this AFTER the master build prompt, or at the start of a new Claude Code session

---

## CONTEXT

This prompt contains three sets of additions to the Lumitrade master build.
They emerged from product thinking sessions after the original spec was written.
They do NOT change the Phase 0 architecture — they slot cleanly into it.
Build these additions alongside the phases they belong to.

---

## ADDITION SET 1: SELF-IMPROVEMENT FOUNDATION
### Build during: Phase 3 (AI Brain), after prompt_builder.py is complete

These four additions do nothing in Phase 0 but make the self-improvement
system a simple Phase 2 feature instead of a painful restructure.

---

### 1A — New Database Migration

Create file: `database/migrations/004_performance_insights.sql`

```sql
-- Performance insights table
-- Stores AI-generated findings about trading patterns.
-- Phase 0: Empty — populated once 50+ trades are logged.
-- Phase 2: Auto-populated by PerformanceAnalyzer every 10 trades.

CREATE TABLE performance_insights (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID REFERENCES accounts(id),
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    insight_type    TEXT NOT NULL,
    -- Values: SESSION_PERFORMANCE | PAIR_WIN_RATE |
    --         INDICATOR_ACCURACY  | PROMPT_PATTERN |
    --         VOLATILITY_FILTER   | NEWS_IMPACT
    scope           TEXT NOT NULL,
    -- Examples: 'EUR_USD' | 'LONDON' | 'RSI_OVERSOLD' | 'GBP_USD_TOKYO'
    finding         TEXT NOT NULL,
    -- Plain English: "EUR/USD in TOKYO session has 31% win rate over 42 trades"
    data            JSONB,
    -- Raw numbers: {"win_rate": 0.31, "sample_size": 42, "avg_pips": -2.1}
    recommendation  TEXT,
    -- Action: "Reduce position size to 0.5% for EUR/USD during TOKYO session"
    applied         BOOLEAN NOT NULL DEFAULT FALSE,
    -- Has the system acted on this insight yet?
    confidence      DECIMAL(4,3),
    -- Statistical confidence 0.0-1.0 (requires min sample size to be meaningful)
    expires_at      TIMESTAMPTZ
    -- Insights become stale — recalculate after significant new data
);

CREATE INDEX idx_insights_account_scope
    ON performance_insights(account_id, scope, applied);
CREATE INDEX idx_insights_account_type
    ON performance_insights(account_id, insight_type, generated_at DESC);
```

---

### 1B — Prompt Builder Addition

In `backend/lumitrade/ai_brain/prompt_builder.py`:

Add this method to the `PromptBuilder` class:

```python
async def _get_performance_insights(self, pair: str) -> str:
    """
    Returns recent performance insights for this currency pair.

    Phase 0: Always returns 'no insights yet' — insufficient data.
    Phase 2: Returns real pattern findings from PerformanceAnalyzer.

    This slot exists in the prompt structure now so that when
    PerformanceAnalyzer starts populating the table, the insights
    appear in AI reasoning automatically — zero prompt changes needed.
    """
    try:
        insights = await self.db.select(
            "performance_insights",
            {
                "account_id": self.account_id,
                "scope":      pair,
                "applied":    False,
            },
            order="confidence",
            limit=3,
        )
    except Exception:
        # Never let insight retrieval break signal generation
        return "  No performance insights available."

    if not insights:
        return "  No performance insights yet — insufficient trade history."

    lines = [f"Recent performance patterns identified for {pair}:"]
    for insight in insights:
        lines.append(f"  • {insight['finding']}")
        if insight.get("recommendation"):
            lines.append(f"    Suggested adjustment: {insight['recommendation']}")
    return "\n".join(lines)
```

Then add the PERFORMANCE INSIGHTS section to the `build_prompt()` sections list,
between RECENT TRADES and YOUR TASK:

```python
sections = [
    "=== MARKET CONTEXT ===",
    # ... existing sections ...
    "=== RECENT TRADES ON THIS PAIR (last 3) ===",
    _format_recent_trades(snapshot.recent_trades),
    "",
    "=== PERFORMANCE INSIGHTS ===",
    await self._get_performance_insights(snapshot.pair),   # ← ADD THIS
    "",
    "=== YOUR TASK ===",
    # ... existing task section ...
]
```

---

### 1C — Post-Trade Hook in Execution Engine

In `backend/lumitrade/execution_engine/engine.py`:

Add the trigger method and hook call to `_close_trade()`:

```python
async def _close_trade(self, trade: Trade, exit_reason: ExitReason):
    """Close a trade and trigger self-improvement analysis."""

    # --- existing close logic (log, update DB, send alert) ---
    # ... keep all existing code here unchanged ...

    # Self-improvement hook
    # Silent no-op until MIN_TRADES reached.
    # Activates automatically at trade 50 — no future code changes needed.
    await self._trigger_insight_analysis(trade)


async def _trigger_insight_analysis(self, trade: Trade):
    """
    Queues a performance analysis pass after each trade closes.

    Phase 0 behavior: does nothing — returns silently below MIN_TRADES.
    Phase 2 behavior: runs full PerformanceAnalyzer every 10 trades.

    The performance_analyzer attribute is injected in __init__ as a stub.
    When Phase 2 implements the analyzer, this hook is already wired up.
    """
    MIN_TRADES_FOR_ANALYSIS = 50
    ANALYSIS_EVERY_N_TRADES = 10

    try:
        trade_count = await self.db.count(
            "trades",
            {"account_id": trade.account_id, "status": "CLOSED"}
        )
    except Exception as e:
        logger.warning("insight_trigger_count_failed", error=str(e))
        return

    if trade_count < MIN_TRADES_FOR_ANALYSIS:
        logger.debug("insight_trigger_skipped_insufficient_data",
                    trade_count=trade_count,
                    required=MIN_TRADES_FOR_ANALYSIS)
        return

    if trade_count % ANALYSIS_EVERY_N_TRADES == 0:
        logger.info("insight_analysis_triggered", trade_count=trade_count)
        asyncio.create_task(
            self.performance_analyzer.analyze(trade.account_id),
            name=f"insight_analysis_{trade_count}"
        )
```

Also add `self.performance_analyzer` to `ExecutionEngine.__init__()`:

```python
from ..analytics.performance_analyzer import PerformanceAnalyzer

class ExecutionEngine:
    def __init__(self, oanda_client, state_manager, db, alert_service):
        # ... existing init code ...
        self.performance_analyzer = PerformanceAnalyzer(db)  # ← ADD THIS
```

---

### 1D — PerformanceAnalyzer Stub

Create file: `backend/lumitrade/analytics/__init__.py` (empty)

Create file: `backend/lumitrade/analytics/performance_analyzer.py`

```python
"""
Lumitrade Performance Analyzer
================================
Analyzes trade history to generate performance insights.
Stores findings in the performance_insights table.
The prompt builder reads these findings and includes them in AI signals.

Phase 0: Stub — all analysis methods are TODO stubs.
         The class exists and is importable.
         The hook in ExecutionEngine calls analyze() but it does nothing.

Phase 2 implementation plan (uncomment when 50+ trades exist):
    1. _analyze_session_performance  — find best/worst trading sessions
    2. _analyze_pair_performance     — find best/worst pairs
    3. _analyze_indicator_accuracy   — find which indicators predicted wins
    4. _analyze_confidence_calibration — does 80% confidence actually win 80%?
    5. _analyze_prompt_patterns      — what language in reasoning predicts wins

Phase 3 implementation plan (uncomment when 500+ trades exist):
    6. _evolve_prompt_instructions   — update system prompt based on patterns
    7. _update_session_filters       — auto-adjust session blackout windows
    8. _update_confidence_thresholds — auto-raise thresholds for weak conditions
"""

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class PerformanceAnalyzer:
    """
    Reads the trade log and generates actionable performance insights.
    Insights are stored to performance_insights table and picked up
    automatically by the prompt builder on the next signal scan.
    """

    MIN_SAMPLE_SIZE = 20       # Minimum trades to draw any conclusion
    HIGH_CONFIDENCE_MIN = 30   # Minimum trades for high-confidence insight

    def __init__(self, db: DatabaseClient):
        self.db = db

    async def analyze(self, account_id: str) -> None:
        """
        Entry point. Called by ExecutionEngine after every 10th trade.
        Runs all analysis modules and stores insights to DB.

        Phase 0: Does nothing — all modules are stubs.
        """
        logger.info("performance_analysis_started", account_id=account_id)

        # TODO Phase 2: Uncomment these one by one as you implement them
        # await self._analyze_session_performance(account_id)
        # await self._analyze_pair_performance(account_id)
        # await self._analyze_indicator_accuracy(account_id)
        # await self._analyze_confidence_calibration(account_id)
        # await self._analyze_prompt_patterns(account_id)

        # TODO Phase 3: Uncomment after Phase 2 is proven stable
        # await self._evolve_prompt_instructions(account_id)
        # await self._update_session_filters(account_id)
        # await self._update_confidence_thresholds(account_id)

        logger.info("performance_analysis_completed",
                   account_id=account_id,
                   note="Phase 0 stub — no analysis performed yet")

    # ── Phase 2 stubs ─────────────────────────────────────────────

    async def _analyze_session_performance(self, account_id: str) -> None:
        """
        TODO Phase 2:
        Query trades grouped by session (LONDON, NEW_YORK, OVERLAP, TOKYO).
        For each session with MIN_SAMPLE_SIZE trades:
          - Calculate win rate
          - Calculate avg pips
          - Compare to overall win rate
        If session win rate is >15% below average → store LOW_WIN_RATE insight
        If session win rate is >15% above average → store HIGH_WIN_RATE insight
        Store findings to performance_insights with scope=session_name
        """
        pass

    async def _analyze_pair_performance(self, account_id: str) -> None:
        """
        TODO Phase 2:
        Query trades grouped by pair (EUR_USD, GBP_USD, USD_JPY).
        For each pair with MIN_SAMPLE_SIZE trades:
          - Calculate win rate, avg win pips, avg loss pips, profit factor
          - Identify best and worst performing pair
        Store findings to performance_insights with scope=pair_name
        """
        pass

    async def _analyze_indicator_accuracy(self, account_id: str) -> None:
        """
        TODO Phase 2:
        For trades with indicators_snapshot stored:
          - When RSI was oversold (<30) at signal: what was win rate?
          - When RSI was overbought (>70) at signal: what was win rate?
          - When MACD histogram was positive: what was win rate on BUY signals?
          - When all 3 EMAs were aligned: what was win rate?
        Store accuracy scores to performance_insights
        """
        pass

    async def _analyze_confidence_calibration(self, account_id: str) -> None:
        """
        TODO Phase 2:
        Check whether AI confidence scores are calibrated:
          - Trades with confidence 0.65-0.70: actual win rate?
          - Trades with confidence 0.70-0.80: actual win rate?
          - Trades with confidence 0.80-0.90: actual win rate?
          - Trades with confidence 0.90+:     actual win rate?
        If confidence 0.80 signals only win 45% of the time →
        the AI is overconfident → raise confidence threshold
        Store calibration findings to performance_insights
        """
        pass

    async def _analyze_prompt_patterns(self, account_id: str) -> None:
        """
        TODO Phase 2:
        Query the AI reasoning text for all closed trades.
        For winning trades: find phrases that appear most frequently
        For losing trades:  find phrases that appear most frequently
        Phrases that appear in wins but not losses = positive signals
        Phrases that appear in losses but not wins = warning signals
        Store pattern findings to performance_insights
        These get included in the next signal prompt automatically
        """
        pass

    # ── Phase 3 stubs ─────────────────────────────────────────────

    async def _evolve_prompt_instructions(self, account_id: str) -> None:
        """
        TODO Phase 3 (requires 500+ trades):
        Based on prompt pattern analysis findings:
        Generate updated prompt instruction additions like:
          "Pay extra attention to EMA alignment — appears in 73% of wins"
          "Be cautious with consolidating markets — appears in 71% of losses"
        These additions are stored and injected into the PERFORMANCE
        INSIGHTS section of the prompt automatically.
        """
        pass

    async def _update_session_filters(self, account_id: str) -> None:
        """
        TODO Phase 3 (requires 200+ trades per session):
        Based on session performance analysis:
        If TOKYO session win rate < 35% over 50+ trades →
        recommend adding TOKYO to session blackout for affected pairs.
        Store recommendation to performance_insights for operator review.
        Do NOT auto-apply — require operator approval via dashboard.
        """
        pass

    async def _update_confidence_thresholds(self, account_id: str) -> None:
        """
        TODO Phase 3 (requires confidence calibration data):
        Based on confidence calibration findings:
        If confidence 0.65-0.70 signals win only 38% of the time →
        recommend raising minimum confidence threshold to 0.72.
        Store recommendation to performance_insights for operator review.
        Do NOT auto-apply — require operator approval via dashboard.
        """
        pass
```

---

## ADDITION SET 2: ADAPTIVE POSITION SIZING
### Build during: Phase 4 (Risk Engine), after position_sizer.py is complete

The current position sizer uses fixed confidence-to-risk-percentage mapping.
This addition extends it to include recent performance context in the AI prompt,
allowing Claude to recommend position size adjustments based on track record.

---

### 2A — Add Performance Context to MarketSnapshot

In `backend/lumitrade/core/models.py`, add a new dataclass:

```python
@dataclass(frozen=True)
class PerformanceContext:
    """
    Recent performance metrics passed to AI for adaptive position sizing.
    Populated from trade history. Empty/default values in Phase 0.
    """
    last_10_win_rate:           Decimal   # 0.0 if fewer than 10 trades
    last_10_avg_pips:           Decimal   # 0.0 if fewer than 10 trades
    consecutive_wins:           int       # Current winning streak
    consecutive_losses:         int       # Current losing streak
    current_drawdown_from_peak: Decimal   # 0.0 if at equity peak
    account_growth_this_week:   Decimal   # % change from Monday open
    market_volatility:          str       # LOW | NORMAL | HIGH (from ATR)
    trend_strength:             str       # WEAK | MODERATE | STRONG (from EMAs)
    sample_size:                int       # How many trades are in this calc
    is_sufficient_data:         bool      # True only if sample_size >= 20
```

Add `performance_context: PerformanceContext` field to `MarketSnapshot`:

```python
@dataclass(frozen=True)
class MarketSnapshot:
    # ... existing fields ...
    performance_context: PerformanceContext    # ← ADD THIS
```

---

### 2B — Performance Context Builder

Create file: `backend/lumitrade/analytics/performance_context_builder.py`

```python
"""
Builds PerformanceContext from trade history for each signal scan.
Provides the AI with recent performance data for adaptive sizing decisions.
"""

from decimal import Decimal
from datetime import datetime, timezone, timedelta
from ..core.models import PerformanceContext
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

MIN_TRADES_FOR_CONTEXT = 20


class PerformanceContextBuilder:
    """Builds PerformanceContext from the trade history database."""

    def __init__(self, db: DatabaseClient):
        self.db = db

    async def build(
        self, account_id: str, pair: str, current_atr: Decimal
    ) -> PerformanceContext:
        """
        Build PerformanceContext for the current signal scan.
        Returns default empty context if insufficient trade history.
        """
        try:
            return await self._build_context(account_id, pair, current_atr)
        except Exception as e:
            logger.warning("performance_context_build_failed", error=str(e))
            return self._empty_context()

    async def _build_context(
        self, account_id: str, pair: str, current_atr: Decimal
    ) -> PerformanceContext:
        # Get last 10 closed trades for this pair
        recent_trades = await self.db.select(
            "trades",
            {"account_id": account_id, "status": "CLOSED"},
            order="closed_at",
            limit=10,
        )

        if len(recent_trades) < MIN_TRADES_FOR_CONTEXT:
            return self._empty_context()

        # Win rate over last 10 trades
        wins = sum(1 for t in recent_trades if t["outcome"] == "WIN")
        win_rate = Decimal(str(wins)) / Decimal("10")

        # Average pips over last 10 trades
        pnl_values = [
            Decimal(str(t["pnl_pips"]))
            for t in recent_trades
            if t.get("pnl_pips") is not None
        ]
        avg_pips = (
            sum(pnl_values) / Decimal(str(len(pnl_values)))
            if pnl_values else Decimal("0")
        )

        # Consecutive wins/losses (from most recent backward)
        consecutive_wins = 0
        consecutive_losses = 0
        for t in reversed(recent_trades):
            if t["outcome"] == "WIN":
                if consecutive_losses > 0:
                    break
                consecutive_wins += 1
            elif t["outcome"] == "LOSS":
                if consecutive_wins > 0:
                    break
                consecutive_losses += 1
            else:
                break

        # Account growth this week
        monday = datetime.now(timezone.utc) - timedelta(
            days=datetime.now(timezone.utc).weekday()
        )
        week_snapshot = await self.db.select_one(
            "performance_snapshots",
            {"account_id": account_id},
        )
        week_growth = Decimal("0")
        if week_snapshot and week_snapshot.get("starting_balance"):
            current = Decimal(str(week_snapshot.get("ending_balance", 0)))
            start = Decimal(str(week_snapshot["starting_balance"]))
            if start > 0:
                week_growth = (current - start) / start

        # Market volatility from ATR
        # These thresholds are approximate — adjust based on your pairs
        if current_atr < Decimal("0.0005"):
            volatility = "LOW"
        elif current_atr > Decimal("0.0015"):
            volatility = "HIGH"
        else:
            volatility = "NORMAL"

        return PerformanceContext(
            last_10_win_rate=win_rate,
            last_10_avg_pips=avg_pips,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            current_drawdown_from_peak=Decimal("0"),  # TODO: implement peak tracking
            account_growth_this_week=week_growth,
            market_volatility=volatility,
            trend_strength="MODERATE",  # TODO: compute from EMA spread
            sample_size=len(recent_trades),
            is_sufficient_data=True,
        )

    def _empty_context(self) -> PerformanceContext:
        """Returns a safe default when insufficient data exists."""
        return PerformanceContext(
            last_10_win_rate=Decimal("0"),
            last_10_avg_pips=Decimal("0"),
            consecutive_wins=0,
            consecutive_losses=0,
            current_drawdown_from_peak=Decimal("0"),
            account_growth_this_week=Decimal("0"),
            market_volatility="NORMAL",
            trend_strength="MODERATE",
            sample_size=0,
            is_sufficient_data=False,
        )
```

---

### 2C — Update Prompt Builder for Adaptive Sizing

In `backend/lumitrade/ai_brain/prompt_builder.py`:

Add a performance context formatter and include it in the prompt:

```python
def _format_performance_context(self, ctx: PerformanceContext) -> str:
    """
    Format recent performance context for the AI.
    Only included when sufficient data exists (20+ trades).
    Guides Claude toward appropriate position size recommendations.
    """
    if not ctx.is_sufficient_data:
        return ("  Insufficient trade history for adaptive sizing.\n"
                "  Use standard confidence-based position sizing.")

    lines = [
        f"  Recent win rate (last 10 trades): {ctx.last_10_win_rate:.0%}",
        f"  Average pips (last 10 trades):    {ctx.last_10_avg_pips:+.1f}",
        f"  Current streak: "
        f"{'%d consecutive wins' % ctx.consecutive_wins if ctx.consecutive_wins > 0 else '%d consecutive losses' % ctx.consecutive_losses if ctx.consecutive_losses > 0 else 'no streak'}",
        f"  Account growth this week:          {ctx.account_growth_this_week:+.1%}",
        f"  Market volatility (ATR):           {ctx.market_volatility}",
        f"  Trend strength (EMA alignment):    {ctx.trend_strength}",
        "",
        "  When recommending risk_pct, consider:",
        "  - Recent win rate above 60% + strong trend + low volatility → up to 1.5%",
        "  - Recent win rate below 40% OR 3+ consecutive losses → cap at 0.5%",
        "  - Default: 0.5% to 1.0% based on signal confidence",
        "  - Hard limits enforced by risk engine: min 0.25%, max 2.0%",
    ]
    return "\n".join(lines)
```

Add `recommended_risk_pct` and `risk_reasoning` to the AI output schema
in the SYSTEM_PROMPT:

```python
SYSTEM_PROMPT = """You are Lumitrade's professional forex trading analyst.
...
REQUIRED JSON SCHEMA:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "entry_price": float,
  "stop_loss": float,
  "take_profit": float,
  "recommended_risk_pct": 0.0025-0.02,   ← ADD THIS (0.25% to 2.0%)
  "risk_reasoning": "1-2 sentences explaining the position size recommendation",  ← ADD THIS
  "summary": "2-4 plain English sentences. No jargon.",
  ...
}
"""
```

---

### 2D — Update AI Output Validator

In `backend/lumitrade/ai_brain/validator.py`:

Add validation for the two new fields:

```python
# Add to REQUIRED_FIELDS list — but make these optional with defaults
OPTIONAL_FIELDS_WITH_DEFAULTS = {
    "recommended_risk_pct": Decimal("0.01"),   # Default to 1% if missing
    "risk_reasoning": "No risk reasoning provided.",
}

# In the validate() method, after required fields check:
# Handle optional fields — use defaults if missing
for field, default in OPTIONAL_FIELDS_WITH_DEFAULTS.items():
    if field not in data:
        data[field] = default

# Validate recommended_risk_pct bounds
if "recommended_risk_pct" in data:
    try:
        rp = Decimal(str(data["recommended_risk_pct"]))
        if not (Decimal("0.0025") <= rp <= Decimal("0.02")):
            # Out of bounds — use default instead of failing
            data["recommended_risk_pct"] = Decimal("0.01")
            logger.warning("recommended_risk_pct_out_of_bounds",
                          value=str(rp))
    except Exception:
        data["recommended_risk_pct"] = Decimal("0.01")
```

---

### 2E — Update Risk Engine to Use AI Recommendation

In `backend/lumitrade/risk_engine/engine.py`:

Update `_confidence_to_risk_pct()` to consider AI recommendation
when performance context has sufficient data:

```python
def _determine_risk_pct(
    self,
    proposal: SignalProposal,
    has_sufficient_performance_data: bool,
) -> Decimal:
    """
    Determine final risk percentage for position sizing.

    If performance context has sufficient data AND AI provided a
    risk recommendation → use AI recommendation (within hard limits).
    Otherwise → use standard confidence-based scaling.

    Hard limits are ALWAYS enforced regardless of AI recommendation.
    """
    HARD_MIN = Decimal("0.0025")   # 0.25% absolute minimum
    HARD_MAX = Decimal("0.02")     # 2.00% absolute maximum

    # Standard confidence-based sizing (always available)
    if proposal.confidence_adjusted >= Decimal("0.90"):
        standard_risk = Decimal("0.02")
    elif proposal.confidence_adjusted >= Decimal("0.80"):
        standard_risk = Decimal("0.01")
    else:
        standard_risk = Decimal("0.005")

    # If AI provided a recommendation AND we have enough data to trust it
    if (has_sufficient_performance_data
            and hasattr(proposal, 'recommended_risk_pct')
            and proposal.recommended_risk_pct):

        ai_recommendation = Decimal(str(proposal.recommended_risk_pct))

        # Enforce hard limits — AI cannot exceed these no matter what
        final_risk = max(HARD_MIN, min(HARD_MAX, ai_recommendation))

        logger.info("adaptive_position_sizing_used",
                   ai_recommended=str(ai_recommendation),
                   final_applied=str(final_risk),
                   standard_would_have_been=str(standard_risk))

        return final_risk

    # Fall back to standard confidence-based sizing
    return standard_risk
```

---

## ADDITION SET 3: CLAUDE CODE PROMPT ADDENDUM
### Add this text to the master Claude Code prompt

Add the following at the END of the master build prompt,
after the "WHAT SUCCESS LOOKS LIKE" section:

---

```
## ADDITION: SELF-IMPROVEMENT FOUNDATION

Build these four items during Phase 3 (AI Brain), after completing prompt_builder.py:

1. Create database/migrations/004_performance_insights.sql
   — performance_insights table with all fields as specified
   — index on (account_id, scope, applied)
   — index on (account_id, insight_type, generated_at DESC)

2. Add _get_performance_insights() to PromptBuilder class
   — queries performance_insights table for this pair
   — returns "no insights yet" string when table is empty
   — returns formatted findings when data exists
   — never raises exceptions (catch all, return safe default)
   — add "=== PERFORMANCE INSIGHTS ===" section to build_prompt()
     between RECENT TRADES and YOUR TASK sections

3. Add _trigger_insight_analysis() to ExecutionEngine
   — called at end of every _close_trade() method
   — silent no-op when trade_count < 50
   — triggers PerformanceAnalyzer.analyze() every 10 trades after that
   — add PerformanceAnalyzer instance to ExecutionEngine.__init__()

4. Create backend/lumitrade/analytics/performance_analyzer.py
   — PerformanceAnalyzer class with analyze() entry point
   — all Phase 2 and Phase 3 methods present as stub functions
   — every stub has a detailed TODO comment explaining what to implement
   — analyze() method calls nothing in Phase 0 (all calls commented out)
   — create backend/lumitrade/analytics/__init__.py (empty)

These four items cost 70 lines total in Phase 0.
They do nothing until trade 50. They unlock self-improvement in Phase 2
without touching any other module.

## ADDITION: ADAPTIVE POSITION SIZING FOUNDATION

Build these items during Phase 4 (Risk Engine), after position_sizer.py:

1. Add PerformanceContext dataclass to core/models.py
   — all fields as specified (win_rate, avg_pips, streaks, volatility, etc.)
   — frozen=True, all Decimal fields use Decimal type
   — add performance_context: PerformanceContext field to MarketSnapshot

2. Create backend/lumitrade/analytics/performance_context_builder.py
   — PerformanceContextBuilder class with build() entry point
   — build() catches all exceptions and returns _empty_context() on any error
   — _empty_context() returns safe defaults (is_sufficient_data=False)
   — only computes real context when 20+ closed trades exist
   — call build() inside DataEngine when assembling MarketSnapshot

3. Update SYSTEM_PROMPT in ai_brain/prompt_builder.py
   — add recommended_risk_pct (0.0025 to 0.02) to required JSON schema
   — add risk_reasoning (string) to required JSON schema
   — add _format_performance_context() method to PromptBuilder
   — add "=== PERFORMANCE CONTEXT ===" section to build_prompt()
     between ACCOUNT CONTEXT and RECENT TRADES sections

4. Update ai_brain/validator.py
   — recommended_risk_pct and risk_reasoning are optional fields
   — if missing: use defaults (0.01 and empty string)
   — if present but out of bounds: clamp to valid range, log warning
   — never reject a signal because these fields are missing or invalid

5. Update risk_engine/engine.py
   — replace _confidence_to_risk_pct() with _determine_risk_pct()
   — uses AI recommendation when performance context is sufficient
   — falls back to confidence-based sizing when data is insufficient
   — ALWAYS enforces hard limits: min 0.25%, max 2.0%
   — logs which path was taken (adaptive vs standard)

IMPORTANT CONSTRAINT: These additions must never cause a signal to be
rejected or a trade to fail. They are enhancements to sizing only.
If any part of adaptive sizing fails for any reason, fall back to
standard confidence-based sizing silently.
```

---

## SUMMARY OF ALL ADDITIONS

| Addition | File(s) Changed | Phase | Lines Added | Impact on Phase 0 |
|---|---|---|---|---|
| performance_insights table | 004_performance_insights.sql | Phase 3 | 25 SQL | Zero — empty table |
| Prompt insights slot | prompt_builder.py | Phase 3 | 20 Python | Returns empty string |
| Post-trade hook | execution_engine.py | Phase 3 | 15 Python | Silent no-op |
| PerformanceAnalyzer stub | analytics/performance_analyzer.py | Phase 3 | 80 Python | Does nothing |
| PerformanceContext dataclass | core/models.py | Phase 4 | 15 Python | Empty defaults |
| PerformanceContextBuilder | analytics/performance_context_builder.py | Phase 4 | 70 Python | Returns empty context |
| Adaptive sizing prompt section | prompt_builder.py | Phase 4 | 20 Python | Shows no data message |
| Validator optional fields | ai_brain/validator.py | Phase 4 | 15 Python | Adds safe defaults |
| Adaptive risk_pct logic | risk_engine/engine.py | Phase 4 | 25 Python | Falls back to standard |

Total: approximately 285 lines across 7 files.
Zero behavioral change in Phase 0.
Unlocks self-improvement and adaptive sizing automatically as data accumulates.

---

# ADDITION SET B: FUTURE FEATURE FOUNDATIONS (15 FEATURES)
## These foundations are built during Phase 0 so features activate later with no restructuring

## ADDITION: FUTURE FEATURE FOUNDATIONS
### Build these during their designated phases — foundations in Phase 0

The following 15 features are NOT built in Phase 0.
However, their foundations — stubs, DB tables, interfaces, enum values, and prompt slots —
ARE built during Phase 0 so activating them later requires only implementing logic.

---

### PHASE 0 FOUNDATIONS (Build NOW alongside the main phases)

**During Phase 1 (Project Foundation):**
1. Add to core/enums.py: MarketRegime, CurrencySentiment, AssetClass, StrategyStatus enums
2. Add to core/models.py: market_regime and sentiment fields to MarketSnapshot (safe defaults)
3. Create infrastructure/broker_interface.py: BrokerInterface abstract base class
4. OandaClient must inherit from BrokerInterface
5. Run migration: database/migrations/005_future_feature_tables.sql (all 12 future tables)
6. Add to .env.example: all optional future feature env vars (commented out)
7. Add features property to LumitradeConfig (derives flags from env var presence)

**During Phase 2 (Data Engine):**
8. Create data_engine/regime_classifier.py: RegimeClassifier stub (returns UNKNOWN always)
9. AssembleMarketSnapshot to include regime_classifier.classify() result

**During Phase 3 (AI Brain):**
10. Create ai_brain/consensus_engine.py: ConsensusEngine stub (passthrough to primary)
11. Create ai_brain/sentiment_analyzer.py: SentimentAnalyzer stub (returns NEUTRAL always)
12. Add PERFORMANCE INSIGHTS slot to prompt (from Additions Prompt)
13. Add sentiment context slot to prompt (empty until F-03 active)

**During Phase 4 (Risk Engine):**
14. Create risk_engine/correlation_matrix.py: CorrelationMatrix stub (returns 1.0 multiplier)
15. Add correlation check to risk engine filter chain (no-op in Phase 0)

**During Phase 5 (Execution Engine):**
16. Post-trade hook already specified in Additions Prompt — add journal + analytics triggers

**During Phase 6 (State & Orchestration):**
17. Add weekly scheduler to main.py (fires Sunday 20:00 EST — calls journal + intelligence stubs)

**Create these analytics stub files:**
18. analytics/journal_generator.py: JournalGenerator stub (returns None always)
19. analytics/coach_service.py: CoachService stub
20. analytics/intelligence_report.py: IntelligenceReportGenerator stub
21. analytics/risk_of_ruin.py: RiskOfRuinCalculator stub (returns insufficient data)
22. analytics/backtest_runner.py: BacktestRunner stub

**Create these new directories and stub files:**
23. marketplace/__init__.py + strategy_registry.py + copy_executor.py (all stubs)
24. api/__init__.py + public_api.py + webhook_dispatcher.py (all stubs)
25. fund/__init__.py + investor_reporting.py (stub)

**During Phase 7 (Dashboard Frontend):**
26. Add ComingSoon.tsx shared component
27. Add stub pages: /journal, /coach, /intelligence, /marketplace, /copy, /backtest, /api-keys
28. Update Sidebar.tsx with full nav list including future pages (with phase badges)
29. Add types/future.ts with all future feature TypeScript interfaces
30. Add RiskOfRuinPanel stub to analytics page (shows insufficient data message)
31. Add market regime badge to SystemStatusPanel (shows — until RegimeClassifier active)

**QTS additions:**
32. Add future marker to pytest.ini
33. Create tests/unit/test_future_stubs.py with Phase 0 stub verification tests
    (These run in Phase 0 CI — verify stubs return safe defaults)
34. Create tests/future/ directory with all @pytest.mark.future test stubs

---

### CONSTRAINT: ALL STUBS MUST BE SILENT NO-OPS

Every stub must:
- Return a safe default value that causes ZERO behavioral change
- Never raise an exception
- Never block or slow down the main trading pipeline
- Log at DEBUG level only (never INFO or higher)
- Be importable and instantiatable without any additional configuration

If a stub fails for any reason, it must catch the exception and return the safe default.
The trading pipeline must never be interrupted by a future feature stub.

---

### HOW TO ACTIVATE A FEATURE LATER

When ready to implement Feature F-XX:
1. Add the required env var(s) to Railway and .env
2. The features flag in config automatically becomes True
3. Replace stub method body with real implementation
4. Remove @pytest.mark.future from the feature's test cases
5. Run the test suite — all feature tests now execute
6. Deploy

No architectural changes. No schema migrations. No restructuring.
The entire activation is: implement the stub + set the env var.

---
---

# ADDITION SET C: SUBAGENT ARCHITECTURE (ALL 5 AGENTS)
## Build these foundations during their designated phases

---

## THE 5 SUBAGENTS

Lumitrade uses 5 specialized AI subagents — separate async Claude calls that run
alongside the main trading pipeline. Each has a Phase 0 stub that is a silent no-op.
None ever block the main trading loop. All exceptions are caught and logged.

```
SA-01  Market Analyst       — Phase 2 | Parallel to each signal scan
SA-02  Post-Trade Analyst   — Phase 2 | Fires on every trade close (async)
SA-03  Risk Monitor         — Phase 2 | Every 30 min while positions open
SA-04  Intelligence Agent   — Phase 2 | Sunday 19:00 EST weekly batch
SA-05  Onboarding Agent     — Phase 3 | New SaaS user signup conversation
```

---

## PHASE 0 FOUNDATIONS (Build alongside main phases)

### During Phase 3 (AI Brain) — add:

**Create directory: backend/lumitrade/subagents/**

Create these files (all stubs, all silent no-ops in Phase 0):

**subagents/__init__.py** — empty

**subagents/base_agent.py** — BaseSubagent abstract class:
- model = "claude-sonnet-4-20250514"
- max_tokens = 1000, timeout_seconds = 30
- _call_claude(system, user) -> str (with asyncio.wait_for timeout)
- All exceptions caught — returns "" on any failure
- Abstract run(context: dict) -> dict method

**subagents/market_analyst.py** — SA-01 MarketAnalystAgent(BaseSubagent):
- run() returns {"briefing": ""} in Phase 0 (empty string — no effect on prompt)
- TODO Phase 2: call Claude with OHLCV + indicators, return structured briefing

**subagents/post_trade_analyst.py** — SA-02 PostTradeAnalystAgent(BaseSubagent):
- run() returns {} in Phase 0
- MIN_TRADES = 20 (check before firing)
- TODO Phase 2: analyze closed trade, store finding to performance_insights

**subagents/risk_monitor.py** — SA-03 RiskMonitorAgent(BaseSubagent):
- run() returns {} in Phase 0
- CRITICAL CONSTRAINT: NEVER auto-closes positions — only logs + alerts
- TODO Phase 2: check thesis validity for each open trade every 30 min

**subagents/intelligence_subagent.py** — SA-04 IntelligenceSubagent(BaseSubagent):
- run() returns {} when NEWS_API_KEY absent (Phase 0 safe default)
- TODO Phase 2: 3 sequential Claude calls (news analyst, perf analyst, writer)

**subagents/onboarding_agent.py** — SA-05 OnboardingAgent(BaseSubagent):
- run() returns {"response": "", "completed": False} in Phase 0
- TODO Phase 3: conversational setup for new SaaS users

**subagents/subagent_orchestrator.py** — SubagentOrchestrator:
- Instantiates all 5 agents
- Exposes: get_analyst_briefing(), run_post_trade(), run_risk_monitor(),
           run_weekly_intelligence(), run_onboarding()
- All methods delegate to stubs in Phase 0

### During Phase 5 (Execution Engine) — add:

Wire SA-02 into ExecutionEngine._close_trade():
```python
# At end of _close_trade():
asyncio.create_task(
    self.subagents.run_post_trade(trade, signal),
    name=f"post_trade_{trade.id}"
)
```

Wire SA-01 into SignalScanner.scan():
```python
# Before building AI prompt:
briefing = await self.subagents.get_analyst_briefing(snapshot)
# Pass briefing to prompt_builder — empty string in Phase 0 = no change
```

### During Phase 6 (State & Orchestration) — add:

Add SubagentOrchestrator to main.py OrchestratorService.__init__():
```python
self.subagents = SubagentOrchestrator(config, db, alert_service)
```

Add SA-03 scheduler loop (runs every 30 min while positions open):
```python
asyncio.create_task(self._risk_monitor_loop(), name="risk_monitor")
```

Add SA-04 weekly scheduler (Sunday 19:00 EST):
```python
asyncio.create_task(self._weekly_intelligence_loop(), name="intelligence")
```

### Database migrations — add during Phase 1:

Create: database/migrations/006_subagent_tables.sql
Three new tables:
- analyst_briefings (signal_id, pair, briefing, model_used, tokens_used, latency_ms)
- risk_monitor_log (trade_id, thesis_valid, reasoning, recommendation, urgency, action_taken)
- onboarding_sessions (account_id, messages JSONB, completed, settings_applied)

### Frontend stubs — add during Phase 7:

Add to Sidebar NAV_ITEMS:
- { href: "/onboarding", label: "Onboarding", phase: 3 } (ComingSoon)

Update SignalDetailPanel.tsx — add analyst briefing section:
```tsx
{signal.analyst_briefing && (
  <Section title="Market Analysis">
    <p className="text-secondary">{signal.analyst_briefing}</p>
  </Section>
)}
```
(Hidden when analyst_briefing is empty — Phase 0 safe)

Update OpenPositionsTable.tsx — add Thesis column:
- thesis_valid=true  → green dot "Valid"
- thesis_valid=false → amber dot "Review" (click to see reasoning)
- not checked yet    → gray "—"

### QTS — add during Phase 8:

Create: tests/unit/test_subagent_stubs.py (NO future marker — runs now)
- test_market_analyst_returns_empty_string_in_phase_0
- test_post_trade_analyst_returns_empty_dict_in_phase_0
- test_risk_monitor_returns_empty_dict_in_phase_0
- test_intelligence_returns_empty_when_no_api_key
- test_onboarding_returns_empty_response_in_phase_0
- test_all_agents_inherit_from_base_subagent
- test_base_agent_timeout_configured

Create: tests/future/test_subagents.py (all @pytest.mark.future)
- SA-01: briefing generated, stored, appears in prompt, handles timeout
- SA-02: skips below MIN_TRADES, stores to performance_insights, handles bad JSON
- SA-03: skips with no trades, stores log, sends alert on invalid thesis,
         NEVER auto-closes positions (most critical test)
- SA-04: skips without API key, makes 3 Claude calls, stores report, sends email
- SA-05: loads history, applies settings on JSON detection, rate limits at 20 msgs

---

## AGENT INTERACTION DIAGRAM

```
Every 15 min signal scan:
[DataEngine] -> SA-01 Market Analyst (async, ~2s) -> briefing
                                                         |
                                              [AIBrain Signal Decision]
                                              receives: briefing + indicators
                                              produces: BUY/SELL/HOLD signal
                                                         |
                                              [RiskEngine validates]
                                                         |
                                              [ExecutionEngine places order]
                                                         |
                                         SA-02 Post-Trade Analyst (on close, async)
                                         stores: performance_insights finding

Every 30 min (while positions open):
SA-03 Risk Monitor -> checks thesis for each position
                   -> logs to risk_monitor_log
                   -> sends alert if thesis invalidated
                   -> NEVER auto-closes anything

Every Sunday 19:00 EST:
SA-04 Intelligence -> News Analyst Claude call
                   -> Perf Analyst Claude call
                   -> Writer Claude call
                   -> stores intelligence_reports
                   -> sends email to operator

New SaaS user signup (Phase 3):
SA-05 Onboarding -> conversational setup
                 -> auto-applies recommended settings
                 -> marks onboarding complete
```

---

## CRITICAL SA-03 CONSTRAINT

The Risk Monitor subagent must NEVER automatically close, modify, or affect
any trading position. Its ONLY outputs are:
1. A log entry in risk_monitor_log
2. A dashboard notification (thesis badge on position row)
3. An SMS alert if urgency=HIGH

All trade actions remain operator decisions. This constraint is hardcoded.
The test test_risk_monitor_never_closes_trades_automatically must always pass.

---

## ACTIVATION

To activate any subagent in Phase 2/3:
1. Remove @pytest.mark.future from its test file
2. Implement the TODO block in the stub's run() method
3. For SA-04: add NEWS_API_KEY to Railway env vars
4. For SA-03: set RISK_MONITOR_ENABLED=true in Railway env vars
5. Deploy — orchestrator auto-wires everything

