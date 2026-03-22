"""SA-03: Risk Monitor Subagent. Phase 0: silent no-op. NEVER auto-closes positions."""

from .base_agent import BaseSubagent
from ..infrastructure.db import DatabaseClient
from ..infrastructure.alert_service import AlertService
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class RiskMonitorAgent(BaseSubagent):
    """
    Phase 0: Silent no-op.
    Phase 2: Checks thesis validity for open positions every 30 min.
    CRITICAL: NEVER auto-closes positions. Only logs + alerts.
    """

    def __init__(self, config, db: DatabaseClient, alerts: AlertService):
        super().__init__(config)
        self.db = db
        self.alerts = alerts

    async def run(self, context: dict) -> dict:
        logger.debug("risk_monitor_skipped_phase_0")
        return {}
