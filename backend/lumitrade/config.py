"""
Lumitrade Configuration System
================================
All configuration loaded from environment variables via Pydantic Settings.
Per BDS Section 3.1 + DOS v2.0 Section 11.3 + Master Prompt Pattern 6.

Telnyx replaces Twilio for SMS alerts.
"""

import uuid
from decimal import Decimal
from functools import cached_property
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LumitradeConfig(BaseSettings):
    """All configuration loaded from environment variables."""

    # ── OANDA ──────────────────────────────────────────────────
    oanda_api_key_data: str = Field(validation_alias="OANDA_API_KEY_DATA")
    oanda_api_key_trading: str = Field(validation_alias="OANDA_API_KEY_TRADING")
    oanda_account_id: str = Field(validation_alias="OANDA_ACCOUNT_ID")
    oanda_environment: str = Field(
        validation_alias="OANDA_ENVIRONMENT", default="practice"
    )

    # ── Anthropic ──────────────────────────────────────────────
    anthropic_api_key: str = Field(validation_alias="ANTHROPIC_API_KEY")
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 2000

    # ── Supabase ───────────────────────────────────────────────
    supabase_url: str = Field(validation_alias="SUPABASE_URL")
    supabase_service_key: str = Field(validation_alias="SUPABASE_SERVICE_KEY")

    # ── Telnyx (SMS alerts) ────────────────────────────────────
    telnyx_api_key: str = Field(validation_alias="TELNYX_API_KEY")
    telnyx_from_number: str = Field(validation_alias="TELNYX_FROM_NUMBER")
    alert_sms_to: str = Field(validation_alias="ALERT_SMS_TO")

    # ── SendGrid (email alerts) ────────────────────────────────
    sendgrid_api_key: str = Field(validation_alias="SENDGRID_API_KEY")
    alert_email_to: str = Field(validation_alias="ALERT_EMAIL_TO")

    # ── IG Markets / tastyfx (gold trading) ──────────────────
    ig_api_key: str = Field(validation_alias="IG_API_KEY", default="")
    ig_username: str = Field(validation_alias="IG_USERNAME", default="")
    ig_password: str = Field(validation_alias="IG_PASSWORD", default="")
    ig_is_demo: bool = Field(validation_alias="IG_IS_DEMO", default=True)
    ig_pairs: list[str] = ["XAU_USD"]

    # ── Instance ───────────────────────────────────────────────
    instance_id: str = Field(validation_alias="INSTANCE_ID")
    trading_mode: str = Field(validation_alias="TRADING_MODE", default="PAPER")
    log_level: str = Field(validation_alias="LOG_LEVEL", default="INFO")
    sentry_dsn: str = Field(validation_alias="SENTRY_DSN", default="")

    # ── Trading parameters (DB overrides env) ──────────────────
    # USD_CAD: only profitable pair in 2-year backtest (+$24,637 at 3x ATR)
    #          — also the current franchise pair, 66.7% live WR.
    # USD_JPY: the backtest was direction-agnostic and showed -$25K,
    #          but our live direction-specific memory disagrees —
    #          BUY:USD_JPY BOOST rule is 84.6% WR / +$8,586 over 13 live
    #          trades, and BUY:USD_JPY:NY is 71% WR / +$4,694.
    #          Lesson filter will BLOCK SELL:USD_JPY automatically if
    #          the direction re-deteriorates (<35% WR on 5+ trades).
    pairs: list[str] = ["USD_CAD", "USD_JPY"]
    # Chart-first mode: Claude sees the TradingView chart and decides BUY or SELL.
    # Old 85-trade SELL data was from text-only mode — Claude can now SEE the chart.
    buy_only_mode: bool = Field(validation_alias="BUY_ONLY_MODE", default=False)
    signal_interval_minutes: int = 15
    max_risk_pct: Decimal = Decimal("0.02")
    min_confidence: Decimal = Decimal("0.70")  # Raised from 0.65 — data showed 60-70% bracket underperforms
    # 106-trade audit (2026-04-21): 0.80+ confidence bucket WR collapsed to
    # 27.3% (−$5,620 over 22 trades). Confidence model is currently inverted
    # above 0.80 — higher claimed confidence → worse outcomes. Until the
    # scorer is recalibrated, reject signals above 0.80 rather than size up
    # on them. Drops from 0.95 (chart-mode era) back to 0.80.
    max_confidence: Decimal = Decimal("0.80")
    # 17-23 UTC blocked: late NY session + dead zone. 85-trade data + industry research confirm
    # low volume, wide spreads, choppy moves. Main session filter in main.py blocks >=17 UTC.
    no_trade_hours_utc: list[int] = [17, 18, 19, 20, 21, 22, 23]
    # Weekday blackout knob. Python weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri.
    # Tuesday breakdown (23 trades / −$13,309) is dominated by W14 (17
    # trades / −$11,081) and by pairs now excluded from the pair list
    # (GBP/EUR/CHF/NZD on Tue = 0/12). Post-restriction Tuesday sample is
    # only 6 trades. Leaving empty by default — re-enable with [1] if
    # Tuesday drawdowns recur on USD_CAD / USD_JPY specifically.
    blocked_weekdays_utc: list[int] = []
    max_open_trades: int = 100
    max_positions_per_pair: int = 10
    max_position_units: int = 500_000
    daily_loss_limit_pct: Decimal = Decimal("0.05")
    weekly_loss_limit_pct: Decimal = Decimal("0.10")
    max_spread_pips: Decimal = Decimal("5.0")
    news_blackout_before_min: int = 30
    news_blackout_after_min: int = 15
    trade_cooldown_minutes: int = 5
    min_rr_ratio: Decimal = Decimal("1.5")
    min_sl_pips: Decimal = Decimal("15.0")
    min_tp_pips: Decimal = Decimal("15.0")
    # Raised from 6 → 24. 106-trade audit showed 6-24h bucket = 56% WR /
    # +$5,795 and 24h+ bucket = 86% WR / +$6,802, while 0-6h = 31% WR /
    # −$11,692. Forced 6h exit was severing trades just as they matured.
    max_hold_hours: int = 24
    price_deviation_max: Decimal = Decimal("0.005")
    stale_tick_seconds: int = 5
    position_monitor_interval: int = 60
    circuit_breaker_reset_sec: int = 30
    confidence_boost: Decimal = Decimal("0.05")
    confidence_penalty: Decimal = Decimal("0.05")
    lesson_block_threshold: Decimal = Decimal("0.35")
    lesson_boost_threshold: Decimal = Decimal("0.65")

    @cached_property
    def account_uuid(self) -> str:
        """Deterministic UUID derived from OANDA account ID for DB storage."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"lumitrade.{self.oanda_account_id}"))

    # ── Capital.com (gold/metals trading) ────────────────────────
    capital_api_key: Optional[str] = Field(
        validation_alias="CAPITAL_API_KEY", default=None
    )
    capital_identifier: Optional[str] = Field(
        validation_alias="CAPITAL_IDENTIFIER", default=None
    )
    capital_password: Optional[str] = Field(
        validation_alias="CAPITAL_PASSWORD", default=None
    )

    # ── Future features (optional — absence = feature inactive) ─
    openai_api_key: Optional[str] = Field(
        validation_alias="OPENAI_API_KEY", default=None
    )
    news_api_key: Optional[str] = Field(
        validation_alias="NEWS_API_KEY", default=None
    )
    stripe_secret_key: Optional[str] = Field(
        validation_alias="STRIPE_SECRET_KEY", default=None
    )
    stripe_connect_client_id: Optional[str] = Field(
        validation_alias="STRIPE_CONNECT_CLIENT_ID", default=None
    )
    coinbase_api_key: Optional[str] = Field(
        validation_alias="COINBASE_API_KEY", default=None
    )
    alpaca_api_key: Optional[str] = Field(
        validation_alias="ALPACA_API_KEY", default=None
    )
    expo_push_token: Optional[str] = Field(
        validation_alias="EXPO_PUSH_TOKEN", default=None
    )
    risk_monitor_enabled: Optional[str] = Field(
        validation_alias="RISK_MONITOR_ENABLED", default=None
    )

    @property
    def oanda_base_url(self) -> str:
        env = (
            "fxtrade"
            if self.oanda_environment == "live"
            else "fxpractice"
        )
        return f"https://api-{env}.oanda.com"

    @property
    def oanda_stream_url(self) -> str:
        env = (
            "stream-fxtrade"
            if self.oanda_environment == "live"
            else "stream-fxpractice"
        )
        return f"https://{env}.oanda.com"

    @property
    def features(self) -> dict[str, bool]:
        """Derive feature flags from environment variable presence."""
        return {
            "multi_model_ai": bool(self.openai_api_key),
            "news_sentiment": bool(self.news_api_key),
            "intelligence_report": bool(self.news_api_key),
            "marketplace": bool(self.stripe_secret_key),
            "copy_trading": bool(self.stripe_secret_key),
            "crypto": bool(self.coinbase_api_key),
            "stocks": bool(self.alpaca_api_key),
            "mobile_push": bool(self.expo_push_token),
            "risk_monitor": bool(self.risk_monitor_enabled),
        }

    model_config = SettingsConfigDict(
        env_file=".env",
        populate_by_name=True,
    )
