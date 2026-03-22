"""SA-02: Post-Trade Analyst Subagent. Phase 0: silent no-op."""

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)


class PostTradeAnalystAgent(BaseSubagent):
    """Phase 0: Silent no-op. Phase 2: Analyzes closed trades."""

    MIN_TRADES = 20

    def __init__(self, config, db: DatabaseClient):
        super().__init__(config)
        self.db = db

    async def run(self, context: dict) -> dict:
        logger.debug("post_trade_analyst_skipped_phase_0")
        return {}
