"""
Lumitrade Subagent Orchestrator
==================================
Manages lifecycle of all 5 subagents. Per SAS v2.0 Section 15.5.
"""

from ..config import LumitradeConfig
from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
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
    ):
        self.market_analyst = MarketAnalystAgent(config)
        self.post_trade = PostTradeAnalystAgent(config, db)
        self.risk_monitor = RiskMonitorAgent(config, db, alerts)
        self.intelligence = IntelligenceSubagent(config, db, alerts)
        self.onboarding = OnboardingAgent(config, db)

    async def get_analyst_briefing(self, snapshot) -> dict:
        return await self.market_analyst.run({"snapshot": snapshot})

    async def run_post_trade(self, trade, signal) -> None:
        await self.post_trade.run({"trade": trade, "signal": signal})

    async def run_risk_monitor(self, open_trades, market_data) -> None:
        await self.risk_monitor.run({"trades": open_trades, "market": market_data})

    async def run_weekly_intelligence(self, account_id: str) -> None:
        await self.intelligence.run({"account_id": account_id})

    async def run_onboarding(self, account_id: str, message: str) -> str:
        result = await self.onboarding.run(
            {"account_id": account_id, "user_message": message},
        )
        return result.get("response", "")
