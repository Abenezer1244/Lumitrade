# Phase 1: Project Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the complete Lumitrade repository structure, core domain models, infrastructure clients, utilities, database migrations, and security files — the foundation everything else builds on.

**Architecture:** Monorepo with `backend/` (Python 3.11 async) and `frontend/` (Next.js 14). Core domain models as frozen dataclasses. Pydantic Settings for config. Supabase async client for DB. structlog for JSON logging with scrubbing.

**Tech Stack:** Python 3.11, pydantic-settings, supabase-py (AsyncClient), structlog, httpx, Decimal arithmetic, pytest

**Key research findings:**
- Supabase Python has async support: `create_async_client` / `AsyncClient` with `await` on all operations
- pydantic-settings uses `validation_alias` for env var mapping (not just `alias`)
- structlog: use `structlog.stdlib.filter_by_level` + `JSONRenderer` for structured output
- Telnyx SMS via raw httpx POST (no SDK needed)

---

## Task 1: Create Repository Directory Structure

**Files:**
- Create: Full directory tree per SAS Section 4

- [ ] **Step 1: Create backend directory structure**

```bash
cd "C:/Users/Windows/OneDrive - Seattle Colleges/Desktop/Lumitrade"
mkdir -p backend/lumitrade/{core,data_engine,ai_brain,risk_engine,execution_engine,state,infrastructure,utils,analytics,subagents,marketplace,api,fund}
mkdir -p backend/tests/{unit,integration,chaos,security,e2e,future,performance}
mkdir -p backend/scripts
mkdir -p database/{migrations,seed}
mkdir -p .github/workflows
```

- [ ] **Step 2: Create frontend directory structure**

```bash
mkdir -p frontend/src/{app/{dashboard,signals,trades,analytics,settings,auth/{login,callback},api/{account,positions,signals,trades,analytics,system/{health,alerts},control/kill-switch,settings},journal,coach,intelligence,marketplace,copy,backtest,api-keys,onboarding},components/{layout,dashboard,signals,trades,analytics,settings,ui},hooks,lib,types}
```

- [ ] **Step 3: Create all __init__.py files**

```bash
find backend/lumitrade -type d -exec touch {}/__init__.py \;
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: create complete repository directory structure per SAS Section 4"
```

---

## Task 2: Core Enums (core/enums.py)

**Files:**
- Create: `backend/lumitrade/core/enums.py`

- [ ] **Step 1: Implement all enums from BDS Section 2.1**

All 12 original enums + 4 future enums from SAS v2.0 Section 14.4:
- Action, Direction, RiskState, Session, TradingMode, ExitReason, OrderStatus, Outcome, TradeDuration, GenerationMethod, NewsImpact, CircuitBreakerState
- MarketRegime, CurrencySentiment, AssetClass, StrategyStatus

Every enum inherits from `(str, Enum)` for JSON serialization.

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/core/enums.py
git commit -m "feat: add all 16 enums per BDS Section 2.1 and SAS v2.0 Section 14.4"
```

---

## Task 3: Core Models (core/models.py)

**Files:**
- Create: `backend/lumitrade/core/models.py`

- [ ] **Step 1: Implement all dataclasses from BDS Section 2.2**

All 14 original dataclasses + PerformanceContext from Addition Set 2:
- Candle, PriceTick, IndicatorSet, NewsEvent, DataQuality, AccountContext, TradeSummary, MarketSnapshot
- SignalProposal, ApprovedOrder, OrderResult, RiskRejection
- PerformanceContext (Addition Set 2A)

All use `@dataclass(frozen=True)`. All financial values use `Decimal`. MarketSnapshot includes `market_regime`, `sentiment`, `ai_models`, `performance_context` fields with safe defaults.

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/core/models.py
git commit -m "feat: add all 15 frozen dataclasses per BDS Section 2.2"
```

---

## Task 4: Custom Exceptions (core/exceptions.py)

**Files:**
- Create: `backend/lumitrade/core/exceptions.py`

- [ ] **Step 1: Implement exception hierarchy**

```python
class LumitradeError(Exception):
    """Base exception for all Lumitrade errors."""

class DataValidationError(LumitradeError):
    """Raised when market data fails validation."""

class AIValidationError(LumitradeError):
    """Raised when AI output fails validation."""

class RiskRejectionError(LumitradeError):
    """Raised when a signal is rejected by risk engine."""

class ExecutionError(LumitradeError):
    """Raised when order execution fails."""

class CircuitBreakerOpenError(LumitradeError):
    """Raised when circuit breaker is OPEN."""

class OrderExpiredError(ExecutionError):
    """Raised when an ApprovedOrder has expired."""

class ReconciliationError(LumitradeError):
    """Raised when position reconciliation finds discrepancies."""

class LockAcquisitionError(LumitradeError):
    """Raised when distributed lock cannot be acquired."""
```

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/core/exceptions.py
git commit -m "feat: add custom exception hierarchy per SAS spec"
```

---

## Task 5: Configuration System (config.py)

**Files:**
- Create: `backend/lumitrade/config.py`

- [ ] **Step 1: Implement LumitradeConfig from BDS Section 3.1**

Pydantic BaseSettings with all env vars. Use `validation_alias` for env var mapping. Include:
- OANDA keys (data + trading), account ID, environment
- Anthropic API key, model config
- Supabase URL + service key
- Telnyx API key + from number (NOT Twilio)
- Alert SMS/email recipients
- Instance ID, trading mode, log level, Sentry DSN
- Trading parameters with Decimal defaults
- `oanda_base_url` and `oanda_stream_url` properties
- `features` property for feature flags (derived from env var presence)
- Future feature optional env vars (openai, news_api, stripe, etc.)

Use `model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)`

Do NOT instantiate a singleton at module level — let each component create its own instance or receive it via dependency injection.

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/config.py
git commit -m "feat: add Pydantic Settings config with all env vars per BDS Section 3"
```

---

## Task 6: Secure Logger (infrastructure/secure_logger.py)

**Files:**
- Create: `backend/lumitrade/infrastructure/secure_logger.py`
- Test: `backend/tests/unit/test_secure_logger.py`

- [ ] **Step 1: Write failing tests for secure logger**

6 tests from SS Section 7.2:
- test_scrubs_bearer_token
- test_scrubs_anthropic_key
- test_scrubs_api_key_pattern
- test_preserves_normal_text
- test_scrubs_email
- test_scrubs_phone_number

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd backend && python -m pytest tests/unit/test_secure_logger.py -v
```

- [ ] **Step 3: Implement secure_logger.py from SS Section 7.1**

8 compiled regex scrub patterns. `_scrub_processor` for structlog that recursively scrubs all string values. `configure_logging()` and `get_logger()` functions.

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd backend && python -m pytest tests/unit/test_secure_logger.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/lumitrade/infrastructure/secure_logger.py backend/tests/unit/test_secure_logger.py
git commit -m "feat: add SecureLogger with 8 scrub patterns and tests per SS Section 7"
```

---

## Task 7: Database Client (infrastructure/db.py)

**Files:**
- Create: `backend/lumitrade/infrastructure/db.py`

- [ ] **Step 1: Implement DatabaseClient from SS Section 4.1**

Uses `create_async_client` / `AsyncClient` from supabase-py. All methods async with `await`. Methods: `connect()`, `insert()`, `select()`, `select_one()`, `update()`, `upsert()`, `count()`. All parameterized — never raw SQL.

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/infrastructure/db.py
git commit -m "feat: add async DatabaseClient with parameterized queries per SS Section 4"
```

---

## Task 8: Broker Interface (infrastructure/broker_interface.py)

**Files:**
- Create: `backend/lumitrade/infrastructure/broker_interface.py`

- [ ] **Step 1: Implement BrokerInterface ABC from SAS v2.0 Section 14.6**

Abstract base class with methods: `get_candles()`, `get_account_summary()`, `get_open_trades()`, `place_market_order()`, `close_trade()`, `stream_prices()`. OandaClient will implement this.

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/infrastructure/broker_interface.py
git commit -m "feat: add BrokerInterface ABC for multi-broker support per SAS v2.0"
```

---

## Task 9: OANDA Client (infrastructure/oanda_client.py)

**Files:**
- Create: `backend/lumitrade/infrastructure/oanda_client.py`

- [ ] **Step 1: Implement OandaClient and OandaTradingClient from BDS Section 4.1**

OandaClient (read-only, DATA key): `get_candles()`, `get_pricing()`, `get_account_summary()`, `get_open_trades()`, `stream_prices()`, `close()`. Inherits from BrokerInterface.

OandaTradingClient (TRADING key, ExecutionEngine ONLY): extends OandaClient with `place_market_order()`, `close_trade()`, `modify_trade()`.

Both use `httpx.AsyncClient` with `verify=True` (TLS enforced). Uses `_create_secure_client()` from SS Section 5.1 with SSL context.

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/infrastructure/oanda_client.py
git commit -m "feat: add OANDA clients (read-only + trading) per BDS Section 4.1"
```

---

## Task 10: Alert Service (infrastructure/alert_service.py)

**Files:**
- Create: `backend/lumitrade/infrastructure/alert_service.py`

- [ ] **Step 1: Implement AlertService from Master Prompt Pattern 6**

Telnyx SMS via raw httpx (NOT Twilio). SendGrid for email. 4 severity levels: `send_info()`, `send_warning()`, `send_error()`, `send_critical()`. All sends logged to `alerts_log` table.

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/infrastructure/alert_service.py
git commit -m "feat: add AlertService with Telnyx SMS + SendGrid email per Master Prompt"
```

---

## Task 11: Pip Math Utilities (utils/pip_math.py)

**Files:**
- Create: `backend/lumitrade/utils/pip_math.py`
- Test: `backend/tests/unit/test_pip_math.py`

- [ ] **Step 1: Write failing tests — all 15 from QTS Table 6**

PM-001 through PM-015. All use `Decimal` arithmetic. Manually verified expected values.

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd backend && python -m pytest tests/unit/test_pip_math.py -v
```

- [ ] **Step 3: Implement pip_math.py from BDS Section 10.1**

`pip_size()`, `pips_between()`, `pip_value_per_unit()`, `calculate_position_size()`. All Decimal. Floor to micro lot (1000 units).

- [ ] **Step 4: Run tests — confirm all 15 pass**

```bash
cd backend && python -m pytest tests/unit/test_pip_math.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/lumitrade/utils/pip_math.py backend/tests/unit/test_pip_math.py
git commit -m "feat: add pip math utilities with 15 tests per BDS Section 10.1 and QTS"
```

---

## Task 12: Time Utilities (utils/time_utils.py)

**Files:**
- Create: `backend/lumitrade/utils/time_utils.py`

- [ ] **Step 1: Implement from BDS Section 10.2**

`get_current_session()` — returns Session enum based on UTC time. `is_market_open()` — checks weekday/time for forex market hours.

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/utils/time_utils.py
git commit -m "feat: add time utilities (session detection, market hours) per BDS Section 10.2"
```

---

## Task 13: Database Migrations (001-006)

**Files:**
- Create: `database/migrations/001_initial_schema.sql`
- Create: `database/migrations/002_add_indexes.sql`
- Create: `database/migrations/003_add_rls_policies.sql`
- Create: `database/migrations/004_performance_insights.sql`
- Create: `database/migrations/005_future_feature_tables.sql`
- Create: `database/migrations/006_subagent_tables.sql`

- [ ] **Step 1: Create all 6 migration files from BDS Section 9**

001: accounts, signals, trades, risk_events, system_state, performance_snapshots, execution_log, alerts_log, system_events
002: All performance indexes
003: RLS policies on all tables
004: performance_insights table (Addition Set 1A)
005: 12 future feature tables (BDS Section 13.7)
006: 3 subagent tables (BDS Section 16.7)

- [ ] **Step 2: Commit**

```bash
git add database/migrations/
git commit -m "feat: add all 6 database migrations per BDS Section 9"
```

---

## Task 14: Security Files (.gitignore, .env.example, .pre-commit-config.yaml)

**Files:**
- Create: `.gitignore` from SS Section 3.2
- Create: `.env.example` from SS Section 3.3 + Telnyx vars
- Create: `.pre-commit-config.yaml` from SS Section 3.1

- [ ] **Step 1: Create .gitignore**

All security-critical entries: .env*, *.pem, *.key, secrets/, credentials/, logs/, __pycache__/, node_modules/, .next/, .DS_Store

- [ ] **Step 2: Create .env.example**

All 17+ variables with placeholder values. Telnyx (not Twilio). Future feature vars commented out.

- [ ] **Step 3: Create .pre-commit-config.yaml**

gitleaks v8.18.2, detect-private-key, bandit for Python.

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.example .pre-commit-config.yaml
git commit -m "feat: add security files (.gitignore, .env.example, pre-commit hooks) per SS Section 3"
```

---

## Task 15: Python Project Files

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/requirements.txt`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml with project metadata and pytest config**

Include pytest markers (unit, integration, chaos, e2e, performance, security, critical, future, live). asyncio_mode = auto. Coverage config.

- [ ] **Step 2: Create requirements.txt from BDS Section 1.2**

All pinned versions. Remove twilio. Keep all others. Note: hashes omitted for now — add via pip-compile before production.

- [ ] **Step 3: Create tests/conftest.py**

Shared fixtures: mock_config, mock_db, mock_alerts. Fake env vars for test isolation.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/requirements.txt backend/tests/conftest.py
git commit -m "feat: add Python project config, requirements, and test fixtures"
```

---

## Task 16: Verify Phase 1 — Run All Tests

- [ ] **Step 1: Install dependencies**

```bash
cd backend && pip install -r requirements.txt
```

- [ ] **Step 2: Run all Phase 1 tests**

```bash
cd backend && python -m pytest tests/unit/test_pip_math.py tests/unit/test_secure_logger.py -v
```

Expected: All tests green (15 pip_math + 6 secure_logger = 21 tests).

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "milestone: Phase 1 Foundation complete — all tests passing"
```

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 1 | Directory structure | ~50 dirs | - |
| 2 | Core enums | 1 file | - |
| 3 | Core models | 1 file | - |
| 4 | Custom exceptions | 1 file | - |
| 5 | Config system | 1 file | - |
| 6 | Secure logger | 1 file | 6 tests |
| 7 | Database client | 1 file | - |
| 8 | Broker interface | 1 file | - |
| 9 | OANDA client | 1 file | - |
| 10 | Alert service | 1 file | - |
| 11 | Pip math | 1 file | 15 tests |
| 12 | Time utils | 1 file | - |
| 13 | DB migrations | 6 files | - |
| 14 | Security files | 3 files | - |
| 15 | Project files | 3 files | - |
| 16 | Verify all | - | 21 tests |
