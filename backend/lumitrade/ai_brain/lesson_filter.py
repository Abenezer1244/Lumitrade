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

from datetime import datetime, timedelta, timezone

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

        # Fetch both sets up-front so we can apply specificity precedence.
        # (Previously: BLOCK-first matching meant a wildcard BLOCK would
        # suppress a more-specific BOOST on the same conditions.)
        try:
            block_rules = await self._db.select(
                "trading_lessons",
                {"account_id": account_id, "rule_type": "BLOCK"},
            )
        except Exception as e:
            logger.warning("lesson_filter_block_query_failed", error=str(e))
            block_rules = []

        try:
            boost_rules = await self._db.select(
                "trading_lessons",
                {"account_id": account_id, "rule_type": "BOOST"},
            )
        except Exception as e:
            logger.warning("lesson_filter_boost_query_failed", error=str(e))
            boost_rules = []

        cutoff = datetime.now(timezone.utc) - timedelta(days=self._config.lesson_max_age_days)
        matching_blocks = [
            r for r in block_rules
            if self._matches(r, pair, direction, session) and self._is_fresh(r, cutoff)
        ]
        matching_boosts = [
            r for r in boost_rules
            if self._matches(r, pair, direction, session) and self._is_fresh(r, cutoff)
        ]

        # ── Specificity precedence ───────────────────────────────
        # A BOOST that is at least as specific as every matching BLOCK wins.
        # Specificity = count of non-wildcard fields (pair, direction, session).
        # This prevents a broad BLOCK (e.g., "SELL:*:*") from suppressing a
        # pair-specific BOOST (e.g., "SELL:USD_CAD:LONDON") when both match.
        if matching_blocks:
            most_specific_block = max(matching_blocks, key=self._specificity)
            if matching_boosts:
                most_specific_boost = max(matching_boosts, key=self._specificity)
                if self._specificity(most_specific_boost) >= self._specificity(
                    most_specific_block
                ):
                    logger.info(
                        "lesson_filter_block_overridden_by_boost",
                        pair=pair,
                        direction=direction,
                        session=session,
                        block=most_specific_block.get("pattern_key", ""),
                        boost=most_specific_boost.get("pattern_key", ""),
                    )
                else:
                    logger.info(
                        "lesson_filter_blocked",
                        pair=pair,
                        direction=direction,
                        session=session,
                        pattern_key=most_specific_block.get("pattern_key", ""),
                        evidence=most_specific_block.get("evidence", ""),
                        win_rate=str(most_specific_block.get("win_rate", "")),
                        sample_size=most_specific_block.get("sample_size", 0),
                    )
                    return True, []
            else:
                logger.info(
                    "lesson_filter_blocked",
                    pair=pair,
                    direction=direction,
                    session=session,
                    pattern_key=most_specific_block.get("pattern_key", ""),
                    evidence=most_specific_block.get("evidence", ""),
                    win_rate=str(most_specific_block.get("win_rate", "")),
                    sample_size=most_specific_block.get("sample_size", 0),
                )
                return True, []

        # Not blocked — collect boost messages for prompt injection.
        boost_messages: list[str] = []
        for rule in matching_boosts:
            evidence = rule.get("evidence", "")
            pattern_key = rule.get("pattern_key", "")
            boost_messages.append(f"PREFERRED SETUP: {pattern_key} — {evidence}")
            logger.info(
                "lesson_filter_boost_matched",
                pair=pair,
                direction=direction,
                session=session,
                pattern_key=pattern_key,
            )

        return False, boost_messages

    @staticmethod
    def _specificity(rule: dict) -> int:
        """Count non-wildcard fields. 3 = exact pair+direction+session match."""
        return sum(
            1
            for field in ("pair", "direction", "session")
            if rule.get(field, "*") != "*"
        )

    @staticmethod
    def _is_fresh(rule: dict, cutoff: datetime) -> bool:
        """Return True if the rule was created/updated within the max-age window.
        Rules without a timestamp are treated as fresh (legacy rows).
        Codex+Claude audit 2026-04-30 — P3 fix."""
        for ts_field in ("updated_at", "created_at"):
            raw = rule.get(ts_field)
            if not raw:
                continue
            try:
                ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts >= cutoff
            except (ValueError, TypeError):
                continue
        return True  # no timestamp — treat as fresh (legacy row)

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
