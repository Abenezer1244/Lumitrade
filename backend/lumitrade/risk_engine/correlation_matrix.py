"""
Lumitrade Correlation Matrix
==============================
Known historical forex correlations for the 8 traded instruments.

Uses static 90-day rolling approximate correlations. Phase 2 will
compute rolling correlations from live candle data.

Per BDS Section 13.4.
"""

from decimal import Decimal

from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# ── Static correlation table (approximate 90-day rolling) ─────────
# Keys are normalized: alphabetically sorted tuple of pairs.
_CORRELATION_TABLE: dict[tuple[str, str], Decimal] = {
    # Original 3 pairs
    ("EUR_USD", "GBP_USD"): Decimal("0.85"),
    ("EUR_USD", "USD_JPY"): Decimal("-0.60"),
    ("GBP_USD", "USD_JPY"): Decimal("-0.55"),
    # New major pairs
    ("AUD_USD", "EUR_USD"): Decimal("0.70"),
    ("AUD_USD", "GBP_USD"): Decimal("0.65"),
    ("AUD_USD", "NZD_USD"): Decimal("0.90"),
    ("AUD_USD", "USD_JPY"): Decimal("-0.50"),
    ("EUR_USD", "NZD_USD"): Decimal("0.65"),
    ("EUR_USD", "USD_CAD"): Decimal("-0.55"),
    ("EUR_USD", "USD_CHF"): Decimal("-0.90"),
    ("GBP_USD", "NZD_USD"): Decimal("0.60"),
    ("GBP_USD", "USD_CAD"): Decimal("-0.50"),
    ("GBP_USD", "USD_CHF"): Decimal("-0.75"),
    ("NZD_USD", "USD_JPY"): Decimal("-0.45"),
    ("USD_CAD", "USD_CHF"): Decimal("0.50"),
    ("USD_CAD", "USD_JPY"): Decimal("0.55"),
    ("USD_CHF", "USD_JPY"): Decimal("0.60"),
    # Gold
    ("EUR_USD", "XAU_USD"): Decimal("0.40"),
    ("USD_CHF", "XAU_USD"): Decimal("-0.35"),
    ("USD_JPY", "XAU_USD"): Decimal("-0.30"),
}


def _normalize_key(pair_a: str, pair_b: str) -> tuple[str, str]:
    """Return a consistently ordered tuple for lookup."""
    if pair_a <= pair_b:
        return (pair_a, pair_b)
    return (pair_b, pair_a)


class CorrelationMatrix:
    """
    Provides forex pair correlations and position size multipliers
    based on known historical correlations.

    Phase 0/1: Uses static correlation values for the 3 traded pairs.

    TODO Phase 2: Compute rolling correlations from stored candle data,
    update correlations on a configurable schedule (e.g., daily),
    persist computed correlations to the database, and support
    dynamic pair expansion beyond the initial 3.
    """

    def get_correlation(self, pair_a: str, pair_b: str) -> Decimal:
        """
        Return the correlation coefficient between two currency pairs.

        Args:
            pair_a: First currency pair (e.g. "EUR_USD").
            pair_b: Second currency pair (e.g. "GBP_USD").

        Returns:
            Decimal correlation coefficient in range [-1.0, 1.0].
            Same pair returns 1.0, unknown pair returns 0.0.
        """
        if pair_a == pair_b:
            return Decimal("1.0")

        key = _normalize_key(pair_a, pair_b)
        correlation = _CORRELATION_TABLE.get(key, Decimal("0.0"))
        return correlation

    def get_position_size_multiplier(
        self,
        open_pairs: list[str],
        new_pair: str,
    ) -> Decimal:
        """
        Return the position size multiplier based on correlation with open positions.

        Formula: multiplier = 1.0 - (max_abs_correlation × 0.5)
        - 0.0 correlation  -> 1.0x (full size)
        - 0.85 correlation -> 0.575x (reduced due to EUR_USD/GBP_USD overlap)
        - 1.0 correlation  -> 0.5x (half size, same pair already open)

        Args:
            open_pairs: List of currency pairs with open positions.
            new_pair: The pair being evaluated for a new position.

        Returns:
            Decimal multiplier in range [0.5, 1.0]. Always >= 0.5.
        """
        if not open_pairs:
            return Decimal("1.0")

        max_abs_corr = Decimal("0.0")
        most_correlated_pair = ""

        for open_pair in open_pairs:
            corr = self.get_correlation(open_pair, new_pair)
            abs_corr = abs(corr)
            if abs_corr > max_abs_corr:
                max_abs_corr = abs_corr
                most_correlated_pair = open_pair

        multiplier = Decimal("1.0") - (max_abs_corr * Decimal("0.5"))

        if max_abs_corr > Decimal("0.0"):
            logger.info(
                "correlation_size_adjustment",
                new_pair=new_pair,
                most_correlated_with=most_correlated_pair,
                correlation=str(max_abs_corr),
                multiplier=str(multiplier),
            )

        return multiplier
