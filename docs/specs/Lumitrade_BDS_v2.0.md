



LUMITRADE
Backend Developer Specification

ROLE 3 — SENIOR BACKEND DEVELOPER
Version 1.0  |  Python 3.11 + asyncio + Supabase + OANDA + Claude API
Classification: Confidential
Date: March 20, 2026




# 1. Backend Development Standards
## 1.1 Code Quality Standards

## 1.2 Python Dependencies — requirements.txt
Pinning Policy  All dependencies pinned to exact versions. Hashes required for all packages. Run: pip-compile --generate-hashes to regenerate after any update.

# ── Core async & HTTP ─────────────────────────────────────────
aiohttp==3.9.3
httpx==0.27.0
aiofiles==23.2.1

# ── OANDA API ─────────────────────────────────────────────────
# Using raw httpx — no official async OANDA SDK exists
# OANDA v20 API documented at: https://developer.oanda.com/rest-live-v20/introduction/

# ── Anthropic / Claude ────────────────────────────────────────
anthropic==0.25.0

# ── Database ──────────────────────────────────────────────────
supabase==2.4.0
postgrest==0.16.1

# ── Financial data & indicators ───────────────────────────────
pandas==2.2.1
numpy==1.26.4
pandas-ta==0.3.14b

# ── Alerting ──────────────────────────────────────────────────
twilio==8.13.0
sendgrid==6.11.0

# ── Logging & observability ───────────────────────────────────
structlog==24.1.0
sentry-sdk==1.45.0

# ── Config & environment ──────────────────────────────────────
python-dotenv==1.0.1
pydantic==2.6.4
pydantic-settings==2.2.1

# ── Testing ───────────────────────────────────────────────────
pytest==8.1.1
pytest-asyncio==0.23.6
pytest-mock==3.14.0
respx==0.20.2
pytest-cov==5.0.0
hypothesis==6.100.0

# ── Code quality ──────────────────────────────────────────────
ruff==0.3.4
mypy==1.9.0
pre-commit==3.7.0

# 2. Core Domain Models
## 2.1 core/enums.py — Complete Enum Definitions
from enum import Enum, auto

class Action(str, Enum):
BUY  = "BUY"
SELL = "SELL"
HOLD = "HOLD"

class Direction(str, Enum):
BUY  = "BUY"
SELL = "SELL"

class RiskState(str, Enum):
NORMAL         = "NORMAL"
CAUTIOUS       = "CAUTIOUS"
NEWS_BLOCK     = "NEWS_BLOCK"
DAILY_LIMIT    = "DAILY_LIMIT"
WEEKLY_LIMIT   = "WEEKLY_LIMIT"
CIRCUIT_OPEN   = "CIRCUIT_OPEN"
EMERGENCY_HALT = "EMERGENCY_HALT"

class Session(str, Enum):
LONDON    = "LONDON"
NEW_YORK  = "NEW_YORK"
OVERLAP   = "OVERLAP"
TOKYO     = "TOKYO"
OTHER     = "OTHER"

class TradingMode(str, Enum):
PAPER = "PAPER"
LIVE  = "LIVE"

class ExitReason(str, Enum):
SL_HIT    = "SL_HIT"
TP_HIT    = "TP_HIT"
AI_CLOSE  = "AI_CLOSE"
MANUAL    = "MANUAL"
EMERGENCY = "EMERGENCY"
UNKNOWN   = "UNKNOWN"

class OrderStatus(str, Enum):
PENDING         = "PENDING"
SUBMITTED       = "SUBMITTED"
ACKNOWLEDGED    = "ACKNOWLEDGED"
FILLED          = "FILLED"
PARTIAL         = "PARTIAL"
REJECTED        = "REJECTED"
TIMEOUT         = "TIMEOUT"
CANCELLED       = "CANCELLED"

class Outcome(str, Enum):
WIN       = "WIN"
LOSS      = "LOSS"
BREAKEVEN = "BREAKEVEN"

class TradeDuration(str, Enum):
SCALP    = "SCALP"     # < 1 hour
INTRADAY = "INTRADAY"  # 1-8 hours
SWING    = "SWING"     # 1-3 days

class GenerationMethod(str, Enum):
AI         = "AI"
RULE_BASED = "RULE_BASED"

class NewsImpact(str, Enum):
HIGH   = "HIGH"
MEDIUM = "MEDIUM"
LOW    = "LOW"

class CircuitBreakerState(str, Enum):
CLOSED    = "CLOSED"
OPEN      = "OPEN"
HALF_OPEN = "HALF_OPEN"

## 2.2 core/models.py — Complete Dataclass Definitions
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Optional
from .enums import *

# ── Market Data Models ─────────────────────────────────────────

@dataclass(frozen=True)
class Candle:
time: datetime
open: Decimal
high: Decimal
low: Decimal
close: Decimal
volume: int
complete: bool          # False = current forming candle
timeframe: str          # "M5","M15","H1","H4","D"

@dataclass(frozen=True)
class PriceTick:
pair: str
bid: Decimal
ask: Decimal
timestamp: datetime

@property
def mid(self) -> Decimal:
return (self.bid + self.ask) / 2

@property
def spread_pips(self) -> Decimal:
pip_size = Decimal("0.0001") if "JPY" not in self.pair else Decimal("0.01")
return (self.ask - self.bid) / pip_size

@dataclass(frozen=True)
class IndicatorSet:
rsi_14: Decimal
macd_line: Decimal
macd_signal: Decimal
macd_histogram: Decimal
ema_20: Decimal
ema_50: Decimal
ema_200: Decimal
atr_14: Decimal
bb_upper: Decimal
bb_mid: Decimal
bb_lower: Decimal
computed_at: datetime

def to_dict(self) -> dict:
return {k: str(v) for k, v in self.__dict__.items()}

@dataclass(frozen=True)
class NewsEvent:
event_id: str
title: str
currencies_affected: list[str]  # e.g. ["EUR", "USD"]
impact: NewsImpact
scheduled_at: datetime
minutes_until: int              # negative = already happened

@dataclass(frozen=True)
class DataQuality:
is_fresh: bool                  # Price < 5s old
spike_detected: bool
spread_acceptable: bool
candles_complete: bool          # No gaps detected
ohlc_valid: bool

@property
def is_tradeable(self) -> bool:
return (self.is_fresh and not self.spike_detected
and self.spread_acceptable and self.candles_complete
and self.ohlc_valid)

@dataclass(frozen=True)
class AccountContext:
account_id: str
balance: Decimal
equity: Decimal
margin_used: Decimal
open_trade_count: int
daily_pnl: Decimal
fetched_at: datetime

@dataclass(frozen=True)
class TradeSummary:           # Recent trade context for AI prompt
pair: str
direction: Direction
outcome: Optional[Outcome]
pnl_pips: Optional[Decimal]
opened_at: datetime
closed_at: Optional[datetime]

@dataclass(frozen=True)
class MarketSnapshot:
pair: str
session: Session
timestamp: datetime
bid: Decimal
ask: Decimal
spread_pips: Decimal
candles_m15: list[Candle]
candles_h1: list[Candle]
candles_h4: list[Candle]
indicators: IndicatorSet
news_events: list[NewsEvent]
recent_trades: list[TradeSummary]
account_context: AccountContext
data_quality: DataQuality

# ── Signal & Order Models ──────────────────────────────────────

@dataclass(frozen=True)
class SignalProposal:
signal_id: UUID
pair: str
action: Action
confidence_raw: Decimal
confidence_adjusted: Decimal
confidence_adjustment_log: dict
entry_price: Decimal
stop_loss: Decimal
take_profit: Decimal
summary: str
reasoning: str
timeframe_scores: dict
indicators_snapshot: dict
key_levels: list[Decimal]
invalidation_level: Decimal
expected_duration: TradeDuration
generation_method: GenerationMethod
session: Session
spread_pips: Decimal
news_context: list[NewsEvent]
ai_prompt_hash: str
created_at: datetime

@dataclass(frozen=True)
class ApprovedOrder:
order_ref: UUID
signal_id: UUID
pair: str
direction: Direction
units: int
entry_price: Decimal
stop_loss: Decimal
take_profit: Decimal
risk_amount_usd: Decimal
risk_pct: Decimal
account_balance_at_approval: Decimal
approved_at: datetime
expiry: datetime
mode: TradingMode

@property
def is_expired(self) -> bool:
from datetime import timezone
return datetime.now(timezone.utc) > self.expiry

@dataclass(frozen=True)
class OrderResult:
order_ref: UUID
broker_order_id: str
broker_trade_id: str
status: OrderStatus
fill_price: Decimal
fill_units: int
fill_timestamp: datetime
stop_loss_confirmed: Decimal
take_profit_confirmed: Decimal
slippage_pips: Decimal
raw_response: dict

@dataclass(frozen=True)
class RiskRejection:
signal_id: UUID
rule_violated: str
current_value: str
threshold: str
risk_state: RiskState
rejected_at: datetime

# 3. Configuration System
## 3.1 config.py — Pydantic Settings
from pydantic_settings import BaseSettings
from pydantic import Field
from decimal import Decimal

class LumitradeConfig(BaseSettings):
"""All configuration loaded from environment variables."""

# OANDA
oanda_api_key_data: str     = Field(alias="OANDA_API_KEY_DATA")
oanda_api_key_trading: str  = Field(alias="OANDA_API_KEY_TRADING")
oanda_account_id: str       = Field(alias="OANDA_ACCOUNT_ID")
oanda_environment: str      = Field(alias="OANDA_ENVIRONMENT", default="practice")

# Anthropic
anthropic_api_key: str      = Field(alias="ANTHROPIC_API_KEY")
claude_model: str           = "claude-sonnet-4-20250514"
claude_max_tokens: int      = 2000

# Supabase
supabase_url: str           = Field(alias="SUPABASE_URL")
supabase_service_key: str   = Field(alias="SUPABASE_SERVICE_KEY")

# Alerting
twilio_account_sid: str     = Field(alias="TWILIO_ACCOUNT_SID")
twilio_auth_token: str      = Field(alias="TWILIO_AUTH_TOKEN")
twilio_from_number: str     = Field(alias="TWILIO_FROM_NUMBER")
alert_sms_to: str           = Field(alias="ALERT_SMS_TO")
sendgrid_api_key: str       = Field(alias="SENDGRID_API_KEY")
alert_email_to: str         = Field(alias="ALERT_EMAIL_TO")

# Instance
instance_id: str            = Field(alias="INSTANCE_ID")
trading_mode: str           = Field(alias="TRADING_MODE", default="PAPER")
log_level: str              = Field(alias="LOG_LEVEL", default="INFO")
sentry_dsn: str             = Field(alias="SENTRY_DSN", default="")

# Trading parameters (also readable from DB — DB overrides env)
pairs: list[str]            = ["EUR_USD", "GBP_USD", "USD_JPY"]
signal_interval_minutes: int = 15
max_risk_pct: Decimal       = Decimal("0.02")   # 2% max
min_confidence: Decimal     = Decimal("0.65")
max_open_trades: int        = 3
daily_loss_limit_pct: Decimal = Decimal("0.05") # 5%
weekly_loss_limit_pct: Decimal = Decimal("0.10") # 10%
max_spread_pips: Decimal    = Decimal("3.0")
news_blackout_before_min: int = 30
news_blackout_after_min: int  = 15
trade_cooldown_minutes: int   = 60
min_rr_ratio: Decimal       = Decimal("1.5")

@property
def oanda_base_url(self) -> str:
env = "fxtrade" if self.oanda_environment == "live" else "fxpractice"
return f"https://api-{env}.oanda.com"

@property
def oanda_stream_url(self) -> str:
env = "stream-fxtrade" if self.oanda_environment == "live" else "stream-fxpractice"
return f"https://{env}.oanda.com"

class Config:
populate_by_name = True
env_file = ".env"

# Singleton — import this everywhere
config = LumitradeConfig()

# 4. Data Engine Implementation
## 4.1 infrastructure/oanda_client.py
import httpx
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from ..config import config
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

class OandaClient:
"""Read-only OANDA client. Uses DATA key only."""

BASE_URL = config.oanda_base_url
STREAM_URL = config.oanda_stream_url

def __init__(self):
self._headers = {
"Authorization": f"Bearer {config.oanda_api_key_data}",
"Content-Type": "application/json",
}
self._client = httpx.AsyncClient(
headers=self._headers,
timeout=httpx.Timeout(10.0),
verify=True,   # Never disable TLS verification
)

async def get_candles(
self, pair: str, granularity: str, count: int = 50
) -> list[dict]:
"""Fetch OHLCV candles from OANDA REST API."""
url = f"{self.BASE_URL}/v3/instruments/{pair}/candles"
params = {"granularity": granularity, "count": count, "price": "M"}
try:
resp = await self._client.get(url, params=params)
resp.raise_for_status()
return resp.json()["candles"]
except httpx.HTTPStatusError as e:
logger.error("oanda_candle_fetch_failed", pair=pair,
granularity=granularity, status=e.response.status_code)
raise

async def get_pricing(self, pairs: list[str]) -> dict:
"""Get current bid/ask for one or more pairs."""
url = f"{self.BASE_URL}/v3/accounts/{config.oanda_account_id}/pricing"
params = {"instruments": ",".join(pairs)}
resp = await self._client.get(url, params=params)
resp.raise_for_status()
return resp.json()

async def get_account_summary(self) -> dict:
"""Fetch account balance, equity, margin."""
url = f"{self.BASE_URL}/v3/accounts/{config.oanda_account_id}/summary"
resp = await self._client.get(url)
resp.raise_for_status()
return resp.json()["account"]

async def get_open_trades(self) -> list[dict]:
"""Fetch all currently open trades."""
url = f"{self.BASE_URL}/v3/accounts/{config.oanda_account_id}/openTrades"
resp = await self._client.get(url)
resp.raise_for_status()
return resp.json()["trades"]

async def stream_prices(self, pairs: list[str]):
"""Async generator yielding real-time price ticks."""
url = f"{self.STREAM_URL}/v3/accounts/{config.oanda_account_id}/pricing/stream"
params = {"instruments": ",".join(pairs)}
stream_headers = {**self._headers}
async with httpx.AsyncClient(timeout=None, verify=True) as client:
async with client.stream("GET", url, params=params,
headers=stream_headers) as resp:
resp.raise_for_status()
async for line in resp.aiter_lines():
if line.strip():
yield line

async def close(self):
await self._client.aclose()


class OandaTradingClient(OandaClient):
"""Trading-capable OANDA client. Uses TRADING key."""
# ONLY instantiated by ExecutionEngine. Never import elsewhere.

def __init__(self):
super().__init__()
# Override with trading key for order methods
self._trading_headers = {
"Authorization": f"Bearer {config.oanda_api_key_trading}",
"Content-Type": "application/json",
}
self._trading_client = httpx.AsyncClient(
headers=self._trading_headers,
timeout=httpx.Timeout(15.0),
verify=True,
)

async def place_market_order(
self, pair: str, units: int, sl: Decimal, tp: Decimal,
client_request_id: str
) -> dict:
"""Place market order with attached SL and TP."""
url = f"{self.BASE_URL}/v3/accounts/{config.oanda_account_id}/orders"
body = {
"order": {
"type": "MARKET",
"instrument": pair,
"units": str(units),
"stopLossOnFill": {"price": str(sl)},
"takeProfitOnFill": {"price": str(tp)},
"clientExtensions": {"id": client_request_id},
}
}
resp = await self._trading_client.post(url, json=body)
resp.raise_for_status()
return resp.json()

async def close_trade(self, broker_trade_id: str) -> dict:
url = (f"{self.BASE_URL}/v3/accounts/{config.oanda_account_id}"
f"/trades/{broker_trade_id}/close")
resp = await self._trading_client.put(url, json={"units": "ALL"})
resp.raise_for_status()
return resp.json()

async def modify_trade(
self, broker_trade_id: str, sl: Decimal, tp: Decimal
) -> dict:
url = (f"{self.BASE_URL}/v3/accounts/{config.oanda_account_id}"
f"/trades/{broker_trade_id}/orders")
body = {
"stopLoss": {"price": str(sl)},
"takeProfit": {"price": str(tp)},
}
resp = await self._trading_client.put(url, json=body)
resp.raise_for_status()
return resp.json()

## 4.2 data_engine/validator.py
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from dataclasses import dataclass
from collections import deque
from ..core.models import PriceTick, Candle, DataQuality
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

STALE_THRESHOLD_SECONDS = 5
SPIKE_STD_MULTIPLIER    = Decimal("3.0")
ROLLING_WINDOW          = 20
MAX_SPREAD_PIPS         = Decimal("5.0")  # Hard ceiling — config threshold is lower

class DataValidator:
"""Validates all incoming market data before use."""

def __init__(self):
# Rolling price buffer per pair for spike detection
self._price_history: dict[str, deque[Decimal]] = {}

def validate_tick(self, tick: PriceTick) -> DataQuality:
"""Full validation pipeline for a price tick."""
is_fresh        = self._check_freshness(tick)
spike_detected  = self._check_spike(tick)
spread_ok       = self._check_spread(tick)

if not spike_detected:
self._update_price_history(tick)

quality = DataQuality(
is_fresh=is_fresh,
spike_detected=spike_detected,
spread_acceptable=spread_ok,
candles_complete=True,   # Set by candle validator separately
ohlc_valid=True,
)

if not quality.is_tradeable:
logger.warning("data_quality_check_failed", pair=tick.pair,
fresh=is_fresh, spike=spike_detected, spread=spread_ok)
return quality

def validate_candles(self, candles: list[Candle]) -> bool:
"""Validate candle series integrity."""
for candle in candles:
if not self._check_ohlc(candle):
logger.error("ohlc_integrity_failed", candle_time=candle.time)
return False
if not self._check_gaps(candles):
return False
return True

def _check_freshness(self, tick: PriceTick) -> bool:
age = (datetime.now(timezone.utc) - tick.timestamp).total_seconds()
return age <= STALE_THRESHOLD_SECONDS

def _check_spike(self, tick: PriceTick) -> bool:
history = self._price_history.get(tick.pair)
if not history or len(history) < ROLLING_WINDOW:
return False  # Not enough history — cannot detect spike
mean = sum(history) / len(history)
variance = sum((p - mean) ** 2 for p in history) / len(history)
std = variance ** Decimal("0.5")
if std == 0:
return False
z_score = abs(tick.mid - mean) / std
return z_score > SPIKE_STD_MULTIPLIER

def _check_spread(self, tick: PriceTick) -> bool:
return tick.spread_pips <= MAX_SPREAD_PIPS

def _check_ohlc(self, c: Candle) -> bool:
return (c.low <= c.open <= c.high and c.low <= c.close <= c.high)

def _check_gaps(self, candles: list[Candle]) -> bool:
tf_seconds = {"M5":300,"M15":900,"H1":3600,"H4":14400,"D":86400}
if len(candles) < 2:
return True
expected = tf_seconds.get(candles[0].timeframe, 900)
for i in range(1, len(candles)):
gap = (candles[i].time - candles[i-1].time).total_seconds()
if gap > expected * 1.5:
logger.warning("candle_gap_detected",
gap_seconds=gap, expected=expected,
candle_time=candles[i].time)
return False
return True

def _update_price_history(self, tick: PriceTick):
if tick.pair not in self._price_history:
self._price_history[tick.pair] = deque(maxlen=200)
self._price_history[tick.pair].append(tick.mid)

# 5. AI Brain Implementation
## 5.1 ai_brain/prompt_builder.py
from decimal import Decimal
from ..core.models import MarketSnapshot, NewsEvent
from ..core.enums import Action

SYSTEM_PROMPT = """You are Lumitrade's professional forex trading analyst.
Your role: analyze multi-timeframe market data and generate high-probability
trading signals with disciplined risk management.

CRITICAL RULES:
1. Respond ONLY with valid JSON matching the exact schema below.
2. No text outside the JSON object. No markdown. No code fences.
3. If conditions are unclear or conflicting — return action: HOLD.
4. Never force a trade. Capital preservation over opportunity.
5. confidence must reflect genuine conviction — never inflate it.

REQUIRED JSON SCHEMA:
{
"action": "BUY" | "SELL" | "HOLD",
"confidence": 0.0-1.0,
"entry_price": float,
"stop_loss": float,
"take_profit": float,
"summary": "2-4 plain English sentences. No jargon.",
"reasoning": "Full technical analysis. Min 100 words. Cite specific indicator values.",
"timeframe_h4_score": 0.0-1.0,
"timeframe_h1_score": 0.0-1.0,
"timeframe_m15_score": 0.0-1.0,
"key_levels": [float, float],
"invalidation_level": float,
"expected_duration": "SCALP" | "INTRADAY" | "SWING"
}"""


def build_prompt(snapshot: MarketSnapshot) -> str:
"""Assemble the full user prompt from a MarketSnapshot."""
ind = snapshot.indicators
acc = snapshot.account_context

sections = [
f"=== MARKET CONTEXT ===",
f"Pair: {snapshot.pair}",
f"Session: {snapshot.session.value}",
f"Timestamp: {snapshot.timestamp.isoformat()}",
f"Current Bid: {snapshot.bid}  Ask: {snapshot.ask}",
f"Spread: {snapshot.spread_pips} pips",
"",
"=== TECHNICAL INDICATORS ===",
f"RSI(14): {ind.rsi_14}",
f"MACD Line: {ind.macd_line} | Signal: {ind.macd_signal} | Histogram: {ind.macd_histogram}",
f"EMA 20: {ind.ema_20} | EMA 50: {ind.ema_50} | EMA 200: {ind.ema_200}",
f"ATR(14): {ind.atr_14}",
f"Bollinger Upper: {ind.bb_upper} | Mid: {ind.bb_mid} | Lower: {ind.bb_lower}",
"",
"=== CANDLE DATA (last 20 candles each timeframe) ===",
"H4 OHLCV (newest first):",
_format_candles(snapshot.candles_h4[-20:]),
"H1 OHLCV (newest first):",
_format_candles(snapshot.candles_h1[-20:]),
"M15 OHLCV (newest first):",
_format_candles(snapshot.candles_m15[-20:]),
"",
"=== ECONOMIC CALENDAR (next 4 hours) ===",
_format_news(snapshot.news_events),
"",
"=== ACCOUNT CONTEXT ===",
f"Balance: ${acc.balance}  Equity: ${acc.equity}",
f"Open trades: {acc.open_trade_count}  Daily P&L: ${acc.daily_pnl}",
"",
"=== RECENT TRADES ON THIS PAIR (last 3) ===",
_format_recent_trades(snapshot.recent_trades),
"",
"=== YOUR TASK ===",
f"Analyze {snapshot.pair} and return your trading decision as JSON.",
"Apply multi-timeframe confluence: H4 trend + H1 structure + M15 entry.",
"Only recommend BUY or SELL if all three timeframes confirm the bias.",
"Minimum risk/reward ratio: 1.5:1. If not achievable — return HOLD.",
]
return "\n".join(sections)

def _format_candles(candles: list) -> str:
lines = []
for c in reversed(candles):
lines.append(
f"  {c.time.strftime('%Y-%m-%d %H:%M')} "
f"O:{c.open} H:{c.high} L:{c.low} C:{c.close} V:{c.volume}"
)
return "\n".join(lines)

def _format_news(events: list[NewsEvent]) -> str:
if not events:
return "  No high/medium impact events in next 4 hours."
lines = []
for e in events:
lines.append(
f"  [{e.impact.value}] {e.title} "
f"({", ".join(e.currencies_affected)}) "
f"in {e.minutes_until} min"
)
return "\n".join(lines)

def _format_recent_trades(trades: list) -> str:
if not trades:
return "  No recent trades on this pair."
lines = []
for t in trades:
outcome = t.outcome.value if t.outcome else "OPEN"
lines.append(f"  {t.direction.value} | {outcome} | {t.pnl_pips} pips")
return "\n".join(lines)

## 5.2 ai_brain/validator.py
import json
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from ..core.enums import Action, TradeDuration
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

@dataclass
class ValidationResult:
passed: bool
data: dict | None = None
reason: str = ""

REQUIRED_FIELDS = [
"action","confidence","entry_price","stop_loss","take_profit",
"summary","reasoning","timeframe_h4_score","timeframe_h1_score",
"timeframe_m15_score","key_levels","invalidation_level","expected_duration"
]

class AIOutputValidator:
"""Validates raw Claude API JSON output before it enters the pipeline."""

def validate(self, raw: str, live_price: Decimal) -> ValidationResult:
# Step 1: Parse JSON
try:
data = json.loads(raw)
except json.JSONDecodeError as e:
return ValidationResult(False, reason=f"JSON parse failed: {e}")

# Step 2: Required fields
for field in REQUIRED_FIELDS:
if field not in data:
return ValidationResult(False, reason=f"Missing field: {field}")

# Step 3: Action enum
if data["action"] not in [a.value for a in Action]:
return ValidationResult(False, reason=f"Invalid action: {data['action']}")

# Step 4: Numeric bounds
try:
confidence = Decimal(str(data["confidence"]))
entry      = Decimal(str(data["entry_price"]))
sl         = Decimal(str(data["stop_loss"]))
tp         = Decimal(str(data["take_profit"]))
except (InvalidOperation, TypeError) as e:
return ValidationResult(False, reason=f"Numeric conversion failed: {e}")

if not (Decimal("0") <= confidence <= Decimal("1")):
return ValidationResult(False, reason=f"Confidence out of range: {confidence}")

# Step 5: Logic consistency (only for BUY/SELL)
action = data["action"]
if action == "BUY":
if sl >= entry:
return ValidationResult(False, reason="BUY: SL must be below entry")
if tp <= entry:
return ValidationResult(False, reason="BUY: TP must be above entry")
elif action == "SELL":
if sl <= entry:
return ValidationResult(False, reason="SELL: SL must be above entry")
if tp >= entry:
return ValidationResult(False, reason="SELL: TP must be below entry")

# Step 6: Price sanity (entry vs live price)
if action != "HOLD" and live_price > 0:
deviation = abs(entry - live_price) / live_price
if deviation > Decimal("0.005"):
return ValidationResult(
False,
reason=f"Entry {entry} deviates {deviation:.2%} from live {live_price}"
)

# Step 7: Risk/reward ratio
if action != "HOLD":
risk   = abs(entry - sl)
reward = abs(tp - entry)
rr     = reward / risk if risk > 0 else Decimal("0")
if rr < Decimal("1.5"):
return ValidationResult(False, reason=f"RR ratio {rr:.2f} below minimum 1.5")

# Step 8: Summary and reasoning quality
if len(data.get("summary","")) < 20:
return ValidationResult(False, reason="Summary too short")
if len(data.get("reasoning","")) < 100:
return ValidationResult(False, reason="Reasoning too short (min 100 chars)")

logger.info("ai_output_validated", action=action, confidence=str(confidence))
return ValidationResult(True, data=data)

# 6. Risk Engine Implementation
## 6.1 risk_engine/engine.py
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4
from ..core.models import SignalProposal, ApprovedOrder, RiskRejection
from ..core.enums import Action, Direction, RiskState, TradingMode
from ..state.manager import StateManager
from ..config import config
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from .position_sizer import PositionSizer
from .calendar_guard import CalendarGuard
from .state_machine import RiskStateMachine

logger = get_logger(__name__)

class RiskEngine:
"""Validates every SignalProposal against all risk rules."""

def __init__(self, state_manager: StateManager, db: DatabaseClient):
self.state   = state_manager
self.db      = db
self.sizer   = PositionSizer()
self.guard   = CalendarGuard()
self.machine = RiskStateMachine(state_manager)

async def evaluate(
self, proposal: SignalProposal, account_balance: Decimal
) -> ApprovedOrder | RiskRejection:
"""Run full validation pipeline. Returns ApprovedOrder or RiskRejection."""

sys_state = await self.state.get()
rejection = None  # Will be set if any check fails

checks = [
self._check_risk_state(sys_state),
self._check_position_count(sys_state),
self._check_cooldown(proposal.pair, sys_state),
self._check_confidence(proposal, sys_state),
self._check_spread(proposal),
await self._check_news(proposal),
self._check_rr_ratio(proposal),
self._check_action(proposal),
]

for rule_name, passed, reason, value, threshold in checks:
if not passed:
rejection = RiskRejection(
signal_id=proposal.signal_id,
rule_violated=rule_name,
current_value=str(value),
threshold=str(threshold),
risk_state=sys_state.risk_state,
rejected_at=datetime.now(timezone.utc),
)
break

if rejection:
await self._log_rejection(rejection)
return rejection

# All checks passed — size position and create ApprovedOrder
direction = Direction.BUY if proposal.action == Action.BUY else Direction.SELL
risk_pct  = self._confidence_to_risk_pct(proposal.confidence_adjusted)
units, risk_usd = self.sizer.calculate(
balance=account_balance,
risk_pct=risk_pct,
entry=proposal.entry_price,
stop_loss=proposal.stop_loss,
pair=proposal.pair,
)

if units < 1000:
return RiskRejection(
signal_id=proposal.signal_id,
rule_violated="MINIMUM_POSITION_SIZE",
current_value=str(units),
threshold="1000",
risk_state=sys_state.risk_state,
rejected_at=datetime.now(timezone.utc),
)

now = datetime.now(timezone.utc)
return ApprovedOrder(
order_ref=uuid4(),
signal_id=proposal.signal_id,
pair=proposal.pair,
direction=direction,
units=units if direction == Direction.BUY else -units,
entry_price=proposal.entry_price,
stop_loss=proposal.stop_loss,
take_profit=proposal.take_profit,
risk_amount_usd=risk_usd,
risk_pct=risk_pct,
account_balance_at_approval=account_balance,
approved_at=now,
expiry=now + timedelta(seconds=30),
mode=TradingMode(config.trading_mode),
)

def _check_risk_state(self, sys_state):
blocked = {RiskState.DAILY_LIMIT, RiskState.WEEKLY_LIMIT,
RiskState.CIRCUIT_OPEN, RiskState.EMERGENCY_HALT}
passed = sys_state.risk_state not in blocked
return ("RISK_STATE", passed, "",
sys_state.risk_state.value, "NORMAL or CAUTIOUS")

def _check_position_count(self, sys_state):
count   = len(sys_state.open_trades)
max_pos = config.max_open_trades
return ("MAX_POSITIONS", count < max_pos, "",
count, max_pos)

def _check_cooldown(self, pair, sys_state):
last = sys_state.last_signal_time.get(pair)
if not last:
return ("COOLDOWN", True, "", 0, config.trade_cooldown_minutes)
elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
passed  = elapsed >= config.trade_cooldown_minutes
return ("COOLDOWN", passed, "", round(elapsed, 1), config.trade_cooldown_minutes)

def _check_confidence(self, proposal, sys_state):
threshold = (sys_state.confidence_threshold_override
or config.min_confidence)
passed = proposal.confidence_adjusted >= threshold
return ("CONFIDENCE", passed, "",
proposal.confidence_adjusted, threshold)

def _check_spread(self, proposal):
passed = proposal.spread_pips <= config.max_spread_pips
return ("SPREAD", passed, "",
proposal.spread_pips, config.max_spread_pips)

async def _check_news(self, proposal):
in_blackout = await self.guard.is_blackout(proposal.pair)
return ("NEWS_BLACKOUT", not in_blackout, "", in_blackout, False)

def _check_rr_ratio(self, proposal):
risk   = abs(proposal.entry_price - proposal.stop_loss)
reward = abs(proposal.take_profit - proposal.entry_price)
rr     = reward / risk if risk > 0 else Decimal("0")
passed = rr >= config.min_rr_ratio
return ("RR_RATIO", passed, "", round(rr, 2), config.min_rr_ratio)

def _check_action(self, proposal):
passed = proposal.action in (Action.BUY, Action.SELL)
return ("ACTION_NOT_HOLD", passed, "", proposal.action.value, "BUY or SELL")

def _confidence_to_risk_pct(self, confidence: Decimal) -> Decimal:
if confidence >= Decimal("0.90"):
return Decimal("0.02")
elif confidence >= Decimal("0.80"):
return Decimal("0.01")
else:
return Decimal("0.005")

async def _log_rejection(self, rejection: RiskRejection):
await self.db.insert("risk_events", {
"event_type": rejection.rule_violated,
"detail": f"Signal {rejection.signal_id} rejected: {rejection.current_value} vs {rejection.threshold}",
"signal_id": str(rejection.signal_id),
"risk_state": rejection.risk_state.value,
"created_at": rejection.rejected_at.isoformat(),
})

# 7. Execution Engine Implementation
## 7.1 execution_engine/circuit_breaker.py
import asyncio
from datetime import datetime, timezone
from ..core.enums import CircuitBreakerState
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

FAILURE_THRESHOLD  = 3    # failures to trip
FAILURE_WINDOW_SEC = 60   # within this window
RESET_TIMEOUT_SEC  = 30   # wait before half-open

class CircuitBreaker:
"""Tracks OANDA API failures and trips to protect the account."""

def __init__(self):
self._state       = CircuitBreakerState.CLOSED
self._failures:   list[datetime] = []
self._opened_at:  datetime | None = None
self._lock        = asyncio.Lock()

@property
def state(self) -> CircuitBreakerState:
return self._state

@property
def is_open(self) -> bool:
return self._state == CircuitBreakerState.OPEN

async def record_success(self):
async with self._lock:
if self._state == CircuitBreakerState.HALF_OPEN:
self._state    = CircuitBreakerState.CLOSED
self._failures = []
self._opened_at = None
logger.info("circuit_breaker_closed")

async def record_failure(self):
async with self._lock:
now = datetime.now(timezone.utc)
# Remove failures outside window
self._failures = [
f for f in self._failures
if (now - f).total_seconds() < FAILURE_WINDOW_SEC
]
self._failures.append(now)

if len(self._failures) >= FAILURE_THRESHOLD:
if self._state != CircuitBreakerState.OPEN:
self._state     = CircuitBreakerState.OPEN
self._opened_at = now
logger.error("circuit_breaker_tripped",
failures=len(self._failures))

async def check_and_transition(self) -> CircuitBreakerState:
"""Call before each API attempt. Returns current state."""
async with self._lock:
if self._state == CircuitBreakerState.OPEN:
elapsed = (
datetime.now(timezone.utc) - self._opened_at
).total_seconds()
if elapsed >= RESET_TIMEOUT_SEC:
self._state = CircuitBreakerState.HALF_OPEN
logger.info("circuit_breaker_half_open")
return self._state

## 7.2 execution_engine/fill_verifier.py
from decimal import Decimal
from ..core.models import ApprovedOrder, OrderResult
from ..core.enums import OrderStatus
from ..infrastructure.secure_logger import get_logger
from ..infrastructure.alert_service import AlertService
from ..utils.pip_math import pips_between

logger = get_logger(__name__)
HIGH_SLIPPAGE_THRESHOLD_PIPS = Decimal("3.0")

class FillVerifier:
"""Verifies every order fill meets expectations."""

def __init__(self, alert_service: AlertService):
self.alerts = alert_service

async def verify(
self, order: ApprovedOrder, result: OrderResult
) -> OrderResult:
"""Verify fill and return enriched OrderResult with slippage."""

if result.status != OrderStatus.FILLED:
logger.warning("fill_not_complete",
status=result.status.value,
order_ref=str(order.order_ref))
return result

# Calculate slippage
slippage = pips_between(
order.entry_price, result.fill_price, order.pair
)

if slippage > HIGH_SLIPPAGE_THRESHOLD_PIPS:
msg = (f"HIGH SLIPPAGE: {slippage:.1f} pips on {order.pair} "
f"(intended {order.entry_price}, filled {result.fill_price})")
logger.warning("high_slippage_detected",
slippage_pips=str(slippage),
pair=order.pair)
await self.alerts.send_warning(msg)

# Check for partial fill — recalculate levels if needed
if result.fill_units != abs(order.units):
logger.warning("partial_fill_detected",
expected=abs(order.units),
actual=result.fill_units)

# Verify SL and TP were attached
if not result.stop_loss_confirmed or not result.take_profit_confirmed:
logger.error("sl_tp_not_confirmed",
order_ref=str(order.order_ref))
await self.alerts.send_critical(
f"SL/TP NOT CONFIRMED on trade {result.broker_trade_id}!"
)

logger.info("fill_verified",
pair=order.pair,
fill_price=str(result.fill_price),
slippage_pips=str(slippage),
broker_trade_id=result.broker_trade_id)

from dataclasses import replace
return replace(result, slippage_pips=slippage)

# 8. Infrastructure Layer Implementation
## 8.1 infrastructure/secure_logger.py
import re
import structlog
import logging
from ..config import config

SCRUB_PATTERNS = [
(r"Bearer\s+[A-Za-z0-9\-._]{10,}", "Bearer [REDACTED]"),
(r"(?i)api[_-]?key[\s:=]+\S+",     "api_key=[REDACTED]"),
(r"(?i)password[\s:=]+\S+",         "password=[REDACTED]"),
(r"[A-Za-z0-9+/]{40,}={0,2}",         "[REDACTED_TOKEN]"),
]

def _scrub(_, __, event_dict):
"""structlog processor that scrubs sensitive data from all log values."""
for key, value in event_dict.items():
if isinstance(value, str):
for pattern, replacement in SCRUB_PATTERNS:
value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
event_dict[key] = value
return event_dict

def configure_logging():
"""Call once at startup from main.py."""
level = getattr(logging, config.log_level.upper(), logging.INFO)
structlog.configure(
processors=[
structlog.stdlib.filter_by_level,
structlog.stdlib.add_logger_name,
structlog.stdlib.add_log_level,
structlog.processors.TimeStamper(fmt="iso", utc=True),
_scrub,                              # Scrub BEFORE rendering
structlog.processors.JSONRenderer(), # Output JSON
],
wrapper_class=structlog.stdlib.BoundLogger,
context_class=dict,
logger_factory=structlog.stdlib.LoggerFactory(),
cache_logger_on_first_use=True,
)
logging.basicConfig(level=level)

def get_logger(name: str):
return structlog.get_logger(name)

## 8.2 infrastructure/alert_service.py
import asyncio
from twilio.rest import Client as TwilioClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from ..config import config
from .secure_logger import get_logger
from ..infrastructure.db import DatabaseClient

logger = get_logger(__name__)

class AlertService:
"""Delivers SMS and email alerts. All sends logged to alerts_log table."""

def __init__(self, db: DatabaseClient):
self.db      = db
self._twilio = TwilioClient(config.twilio_account_sid,
config.twilio_auth_token)
self._sg     = SendGridAPIClient(config.sendgrid_api_key)

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
None, self._send_sms, message
)
await self._log_alert("ERROR", message, channel="sms")

async def send_critical(self, message: str):
"""Critical: SMS + email immediately."""
await asyncio.get_event_loop().run_in_executor(
None, self._send_sms, f"CRITICAL: {message}"
)
await asyncio.get_event_loop().run_in_executor(
None, self._send_email, "CRITICAL", message
)
await self._log_alert("CRITICAL", message, channel="sms+email")

def _send_sms(self, body: str):
try:
msg = self._twilio.messages.create(
body=f"[LUMITRADE] {body}",
from_=config.twilio_from_number,
to=config.alert_sms_to,
)
logger.info("sms_sent", sid=msg.sid)
except Exception as e:
logger.error("sms_send_failed", error=str(e))

def _send_email(self, level: str, body: str):
try:
mail = Mail(
from_email="alerts@lumitrade.app",
to_emails=config.alert_email_to,
subject=f"[Lumitrade {level}] {body[:80]}",
plain_text_content=body,
)
self._sg.send(mail)
logger.info("email_sent", level=level)
except Exception as e:
logger.error("email_send_failed", error=str(e))

async def _log_alert(self, level: str, message: str, channel: str):
from datetime import datetime, timezone
await self.db.insert("alerts_log", {
"level": level, "message": message,
"channel": channel,
"created_at": datetime.now(timezone.utc).isoformat(),
})

# 9. Database Migrations
## 9.1 001_initial_schema.sql
-- Lumitrade Initial Schema
-- Run: psql $DATABASE_URL < database/migrations/001_initial_schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── accounts ──────────────────────────────────────────────────
CREATE TABLE accounts (
id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
owner_name      TEXT NOT NULL,
broker          TEXT NOT NULL DEFAULT 'OANDA',
broker_account_id TEXT NOT NULL,
account_type    TEXT NOT NULL CHECK (account_type IN ('PRACTICE','LIVE')),
base_currency   TEXT NOT NULL DEFAULT 'USD',
is_active       BOOLEAN NOT NULL DEFAULT TRUE,
created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── signals ────────────────────────────────────────────────────
CREATE TABLE signals (
id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id              UUID NOT NULL REFERENCES accounts(id),
pair                    TEXT NOT NULL,
action                  TEXT NOT NULL CHECK (action IN ('BUY','SELL','HOLD')),
confidence_raw          DECIMAL(5,4) NOT NULL,
confidence_adjusted     DECIMAL(5,4) NOT NULL,
confidence_adjustment_log JSONB,
entry_price             DECIMAL(12,5),
stop_loss               DECIMAL(12,5),
take_profit             DECIMAL(12,5),
summary                 TEXT,
reasoning               TEXT,
indicators_snapshot     JSONB,
timeframe_scores        JSONB,
key_levels              JSONB,
news_context            JSONB,
session                 TEXT,
spread_pips             DECIMAL(6,2),
executed                BOOLEAN NOT NULL DEFAULT FALSE,
rejection_reason        TEXT,
generation_method       TEXT NOT NULL DEFAULT 'AI',
ai_prompt_hash          TEXT,
created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── trades ─────────────────────────────────────────────────────
CREATE TABLE trades (
id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id          UUID NOT NULL REFERENCES accounts(id),
signal_id           UUID REFERENCES signals(id),
broker_trade_id     TEXT,
pair                TEXT NOT NULL,
direction           TEXT NOT NULL CHECK (direction IN ('BUY','SELL')),
mode                TEXT NOT NULL CHECK (mode IN ('PAPER','LIVE')),
entry_price         DECIMAL(12,5) NOT NULL,
exit_price          DECIMAL(12,5),
stop_loss           DECIMAL(12,5) NOT NULL,
take_profit         DECIMAL(12,5) NOT NULL,
position_size       INTEGER NOT NULL,
confidence_score    DECIMAL(5,4),
slippage_pips       DECIMAL(6,2),
pnl_pips            DECIMAL(8,2),
pnl_usd             DECIMAL(12,2),
status              TEXT NOT NULL DEFAULT 'OPEN'
CHECK (status IN ('OPEN','CLOSED','CANCELLED')),
exit_reason         TEXT CHECK (exit_reason IN
('SL_HIT','TP_HIT','AI_CLOSE','MANUAL','EMERGENCY','UNKNOWN')),
outcome             TEXT CHECK (outcome IN ('WIN','LOSS','BREAKEVEN')),
session             TEXT,
opened_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
closed_at           TIMESTAMPTZ,
duration_minutes    INTEGER
);

-- ── risk_events ─────────────────────────────────────────────────
CREATE TABLE risk_events (
id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id  UUID REFERENCES accounts(id),
signal_id   UUID REFERENCES signals(id),
event_type  TEXT NOT NULL,
detail      TEXT,
risk_state  TEXT,
created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── system_state ────────────────────────────────────────────────
CREATE TABLE system_state (
id                          TEXT PRIMARY KEY DEFAULT 'singleton',
risk_state                  TEXT NOT NULL DEFAULT 'NORMAL',
open_trades                 JSONB NOT NULL DEFAULT '[]',
pending_orders              JSONB NOT NULL DEFAULT '[]',
daily_pnl_usd               DECIMAL(12,2) NOT NULL DEFAULT 0,
weekly_pnl_usd              DECIMAL(12,2) NOT NULL DEFAULT 0,
daily_opening_balance       DECIMAL(12,2),
weekly_opening_balance      DECIMAL(12,2),
daily_trade_count           INTEGER NOT NULL DEFAULT 0,
consecutive_losses          INTEGER NOT NULL DEFAULT 0,
circuit_breaker_state       TEXT NOT NULL DEFAULT 'CLOSED',
circuit_breaker_failures    INTEGER NOT NULL DEFAULT 0,
last_signal_time            JSONB NOT NULL DEFAULT '{}',
confidence_threshold_override DECIMAL(5,4),
is_primary_instance         BOOLEAN NOT NULL DEFAULT FALSE,
instance_id                 TEXT,
lock_expires_at             TIMESTAMPTZ,
updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO system_state (id) VALUES ('singleton') ON CONFLICT DO NOTHING;

-- ── performance_snapshots ───────────────────────────────────────
CREATE TABLE performance_snapshots (
id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id          UUID NOT NULL REFERENCES accounts(id),
date                DATE NOT NULL,
starting_balance    DECIMAL(12,2) NOT NULL,
ending_balance      DECIMAL(12,2) NOT NULL,
total_trades        INTEGER NOT NULL DEFAULT 0,
wins                INTEGER NOT NULL DEFAULT 0,
losses              INTEGER NOT NULL DEFAULT 0,
breakevens          INTEGER NOT NULL DEFAULT 0,
win_rate            DECIMAL(5,4),
profit_factor       DECIMAL(8,4),
max_drawdown_pct    DECIMAL(5,4),
total_pnl_usd       DECIMAL(12,2),
UNIQUE (account_id, date)
);

-- ── execution_log ───────────────────────────────────────────────
CREATE TABLE execution_log (
id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id      UUID REFERENCES accounts(id),
endpoint        TEXT NOT NULL,
method          TEXT NOT NULL,
request_ref     TEXT,
response_code   INTEGER,
latency_ms      INTEGER,
error_message   TEXT,
created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── alerts_log ──────────────────────────────────────────────────
CREATE TABLE alerts_log (
id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id  UUID REFERENCES accounts(id),
level       TEXT NOT NULL,
message     TEXT NOT NULL,
channel     TEXT NOT NULL,
delivered   BOOLEAN DEFAULT TRUE,
created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

## 9.2 002_add_indexes.sql
-- Performance indexes for all hot query paths
CREATE INDEX idx_trades_account_status   ON trades(account_id, status);
CREATE INDEX idx_trades_account_opened   ON trades(account_id, opened_at DESC);
CREATE INDEX idx_trades_account_pair     ON trades(account_id, pair, opened_at DESC);
CREATE INDEX idx_trades_account_outcome  ON trades(account_id, outcome, opened_at);
CREATE INDEX idx_signals_account_created ON signals(account_id, created_at DESC);
CREATE INDEX idx_signals_pair_executed   ON signals(account_id, pair, executed);
CREATE INDEX idx_risk_events_created     ON risk_events(account_id, created_at DESC);
CREATE INDEX idx_execution_log_created   ON execution_log(account_id, created_at DESC);
CREATE INDEX idx_perf_account_date       ON performance_snapshots(account_id, date DESC);
CREATE INDEX idx_alerts_created          ON alerts_log(account_id, created_at DESC);

## 9.3 003_add_rls_policies.sql
-- Enable RLS on all tables
ALTER TABLE accounts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals             ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades              ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_events         ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_log       ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts_log          ENABLE ROW LEVEL SECURITY;

-- Service role bypasses all RLS (backend uses service role key)
-- Anon/authenticated roles are restricted to their own data
-- Phase 0: single user — these policies are future-proof for multi-tenant

CREATE POLICY "user_own_data" ON trades
FOR ALL USING (account_id::text = auth.uid()::text);

CREATE POLICY "user_own_signals" ON signals
FOR ALL USING (account_id::text = auth.uid()::text);

CREATE POLICY "user_own_risk_events" ON risk_events
FOR SELECT USING (account_id::text = auth.uid()::text);

CREATE POLICY "user_own_alerts" ON alerts_log
FOR SELECT USING (account_id::text = auth.uid()::text);

# 10. Utility Modules
## 10.1 utils/pip_math.py
from decimal import Decimal

# Pip sizes per currency pair
PIP_SIZE: dict[str, Decimal] = {
"EUR_USD": Decimal("0.0001"),
"GBP_USD": Decimal("0.0001"),
"USD_JPY": Decimal("0.01"),
"EUR_JPY": Decimal("0.01"),
"GBP_JPY": Decimal("0.01"),
}
DEFAULT_PIP = Decimal("0.0001")

# Pip value per 1 unit for USD-denominated accounts
# EUR/USD & GBP/USD: 1 pip = $0.0001 per unit
# USD/JPY: 1 pip = 0.01/rate per unit (approximate)

def pip_size(pair: str) -> Decimal:
return PIP_SIZE.get(pair, DEFAULT_PIP)

def pips_between(price_a: Decimal, price_b: Decimal, pair: str) -> Decimal:
"""Calculate absolute pip difference between two prices."""
return abs(price_a - price_b) / pip_size(pair)

def pip_value_per_unit(pair: str, current_rate: Decimal) -> Decimal:
"""USD value of 1 pip movement for 1 unit of the pair."""
if pair.endswith("_USD"):
# Quote currency is USD: pip value = pip_size
return pip_size(pair)
elif pair.startswith("USD_"):
# Base currency is USD: pip value = pip_size / rate
return pip_size(pair) / current_rate
else:
# Cross pair: approximate via USD rate (simplified for Phase 0)
return pip_size(pair)

def calculate_position_size(
balance: Decimal,
risk_pct: Decimal,
sl_pips: Decimal,
pair: str,
current_rate: Decimal,
) -> tuple[int, Decimal]:
"""
Returns (units: int, risk_amount_usd: Decimal).
Rounds DOWN to nearest 1000 units (micro lot).
"""
risk_usd    = balance * risk_pct
pv_per_unit = pip_value_per_unit(pair, current_rate)
if sl_pips == 0 or pv_per_unit == 0:
return 0, Decimal("0")
raw_units   = risk_usd / (sl_pips * pv_per_unit)
units       = int(raw_units / 1000) * 1000  # Floor to micro lot
actual_risk = units * sl_pips * pv_per_unit
return units, actual_risk

## 10.2 utils/time_utils.py
from datetime import datetime, timezone, time
from ..core.enums import Session

# All times in UTC
LONDON_OPEN  = time(7, 0)    # 08:00 BST = 07:00 UTC
LONDON_CLOSE = time(16, 0)   # 17:00 BST = 16:00 UTC
NY_OPEN      = time(13, 0)   # 09:00 EST = 13:00 UTC (summer)
NY_CLOSE     = time(21, 0)   # 17:00 EST = 21:00 UTC
TOKYO_OPEN   = time(0, 0)
TOKYO_CLOSE  = time(6, 0)


def get_current_session(dt: datetime | None = None) -> Session:
"""Determine which forex trading session is currently active."""
now = (dt or datetime.now(timezone.utc)).time()

in_london = LONDON_OPEN <= now < LONDON_CLOSE
in_ny     = NY_OPEN <= now < NY_CLOSE
in_tokyo  = now >= TOKYO_OPEN and now < TOKYO_CLOSE

if in_london and in_ny:
return Session.OVERLAP
elif in_london:
return Session.LONDON
elif in_ny:
return Session.NEW_YORK
elif in_tokyo:
return Session.TOKYO
return Session.OTHER


def is_market_open(dt: datetime | None = None) -> bool:
"""Forex market is closed Saturday + most of Sunday."""
now = dt or datetime.now(timezone.utc)
weekday = now.weekday()  # 0=Monday, 5=Saturday, 6=Sunday
if weekday == 5:  # Saturday always closed
return False
if weekday == 6 and now.time() < time(21, 0):  # Sunday before NY open
return False
if weekday == 4 and now.time() >= time(21, 0):  # Friday after NY close
return False
return True

# 11. Main Entry Point
## 11.1 main.py — OrchestratorService
"""
Lumitrade — Main entry point.
Run via: python -m lumitrade.main
Managed by Supervisord in production.
"""
import asyncio
import signal
import sys
from .infrastructure.secure_logger import configure_logging, get_logger
from .infrastructure.db import DatabaseClient
from .infrastructure.oanda_client import OandaClient, OandaTradingClient
from .infrastructure.alert_service import AlertService
from .infrastructure.watchdog import Watchdog
from .state.manager import StateManager
from .state.lock import DistributedLock
from .data_engine.engine import DataEngine
from .ai_brain.scanner import SignalScanner
from .risk_engine.engine import RiskEngine
from .execution_engine.engine import ExecutionEngine
from .config import config

configure_logging()
logger = get_logger("orchestrator")


class OrchestratorService:
"""Top-level coordinator for all Lumitrade components."""

def __init__(self):
self._shutdown = asyncio.Event()
self._tasks: list[asyncio.Task] = []

# Infrastructure
self.db           = DatabaseClient()
self.oanda        = OandaClient()
self.oanda_trade  = OandaTradingClient()
self.alerts       = AlertService(self.db)
self.lock         = DistributedLock(self.db)

# Core services
self.state    = StateManager(self.db, self.oanda)
self.data_eng = DataEngine(self.oanda, self.db)
self.scanner  = SignalScanner(self.data_eng, self.db, self.alerts)
self.risk_eng = RiskEngine(self.state, self.db)
self.exec_eng = ExecutionEngine(
self.oanda_trade, self.state, self.db, self.alerts
)
self.watchdog = Watchdog(self.state, self.alerts)

async def startup(self):
"""Full startup sequence — must complete before trading begins."""
logger.info("lumitrade_starting", instance_id=config.instance_id)

# 1. Connect database
await self.db.connect()
logger.info("database_connected")

# 2. Restore persisted system state
await self.state.restore()
logger.info("state_restored", risk_state=self.state.current.risk_state.value)

# 3. Try to acquire primary lock
is_primary = await self.lock.acquire(config.instance_id)
logger.info("lock_status", is_primary=is_primary)

# 4. Validate OANDA connection
account = await self.oanda.get_account_summary()
logger.info("oanda_connected", balance=account.get("balance"))

# 5. Start background tasks
self._tasks = [
asyncio.create_task(self.data_eng.stream_task(config.pairs),
name="price_stream"),
asyncio.create_task(self.scanner.scan_loop(),
name="signal_scan"),
asyncio.create_task(self.exec_eng.position_monitor(),
name="position_monitor"),
asyncio.create_task(self.state.persist_loop(),
name="state_persist"),
asyncio.create_task(self.lock.renew_loop(config.instance_id),
name="heartbeat"),
asyncio.create_task(self.watchdog.run(),
name="watchdog"),
]
logger.info("lumitrade_running", mode=config.trading_mode)
await self.alerts.send_info(
f"Lumitrade started ({config.trading_mode} mode) on {config.instance_id}"
)

async def shutdown(self, reason: str = "SIGTERM"):
"""Graceful shutdown — waits for in-flight orders, persists state."""
logger.info("lumitrade_shutting_down", reason=reason)
self._shutdown.set()

# Cancel background tasks
for task in self._tasks:
task.cancel()
await asyncio.gather(*self._tasks, return_exceptions=True)

# Persist final state
await self.state.save()
await self.lock.release(config.instance_id)
await self.oanda.close()
logger.info("lumitrade_stopped")

async def run(self):
loop = asyncio.get_event_loop()
for sig in (signal.SIGTERM, signal.SIGINT):
loop.add_signal_handler(
sig, lambda: asyncio.create_task(self.shutdown(sig.name))
)
await self.startup()
await self._shutdown.wait()


if __name__ == "__main__":
orchestrator = OrchestratorService()
try:
asyncio.run(orchestrator.run())
except KeyboardInterrupt:
pass
sys.exit(0)

# 12. Testing Patterns & Examples
## 12.1 Unit Test Pattern — AI Validator
# tests/unit/test_ai_validator.py
import pytest
from decimal import Decimal
from lumitrade.ai_brain.validator import AIOutputValidator

@pytest.fixture
def validator():
return AIOutputValidator()

VALID_BUY = {
"action": "BUY", "confidence": 0.82,
"entry_price": 1.08430, "stop_loss": 1.08230,
"take_profit": 1.08730,
"summary": "EUR/USD shows bullish confluence across all timeframes.",
"reasoning": "H4 shows price above EMA 200 with RSI 58 maintaining bullish momentum. " * 3,
"timeframe_h4_score": 0.85, "timeframe_h1_score": 0.78,
"timeframe_m15_score": 0.71, "key_levels": [1.0830, 1.0800],
"invalidation_level": 1.0810, "expected_duration": "INTRADAY"
}

def test_accepts_valid_buy_signal(validator):
result = validator.validate(
__import__("json").dumps(VALID_BUY), Decimal("1.08435")
)
assert result.passed

def test_rejects_missing_confidence(validator):
data = {**VALID_BUY}
del data["confidence"]
result = validator.validate(
__import__("json").dumps(data), Decimal("1.08435")
)
assert not result.passed
assert "confidence" in result.reason

def test_rejects_buy_sl_above_entry(validator):
data = {**VALID_BUY, "stop_loss": 1.08600}  # Above entry
result = validator.validate(
__import__("json").dumps(data), Decimal("1.08435")
)
assert not result.passed
assert "SL" in result.reason

def test_rejects_rr_below_1_5(validator):
# Entry 1.0843, SL 1.0800 (43 pips), TP 1.0880 (37 pips) = 0.86 RR
data = {**VALID_BUY, "stop_loss": 1.08000, "take_profit": 1.08800}
result = validator.validate(
__import__("json").dumps(data), Decimal("1.08435")
)
assert not result.passed
assert "RR" in result.reason

def test_rejects_entry_far_from_live_price(validator):
data = {**VALID_BUY, "entry_price": 1.09500}  # 1% away
result = validator.validate(
__import__("json").dumps(data), Decimal("1.08435")
)
assert not result.passed
assert "deviates" in result.reason

## 12.2 Async Test Pattern — Risk Engine
# tests/unit/test_risk_engine.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone
from lumitrade.risk_engine.engine import RiskEngine
from lumitrade.core.enums import Action, RiskState, Session, TradeDuration, GenerationMethod
from lumitrade.core.models import SignalProposal, RiskRejection, ApprovedOrder


@pytest.fixture
def mock_state_manager():
from lumitrade.state.manager import StateManager
from lumitrade.core.enums import CircuitBreakerState
state = MagicMock()
sys_state = MagicMock()
sys_state.risk_state = RiskState.NORMAL
sys_state.open_trades = []
sys_state.last_signal_time = {}
sys_state.confidence_threshold_override = None
sys_state.consecutive_losses = 0
state.get = AsyncMock(return_value=sys_state)
return state


@pytest.fixture
def valid_proposal():
return SignalProposal(
signal_id=uuid4(), pair="EUR_USD",
action=Action.BUY,
confidence_raw=Decimal("0.82"),
confidence_adjusted=Decimal("0.80"),
confidence_adjustment_log={},
entry_price=Decimal("1.08430"),
stop_loss=Decimal("1.08230"),
take_profit=Decimal("1.08830"),
summary="Test signal", reasoning="Test reasoning " * 5,
timeframe_scores={}, indicators_snapshot={},
key_levels=[], invalidation_level=Decimal("1.0810"),
expected_duration=TradeDuration.INTRADAY,
generation_method=GenerationMethod.AI,
session=Session.OVERLAP, spread_pips=Decimal("1.2"),
news_context=[], ai_prompt_hash="abc123",
created_at=datetime.now(timezone.utc),
)


@pytest.mark.asyncio
async def test_approves_valid_signal(mock_state_manager, valid_proposal):
db = AsyncMock()
engine = RiskEngine(mock_state_manager, db)
engine.guard.is_blackout = AsyncMock(return_value=False)
result = await engine.evaluate(valid_proposal, Decimal("300"))
assert isinstance(result, ApprovedOrder)

@pytest.mark.asyncio
async def test_rejects_when_daily_limit_hit(mock_state_manager, valid_proposal):
mock_state_manager.get.return_value.risk_state = RiskState.DAILY_LIMIT
db = AsyncMock()
engine = RiskEngine(mock_state_manager, db)
result = await engine.evaluate(valid_proposal, Decimal("300"))
assert isinstance(result, RiskRejection)
assert result.rule_violated == "RISK_STATE"



END OF DOCUMENT
Lumitrade Backend Developer Specification v1.0  |  Confidential
Next Document: Frontend Developer Specification (Role 4)





LUMITRADE
Backend Developer Specification

ROLE 3 — SENIOR BACKEND DEVELOPER
All original Python modules + 15 future feature stubs
Version 2.0  |  Includes future feature foundations
Date: March 21, 2026




# 1–12. All Original BDS Sections
All original Backend Developer Specification content is unchanged: development standards, requirements.txt, core models, config system, data engine, AI brain, risk engine, execution engine, infrastructure, database migrations, utilities, main entry point, and testing patterns.
Reference  Original BDS v1.0 is the authoritative source for all Phase 0 Python implementation. This document adds Section 13 only.

# 13. Future Feature Stub Implementations
Every stub below follows the same pattern: complete class with all methods defined, every method body is a single comment explaining exactly what Phase 2/3 should implement, and a safe return value that causes zero side effects.

## 13.1 regime_classifier.py — Feature F-02
# data_engine/regime_classifier.py
from decimal import Decimal
from ..core.enums import MarketRegime
from ..core.models import IndicatorSet, Candle
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

class RegimeClassifier:
"""
Classifies current market regime from indicators and price action.
Phase 0: Always returns UNKNOWN (no behavioral effect).
Phase 2: Implement classify() with full EMA/ATR logic.
"""

def classify(self, indicators: IndicatorSet,
candles_h4: list[Candle]) -> MarketRegime:
"""
TODO Phase 2:
TRENDING:  abs(ema_20 - ema_200) > 1.5 * atr_14
AND price > ema_50 (for BULL) or < ema_50 (for BEAR)
RANGING:   abs(ema_20 - ema_200) < 0.5 * atr_14
AND last 20 H4 closes oscillating around ema_50
HIGH_VOL:  atr_14 > 2.0 * rolling_30day_avg_atr
LOW_LIQ:   spread_pips > 4.0 OR outside market hours
"""
return MarketRegime.UNKNOWN  # Phase 0 safe default

## 13.2 consensus_engine.py — Feature F-01
# ai_brain/consensus_engine.py
from dataclasses import dataclass
from decimal import Decimal
from ..core.enums import Action
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

@dataclass
class ModelVote:
model_id: str
action: Action
confidence: Decimal
raw_response: dict

class ConsensusEngine:
"""
Runs multiple AI models and produces a consensus signal.
Phase 0: Passes through single Claude result unchanged.
Phase 2: Add OpenAI call, implement voting logic.
"""

def __init__(self, models: list[str] = None):
self.models = models or ["claude-sonnet"]

async def get_consensus(self, prompt: str,
primary_result: dict) -> dict:
"""
TODO Phase 2:
1. Call each additional model with same prompt
2. Collect ModelVote from each
3. Apply voting: 2/3 agree → execute, all disagree → HOLD
4. Unanimous agreement → increase confidence by 0.10
5. Return winning signal or HOLD
"""
return primary_result  # Phase 0: single model passthrough

## 13.3 sentiment_analyzer.py — Feature F-03
# ai_brain/sentiment_analyzer.py
from ..core.enums import CurrencySentiment
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

class SentimentAnalyzer:
"""
Analyzes financial news to produce per-currency sentiment scores.
Phase 0: Returns NEUTRAL for all currencies (no behavioral effect).
Phase 2: Fetch news via API, call Claude to analyze, return scores.
"""

async def analyze(self, currencies: list[str]) -> dict[str, CurrencySentiment]:
"""
TODO Phase 2:
1. Fetch headlines for each currency from NewsAPI/Benzinga
2. Call Claude with headlines: "Analyze sentiment for {currency}"
3. Parse response: BULLISH / BEARISH / NEUTRAL + confidence
4. Cache result for 30 minutes (news doesnt change that fast)
5. Return dict: {"EUR": BEARISH, "USD": NEUTRAL, "GBP": BULLISH}
"""),
return {c: CurrencySentiment.NEUTRAL for c in currencies}

## 13.4 correlation_matrix.py — Feature F-04
# risk_engine/correlation_matrix.py
from decimal import Decimal
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

class CorrelationMatrix:
"""
Tracks rolling correlation between currency pairs.
Phase 0: Returns 0.0 correlation for all pairs (no effect on sizing).
Phase 2: Compute from 30-day rolling price returns.
"""

def get_correlation(self, pair_a: str, pair_b: str) -> Decimal:
"""
TODO Phase 2:
1. Fetch last 30 days of daily close prices for both pairs
2. Compute Pearson correlation coefficient
3. Cache result — update daily
4. Return correlation: -1.0 to 1.0
Known correlations: EUR_USD/GBP_USD ~0.87, EUR_USD/USD_JPY ~-0.72
"""
return Decimal("0.0")  # Phase 0: no correlation adjustment

def get_position_size_multiplier(self,
open_pairs: list[str],
new_pair: str) -> Decimal:
"""
TODO Phase 2:
For each open position, compute correlation with new_pair.
If max correlation > 0.90: return Decimal("0.25")
If max correlation > 0.80: return Decimal("0.50")
Otherwise: return Decimal("1.0") (no reduction)
"""
return Decimal("1.0")  # Phase 0: full size always

## 13.5 journal_generator.py — Feature F-05
# analytics/journal_generator.py
from datetime import datetime, timezone, timedelta
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

MIN_TRADES_FOR_JOURNAL = 5

class JournalGenerator:
"""
Generates weekly AI trading journals.
Phase 0: Does nothing (insufficient data).
Phase 2: Full journal generation + email delivery.
"""

def __init__(self, db: DatabaseClient):
self.db = db

async def generate_weekly(self, account_id: str) -> str | None:
"""
TODO Phase 2:
1. Fetch all trades from last 7 days
2. If < MIN_TRADES: return None (skip this week)
3. Assemble trade context: best trade, worst trade,
session breakdown, win rate vs prior week
4. Call Claude with context + journal prompt
5. Store result in trade_journals table
6. Send via SendGrid to operator email
7. Return journal text
"""
logger.debug("journal_skipped_phase_0")
return None

## 13.6 risk_of_ruin.py — Feature F-12
# analytics/risk_of_ruin.py
from decimal import Decimal
from dataclasses import dataclass
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

@dataclass
class RuinAnalysis:
prob_loss_25pct: Decimal
prob_loss_50pct: Decimal
prob_loss_100pct: Decimal
edge: Decimal
status: str  # SAFE | WARNING | DANGER
sample_size: int
is_sufficient: bool

class RiskOfRuinCalculator:
"""
Calculates probability of account ruin from trade statistics.
Phase 0: Returns insufficient data result.
Phase 2: Full calculation after 20+ trades.
"""),
MIN_SAMPLE = 20

def calculate(self, win_rate: Decimal, avg_win_pips: Decimal,
avg_loss_pips: Decimal, risk_pct: Decimal,
sample_size: int) -> RuinAnalysis:
"""
TODO Phase 2:
edge = (WR * avg_win - LR * avg_loss) / (WR * avg_win + LR * avg_loss)
ror_formula = ((1 - edge) / (1 + edge)) ^ (1 / risk_pct)
Compute for 25%, 50%, 100% capital loss thresholds.
status: SAFE if prob_100pct < 1%, WARNING if < 10%, DANGER if >= 10%
"""
if sample_size < self.MIN_SAMPLE:
return RuinAnalysis(
prob_loss_25pct=Decimal("0"),
prob_loss_50pct=Decimal("0"),
prob_loss_100pct=Decimal("0"),
edge=Decimal("0"),
status="INSUFFICIENT_DATA",
sample_size=sample_size,
is_sufficient=False
)
return RuinAnalysis(  # Stub return for Phase 0
prob_loss_25pct=Decimal("0"),
prob_loss_50pct=Decimal("0"),
prob_loss_100pct=Decimal("0"),
edge=Decimal("0"),
status="INSUFFICIENT_DATA",
sample_size=sample_size,
is_sufficient=False
)

## 13.7 005_future_feature_tables.sql
Add this migration file: database/migrations/005_future_feature_tables.sql

-- Future feature tables. All empty in Phase 0.
-- Populated when features are activated in Phase 2/3/4.
-- No foreign key violations possible: all inserts conditional on feature being active.

CREATE TABLE trade_journals (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
week_start DATE NOT NULL,
content_text TEXT,
best_trade_id UUID REFERENCES trades(id),
worst_trade_id UUID REFERENCES trades(id),
win_rate_vs_prior DECIMAL(5,4),
recommendation TEXT,
generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
UNIQUE(account_id, week_start)
);

CREATE TABLE intelligence_reports (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
week_start DATE NOT NULL,
macro_summary TEXT,
key_levels JSONB,
calendar_preview JSONB,
system_alignment TEXT,
generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE market_regimes (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
pair TEXT NOT NULL,
regime TEXT NOT NULL,
ema_spread DECIMAL(10,5),
atr_ratio DECIMAL(6,3),
detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sentiment_snapshots (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
currencies JSONB NOT NULL,
confidence DECIMAL(4,3),
key_headline TEXT,
fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE coach_conversations (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
session_id TEXT NOT NULL,
messages JSONB NOT NULL DEFAULT '[]',
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE strategies (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
creator_account_id UUID REFERENCES accounts(id),
name TEXT NOT NULL,
description TEXT,
config JSONB NOT NULL,
status TEXT NOT NULL DEFAULT 'DRAFT',
live_since TIMESTAMPTZ,
stripe_product_id TEXT,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE strategy_subscriptions (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
strategy_id UUID REFERENCES strategies(id),
subscriber_account_id UUID REFERENCES accounts(id),
stripe_subscription_id TEXT,
started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
cancelled_at TIMESTAMPTZ
);

CREATE TABLE copy_relationships (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
leader_account_id UUID REFERENCES accounts(id),
follower_account_id UUID REFERENCES accounts(id),
size_multiplier DECIMAL(4,2) NOT NULL DEFAULT 1.0,
active BOOLEAN NOT NULL DEFAULT TRUE,
started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE backtest_runs (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
config JSONB NOT NULL,
date_from DATE, date_to DATE,
status TEXT NOT NULL DEFAULT 'PENDING',
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE backtest_results (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
run_id UUID REFERENCES backtest_runs(id),
trades_count INT, win_rate DECIMAL(5,4),
profit_factor DECIMAL(8,4), max_drawdown_pct DECIMAL(5,4),
total_pips DECIMAL(10,2), sharpe_ratio DECIMAL(8,4)
);

CREATE TABLE api_keys (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
key_hash TEXT NOT NULL UNIQUE,
label TEXT,
last_used_at TIMESTAMPTZ,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
revoked_at TIMESTAMPTZ
);

CREATE TABLE webhook_endpoints (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id UUID REFERENCES accounts(id),
url TEXT NOT NULL,
events JSONB NOT NULL DEFAULT '["signal", "trade"]',
secret_hash TEXT,
active BOOLEAN NOT NULL DEFAULT TRUE,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE fund_accounts (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
investor_name TEXT NOT NULL,
amount_usd DECIMAL(14,2) NOT NULL,
joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
current_value DECIMAL(14,2),
performance_fee_paid DECIMAL(14,2) NOT NULL DEFAULT 0
);


# 14. Self-Improvement Foundations
These foundations are built during Phase 0 alongside the main system. They do nothing until sufficient trade data exists, then activate automatically.
## 14.1 performance_insights Table (Migration 004)
-- database/migrations/004_performance_insights.sql
CREATE TABLE performance_insights (
id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
account_id      UUID REFERENCES accounts(id),
generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
insight_type    TEXT NOT NULL,
-- SESSION_PERFORMANCE | PAIR_WIN_RATE | INDICATOR_ACCURACY | PROMPT_PATTERN
scope           TEXT NOT NULL,
-- EUR_USD | LONDON | RSI_OVERSOLD | GBP_USD_TOKYO
finding         TEXT NOT NULL,
data            JSONB,
recommendation  TEXT,
applied         BOOLEAN NOT NULL DEFAULT FALSE,
confidence      DECIMAL(4,3),
expires_at      TIMESTAMPTZ
);
CREATE INDEX idx_insights_account_scope
ON performance_insights(account_id, scope, applied);
## 14.2 PerformanceAnalyzer Stub
# analytics/performance_analyzer.py
class PerformanceAnalyzer:
"""
Phase 0: All methods are stubs — analyze() does nothing.
Phase 2: Implement analysis methods one by one.
Phase 3: Add prompt evolution and rule updating.
"""
MIN_TRADES = 50
ANALYZE_EVERY = 10

def __init__(self, db: DatabaseClient):
self.db = db

async def analyze(self, account_id: str) -> None:
# Phase 0: does nothing
# TODO Phase 2: uncomment these one by one:
# await self._analyze_session_performance(account_id)
# await self._analyze_pair_performance(account_id)
# await self._analyze_indicator_accuracy(account_id)
# await self._analyze_confidence_calibration(account_id)
# await self._analyze_prompt_patterns(account_id)
# TODO Phase 3: uncomment after Phase 2 stable:
# await self._evolve_prompt_instructions(account_id)
# await self._update_session_filters(account_id)
# await self._update_confidence_thresholds(account_id)
pass

async def _analyze_session_performance(self, account_id: str): pass
async def _analyze_pair_performance(self, account_id: str): pass
async def _analyze_indicator_accuracy(self, account_id: str): pass
async def _analyze_confidence_calibration(self, account_id: str): pass
async def _analyze_prompt_patterns(self, account_id: str): pass
async def _evolve_prompt_instructions(self, account_id: str): pass
async def _update_session_filters(self, account_id: str): pass
async def _update_confidence_thresholds(self, account_id: str): pass
## 14.3 Post-Trade Hook in ExecutionEngine
# Add to execution_engine/engine.py — end of _close_trade()
await self._trigger_insight_analysis(trade)

async def _trigger_insight_analysis(self, trade: Trade):
MIN_TRADES = 50
EVERY_N = 10
try:
count = await self.db.count('trades',
{'account_id': trade.account_id, 'status': 'CLOSED'})
if count < MIN_TRADES:
return  # Silent — not enough data yet
if count % EVERY_N == 0:
asyncio.create_task(
self.performance_analyzer.analyze(trade.account_id))
except Exception as e:
logger.warning('insight_trigger_failed', error=str(e))
## 14.4 Performance Insights Prompt Slot
# Add to ai_brain/prompt_builder.py
async def _get_performance_insights(self, pair: str) -> str:
try:
insights = await self.db.select(
'performance_insights',
{'account_id': self.account_id, 'scope': pair, 'applied': False},
limit=3, order='confidence')
if not insights:
return '  No performance insights yet.'
lines = [f'Recent patterns for {pair}:']
for i in insights:
lines.append(f'  - {i["finding"]}')
if i.get('recommendation'):
lines.append(f'    Adjustment: {i["recommendation"]}')
return chr(10).join(lines)
except Exception:
return '  No performance insights available.'

# Add to build_prompt() sections list:
'=== PERFORMANCE INSIGHTS ==='
await self._get_performance_insights(snapshot.pair)

# 15. Adaptive Position Sizing Foundations
Allows Claude to recommend position size based on recent performance. All components are Phase 0 stubs that fall back to standard confidence-based sizing until 20+ trades exist.
## 15.1 PerformanceContext Dataclass
# Add to core/models.py
@dataclass(frozen=True)
class PerformanceContext:
last_10_win_rate:           Decimal = Decimal('0')
last_10_avg_pips:           Decimal = Decimal('0')
consecutive_wins:           int     = 0
consecutive_losses:         int     = 0
current_drawdown_from_peak: Decimal = Decimal('0')
account_growth_this_week:   Decimal = Decimal('0')
market_volatility:          str     = 'NORMAL'
trend_strength:             str     = 'MODERATE'
sample_size:                int     = 0
is_sufficient_data:         bool    = False

# Also add to MarketSnapshot:
performance_context: PerformanceContext = field(default_factory=PerformanceContext)
## 15.2 PerformanceContextBuilder Stub
# analytics/performance_context_builder.py
class PerformanceContextBuilder:
MIN_TRADES = 20

def __init__(self, db: DatabaseClient):
self.db = db

async def build(self, account_id: str, pair: str,
current_atr: Decimal) -> PerformanceContext:
try:
return await self._build_context(account_id, pair, current_atr)
except Exception as e:
logger.warning('perf_context_failed', error=str(e))
return PerformanceContext()  # Safe defaults

async def _build_context(self, account_id, pair, atr):
# TODO Phase 2: implement full calculation
# Fetch last 10 trades, compute win_rate, avg_pips,
# consecutive streaks, weekly growth, volatility from ATR
return PerformanceContext()  # Phase 0: always returns defaults
## 15.3 recommended_risk_pct in AI Schema
# Add to SYSTEM_PROMPT in ai_brain/prompt_builder.py
# REQUIRED JSON SCHEMA — add these two fields:
"recommended_risk_pct": 0.0025-0.02,  # 0.25% to 2.0%
"risk_reasoning": "1-2 sentences explaining position size recommendation"

# Add to ai_brain/validator.py — optional fields with safe defaults:
OPTIONAL_FIELDS = {
'recommended_risk_pct': Decimal('0.01'),
'risk_reasoning': 'No risk reasoning provided.',
}
# If missing: use default. If out of range: clamp. Never reject signal.
## 15.4 Adaptive Risk Engine Method
# Replace _confidence_to_risk_pct() in risk_engine/engine.py
def _determine_risk_pct(self, proposal: SignalProposal,
has_sufficient_data: bool) -> Decimal:
HARD_MIN = Decimal('0.0025')  # 0.25% absolute minimum
HARD_MAX = Decimal('0.02')    # 2.00% absolute maximum

# Standard confidence-based sizing (always available)
if proposal.confidence_adjusted >= Decimal('0.90'):
standard = Decimal('0.02')
elif proposal.confidence_adjusted >= Decimal('0.80'):
standard = Decimal('0.01')
else:
standard = Decimal('0.005')

# Use AI recommendation only when sufficient data exists
if (has_sufficient_data
and hasattr(proposal, 'recommended_risk_pct')
and proposal.recommended_risk_pct):
ai_rec = Decimal(str(proposal.recommended_risk_pct))
final = max(HARD_MIN, min(HARD_MAX, ai_rec))
return final  # Adaptive sizing active

return standard  # Phase 0: standard sizing

# 16. Subagent Stub Implementations
All 5 subagent stubs are created during Phase 0. Each is importable and callable. All return safe defaults in Phase 0. None affect the trading pipeline until activated in Phase 2/3.
## 16.1 base_agent.py
# subagents/base_agent.py
import asyncio
from abc import ABC, abstractmethod
from anthropic import AsyncAnthropic
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

class BaseSubagent(ABC):
model = "claude-sonnet-4-20250514"
max_tokens = 1000
timeout_seconds = 30

def __init__(self, config):
self.config = config
self._client = AsyncAnthropic(api_key=config.anthropic_api_key)

@abstractmethod
async def run(self, context: dict) -> dict:
"""Main entry. Must return dict. Never raise."""
...

async def _call_claude(self, system: str, user: str) -> str:
try:
resp = await asyncio.wait_for(
self._client.messages.create(
model=self.model,
max_tokens=self.max_tokens,
system=system,
messages=[{"role": "user", "content": user}]
), timeout=self.timeout_seconds)
return resp.content[0].text
except Exception as e:
logger.warning("subagent_failed",
agent=self.__class__.__name__, error=str(e))
return ""
## 16.2 market_analyst.py — SA-01
# subagents/market_analyst.py
from .base_agent import BaseSubagent
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

ANALYST_SYSTEM = """You are a professional forex market analyst.
You receive raw OHLCV data and indicator values for one currency pair.
Your job is to write a clear, structured market briefing (200-400 words)
that a signal decision AI will use to decide whether to trade.

Cover: trend direction on each timeframe, key support/resistance levels,
indicator readings and what they mean, spread and session context,
and a one-sentence overall bias (bullish/bearish/neutral).

Be specific with numbers. Do not recommend action — only analyze."""

class MarketAnalystAgent(BaseSubagent):
"""
SA-01: Produces structured market briefing before signal decision.
Phase 0: Returns empty string (signal decision uses raw data directly).
Phase 2: Returns full briefing — wired into prompt_builder.py.
"""

async def run(self, context: dict) -> dict:
"""
TODO Phase 2:
1. Format snapshot data into analyst prompt
2. Call _call_claude(ANALYST_SYSTEM, formatted_data)
3. Return {"briefing": analyst_text}
4. Store briefing in analyst_briefings table
5. Wire into prompt_builder: add === ANALYST BRIEFING === section
"""
logger.debug("market_analyst_skipped_phase_0")
return {"briefing": ""}  # Phase 0: empty — no behavioral effect
## 16.3 post_trade_analyst.py — SA-02
# subagents/post_trade_analyst.py
from .base_agent import BaseSubagent
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

POST_TRADE_SYSTEM = """You are a professional forex trading analyst.
You receive a completed trade record with the AI reasoning that generated it,
the indicator values at entry, and the outcome.

Your job is to produce ONE specific finding about why this trade won or lost,
and ONE actionable recommendation for the system.

Be brutally honest. If the trade lost due to bad timing, say so.
If the indicators were correct but news moved the market, say so.

Output JSON: {"finding": "...", "recommendation": "...", "confidence": 0.0-1.0}"""

class PostTradeAnalystAgent(BaseSubagent):
"""
SA-02: Analyzes every closed trade and stores findings.
Phase 0: Silent no-op.
Phase 2: Active after 20+ closed trades. Populates performance_insights.
"""
MIN_TRADES = 20

def __init__(self, config, db: DatabaseClient):
super().__init__(config)
self.db = db

async def run(self, context: dict) -> dict:
"""
TODO Phase 2:
1. Check trade_count >= MIN_TRADES, else return {}
2. Fetch signal reasoning, indicator snapshot, outcome
3. Format into POST_TRADE_SYSTEM prompt
4. Call _call_claude()
5. Parse JSON response
6. Store in performance_insights table with:
insight_type=POST_TRADE_ANALYSIS
scope=pair
finding=finding
recommendation=recommendation
confidence=confidence
7. Return {"finding": ..., "stored": True}
"""
logger.debug("post_trade_analyst_skipped_phase_0")
return {}
## 16.4 risk_monitor.py — SA-03
# subagents/risk_monitor.py
from .base_agent import BaseSubagent
from ..infrastructure.db import DatabaseClient
from ..infrastructure.alert_service import AlertService
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

RISK_MONITOR_SYSTEM = """You are a professional forex risk manager.
You are given an open trading position and current market conditions.

Your job: determine if the original trade thesis still holds.
The original thesis is described by the AI reasoning that opened the trade.

Evaluate: Has price broken the key level that justified the trade?
Has market structure changed against the position?
Are current conditions materially different from entry conditions?

Output JSON: {
"thesis_valid": true/false,
"reasoning": "...",
"recommendation": "HOLD" | "CLOSE_EARLY" | "REDUCE_SIZE",
"urgency": "LOW" | "MEDIUM" | "HIGH"
}"""

class RiskMonitorAgent(BaseSubagent):
"""
SA-03: Checks open position thesis every 30 minutes.
Phase 0: Silent no-op.
Phase 2: Active when RISK_MONITOR_ENABLED=true in config.
"""

def __init__(self, config, db: DatabaseClient, alerts: AlertService):
super().__init__(config)
self.db = db
self.alerts = alerts

async def run(self, context: dict) -> dict:
"""
TODO Phase 2:
1. If no open trades: return {} immediately
2. For each open trade:
a. Fetch original signal reasoning
b. Fetch current market conditions for the pair
c. Format into RISK_MONITOR_SYSTEM prompt
d. Call _call_claude()
e. Parse JSON response
f. Store in risk_monitor_log table
g. If thesis_valid=False AND urgency=HIGH:
- Send WARNING alert immediately
- Surface recommendation on dashboard
h. If urgency=HIGH and recommendation=CLOSE_EARLY:
- Send CRITICAL alert
- Do NOT auto-close (operator decides)
3. Return {"checks": N, "alerts_sent": M}
"""
logger.debug("risk_monitor_skipped_phase_0")
return {}
## 16.5 intelligence_subagent.py — SA-04
# subagents/intelligence_subagent.py
from .base_agent import BaseSubagent
from ..infrastructure.db import DatabaseClient
from ..infrastructure.alert_service import AlertService
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

class IntelligenceSubagent(BaseSubagent):
"""
SA-04: Generates weekly intelligence report via 3 sequential sub-calls.
Phase 0: Silent no-op.
Phase 2: Active when NEWS_API_KEY env var present.
""",

def __init__(self, config, db: DatabaseClient, alerts: AlertService):
super().__init__(config)
self.db = db
self.alerts = alerts

async def run(self, context: dict) -> dict:
"""
TODO Phase 2:
3 sequential Claude calls:
CALL 1 — News Analyst:
Fetch week headlines from NEWS_API for each trading pair currency.
Prompt: "Analyze this week macro news for EUR, USD, GBP, JPY.
What were the 3 most market-moving events? Rate overall
sentiment for each currency: BULLISH/BEARISH/NEUTRAL."
Output: news_summary (dict per currency)

CALL 2 — Performance Analyst:
Fetch last 7 days of trade records.
Prompt: "Analyze these trades. What worked? What failed?
Which session was best? Which pair was best?
One specific recommendation for next week."
Output: performance_summary (text)

CALL 3 — Intelligence Writer:
Combine news_summary + performance_summary.
Prompt: "Write a weekly intelligence report for a forex trader.
Include: macro environment, key levels to watch,
economic calendar preview, system performance,
and how current Lumitrade settings align with macro."
Output: full_report (text)

Store in intelligence_reports table.
Send via SendGrid to operator email.
Store for /intelligence dashboard page.
Return {"report_id": uuid, "word_count": N}
"""
if not getattr(self.config, "news_api_key", None):
logger.debug("intelligence_skipped_no_api_key")
return {}
logger.debug("intelligence_subagent_skipped_phase_0")
return {}
## 16.6 onboarding_agent.py — SA-05
# subagents/onboarding_agent.py
from .base_agent import BaseSubagent
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

ONBOARDING_SYSTEM = """You are Lumitrade's friendly onboarding assistant.
Your job is to guide a new user through setting up their trading configuration.

You ask one question at a time. You are warm, clear, and never use jargon.
Based on their answers, you will recommend appropriate risk settings.

Questions to cover (in order):
1. How much capital are they starting with? ($100-$50,000)
2. Have they traded forex before? (Yes/No)
3. How would they describe their risk tolerance? (Conservative/Moderate/Aggressive)
4. How often do they want to check the dashboard? (Daily/Weekly)

After all answers, recommend settings and ask for confirmation.
Then output a JSON block: {"settings": {...}, "explanation": "..."}"""

class OnboardingAgent(BaseSubagent):
"""
SA-05: Conversational new user onboarding for SaaS.
Phase 0: Silent no-op (single user, no onboarding needed).
Phase 3: Active at SaaS launch.
"""

def __init__(self, config, db: DatabaseClient):
super().__init__(config)
self.db = db

async def run(self, context: dict) -> dict:
"""
TODO Phase 3:
1. Load conversation history from onboarding_sessions table
2. Append new user message
3. Call _call_claude(ONBOARDING_SYSTEM, full_conversation)
4. Append assistant response to history
5. Store updated history in onboarding_sessions
6. If response contains JSON settings block:
a. Parse settings
b. Apply to user account via settings service
c. Mark onboarding as completed
d. Send welcome email
7. Return {"response": assistant_text, "completed": bool}
"""
logger.debug("onboarding_agent_skipped_phase_0")
return {"response": "", "completed": False}
## 16.7 Migration 006: Subagent Tables
-- database/migrations/006_subagent_tables.sql
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
urgency TEXT,
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

-- analyst_briefings index for fast signal lookup
CREATE INDEX idx_briefings_signal ON analyst_briefings(signal_id);
-- risk_monitor index for open trade monitoring
CREATE INDEX idx_risk_monitor_trade ON risk_monitor_log(trade_id, checked_at DESC);

| Attribute | Value |
|---|---|
| Document | Backend Developer Specification (BDS) |
| Preceding | PRD v1.0 + System Architecture Specification v1.0 |
| Role | Senior Backend Developer |
| Runtime | Python 3.11 — asyncio event-driven |
| Primary libraries | aiohttp, pandas-ta, supabase-py, anthropic, httpx, structlog, supervisord |
| Broker | OANDA v20 REST API + Streaming |
| Database | Supabase (PostgreSQL) — async client |
| Deployment target | Railway.app (Docker container) |
| Next Document | Frontend Developer Specification (Role 4) |


| Standard | Requirement |
|---|---|
| Type hints | All function signatures must include type hints. Use Python 3.11 built-in generics (list[str] not List[str]). No untyped functions. |
| Docstrings | All public classes and methods require Google-style docstrings with Args, Returns, Raises sections. |
| Error handling | Every async function must have explicit error handling. No bare except clauses. All exceptions logged with context before re-raising or handling. |
| Async purity | All I/O operations must be async. No blocking calls (requests, time.sleep) in async context. Use httpx.AsyncClient, asyncio.sleep, run_in_executor for blocking ops. |
| Immutability | Dataclasses use frozen=True where values should not change after creation. No mutable default arguments. |
| Constants | All magic numbers and strings defined as module-level constants or loaded from config. No hardcoded values in business logic. |
| Decimal arithmetic | All financial calculations use Python Decimal with explicit precision. No float arithmetic for money values. |
| Logging | Every function uses the module-level logger. Log entry and exit of all significant operations. Always include context (pair, signal_id, trade_id). |


| Attribute | Value |
|---|---|
| Version | 2.0 — all original code + future feature stub implementations |
| New files | 15 stub modules with complete class signatures and TODO comments |
| Migration | New: 005_future_feature_tables.sql with all 12 future tables |
| Behavioral change | Zero — all stubs are silent no-ops in Phase 0 |
