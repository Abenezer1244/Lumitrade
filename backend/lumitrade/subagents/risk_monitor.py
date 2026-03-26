"""
SA-03: Risk Monitor Subagent
===============================
Monitors open positions and assesses whether the original trade
thesis is still valid given current market price.

CRITICAL: This subagent NEVER auto-closes positions.
It only logs assessments and sends alerts for invalid theses.
Position management is the sole responsibility of the ExecutionEngine.

Per BDS Section 16.4.
"""

from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a forex risk monitor. Assess whether a trade thesis is still valid. "
    "Respond with exactly VALID or INVALID as the first word, followed by a single "
    "sentence explanation. Nothing else."
)

USER_PROMPT_TEMPLATE = (
    "Pair: {pair}, Direction: {direction}, Entry: {entry}, Current: {current}. "
    "Is the thesis still VALID or INVALID? One sentence reason."
)


class RiskMonitorAgent(BaseSubagent):
    """
    SA-03: Checks thesis validity for open positions.

    For each open trade, asks Claude whether the original thesis
    is still valid given current price vs entry price.

    CRITICAL: NEVER auto-closes positions. Only logs + alerts.
    If a thesis is assessed as INVALID, sends a warning alert
    via AlertService. The human operator or ExecutionEngine
    decides whether to close.
    """

    def __init__(self, config, db: DatabaseClient, alerts: AlertService):
        super().__init__(config)
        self.db = db
        self.alerts = alerts

    async def run(self, context: dict) -> dict:
        """
        Assess thesis validity for all open trades.

        Args:
            context: Must contain:
                - open_trades (list[dict]): each with trade_id, pair,
                  direction, entry_price, current_price

        Returns:
            Dict mapping trade_id -> {"thesis_valid": bool, "assessment": str}.
            Returns {} if no open trades or on error.
        """
        open_trades: list = context.get("open_trades", [])

        if not open_trades:
            logger.debug("risk_monitor_no_open_trades")
            return {}

        results: dict = {}

        for trade in open_trades:
            trade_id: str = str(trade.get("trade_id", "unknown"))
            pair: str = trade.get("pair", "UNKNOWN")
            direction: str = trade.get("direction", "?")
            entry: str = str(trade.get("entry_price", "?"))
            current: str = str(trade.get("current_price", "?"))

            try:
                user_prompt = USER_PROMPT_TEMPLATE.format(
                    pair=pair,
                    direction=direction,
                    entry=entry,
                    current=current,
                )

                response = await self._call_claude(
                    system=SYSTEM_PROMPT,
                    user=user_prompt,
                )

                thesis_valid = self._parse_validity(response)
                assessment = response.strip() if response else "No assessment available"

                results[trade_id] = {
                    "thesis_valid": thesis_valid,
                    "assessment": assessment,
                }

                logger.info(
                    "risk_monitor_assessment",
                    trade_id=trade_id,
                    pair=pair,
                    direction=direction,
                    thesis_valid=thesis_valid,
                )

                # NEVER auto-close. Only alert on invalid thesis.
                if not thesis_valid:
                    alert_msg = (
                        f"Thesis INVALID for {pair} {direction} "
                        f"(trade {trade_id}). Entry: {entry}, "
                        f"Current: {current}. {assessment}"
                    )
                    logger.warning(
                        "risk_monitor_thesis_invalid",
                        trade_id=trade_id,
                        pair=pair,
                        direction=direction,
                        entry=entry,
                        current=current,
                    )
                    try:
                        await self.alerts.send_warning(alert_msg)
                    except Exception as alert_err:
                        logger.error(
                            "risk_monitor_alert_failed",
                            trade_id=trade_id,
                            error=str(alert_err),
                        )

            except Exception as e:
                logger.error(
                    "risk_monitor_trade_error",
                    trade_id=trade_id,
                    pair=pair,
                    error=str(e),
                )
                results[trade_id] = {
                    "thesis_valid": True,  # Fail-safe: assume valid on error
                    "assessment": "Assessment failed — defaulting to valid",
                }

        logger.info(
            "risk_monitor_complete",
            trades_assessed=len(results),
            invalid_count=sum(
                1 for r in results.values() if not r["thesis_valid"]
            ),
        )
        return results

    @staticmethod
    def _parse_validity(response: str) -> bool:
        """
        Parse Claude's response for VALID/INVALID verdict.

        Looks for VALID or INVALID as the first word. If the response
        is empty or ambiguous, defaults to True (fail-safe: assume valid).
        """
        if not response:
            return True  # Fail-safe: no response means assume valid

        first_word = response.strip().split()[0].upper().rstrip(".:,;")

        if first_word == "INVALID":
            return False
        if first_word == "VALID":
            return True

        # Check if INVALID appears anywhere in response (fallback)
        upper_response = response.upper()
        if "INVALID" in upper_response:
            return False

        # Default: fail-safe to valid
        return True
