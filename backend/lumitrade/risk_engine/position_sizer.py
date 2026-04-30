"""
Lumitrade Position Sizer
==========================
Calculates position size in units based on account balance,
risk percentage, entry price, stop loss, and currency pair.
Uses pip_math utilities with Decimal arithmetic throughout.
Per BDS Section 6.1.
"""

from decimal import Decimal

from ..infrastructure.secure_logger import get_logger
from ..utils.pip_math import calculate_position_size, pips_between

logger = get_logger(__name__)


class PositionSizer:
    """Compute position size from risk parameters using pip math."""

    def calculate(
        self,
        balance: Decimal,
        risk_pct: Decimal,
        entry: Decimal,
        stop_loss: Decimal,
        pair: str,
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate position size in units and the actual USD risk amount.

        Args:
            balance: Account balance in USD (Decimal).
            risk_pct: Risk as a decimal fraction (e.g. Decimal("0.01") = 1%).
            entry: Entry price.
            stop_loss: Stop-loss price.
            pair: Currency pair in OANDA format (e.g. "EUR_USD").

        Returns:
            Tuple of (units: Decimal, risk_amount_usd: Decimal).
            Forex units are whole-number Decimals; crypto may be fractional.
            Returns (0, Decimal("0")) if stop loss distance is zero.
        """
        sl_pips = pips_between(entry, stop_loss, pair)

        if sl_pips == Decimal("0"):
            logger.warning(
                "position_size_zero_sl",
                pair=pair,
                entry=str(entry),
                stop_loss=str(stop_loss),
            )
            return Decimal("0"), Decimal("0")

        units, risk_amount_usd = calculate_position_size(
            balance, risk_pct, sl_pips, pair, entry,
        )

        logger.info(
            "position_sized",
            pair=pair,
            balance=str(balance),
            risk_pct=str(risk_pct),
            sl_pips=str(sl_pips),
            units=units,
            risk_usd=str(risk_amount_usd),
        )

        return units, risk_amount_usd
