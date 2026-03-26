"""
Lumitrade Event Publisher
===========================
Publishes agent activity events to the agent_events Supabase table
for the Mission Control live feed on the dashboard.

All publish calls are fire-and-forget — never block trading operations.
"""

import asyncio
from datetime import datetime, timezone

from .db import DatabaseClient
from .secure_logger import get_logger

logger = get_logger(__name__)

TABLE = "agent_events"


class EventPublisher:
    """Publish agent activity events to Supabase for Mission Control feed."""

    def __init__(self, db: DatabaseClient, account_id: str):
        self._db = db
        self._account_id = account_id

    def publish(
        self,
        agent: str,
        event_type: str,
        title: str,
        detail: str = "",
        pair: str = "",
        severity: str = "INFO",
        metadata: dict | None = None,
    ) -> None:
        """
        Fire-and-forget event publish. Never blocks the caller.

        Args:
            agent: Agent identifier (SA-01, RISK_ENGINE, CLAUDE, etc.)
            event_type: Event category (SCAN_START, BRIEFING, SIGNAL, etc.)
            title: Short one-line summary
            detail: Full detail text
            pair: Currency pair if applicable
            severity: INFO, WARNING, ERROR, SUCCESS
            metadata: Additional structured data
        """
        asyncio.create_task(
            self._write(agent, event_type, title, detail, pair, severity, metadata),
            name=f"event_{agent}_{event_type}",
        )

    async def _write(
        self,
        agent: str,
        event_type: str,
        title: str,
        detail: str,
        pair: str,
        severity: str,
        metadata: dict | None,
    ) -> None:
        """Async insert to agent_events table."""
        try:
            await self._db.insert(TABLE, {
                "account_id": self._account_id,
                "agent": agent,
                "event_type": event_type,
                "pair": pair,
                "severity": severity,
                "title": title,
                "detail": detail,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            # Never crash — Mission Control is observability, not critical path
            logger.debug("event_publish_failed", agent=agent, error=str(e))
