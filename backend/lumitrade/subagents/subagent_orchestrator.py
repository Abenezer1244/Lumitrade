"""
Lumitrade Subagent Orchestrator
==================================
Manages lifecycle of all 5 subagents. Per SAS v2.0 Section 15.5.
"""

from __future__ import annotations

from ..config import LumitradeConfig
from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
from ..infrastructure.event_publisher import EventPublisher
from ..infrastructure.secure_logger import get_logger
from .intelligence_subagent import IntelligenceSubagent
from .market_analyst import MarketAnalystAgent
from .onboarding_agent import OnboardingAgent
from .post_trade_analyst import PostTradeAnalystAgent
from .risk_monitor import RiskMonitorAgent

logger = get_logger(__name__)


class SubagentOrchestrator:
    """Coordinates all 5 subagents."""

    def __init__(
        self,
        config: LumitradeConfig,
        db: DatabaseClient,
        alerts: AlertService,
        events: EventPublisher | None = None,
    ):
        self._config = config
        self._db = db
        self._events = events
        self.market_analyst = MarketAnalystAgent(config)
        self.post_trade = PostTradeAnalystAgent(config, db, events=events)
        self.risk_monitor = RiskMonitorAgent(config, db, alerts, events=events)
        self.intelligence = IntelligenceSubagent(config, db, alerts)
        self.onboarding = OnboardingAgent(config, db)

    async def get_analyst_briefing(self, snapshot) -> dict:
        return await self.market_analyst.run({
            "pair": snapshot.pair,
            "indicators": {
                "rsi_14": str(snapshot.indicators.rsi_14),
                "macd_line": str(snapshot.indicators.macd_line),
                "macd_signal": str(snapshot.indicators.macd_signal),
                "ema_20": str(snapshot.indicators.ema_20),
                "ema_50": str(snapshot.indicators.ema_50),
                "ema_200": str(snapshot.indicators.ema_200),
                "atr_14": str(snapshot.indicators.atr_14),
                "bb_upper": str(snapshot.indicators.bb_upper),
                "bb_lower": str(snapshot.indicators.bb_lower),
            },
            "candles": [
                {
                    "open": str(c.open), "high": str(c.high),
                    "low": str(c.low), "close": str(c.close),
                    "volume": str(getattr(c, "volume", 0)),
                    "time": str(getattr(c, "time", "")),
                }
                for c in (snapshot.candles_h1 or [])[-30:]
            ],
        })

    async def run_post_trade(self, trade, signal) -> None:
        recent_trades = signal.get("recent_trades", []) if isinstance(signal, dict) else []
        result = await self.post_trade.run({"recent_trades": recent_trades, "closed_trade": trade})
        status = result.get("status")
        if status == "error":
            logger.error("post_trade_analyst_failed", error=result.get("error"))
        elif status == "partial":
            logger.warning("post_trade_insight_lost", error=result.get("error"))

    async def run_risk_monitor(self, open_trades, market_data) -> None:
        await self.risk_monitor.run({"open_trades": open_trades, "market": market_data})

    async def run_weekly_intelligence(self, account_id: str) -> None:
        # Fetch real context for the intelligence report
        try:
            recent_trades = await self._db.select(
                "trades",
                {"status": "CLOSED", "account_id": account_id},
                order="closed_at",
                limit=20,
            ) if hasattr(self, "_db") else []
        except Exception:
            recent_trades = []

        try:
            state_row = await self._db.select_one(
                "system_state", {"id": "singleton"}
            ) if hasattr(self, "_db") else {}
            account_summary = {
                "balance": state_row.get("daily_opening_balance", "0") if state_row else "0",
                "weekly_opening": state_row.get("weekly_opening_balance", "0") if state_row else "0",
            }
        except Exception:
            account_summary = {}

        result = await self.intelligence.run({
            "account_id": account_id,
            "recent_trades": recent_trades,
            "account_summary": account_summary,
            "pairs": self._config.pairs,
        })
        if result.get("status") == "error":
            logger.error(
                "weekly_intelligence_failed",
                account_id=account_id,
                error=result.get("error"),
            )

    async def run_onboarding(self, account_id: str, message: str) -> str:
        result = await self.onboarding.run(
            {"account_id": account_id, "user_message": message},
        )
        return result.get("response", "")
