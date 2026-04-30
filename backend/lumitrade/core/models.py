"""
Lumitrade Core Domain Models
=============================
All inter-component data contracts as frozen dataclasses.
Every financial value uses Decimal. All dataclasses are immutable (frozen=True).

Per BDS Section 2.2 + SAS v2.0 Section 14.5 + Addition Set 2A.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from ..utils.pip_math import pip_size as get_pip_size
from .enums import (
    Action,
    CurrencySentiment,
    Direction,
    GenerationMethod,
    MarketRegime,
    NewsImpact,
    OrderStatus,
    Outcome,
    RiskState,
    Session,
    TradeDuration,
    TradingMode,
)

# ── Market Data Models ─────────────────────────────────────────


@dataclass(frozen=True)
class Candle:
    """Single OHLCV candle from OANDA."""

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    complete: bool  # False = current forming candle
    timeframe: str  # "M5", "M15", "H1", "H4", "D"


@dataclass(frozen=True)
class PriceTick:
    """Real-time bid/ask price from OANDA streaming."""

    pair: str
    bid: Decimal
    ask: Decimal
    timestamp: datetime

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / 2

    @property
    def spread_pips(self) -> Decimal:
        return (self.ask - self.bid) / get_pip_size(self.pair)


@dataclass(frozen=True)
class IndicatorSet:
    """Computed technical indicators for a currency pair."""

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
    # ADX for trend strength: <25 = ranging, >25 = trending
    adx_14: Decimal = Decimal("0")

    def to_dict(self) -> dict:
        return {k: str(v) for k, v in self.__dict__.items()}


@dataclass(frozen=True)
class NewsEvent:
    """Economic calendar event."""

    event_id: str
    title: str
    currencies_affected: list[str]  # e.g. ["EUR", "USD"]
    impact: NewsImpact
    scheduled_at: datetime
    minutes_until: int  # negative = already happened


@dataclass(frozen=True)
class DataQuality:
    """Result of data validation pipeline."""

    is_fresh: bool  # Price < 5s old
    spike_detected: bool
    spread_acceptable: bool
    candles_complete: bool  # No gaps detected
    ohlc_valid: bool

    @property
    def is_tradeable(self) -> bool:
        return (
            self.is_fresh
            and not self.spike_detected
            and self.spread_acceptable
            and self.candles_complete
            and self.ohlc_valid
        )


@dataclass(frozen=True)
class AccountContext:
    """OANDA account snapshot for AI prompt context."""

    account_id: str
    balance: Decimal
    equity: Decimal
    margin_used: Decimal
    open_trade_count: int
    daily_pnl: Decimal
    fetched_at: datetime


@dataclass(frozen=True)
class TradeSummary:
    """Recent trade context for AI prompt."""

    pair: str
    direction: Direction
    outcome: Optional[Outcome]
    pnl_pips: Optional[Decimal]
    opened_at: datetime
    closed_at: Optional[datetime]


@dataclass(frozen=True)
class PerformanceContext:
    """
    Recent performance metrics passed to AI for adaptive position sizing.
    Populated from trade history. Empty/default values in Phase 0.
    Per Addition Set 2A.
    """

    last_10_win_rate: Decimal = Decimal("0")
    last_10_avg_pips: Decimal = Decimal("0")
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    current_drawdown_from_peak: Decimal = Decimal("0")
    account_growth_this_week: Decimal = Decimal("0")
    market_volatility: str = "NORMAL"  # LOW | NORMAL | HIGH
    trend_strength: str = "MODERATE"  # WEAK | MODERATE | STRONG
    sample_size: int = 0
    is_sufficient_data: bool = False


@dataclass(frozen=True)
class MarketSnapshot:
    """
    Complete market context assembled by DataEngine for each signal scan.
    Flows from DataEngine -> SignalScanner -> AIBrain.
    """

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
    # Phase 0 defaults — populated when features activate
    candles_d1: list[Candle] = field(default_factory=list)
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    sentiment: dict[str, CurrencySentiment] = field(default_factory=dict)
    ai_models: list[str] = field(default_factory=lambda: ["claude-sonnet"])
    performance_context: PerformanceContext = field(
        default_factory=PerformanceContext
    )


# ── Signal & Order Models ──────────────────────────────────────


@dataclass(frozen=True)
class SignalProposal:
    """
    AI-generated trading signal. Flows from AIBrain -> RiskEngine.
    Contains all information needed for risk evaluation.
    """

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
    # Adaptive sizing fields (optional — safe defaults)
    recommended_risk_pct: Optional[Decimal] = None
    risk_reasoning: str = ""


@dataclass(frozen=True)
class ApprovedOrder:
    """
    Risk-approved order ready for execution. Flows from RiskEngine -> ExecutionEngine.
    Expires 30 seconds after approval — reject if stale.
    """

    order_ref: UUID
    signal_id: UUID
    pair: str
    direction: Direction
    units: Decimal  # Decimal to support fractional crypto units (e.g. 0.97 BTC)
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    risk_amount_usd: Decimal
    risk_pct: Decimal
    confidence: Decimal
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
    """Result of an order execution attempt from the broker."""

    order_ref: UUID
    broker_order_id: str
    broker_trade_id: str
    status: OrderStatus
    fill_price: Decimal
    fill_units: Decimal  # Decimal to support fractional crypto fills
    fill_timestamp: datetime
    stop_loss_confirmed: Decimal
    take_profit_confirmed: Decimal
    slippage_pips: Decimal
    raw_response: dict


@dataclass(frozen=True)
class RiskRejection:
    """Result when a signal fails risk validation."""

    signal_id: UUID
    rule_violated: str
    current_value: str
    threshold: str
    risk_state: RiskState
    rejected_at: datetime
