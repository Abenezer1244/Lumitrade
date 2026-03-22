"""
Security Validation Tests
===========================
Per SS Section 7.2 — verify sensitive data scrubbing, no TLS bypass,
no hardcoded secrets in the codebase.
SEC-001 through SEC-009.
"""

import os
import subprocess

import pytest

from lumitrade.infrastructure.secure_logger import _scrub_processor, scrub_value


@pytest.mark.security
class TestCredentialScrubbing:
    """SEC-001 through SEC-006: verify all credential patterns are scrubbed."""

    def test_sec_001_bearer_token_scrubbed(self):
        """SEC-001: OANDA Bearer tokens must be fully redacted."""
        raw = "Authorization: Bearer sk-oanda-abc123def456ghi789jkl012mno345"
        result = scrub_value(raw)
        assert "Bearer [REDACTED]" in result
        assert "sk-oanda-abc123" not in result

    def test_sec_002_anthropic_key_scrubbed(self):
        """SEC-002: Anthropic API keys (sk-ant-*) must be redacted."""
        raw = "Using key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
        result = scrub_value(raw)
        assert "[REDACTED_ANTHROPIC_KEY]" in result
        assert "sk-ant-api03" not in result

    def test_sec_003_sendgrid_key_scrubbed(self):
        """SEC-003: SendGrid keys (SG.*) must be redacted."""
        raw = "Sending email with SG.abcdefghij.klmnopqrstuvwxyz0123456789"
        result = scrub_value(raw)
        assert "[REDACTED_SENDGRID_KEY]" in result
        assert "SG.abcdefghij" not in result

    def test_sec_004_email_address_scrubbed(self):
        """SEC-004: Email addresses must be redacted in logs."""
        raw = "Alert sent to trader@example.com for margin call"
        result = scrub_value(raw)
        assert "[REDACTED_EMAIL]" in result
        assert "trader@example.com" not in result

    def test_sec_005_phone_number_scrubbed(self):
        """SEC-005: E.164 phone numbers must be partially redacted."""
        raw = "SMS alert sent to +12065551234"
        result = scrub_value(raw)
        assert "+1[REDACTED]" in result
        assert "2065551234" not in result

    def test_sec_006_normal_trading_text_preserved(self):
        """SEC-006: Normal trading messages must not trigger false positives."""
        messages = [
            "EUR/USD BUY confidence=0.82",
            "Position sized: 3000 units at 1.0842",
            "RSI(14) = 65.3, MACD histogram positive",
            "Take profit hit at 1.0900, +58 pips",
            "Daily P&L: +$12.50 (0.42%)",
        ]
        for msg in messages:
            result = scrub_value(msg)
            assert result == msg, f"False positive scrub on: {msg!r}"


@pytest.mark.security
class TestNestedScrubbing:
    """SEC-007: verify recursive scrubbing via _scrub_processor."""

    def test_sec_007_nested_dict_values_scrubbed(self):
        """SEC-007: Nested dict/list values must be scrubbed recursively."""
        event = {
            "event": "outbound_request",
            "headers": {
                "Authorization": "Bearer sk-oanda-abc123def456ghi789jkl012mno345",
                "X-Custom": "normal header value",
            },
            "recipients": [
                "admin@lumitrade.com",
                "alerts@lumitrade.com",
            ],
            "phone": "+12065559876",
            "count": 3,
            "rate": 1.0842,
        }
        result = _scrub_processor(None, None, event)

        # Bearer token scrubbed in nested dict
        assert "Bearer [REDACTED]" in result["headers"]["Authorization"]
        assert "sk-oanda" not in result["headers"]["Authorization"]

        # Normal header preserved
        assert result["headers"]["X-Custom"] == "normal header value"

        # Emails scrubbed in list
        for email in result["recipients"]:
            assert "[REDACTED_EMAIL]" in email

        # Phone scrubbed
        assert "+1[REDACTED]" in result["phone"]

        # Non-string values preserved
        assert result["count"] == 3
        assert result["rate"] == 1.0842

    def test_sec_007b_tuple_values_scrubbed(self):
        """SEC-007b: Tuple values should also be scrubbed recursively."""
        event = {
            "event": "test",
            "contacts": ("user@test.com", "+12065551111"),
        }
        result = _scrub_processor(None, None, event)
        assert isinstance(result["contacts"], tuple)
        assert "[REDACTED_EMAIL]" in result["contacts"][0]
        assert "+1[REDACTED]" in result["contacts"][1]


@pytest.mark.security
class TestCodebaseSecurity:
    """SEC-008 and SEC-009: static analysis of the codebase for security issues."""

    @pytest.fixture
    def backend_root(self):
        """Return the absolute path to the backend source directory."""
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "lumitrade")
        )

    def test_sec_008_no_verify_false_in_codebase(self, backend_root):
        """SEC-008: verify=False must never appear in production code (TLS bypass)."""
        result = subprocess.run(
            ["grep", "-rn", "verify=False", backend_root],
            capture_output=True,
            text=True,
        )
        matches = [
            line
            for line in result.stdout.strip().splitlines()
            if line and not any(
                skip in line
                for skip in [
                    "__pycache__", ".pyc", "test_", "conftest",
                    "# ", "NEVER set", "Per SS",  # Allow doc comments
                ]
            )
        ]
        assert matches == [], (
            "Found verify=False in production code:\n" + "\n".join(matches)
        )

    def test_sec_009_no_hardcoded_api_keys(self, backend_root):
        """SEC-009: No hardcoded API keys in source files."""
        dangerous_patterns = [
            "sk-ant-api",  # Anthropic key prefix with real value
            "SG.real",     # SendGrid key with real prefix
        ]
        for pattern in dangerous_patterns:
            result = subprocess.run(
                ["grep", "-rn", pattern, backend_root],
                capture_output=True,
                text=True,
            )
            matches = [
                line
                for line in result.stdout.strip().splitlines()
                if line
                and not any(
                    skip in line
                    for skip in [
                        "__pycache__",
                        ".pyc",
                        "test_",
                        "conftest",
                        "SCRUB_PATTERNS",
                        "# Anthropic",
                        "# SendGrid",
                    ]
                )
            ]
            assert matches == [], (
                f"Possible hardcoded key pattern '{pattern}' found:\n"
                + "\n".join(matches)
            )
