"""
SA-04: Intelligence Subagent
==============================
Generates a weekly macro intelligence report via Claude. Pulls upcoming
economic events from data_engine/calendar.py, caches reports in the
intelligence_reports table (one row per ISO week), and surfaces them to
the dashboard. Covers per-pair outlook, key events, performance review,
and one strategic recommendation.
"""

import json
from datetime import datetime, timezone
from typing import Any, TypedDict

from ..infrastructure.alert_service import AlertService
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger
from .base_agent import BaseSubagent

logger = get_logger(__name__)


class IntelligenceContext(TypedDict, total=False):
    """Expected shape of the context dict passed to ``IntelligenceSubagent.run``.

    All keys are optional (``total=False``) — the subagent treats missing
    keys as defaults. Annotation-only; runtime is a plain ``dict``.
    """

    account_id: str
    recent_trades: list[dict[str, Any]]
    account_summary: dict[str, Any]
    pairs: list[str]


class IntelligenceReport(TypedDict, total=False):
    """Return shape of ``IntelligenceSubagent.run``. Empty dict on error."""

    report: str
    generated_at: str

INTELLIGENCE_SYSTEM_PROMPT = """You are a senior forex market analyst for Lumitrade, an AI-powered forex trading system.
You produce concise, actionable weekly intelligence reports for a systematic trader.

Your report MUST contain these four sections:
1. **Market Outlook** — For each currency pair provided, give a 2-3 sentence directional outlook with key levels.
2. **Key Economic Events** — List the most important upcoming events (central bank decisions, NFP, CPI, GDP) that could move the pairs.
3. **Performance Review** — Analyze the recent trade results provided and identify patterns (win rate, best/worst pair, common entry issues).
4. **Strategic Recommendation** — One specific, actionable recommendation to improve trading performance this week.

Keep the total report under 800 words. Be direct and professional. No fluff."""


class IntelligenceSubagent(BaseSubagent):
    """Generates weekly macro intelligence reports via Claude."""

    max_tokens = 2000
    timeout_seconds = 45

    def __init__(self, config, db: DatabaseClient, alerts: AlertService):
        super().__init__(config)
        self.db = db
        self.alerts = alerts

    async def run(self, context: dict) -> dict:
        """Generate a weekly intelligence report.

        Expected context keys:
            - recent_trades: list[dict] — last 10-20 closed trades
            - account_summary: dict — balance, equity, margin_used, open_positions
            - pairs: list[str] — active trading pairs (e.g. ["EUR_USD", "GBP_USD", "USD_JPY"])

        Returns:
            {"report": str, "generated_at": str} on success, {} on error.
        """
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        account_id = context.get("account_id", "default")

        # Check DB for a cached report from today
        try:
            cached = await self.db.select(
                "intelligence_reports",
                {"account_id": account_id, "report_date": today_str},
                limit=1,
            )
            if cached:
                logger.info("intelligence_report_cache_hit", report_date=today_str)
                return {
                    "report": cached[0]["report"],
                    "generated_at": cached[0]["generated_at"],
                }
        except Exception as e:
            logger.warning("intelligence_cache_read_error", error=str(e))

        recent_trades = context.get("recent_trades", [])
        account_summary = context.get("account_summary", {})
        pairs = context.get("pairs", ["EUR_USD", "GBP_USD", "USD_JPY"])

        user_prompt = await self._build_user_prompt(recent_trades, account_summary, pairs)

        try:
            response_text = await self._call_claude(
                system=INTELLIGENCE_SYSTEM_PROMPT,
                user=user_prompt,
            )

            if not response_text:
                logger.warning("intelligence_empty_response")
                return {}

            generated_at = datetime.now(timezone.utc).isoformat()

            # Persist report to DB for caching and historical access
            try:
                await self.db.upsert(
                    "intelligence_reports",
                    {
                        "account_id": account_id,
                        "report_date": today_str,
                        "report": response_text,
                        "generated_at": generated_at,
                    },
                )
            except Exception as e:
                logger.warning("intelligence_report_save_error", error=str(e))

            logger.info(
                "intelligence_report_generated",
                pairs_count=len(pairs),
                trades_analyzed=len(recent_trades),
                report_length=len(response_text),
            )

            return {
                "report": response_text,
                "generated_at": generated_at,
            }

        except Exception as e:
            logger.error("intelligence_subagent_error", error=str(e))
            return {}

    async def _build_user_prompt(
        self,
        recent_trades: list,
        account_summary: dict,
        pairs: list,
    ) -> str:
        """Build the user prompt with trade data, account context, and calendar events."""
        sections = []

        sections.append(f"Active pairs: {', '.join(pairs)}")

        if account_summary:
            sections.append(
                f"Account: balance={account_summary.get('balance', 'N/A')}, "
                f"equity={account_summary.get('equity', 'N/A')}, "
                f"open_positions={account_summary.get('open_positions', 0)}"
            )

        if recent_trades:
            trade_lines = []
            for t in recent_trades[:20]:
                trade_lines.append(
                    f"  {t.get('pair', '?')} {t.get('direction', '?')} "
                    f"outcome={t.get('outcome', '?')} "
                    f"pnl={t.get('realized_pnl', '?')} "
                    f"closed={t.get('closed_at', '?')}"
                )
            sections.append("Recent trades:\n" + "\n".join(trade_lines))
        else:
            sections.append("Recent trades: No closed trades yet.")

        # Fetch upcoming economic calendar events
        try:
            events = await self.db.select("economic_calendar", {}, order="event_time", limit=10)
            if events:
                event_lines = [
                    f"  {e.get('event_time', '')} — {e.get('currency', '')} {e.get('event_name', '')}"
                    for e in events
                ]
                sections.append("Upcoming economic events:\n" + "\n".join(event_lines))
        except Exception:
            pass  # Calendar table may not exist yet

        sections.append(
            "Generate the weekly intelligence report now. "
            "Today is " + datetime.now(timezone.utc).strftime("%Y-%m-%d") + "."
        )

        return "\n\n".join(sections)
