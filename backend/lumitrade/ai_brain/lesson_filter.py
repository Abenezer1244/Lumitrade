"""
Lumitrade Lesson Filter
=========================
Pre-filter that checks BLOCK and BOOST rules before AI signal generation.
Runs before every Claude API call to prevent known-losing patterns
and highlight known-winning setups.

BLOCK rules: If any BLOCK rule matches current conditions, the pair is skipped.
BOOST rules: Matching BOOST rules are injected into the AI prompt as preferred setups.

Pattern matching supports wildcards ("*") on pair, direction, and session fields.
"""

from __future__ import annotations

from ..config import LumitradeConfig
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class LessonFilter:
    """Pre-filter that checks trading_lessons for BLOCK/BOOST rules."""

    def __init__(self, db: DatabaseClient, config: LumitradeConfig) -> None:
        self._db = db
        self._config = config

    async def check(
        self,
        pair: str,
        direction: str,
        session: str,
        indicators: dict | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Check if current trade conditions match any BLOCK or BOOST rules.

        Args:
            pair: Currency pair, e.g. "USD_JPY"
            direction: "BUY" or "SELL"
            session: "ASIAN", "LONDON", "NY", or "OTHER"
            indicators: Optional indicator snapshot (for future granular matching)

        Returns:
            Tuple of (is_blocked: bool, boost_messages: list[str])
            - is_blocked: True if any BLOCK rule matches — skip this trade
            - boost_messages: List of evidence strings from matching BOOST rules
        """
        account_id = self._config.account_uuid

        # ── Check BLOCK rules ────────────────────────────────────
        try:
            block_rules = await self._db.select(
                "trading_lessons",
                {"account_id": account_id, "rule_type": "BLOCK"},
            )
        except Exception as e:
            logger.warning("lesson_filter_block_query_failed", error=str(e))
            # Fail open — don't block trades if we can't read rules
            block_rules = []

        for rule in block_rules:
            if self._matches(rule, pair, direction, session):
                logger.info(
                    "lesson_filter_blocked",
                    pair=pair,
                    direction=direction,
                    session=session,
                    pattern_key=rule.get("pattern_key", ""),
                    evidence=rule.get("evidence", ""),
                    win_rate=str(rule.get("win_rate", "")),
                    sample_size=rule.get("sample_size", 0),
                )
                return True, []

        # ── Check BOOST rules ────────────────────────────────────
        boost_messages: list[str] = []
        try:
            boost_rules = await self._db.select(
                "trading_lessons",
                {"account_id": account_id, "rule_type": "BOOST"},
            )
        except Exception as e:
            logger.warning("lesson_filter_boost_query_failed", error=str(e))
            boost_rules = []

        for rule in boost_rules:
            if self._matches(rule, pair, direction, session):
                evidence = rule.get("evidence", "")
                pattern_key = rule.get("pattern_key", "")
                msg = f"PREFERRED SETUP: {pattern_key} — {evidence}"
                boost_messages.append(msg)
                logger.info(
                    "lesson_filter_boost_matched",
                    pair=pair,
                    direction=direction,
                    session=session,
                    pattern_key=pattern_key,
                )

        return False, boost_messages

    def _matches(
        self,
        rule: dict,
        pair: str,
        direction: str,
        session: str,
    ) -> bool:
        """
        Check if a rule matches the given conditions.
        Wildcard "*" in any rule field matches any value.
        """
        rule_pair = rule.get("pair", "")
        rule_direction = rule.get("direction", "")
        rule_session = rule.get("session", "")

        # Pair match (wildcard or exact)
        if rule_pair != "*" and rule_pair != pair:
            return False

        # Direction match (wildcard or exact)
        if rule_direction != "*" and rule_direction != direction:
            return False

        # Session match (wildcard or exact)
        if rule_session != "*" and rule_session != session:
            return False

        return True
