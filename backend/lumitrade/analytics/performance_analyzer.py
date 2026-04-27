"""
Lumitrade Performance Analyzer
================================
Analyzes trade history to generate per-account performance insights and
self-tuning recommendations. Eight analysis methods implemented: session
breakdown, pair breakdown, indicator accuracy, confidence calibration,
prompt-pattern review, plus the three Phase-3 self-tuning passes
(_evolve_prompt_instructions, _update_session_filters,
_update_confidence_thresholds) which write to performance_insights and
config-override rows.

Per Addition Set 1D.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict

from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from ..utils.time_utils import parse_iso_utc

logger = get_logger(__name__)


class TradeRow(TypedDict, total=False):
    """One row from the `trades` table (database/migrations/001).

    Marked `total=False` because Supabase round-trips DECIMAL columns as
    strings and nullable columns may be absent. All numeric fields
    (`entry_price`, `pnl_pips`, `pnl_usd`, `confidence_score`, etc.) are
    typed as `str` because Supabase returns them as strings — coerce
    via `_to_decimal()` before arithmetic. Used for static documentation
    of the row shape inside this module's internal helpers; the
    public-facing analyzer methods continue to accept `list[dict]` to
    preserve their signatures.
    """

    id: str
    account_id: str
    signal_id: str | None
    broker_trade_id: str | None
    pair: str
    direction: str  # "BUY" | "SELL"
    mode: str  # "PAPER" | "LIVE"
    entry_price: str
    exit_price: str | None
    stop_loss: str
    take_profit: str
    position_size: int
    confidence_score: str | None
    slippage_pips: str | None
    pnl_pips: str | None
    pnl_usd: str | None
    status: str  # "OPEN" | "CLOSED" | "CANCELLED"
    exit_reason: str | None  # "SL_HIT" | "TP_HIT" | "AI_CLOSE" | "MANUAL" | "EMERGENCY" | "UNKNOWN"
    outcome: str | None  # "WIN" | "LOSS" | "BREAKEVEN"
    session: str | None
    opened_at: str
    closed_at: str | None
    duration_minutes: int | None


class PerformanceAnalyzer:
    """Reads trade log and generates actionable performance insights."""

    MIN_SAMPLE_SIZE = 20
    HIGH_CONFIDENCE_MIN = 30

    # Confidence buckets for indicator accuracy analysis
    CONFIDENCE_BUCKETS: list[tuple[str, Decimal, Decimal]] = [
        ("0.65-0.70", Decimal("0.65"), Decimal("0.70")),
        ("0.70-0.80", Decimal("0.70"), Decimal("0.80")),
        ("0.80-0.90", Decimal("0.80"), Decimal("0.90")),
        ("0.90+", Decimal("0.90"), Decimal("1.01")),
    ]

    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def analyze(self, account_id: str) -> None:
        """
        Entry point. Called by ExecutionEngine after every 10th trade
        (once MIN_SAMPLE_SIZE closed trades exist).

        Fetches all closed trades once, then distributes to each analyzer.
        """
        logger.info("performance_analysis_started", account_id=account_id)

        try:
            trades = await self.db.select(
                "trades",
                {"account_id": account_id, "status": "CLOSED"},
                order="closed_at",
            )
        except Exception as exc:
            logger.error(
                "performance_analysis_trade_fetch_failed",
                account_id=account_id,
                error=str(exc),
            )
            return

        if len(trades) < self.MIN_SAMPLE_SIZE:
            logger.info(
                "performance_analysis_skipped_insufficient_data",
                account_id=account_id,
                trade_count=len(trades),
                min_required=self.MIN_SAMPLE_SIZE,
            )
            return

        # Phase 2 analyzers
        await self._analyze_session_performance(account_id, trades)
        await self._analyze_pair_performance(account_id, trades)
        await self._analyze_indicator_accuracy(account_id, trades)
        await self._analyze_confidence_calibration(account_id, trades)
        await self._analyze_prompt_patterns(account_id, trades)

        # Phase 3 stubs (silent no-ops)
        await self._evolve_prompt_instructions(account_id, trades)
        await self._update_session_filters(account_id, trades)
        await self._update_confidence_thresholds(account_id, trades)

        logger.info(
            "performance_analysis_completed",
            account_id=account_id,
            trade_count=len(trades),
        )

    # ------------------------------------------------------------------
    # Helper: safe Decimal conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        """Convert a value to Decimal safely. Returns None on failure."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Helper: date range from trade list
    # ------------------------------------------------------------------

    @staticmethod
    def _date_range(trades: list[TradeRow]) -> tuple[str, str]:
        """Return (period_start, period_end) ISO date strings from trades.

        Internal helper; `TradeRow` documents the expected row shape.
        Callers pass `list[dict]` from Supabase — the runtime contract
        is unchanged because TypedDicts are dicts at runtime.
        """
        dates: list[str] = []
        for t in trades:
            opened = t.get("opened_at") or t.get("closed_at")
            if opened:
                if isinstance(opened, str):
                    dates.append(opened[:10])
                elif isinstance(opened, datetime):
                    dates.append(opened.date().isoformat())
        if not dates:
            today = date.today().isoformat()
            return today, today
        return min(dates), max(dates)

    # ------------------------------------------------------------------
    # Helper: store insight
    # ------------------------------------------------------------------

    async def _store_insight(
        self,
        account_id: str,
        insight_type: str,
        metric_name: str,
        metric_value: Decimal,
        sample_size: int,
        period_start: str,
        period_end: str,
        *,
        pair: str | None = None,
        session: str | None = None,
        benchmark_value: Decimal | None = None,
        deviation_pct: Decimal | None = None,
        is_actionable: bool = False,
        recommendation: str | None = None,
        detail: dict | None = None,
    ) -> None:
        """Insert a row into performance_insights via DatabaseClient."""
        row: dict[str, Any] = {
            "account_id": account_id,
            "insight_type": insight_type,
            "pair": pair,
            "session": session,
            "period_start": period_start,
            "period_end": period_end,
            "metric_name": metric_name,
            "metric_value": str(metric_value),
            "benchmark_value": str(benchmark_value) if benchmark_value is not None else None,
            "deviation_pct": str(deviation_pct) if deviation_pct is not None else None,
            "sample_size": sample_size,
            "is_actionable": is_actionable,
            "recommendation": recommendation,
            "detail": json.dumps(detail) if detail else "{}",
        }
        await self.db.insert("performance_insights", row)

    # ------------------------------------------------------------------
    # Phase 2: Session Performance
    # ------------------------------------------------------------------

    async def _analyze_session_performance(
        self, account_id: str, trades: list[dict]
    ) -> None:
        """
        Group trades by hour of day (UTC from opened_at).
        Calculate win rate per hour bucket.
        Find best and worst trading hours.
        Store insight in performance_insights.
        """
        try:
            hour_buckets: dict[int, dict[str, int]] = defaultdict(
                lambda: {"wins": 0, "losses": 0, "total": 0}
            )

            for trade in trades:
                opened_at = trade.get("opened_at")
                if not opened_at:
                    continue

                dt = parse_iso_utc(opened_at)
                if dt is None:
                    continue

                hour = dt.hour
                hour_buckets[hour]["total"] += 1
                outcome = trade.get("outcome", "")
                if outcome == "WIN":
                    hour_buckets[hour]["wins"] += 1
                elif outcome == "LOSS":
                    hour_buckets[hour]["losses"] += 1

            if not hour_buckets:
                logger.debug("session_performance_no_data", account_id=account_id)
                return

            # Calculate win rates per hour
            hour_rates: dict[int, Decimal] = {}
            hour_detail: dict[str, Any] = {}
            for hour, counts in sorted(hour_buckets.items()):
                total = counts["total"]
                if total > 0:
                    win_rate = Decimal(str(counts["wins"])) / Decimal(str(total))
                    hour_rates[hour] = win_rate
                    hour_detail[str(hour)] = {
                        "wins": counts["wins"],
                        "losses": counts["losses"],
                        "total": total,
                        "win_rate": str(win_rate.quantize(Decimal("0.0001"))),
                    }

            if not hour_rates:
                return

            # Find best and worst hours
            best_hour = max(hour_rates, key=lambda h: hour_rates[h])
            worst_hour = min(hour_rates, key=lambda h: hour_rates[h])

            # Overall win rate as benchmark
            total_wins = sum(c["wins"] for c in hour_buckets.values())
            total_trades = sum(c["total"] for c in hour_buckets.values())
            overall_wr = (
                Decimal(str(total_wins)) / Decimal(str(total_trades))
                if total_trades > 0
                else Decimal("0")
            )

            period_start, period_end = self._date_range(trades)

            best_wr = hour_rates[best_hour].quantize(Decimal("0.0001"))
            worst_wr = hour_rates[worst_hour].quantize(Decimal("0.0001"))
            best_deviation = (
                ((best_wr - overall_wr) / overall_wr * Decimal("100")).quantize(Decimal("0.01"))
                if overall_wr > 0
                else Decimal("0")
            )

            recommendation_parts: list[str] = []
            if best_wr > overall_wr:
                recommendation_parts.append(
                    f"Best trading hour: {best_hour:02d}:00 UTC "
                    f"(win rate {best_wr})."
                )
            if worst_wr < overall_wr and hour_buckets[worst_hour]["total"] >= 5:
                recommendation_parts.append(
                    f"Consider avoiding hour {worst_hour:02d}:00 UTC "
                    f"(win rate {worst_wr})."
                )

            await self._store_insight(
                account_id=account_id,
                insight_type="SESSION_PERFORMANCE",
                metric_name="best_hour_win_rate",
                metric_value=best_wr,
                sample_size=total_trades,
                period_start=period_start,
                period_end=period_end,
                session=f"{best_hour:02d}:00",
                benchmark_value=overall_wr.quantize(Decimal("0.0001")),
                deviation_pct=best_deviation,
                is_actionable=len(recommendation_parts) > 0,
                recommendation=" ".join(recommendation_parts) if recommendation_parts else None,
                detail={
                    "hourly_breakdown": hour_detail,
                    "best_hour": best_hour,
                    "worst_hour": worst_hour,
                    "overall_win_rate": str(overall_wr.quantize(Decimal("0.0001"))),
                },
            )

            logger.info(
                "session_performance_analyzed",
                account_id=account_id,
                best_hour=best_hour,
                worst_hour=worst_hour,
                total_trades=total_trades,
            )

        except Exception as exc:
            logger.error(
                "session_performance_analysis_failed",
                account_id=account_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Phase 2: Pair Performance
    # ------------------------------------------------------------------

    async def _analyze_pair_performance(
        self, account_id: str, trades: list[dict]
    ) -> None:
        """
        Group trades by pair.
        Calculate win rate, avg PnL, trade count per pair.
        Find best and worst performing pair.
        Store insight.
        """
        try:
            pair_stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"wins": 0, "losses": 0, "total": 0, "pnl_pips": Decimal("0"), "pnl_usd": Decimal("0")}
            )

            for trade in trades:
                pair = trade.get("pair")
                if not pair:
                    continue

                pair_stats[pair]["total"] += 1
                outcome = trade.get("outcome", "")
                if outcome == "WIN":
                    pair_stats[pair]["wins"] += 1
                elif outcome == "LOSS":
                    pair_stats[pair]["losses"] += 1

                pnl_pips = self._to_decimal(trade.get("pnl_pips"))
                if pnl_pips is not None:
                    pair_stats[pair]["pnl_pips"] += pnl_pips

                pnl_usd = self._to_decimal(trade.get("pnl_usd"))
                if pnl_usd is not None:
                    pair_stats[pair]["pnl_usd"] += pnl_usd

            if not pair_stats:
                logger.debug("pair_performance_no_data", account_id=account_id)
                return

            # Calculate per-pair metrics
            pair_detail: dict[str, Any] = {}
            pair_win_rates: dict[str, Decimal] = {}

            for pair, stats in pair_stats.items():
                total = stats["total"]
                win_rate = (
                    Decimal(str(stats["wins"])) / Decimal(str(total))
                    if total > 0
                    else Decimal("0")
                )
                avg_pnl_pips = (
                    stats["pnl_pips"] / Decimal(str(total))
                    if total > 0
                    else Decimal("0")
                )
                avg_pnl_usd = (
                    stats["pnl_usd"] / Decimal(str(total))
                    if total > 0
                    else Decimal("0")
                )
                pair_win_rates[pair] = win_rate
                pair_detail[pair] = {
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "total": total,
                    "win_rate": str(win_rate.quantize(Decimal("0.0001"))),
                    "avg_pnl_pips": str(avg_pnl_pips.quantize(Decimal("0.01"))),
                    "avg_pnl_usd": str(avg_pnl_usd.quantize(Decimal("0.01"))),
                    "total_pnl_usd": str(stats["pnl_usd"].quantize(Decimal("0.01"))),
                }

            # Best and worst by win rate (require minimum 3 trades)
            qualified = {p: wr for p, wr in pair_win_rates.items() if pair_stats[p]["total"] >= 3}
            if not qualified:
                qualified = pair_win_rates

            best_pair = max(qualified, key=lambda p: qualified[p])
            worst_pair = min(qualified, key=lambda p: qualified[p])

            total_all = sum(s["total"] for s in pair_stats.values())
            total_wins = sum(s["wins"] for s in pair_stats.values())
            overall_wr = (
                Decimal(str(total_wins)) / Decimal(str(total_all))
                if total_all > 0
                else Decimal("0")
            )

            period_start, period_end = self._date_range(trades)
            best_wr = pair_win_rates[best_pair].quantize(Decimal("0.0001"))

            recommendation_parts: list[str] = []
            if best_wr > overall_wr:
                recommendation_parts.append(
                    f"Strongest pair: {best_pair} (win rate {best_wr})."
                )
            worst_wr = pair_win_rates[worst_pair].quantize(Decimal("0.0001"))
            if worst_wr < overall_wr and pair_stats[worst_pair]["total"] >= 3:
                recommendation_parts.append(
                    f"Weakest pair: {worst_pair} (win rate {worst_wr}). "
                    f"Consider reducing exposure."
                )

            await self._store_insight(
                account_id=account_id,
                insight_type="PAIR_ANALYSIS",
                metric_name="best_pair_win_rate",
                metric_value=best_wr,
                sample_size=total_all,
                period_start=period_start,
                period_end=period_end,
                pair=best_pair,
                benchmark_value=overall_wr.quantize(Decimal("0.0001")),
                deviation_pct=(
                    ((best_wr - overall_wr) / overall_wr * Decimal("100")).quantize(Decimal("0.01"))
                    if overall_wr > 0
                    else Decimal("0")
                ),
                is_actionable=len(recommendation_parts) > 0,
                recommendation=" ".join(recommendation_parts) if recommendation_parts else None,
                detail={
                    "pair_breakdown": pair_detail,
                    "best_pair": best_pair,
                    "worst_pair": worst_pair,
                    "overall_win_rate": str(overall_wr.quantize(Decimal("0.0001"))),
                },
            )

            logger.info(
                "pair_performance_analyzed",
                account_id=account_id,
                best_pair=best_pair,
                worst_pair=worst_pair,
                pairs_analyzed=len(pair_stats),
            )

        except Exception as exc:
            logger.error(
                "pair_performance_analysis_failed",
                account_id=account_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Phase 2: Indicator Accuracy (confidence range analysis)
    # ------------------------------------------------------------------

    async def _analyze_indicator_accuracy(
        self, account_id: str, trades: list[dict]
    ) -> None:
        """
        For trades that have confidence_score, group by confidence ranges
        (0.65-0.70, 0.70-0.80, 0.80-0.90, 0.90+).
        Calculate actual win rate per confidence range.
        Identify if high-confidence trades actually win more.
        Store insight.
        """
        try:
            bucket_stats: dict[str, dict[str, int]] = {
                label: {"wins": 0, "losses": 0, "total": 0}
                for label, _, _ in self.CONFIDENCE_BUCKETS
            }

            scored_count = 0
            for trade in trades:
                confidence = self._to_decimal(trade.get("confidence_score"))
                if confidence is None:
                    continue

                scored_count += 1
                outcome = trade.get("outcome", "")

                for label, low, high in self.CONFIDENCE_BUCKETS:
                    if low <= confidence < high:
                        bucket_stats[label]["total"] += 1
                        if outcome == "WIN":
                            bucket_stats[label]["wins"] += 1
                        elif outcome == "LOSS":
                            bucket_stats[label]["losses"] += 1
                        break

            if scored_count < self.MIN_SAMPLE_SIZE:
                logger.debug(
                    "indicator_accuracy_insufficient_scored_trades",
                    account_id=account_id,
                    scored_count=scored_count,
                )
                return

            # Build detail and check monotonicity
            bucket_detail: dict[str, Any] = {}
            win_rates_ordered: list[Decimal] = []

            for label, _, _ in self.CONFIDENCE_BUCKETS:
                stats = bucket_stats[label]
                total = stats["total"]
                if total > 0:
                    wr = Decimal(str(stats["wins"])) / Decimal(str(total))
                else:
                    wr = Decimal("0")
                win_rates_ordered.append(wr)
                bucket_detail[label] = {
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "total": total,
                    "win_rate": str(wr.quantize(Decimal("0.0001"))),
                }

            # Check if higher confidence actually predicts higher win rate
            # (monotonically increasing across non-empty buckets)
            non_empty_rates = [
                wr
                for wr, (label, _, _) in zip(win_rates_ordered, self.CONFIDENCE_BUCKETS)
                if bucket_stats[label]["total"] >= 3
            ]
            is_monotonic = all(
                non_empty_rates[i] <= non_empty_rates[i + 1]
                for i in range(len(non_empty_rates) - 1)
            ) if len(non_empty_rates) >= 2 else False

            # Highest bucket win rate
            highest_bucket_label = self.CONFIDENCE_BUCKETS[-1][0]
            highest_bucket_wr = (
                Decimal(str(bucket_stats[highest_bucket_label]["wins"]))
                / Decimal(str(bucket_stats[highest_bucket_label]["total"]))
                if bucket_stats[highest_bucket_label]["total"] > 0
                else Decimal("0")
            ).quantize(Decimal("0.0001"))

            # Overall win rate of scored trades
            total_wins = sum(s["wins"] for s in bucket_stats.values())
            total_all = sum(s["total"] for s in bucket_stats.values())
            overall_wr = (
                Decimal(str(total_wins)) / Decimal(str(total_all))
                if total_all > 0
                else Decimal("0")
            ).quantize(Decimal("0.0001"))

            period_start, period_end = self._date_range(trades)

            recommendation = None
            is_actionable = False
            if not is_monotonic and len(non_empty_rates) >= 2:
                recommendation = (
                    "Confidence scores are not well-calibrated: higher confidence "
                    "does not reliably predict higher win rates. Review AI signal "
                    "quality and confidence adjustment factors."
                )
                is_actionable = True
            elif is_monotonic:
                recommendation = (
                    "Confidence calibration is healthy: higher confidence correlates "
                    "with higher win rates."
                )

            await self._store_insight(
                account_id=account_id,
                insight_type="CONFIDENCE_CALIBRATION",
                metric_name="highest_bucket_win_rate",
                metric_value=highest_bucket_wr,
                sample_size=total_all,
                period_start=period_start,
                period_end=period_end,
                benchmark_value=overall_wr,
                deviation_pct=(
                    ((highest_bucket_wr - overall_wr) / overall_wr * Decimal("100")).quantize(Decimal("0.01"))
                    if overall_wr > 0
                    else Decimal("0")
                ),
                is_actionable=is_actionable,
                recommendation=recommendation,
                detail={
                    "confidence_buckets": bucket_detail,
                    "is_monotonically_increasing": is_monotonic,
                    "scored_trade_count": scored_count,
                    "overall_win_rate": str(overall_wr),
                },
            )

            logger.info(
                "indicator_accuracy_analyzed",
                account_id=account_id,
                scored_trades=scored_count,
                is_monotonic=is_monotonic,
            )

        except Exception as exc:
            logger.error(
                "indicator_accuracy_analysis_failed",
                account_id=account_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Phase 2: Confidence Calibration
    # ------------------------------------------------------------------

    async def _analyze_confidence_calibration(
        self, account_id: str, trades: list[dict]
    ) -> None:
        """
        Compare average confidence of winning trades vs losing trades.
        Calculate calibration score (how well confidence predicts outcomes).
        Store insight.
        """
        try:
            win_confidences: list[Decimal] = []
            loss_confidences: list[Decimal] = []

            for trade in trades:
                confidence = self._to_decimal(trade.get("confidence_score"))
                if confidence is None:
                    continue

                outcome = trade.get("outcome", "")
                if outcome == "WIN":
                    win_confidences.append(confidence)
                elif outcome == "LOSS":
                    loss_confidences.append(confidence)

            if not win_confidences or not loss_confidences:
                logger.debug(
                    "confidence_calibration_insufficient_data",
                    account_id=account_id,
                    wins=len(win_confidences),
                    losses=len(loss_confidences),
                )
                return

            avg_win_confidence = sum(win_confidences) / Decimal(str(len(win_confidences)))
            avg_loss_confidence = sum(loss_confidences) / Decimal(str(len(loss_confidences)))

            # Calibration score: the gap between avg winning confidence and avg losing
            # confidence. Higher is better -- means confidence is predictive.
            # Range roughly -1 to +1. Positive = wins have higher confidence.
            calibration_gap = avg_win_confidence - avg_loss_confidence

            # Normalize to a 0-1 score: 0.5 + gap/2 (clamped)
            raw_score = Decimal("0.5") + calibration_gap / Decimal("2")
            calibration_score = max(Decimal("0"), min(Decimal("1"), raw_score)).quantize(
                Decimal("0.0001")
            )

            period_start, period_end = self._date_range(trades)

            # Generate recommendation
            is_actionable = False
            recommendation = None
            if calibration_gap <= Decimal("0"):
                recommendation = (
                    "Losing trades have equal or higher confidence than winning trades. "
                    "The AI confidence signal is not predictive. Review prompt engineering "
                    "and confidence adjustment pipeline."
                )
                is_actionable = True
            elif calibration_gap < Decimal("0.05"):
                recommendation = (
                    "Minimal confidence gap between wins and losses. "
                    "Confidence is weakly predictive. Consider adding more "
                    "confirmation signals to improve calibration."
                )
                is_actionable = True
            else:
                recommendation = (
                    f"Confidence is predictive: winning trades average "
                    f"{avg_win_confidence.quantize(Decimal('0.0001'))} vs "
                    f"{avg_loss_confidence.quantize(Decimal('0.0001'))} for losses."
                )

            total_scored = len(win_confidences) + len(loss_confidences)

            await self._store_insight(
                account_id=account_id,
                insight_type="CONFIDENCE_CALIBRATION",
                metric_name="calibration_score",
                metric_value=calibration_score,
                sample_size=total_scored,
                period_start=period_start,
                period_end=period_end,
                benchmark_value=Decimal("0.5500"),  # a well-calibrated system target
                deviation_pct=(
                    ((calibration_score - Decimal("0.55")) / Decimal("0.55") * Decimal("100")).quantize(
                        Decimal("0.01")
                    )
                ),
                is_actionable=is_actionable,
                recommendation=recommendation,
                detail={
                    "avg_win_confidence": str(avg_win_confidence.quantize(Decimal("0.0001"))),
                    "avg_loss_confidence": str(avg_loss_confidence.quantize(Decimal("0.0001"))),
                    "calibration_gap": str(calibration_gap.quantize(Decimal("0.0001"))),
                    "win_sample_size": len(win_confidences),
                    "loss_sample_size": len(loss_confidences),
                },
            )

            logger.info(
                "confidence_calibration_analyzed",
                account_id=account_id,
                calibration_score=str(calibration_score),
                calibration_gap=str(calibration_gap.quantize(Decimal("0.0001"))),
                win_count=len(win_confidences),
                loss_count=len(loss_confidences),
            )

        except Exception as exc:
            logger.error(
                "confidence_calibration_analysis_failed",
                account_id=account_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Phase 2: Prompt Patterns (overall summary stats)
    # ------------------------------------------------------------------

    async def _analyze_prompt_patterns(
        self, account_id: str, trades: list[dict]
    ) -> None:
        """
        Calculate overall stats: total trades, win rate, avg pips,
        profit factor. Store as a summary insight.
        """
        try:
            total = len(trades)
            if total == 0:
                return

            wins = 0
            losses = 0
            total_win_pips = Decimal("0")
            total_loss_pips = Decimal("0")
            total_pnl_pips = Decimal("0")
            total_pnl_usd = Decimal("0")

            for trade in trades:
                outcome = trade.get("outcome", "")
                pnl_pips = self._to_decimal(trade.get("pnl_pips")) or Decimal("0")
                pnl_usd = self._to_decimal(trade.get("pnl_usd")) or Decimal("0")

                total_pnl_pips += pnl_pips
                total_pnl_usd += pnl_usd

                if outcome == "WIN":
                    wins += 1
                    total_win_pips += pnl_pips
                elif outcome == "LOSS":
                    losses += 1
                    total_loss_pips += abs(pnl_pips)

            win_rate = (
                Decimal(str(wins)) / Decimal(str(total))
                if total > 0
                else Decimal("0")
            ).quantize(Decimal("0.0001"))

            avg_pips = (total_pnl_pips / Decimal(str(total))).quantize(Decimal("0.01"))

            # Profit factor = gross wins / gross losses
            profit_factor = (
                (total_win_pips / total_loss_pips).quantize(Decimal("0.0001"))
                if total_loss_pips > 0
                else Decimal("999.9999")  # no losses means infinite profit factor, cap it
            )

            avg_win_pips = (
                (total_win_pips / Decimal(str(wins))).quantize(Decimal("0.01"))
                if wins > 0
                else Decimal("0")
            )
            avg_loss_pips = (
                (total_loss_pips / Decimal(str(losses))).quantize(Decimal("0.01"))
                if losses > 0
                else Decimal("0")
            )

            period_start, period_end = self._date_range(trades)

            recommendation = None
            is_actionable = False
            if profit_factor < Decimal("1"):
                recommendation = (
                    f"Profit factor is below 1.0 ({profit_factor}). "
                    f"The system is losing money overall. Review signal quality "
                    f"and risk parameters."
                )
                is_actionable = True
            elif profit_factor < Decimal("1.5"):
                recommendation = (
                    f"Profit factor ({profit_factor}) is marginal. "
                    f"Target 1.5+ for robust profitability."
                )
                is_actionable = True
            else:
                recommendation = (
                    f"Profit factor ({profit_factor}) is healthy."
                )

            await self._store_insight(
                account_id=account_id,
                insight_type="RISK_EFFICIENCY",
                metric_name="profit_factor",
                metric_value=profit_factor,
                sample_size=total,
                period_start=period_start,
                period_end=period_end,
                benchmark_value=Decimal("1.5000"),
                deviation_pct=(
                    ((profit_factor - Decimal("1.5")) / Decimal("1.5") * Decimal("100")).quantize(
                        Decimal("0.01")
                    )
                ),
                is_actionable=is_actionable,
                recommendation=recommendation,
                detail={
                    "total_trades": total,
                    "wins": wins,
                    "losses": losses,
                    "breakevens": total - wins - losses,
                    "win_rate": str(win_rate),
                    "avg_pnl_pips": str(avg_pips),
                    "avg_win_pips": str(avg_win_pips),
                    "avg_loss_pips": str(avg_loss_pips),
                    "total_pnl_pips": str(total_pnl_pips.quantize(Decimal("0.01"))),
                    "total_pnl_usd": str(total_pnl_usd.quantize(Decimal("0.01"))),
                    "profit_factor": str(profit_factor),
                },
            )

            logger.info(
                "prompt_patterns_analyzed",
                account_id=account_id,
                total_trades=total,
                win_rate=str(win_rate),
                profit_factor=str(profit_factor),
            )

        except Exception as exc:
            logger.error(
                "prompt_patterns_analysis_failed",
                account_id=account_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Phase 3: Self-optimisation methods
    # ------------------------------------------------------------------

    async def _evolve_prompt_instructions(
        self, account_id: str, trades: list[dict]
    ) -> None:
        """
        Analyse which pair+direction combos correlate with wins vs losses.
        Combos with <30% win rate and >5 trades generate a warning insight.
        Combos with >60% win rate and >5 trades generate a positive insight.
        Insights are written to performance_insights with
        insight_type="prompt_evolution".
        """
        MIN_COMBO_TRADES = 5
        LOW_WIN_RATE_THRESHOLD = Decimal("0.30")
        HIGH_WIN_RATE_THRESHOLD = Decimal("0.60")

        try:
            combo_stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"wins": 0, "losses": 0, "total": 0}
            )

            for trade in trades:
                pair = trade.get("pair")
                direction = trade.get("direction")
                if not pair or not direction:
                    continue
                key = f"{pair}_{direction}"
                combo_stats[key]["total"] += 1
                outcome = trade.get("outcome", "")
                if outcome == "WIN":
                    combo_stats[key]["wins"] += 1
                elif outcome == "LOSS":
                    combo_stats[key]["losses"] += 1

            if not combo_stats:
                logger.debug("evolve_prompt_instructions_no_data", account_id=account_id)
                return

            period_start, period_end = self._date_range(trades)
            insights_saved = 0

            for key, stats in combo_stats.items():
                total = stats["total"]
                if total <= MIN_COMBO_TRADES:
                    continue

                win_rate = Decimal(str(stats["wins"])) / Decimal(str(total))
                win_rate_q = win_rate.quantize(Decimal("0.0001"))
                pair_dir = key.replace("_", " ")

                if win_rate < LOW_WIN_RATE_THRESHOLD:
                    recommendation = (
                        f"{pair_dir}: only {win_rate_q} win rate over {total} trades. "
                        f"Consider filtering out this pair/direction combination in the prompt."
                    )
                    is_actionable = True
                elif win_rate > HIGH_WIN_RATE_THRESHOLD:
                    recommendation = (
                        f"{pair_dir}: strong {win_rate_q} win rate over {total} trades. "
                        f"Emphasise this pair/direction combination in the prompt."
                    )
                    is_actionable = False
                else:
                    continue  # neutral — no insight needed

                try:
                    await self._store_insight(
                        account_id=account_id,
                        insight_type="prompt_evolution",
                        metric_name=f"combo_{key}_win_rate",
                        metric_value=win_rate_q,
                        sample_size=total,
                        period_start=period_start,
                        period_end=period_end,
                        pair=key.split("_")[0],
                        is_actionable=is_actionable,
                        recommendation=recommendation,
                        detail={
                            "pair": key.split("_")[0],
                            "direction": key.split("_", 1)[1] if "_" in key else "",
                            "wins": stats["wins"],
                            "losses": stats["losses"],
                            "total": total,
                            "win_rate": str(win_rate_q),
                        },
                    )
                    insights_saved += 1
                except Exception as exc:
                    logger.warning(
                        "evolve_prompt_instructions_store_failed",
                        account_id=account_id,
                        combo=key,
                        error=str(exc),
                    )

            logger.info(
                "evolve_prompt_instructions_completed",
                account_id=account_id,
                combos_evaluated=len(combo_stats),
                insights_saved=insights_saved,
            )

        except Exception as exc:
            logger.error(
                "evolve_prompt_instructions_failed",
                account_id=account_id,
                error=str(exc),
            )

    async def _update_session_filters(
        self, account_id: str, trades: list[dict]
    ) -> None:
        """
        Analyse trading hour (UTC) performance.
        Any hour with >5 trades and <25% win rate gets an insight recommending
        it be blocked.
        Insights written to performance_insights with
        insight_type="session_filter".
        """
        MIN_HOUR_TRADES = 5
        BLOCK_THRESHOLD = Decimal("0.25")

        try:
            hour_stats: dict[int, dict[str, int]] = defaultdict(
                lambda: {"wins": 0, "losses": 0, "total": 0}
            )

            for trade in trades:
                opened_at = trade.get("opened_at")
                if not opened_at:
                    continue
                dt = parse_iso_utc(opened_at)
                if dt is None:
                    continue

                hour = dt.hour
                hour_stats[hour]["total"] += 1
                outcome = trade.get("outcome", "")
                if outcome == "WIN":
                    hour_stats[hour]["wins"] += 1
                elif outcome == "LOSS":
                    hour_stats[hour]["losses"] += 1

            if not hour_stats:
                logger.debug("update_session_filters_no_data", account_id=account_id)
                return

            period_start, period_end = self._date_range(trades)
            insights_saved = 0

            for hour, stats in sorted(hour_stats.items()):
                total = stats["total"]
                if total <= MIN_HOUR_TRADES:
                    continue

                win_rate = Decimal(str(stats["wins"])) / Decimal(str(total))
                win_rate_q = win_rate.quantize(Decimal("0.0001"))

                if win_rate >= BLOCK_THRESHOLD:
                    continue  # acceptable performance — no insight

                recommendation = (
                    f"Hour {hour:02d}:00 UTC has only {win_rate_q} win rate over "
                    f"{total} trades. Recommend blocking this hour in session filters."
                )

                try:
                    await self._store_insight(
                        account_id=account_id,
                        insight_type="session_filter",
                        metric_name=f"hour_{hour}_win_rate",
                        metric_value=win_rate_q,
                        sample_size=total,
                        period_start=period_start,
                        period_end=period_end,
                        session=f"{hour:02d}:00",
                        is_actionable=True,
                        recommendation=recommendation,
                        detail={
                            "hour_utc": hour,
                            "wins": stats["wins"],
                            "losses": stats["losses"],
                            "total": total,
                            "win_rate": str(win_rate_q),
                        },
                    )
                    insights_saved += 1
                except Exception as exc:
                    logger.warning(
                        "update_session_filters_store_failed",
                        account_id=account_id,
                        hour=hour,
                        error=str(exc),
                    )

            logger.info(
                "update_session_filters_completed",
                account_id=account_id,
                hours_evaluated=len(hour_stats),
                insights_saved=insights_saved,
            )

        except Exception as exc:
            logger.error(
                "update_session_filters_failed",
                account_id=account_id,
                error=str(exc),
            )

    async def _update_confidence_thresholds(
        self, account_id: str, trades: list[dict]
    ) -> None:
        """
        Bucket trades into confidence ranges: 60-70, 70-80, 80-90, 90-100.
        For each bucket with >5 trades, compute win rate and net P&L.
        If a bucket has <30% win rate, save an insight recommending that range
        be avoided.
        Insights written to performance_insights with
        insight_type="confidence_calibration".
        """
        # Aronson (2007) minimum for statistical significance.
        # Below this threshold, a "bad" bucket is indistinguishable from noise
        # in a low-frequency system (Codex review 2026-04-27 finding #3).
        MIN_BUCKET_TRADES = 30
        LOW_WIN_RATE_THRESHOLD = Decimal("0.30")

        # Buckets defined as (label, low_inclusive, high_exclusive) in 0-100 scale
        THRESHOLD_BUCKETS: list[tuple[str, Decimal, Decimal]] = [
            ("60-70", Decimal("60"), Decimal("70")),
            ("70-80", Decimal("70"), Decimal("80")),
            ("80-90", Decimal("80"), Decimal("90")),
            ("90-100", Decimal("90"), Decimal("101")),
        ]

        try:
            bucket_stats: dict[str, dict[str, Any]] = {
                label: {"wins": 0, "losses": 0, "total": 0, "net_pnl_usd": Decimal("0")}
                for label, _, _ in THRESHOLD_BUCKETS
            }

            for trade in trades:
                # Accept both "confidence" (0-100) and "confidence_score" (0-1)
                raw_conf = trade.get("confidence") or trade.get("confidence_score")
                confidence = self._to_decimal(raw_conf)
                if confidence is None:
                    continue

                # Normalise: if stored as 0-1 fraction, scale to 0-100
                if confidence <= Decimal("1"):
                    confidence = confidence * Decimal("100")

                outcome = trade.get("outcome", "")
                pnl_usd = self._to_decimal(trade.get("pnl_usd")) or Decimal("0")

                for label, low, high in THRESHOLD_BUCKETS:
                    if low <= confidence < high:
                        bucket_stats[label]["total"] += 1
                        bucket_stats[label]["net_pnl_usd"] += pnl_usd
                        if outcome == "WIN":
                            bucket_stats[label]["wins"] += 1
                        elif outcome == "LOSS":
                            bucket_stats[label]["losses"] += 1
                        break

            period_start, period_end = self._date_range(trades)
            insights_saved = 0

            for label, low, high in THRESHOLD_BUCKETS:
                stats = bucket_stats[label]
                total = stats["total"]
                if total <= MIN_BUCKET_TRADES:
                    continue

                win_rate = Decimal(str(stats["wins"])) / Decimal(str(total))
                win_rate_q = win_rate.quantize(Decimal("0.0001"))
                net_pnl_usd_q = stats["net_pnl_usd"].quantize(Decimal("0.01"))

                if win_rate >= LOW_WIN_RATE_THRESHOLD:
                    continue  # performing adequately — no insight needed

                # Wilson 95% CI — guards against acting on noise
                from math import sqrt as _sqrt
                z = 1.96
                n = total
                p = float(win_rate)
                ci_lo = (p + z*z/(2*n) - z*_sqrt((p*(1-p) + z*z/(4*n))/n)) / (1 + z*z/n)
                ci_hi = (p + z*z/(2*n) + z*_sqrt((p*(1-p) + z*z/(4*n))/n)) / (1 + z*z/n)
                recommendation = (
                    f"Confidence range {label}: {win_rate_q} win rate over {total} trades "
                    f"(95% CI [{ci_lo:.2f}, {ci_hi:.2f}], net P&L: ${net_pnl_usd_q}). "
                    f"Advisory only — monitor for further deterioration."
                )

                try:
                    await self._store_insight(
                        account_id=account_id,
                        insight_type="confidence_calibration",
                        metric_name=f"confidence_bucket_{label}_win_rate",
                        metric_value=win_rate_q,
                        sample_size=total,
                        period_start=period_start,
                        period_end=period_end,
                        is_actionable=False,
                        recommendation=recommendation,
                        detail={
                            "confidence_range": label,
                            "wins": stats["wins"],
                            "losses": stats["losses"],
                            "total": total,
                            "win_rate": str(win_rate_q),
                            "net_pnl_usd": str(net_pnl_usd_q),
                        },
                    )
                    insights_saved += 1
                except Exception as exc:
                    logger.warning(
                        "update_confidence_thresholds_store_failed",
                        account_id=account_id,
                        bucket=label,
                        error=str(exc),
                    )

            logger.info(
                "update_confidence_thresholds_completed",
                account_id=account_id,
                insights_saved=insights_saved,
            )

        except Exception as exc:
            logger.error(
                "update_confidence_thresholds_failed",
                account_id=account_id,
                error=str(exc),
            )
