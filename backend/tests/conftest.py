"""
Lumitrade Test Configuration
===============================
Shared fixtures and fake env vars for test isolation.
No real API calls in unit tests.
"""

import os

# Set fake env vars BEFORE any lumitrade imports
os.environ.setdefault("OANDA_API_KEY_DATA", "test_key_data")
os.environ.setdefault("OANDA_API_KEY_TRADING", "test_key_trading")
os.environ.setdefault("OANDA_ACCOUNT_ID", "test_account")
os.environ.setdefault("OANDA_ENVIRONMENT", "practice")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test_service_key")
os.environ.setdefault("TELNYX_API_KEY", "test_telnyx_key")
os.environ.setdefault("TELNYX_FROM_NUMBER", "+10000000000")
os.environ.setdefault("ALERT_SMS_TO", "+10000000001")
os.environ.setdefault("SENDGRID_API_KEY", "test_sg_key")
os.environ.setdefault("ALERT_EMAIL_TO", "test@test.com")
os.environ.setdefault("INSTANCE_ID", "ci-test")
os.environ.setdefault("TRADING_MODE", "PAPER")
