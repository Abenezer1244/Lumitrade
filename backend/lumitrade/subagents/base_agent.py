"""
Lumitrade Base Subagent
=========================
Abstract base class for all 5 subagents.
Enforces error isolation — never raises, always returns safe default.
Per BDS Section 16.1.
"""

import asyncio
from abc import ABC, abstractmethod

from anthropic import AsyncAnthropic

from ..config import LumitradeConfig
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class BaseSubagent(ABC):
    """All subagents inherit from this. Enforces error isolation."""

    model = "claude-sonnet-4-20250514"
    max_tokens = 1000
    timeout_seconds = 30

    def __init__(self, config: LumitradeConfig):
        self.config = config
        self._client = AsyncAnthropic(api_key=config.anthropic_api_key)

    @abstractmethod
    async def run(self, context: dict) -> dict:
        """Main entry point. Must return dict. Never raise."""
        ...

    async def _call_claude(self, system: str, user: str) -> str:
        """Shared Claude API call with timeout + error handling."""
        try:
            resp = await asyncio.wait_for(
                self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                ),
                timeout=self.timeout_seconds,
            )
            return resp.content[0].text
        except Exception as e:
            logger.warning(
                "subagent_failed",
                agent=self.__class__.__name__,
                error=str(e),
            )
            return ""
