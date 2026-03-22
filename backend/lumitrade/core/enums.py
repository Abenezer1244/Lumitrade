"""Lumitrade domain enums.

All enums inherit from (str, Enum) for JSON-serialisable string values.
Original 12 from the Base Domain Schema (BDS) plus 4 future enums from SAS v2.0.
"""

from enum import Enum


# ---------------------------------------------------------------------------
# BDS enums (12)
# ---------------------------------------------------------------------------


class Action(str, Enum):
    """Signal action recommendation."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Direction(str, Enum):
    """Trade direction (no HOLD -- only executable sides)."""

    BUY = "BUY"
    SELL = "SELL"


class RiskState(str, Enum):
    """Current state of the risk manager."""

    NORMAL = "NORMAL"
    CAUTIOUS = "CAUTIOUS"
    NEWS_BLOCK = "NEWS_BLOCK"
    DAILY_LIMIT = "DAILY_LIMIT"
    WEEKLY_LIMIT = "WEEKLY_LIMIT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    EMERGENCY_HALT = "EMERGENCY_HALT"


class Session(str, Enum):
    """Market session windows."""

    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    OVERLAP = "OVERLAP"
    TOKYO = "TOKYO"
    OTHER = "OTHER"


class TradingMode(str, Enum):
    """Paper vs live execution mode."""

    PAPER = "PAPER"
    LIVE = "LIVE"


class ExitReason(str, Enum):
    """Why a position was closed."""

    SL_HIT = "SL_HIT"
    TP_HIT = "TP_HIT"
    AI_CLOSE = "AI_CLOSE"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"
    UNKNOWN = "UNKNOWN"


class OrderStatus(str, Enum):
    """Lifecycle states of a broker order."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class Outcome(str, Enum):
    """Trade result classification."""

    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


class TradeDuration(str, Enum):
    """Holding-period classification."""

    SCALP = "SCALP"
    INTRADAY = "INTRADAY"
    SWING = "SWING"


class GenerationMethod(str, Enum):
    """How a signal was produced."""

    AI = "AI"
    RULE_BASED = "RULE_BASED"


class NewsImpact(str, Enum):
    """Expected impact level of a news event."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CircuitBreakerState(str, Enum):
    """Circuit breaker finite-state-machine states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


# ---------------------------------------------------------------------------
# SAS v2.0 future enums (4)
# ---------------------------------------------------------------------------


class MarketRegime(str, Enum):
    """Detected market regime for adaptive strategy selection."""

    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    UNKNOWN = "UNKNOWN"


class CurrencySentiment(str, Enum):
    """Aggregate sentiment for a currency."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class AssetClass(str, Enum):
    """Supported tradeable asset classes."""

    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    STOCKS = "STOCKS"
    OPTIONS = "OPTIONS"


class StrategyStatus(str, Enum):
    """Lifecycle status of a trading strategy."""

    DRAFT = "DRAFT"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
