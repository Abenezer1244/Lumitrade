"""
Lumitrade Consensus Engine — Self-Consistency Validation
==========================================================
Makes a second-opinion Claude Haiku call to validate the primary signal.
If the second opinion agrees with the proposal action, confidence is boosted.
If it disagrees, confidence is reduced. On any error, the proposal passes
through unchanged (fail-open for availability).

Per BDS Section 13.2.
"""

from dataclasses import replace
from decimal import Decimal

from anthropic import AsyncAnthropic

from ..config import LumitradeConfig
from ..core.enums import Action
from ..core.models import SignalProposal
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────
CONSENSUS_MODEL = "claude-haiku-4-5-20251001"
CONSENSUS_MAX_TOKENS = 50
CONFIDENCE_BOOST = Decimal("0.05")
CONFIDENCE_PENALTY = Decimal("0.05")
CONFIDENCE_MAX = Decimal("1.0")
CONFIDENCE_MIN = Decimal("0.0")

SYSTEM_PROMPT = (
    "You are a senior forex analyst. Given market context for a currency pair, "
    "respond with exactly one word: BUY, SELL, or HOLD. "
    "No explanation, no punctuation, just the single word."
)


class ConsensusEngine:
    """
    Self-consistency validation via a second-opinion Claude Haiku call.

    The engine asks a fresh Haiku instance whether to BUY, SELL, or HOLD
    the given pair based on the market context. If the second opinion
    matches the primary signal's action, confidence is boosted by 0.05
    (capped at 1.0). If it disagrees, confidence is reduced by 0.10
    (floored at 0.0). On any error, the proposal passes through unchanged.
    """

    def __init__(self, config: LumitradeConfig) -> None:
        self._config = config
        self._client = AsyncAnthropic(api_key=config.anthropic_api_key)

    async def validate(
        self, proposal: SignalProposal, market_context: str
    ) -> SignalProposal:
        """
        Validate a SignalProposal via second-opinion Haiku call.

        Args:
            proposal: The primary AI-generated signal to validate.
            market_context: Formatted market context string for the pair.

        Returns:
            A new SignalProposal with adjusted confidence_adjusted, or
            the original proposal unchanged on error.
        """
        # HOLD signals do not need consensus validation
        if proposal.action == Action.HOLD:
            logger.debug(
                "consensus_skipped_hold",
                signal_id=str(proposal.signal_id),
                pair=proposal.pair,
            )
            return proposal

        try:
            second_opinion = await self._get_second_opinion(
                proposal.pair, market_context
            )
        except Exception as e:
            logger.error(
                "consensus_second_opinion_failed",
                signal_id=str(proposal.signal_id),
                pair=proposal.pair,
                error=str(e),
            )
            return proposal

        agrees = second_opinion == proposal.action

        if agrees:
            new_confidence = min(
                CONFIDENCE_MAX,
                proposal.confidence_adjusted + self._config.confidence_boost,
            )
            logger.info(
                "consensus_agreement",
                signal_id=str(proposal.signal_id),
                pair=proposal.pair,
                primary_action=(proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action)),
                second_opinion=second_opinion.value,
                old_confidence=str(proposal.confidence_adjusted),
                new_confidence=str(new_confidence),
            )
        else:
            new_confidence = max(
                CONFIDENCE_MIN,
                proposal.confidence_adjusted - self._config.confidence_penalty,
            )
            logger.warning(
                "consensus_disagreement",
                signal_id=str(proposal.signal_id),
                pair=proposal.pair,
                primary_action=(proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action)),
                second_opinion=second_opinion.value,
                old_confidence=str(proposal.confidence_adjusted),
                new_confidence=str(new_confidence),
            )

        # Update the confidence adjustment log with consensus result
        updated_log = dict(proposal.confidence_adjustment_log)
        updated_log["consensus"] = {
            "second_opinion": second_opinion.value,
            "agrees": agrees,
            "adjustment": str(self._config.confidence_boost if agrees else -self._config.confidence_penalty),
        }

        return replace(
            proposal,
            confidence_adjusted=new_confidence,
            confidence_adjustment_log=updated_log,
        )

    async def _get_second_opinion(
        self, pair: str, market_context: str
    ) -> Action:
        """
        Call Claude Haiku for a fresh BUY/SELL/HOLD opinion.

        Args:
            pair: The currency pair (e.g., "EUR_USD").
            market_context: Formatted market data for the pair.

        Returns:
            An Action enum value from the Haiku response.

        Raises:
            ValueError: If the response cannot be parsed to a valid Action.
            Exception: Any API communication error.
        """
        user_prompt = (
            f"Should a trader BUY, SELL, or HOLD {pair}?\n\n"
            f"Market context:\n{market_context}"
        )

        response = await self._client.messages.create(
            model=CONSENSUS_MODEL,
            max_tokens=CONSENSUS_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = response.content[0].text.strip().upper()

        logger.info(
            "consensus_haiku_response",
            pair=pair,
            model=CONSENSUS_MODEL,
            raw_response=raw_text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        # Parse the response — extract the first valid action word
        for token in raw_text.split():
            cleaned = token.strip(".,!?;:")
            if cleaned in {"BUY", "SELL", "HOLD"}:
                return Action(cleaned)

        raise ValueError(
            f"Could not parse Haiku response to valid Action: '{raw_text}'"
        )

    async def close(self) -> None:
        """Close the underlying Anthropic client."""
        await self._client.close()
