"""
Lumitrade Claude API Client
==============================
Wrapper for Anthropic Python SDK. Handles API calls with retry.
Per BDS Section 5 and Master Prompt.
"""

import asyncio

from anthropic import AsyncAnthropic

from ..config import LumitradeConfig
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class ClaudeClient:
    """Anthropic Claude API client with error handling."""

    def __init__(self, config: LumitradeConfig):
        self.config = config
        self._client = AsyncAnthropic(api_key=config.anthropic_api_key)

    async def call(self, system: str, user: str) -> str:
        """
        Call Claude API with system and user prompts.
        Returns raw response text.
        """
        try:
            response = await self._client.messages.create(
                model=self.config.claude_model,
                max_tokens=self.config.claude_max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = response.content[0].text
            logger.info(
                "claude_api_call_success",
                model=self.config.claude_model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return text
        except Exception as e:
            logger.error("claude_api_call_failed", error=str(e))
            raise

    async def close(self) -> None:
        """Close the client."""
        await self._client.close()
