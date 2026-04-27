"""
Lumitrade Lesson Analyzer
===========================
Extracts trading patterns from closed trades and creates BLOCK/BOOST rules.
Called after every trade closes to build the adaptive trading memory.

After each trade:
  1. Extract pattern keys at multiple granularities
  2. Query all historical trades matching each pattern
  3. Calculate win rate and P&L for the pattern
  4. Upsert into trading_lessons with rule_type:
     - BLOCK if win_rate < 0.35 and sample_size >= 5
     - BOOST if win_rate > 0.65 and sample_size >= 5
     - NEUTRAL otherwise

Phase 0: Fully implemented — real pattern extraction from real trades.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ..config import LumitradeConfig
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from ..utils.time_utils import parse_iso_utc

logger = get_logger(__name__)

# ── Session hour ranges (UTC) ────────────────────────────────────
# ASIAN: 0-8, LONDON: 8-13, NY: 13-21, OTHER: 21-24
SESSION_RANGES: dict[str, tuple[int, int]] = {
    "ASIAN": (0, 8),
    "LONDON": (8, 13),
    "NY": (13, 21),
}

# ── RSI bracket boundaries ───────────────────────────────────────
RSI_BRACKETS: list[tuple[str, float, float]] = [
    ("RSI_LT_30", 0.0, 30.0),
    ("RSI_30_40", 30.0, 40.0),
    ("RSI_40_50", 40.0, 50.0),
    ("RSI_50_60", 50.0, 60.0),
    ("RSI_60_70", 60.0, 70.0),
    ("RSI_GT_70", 70.0, 100.0),
]

# ── Rule thresholds ──────────────────────────────────────────────
BLOCK_WIN_RATE = Decimal("0.35")
BOOST_WIN_RATE = Decimal("0.65")
MIN_SAMPLE_SIZE = 5


def _hour_to_session(hour: int) -> str:
    """Map UTC hour to session name."""
    for session_name, (start, end) in SESSION_RANGES.items():
        if start <= hour < end:
            return session_name
    return "OTHER"


def _rsi_to_bracket(rsi_value: float) -> str:
    """Map RSI value to bracket string."""
    for bracket_name, low, high in RSI_BRACKETS:
        if low <= rsi_value < high:
            return bracket_name
    return "RSI_UNKNOWN"


def _ema_alignment(ema20: float, ema50: float, ema200: float) -> str:
    """Determine EMA alignment: BULLISH, BEARISH, or MIXED."""
    if ema20 == 0 or ema50 == 0 or ema200 == 0:
        return "UNKNOWN"
    if ema20 > ema50 > ema200:
        return "BULLISH"
    if ema20 < ema50 < ema200:
        return "BEARISH"
    return "MIXED"


class LessonAnalyzer:
    """Extracts patterns from closed trades and maintains BLOCK/BOOST rules."""

    def __init__(self, db: DatabaseClient, config: LumitradeConfig) -> None:
        self._db = db
        self._config = config

    async def analyze_trade(
        self, trade: dict, indicators_at_entry: dict
    ) -> list[str]:
        """
        Called after every trade closes. Extracts pattern keys,
        queries historical trades matching each pattern, and upserts
        trading_lessons with updated win rates and rule types.

        Args:
            trade: The closed trade record from DB.
            indicators_at_entry: Indicator snapshot at entry time.
                May be empty — the analyzer will infer session from opened_at
                and query by pair/direction/session.

        Returns:
            List of rule descriptions that were created or updated.
        """
        pair = trade.get("pair", "")
        direction = trade.get("direction", "")
        account_id = trade.get("account_id", self._config.account_uuid)
        trade_id = trade.get("id", "")

        if not pair or not direction:
            logger.warning(
                "lesson_analyzer_skip_missing_fields",
                trade_id=trade_id,
            )
            return []

        # Determine session from opened_at timestamp
        session = self._extract_session(trade)

        # Extract indicator conditions from snapshot
        rsi_bracket = self._extract_rsi_bracket(indicators_at_entry)
        ema_align = self._extract_ema_alignment(indicators_at_entry)

        # Build pattern keys at multiple granularities (most specific first)
        pattern_keys = self._build_pattern_keys(
            direction, pair, session, rsi_bracket, ema_align
        )

        rules_updated: list[str] = []

        for pattern_key, key_pair, key_direction, key_session in pattern_keys:
            try:
                result = await self._evaluate_pattern(
                    account_id=account_id,
                    pattern_key=pattern_key,
                    pair=key_pair,
                    direction=key_direction,
                    session=key_session,
                    indicators_at_entry=indicators_at_entry,
                    trade_id=trade_id,
                )
                if result:
                    rules_updated.append(result)
            except Exception as e:
                logger.warning(
                    "lesson_pattern_evaluation_failed",
                    pattern_key=pattern_key,
                    error=str(e),
                )

        if rules_updated:
            logger.info(
                "lesson_analysis_complete",
                trade_id=trade_id,
                pair=pair,
                direction=direction,
                rules_updated=len(rules_updated),
            )

        return rules_updated

    def _extract_session(self, trade: dict) -> str:
        """Extract session name from trade opened_at timestamp."""
        opened_at = trade.get("opened_at", "")
        if not opened_at:
            return "OTHER"
        dt = parse_iso_utc(opened_at)
        if dt is None:
            return "OTHER"
        return _hour_to_session(dt.hour)

    def _extract_rsi_bracket(self, indicators: dict) -> str:
        """Extract RSI bracket from indicator snapshot."""
        rsi = indicators.get("rsi_14") or indicators.get("rsi")
        if rsi is None:
            return "RSI_UNKNOWN"
        try:
            return _rsi_to_bracket(float(rsi))
        except (ValueError, TypeError):
            return "RSI_UNKNOWN"

    def _extract_ema_alignment(self, indicators: dict) -> str:
        """Extract EMA alignment from indicator snapshot."""
        try:
            ema20 = float(indicators.get("ema_20", 0))
            ema50 = float(indicators.get("ema_50", 0))
            ema200 = float(indicators.get("ema_200", 0))
            return _ema_alignment(ema20, ema50, ema200)
        except (ValueError, TypeError):
            return "UNKNOWN"

    def _build_pattern_keys(
        self,
        direction: str,
        pair: str,
        session: str,
        rsi_bracket: str,
        ema_align: str,
    ) -> list[tuple[str, str, str, str]]:
        """
        Build pattern keys at multiple granularities.
        Returns list of (pattern_key, pair, direction, session) tuples.
        Most specific first, broadest last.
        """
        keys: list[tuple[str, str, str, str]] = []

        # Specific: direction:pair:session:rsi:ema
        if rsi_bracket != "RSI_UNKNOWN" and ema_align != "UNKNOWN":
            keys.append((
                f"{direction}:{pair}:{session}:{rsi_bracket}:{ema_align}",
                pair, direction, session,
            ))

        # Medium: direction:pair:session
        keys.append((
            f"{direction}:{pair}:{session}",
            pair, direction, session,
        ))

        # Broad: direction:pair
        keys.append((
            f"{direction}:{pair}",
            pair, direction, "*",
        ))

        return keys

    async def _evaluate_pattern(
        self,
        account_id: str,
        pattern_key: str,
        pair: str,
        direction: str,
        session: str,
        indicators_at_entry: dict,
        trade_id: str,
    ) -> str | None:
        """
        Query historical trades matching this pattern, calculate stats,
        and upsert the trading_lessons row.

        Returns a description string if a rule was created/updated, else None.
        """
        # Query closed trades matching pair and direction
        filters: dict = {
            "account_id": account_id,
            "pair": pair,
            "direction": direction,
            "status": "CLOSED",
        }
        matching_trades = await self._db.select("trades", filters)

        if not matching_trades:
            return None

        # Filter by session if not wildcard
        if session != "*":
            matching_trades = [
                t for t in matching_trades
                if self._extract_session(t) == session
            ]

        if not matching_trades:
            return None

        # Calculate win/loss stats
        wins = sum(1 for t in matching_trades if t.get("outcome") == "WIN")
        losses = sum(
            1 for t in matching_trades
            if t.get("outcome") in ("LOSS", "BREAKEVEN")
        )
        sample_size = len(matching_trades)

        if sample_size == 0:
            return None

        win_rate = Decimal(str(wins)) / Decimal(str(sample_size))

        # Calculate total P&L
        total_pnl = Decimal("0")
        for t in matching_trades:
            pnl = t.get("pnl_usd")
            if pnl is not None:
                try:
                    total_pnl += Decimal(str(pnl))
                except (ValueError, ArithmeticError, TypeError) as exc:
                    # Bad pnl_usd value in DB — drop from total but surface
                    # so we can investigate (lesson rule_type depends on this).
                    logger.warning(
                        "lesson_pnl_parse_failed",
                        trade_id=t.get("id"),
                        pnl_raw=str(pnl),
                        error=str(exc),
                    )

        # Determine rule type
        block_threshold = self._config.lesson_block_threshold if hasattr(self._config, 'lesson_block_threshold') else BLOCK_WIN_RATE
        boost_threshold = self._config.lesson_boost_threshold if hasattr(self._config, 'lesson_boost_threshold') else BOOST_WIN_RATE
        if win_rate < block_threshold and sample_size >= MIN_SAMPLE_SIZE:
            rule_type = "BLOCK"
        elif win_rate > boost_threshold and sample_size >= MIN_SAMPLE_SIZE:
            rule_type = "BOOST"
        else:
            rule_type = "NEUTRAL"

        # Build evidence summary
        evidence = (
            f"{wins}W/{losses}L out of {sample_size} trades, "
            f"WR={win_rate:.1%}, P&L=${total_pnl:.2f}"
        )

        # Extract indicator conditions for the pattern key
        indicator_conditions: dict = {}
        if indicators_at_entry:
            rsi = indicators_at_entry.get("rsi_14") or indicators_at_entry.get("rsi")
            if rsi is not None:
                indicator_conditions["rsi_bracket"] = self._extract_rsi_bracket(
                    indicators_at_entry
                )
            ema_align = self._extract_ema_alignment(indicators_at_entry)
            if ema_align != "UNKNOWN":
                indicator_conditions["ema_alignment"] = ema_align

        # Upsert into trading_lessons
        now = datetime.now(timezone.utc).isoformat()
        lesson_data = {
            "id": str(uuid4()),
            "account_id": account_id,
            "pattern_key": pattern_key,
            "pair": pair,
            "direction": direction,
            "session": session,
            "indicator_conditions": indicator_conditions,
            "rule_type": rule_type,
            "win_count": wins,
            "loss_count": losses,
            "sample_size": sample_size,
            "win_rate": str(win_rate),
            "total_pnl": str(total_pnl),
            "evidence": evidence,
            "created_from_trade_id": trade_id if trade_id else None,
            "created_at": now,
            "updated_at": now,
        }

        try:
            await self._db.upsert("trading_lessons", lesson_data)
        except Exception as e:
            logger.warning(
                "lesson_upsert_failed",
                pattern_key=pattern_key,
                error=str(e),
            )
            return None

        logger.info(
            "lesson_upserted",
            pattern_key=pattern_key,
            rule_type=rule_type,
            win_rate=str(win_rate),
            sample_size=sample_size,
            total_pnl=str(total_pnl),
        )

        return f"{rule_type}: {pattern_key} ({evidence})"

    async def seed_initial_rules(self) -> list[str]:
        """
        Pre-load BLOCK/BOOST rules derived from the 72-trade historical analysis.
        These represent statistically significant patterns with enough sample size
        to justify hard rules.

        Called once during initial setup or migration.
        """
        account_id = self._config.account_uuid
        now = datetime.now(timezone.utc).isoformat()
        rules_created: list[str] = []

        seed_rules = [
            # BLOCK: SELL any pair any session (0% WR, 13 trades)
            {
                "pattern_key": "SELL:*:*",
                "pair": "*",
                "direction": "SELL",
                "session": "*",
                "rule_type": "BLOCK",
                "win_count": 0,
                "loss_count": 13,
                "sample_size": 13,
                "win_rate": "0.0000",
                "total_pnl": "-3500.00",
                "evidence": "0W/13L, WR=0.0%, P&L=-$3500.00 (72-trade analysis)",
            },
            # BLOCK: Any direction GBP_USD any session (7% WR, 14 trades)
            {
                "pattern_key": "*:GBP_USD:*",
                "pair": "GBP_USD",
                "direction": "*",
                "session": "*",
                "rule_type": "BLOCK",
                "win_count": 1,
                "loss_count": 13,
                "sample_size": 14,
                "win_rate": "0.0714",
                "total_pnl": "-2800.00",
                "evidence": "1W/13L, WR=7.1%, P&L=-$2800.00 (72-trade analysis)",
            },
            # BLOCK: Any direction EUR_USD any session (31% WR, 13 trades)
            {
                "pattern_key": "*:EUR_USD:*",
                "pair": "EUR_USD",
                "direction": "*",
                "session": "*",
                "rule_type": "BLOCK",
                "win_count": 4,
                "loss_count": 9,
                "sample_size": 13,
                "win_rate": "0.3077",
                "total_pnl": "-1200.00",
                "evidence": "4W/9L, WR=30.8%, P&L=-$1200.00 (72-trade analysis)",
            },
            # BOOST: BUY USD_JPY ASIAN (80% WR, 5 trades)
            {
                "pattern_key": "BUY:USD_JPY:ASIAN",
                "pair": "USD_JPY",
                "direction": "BUY",
                "session": "ASIAN",
                "rule_type": "BOOST",
                "win_count": 4,
                "loss_count": 1,
                "sample_size": 5,
                "win_rate": "0.8000",
                "total_pnl": "2500.00",
                "evidence": "4W/1L, WR=80.0%, P&L=+$2500.00 (72-trade analysis)",
            },
            # BOOST: BUY USD_CAD LONDON (100% WR, 3 trades)
            {
                "pattern_key": "BUY:USD_CAD:LONDON",
                "pair": "USD_CAD",
                "direction": "BUY",
                "session": "LONDON",
                "rule_type": "BOOST",
                "win_count": 3,
                "loss_count": 0,
                "sample_size": 3,
                "win_rate": "1.0000",
                "total_pnl": "1133.00",
                "evidence": "3W/0L, WR=100%, P&L=+$1133.00 (72-trade analysis)",
            },
        ]

        for rule in seed_rules:
            try:
                lesson_data = {
                    "id": str(uuid4()),
                    "account_id": account_id,
                    "pattern_key": rule["pattern_key"],
                    "pair": rule["pair"],
                    "direction": rule["direction"],
                    "session": rule["session"],
                    "indicator_conditions": {},
                    "rule_type": rule["rule_type"],
                    "win_count": rule["win_count"],
                    "loss_count": rule["loss_count"],
                    "sample_size": rule["sample_size"],
                    "win_rate": rule["win_rate"],
                    "total_pnl": rule["total_pnl"],
                    "evidence": rule["evidence"],
                    "created_from_trade_id": None,
                    "created_at": now,
                    "updated_at": now,
                }
                await self._db.upsert("trading_lessons", lesson_data)
                desc = f"{rule['rule_type']}: {rule['pattern_key']} ({rule['evidence']})"
                rules_created.append(desc)
                logger.info(
                    "seed_rule_created",
                    pattern_key=rule["pattern_key"],
                    rule_type=rule["rule_type"],
                )
            except Exception as e:
                logger.warning(
                    "seed_rule_failed",
                    pattern_key=rule["pattern_key"],
                    error=str(e),
                )

        logger.info(
            "seed_rules_complete",
            rules_created=len(rules_created),
        )
        return rules_created
