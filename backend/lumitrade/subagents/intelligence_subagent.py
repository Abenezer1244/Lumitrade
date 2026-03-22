"""SA-04: Intelligence Subagent. Phase 0: silent no-op."""

from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)


class IntelligenceSubagent(BaseSubagent):
    """Phase 0: Silent no-op. Phase 2: Weekly intelligence report."""

    def __init__(self, config, db: DatabaseClient, alerts: AlertService):
        super().__init__(config)
        self.db = db
        self.alerts = alerts

    async def run(self, context: dict) -> dict:
        if not getattr(self.config, "news_api_key", None):
            logger.debug("intelligence_skipped_no_api_key")
            return {}
        logger.debug("intelligence_subagent_skipped_phase_0")
        return {}
