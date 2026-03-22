



LUMITRADE
Security Specification

ROLE 6 — SENIOR SECURITY DEVELOPER
Version 1.0  |  Financial-grade security for a live trading system
Classification: CONFIDENTIAL — Handle with extreme care
Date: March 20, 2026




# 1. Security Philosophy & Core Principles
Critical Context  Lumitrade has API keys with direct access to a live brokerage account containing real money. A security breach is not just a data leak — it is a financial loss event. Every security control is designed with this in mind.

## 1.1 Security Design Principles

# 2. Complete Threat Model
## 2.1 Asset Inventory

## 2.2 Threat Actor Profiles

## 2.3 Full Attack Surface Analysis

# 3. Secrets Management Implementation
## 3.1 Pre-Commit Hook Setup
The first line of defense against leaked secrets is preventing them from ever entering the Git repository. Pre-commit hooks run automatically before every commit.

# Install pre-commit
pip install pre-commit

# .pre-commit-config.yaml — place in repository root
repos:
- repo: https://github.com/gitleaks/gitleaks
rev: v8.18.2
hooks:
- id: gitleaks
name: Detect hardcoded secrets
description: Scans for secrets before commit

- repo: https://github.com/pre-commit/pre-commit-hooks
rev: v4.6.0
hooks:
- id: detect-private-key
- id: check-added-large-files
args: ["--maxkb=500"]
- id: check-merge-conflict
- id: check-yaml
- id: check-json

# Python security checks
- repo: https://github.com/PyCQA/bandit
rev: 1.7.8
hooks:
- id: bandit
args: ["-r", "backend/lumitrade/", "-ll"]
name: Python security scan

# Install the hooks (run once after cloning):
pre-commit install

# Scan entire git history (run once on existing repo):
gitleaks detect --source . --log-opts="--all"

## 3.2 .gitignore — Security-Critical Entries
# Environment files — NEVER commit
.env
.env.local
.env.*.local
.env.production
.env.staging
*.env

# Key files
*.pem
*.key
*.p12
*.pfx
id_rsa
id_ed25519

# Secrets and credentials
secrets/
credentials/
*credentials*.json
*service-account*.json

# Log files (may contain sensitive data)
logs/
*.log

# Python
__pycache__/
.venv/
*.pyc

# Node
node_modules/
.next/

# OS
.DS_Store
Thumbs.db

## 3.3 .env.example — Required Variables Template
This file IS committed to Git. It documents all required variables without any real values. Every developer and deployment uses this as the reference.

# ── Lumitrade Environment Variables Template ───────────────────
# Copy this to .env and fill in real values
# NEVER commit .env — only .env.example

# OANDA — create at developer.oanda.com
OANDA_API_KEY_DATA=your-read-only-api-key-here
OANDA_API_KEY_TRADING=your-trading-api-key-here
OANDA_ACCOUNT_ID=your-oanda-account-id
OANDA_ENVIRONMENT=practice  # or: live

# Anthropic — console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Supabase — supabase.com project settings
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key  # NEVER expose to browser
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key  # Safe for browser

# Twilio — console.twilio.com
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1XXXXXXXXXX
ALERT_SMS_TO=+1XXXXXXXXXX  # Your phone number

# SendGrid — app.sendgrid.com
SENDGRID_API_KEY=SG.your-key-here
ALERT_EMAIL_TO=your@email.com

# System
INSTANCE_ID=cloud-primary  # or: local-backup
TRADING_MODE=PAPER  # or: LIVE
LOG_LEVEL=INFO
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# 4. Input Validation & Injection Prevention
## 4.1 Database Query Security
All database interactions use the Supabase Python client with parameterized queries. Raw SQL string interpolation is strictly prohibited throughout the codebase.

# infrastructure/db.py — Secure database client wrapper
from supabase import create_client, Client
from ..config import config
from .secure_logger import get_logger

logger = get_logger(__name__)

class DatabaseClient:
"""All database operations go through this class."""

def __init__(self):
self._client: Client | None = None

async def connect(self):
self._client = create_client(
config.supabase_url,
config.supabase_service_key  # Service key — backend only
)

async def insert(self, table: str, data: dict) -> dict:
"""Parameterized insert — never raw SQL."""
result = self._client.table(table).insert(data).execute()
return result.data

async def select(self, table: str, filters: dict,
columns: str = "*",
order: str | None = None,
limit: int | None = None) -> list:
"""Parameterized select with filter dict."""
# NEVER: f"SELECT * FROM {table} WHERE id = {user_input}"
# ALWAYS: parameterized via Supabase client
query = self._client.table(table).select(columns)
for key, value in filters.items():
query = query.eq(key, value)
if order:
query = query.order(order, desc=True)
if limit:
query = query.limit(limit)
result = query.execute()
return result.data

async def select_one(self, table: str, filters: dict) -> dict | None:
rows = await self.select(table, filters, limit=1)
return rows[0] if rows else None

async def update(self, table: str, filters: dict,
data: dict) -> dict:
"""Parameterized update."""
query = self._client.table(table).update(data)
for key, value in filters.items():
query = query.eq(key, value)
result = query.execute()
return result.data

async def upsert(self, table: str, data: dict) -> dict:
result = self._client.table(table).upsert(data).execute()
return result.data

## 4.2 AI Prompt Injection Prevention
The AI brain receives structured market data. However, economic news titles from external APIs could theoretically contain injection attempts. These controls prevent prompt manipulation:

# ai_brain/prompt_builder.py — Injection-safe news formatting

MAX_NEWS_TITLE_LEN = 100
ALLOWED_CHARS      = re.compile(r"[^a-zA-Z0-9 .,\-()%/]")

def _sanitize_news_title(title: str) -> str:
"""
Strip any characters that could be used for prompt injection.
News titles are display data only — no special chars needed.
"""
sanitized = ALLOWED_CHARS.sub("", title)
return sanitized[:MAX_NEWS_TITLE_LEN]

def _format_news(events: list[NewsEvent]) -> str:
"""News is structural data only — never interpolated as instructions."""
lines = []
for e in events:
# Only include: impact level, sanitized title, affected currencies, time
# Structure makes injection semantically impossible
safe_title = _sanitize_news_title(e.title)
currencies = ",".join(c for c in e.currencies_affected if c.isalpha())
lines.append(
f"  [{e.impact.value}] {safe_title} ({currencies}) in {e.minutes_until}m"
)
return "\n".join(lines)

## 4.3 API Response Validation
All external API responses are validated before use. No field from an external source is used without type checking and bounds validation.

# infrastructure/oanda_client.py — Response validation

def _parse_candle(raw: dict) -> Candle:
"""Parse and validate a single OANDA candle response."""
try:
mid = raw["mid"]
return Candle(
time=datetime.fromisoformat(raw["time"].replace("Z", "+00:00")),
open=Decimal(mid["o"]),
high=Decimal(mid["h"]),
low=Decimal(mid["l"]),
close=Decimal(mid["c"]),
volume=int(raw.get("volume", 0)),
complete=bool(raw.get("complete", True)),
timeframe=raw.get("granularity", "M15"),
)
except (KeyError, ValueError, InvalidOperation) as e:
raise DataValidationError(f"Invalid candle data: {e}") from e

def _validate_account_response(data: dict) -> dict:
"""Validate account summary has required fields with sensible values."""
required = ["balance", "equity", "marginUsed"]
for field in required:
if field not in data:
raise DataValidationError(f"Account response missing: {field}")
try:
val = float(data[field])
if val < 0:
raise DataValidationError(f"Negative account field: {field}={val}")
except (ValueError, TypeError) as e:
raise DataValidationError(f"Non-numeric account field {field}: {e}")
return data

# 5. Transport & Network Security
## 5.1 TLS Enforcement
All external communications use TLS 1.2 minimum, TLS 1.3 preferred. Certificate verification is always enabled. There is no exception to this rule — no verify=False anywhere in the codebase.

# infrastructure/oanda_client.py — TLS-enforced HTTP client
import ssl
import httpx

def _create_secure_client(api_key: str,
timeout: float = 10.0) -> httpx.AsyncClient:
"""
Create an HTTPX client with:
- TLS verification always enabled
- TLS 1.2 minimum (1.3 preferred)
- Connection pooling
- Explicit timeout
"""
# Create SSL context with strict settings
ssl_ctx = ssl.create_default_context()
ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
ssl_ctx.verify_mode     = ssl.CERT_REQUIRED
ssl_ctx.check_hostname  = True

return httpx.AsyncClient(
headers={"Authorization": f"Bearer {api_key}",
"Content-Type": "application/json"},
timeout=httpx.Timeout(
connect=5.0,
read=timeout,
write=5.0,
pool=2.0,
),
verify=ssl_ctx,          # NEVER set to False
limits=httpx.Limits(
max_connections=10,
max_keepalive_connections=5,
),
)

## 5.2 Next.js Security Headers
// frontend/next.config.ts — Security headers applied to every response
const securityHeaders = [
// Prevent clickjacking — no iframes allowed
{ key: "X-Frame-Options", value: "DENY" },

// Prevent MIME type sniffing
{ key: "X-Content-Type-Options", value: "nosniff" },

// Strict referrer policy
{ key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },

// Disable dangerous browser features
{ key: "Permissions-Policy",
value: "camera=(), microphone=(), geolocation=(), payment=()" },

// HSTS — force HTTPS for 1 year
{ key: "Strict-Transport-Security",
value: "max-age=31536000; includeSubDomains" },

// Content Security Policy — restrict resource loading
{ key: "Content-Security-Policy",
value: [
"default-src 'self'",
"script-src 'self' 'unsafe-inline'",  // Next.js requires this
"style-src 'self' 'unsafe-inline' fonts.googleapis.com",
"font-src 'self' fonts.gstatic.com",
"connect-src 'self' *.supabase.co wss://*.supabase.co",
"img-src 'self' data:",
"frame-ancestors 'none'",
].join("; ") },
];

# 6. Authentication & Authorization
## 6.1 Dashboard Authentication
The dashboard is protected by Supabase Auth. Phase 0 uses email/password authentication with a single authorized user (the operator). All API routes validate the session token server-side.

// frontend/src/middleware.ts — Protect all dashboard routes
import { createServerClient } from "@supabase/ssr";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_ROUTES = ["/auth/login", "/auth/callback"];

export async function middleware(request: NextRequest) {
const response = NextResponse.next();

const supabase = createServerClient(
process.env.NEXT_PUBLIC_SUPABASE_URL!,
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
{ cookies: {
get: (name) => request.cookies.get(name)?.value,
set: (name, value, options) => {
response.cookies.set({ name, value, ...options });
},
remove: (name, options) => {
response.cookies.set({ name, value: "", ...options });
},
}
}
);

const { data: { session } } = await supabase.auth.getSession();
const isPublic = PUBLIC_ROUTES.some(r =>
request.nextUrl.pathname.startsWith(r));

// Not authenticated + not public route → redirect to login
if (!session && !isPublic) {
return NextResponse.redirect(
new URL("/auth/login", request.url)
);
}

// Authenticated + on login page → redirect to dashboard
if (session && request.nextUrl.pathname === "/auth/login") {
return NextResponse.redirect(
new URL("/dashboard", request.url)
);
}

return response;
}

export const config = {
matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

## 6.2 API Route Authentication
// frontend/src/lib/auth.ts — Server-side auth helper for API routes
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function requireAuth() {
const cookieStore = cookies();
const supabase = createServerClient(
process.env.NEXT_PUBLIC_SUPABASE_URL!,
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
{ cookies: { get: (name) => cookieStore.get(name)?.value } }
);

const { data: { session }, error } = await supabase.auth.getSession();

if (error || !session) {
return {
session: null,
error: NextResponse.json(
{ error: "Unauthorized" },
{ status: 401 }
)
};
}
return { session, error: null };
}

// Usage in every API route:
export async function GET() {
const { session, error } = await requireAuth();
if (error) return error;
// ... rest of handler
}

## 6.3 Supabase Row Level Security
RLS is the final authorization layer. Even if an API route has a bug and returns data without auth checks, RLS ensures a user can only see their own data. The service role key (backend only) bypasses RLS.

-- Verify RLS is working correctly (run in Supabase SQL editor)
-- This should return 0 rows when called with anon role
SET ROLE anon;
SELECT count(*) FROM trades;  -- Should return 0 (no rows without auth)
RESET ROLE;

-- This should return rows when called with service role
SELECT count(*) FROM trades;  -- Returns actual count

# 7. Secure Logging Implementation
## 7.1 Complete SecureLogger with All Patterns
# infrastructure/secure_logger.py — Production implementation
import re
import structlog
import logging
from typing import Any
from ..config import config

# ── Scrub patterns — order matters (most specific first) ────────
SCRUB_PATTERNS: list[tuple[str, str]] = [
# OANDA Bearer tokens
(r"Bearer\s+[A-Za-z0-9\-._]{10,}", "Bearer [REDACTED]"),

# API key patterns in key=value form
(r"(?i)(api[_-]?key|apikey|api_secret)[\s:='"]+[A-Za-z0-9\-._]{10,}",
"api_key=[REDACTED]"),

# Password patterns
(r"(?i)(password|passwd|pwd)[\s:='"]+\S+",
"password=[REDACTED]"),

# Anthropic API keys (sk-ant- prefix)
(r"sk-ant-[A-Za-z0-9\-._]{10,}", "[REDACTED_ANTHROPIC_KEY]"),

# SendGrid keys (SG. prefix)
(r"SG\.[A-Za-z0-9\-._]{10,}", "[REDACTED_SENDGRID_KEY]"),

# Generic long base64-like tokens (40+ chars)
(r"(?<![A-Za-z0-9])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9])",
"[REDACTED_TOKEN]"),

# Phone numbers (E.164 format)
(r"\+1[0-9]{10}", "+1[REDACTED]"),

# Email addresses (in logs — may indicate PII)
(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
"[REDACTED_EMAIL]"),
]

_compiled_patterns = [
(re.compile(p, re.IGNORECASE), r)
for p, r in SCRUB_PATTERNS
]


def scrub_value(value: str) -> str:
"""Apply all scrub patterns to a string value."""
for pattern, replacement in _compiled_patterns:
value = pattern.sub(replacement, value)
return value


def _scrub_processor(logger, method, event_dict: dict) -> dict:
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


def configure_logging():
level = getattr(logging, config.log_level.upper(), logging.INFO)
structlog.configure(
processors=[
structlog.stdlib.filter_by_level,
structlog.stdlib.add_logger_name,
structlog.stdlib.add_log_level,
structlog.processors.TimeStamper(fmt="iso", utc=True),
_scrub_processor,          # SCRUB BEFORE RENDERING
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
return structlog.get_logger(name)

## 7.2 Secure Logger Unit Tests
# tests/unit/test_secure_logger.py
import pytest
from lumitrade.infrastructure.secure_logger import scrub_value

def test_scrubs_bearer_token():
msg = "Authorization: Bearer sk-oanda-abc123def456ghi789jkl012mno345"
result = scrub_value(msg)
assert "Bearer [REDACTED]" in result
assert "sk-oanda" not in result

def test_scrubs_anthropic_key():
msg = "Using key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
result = scrub_value(msg)
assert "[REDACTED_ANTHROPIC_KEY]" in result
assert "sk-ant" not in result

def test_scrubs_api_key_pattern():
msg = "api_key=my-secret-key-1234567890abcdef"
result = scrub_value(msg)
assert "api_key=[REDACTED]" in result

def test_preserves_normal_text():
msg = "Signal generated: EUR/USD BUY confidence=0.82"
result = scrub_value(msg)
assert result == msg  # No change — no sensitive data

def test_scrubs_email():
msg = "Alert sent to trader@example.com"
result = scrub_value(msg)
assert "[REDACTED_EMAIL]" in result
assert "trader@example.com" not in result

def test_scrubs_nested_dict():
from lumitrade.infrastructure.secure_logger import _scrub_processor
event = {"event": "api_call", "data": {"token": "Bearer abc123def456ghi789"}}
result = _scrub_processor(None, None, event)
assert "[REDACTED]" in result["data"]["token"]

# 8. Dependency Security
## 8.1 Python Dependency Pinning with Hash Verification
All Python dependencies are pinned to exact versions with cryptographic hash verification. This prevents supply chain attacks via dependency hijacking or version substitution.

# Generate requirements.txt with hashes (run after any dependency change):
pip install pip-tools
pip-compile --generate-hashes --output-file=requirements.txt requirements.in

# Install with hash verification (used in Docker and CI):
pip install --require-hashes -r requirements.txt

# Example of what a hash-pinned entry looks like:
anthropic==0.25.0 \
--hash=sha256:abc123def456... \
--hash=sha256:789ghi012jkl...

## 8.2 Node.js Dependency Security
# Use npm ci (not npm install) — uses exact versions from package-lock.json
npm ci

# Audit for known vulnerabilities:
npm audit

# Fix automatically where safe:
npm audit fix

# Check for outdated packages monthly:
npm outdated

## 8.3 Automated Vulnerability Scanning
GitHub Dependabot is configured to automatically scan for known vulnerabilities in dependencies and open pull requests when updates are available.

# .github/dependabot.yml
version: 2
updates:
- package-ecosystem: "pip"
directory: "/backend"
schedule:
interval: "weekly"
day: "sunday"
reviewers:
- "yourusername"
labels:
- "security"
- "dependencies"

- package-ecosystem: "npm"
directory: "/frontend"
schedule:
interval: "weekly"
day: "sunday"
reviewers:
- "yourusername"
labels:
- "security"
- "dependencies"

- package-ecosystem: "docker"
directory: "/backend"
schedule:
interval: "monthly"

# 9. Security Audit Checklist
## 9.1 Pre-Launch Security Audit
Complete every item before depositing any real capital. This is the minimum security bar for a live trading system.


## 9.2 Monthly Security Review
- Run gitleaks on any new commits since last review
- Check GitHub Dependabot alerts — address any HIGH or CRITICAL severity
- Review Railway access logs for any unexpected IPs or requests
- Review Supabase auth logs for failed login attempts
- Check OANDA account activity log for any unexpected API usage
- Verify key rotation is on schedule (rotation calendar)
- Test kill switch still functions correctly
- Review Sentry for any new error patterns that could indicate a security issue

## 9.3 Incident Response — Security Breach
If you suspect a key has been leaked  Do not hesitate. Rotate immediately. Cost of rotation: 10 minutes. Cost of delay: entire account.

- IMMEDIATELY activate kill switch — halt all trading
- Rotate the compromised key first (see Section 8.1 of DevOps spec for procedure)
- Check OANDA trade history for any unauthorized trades in last 24 hours
- If unauthorized trades found: contact OANDA support immediately
- Check Anthropic API usage for unexpected consumption (console.anthropic.com)
- Check Twilio logs for unexpected SMS usage
- Run gitleaks on full repo history to understand how the key was exposed
- Review Railway and Supabase access logs from the compromise window
- Document the incident: what was compromised, when discovered, what actions taken
- After all keys rotated and system confirmed clean: resume paper trading first, then live



END OF DOCUMENT
Lumitrade Security Specification v1.0  |  CONFIDENTIAL
Next Document: UI/UX Specification (Role 7)





LUMITRADE
Security Specification

ROLE 6 — SENIOR SECURITY DEVELOPER
All original security controls + future feature threat model
Version 2.0  |  Includes future feature foundations
Date: March 21, 2026




# 1–9. All Original SS Sections
All original Security Specification content is unchanged: security philosophy, threat model, secrets management, input validation, transport security, authentication, secure logging, dependency security, and audit checklist.
Reference  Original SS v1.0 is the authoritative source for all Phase 0 security. This document adds Section 10 only.

# 10. Future Feature Security Requirements
## 10.1 Feature Security Threat Matrix

## 10.2 API Key Security Implementation
When Feature F-14 (Public API) is activated:

# API key generation and storage
import secrets, bcrypt

def generate_api_key() -> tuple[str, str]:
"""Returns (raw_key_for_user, hashed_key_for_db)."""
raw_key = f"lt_{secrets.token_urlsafe(32)}"
hashed  = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
return raw_key, hashed
# raw_key shown to user ONCE — never stored
# hashed stored in api_keys.key_hash

def verify_api_key(raw_key: str, stored_hash: str) -> bool:
return bcrypt.checkpw(raw_key.encode(), stored_hash.encode())

## 10.3 Webhook Security Implementation
When Feature F-14 (Webhooks) is activated:

# Webhook URL validation — prevent SSRF
import ipaddress, socket

PRIVATE_RANGES = [
ipaddress.ip_network("10.0.0.0/8"),
ipaddress.ip_network("172.16.0.0/12"),
ipaddress.ip_network("192.168.0.0/16"),
ipaddress.ip_network("127.0.0.0/8"),
ipaddress.ip_network("::1/128"),
]

def validate_webhook_url(url: str) -> bool:
if not url.startswith("https://"):
return False  # HTTPS required
try:
hostname = url.split("/")[2].split(":")[0]
ip = ipaddress.ip_address(socket.gethostbyname(hostname))
for private_range in PRIVATE_RANGES:
if ip in private_range:
return False  # Block SSRF
return True
except Exception:
return False

## 10.4 Marketplace Fraud Prevention
When Feature F-06 (Strategy Marketplace) is activated:
- All performance statistics are computed server-side by querying the trades table directly. No strategy creator can submit their own performance numbers.
- Strategy must have minimum 90 live trading days before listing. Verified by checking live_since timestamp against minimum age.
- Suspicious patterns that trigger manual review: win rate > 80%, zero losing weeks, equity curve too smooth (may indicate falsified results).
- Stripe webhook signature verified on every payment event before crediting revenue.
- Creator payouts via Stripe Connect — funds never pass through Lumitrade bank account.


# 11. Subagent Security Requirements
Each subagent introduces specific security considerations. All inherit the same Anthropic API key controls, log scrubbing, and error isolation as the main system.
## 11.1 Subagent Threat Model
SA-01 Market Analyst:
Threat: Prompt injection via manipulated market data
Control: All market data sanitized before insertion into prompt.
Numeric values only — no raw text from external sources.

SA-02 Post-Trade Analyst:
Threat: AI reasoning from previous signal contains injected content
Control: AI reasoning text treated as untrusted — sanitized via
_sanitize_text() before inclusion in analyst prompt.

SA-03 Risk Monitor:
Threat: Monitor recommendation to close triggering unauthorized action
Control: SA-03 NEVER auto-closes positions. It only creates log entries
and sends alerts. All action requires operator decision.
This constraint is hardcoded, not configurable.

SA-04 Intelligence Subagent:
Threat: Malicious news headline injecting instructions
Control: Headlines truncated to 200 chars. Special chars stripped.
_sanitize_news_title() applied to every headline.
No URLs from news content are fetched or executed.

SA-05 Onboarding Agent:
Threat: User attempting to extract system prompt or config via chat
Control: System prompt never echoed. Config values never included
in onboarding conversation. Agent only discusses setup topics.
Rate limited: 20 messages per onboarding session maximum.
## 11.2 Shared Subagent Security Controls
1. All subagents use the same ANTHROPIC_API_KEY — no separate keys needed.
2. All subagent responses scrubbed through SecureLogger before storage.
3. All subagents timeout at 30 seconds — never block indefinitely.
4. All subagent exceptions caught and logged — never propagate to main loop.
5. All subagent DB writes use parameterized queries via DatabaseClient.
6. Subagent API usage logged to ai_interaction_log with agent_type field.
## 11.3 SA-03 Risk Monitor Hard Constraint
CRITICAL  The Risk Monitor subagent must NEVER automatically close, modify, or affect any trading position. Its only outputs are: (1) database log entry, (2) dashboard notification, (3) SMS alert. All trade decisions remain with the operator. This constraint is non-negotiable and must be enforced in code review.

| Attribute | Value |
|---|---|
| Document | Security Specification (SS) |
| Security classification | Confidential — contains threat model and control details |
| Scope | All Lumitrade components: backend engine, frontend dashboard, infrastructure, CI/CD |
| Risk level | HIGH — system has direct access to real brokerage account and capital |
| Regulatory context | Personal trading automation tool — not a registered investment advisor |
| Next document | UI/UX Specification (Role 7) |


| Principle | Application in Lumitrade |
|---|---|
| Least privilege | Every component gets only the permissions it needs. Data engine: read-only OANDA key. Execution engine: trading key. Frontend: anon Supabase key with RLS. No component has more access than required. |
| Defense in depth | Multiple independent security layers. If one fails, others catch it. IP whitelist + TLS + key isolation + RLS + log scrubbing — an attacker must defeat all layers simultaneously. |
| Fail secure | On any authentication failure, connection error, or ambiguous state — the system defaults to the safe action (halt trading, reject order, log and alert). Never default to permissive. |
| Zero trust | No component trusts another by default. All inter-component communication is validated. Database queries use typed parameters. No raw string interpolation in queries. |
| Audit everything | Every sensitive operation — order placement, key usage, config change, kill switch activation — generates an immutable, timestamped log record. The audit trail is the ground truth. |
| Secrets never travel | API keys exist only in environment variables and secrets managers. Never in code, logs, error messages, database records, HTTP responses, or Git history. |


| Asset | Sensitivity | Impact if Compromised |
|---|---|---|
| OANDA trading API key | CRITICAL | Attacker can place trades, drain account, manipulate positions |
| OANDA data API key | HIGH | Attacker can read all price data and account details |
| Anthropic API key | HIGH | Attacker can run expensive AI queries on your bill |
| Supabase service key | CRITICAL | Attacker has full database read/write — all trades, all state |
| Supabase anon key | MEDIUM | Limited by RLS policies — exposure still requires rotation |
| Twilio credentials | MEDIUM | Attacker can send SMS from your number, intercept alerts |
| SendGrid API key | MEDIUM | Attacker can send email from your domain, intercept reports |
| Trade history data | MEDIUM | Financial records — privacy concern, strategy exposure |
| System state data | HIGH | Attacker knows open positions, can front-run or manipulate |
| AI prompt content | LOW | Market data and analysis — not personally sensitive |
| Source code | MEDIUM | Reveals system logic, potential vulnerability discovery |


| Actor | Motivation | Capability |
|---|---|---|
| Automated scanner | Opportunistic credential harvesting from public repos | Low — script-based, exploits known patterns like hardcoded keys |
| Compromised dependency | Supply chain attack via malicious npm or PyPI package | Medium — code execution in the trading engine process |
| Phishing/social engineering | Credential theft targeting the operator | Low-Medium — targets human, not technical controls |
| Compromised cloud server | Full access to running process and environment | High — if Railway instance is compromised, all env vars exposed |
| Insider threat (future SaaS) | Malicious employee or contractor with codebase access | Medium — mitigated by secrets manager, not hardcoded keys |
| Prompt injection via data | Malicious content in market data feeds manipulates AI | Low — structured numeric data, not natural language input |


| Attack Vector | Threat | Likelihood | Controls |
|---|---|---|---|
| API key in source code | Key committed to GitHub — automated scanners find it within minutes | HIGH if not controlled | Pre-commit gitleaks hook. .gitignore. No keys in any file. GitHub secret scanning enabled. |
| API key in environment variable leak | Key appears in logs, crash reports, or error messages | MEDIUM | SecureLogger scrubber on all output. Sentry before_send scrubber. No env var dumping in error handlers. |
| Compromised Railway instance | Attacker gains shell access — reads all env vars | LOW | IP whitelist on OANDA (only Railway IP). Separate data/trading keys. Blast radius limited. |
| Man-in-the-middle (HTTPS) | Intercept API calls to OANDA or Anthropic | VERY LOW | TLS 1.3 enforced. Certificate validation on all connections. Never verify=False. |
| Dependency supply chain attack | Malicious package injected via PyPI or npm | LOW-MEDIUM | All deps pinned with exact versions and hash verification. requirements.txt --require-hashes. |
| Runaway trading (logic bug) | Bug causes excessive orders, drains account | MEDIUM | Daily/weekly loss limits. Max position count. Circuit breaker. Kill switch. All independent layers. |
| Database breach (Supabase) | Attacker reads all trade history and state | LOW | Encryption at rest by Supabase. RLS policies. Service key only on backend. No credentials in DB. |
| Brute force dashboard login | Attacker guesses credentials to access dashboard | LOW | Supabase Auth rate limiting. Strong password policy. No default credentials. |
| Prompt injection via market data | Attacker embeds instructions in financial news feed | VERY LOW | Market data is structured OHLCV numbers — not natural language. News is for calendar only, not injected into prompt as-is. |
| Session hijacking (dashboard) | Attacker steals session token from browser | LOW | Supabase Auth JWT with short expiry. HTTPS only. Secure + HttpOnly cookie flags. |
| OANDA API rate limit abuse | Bug causes excessive API calls — rate limited or banned | LOW-MEDIUM | Circuit breaker. Exponential backoff. Scan interval minimum enforced. Request queue. |
| Git history exposure | Old API key removed from code but visible in git history | MEDIUM if rotation not done | gitleaks full history scan before any public repo. Key rotation immediately after any suspected exposure. |


| Category | Audit Item | Verified |
|---|---|---|
| Secrets | gitleaks full history scan returns zero findings | [ ] |
| Secrets | GitHub secret scanning enabled on repository | [ ] |
| Secrets | pre-commit hook installed and tested (commit a fake key — should be blocked) | [ ] |
| Secrets | All .env files confirmed in .gitignore | [ ] |
| Secrets | No secrets in any GitHub Actions workflow files (use ${{ secrets.X }}) | [ ] |
| Secrets | All 6 API keys confirmed as Railway env vars (not in code) | [ ] |
| OANDA | Read-only key assigned to data engine only (confirmed in code) | [ ] |
| OANDA | Trading key assigned to execution engine only (confirmed in code) | [ ] |
| OANDA | IP whitelist active — test from non-whitelisted IP confirms rejection | [ ] |
| OANDA | 2FA enabled on OANDA web portal account | [ ] |
| TLS | curl -v confirms TLS 1.3 on all OANDA API calls | [ ] |
| TLS | No verify=False anywhere in codebase (grep confirmed) | [ ] |
| Logging | Test log with embedded API key — confirm scrubbed in Railway logs | [ ] |
| Logging | Test log with email address — confirm scrubbed | [ ] |
| Logging | Sentry before_send scrubber confirmed working (test error sent) | [ ] |
| Database | Supabase RLS confirmed active on all 7 tables | [ ] |
| Database | Anon key confirmed cannot read data without auth | [ ] |
| Database | Service key confirmed NOT in any frontend code or env vars | [ ] |
| Frontend | Security headers confirmed via securityheaders.com scan | [ ] |
| Frontend | CSP blocks loading from unauthorized domains (test with devtools) | [ ] |
| Frontend | Dashboard login page tested — invalid credentials rejected | [ ] |
| Frontend | API routes tested without auth — confirm 401 returned | [ ] |
| Dependencies | npm audit returns zero high/critical vulnerabilities | [ ] |
| Dependencies | pip-audit returns zero known vulnerabilities | [ ] |
| Dependencies | All Python deps have hash verification (requirements.txt) | [ ] |
| Docker | Container runs as non-root user (confirmed: whoami = lumitrade) | [ ] |
| Kill Switch | Kill switch requires typed confirmation — tested that single click does nothing | [ ] |


| Attribute | Value |
|---|---|
| Version | 2.0 — future feature threat model and security requirements per feature |
| New threats added | Marketplace manipulation, copy trading fraud, API key abuse, fund misappropriation |
| New security controls | API key hashing, webhook secret validation, Stripe webhook verification, fund audit trail |
| Compliance additions | Copy trading legal notes, fund regulatory requirements, marketplace fraud prevention |


| Feature | New Threat | Likelihood | Control |
|---|---|---|---|
| F-01 Multi-Model AI | OpenAI key exposure | Medium | Same rules as Anthropic key: env var only, scrubbed from logs, rotated 90 days |
| F-03 News Sentiment | News API key abuse | Low | Env var only. Cache responses 30 min to minimize API calls. Rate limit enforced. |
| F-06 Marketplace | Fake performance data | High | All strategy stats computed server-side from audited OANDA records. No self-reported data accepted. |
| F-06 Marketplace | Stripe webhook spoofing | High | Verify Stripe-Signature header on every webhook. Reject unverified requests with 401. |
| F-07 Copy Trading | Unauthorized copying | Medium | copy_relationships table with RLS. Leader must explicitly opt-in. Follower pays before signals flow. |
| F-07 Copy Trading | Front-running | High | Copy signals delivered simultaneously to all followers. No sequential delivery that enables front-running. |
| F-08 AI Coach | Trade history exposure | Medium | Coach context limited to authenticated account_id. RLS enforced. No cross-account data accessible. |
| F-14 Public API | API key brute force | Medium | Keys are 32-byte random tokens stored as bcrypt hash. Rate limiting: 100 req/min per key. Key revocation immediate. |
| F-14 Webhooks | SSRF via webhook URL | High | Validate webhook URLs: must be HTTPS, no private IP ranges (10.x, 192.168.x, 172.16.x, localhost). DNS validation on registration. |
| F-15 Fund | Misappropriation of investor capital | Critical | Fund accounts held at regulated custodian (not Lumitrade). Lumitrade only holds API keys for trading. Full audit trail required. |
