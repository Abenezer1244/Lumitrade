"""
SA-05: Onboarding Agent
=========================
Guides new users through Lumitrade setup via conversational AI.
Steps: (1) Connect OANDA account, (2) Set risk parameters, (3) Understand dashboard.

Phase 2 TODO:
- Persist onboarding_state in DB so progress survives page reloads
- Add validation that OANDA credentials actually work before marking step 1 complete
- Add interactive dashboard tour with frontend integration
- Track onboarding completion analytics
"""

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)

ONBOARDING_SYSTEM_PROMPT = """You are the Lumitrade onboarding assistant. You guide new users through setting up their AI-powered forex trading system.

You walk users through THREE steps in order:
1. **Connect OANDA** — Help them create an OANDA practice account, find their API key and account ID, and enter them in Lumitrade settings.
2. **Set Risk Parameters** — Explain risk percentage (default 1%), max open positions (default 3), and daily loss limits. Help them choose values appropriate for their experience level.
3. **Understand the Dashboard** — Explain what each section shows: live signals, open positions, trade history, and the analytics page.

Rules:
- Be concise and friendly but professional. This is a real trading system with real money at stake.
- Ask ONE question at a time. Do not overwhelm the user.
- If the user seems confused, simplify your explanation.
- Track which step the user is on based on the onboarding_state provided.
- When the user has completed all three steps, congratulate them and let them know they are ready to start paper trading.
- Never give specific trading advice or financial recommendations.

The onboarding_state will be one of: "step_1_oanda", "step_2_risk", "step_3_dashboard", "completed".
If no state is provided, start from step 1."""

ONBOARDING_STEPS = ["step_1_oanda", "step_2_risk", "step_3_dashboard", "completed"]


class OnboardingAgent(BaseSubagent):
    """Conversational onboarding agent for new Lumitrade users."""

    max_tokens = 800
    timeout_seconds = 30

    def __init__(self, config, db: DatabaseClient):
        super().__init__(config)
        self.db = db

    async def run(self, context: dict) -> dict:
        """Process an onboarding conversation turn.

        Expected context keys:
            - user_message: str — what the user said
            - onboarding_state: str — current step (step_1_oanda, step_2_risk, step_3_dashboard, completed)

        Returns:
            {"response": str, "completed": bool}
            On error: {"response": "I'm having trouble right now. Please try again.", "completed": False}
        """
        user_message = context.get("user_message", "")
        onboarding_state = context.get("onboarding_state", "step_1_oanda")

        if onboarding_state == "completed":
            return {
                "response": (
                    "You have already completed onboarding. "
                    "Your system is ready for paper trading. "
                    "Check the dashboard for live signals."
                ),
                "completed": True,
            }

        if not user_message:
            user_message = "I just signed up. Help me get started."

        user_prompt = (
            f"Current onboarding step: {onboarding_state}\n\n"
            f"User message: {user_message}"
        )

        try:
            response_text = await self._call_claude(
                system=ONBOARDING_SYSTEM_PROMPT,
                user=user_prompt,
            )

            if not response_text:
                logger.warning("onboarding_empty_response")
                return {
                    "response": "I'm having trouble right now. Please try again.",
                    "completed": False,
                }

            completed = onboarding_state == "step_3_dashboard" and self._detect_step_complete(response_text)

            logger.info(
                "onboarding_response_generated",
                state=onboarding_state,
                completed=completed,
                response_length=len(response_text),
            )

            return {
                "response": response_text,
                "completed": completed,
            }

        except Exception as e:
            logger.error("onboarding_agent_error", error=str(e))
            return {
                "response": "I'm having trouble right now. Please try again.",
                "completed": False,
            }

    def _detect_step_complete(self, response_text: str) -> bool:
        """Heuristic to detect if the final step has been completed.

        Looks for congratulatory language that indicates the user has
        finished all three onboarding steps.
        """
        completion_indicators = [
            "ready to start",
            "all set",
            "completed",
            "you're ready",
            "congratulations",
            "paper trading",
            "good to go",
        ]
        response_lower = response_text.lower()
        return any(indicator in response_lower for indicator in completion_indicators)
