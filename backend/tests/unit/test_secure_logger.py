"""
Secure Logger Tests
=====================
Per SS Section 7.2 — verify all scrub patterns work correctly.
"""

import pytest

from lumitrade.infrastructure.secure_logger import scrub_value, _scrub_processor


class TestScrubValue:
    """Test individual scrub patterns."""

    def test_scrubs_bearer_token(self):
        msg = "Authorization: Bearer sk-oanda-abc123def456ghi789jkl012mno345"
        result = scrub_value(msg)
        assert "Bearer [REDACTED]" in result
        assert "sk-oanda" not in result

    def test_scrubs_anthropic_key(self):
        msg = "Using key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
        result = scrub_value(msg)
        assert "[REDACTED_ANTHROPIC_KEY]" in result
        assert "sk-ant" not in result

    def test_scrubs_api_key_pattern(self):
        msg = "api_key=my-secret-key-1234567890abcdef"
        result = scrub_value(msg)
        assert "api_key=[REDACTED]" in result
        assert "my-secret-key" not in result

    def test_preserves_normal_text(self):
        msg = "Signal generated: EUR/USD BUY confidence=0.82"
        result = scrub_value(msg)
        assert result == msg

    def test_scrubs_email(self):
        msg = "Alert sent to trader@example.com"
        result = scrub_value(msg)
        assert "[REDACTED_EMAIL]" in result
        assert "trader@example.com" not in result

    def test_scrubs_phone_number(self):
        msg = "SMS sent to +12065551234"
        result = scrub_value(msg)
        assert "+1[REDACTED]" in result
        assert "2065551234" not in result


class TestScrubProcessor:
    """Test the structlog processor with nested data."""

    def test_scrubs_nested_dict(self):
        event = {
            "event": "api_call",
            "data": {"token": "Bearer abc123def456ghi789jkl012mno345pqr"},
        }
        result = _scrub_processor(None, None, event)
        assert "Bearer [REDACTED]" in result["data"]["token"]

    def test_scrubs_list_values(self):
        event = {
            "event": "test",
            "emails": ["user@example.com", "admin@test.org"],
        }
        result = _scrub_processor(None, None, event)
        assert all("[REDACTED_EMAIL]" in e for e in result["emails"])

    def test_preserves_non_string_values(self):
        event = {"event": "test", "count": 42, "rate": 0.82}
        result = _scrub_processor(None, None, event)
        assert result["count"] == 42
        assert result["rate"] == 0.82
