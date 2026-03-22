"""SA-01: Market Analyst Subagent. Phase 0: returns empty briefing."""

from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)


class MarketAnalystAgent(BaseSubagent):
    """Phase 0: Returns empty briefing. Phase 2: Structured market analysis."""

    async def run(self, context: dict) -> dict:
        logger.debug("market_analyst_skipped_phase_0")
        return {"briefing": ""}
