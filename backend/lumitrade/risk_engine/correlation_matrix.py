"""
Lumitrade Correlation Matrix
==============================
Known historical forex correlations for the 8 traded instruments.

Uses static 90-day rolling approximate correlations. Phase 2 will
compute rolling correlations from live candle data.

Per BDS Section 13.4.
"""

from datetime import datetime, timezone
from decimal import Decimal

from ..infrastructure.db import DatabaseClient
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
    based on historical correlations.

    Prefers live computed correlations from stored candle data; falls
    back to the static table when live data is unavailable or stale.
    """

    def __init__(self, db: DatabaseClient | None = None):
        self._db = db
        self._computed: dict[tuple[str, str], Decimal] = {}
        self._last_refresh: datetime | None = None

    async def refresh(self, pairs: list[str]) -> None:
        """Compute rolling correlations from stored candle close prices.
        Fetches last 90 daily candles per pair from the candles table."""
        if not self._db:
            return
        try:
            pair_closes: dict[str, list[Decimal]] = {}
            for pair in pairs:
                rows = await self._db.select(
                    "candles",
                    {"pair": pair, "granularity": "D"},
                    order="time",
                    limit=90,
                )
                if rows and len(rows) >= 30:
                    pair_closes[pair] = [Decimal(str(r["close"])) for r in rows]

            # Compute Pearson correlation for each pair combo
            for i, pair_a in enumerate(pairs):
                for pair_b in pairs[i + 1:]:
                    if pair_a in pair_closes and pair_b in pair_closes:
                        corr = self._pearson(pair_closes[pair_a], pair_closes[pair_b])
                        key = _normalize_key(pair_a, pair_b)
                        self._computed[key] = corr

            self._last_refresh = datetime.now(timezone.utc)
            logger.info(
                "correlation_matrix_refreshed",
                pairs=len(pairs),
                computed=len(self._computed),
            )
        except Exception as e:
            logger.warning("correlation_refresh_failed", error=str(e))

    @staticmethod
    def _pearson(x: list[Decimal], y: list[Decimal]) -> Decimal:
        """Compute Pearson correlation coefficient between two price series."""
        n = min(len(x), len(y))
        if n < 10:
            return Decimal("0.0")
        x, y = x[-n:], y[-n:]
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        dx = [xi - mean_x for xi in x]
        dy = [yi - mean_y for yi in y]
        import math
        cov = sum(a * b for a, b in zip(dx, dy))
        std_x = Decimal(str(math.sqrt(float(sum(d * d for d in dx)))))
        std_y = Decimal(str(math.sqrt(float(sum(d * d for d in dy)))))
        if std_x == 0 or std_y == 0:
            return Decimal("0.0")
        corr = cov / (std_x * std_y)
        return corr.quantize(Decimal("0.01"))

    def get_correlation(self, pair_a: str, pair_b: str) -> Decimal:
        """
        Return the correlation coefficient between two currency pairs.

        Prefers live computed values; falls back to static table.

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
        # Prefer computed (live data) over static
        if key in self._computed:
            return self._computed[key]
        return _CORRELATION_TABLE.get(key, Decimal("0.0"))

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
