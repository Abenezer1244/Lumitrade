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

    # ── Instance ───────────────────────────────────────────────
    instance_id: str = Field(validation_alias="INSTANCE_ID")
    trading_mode: str = Field(validation_alias="TRADING_MODE", default="PAPER")
    log_level: str = Field(validation_alias="LOG_LEVEL", default="INFO")
    sentry_dsn: str = Field(validation_alias="SENTRY_DSN", default="")

    # ── Trading parameters (DB overrides env) ──────────────────
    pairs: list[str] = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD", "XAU_USD"]
    signal_interval_minutes: int = 15
    max_risk_pct: Decimal = Decimal("0.02")
    min_confidence: Decimal = Decimal("0.65")
    max_open_trades: int = 100
    max_positions_per_pair: int = 1
    max_position_units: int = 500_000
    daily_loss_limit_pct: Decimal = Decimal("0.05")
    weekly_loss_limit_pct: Decimal = Decimal("0.10")
    max_spread_pips: Decimal = Decimal("3.0")
    news_blackout_before_min: int = 30
    news_blackout_after_min: int = 15
    trade_cooldown_minutes: int = 5
    min_rr_ratio: Decimal = Decimal("1.5")

    @cached_property
    def account_uuid(self) -> str:
        """Deterministic UUID derived from OANDA account ID for DB storage."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"lumitrade.{self.oanda_account_id}"))

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
