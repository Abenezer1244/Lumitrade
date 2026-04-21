"""Lesson filter tests — specificity precedence between BOOST and BLOCK.

Regression for the case where a broad BLOCK (e.g., "SELL:*:*") would
suppress a pair-specific BOOST (e.g., "SELL:USD_CAD:LONDON") because
check() returned on the first BLOCK match.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from lumitrade.ai_brain.lesson_filter import LessonFilter


class _StubDb:
    """Minimal async stub exposing only .select()."""

    def __init__(self, rows_by_type: dict[str, list[dict]]):
        self._rows = rows_by_type

    async def select(self, table: str, filters: dict, **_kw: Any) -> list[dict]:
        rule_type = filters.get("rule_type", "")
        return list(self._rows.get(rule_type, []))


def _rule(
    pattern_key: str,
    pair: str,
    direction: str,
    session: str,
    rule_type: str,
    *,
    win_rate: float = 0.5,
    sample_size: int = 10,
    evidence: str = "",
) -> dict:
    return {
        "pattern_key": pattern_key,
        "pair": pair,
        "direction": direction,
        "session": session,
        "rule_type": rule_type,
        "win_rate": win_rate,
        "sample_size": sample_size,
        "evidence": evidence or f"{rule_type} {pattern_key}",
    }


@pytest.fixture
def config():
    c = MagicMock()
    c.account_uuid = "acct-1"
    return c


@pytest.mark.asyncio
async def test_exact_block_without_boost_still_blocks(config) -> None:
    db = _StubDb(
        {
            "BLOCK": [_rule("*:GBP_USD:*", "GBP_USD", "*", "*", "BLOCK")],
            "BOOST": [],
        }
    )
    lf = LessonFilter(db, config)
    blocked, boosts = await lf.check("GBP_USD", "BUY", "LONDON")
    assert blocked is True
    assert boosts == []


@pytest.mark.asyncio
async def test_specific_boost_overrides_wildcard_block(config) -> None:
    """SELL:*:* BLOCK must not suppress SELL:USD_CAD:LONDON BOOST."""
    db = _StubDb(
        {
            "BLOCK": [_rule("SELL:*:*", "*", "SELL", "*", "BLOCK")],
            "BOOST": [
                _rule(
                    "SELL:USD_CAD:LONDON",
                    "USD_CAD",
                    "SELL",
                    "LONDON",
                    "BOOST",
                    win_rate=0.83,
                )
            ],
        }
    )
    lf = LessonFilter(db, config)
    blocked, boosts = await lf.check("USD_CAD", "SELL", "LONDON")
    assert blocked is False, "Specific BOOST should override wildcard BLOCK"
    assert any("SELL:USD_CAD:LONDON" in m for m in boosts)


@pytest.mark.asyncio
async def test_broad_boost_does_not_override_specific_block(config) -> None:
    """A less-specific BOOST should NOT beat a more-specific BLOCK."""
    db = _StubDb(
        {
            "BLOCK": [
                _rule(
                    "BUY:GBP_USD:NY",
                    "GBP_USD",
                    "BUY",
                    "NY",
                    "BLOCK",
                    win_rate=0.05,
                )
            ],
            "BOOST": [_rule("*:GBP_USD:*", "GBP_USD", "*", "*", "BOOST")],
        }
    )
    lf = LessonFilter(db, config)
    blocked, boosts = await lf.check("GBP_USD", "BUY", "NY")
    assert blocked is True, "More-specific BLOCK must win over broader BOOST"


@pytest.mark.asyncio
async def test_no_matching_rules_allows_trade(config) -> None:
    db = _StubDb({"BLOCK": [], "BOOST": []})
    lf = LessonFilter(db, config)
    blocked, boosts = await lf.check("USD_CAD", "BUY", "ASIAN")
    assert blocked is False
    assert boosts == []


@pytest.mark.asyncio
async def test_equal_specificity_ties_to_boost(config) -> None:
    """When BOOST specificity equals BLOCK specificity, allow the trade.

    Rationale: we should not block when the same-specificity evidence is
    mixed — let the AI make the final call with both signals in hand.
    """
    db = _StubDb(
        {
            "BLOCK": [_rule("SELL:USD_CAD", "USD_CAD", "SELL", "*", "BLOCK")],
            "BOOST": [_rule("SELL:USD_CAD", "USD_CAD", "SELL", "*", "BOOST")],
        }
    )
    lf = LessonFilter(db, config)
    blocked, _ = await lf.check("USD_CAD", "SELL", "LONDON")
    assert blocked is False
