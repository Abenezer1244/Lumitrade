"""
Lumitrade Sentiment Analyzer — Claude AI Implementation
=========================================================
Analyzes economic calendar events and price action context to produce
per-currency sentiment scores (BULLISH / BEARISH / NEUTRAL) using
Claude Haiku for fast, low-cost inference.

Results are cached in-memory for 30 minutes to avoid redundant API calls.
Falls back to NEUTRAL on any error — never raises, never blocks trading.

Per BDS Section 13.3.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import anthropic

from ..config import LumitradeConfig
from ..core.enums import CurrencySentiment, NewsImpact
from ..core.models import NewsEvent
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# Cache TTL: 30 minutes in seconds
_CACHE_TTL_SECONDS: int = 1800

# Model: cheapest and fastest Claude model, sufficient for sentiment classification
_HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
_MAX_TOKENS: int = 512


class SentimentAnalyzer:
    """
    Produces per-currency sentiment scores by calling Claude Haiku with
    economic calendar context and optional price action data.

    - Extracts unique currencies from forex pair list (EUR_USD -> EUR, USD)
    - Checks 30-minute in-memory cache before calling the API
    - Builds a structured prompt from calendar events and price context
    - Parses response line-by-line expecting "CURRENCY: SENTIMENT" format
    - Falls back to NEUTRAL for any currency on parse or API error
    """

    def __init__(self, config: LumitradeConfig) -> None:
        self._config = config
        self._client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
        # In-memory cache: { currency: (CurrencySentiment, expiry_timestamp) }
        self._cache: dict[str, tuple[CurrencySentiment, float]] = {}
        logger.info("sentiment_analyzer_initialized", model=_HAIKU_MODEL)

    async def analyze(
        self,
        pairs: list[str],
        calendar_events: list[NewsEvent] | None = None,
        price_action_context: dict[str, Any] | None = None,
    ) -> dict[str, CurrencySentiment]:
        """
        Analyze sentiment for all currencies present in the given pairs.

        Args:
            pairs: Forex pairs like ["EUR_USD", "GBP_USD"].
            calendar_events: Upcoming/recent economic calendar events.
            price_action_context: Optional dict with price action summaries per pair.

        Returns:
            Dict mapping each unique currency to its CurrencySentiment.
            Always returns a result for every currency — NEUTRAL on failure.
        """
        currencies = self._extract_currencies(pairs)
        if not currencies:
            return {}

        now = time.monotonic()
        result: dict[str, CurrencySentiment] = {}
        uncached: list[str] = []

        # Check cache first
        for currency in currencies:
            cached = self._get_cached(currency, now)
            if cached is not None:
                result[currency] = cached
            else:
                uncached.append(currency)

        if not uncached:
            logger.debug(
                "sentiment_all_cached",
                currencies_count=len(currencies),
            )
            return result

        logger.info(
            "sentiment_analysis_started",
            total_currencies=len(currencies),
            cached=len(currencies) - len(uncached),
            uncached=len(uncached),
            uncached_list=",".join(sorted(uncached)),
        )

        # Call Claude Haiku for uncached currencies
        api_results = await self._call_claude(
            uncached,
            calendar_events or [],
            price_action_context or {},
        )

        # Merge API results into final output and cache them
        for currency in uncached:
            sentiment = api_results.get(currency, CurrencySentiment.NEUTRAL)
            result[currency] = sentiment
            self._set_cached(currency, sentiment, now)

        logger.info(
            "sentiment_analysis_complete",
            results={c: s.value for c, s in result.items()},
        )
        return result

    def _extract_currencies(self, pairs: list[str]) -> list[str]:
        """Extract unique currencies from pairs like EUR_USD -> [EUR, USD]."""
        currencies: set[str] = set()
        for pair in pairs:
            parts = pair.split("_")
            if len(parts) == 2:
                currencies.add(parts[0])
                currencies.add(parts[1])
            else:
                logger.warning("sentiment_invalid_pair_format", pair=pair)
        return sorted(currencies)

    def _get_cached(
        self, currency: str, now: float
    ) -> Optional[CurrencySentiment]:
        """Return cached sentiment if present and not expired, else None."""
        entry = self._cache.get(currency)
        if entry is None:
            return None
        sentiment, expiry = entry
        if now >= expiry:
            del self._cache[currency]
            return None
        return sentiment

    def _set_cached(
        self, currency: str, sentiment: CurrencySentiment, now: float
    ) -> None:
        """Store sentiment in cache with TTL."""
        self._cache[currency] = (sentiment, now + _CACHE_TTL_SECONDS)

    def _build_prompt(
        self,
        currencies: list[str],
        calendar_events: list[NewsEvent],
        price_action_context: dict[str, Any],
    ) -> str:
        """
        Build the analysis prompt for Claude Haiku.

        Includes:
        - The list of currencies to rate
        - Relevant economic calendar events with impact levels
        - Optional price action context
        """
        lines: list[str] = []
        lines.append(
            "You are a senior forex fundamental analyst. "
            "Rate the sentiment for each currency listed below as exactly one of: "
            "BULLISH, BEARISH, or NEUTRAL."
        )
        lines.append("")
        lines.append(
            "Base your assessment on the economic calendar events and "
            "price action context provided. If information is insufficient, "
            "rate as NEUTRAL."
        )
        lines.append("")

        # Currencies to rate
        lines.append(f"Currencies to rate: {', '.join(currencies)}")
        lines.append("")

        # Calendar events section
        if calendar_events:
            lines.append("=== ECONOMIC CALENDAR EVENTS ===")
            for event in calendar_events:
                affected = ", ".join(event.currencies_affected)
                timing = self._describe_timing(event.minutes_until)
                lines.append(
                    f"- [{event.impact.value}] {event.title} "
                    f"(affects: {affected}) — {timing}"
                )
            lines.append("")
        else:
            lines.append("No economic calendar events in the near-term window.")
            lines.append("")

        # Price action context
        if price_action_context:
            lines.append("=== PRICE ACTION CONTEXT ===")
            for pair, context in price_action_context.items():
                lines.append(f"- {pair}: {context}")
            lines.append("")

        # Output format instruction
        lines.append("=== OUTPUT FORMAT ===")
        lines.append(
            "Respond with ONLY one line per currency in this exact format, "
            "nothing else:"
        )
        lines.append("")
        for currency in currencies:
            lines.append(f"{currency}: BULLISH or BEARISH or NEUTRAL")

        return "\n".join(lines)

    @staticmethod
    def _describe_timing(minutes_until: int) -> str:
        """Human-readable timing description from minutes_until field."""
        if minutes_until < -60:
            hours_ago = abs(minutes_until) // 60
            return f"{hours_ago}h ago"
        if minutes_until < 0:
            return f"{abs(minutes_until)}min ago"
        if minutes_until == 0:
            return "happening now"
        if minutes_until <= 60:
            return f"in {minutes_until}min"
        hours = minutes_until // 60
        return f"in {hours}h"

    async def _call_claude(
        self,
        currencies: list[str],
        calendar_events: list[NewsEvent],
        price_action_context: dict[str, Any],
    ) -> dict[str, CurrencySentiment]:
        """
        Call Claude Haiku to classify sentiment for the given currencies.
        Returns a dict of currency -> sentiment. Falls back to NEUTRAL on error.
        """
        prompt = self._build_prompt(currencies, calendar_events, price_action_context)

        try:
            response = await self._client.messages.create(
                model=_HAIKU_MODEL,
                max_tokens=_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_text = ""
            for block in response.content:
                if block.type == "text":
                    raw_text += block.text

            logger.debug(
                "sentiment_claude_response",
                model=_HAIKU_MODEL,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            return self._parse_response(raw_text, currencies)

        except anthropic.APIConnectionError as exc:
            logger.error(
                "sentiment_api_connection_error",
                error=str(exc),
            )
            return {c: CurrencySentiment.NEUTRAL for c in currencies}

        except anthropic.RateLimitError as exc:
            logger.warning(
                "sentiment_api_rate_limited",
                error=str(exc),
            )
            return {c: CurrencySentiment.NEUTRAL for c in currencies}

        except anthropic.APIStatusError as exc:
            logger.error(
                "sentiment_api_status_error",
                status_code=exc.status_code,
                error=str(exc),
            )
            return {c: CurrencySentiment.NEUTRAL for c in currencies}

        except Exception as exc:
            logger.error(
                "sentiment_api_unexpected_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return {c: CurrencySentiment.NEUTRAL for c in currencies}

    def _parse_response(
        self,
        raw_text: str,
        expected_currencies: list[str],
    ) -> dict[str, CurrencySentiment]:
        """
        Parse Claude's response line by line.
        Expected format per line: "EUR: BULLISH"
        Falls back to NEUTRAL for any currency that fails to parse.
        """
        valid_sentiments = {s.value: s for s in CurrencySentiment}
        result: dict[str, CurrencySentiment] = {}
        expected_set = set(expected_currencies)

        for line in raw_text.strip().splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue

            # Split on first colon only
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue

            currency = parts[0].strip().upper()
            sentiment_str = parts[1].strip().upper()

            if currency not in expected_set:
                logger.debug(
                    "sentiment_parse_unexpected_currency",
                    currency=currency,
                    line=line,
                )
                continue

            if sentiment_str in valid_sentiments:
                result[currency] = valid_sentiments[sentiment_str]
            else:
                logger.warning(
                    "sentiment_parse_invalid_value",
                    currency=currency,
                    raw_value=sentiment_str,
                )
                result[currency] = CurrencySentiment.NEUTRAL

        # Fill in any missing currencies with NEUTRAL
        for currency in expected_currencies:
            if currency not in result:
                logger.warning(
                    "sentiment_parse_missing_currency",
                    currency=currency,
                )
                result[currency] = CurrencySentiment.NEUTRAL

        return result

    def clear_cache(self) -> None:
        """Clear all cached sentiment data. Useful for testing or forced refresh."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("sentiment_cache_cleared", entries_cleared=count)
