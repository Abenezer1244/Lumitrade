"""
Lumitrade Alert Service
=========================
SMS via Telnyx (raw httpx). Email via SendGrid.
All sends logged to alerts_log table.
Per Master Prompt Pattern 6.
"""

import asyncio

import httpx
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from ..config import LumitradeConfig
from .secure_logger import get_logger

logger = get_logger(__name__)

TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"


class AlertService:
    """Delivers SMS via Telnyx and email via SendGrid. All sends logged."""

    def __init__(self, config: LumitradeConfig, db):
        self.config = config
        self.db = db

    async def send_info(self, message: str):
        """Low-priority: queue for daily digest. No immediate SMS."""
        await self._log_alert("INFO", message, channel="email_queue")

    async def send_warning(self, message: str):
        """Medium-priority: send immediate email."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_email, "WARNING", message)
        await self._log_alert("WARNING", message, channel="email")

    async def send_error(self, message: str):
        """High-priority: send SMS immediately."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sms_sync, message)
        await self._log_alert("ERROR", message, channel="sms")

    async def send_critical(self, message: str):
        """Critical: SMS + email simultaneously."""
        loop = asyncio.get_event_loop()
        await asyncio.gather(
            loop.run_in_executor(
                None, self._send_sms_sync, f"CRITICAL: {message}"
            ),
            loop.run_in_executor(None, self._send_email, "CRITICAL", message),
        )
        await self._log_alert("CRITICAL", message, channel="sms+email")

    def _send_sms_sync(self, body: str):
        """Synchronous Telnyx SMS via httpx (run in executor)."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    TELNYX_MESSAGES_URL,
                    headers={
                        "Authorization": f"Bearer {self.config.telnyx_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": self.config.telnyx_from_number,
                        "to": self.config.alert_sms_to,
                        "text": f"[LUMITRADE] {body}",
                    },
                )
                response.raise_for_status()
                msg_id = response.json().get("data", {}).get("id", "unknown")
                logger.info("sms_sent", message_id=msg_id)
        except Exception as e:
            logger.error("sms_send_failed", error=str(e))

    def _send_email(self, level: str, body: str):
        """Send email via SendGrid."""
        try:
            sg = SendGridAPIClient(self.config.sendgrid_api_key)
            mail = Mail(
                from_email="alerts@lumitrade.app",
                to_emails=self.config.alert_email_to,
                subject=f"[Lumitrade {level}] {body[:80]}",
                plain_text_content=body,
            )
            sg.send(mail)
            logger.info("email_sent", level=level)
        except Exception as e:
            logger.error("email_send_failed", error=str(e))

    async def _log_alert(self, level: str, message: str, channel: str):
        from datetime import datetime, timezone

        try:
            await self.db.insert(
                "alerts_log",
                {
                    "level": level,
                    "message": message,
                    "channel": channel,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            # Alert logging should never crash the engine
            logger.warning(
                "alert_log_failed",
                level=level,
                error=str(e),
            )
