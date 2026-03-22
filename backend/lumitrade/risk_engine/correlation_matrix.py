"""
Lumitrade Correlation Matrix (STUB)
=====================================
Stub per BDS Section 13.4.
Returns safe defaults (zero correlation, no position adjustment).
Will be implemented when multi-pair correlation tracking is activated.

All stubs are silent no-ops returning safe defaults (Rule 6).
"""

from decimal import Decimal

from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class CorrelationMatrix:
    """Stub: returns neutral correlation values until correlation tracking is active."""

    def get_correlation(self, pair_a: str, pair_b: str) -> Decimal:
        """
        Return the correlation coefficient between two currency pairs.

        Stub returns Decimal("0.0") — no correlation assumed.

        Args:
            pair_a: First currency pair (e.g. "EUR_USD").
            pair_b: Second currency pair (e.g. "GBP_USD").

        Returns:
            Decimal correlation coefficient in range [-1.0, 1.0].
        """
        return Decimal("0.0")

    def get_position_size_multiplier(
        self,
        open_pairs: list[str],
        new_pair: str,
    ) -> Decimal:
        """
        Return the position size multiplier based on correlation with open positions.

        Stub returns Decimal("1.0") — no adjustment.

        Args:
            open_pairs: List of currency pairs with open positions.
            new_pair: The pair being evaluated for a new position.

        Returns:
            Decimal multiplier (1.0 = no adjustment, <1.0 = reduce size).
        """
        return Decimal("1.0")
