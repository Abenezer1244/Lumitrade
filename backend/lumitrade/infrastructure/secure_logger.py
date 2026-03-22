"""
Lumitrade Secure Logger
=========================
Structured JSON logging with sensitive data scrubbing.
All log output passes through scrub patterns before rendering.
Per SS Section 7.1 and BDS Section 8.1.
"""

import logging
import re
from typing import Any

import structlog

# ── Scrub patterns — order matters (most specific first) ────────
SCRUB_PATTERNS: list[tuple[str, str]] = [
    # OANDA Bearer tokens
    (r"Bearer\s+[A-Za-z0-9\-._]{10,}", "Bearer [REDACTED]"),
    # Anthropic API keys (sk-ant- prefix)
    (r"sk-ant-[A-Za-z0-9\-._]{10,}", "[REDACTED_ANTHROPIC_KEY]"),
    # SendGrid keys (SG. prefix)
    (r"SG\.[A-Za-z0-9\-._]{10,}", "[REDACTED_SENDGRID_KEY]"),
    # Telnyx keys (KEY0 prefix)
    (r"KEY0[A-Za-z0-9\-._]{10,}", "[REDACTED_TELNYX_KEY]"),
    # API key patterns in key=value form
    (
        r"(?i)(api[_-]?key|apikey|api_secret)[\s:='\"]+[A-Za-z0-9\-._]{10,}",
        "api_key=[REDACTED]",
    ),
    # Password patterns
    (r"(?i)(password|passwd|pwd)[\s:='\"]+\S+", "password=[REDACTED]"),
    # Generic long base64-like tokens (40+ chars)
    (
        r"(?<![A-Za-z0-9])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9])",
        "[REDACTED_TOKEN]",
    ),
    # Phone numbers (E.164 format)
    (r"\+1\d{10}", "+1[REDACTED]"),
    # Email addresses
    (
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        "[REDACTED_EMAIL]",
    ),
]

_compiled_patterns = [
    (re.compile(p, re.IGNORECASE), r) for p, r in SCRUB_PATTERNS
]


def scrub_value(value: str) -> str:
    """Apply all scrub patterns to a string value."""
    for pattern, replacement in _compiled_patterns:
        value = pattern.sub(replacement, value)
    return value


def _scrub_processor(
    logger: Any, method: str, event_dict: dict
) -> dict:
    """structlog processor that scrubs all string values recursively."""

    def scrub_recursive(obj: Any) -> Any:
        if isinstance(obj, str):
            return scrub_value(obj)
        elif isinstance(obj, dict):
            return {k: scrub_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return type(obj)(scrub_recursive(i) for i in obj)
        return obj

    return scrub_recursive(event_dict)


def configure_logging(log_level: str = "INFO") -> None:
    """Call once at startup from main.py."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _scrub_processor,  # SCRUB BEFORE RENDERING
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=level)


def get_logger(name: str):
    """Get a structured logger for the given module name."""
    return structlog.get_logger(name)
