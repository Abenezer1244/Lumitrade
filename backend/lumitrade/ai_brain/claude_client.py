"""
Lumitrade Claude API Client
==============================
Wrapper for Anthropic Python SDK. Handles API calls with retry.
Per BDS Section 5 and Master Prompt.
"""


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

    async def call_with_image(self, system: str, prompt: str, image_b64: str) -> str:
        """
        Call Claude API with a multimodal message (image + text).

        Sends a base64-encoded PNG chart alongside the text prompt for
        visual pattern recognition. Falls back to text-only if image_b64
        is empty.

        Args:
            system: System prompt string.
            prompt: User prompt text.
            image_b64: Base64-encoded PNG image data.

        Returns:
            Raw response text from Claude.
        """
        if not image_b64:
            logger.debug("call_with_image_no_image", fallback="text_only")
            return await self.call(system, prompt)

        try:
            response = await self._client.messages.create(
                model=self.config.claude_model,
                max_tokens=self.config.claude_max_tokens,
                system=system,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }],
            )
            text = response.content[0].text
            logger.info(
                "claude_api_call_with_image_success",
                model=self.config.claude_model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return text
        except Exception as e:
            logger.error("claude_api_call_with_image_failed", error=str(e))
            raise

    async def close(self) -> None:
        """Close the client."""
        await self._client.close()
