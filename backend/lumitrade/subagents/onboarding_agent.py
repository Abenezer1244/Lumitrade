"""SA-05: Onboarding Agent. Phase 0: silent no-op."""

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)


class OnboardingAgent(BaseSubagent):
    """Phase 0: Silent no-op. Phase 3: Conversational onboarding."""

    def __init__(self, config, db: DatabaseClient):
        super().__init__(config)
        self.db = db

    async def run(self, context: dict) -> dict:
        logger.debug("onboarding_agent_skipped_phase_0")
        return {"response": "", "completed": False}
