



LUMITRADE
System Architecture Specification

ROLE 2 — SENIOR SYSTEM ARCHITECT
Version 1.0  |  Phase 0: Forex MVP  |  Claude Code Ready
Classification: Confidential
Date: March 20, 2026




# 1. Architecture Philosophy & Design Principles
Lumitrade's architecture is built on five non-negotiable principles that govern every design decision from file structure to database schema to inter-component communication:


# 2. High-Level System Architecture
## 2.1 System Overview
Lumitrade is composed of six core layers, each with strict input/output contracts. Data flows in one direction through the trading pipeline. Control signals (kill switch, configuration changes) flow from the dashboard into the system state.

Architecture Pattern  Async event-driven pipeline with layered service architecture. Each layer communicates only with its immediate neighbors via typed dataclass contracts. No layer bypasses another.


## 2.2 Data Flow Architecture
The primary trading pipeline processes data in strict linear sequence. Each stage either passes its output to the next stage or terminates the cycle with a logged reason:


## 2.3 Control Flow Architecture
Separate from the trading pipeline, a control flow layer allows the operator to interact with the running system:


# 3. Component Architecture
## 3.1 Component Dependency Map
Each component's dependencies are strictly controlled. No circular dependencies are permitted. The dependency direction is always: lower layer components do not import from higher layer components.


## 3.2 Core Component Specifications
### 3.2.1 OrchestratorService
The top-level coordinator that owns the main async event loop. It instantiates all components, wires their dependencies, starts all async tasks, and owns the graceful shutdown procedure.

### 3.2.2 DataEngine

### 3.2.3 SignalScanner

### 3.2.4 RiskEngine

### 3.2.5 ExecutionEngine

### 3.2.6 StateManager

### 3.2.7 DashboardAPI

# 4. Project File & Folder Structure
## 4.1 Repository Layout
Monorepo Structure  Single GitHub repository containing both backend (Python) and frontend (Next.js). Shared by Claude Code workspace. Each top-level directory is an independent deployable unit.

lumitrade/
├── backend/                    # Python trading engine
│   ├── lumitrade/              # Main package
│   │   ├── __init__.py
│   │   ├── main.py             # Entry point — OrchestratorService
│   │   ├── config.py           # Config loader — env vars + DB
│   │   ├── core/               # Core domain models and contracts
│   │   │   ├── __init__.py
│   │   │   ├── models.py       # All dataclasses: MarketSnapshot, SignalProposal, ApprovedOrder...
│   │   │   ├── enums.py        # All enums: Action, Direction, RiskState, Session, ExitReason...
│   │   │   └── exceptions.py   # Custom exception hierarchy
│   │   ├── data_engine/        # L2 — Market data layer
│   │   │   ├── __init__.py
│   │   │   ├── engine.py       # DataEngine orchestrator
│   │   │   ├── price_stream.py # OANDA streaming connection
│   │   │   ├── candle_fetcher.py # OANDA REST candle fetcher
│   │   │   ├── indicators.py   # pandas-ta indicator computation
│   │   │   ├── validator.py    # DataValidator — all validation checks
│   │   │   └── calendar.py     # Economic calendar fetcher
│   │   ├── ai_brain/           # L3 — AI signal generation layer
│   │   │   ├── __init__.py
│   │   │   ├── scanner.py      # SignalScanner orchestrator
│   │   │   ├── prompt_builder.py # Assembles MarketSnapshot → prompt
│   │   │   ├── claude_client.py  # Anthropic API wrapper
│   │   │   ├── validator.py    # AI output schema + logic validator
│   │   │   ├── confidence.py   # Confidence adjustment pipeline
│   │   │   └── fallback.py     # Rule-based signal fallback
│   │   ├── risk_engine/        # L4 — Risk management layer
│   │   │   ├── __init__.py
│   │   │   ├── engine.py       # RiskEngine — main validation pipeline
│   │   │   ├── state_machine.py # RiskState transitions
│   │   │   ├── position_sizer.py # Position size calculation
│   │   │   ├── filters.py      # Individual risk filter functions
│   │   │   └── calendar_guard.py # News blackout enforcement
│   │   ├── execution_engine/   # L5 — Order execution layer
│   │   │   ├── __init__.py
│   │   │   ├── engine.py       # ExecutionEngine orchestrator
│   │   │   ├── order_machine.py # Order state machine
│   │   │   ├── oanda_executor.py # OANDA API order placement
│   │   │   ├── paper_executor.py # Paper trading simulator
│   │   │   ├── fill_verifier.py  # Post-fill verification
│   │   │   └── circuit_breaker.py # Circuit breaker implementation
│   │   ├── state/              # System state management
│   │   │   ├── __init__.py
│   │   │   ├── manager.py      # StateManager — persist & restore
│   │   │   ├── reconciler.py   # OANDA ↔ DB reconciliation
│   │   │   └── lock.py         # Distributed primary lock
│   │   ├── infrastructure/     # Shared infrastructure clients
│   │   │   ├── __init__.py
│   │   │   ├── db.py           # Supabase client wrapper
│   │   │   ├── oanda_client.py # OANDA REST + Streaming client
│   │   │   ├── anthropic_client.py # Claude API client
│   │   │   ├── alert_service.py    # SMS + email dispatcher
│   │   │   ├── secure_logger.py    # Structured JSON logger + scrubber
│   │   │   └── watchdog.py         # Process health monitor
│   │   └── utils/              # Pure utility functions
│   │       ├── __init__.py
│   │       ├── pip_math.py     # Forex pip calculations
│   │       ├── time_utils.py   # Session detection, market hours
│   │       └── crypto.py       # Hashing utilities (prompt audit)
│   ├── tests/                  # Test suite
│   │   ├── unit/               # Unit tests per module
│   │   ├── integration/        # Integration tests
│   │   └── chaos/              # Chaos / failure scenario tests
│   ├── scripts/                # Operational scripts
│   │   ├── backtest.py         # Backtesting runner
│   │   └── db_migrate.py       # Database migration runner
│   ├── supervisord.conf        # Process supervisor config
│   ├── requirements.txt        # Pinned dependencies with hashes
│   ├── pyproject.toml          # Project metadata
│   └── Dockerfile              # Container definition
│
├── frontend/                   # Next.js dashboard
│   ├── src/
│   │   ├── app/                # Next.js App Router
│   │   │   ├── layout.tsx      # Root layout
│   │   │   ├── page.tsx        # Dashboard home
│   │   │   ├── signals/        # Signal feed page
│   │   │   ├── trades/         # Trade history page
│   │   │   ├── analytics/      # Performance analytics page
│   │   │   ├── settings/       # Settings page
│   │   │   └── api/            # Next.js API routes
│   │   ├── components/         # React components
│   │   │   ├── dashboard/      # Dashboard-specific components
│   │   │   ├── signals/        # Signal card + detail panel
│   │   │   ├── trades/         # Trade history table
│   │   │   ├── charts/         # Equity curve, analytics charts
│   │   │   └── ui/             # Shared UI primitives
│   │   ├── lib/                # Client libraries
│   │   │   ├── supabase.ts     # Supabase client
│   │   │   └── api.ts          # API client functions
│   │   └── types/              # TypeScript type definitions
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.ts
│
├── database/                   # Database management
│   ├── migrations/             # SQL migration files (numbered)
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_add_indexes.sql
│   │   └── 003_add_rls_policies.sql
│   └── seed/                   # Test data seeds
│
├── .github/                    # CI/CD workflows
│   └── workflows/
│       ├── test.yml            # Run test suite on every PR
│       └── deploy.yml          # Deploy to Railway on main merge
│
├── .env.example                # Template — lists all required env vars
├── .gitignore                  # Includes: .env, __pycache__, .DS_Store
├── docker-compose.yml          # Local development environment
└── README.md                   # Setup and development guide

# 5. Inter-Component Data Contracts
All data passed between components is typed using Python dataclasses. These are the single source of truth for component interfaces. No component may access data from another component except through these contracts.

## 5.1 Core Dataclass Definitions
### MarketSnapshot — DataEngine → SignalScanner
@dataclass
class MarketSnapshot:
pair: str                         # e.g. "EUR_USD"
session: Session                  # Enum: LONDON, NEW_YORK, OVERLAP, TOKYO, OTHER
timestamp: datetime
bid: Decimal
ask: Decimal
spread_pips: Decimal
candles_m15: List[Candle]         # Last 50 confirmed M15 candles
candles_h1: List[Candle]          # Last 50 confirmed H1 candles
candles_h4: List[Candle]          # Last 50 confirmed H4 candles
indicators: IndicatorSet          # All computed indicator values
news_events: List[NewsEvent]      # Events in next 4 hours
recent_trades: List[TradeSummary] # Last 3 trades on this pair
account_context: AccountContext   # Balance, equity, open count
data_quality: DataQuality         # Validation scores and flags

### SignalProposal — AIBrain → RiskEngine
@dataclass
class SignalProposal:
signal_id: UUID
pair: str
action: Action                    # Enum: BUY, SELL, HOLD
confidence_raw: Decimal           # Direct from Claude
confidence_adjusted: Decimal      # After adjustment pipeline
confidence_adjustment_log: dict   # Factor-by-factor breakdown
entry_price: Decimal
stop_loss: Decimal
take_profit: Decimal
summary: str                      # Plain English — 2-4 sentences
reasoning: str                    # Full technical analysis
timeframe_scores: dict            # {h4: 0.82, h1: 0.75, m15: 0.71}
indicators_snapshot: dict         # All indicator values at signal time
key_levels: List[Decimal]
invalidation_level: Decimal
expected_duration: TradeDuration  # Enum: SCALP, INTRADAY, SWING
generation_method: GenerationMethod # Enum: AI, RULE_BASED
session: Session
spread_pips: Decimal
news_context: List[NewsEvent]
ai_prompt_hash: str               # SHA256 of prompt for audit
created_at: datetime

### ApprovedOrder — RiskEngine → ExecutionEngine
@dataclass
class ApprovedOrder:
order_ref: UUID                   # Internal idempotency key
signal_id: UUID                   # FK to signals table
pair: str
direction: Direction              # Enum: BUY, SELL
units: int                        # Calculated position size
entry_price: Decimal              # Expected entry
stop_loss: Decimal
take_profit: Decimal
risk_amount_usd: Decimal
risk_pct: Decimal
account_balance_at_approval: Decimal
approved_at: datetime
expiry: datetime                  # 30s from approval — reject if stale
mode: TradingMode                 # Enum: PAPER, LIVE

### OrderResult — ExecutionEngine internal
@dataclass
class OrderResult:
order_ref: UUID
broker_order_id: str
broker_trade_id: str
status: OrderStatus               # Enum: FILLED, PARTIAL, REJECTED, TIMEOUT
fill_price: Decimal
fill_units: int
fill_timestamp: datetime
stop_loss_confirmed: Decimal
take_profit_confirmed: Decimal
slippage_pips: Decimal
raw_response: dict                # Full OANDA response for audit

### SystemState — StateManager ↔ All components
@dataclass
class SystemState:
risk_state: RiskState             # Enum: NORMAL, CAUTIOUS, DAILY_LIMIT...
open_trades: List[OpenTrade]      # All currently open positions
pending_orders: List[PendingOrder]
daily_pnl_usd: Decimal
weekly_pnl_usd: Decimal
daily_opening_balance: Decimal
weekly_opening_balance: Decimal
daily_trade_count: int
consecutive_losses: int
circuit_breaker_state: CircuitBreakerState
circuit_breaker_failure_count: int
circuit_breaker_last_failure: Optional[datetime]
last_signal_time: Dict[str, datetime]  # {pair: timestamp}
confidence_threshold_override: Optional[Decimal]
is_primary_instance: bool
updated_at: datetime

# 6. Async Task Architecture
## 6.1 Task Inventory
All tasks are managed by the OrchestratorService. Each task is a long-running coroutine with its own error handling and recovery logic. No task shares mutable state without going through the StateManager.


## 6.2 Queue Architecture
Tasks communicate via asyncio.Queue instances owned by the OrchestratorService. Queues are bounded to prevent unbounded memory growth.


## 6.3 Concurrency Safety Rules
- One active signal scan per pair at any time — enforced by per-pair asyncio.Lock
- One active order submission per pair at any time — enforced by per-pair trade lock
- State reads and writes go through StateManager — never direct DB access from trading components
- DB writes from execution engine are fire-and-forget with error logging — never block order execution on DB write
- All asyncio.Lock acquisitions have a timeout (default 5s) — deadlock prevention
- No asyncio.sleep() calls inside critical execution paths — use task scheduling instead

# 7. Database Architecture
## 7.1 Database Design Decisions

## 7.2 Index Strategy

## 7.3 Row-Level Security Policies
Supabase RLS enforces data isolation. Applied immediately even in Phase 0 to establish the pattern:
-- All tables: users see only their own account data
CREATE POLICY "account_isolation" ON trades
FOR ALL USING (account_id = auth.uid()::uuid);

-- system_state: only the authenticated service role can write
CREATE POLICY "service_write_only" ON system_state
FOR UPDATE USING (auth.role() = 'service_role');

-- execution_log: read-only for authenticated users (no insert from frontend)
CREATE POLICY "read_only_execution_log" ON execution_log
FOR SELECT USING (account_id = auth.uid()::uuid);

# 8. Infrastructure Architecture
## 8.1 Cloud Primary — Railway.app

## 8.2 Local Backup Architecture

## 8.3 Supervisord Configuration
[supervisord]
nodaemon=true
logfile=/var/log/lumitrade/supervisord.log
logfile_maxbytes=50MB
logfile_backups=5

[program:lumitrade-engine]
command=python -m lumitrade.main
directory=/app/backend
autostart=true
autorestart=true
startretries=5
stopwaitsecs=30
stdout_logfile=/var/log/lumitrade/engine.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
redirect_stderr=false
stderr_logfile=/var/log/lumitrade/engine.err

[program:lumitrade-watchdog]
command=python -m lumitrade.infrastructure.watchdog
autostart=true
autorestart=true
startretries=10
stdout_logfile=/var/log/lumitrade/watchdog.log

## 8.4 Environment Variables Reference

# 9. Security Architecture
## 9.1 Network Security

## 9.2 Secret Access Pattern
The execution engine is the only module permitted to use the trading API key. This is enforced architecturally, not just by convention:
# infrastructure/oanda_client.py
class OandaClient:
"""Base client — uses DATA key only. Read operations."""
def __init__(self):
self.api_key = os.environ["OANDA_API_KEY_DATA"]

class OandaTradingClient(OandaClient):
"""Trading client — extends base. Only instantiated by ExecutionEngine."""
def __init__(self):
self.trading_key = os.environ["OANDA_API_KEY_TRADING"]
# Only this class has methods: place_order, modify_trade, close_trade

## 9.3 Log Scrubbing Architecture
# infrastructure/secure_logger.py
SCRUB_PATTERNS = [
(r"Bearer\s+[A-Za-z0-9\-._]+", "Bearer [REDACTED]"),
(r"[A-Za-z0-9]{40,}", "[REDACTED_TOKEN]"),      # Long token-like strings
(r"api[_-]?key[\s:=]+\S+", "api_key=[REDACTED]"),  # Key=value patterns
(r"password[\s:=]+\S+", "password=[REDACTED]"),
]

def scrub(message: str) -> str:
for pattern, replacement in SCRUB_PATTERNS:
message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
return message

# 10. Observability Architecture
## 10.1 Logging Architecture

## 10.2 Health Endpoint Specification
The /health endpoint is the system's single source of truth for operational status. It is called by UptimeRobot, the local backup heartbeat monitor, and Railway deployment health checks.

GET /health
Response 200 OK (all critical components operational):
{
"status": "healthy",
"instance_id": "cloud-primary",
"is_primary": true,
"timestamp": "2026-03-20T14:32:00Z",
"uptime_seconds": 86432,
"components": {
"oanda_api":    { "status": "ok", "latency_ms": 45 },
"ai_brain":     { "status": "ok", "last_call_ago_s": 892 },
"database":     { "status": "ok", "latency_ms": 12 },
"price_feed":   { "status": "ok", "last_tick_ago_s": 2 },
"risk_engine":  { "status": "ok", "state": "NORMAL" },
"circuit_breaker": { "status": "closed" }
},
"trading": {
"mode": "PAPER",
"open_positions": 2,
"daily_pnl_usd": 4.23,
"signals_today": 8
}
}

Response 503 Service Unavailable (any critical component failed):
{ "status": "degraded", "failed_components": ["price_feed"], ... }

## 10.3 Alert Severity Matrix

# 11. Testing Architecture
## 11.1 Test Strategy Overview

## 11.2 Critical Test Cases
### AI Validation Tests
- test_rejects_signal_missing_confidence_field
- test_rejects_buy_signal_with_sl_above_entry
- test_rejects_sell_signal_with_sl_below_entry
- test_rejects_confidence_above_1_0
- test_rejects_entry_price_deviating_more_than_0_5_pct
- test_rejects_risk_reward_below_1_5
- test_accepts_valid_buy_signal
- test_accepts_valid_sell_signal
- test_hold_signal_does_not_reach_risk_engine
- test_fallback_rule_based_signal_on_ai_failure

### Risk Engine Tests
- test_halts_at_daily_loss_limit
- test_halts_at_weekly_loss_limit
- test_blocks_4th_trade_when_max_is_3
- test_blocks_trade_in_news_blackout_window
- test_blocks_trade_with_spread_above_threshold
- test_position_size_correct_for_small_account
- test_position_size_correct_for_large_account
- test_confidence_threshold_raised_after_3_consecutive_losses
- test_pair_cooldown_prevents_duplicate_signal
- test_risk_state_transitions_normal_to_cautious

### Execution Engine Tests
- test_order_state_machine_normal_flow
- test_order_rejected_if_approved_order_expired
- test_fill_verification_detects_high_slippage
- test_partial_fill_adjusts_sl_tp_correctly
- test_circuit_breaker_trips_after_3_failures
- test_circuit_breaker_half_open_allows_test_call
- test_no_duplicate_order_on_timeout_and_retry
- test_paper_mode_does_not_call_oanda_trading_api

### Chaos Tests
- test_crash_during_order_submission_recovers_correctly
- test_crash_with_open_position_reconciles_on_restart
- test_oanda_api_500_response_activates_circuit_breaker
- test_price_feed_disconnect_halts_new_signals
- test_data_spike_rejected_no_trade_placed
- test_local_backup_takeover_when_cloud_lock_expires
- test_dual_instance_prevention_via_distributed_lock

# 12. Deployment & CI/CD Architecture
## 12.1 CI/CD Pipeline

## 12.2 Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install supervisor
RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (pinned with hashes)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY backend/ /app/backend/
COPY supervisord.conf /etc/supervisor/conf.d/lumitrade.conf

# Create log directory
RUN mkdir -p /var/log/lumitrade

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/lumitrade.conf"]

## 12.3 Database Migration Strategy
- All schema changes are versioned SQL files in database/migrations/
- Files are numbered sequentially: 001_initial_schema.sql, 002_add_indexes.sql
- Migrations are run manually via scripts/db_migrate.py before deployment
- All migrations are additive only (no destructive changes) — columns and tables are never deleted, only added
- Supabase dashboard used for emergency hotfixes only — all changes must also be committed to migration files

# 13. Architecture Decision Records (ADRs)
Each major architectural decision is documented with its context, decision, and consequences. These records are permanent and inform future changes.








END OF DOCUMENT
Lumitrade System Architecture Specification v1.0  |  Confidential
Next Document: Backend Developer Specification (Role 3)





LUMITRADE
System Architecture Specification

ROLE 2 — SENIOR SYSTEM ARCHITECT
All original architecture + future feature component map
Version 2.0  |  Includes future feature foundations
Date: March 21, 2026




# 1–13. All Original SAS Sections
Sections 1 through 13 of the original System Architecture Specification are unchanged. All original architecture decisions, component specifications, file structures, data contracts, async task architecture, database design, infrastructure, security, observability, testing, deployment, and ADRs remain exactly as specified in v1.0.
Reference  Original SAS v1.0 is the authoritative source for all Phase 0 architecture. This document adds Section 14 only.

# 14. Future Feature Architecture
## 14.1 New Modules (Stub — Phase 0)
Create these files now. All are importable but do nothing in Phase 0. They have complete class signatures, method stubs with detailed TODO comments, and the correct import structure so wiring them up later requires only implementing the methods.


## 14.2 Extended File Structure
Add these directories to the existing structure from SAS Section 4:

backend/lumitrade/
├── ai_brain/
│   ├── consensus_engine.py      # F-01: Multi-model voting stub
│   └── sentiment_analyzer.py    # F-03: News sentiment stub
├── data_engine/
│   └── regime_classifier.py     # F-02: Market regime stub
├── risk_engine/
│   └── correlation_matrix.py    # F-04: Correlation guard stub
├── analytics/                   # Already exists from additions prompt
│   ├── journal_generator.py     # F-05: Trade journal stub
│   ├── coach_service.py         # F-08: AI coach stub
│   ├── intelligence_report.py   # F-11: Intelligence report stub
│   ├── risk_of_ruin.py          # F-12: Risk of ruin stub
│   └── backtest_runner.py       # F-13: Backtesting stub
├── marketplace/                 # New directory
│   ├── __init__.py
│   ├── strategy_registry.py     # F-06: Strategy marketplace stub
│   └── copy_executor.py         # F-07: Copy trading stub
├── api/                         # New directory
│   ├── __init__.py
│   ├── public_api.py            # F-14: Public API stub
│   └── webhook_dispatcher.py    # F-14: Webhook delivery stub
└── fund/                        # New directory
├── __init__.py
└── investor_reporting.py    # F-15: Fund reporting stub

## 14.3 New Database Tables
Add these tables to the database schema. All are empty in Phase 0 — they exist so the schema does not need migration when features are activated.


## 14.4 Extended Enums
Add to core/enums.py:

class MarketRegime(str, Enum):
TRENDING      = "TRENDING"
RANGING       = "RANGING"
HIGH_VOL      = "HIGH_VOLATILITY"
LOW_LIQ       = "LOW_LIQUIDITY"
UNKNOWN       = "UNKNOWN"   # Phase 0 default

class CurrencySentiment(str, Enum):
BULLISH  = "BULLISH"
BEARISH  = "BEARISH"
NEUTRAL  = "NEUTRAL"   # Phase 0 default for all currencies

class AssetClass(str, Enum):
FOREX   = "FOREX"    # Phase 0 — only this active
CRYPTO  = "CRYPTO"   # Phase 3
STOCKS  = "STOCKS"   # Phase 3
OPTIONS = "OPTIONS"  # Phase 4

class StrategyStatus(str, Enum):
DRAFT    = "DRAFT"
PENDING  = "PENDING"
ACTIVE   = "ACTIVE"
PAUSED   = "PAUSED"

## 14.5 Extended MarketSnapshot
Add these fields to the MarketSnapshot dataclass. All have safe defaults that produce zero behavioral change in Phase 0:

@dataclass(frozen=True)
class MarketSnapshot:
# ... all existing fields unchanged ...

# F-02: Market regime (default UNKNOWN until RegimeClassifier active)
market_regime: MarketRegime = MarketRegime.UNKNOWN

# F-03: News sentiment (default NEUTRAL for all until SentimentAnalyzer active)
sentiment: dict[str, CurrencySentiment] = field(default_factory=dict)

# F-01: Which AI models to consult (default single-model until ConsensusEngine active)
ai_models: list[str] = field(default_factory=lambda: ["claude-sonnet"])

## 14.6 BrokerInterface Abstract Base Class
Create this now. OandaClient inherits from it. Future brokers (Coinbase, Alpaca, Tastytrade) will implement the same interface, allowing the execution engine to work with any broker without changes.

# infrastructure/broker_interface.py
from abc import ABC, abstractmethod
from decimal import Decimal
from ..core.models import Candle, AccountContext, OrderResult

class BrokerInterface(ABC):
"""Abstract broker interface. All brokers must implement these methods."""

@abstractmethod
async def get_candles(self, pair: str, granularity: str, count: int) -> list[Candle]:
...

@abstractmethod
async def get_account_summary(self) -> AccountContext:
...

@abstractmethod
async def get_open_trades(self) -> list[dict]:
...

@abstractmethod
async def place_market_order(self, pair: str, units: int,
sl: Decimal, tp: Decimal,
client_request_id: str) -> OrderResult:
...

@abstractmethod
async def close_trade(self, broker_trade_id: str) -> dict:
...

@abstractmethod
async def stream_prices(self, pairs: list[str]):
...


# 15. Subagent Architecture Specification
The subagent system adds five specialized Claude API calls alongside the main signal pipeline. Each subagent is isolated, async, and has a stub that is a complete no-op in Phase 0.
## 15.1 Updated System Architecture with Subagents
PHASE 0 (single agent):
DataEngine -> AIBrain (1 Claude call) -> RiskEngine -> Execute

PHASE 2+ (multi-agent):
DataEngine ->
SA-01 Market Analyst (async, runs parallel to data fetch)
|  produces: analyst_briefing (200-400 words)
v
AIBrain Signal Decision (receives briefing, not raw data)
v
RiskEngine -> Execute ->
SA-02 Post-Trade Analyst (fires on close, async)
stores: performance_insights

Parallel at all times (Phase 2):
SA-03 Risk Monitor (every 30 min while positions open)

Weekly batch (Phase 2):
SA-04 Intelligence Subagent (Sunday 19:00 EST)
orchestrates: News Analyst -> Perf Analyst -> Writer

SaaS onboarding (Phase 3):
SA-05 Onboarding Agent (new user signup conversation)
## 15.2 New File Structure for Subagents
backend/lumitrade/subagents/
__init__.py
base_agent.py              # BaseSubagent abstract class
market_analyst.py          # SA-01
post_trade_analyst.py      # SA-02
risk_monitor.py            # SA-03
intelligence_subagent.py   # SA-04
onboarding_agent.py        # SA-05
subagent_orchestrator.py   # Coordinates all agents
## 15.3 BaseSubagent Interface
class BaseSubagent(ABC):
"""All subagents inherit from this. Enforces error isolation."""

model: str = "claude-sonnet-4-20250514"
max_tokens: int = 1000
timeout_seconds: int = 30

@abstractmethod
async def run(self, context: dict) -> dict:
"""Main entry point. Must return dict. Never raise."""
...

async def _call_claude(self, system: str, user: str) -> str:
"""Shared Claude API call with timeout + error handling."""
try:
response = await asyncio.wait_for(
self._anthropic.messages.create(
model=self.model,
max_tokens=self.max_tokens,
system=system,
messages=[{"role": "user", "content": user}]
),
timeout=self.timeout_seconds
)
return response.content[0].text
except Exception as e:
logger.warning("subagent_call_failed",
agent=self.__class__.__name__, error=str(e))
return ""  # Safe empty default
## 15.4 New Database Tables for Subagents
CREATE TABLE analyst_briefings (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
signal_id UUID REFERENCES signals(id),
pair TEXT NOT NULL,
briefing TEXT NOT NULL,
model_used TEXT,
tokens_used INT,
latency_ms INT,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE risk_monitor_log (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
trade_id UUID REFERENCES trades(id),
thesis_valid BOOLEAN NOT NULL,
reasoning TEXT NOT NULL,
recommendation TEXT,
action_taken TEXT,
checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE onboarding_sessions (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
messages JSONB NOT NULL DEFAULT '[]',
completed BOOLEAN NOT NULL DEFAULT FALSE,
settings_applied JSONB,
started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
completed_at TIMESTAMPTZ
);
## 15.5 SubagentOrchestrator
class SubagentOrchestrator:
"""
Manages lifecycle of all 5 subagents.
Instantiated once in main.py alongside other services.
Phase 0: All agents are stubs — orchestrator runs
but produces no output until agents are activated.
"""

def __init__(self, config, db, alert_service):
self.market_analyst    = MarketAnalystAgent(config)
self.post_trade        = PostTradeAnalystAgent(config, db)
self.risk_monitor      = RiskMonitorAgent(config, db, alert_service)
self.intelligence      = IntelligenceSubagent(config, db, alert_service)
self.onboarding        = OnboardingAgent(config, db)

async def get_analyst_briefing(self, snapshot) -> str:
"""Called by SignalScanner before AI signal generation."""
return await self.market_analyst.run({"snapshot": snapshot})

async def run_post_trade(self, trade, signal) -> None:
"""Called by ExecutionEngine after every trade close."""
await self.post_trade.run({"trade": trade, "signal": signal})

async def run_risk_monitor(self, open_trades, market_data) -> None:
"""Called by position_monitor() every 30 minutes."""
await self.risk_monitor.run({"trades": open_trades, "market": market_data})

async def run_weekly_intelligence(self, account_id: str) -> None:
"""Called by weekly scheduler, Sunday 19:00 EST."""
await self.intelligence.run({"account_id": account_id})

async def run_onboarding(self, account_id: str, message: str) -> str:
"""Called by /api/onboarding route for each user message."""
result = await self.onboarding.run({
"account_id": account_id, "user_message": message})
return result.get("response", "")

| Attribute | Value |
|---|---|
| Document | System Architecture Specification (SAS) |
| Preceding Document | Product Requirements Document (PRD) v1.0 |
| Role | Senior System Architect |
| Architect | Claude (AI-assisted) — directed by Abenezer |
| Target Environment | Python 3.11 + Next.js + Supabase + Railway + OANDA |
| Architecture Pattern | Async event-driven + layered service architecture |
| Multi-tenant Ready | Yes — account_id isolation from day one |
| Next Document | Backend Developer Specification (Role 3) |


| Principle | Definition & Application |
|---|---|
| Fail-safe by default | Every component assumes it will fail. Recovery paths, fallbacks, and safe shutdown procedures are designed before the happy path. No exception is silently swallowed. |
| Explicit over implicit | All state is persisted to the database. No in-memory globals. All configuration comes from the database or environment. Nothing is hardcoded in business logic. |
| Single responsibility | Each module does exactly one thing. The data engine does not make AI calls. The AI brain does not place orders. The risk engine does not communicate with brokers. Strict boundaries. |
| Observable by design | Every significant event — signal, decision, trade, error, recovery — generates a structured log record. The system can be fully audited from the database alone, without reading source code. |
| Future-proof contracts | All inter-module communication uses typed dataclass contracts. All database tables include account_id. All configuration is database-stored. Refactoring one module never requires touching another. |


| Layer | Responsibility |
|---|---|
| L1 — Infrastructure | Cloud hosting, process supervision, database, secrets, monitoring, failover |
| L2 — Data Engine | Market data ingestion, validation, indicator computation, economic calendar |
| L3 — AI Brain | Signal generation via Claude API, output validation, confidence adjustment |
| L4 — Risk Engine | Signal validation, position sizing, risk state management, safety filters |
| L5 — Execution Engine | Order placement, fill verification, position management, broker API |
| L6 — Dashboard & Alerting | Real-time UI, performance analytics, alert delivery, system control |


| Stage | Input → Output → Destination |
|---|---|
| 1. Market data ingestion | OANDA API → Raw tick / OHLC candles → Data validation layer |
| 2. Data validation | Raw data → Validated MarketData object OR ValidationFailure → Signal scanner OR halt |
| 3. Indicator computation | Validated candles → IndicatorSet (RSI, MACD, EMA, ATR, BB) → Signal scanner |
| 4. Market snapshot assembly | MarketData + IndicatorSet + NewsEvents → MarketSnapshot → AI Brain |
| 5. AI signal generation | MarketSnapshot → Claude API → Raw JSON response → AI validator |
| 6. AI output validation | Raw JSON → Validated SignalProposal OR ValidationFailure → Risk engine OR log+halt |
| 7. Confidence adjustment | SignalProposal → Adjusted confidence score → Risk engine threshold check |
| 8. Risk engine validation | SignalProposal → ApprovedOrder OR RiskRejection → Execution engine OR log+halt |
| 9. Order execution | ApprovedOrder → OANDA API → OrderResult → Fill verifier |
| 10. Fill verification | OrderResult → FillVerification (slippage check) → Trade logger |
| 11. Trade logging | FillVerification → Database record → Alert dispatcher |
| 12. Alert dispatch | Trade event → SMS (Twilio) + Email queue → Delivery log |


| Control Action | Source → Target → Effect |
|---|---|
| Kill switch activation | Dashboard UI → /api/control/kill-switch → Risk engine → EMERGENCY_HALT state → Close all positions |
| Settings update | Dashboard UI → /api/settings PUT → system_config table → All engines read new config on next cycle |
| Mode switch (paper/live) | Dashboard UI → /api/settings → account.account_type → Execution engine routes to simulator or OANDA |
| Manual position close | Dashboard UI → /api/positions/{id}/close → Execution engine → OANDA close order |
| System restart (weekly halt) | Dashboard UI → /api/control/restart → Risk engine → Reset state → Resume NORMAL |


| Component | Imports From | Never Imports From |
|---|---|---|
| data_engine | oanda_client, validators, db_client, logger | ai_brain, risk_engine, execution_engine |
| ai_brain | anthropic_client, validators, db_client, logger | data_engine, risk_engine, execution_engine |
| risk_engine | db_client, logger, config_service | data_engine, ai_brain, execution_engine |
| execution_engine | oanda_client, db_client, logger, alert_service | data_engine, ai_brain, risk_engine |
| dashboard_api | db_client, config_service, logger | data_engine, ai_brain, risk_engine, execution_engine |
| alert_service | twilio_client, sendgrid_client, db_client, logger | all trading components |
| state_manager | db_client, oanda_client, logger | all trading components |
| watchdog | state_manager, logger, alert_service | all trading components |


| Attribute | Specification |
|---|---|
| Responsibility | Start/stop all async tasks. Handle SIGTERM/SIGINT. Coordinate graceful shutdown. |
| Async tasks spawned | price_stream_task, signal_scan_task, position_monitor_task, state_persist_task, heartbeat_task |
| Startup sequence | 1. Load config. 2. Connect DB. 3. Restore system state. 4. Acquire primary lock. 5. Validate OANDA connection. 6. Start all tasks. 7. Signal ready. |
| Shutdown sequence | 1. Stop new signal scans. 2. Wait for in-flight executions (max 30s). 3. Persist final state. 4. Release primary lock. 5. Close all connections. 6. Exit 0. |
| Crash behavior | Supervisord detects non-zero exit. Restarts within 30s. OrchestratorService runs startup sequence including position reconciliation. |


| Attribute | Specification |
|---|---|
| Responsibility | All market data acquisition, validation, and indicator computation. |
| Sub-components | PriceStreamManager, CandleFetcher, IndicatorComputer, DataValidator, CalendarFetcher |
| Output contract | Produces MarketSnapshot dataclass consumed only by SignalScanner |
| State | Maintains rolling price buffer (last 200 ticks per pair) in memory for spike detection. No other mutable state. |
| Resilience | Primary: OANDA streaming. Fallback: REST polling every 5s. If both fail: DataUnavailable event → signal scan skipped. |
| Validation pipeline | Freshness → Spike detection → Spread check → Pair ID verification → OHLC integrity → Gap detection |
| Indicator computation | Triggered after every new confirmed candle. Uses pandas-ta. All values stored in IndicatorSet dataclass. |


| Attribute | Specification |
|---|---|
| Responsibility | Orchestrate signal generation cycle: request snapshot, call AI, validate output, forward to risk engine. |
| Scan interval | Configurable. Default 15 minutes per pair. Staggered: EUR/USD at :00, GBP/USD at :05, USD/JPY at :10. |
| Pair lock | Acquires per-pair asyncio.Lock before scanning. Prevents concurrent scans on same pair. |
| AI retry protocol | Attempt 1: full prompt. Attempt 2: simplified prompt + explicit format reminder. Attempt 3: rule-based fallback. Attempt 4: HOLD + AI_UNAVAILABLE log. |
| Output | Produces SignalProposal passed to RiskEngine. Also writes signal record to DB regardless of outcome. |
| Cooldown enforcement | Checks last trade timestamp per pair before initiating scan. Skips if within cooldown window. |


| Attribute | Specification |
|---|---|
| Responsibility | Validate every SignalProposal against all risk rules. Produce ApprovedOrder or RiskRejection. |
| State source | Reads risk state from SystemState (DB-persisted). Never relies on in-memory state alone. |
| Validation order | State check → Position count → Pair cooldown → Price freshness → Spread check → News blackout → RR ratio → Confidence threshold → Position sizing → Final approval |
| State machine | NORMAL → CAUTIOUS → DAILY_LIMIT → WEEKLY_LIMIT → EMERGENCY_HALT. Also: NEWS_BLOCK, CIRCUIT_OPEN as overlapping conditions. |
| Position sizing | Computed fresh on every approval using live account balance from OANDA API. Not cached. |
| Rejection logging | Every rejection writes to risk_events table with: signal_id, rule_violated, current_value, threshold, timestamp. |


| Attribute | Specification |
|---|---|
| Responsibility | Place orders on OANDA, verify fills, manage open positions, handle order lifecycle. |
| Order state machine | PENDING → SUBMITTED → ACKNOWLEDGED → FILLED → MANAGED → CLOSED (or TIMEOUT → QUERY_STATUS → resolve) |
| Idempotency | Generates internal order_ref UUID before submission. Queries OANDA by order_ref if result is ambiguous. Never submits twice without confirming first submission failed. |
| Fill verification | Mandatory for every order. Checks: fill price vs intended (slippage), actual units vs requested (partial fill), SL/TP attached correctly. |
| Circuit breaker | Tracks OANDA API failure count. Trips at 3 failures/60s. Half-open test after 30s. Trips back to open on failure. |
| Paper mode | Identical code path. Order submission method is swapped to PaperOrderSimulator. All logging, validation, and state management identical. |
| Position monitor | Async task running every 60s. Queries all open OANDA positions. Reconciles against DB. Flags phantom or ghost trades. |


| Attribute | Specification |
|---|---|
| Responsibility | Persist and restore complete system state. Reconcile with OANDA after crashes. |
| Persistence frequency | Writes SystemState to DB every 30 seconds and on every state transition. |
| Restore sequence | On startup: read DB state → query OANDA open positions → reconcile differences → log discrepancies → return merged state. |
| Ghost trade detection | Trade in DB as OPEN but not found on OANDA → mark CLOSED with exit_reason=UNKNOWN → CRITICAL alert. |
| Phantom trade detection | Trade on OANDA with no DB record → create emergency record → CRITICAL alert → add to managed positions. |
| Primary lock | Supabase row with TTL. Cloud instance renews every 60s. Local backup checks age every 60s. Takes over if age > 180s. |


| Attribute | Specification |
|---|---|
| Framework | Next.js API routes (server-side). Authenticated via Supabase Auth. |
| Real-time updates | Supabase Realtime subscriptions on: trades table, signals table, system_state table, risk_events table. |
| Authentication | Supabase Auth JWT. All API routes validate token. Dashboard served only to authenticated user. |
| Read pattern | Dashboard reads from DB only. Never calls OANDA or trading engines directly. State always flows: OANDA → Engine → DB → Dashboard. |
| Write pattern | Settings and control endpoints write to DB. Trading engines pick up changes on next config read cycle (max 60s lag). |
| Kill switch | Writes EMERGENCY_HALT to system_state. ExecutionEngine detects on next position monitor cycle (max 60s). Also sends SIGTERM to trading process via Railway API if available. |


| Task Name | Interval / Trigger | Priority | Failure Behavior |
|---|---|---|---|
| price_stream_task | Continuous (event-driven) | Critical | Reconnect with exponential backoff. After 3 failures: switch to REST polling fallback. |
| signal_scan_task | Every 15 min per pair (staggered) | Critical | Log failure. Skip cycle. Do not retry immediately. Alert on 3 consecutive scan failures. |
| position_monitor_task | Every 60 seconds | High | Log failure. Continue. Alert if 5 consecutive failures (may indicate broker API issue). |
| state_persist_task | Every 30 seconds | High | Log failure. Continue. Alert if state not persisted for > 120 seconds. |
| heartbeat_task | Every 60 seconds | High | Renews primary DB lock. If renewal fails 2 consecutive times: CRITICAL alert. Initiate graceful shutdown. |
| daily_reset_task | Daily at 17:00 EST | Medium | Log failure. Attempt retry at 17:05. Alert on failure. Manual reset available via dashboard. |
| alert_queue_task | Continuous (queue consumer) | Medium | Retry failed deliveries 3 times with backoff. Log permanent failures. |
| config_refresh_task | Every 60 seconds | Low | Reads system_config from DB. Updates all component configs. Log any parse errors. |


| Queue | Producer → Consumer | Max Size / Behavior When Full |
|---|---|---|
| price_queue | price_stream_task → signal_scan_task | 1000 items. Drop oldest on overflow. Log overflow event. |
| signal_queue | signal_scan_task → risk_engine | 100 items. Block producer if full (backpressure). Alert if blocked > 30s. |
| approved_queue | risk_engine → execution_engine | 50 items. Block producer. Prevents execution engine overload. |
| alert_queue | Any component → alert_service | 500 items. Drop oldest if full. Log drop. Alerts must be near-real-time. |
| log_queue | All components → secure_logger | 10000 items. Drop oldest. Log drop count in batch. Never block trading. |


| Decision | Rationale |
|---|---|
| PostgreSQL via Supabase | ACID compliance critical for financial data. Supabase adds Realtime subscriptions for dashboard. Managed service reduces operational overhead. |
| UUID primary keys everywhere | Prevents sequential ID enumeration. Enables client-side ID generation. Consistent across future microservices split. |
| account_id on all tables | Multi-tenant readiness from day one. Row-level security policies can be added per account. No schema migration needed when SaaS launches. |
| JSONB for flexible fields | indicators_snapshot, confidence_adjustment_log, news_context change shape over time. JSONB allows schema evolution without migrations. |
| DECIMAL for all financial values | Never use FLOAT for money. DECIMAL(10,5) for prices. DECIMAL(10,2) for USD amounts. Exact arithmetic. |
| TIMESTAMPTZ for all timestamps | Always UTC. Timezone-aware comparisons. Consistent across Railway (UTC) and local backup. |
| Immutable trade records | Trades are never updated after close. New records for corrections. Full audit trail preserved. |
| Separate execution_log table | OANDA API calls logged separately from business domain. High volume, different retention policy. |


| Table | Index Columns | Query Pattern Served |
|---|---|---|
| trades | account_id, status | Load all open trades on startup and dashboard |
| trades | account_id, opened_at DESC | Trade history pagination (most recent first) |
| trades | account_id, pair, opened_at DESC | Per-pair performance analysis |
| trades | account_id, outcome, opened_at | Win rate calculation queries |
| signals | account_id, created_at DESC | Signal feed — most recent first |
| signals | account_id, pair, executed | Per-pair signal quality analysis |
| risk_events | account_id, created_at DESC | Risk event feed and alerting |
| execution_log | account_id, created_at DESC | API audit and debugging |
| system_state | id (singleton) | Single-row fast read on every cycle |
| performance_snapshots | account_id, date DESC | Performance chart data |


| Attribute | Specification |
|---|---|
| Service: lumitrade-engine | Python process. Always-on. Supervisord manages sub-processes. 512MB RAM min. Upgrade to 1GB for production. |
| Service: lumitrade-dashboard | Next.js. Railway static deploy or separate service. Autoscaling available on Pro tier. |
| Environment variables | All secrets injected via Railway dashboard. Never in code. Follows .env.example template. |
| Deployment trigger | Push to main branch → GitHub Actions runs tests → on pass → Railway auto-deploys. |
| Health check | GET /health → 200 OK with component status JSON. Railway uses this for deploy health gate. |
| Logs | Structured JSON logs streamed to Railway log viewer. Also persisted to Supabase logs table. |
| Restart policy | Railway restarts crashed services automatically. Supervisord additionally manages sub-process restarts. |
| Region | US-East recommended for OANDA API latency. Configure in Railway service settings. |


| Attribute | Specification |
|---|---|
| Purpose | Automatic failover when cloud primary is unresponsive. Not a development environment. |
| Hardware | Any always-on machine. Laptop with no-sleep setting, Raspberry Pi 4, or home server. |
| Software | Same Python environment as cloud. Same code version via git pull on startup. |
| Activation condition | Cloud /health endpoint unresponsive for 3 consecutive checks (3 minutes). |
| Activation sequence | 1. Log takeover event. 2. Acquire primary DB lock. 3. Connect to Supabase. 4. Restore system state. 5. Start trading engine. 6. Send CRITICAL SMS alert. |
| Deactivation | Cloud comes back online. Cloud acquires primary lock. Local detects it lost lock. Local gracefully stops engine. Local reverts to standby monitor. |
| Data source | Same Supabase DB as cloud. No local data store. Fully stateless except for primary lock. |
| Monitoring | UptimeRobot also monitors local backup health endpoint if possible. |


| Variable | Required | Description |
|---|---|---|
| OANDA_API_KEY_DATA | Yes | Read-only OANDA API key for data engine |
| OANDA_API_KEY_TRADING | Yes | Trading-enabled OANDA API key for execution engine only |
| OANDA_ACCOUNT_ID | Yes | OANDA account identifier (not the key) |
| OANDA_ENVIRONMENT | Yes | practice or live |
| ANTHROPIC_API_KEY | Yes | Claude API key for AI brain |
| SUPABASE_URL | Yes | Supabase project URL |
| SUPABASE_SERVICE_KEY | Yes | Supabase service role key (backend only) |
| SUPABASE_ANON_KEY | Yes | Supabase anon key (frontend only) |
| TWILIO_ACCOUNT_SID | Yes | Twilio SMS account SID |
| TWILIO_AUTH_TOKEN | Yes | Twilio auth token |
| TWILIO_FROM_NUMBER | Yes | Twilio sender phone number |
| ALERT_SMS_TO | Yes | Operator phone number for alerts |
| SENDGRID_API_KEY | Yes | SendGrid API key for email alerts |
| ALERT_EMAIL_TO | Yes | Operator email for daily reports |
| INSTANCE_ID | Yes | Unique ID for this instance (cloud or local) |
| TRADING_MODE | Yes | PAPER or LIVE — overrides DB setting if set |
| LOG_LEVEL | No | DEBUG, INFO, WARNING, ERROR. Default: INFO |
| SENTRY_DSN | No | Sentry error tracking DSN |
| FOREX_FACTORY_API_KEY | No | News calendar API key (falls back to scraping) |


| Boundary | Security Control |
|---|---|
| All external HTTPS calls | HTTPX with TLS 1.3 minimum. Certificate verification enforced. No SSL verification bypass ever. |
| OANDA API | IP whitelisting in OANDA portal. Cloud server outbound IP whitelisted. Trading key restricted to execution_engine module only. |
| Supabase connections | TLS enforced by Supabase. Service key used only server-side. Anon key exposed to frontend with RLS enforcement. |
| Dashboard access | Supabase Auth JWT required. HTTPS only. No HTTP redirect. |
| Inter-process communication | All within single Railway service. No external network exposure between engine and watchdog. |


| Attribute | Specification |
|---|---|
| Format | Structured JSON. One JSON object per line. Machine-readable and human-readable. |
| Required fields | timestamp (ISO-8601 UTC), level, component, event, trace_id, data{} |
| Optional fields | duration_ms, pair, signal_id, trade_id, error_type, stack_trace |
| trace_id | UUID generated per signal scan cycle. Propagated through all components. Links data → AI → risk → execution records. |
| Sinks | 1. stdout (Railway captures). 2. Supabase system_events table (CRITICAL/ERROR only). 3. Sentry (ERROR/CRITICAL + exception). |
| Sensitive data | SecureLogger.scrub() applied to every message before any sink. Verified by unit test. |
| Log retention | Railway: 7 days rolling. Supabase: indefinite for ERROR+. 30 days for INFO. |


| Event | Severity | Channel | Response Time |
|---|---|---|---|
| Trade opened or closed | INFO | Daily email digest | Next morning |
| Signal generated (any) | INFO | Dashboard only | N/A |
| Risk rejection (any) | INFO | Dashboard only | N/A |
| Stale data detected | WARNING | Email immediate | 1 hour |
| AI retry attempt | WARNING | Email immediate | 1 hour |
| Spread filter triggered | WARNING | Dashboard + email | 1 hour |
| Daily loss limit approaching (−3%) | WARNING | SMS | 15 minutes |
| Circuit breaker tripped | ERROR | SMS | 15 minutes |
| Daily loss limit hit (−5%) | ERROR | SMS | 15 minutes |
| Crash + auto-recovery | ERROR | SMS | 15 minutes |
| Weekly loss limit hit (−10%) | CRITICAL | SMS | Immediate |
| Ghost/phantom trade detected | CRITICAL | SMS | Immediate |
| Primary lock lost by cloud | CRITICAL | SMS | Immediate |
| Kill switch activated | CRITICAL | SMS | Immediate |
| Local backup activated | CRITICAL | SMS | Immediate |


| Layer | Coverage Target | Tools |
|---|---|---|
| Unit tests | > 80% code coverage. Every public function. All edge cases and error paths. | pytest, pytest-asyncio, pytest-mock |
| Integration tests | All component-to-component contracts. All DB operations. All external API wrappers (mocked responses). | pytest, respx (HTTP mocking), pytest-supabase |
| Chaos tests | All failure scenarios: crash mid-order, API timeout, data feed loss, duplicate order attempt. | pytest with custom chaos fixtures |
| Backtests | Strategy validation against 12+ months historical data before any live deployment. | Custom backtest.py script |
| End-to-end | Full paper trade cycle from data ingestion to dashboard display. | pytest + playwright (frontend) |


| Stage | Trigger → Action → Gate |
|---|---|
| Pull Request | PR opened → GitHub Actions: lint (ruff) + type check (mypy) + unit tests → PR blocked if any fail |
| Merge to main | Push to main → Full test suite including integration tests → Must pass 100% |
| Deploy to Railway | Tests pass → Railway auto-deploy → Health check /health → 200 OK required |
| Rollback | Health check fails → Railway rolls back to previous deployment automatically |
| Secrets rotation | Manual trigger → Update Railway env vars → Redeploy (zero-downtime rolling) |


| ADR-001: Python over Node.js for backend |  |
|---|---|
| Context | Backend needs to handle financial calculations, pandas DataFrames, and real-time streaming. Must integrate with pandas-ta for indicators. |
| Decision | Python 3.11 with asyncio |
| Rationale | Dominant language in finance/quant. Best-in-class data libraries (pandas, numpy). pandas-ta has 130+ indicators. Strong async support via asyncio. Claude Code generates high-quality Python. |
| Consequences | Node.js cannot be used for backend logic. All financial computation stays in Python. Next.js frontend communicates via REST/Realtime only. |


| ADR-002: Supabase over raw PostgreSQL |  |
|---|---|
| Context | Need a database that also provides real-time subscriptions for dashboard, authentication, and managed infrastructure. |
| Decision | Supabase (managed PostgreSQL + Realtime + Auth) |
| Rationale | Eliminates need for a separate WebSocket server. Auth handled without custom implementation. Scales from free tier to production. Dashboard can subscribe directly to DB changes. Row-level security built-in for future multi-tenancy. |
| Consequences | Supabase becomes a critical dependency. Vendor lock-in risk is acceptable given Supabase is open-source and self-hostable. Direct psycopg2 access available if needed. |


| ADR-003: Monorepo over separate repositories |  |
|---|---|
| Context | Backend (Python) and frontend (Next.js) are developed simultaneously by one person using Claude Code. |
| Decision | Single GitHub monorepo with backend/ and frontend/ directories |
| Rationale | Simpler for solo development. Claude Code has full context of both components. Shared type definitions possible. Single CI/CD pipeline. No cross-repo dependency management. |
| Consequences | Repository grows larger over time. May need to split into separate repos when team grows beyond 3 engineers. Acceptable tradeoff for Phase 0. |


| ADR-004: asyncio over threading for concurrency |  |
|---|---|
| Context | Need to run multiple concurrent tasks: price streaming, signal scanning, position monitoring, alert dispatch. |
| Decision | Python asyncio with async/await throughout |
| Rationale | I/O-bound workloads (API calls, DB queries) benefit from async. Avoids Python GIL limitations. No thread safety issues. Easier to reason about with asyncio.Lock. Claude Code generates cleaner async Python. |
| Consequences | All components must be async-compatible. Synchronous libraries (some pandas operations) run in executor thread pool. Learning curve for asyncio patterns. |


| ADR-005: DB-first state management |  |
|---|---|
| Context | System must recover from crashes without losing track of open positions or risk state. |
| Decision | All system state persisted to Supabase every 30 seconds and on every state transition. No reliance on in-memory state across restarts. |
| Rationale | Memory is volatile. A crash loses all in-memory state. DB-first means any restart is a clean resume. Also enables the local backup to take over with full context. |
| Consequences | Slight latency on state reads. Mitigated by in-memory cache (StateManager keeps last known state in memory, refreshes from DB every 30s). Acceptable tradeoff for reliability. |


| Attribute | Value |
|---|---|
| Version | 2.0 — future feature component stubs and DB schema additions |
| New components | 15 stub modules, 12 new DB tables, extended enums, abstract interfaces |
| Architecture pattern | Unchanged — async event-driven layered service |
| Backward compatible | 100% — all stubs silent no-ops in Phase 0 |


| Module Path | Class | Phase Activated |
|---|---|---|
| lumitrade/ai_brain/consensus_engine.py | ConsensusEngine | Phase 2 |
| lumitrade/ai_brain/sentiment_analyzer.py | SentimentAnalyzer | Phase 2 |
| lumitrade/data_engine/regime_classifier.py | RegimeClassifier | Phase 2 |
| lumitrade/risk_engine/correlation_matrix.py | CorrelationMatrix | Phase 2 |
| lumitrade/analytics/journal_generator.py | JournalGenerator | Phase 2 |
| lumitrade/analytics/coach_service.py | CoachService | Phase 2 |
| lumitrade/analytics/intelligence_report.py | IntelligenceReportGenerator | Phase 2 |
| lumitrade/analytics/risk_of_ruin.py | RiskOfRuinCalculator | Phase 2 |
| lumitrade/analytics/backtest_runner.py | BacktestRunner | Phase 3 |
| lumitrade/marketplace/strategy_registry.py | StrategyRegistry | Phase 3 |
| lumitrade/marketplace/copy_executor.py | CopyTradeExecutor | Phase 3 |
| lumitrade/api/public_api.py | PublicApiGateway | Phase 3 |
| lumitrade/api/webhook_dispatcher.py | WebhookDispatcher | Phase 3 |
| lumitrade/infrastructure/broker_interface.py | BrokerInterface (abstract) | Phase 0 — OandaClient implements it |
| lumitrade/fund/investor_reporting.py | InvestorReporting | Phase 4 |


| Table | Feature | Key Fields |
|---|---|---|
| trade_journals | F-05 | id, account_id, week_start, content_text, best_trade_id, worst_trade_id, win_rate_change, recommendation, generated_at |
| intelligence_reports | F-11 | id, account_id, week_start, macro_summary, key_levels JSONB, calendar_preview JSONB, system_alignment, generated_at |
| coach_conversations | F-08 | id, account_id, session_id, messages JSONB, created_at, updated_at |
| market_regimes | F-02 | id, account_id, pair, regime (TRENDING/RANGING/HIGH_VOL/LOW_LIQ), ema_spread, atr_ratio, detected_at |
| sentiment_snapshots | F-03 | id, currencies JSONB (EUR/USD/GBP→sentiment), confidence, key_headline, fetched_at |
| strategies | F-06 | id, creator_account_id, name, description, config JSONB, status, live_since, stripe_product_id |
| strategy_subscriptions | F-06 | id, strategy_id, subscriber_account_id, started_at, cancelled_at, stripe_subscription_id |
| copy_relationships | F-07 | id, leader_account_id, follower_account_id, size_multiplier, active, started_at |
| backtest_runs | F-13 | id, account_id, config JSONB, date_range, status, created_at |
| backtest_results | F-13 | id, run_id, trades_count, win_rate, profit_factor, max_drawdown, total_pips, sharpe |
| api_keys | F-14 | id, account_id, key_hash, label, last_used_at, created_at, revoked_at |
| webhook_endpoints | F-14 | id, account_id, url, events JSONB, secret_hash, active, created_at |
| fund_accounts | F-15 | id, investor_name, amount_usd, joined_at, current_value, performance_fee_paid |
