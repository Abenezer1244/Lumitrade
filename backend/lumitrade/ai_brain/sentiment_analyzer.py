"""
Lumitrade Sentiment Analyzer — STUB
=======================================
Analyzes financial news to produce per-currency sentiment scores.
Phase 0: Returns NEUTRAL for all currencies.
Per BDS Section 13.3.
"""

from ..core.enums import CurrencySentiment
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """
    Phase 0: Returns NEUTRAL for all currencies.
    Phase 2: Fetch news via API, call Claude to analyze, return scores.
    """

    async def analyze(
        self, currencies: list[str]
    ) -> dict[str, CurrencySentiment]:
        """
        TODO Phase 2:
        1. Fetch headlines for each currency from NewsAPI/Benzinga
        2. Call Claude with headlines
        3. Parse response: BULLISH / BEARISH / NEUTRAL + confidence
        4. Cache result for 30 minutes
        """
        logger.debug("sentiment_analyzer_phase_0_stub")
        return {c: CurrencySentiment.NEUTRAL for c in currencies}
