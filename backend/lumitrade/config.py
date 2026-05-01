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
    paper_balance: Decimal = Field(validation_alias="PAPER_BALANCE", default=Decimal("100000"))
    log_level: str = Field(validation_alias="LOG_LEVEL", default="INFO")
    sentry_dsn: str = Field(validation_alias="SENTRY_DSN", default="")

    # ── Trading parameters (DB overrides env) ──────────────────
    # `pairs`: the trading universe (used in PAPER mode).
    # `live_pairs`: the subset that may trade in LIVE mode.
    #
    # Backtest results under current filter stack + partial close 67%@1.5xRR (2026-04-29):
    #   USD_CAD: PF 2.00, Sharpe 1.94, MAR 2.18, MC P(profit) 95.2%, MaxDD 1.09%
    #            — 5/5 gates. LIVE approved.
    #   USD_JPY: H4 MTF filter (H4 EMA5>EMA10 AND H4 ADX>=25) — 5/5 gates.
    #            33 trades | PF 4.19 | Sharpe 3.46 | MAR 5.71 | MaxDD 0.68% | MC 99.8%
    #            Walk-forward OOS (30%): PF 6.82, MC 99.7%. ADX plateau stable ADX 23-29.
    #            Filter: data_engine/h4_trend_filter.py, wired in scanner.py step 2.5.
    #            LIVE approved (2026-04-29).
    #   BTC_USD: D1 MTF filter (D1 EMA5>EMA10) — 5/5 gates (2026-04-30).
    #            16 trades | WR 81.2% | PF 5.29 | Sharpe 4.84 | MAR 5.51 | MaxDD 0.53% | MC 99.7%
    #            Walk-forward OOS (30%): N=4, 100% WR. N=16 is below 20-trade confidence
    #            threshold — risk capped at 0.5%/trade (~8 trades/yr). Promote to full
    #            confidence after 20+ real-market trades accumulate under D1 filter.
    #            Filter: data_engine/d1_trend_filter.py, wired in scanner.py step 2.6.
    #            LIVE approved (2026-04-30) with caveat above.
    pairs: list[str] = ["USD_CAD", "USD_JPY", "BTC_USD"]
    live_pairs: list[str] = ["USD_CAD", "USD_JPY", "BTC_USD"]
    # Chart-first mode: Claude sees the TradingView chart and decides BUY or SELL.
    # Old 85-trade SELL data was from text-only mode — Claude can now SEE the chart.
    buy_only_mode: bool = Field(validation_alias="BUY_ONLY_MODE", default=False)
    signal_interval_minutes: int = 15  # Live: restored from paper-mode 10min. Reduces API calls, more conservative cadence.
    max_risk_pct: Decimal = Decimal("0.005")  # Default 0.5% — matches dashboard conservative default
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
    max_open_trades: int = 5  # Live: restored from paper-mode 10. Limits real-money exposure to 5 concurrent trades.
    max_positions_per_pair: int = 5  # Default 5 — matches dashboard conservative default
    max_position_units: int = 500_000
    # Two-gate position sizing (Claude + Codex review 2026-04-27):
    # `min_position_units_forex` is the BROKER floor — OANDA accepts ≥1 unit.
    # `min_meaningful_risk_usd` is the POLICY floor — refuse trades whose
    # risk budget is so small the operational cost (Claude API, DB rows,
    # logs) outweighs any meaningful P&L. Old hard-coded 1000-unit gate
    # conflated the two and locked out small accounts.
    min_position_units_forex: int = Field(
        validation_alias="MIN_POSITION_UNITS_FOREX", default=1
    )
    min_meaningful_risk_usd: Decimal = Field(
        validation_alias="MIN_MEANINGFUL_RISK_USD", default=Decimal("0.50")
    )
    daily_loss_limit_pct: Decimal = Decimal("0.05")
    weekly_loss_limit_pct: Decimal = Decimal("0.10")
    max_spread_pips: Decimal = Decimal("5.0")
    news_blackout_before_min: int = 30
    news_blackout_after_min: int = 15
    trade_cooldown_minutes: int = 5  # Live: restored from paper-mode 2min. Prevents over-trading on same pair.
    min_rr_ratio: Decimal = Decimal("1.5")
    min_sl_pips: Decimal = Decimal("15.0")
    min_tp_pips: Decimal = Decimal("15.0")
    # Raised from 6 → 24. 106-trade audit showed 6-24h bucket = 56% WR /
    # +$5,795 and 24h+ bucket = 86% WR / +$6,802, while 0-6h = 31% WR /
    # −$11,692. Forced 6h exit was severing trades just as they matured.
    #
    # Per-pair overrides (see tasks/backtest_2026Q2_results.md ablation):
    # USD_CAD ablation showed removing the 24h cap took PF 1.96 → 3.78
    # (+$8,177 over 2 years). USD_CAD's edge runs in long-trend trades that
    # want >24h. USD_JPY ablation went the opposite way (−$1,250 without cap),
    # so JPY keeps the 24h default.
    max_hold_hours: int = 24
    max_hold_hours_overrides: dict[str, int] = {"USD_CAD": 96, "BTC_USD": 96}
    # BTC-specific risk gates (backtest 2026-04-29 findings):
    # 1.5×ATR + 3:1 RR is the only config that pushed PF > 1.0 (1.09).
    # The wider 3×ATR SL was letting losses run to $343 avg vs $156 avg win.
    btc_min_rr_ratio: Decimal = Decimal("3.0")   # require 3:1 R:R minimum on BTC
    btc_max_sl_pct: Decimal = Decimal("0.02")    # reject BTC SL wider than 2% of price

    # ── Partial scale-out (win big, lose small) ────────────────────
    # Sweep 2026-04-29 across USD_CAD + USD_JPY + BTC_USD (12k H1 candles each):
    # Best config: partial_close_rr_trigger=1.5, partial_close_pct=0.67
    #   USD_CAD: PF 1.96→2.00, Sharpe 1.76→1.94, MAR 2.09→2.18, MC 94.5%→95.0%
    #   USD_JPY: PF 1.04→1.23, Sharpe 0.10→0.49, MAR 0.07→0.50 (threshold!)
    # Disabled by default — enable after migration 018 is applied to Supabase.
    partial_close_enabled: bool = Field(
        validation_alias="PARTIAL_CLOSE_ENABLED", default=False
    )
    partial_close_rr_trigger: Decimal = Decimal("1.5")  # close at 1.5×R:R
    partial_close_pct: Decimal = Decimal("0.67")        # close 67% of position

    def max_hold_hours_for(self, pair: str) -> int:
        """Per-pair max hold time. Falls back to `max_hold_hours` if no override."""
        return self.max_hold_hours_overrides.get(pair, self.max_hold_hours)
    price_deviation_max: Decimal = Decimal("0.005")
    stale_tick_seconds: int = 5
    position_monitor_interval: int = 60
    circuit_breaker_reset_sec: int = 30
    confidence_boost: Decimal = Decimal("0.05")
    confidence_penalty: Decimal = Decimal("0.05")
    lesson_block_threshold: Decimal = Decimal("0.35")
    lesson_boost_threshold: Decimal = Decimal("0.65")
    # Lesson rules older than this many days are ignored — prevents a bad patch
    # from permanently starving a pair via accumulated BLOCK rules.
    # Codex+Claude audit 2026-04-30 — P3 fix.
    lesson_max_age_days: int = 90

    # Defense-in-depth dual-switch for live trading. Both must agree on "LIVE"
    # for actual broker calls to fire. Any mismatch falls back to paper.
    #
    # `trading_mode`        — env var, set on Railway. Restart-only switch.
    # `db_mode_override`    — written by `risk_engine._load_user_settings` from
    #                         the dashboard ModeToggle. Hot-reloaded on each
    #                         signal evaluation, so a panic flip in the UI takes
    #                         effect within ~15 min (one scan cycle).
    db_mode_override: Optional[str] = None  # "LIVE" or "PAPER"; None = default to env

    # Demo-week hard lock. When set, `effective_trading_mode()` returns PAPER
    # unconditionally — env var, dashboard toggle, and arming flow are all
    # bypassed. Use during demo periods where no real-broker order may be
    # sent regardless of operator action. Set FORCE_PAPER_MODE=true on
    # Railway. Default off so production live trading is not affected.
    force_paper_mode: bool = Field(
        validation_alias="FORCE_PAPER_MODE", default=False
    )

    def effective_trading_mode(self) -> str:
        """Returns 'LIVE' iff BOTH the env var AND the dashboard say LIVE.
        Any other combination yields 'PAPER' — i.e. simulated execution.

        Hard override: if `force_paper_mode` is set (FORCE_PAPER_MODE env),
        returns PAPER unconditionally. This is the demo-week safety lock —
        no env / DB / arming combination can produce LIVE while it is on.

        Truth table (when force_paper_mode is False):
          env=LIVE,  db=LIVE   -> LIVE   (real OANDA orders)
          env=LIVE,  db=PAPER  -> PAPER  (dashboard kill-switch)
          env=PAPER, db=LIVE   -> PAPER  (env wins; never live without env)
          env=PAPER, db=PAPER  -> PAPER  (both agree)
          env=PAPER, db=None   -> PAPER  (no DB override yet)
          env=LIVE,  db=None   -> PAPER  (DB hasn't loaded; safe default)
        """
        if self.force_paper_mode:
            return "PAPER"
        if self.trading_mode == "LIVE" and self.db_mode_override == "LIVE":
            return "LIVE"
        return "PAPER"

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

    @classmethod
    def from_env(cls) -> "LumitradeConfig":
        """Construct LumitradeConfig from environment variables.

        Wraps the bare `LumitradeConfig()` call so the
        `# type: ignore[call-arg]` lint-suppression that mypy requires
        (Pydantic v2 BaseSettings infers required fields from env vars,
        which mypy cannot see) lives on a single line in this module
        instead of being copy-pasted at every call site. Behaviour is
        identical to the no-arg constructor; this is a typing
        convenience only.
        """
        return cls()  # type: ignore[call-arg]
